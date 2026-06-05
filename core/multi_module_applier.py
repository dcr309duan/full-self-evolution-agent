import json
import os
import subprocess
import sys
import tempfile
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Tuple


class MultiModuleApplier:
    """
    A self-contained module that applies coordinated changes to multiple files
    in a single atomic git operation. Reads a mutation plan from JSON and
    either commits all changes or rolls back completely on failure.
    """

    def __init__(self, repo_path: str = "."):
        self.repo_path = os.path.abspath(repo_path)
        self._original_contents: Dict[str, str] = {}
        self._stashed_changes: bool = False
        self._temp_dir: Optional[str] = None

    def _run_git(self, args: List[str], check: bool = True) -> subprocess.CompletedProcess:
        """Run a git command in the repository directory."""
        cmd = ["git"] + args
        return subprocess.run(
            cmd,
            cwd=self.repo_path,
            capture_output=True,
            text=True,
            check=check,
        )

    def _ensure_clean_working_tree(self) -> bool:
        """Check if working tree is clean. Returns True if clean."""
        result = self._run_git(["status", "--porcelain"], check=False)
        return result.stdout.strip() == ""

    def _stash_current_changes(self) -> bool:
        """Stash any uncommitted changes. Returns True if stashed."""
        if self._ensure_clean_working_tree():
            return False
        result = self._run_git(["stash", "--include-untracked"], check=False)
        if result.returncode == 0:
            self._stashed_changes = True
            return True
        return False

    def _pop_stash(self) -> bool:
        """Restore previously stashed changes. Returns True on success."""
        if not self._stashed_changes:
            return True
        result = self._run_git(["stash", "pop"], check=False)
        if result.returncode == 0:
            self._stashed_changes = False
            return True
        return False

    def _backup_files(self, file_paths: List[str]) -> bool:
        """Backup current contents of files before modification."""
        self._original_contents = {}
        for file_path in file_paths:
            abs_path = os.path.join(self.repo_path, file_path)
            if os.path.exists(abs_path):
                try:
                    with open(abs_path, "r", encoding="utf-8") as f:
                        self._original_contents[file_path] = f.read()
                except (IOError, OSError) as e:
                    print(f"Error backing up {file_path}: {e}", file=sys.stderr)
                    return False
        return True

    def _restore_files(self) -> bool:
        """Restore all files to their original contents."""
        success = True
        for file_path, content in self._original_contents.items():
            abs_path = os.path.join(self.repo_path, file_path)
            try:
                os.makedirs(os.path.dirname(abs_path), exist_ok=True)
                with open(abs_path, "w", encoding="utf-8") as f:
                    f.write(content)
            except (IOError, OSError) as e:
                print(f"Error restoring {file_path}: {e}", file=sys.stderr)
                success = False
        return success

    def _apply_file_change(self, file_path: str, new_content: str) -> bool:
        """Write new content to a file, creating directories if needed."""
        abs_path = os.path.join(self.repo_path, file_path)
        try:
            os.makedirs(os.path.dirname(abs_path), exist_ok=True)
            with open(abs_path, "w", encoding="utf-8") as f:
                f.write(new_content)
            return True
        except (IOError, OSError) as e:
            print(f"Error writing {file_path}: {e}", file=sys.stderr)
            return False

    def _stage_files(self, file_paths: List[str]) -> bool:
        """Stage all modified files for commit."""
        try:
            self._run_git(["add"] + file_paths)
            return True
        except subprocess.CalledProcessError as e:
            print(f"Error staging files: {e.stderr}", file=sys.stderr)
            return False

    def _create_commit(self, message: str) -> bool:
        """Create a git commit with the given message."""
        try:
            self._run_git(["commit", "-m", message])
            return True
        except subprocess.CalledProcessError as e:
            print(f"Error creating commit: {e.stderr}", file=sys.stderr)
            return False

    def _rollback(self, file_paths: List[str]) -> bool:
        """Rollback all changes: restore files and pop stash."""
        success = True

        # Restore original file contents
        if not self._restore_files():
            print("Warning: Failed to restore some files", file=sys.stderr)
            success = False

        # Unstage any staged changes
        try:
            self._run_git(["reset", "HEAD"] + file_paths, check=False)
        except subprocess.CalledProcessError:
            pass  # Non-fatal if nothing was staged

        # Pop the stash if we created one
        if not self._pop_stash():
            print("Warning: Failed to restore stashed changes", file=sys.stderr)
            success = False

        return success

    def apply_plan(self, plan_file: str) -> bool:
        """
        Apply a coordinated mutation plan from a JSON file atomically.

        The JSON plan should have the structure:
        {
            "files": {
                "path/to/file1.py": "new content as string",
                "path/to/file2.py": "new content as string"
            },
            "commit_message": "Description of changes"
        }

        Returns True if all changes were applied and committed successfully.
        Returns False if any change failed (all changes rolled back).
        """
        # Read and parse the plan
        try:
            with open(plan_file, "r", encoding="utf-8") as f:
                plan = json.load(f)
        except (IOError, json.JSONDecodeError) as e:
            print(f"Error reading plan file: {e}", file=sys.stderr)
            return False

        # Validate plan structure
        if not isinstance(plan, dict) or "files" not in plan:
            print("Invalid plan: missing 'files' key", file=sys.stderr)
            return False

        files = plan["files"]
        commit_message = plan.get("commit_message", "Coordinated mutation applied")

        if not isinstance(files, dict) or len(files) == 0:
            print("Invalid plan: 'files' must be a non-empty dictionary", file=sys.stderr)
            return False

        file_paths = list(files.keys())

        # Ensure we're in a git repository
        if not os.path.exists(os.path.join(self.repo_path, ".git")):
            print(f"Not a git repository: {self.repo_path}", file=sys.stderr)
            return False

        # Stash any existing uncommitted changes
        self._stash_current_changes()

        # Backup current file contents
        if not self._backup_files(file_paths):
            print("Failed to backup files", file=sys.stderr)
            self._pop_stash()
            return False

        # Apply all file changes
        success = True
        for file_path, new_content in files.items():
            if not self._apply_file_change(file_path, new_content):
                success = False
                break

        if not success:
            print("Failed to apply changes, rolling back...", file=sys.stderr)
            self._rollback(file_paths)
            return False

        # Stage all changed files
        if not self._stage_files(file_paths):
            print("Failed to stage files, rolling back...", file=sys.stderr)
            self._rollback(file_paths)
            return False

        # Create the commit
        if not self._create_commit(commit_message):
            print("Failed to create commit, rolling back...", file=sys.stderr)
            self._rollback(file_paths)
            return False

        # Pop the stash if we created one (changes are now committed)
        if not self._pop_stash():
            print("Warning: Failed to restore stashed changes", file=sys.stderr)
            # Don't rollback the commit, but warn the user

        print(f"Successfully applied coordinated mutation: {commit_message}")
        return True


def main():
    """CLI entry point for applying a mutation plan."""
    if len(sys.argv) < 2:
        print("Usage: python multi_module_applier.py <plan_file.json>", file=sys.stderr)
        sys.exit(1)

    plan_file = sys.argv[1]
    repo_path = sys.argv[2] if len(sys.argv) > 2 else "."

    applier = MultiModuleApplier(repo_path)
    success = applier.apply_plan(plan_file)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()