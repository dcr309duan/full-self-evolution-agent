"""core/coordinated_mutation_runner.py

A runner that executes coordinated mutations atomically across multiple modules.
Uses only standard library. Accepts a list of mutation plans, applies them in
sequence with rollback on first failure, and reports success/failure per mutation
and overall.
"""

import copy
import os
import sys
from typing import Any, Dict, List, Optional, Tuple


class CoordinatedMutationRunner:
    """Executes a sequence of coordinated mutations atomically with rollback."""

    def __init__(self, base_dir: Optional[str] = None):
        """Initialize the runner.

        Args:
            base_dir: Base directory for file operations. If None, uses current
                      working directory.
        """
        self.base_dir = base_dir or os.getcwd()
        self._backups: Dict[str, Optional[str]] = {}
        self._applied_plans: List[Dict[str, Any]] = []

    def execute_plans(
        self, plans: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Execute a list of mutation plans atomically.

        Each plan is a dict with keys:
            - 'file': str, relative path to the file to mutate
            - 'action': str, one of 'replace', 'insert', 'delete', 'modify'
            - 'content': str (for replace/insert), the new content
            - 'position': int (for insert/modify), line number (0-indexed)
            - 'old_content': str (for replace/modify), the content to replace
            - 'new_content': str (for replace/modify), the replacement content

        Args:
            plans: List of mutation plan dictionaries.

        Returns:
            List of result dictionaries, one per plan, with keys:
                - 'plan': the original plan dict
                - 'success': bool
                - 'error': str or None
            The overall result is implied: if any plan fails, all prior
            mutations are rolled back.
        """
        results: List[Dict[str, Any]] = []
        self._backups.clear()
        self._applied_plans.clear()

        for plan in plans:
            result = self._apply_single_plan(plan)
            results.append(result)

            if not result["success"]:
                # Rollback all successfully applied plans in reverse order
                self._rollback_all()
                return results

        # All succeeded – clear backups (no rollback needed)
        self._backups.clear()
        self._applied_plans.clear()
        return results

    def _apply_single_plan(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        """Apply a single mutation plan.

        Args:
            plan: Mutation plan dictionary.

        Returns:
            Result dictionary with 'plan', 'success', 'error'.
        """
        file_path = plan.get("file", "")
        if not file_path:
            return {"plan": plan, "success": False, "error": "No file specified"}

        abs_path = os.path.join(self.base_dir, file_path)
        if not os.path.exists(abs_path):
            return {
                "plan": plan,
                "success": False,
                "error": f"File not found: {abs_path}",
            }

        action = plan.get("action", "")
        if action not in ("replace", "insert", "delete", "modify"):
            return {
                "plan": plan,
                "success": False,
                "error": f"Unknown action: {action}",
            }

        try:
            # Read original content
            with open(abs_path, "r", encoding="utf-8") as f:
                original_content = f.read()

            # Backup original content if not already backed up
            if abs_path not in self._backups:
                self._backups[abs_path] = original_content

            # Apply the mutation
            if action == "replace":
                new_content = plan.get("content", "")
                if not new_content:
                    return {
                        "plan": plan,
                        "success": False,
                        "error": "No content provided for replace action",
                    }
                with open(abs_path, "w", encoding="utf-8") as f:
                    f.write(new_content)

            elif action == "insert":
                content_to_insert = plan.get("content", "")
                position = plan.get("position", 0)
                lines = original_content.splitlines(True)
                if position < 0 or position > len(lines):
                    return {
                        "plan": plan,
                        "success": False,
                        "error": f"Invalid position {position} for insert",
                    }
                lines.insert(position, content_to_insert)
                with open(abs_path, "w", encoding="utf-8") as f:
                    f.writelines(lines)

            elif action == "delete":
                position = plan.get("position", 0)
                lines = original_content.splitlines(True)
                if position < 0 or position >= len(lines):
                    return {
                        "plan": plan,
                        "success": False,
                        "error": f"Invalid position {position} for delete",
                    }
                del lines[position]
                with open(abs_path, "w", encoding="utf-8") as f:
                    f.writelines(lines)

            elif action == "modify":
                old_content = plan.get("old_content", "")
                new_content = plan.get("new_content", "")
                if old_content not in original_content:
                    return {
                        "plan": plan,
                        "success": False,
                        "error": "old_content not found in file",
                    }
                modified = original_content.replace(old_content, new_content, 1)
                with open(abs_path, "w", encoding="utf-8") as f:
                    f.write(modified)

            # Record successful application
            self._applied_plans.append(plan)
            return {"plan": plan, "success": True, "error": None}

        except Exception as e:
            return {
                "plan": plan,
                "success": False,
                "error": f"Exception during mutation: {str(e)}",
            }

    def _rollback_all(self) -> None:
        """Rollback all applied mutations in reverse order."""
        # Restore files from backups in reverse order of application
        restored_files = set()
        for plan in reversed(self._applied_plans):
            file_path = plan.get("file", "")
            if not file_path:
                continue
            abs_path = os.path.join(self.base_dir, file_path)
            if abs_path in self._backups and abs_path not in restored_files:
                original_content = self._backups[abs_path]
                try:
                    with open(abs_path, "w", encoding="utf-8") as f:
                        f.write(original_content)
                    restored_files.add(abs_path)
                except Exception:
                    # If rollback fails, we log but continue trying others
                    print(
                        f"Warning: Failed to rollback {abs_path}",
                        file=sys.stderr,
                    )

        self._backups.clear()
        self._applied_plans.clear()

    def dry_run(self, plans: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Simulate execution without modifying any files.

        Args:
            plans: List of mutation plan dictionaries.

        Returns:
            List of result dictionaries indicating expected success/failure.
        """
        results = []
        for plan in plans:
            file_path = plan.get("file", "")
            if not file_path:
                results.append(
                    {"plan": plan, "success": False, "error": "No file specified"}
                )
                continue

            abs_path = os.path.join(self.base_dir, file_path)
            if not os.path.exists(abs_path):
                results.append(
                    {
                        "plan": plan,
                        "success": False,
                        "error": f"File not found: {abs_path}",
                    }
                )
                continue

            action = plan.get("action", "")
            if action not in ("replace", "insert", "delete", "modify"):
                results.append(
                    {
                        "plan": plan,
                        "success": False,
                        "error": f"Unknown action: {action}",
                    }
                )
                continue

            # Additional validation checks
            if action == "replace" and not plan.get("content", ""):
                results.append(
                    {
                        "plan": plan,
                        "success": False,
                        "error": "No content provided for replace action",
                    }
                )
                continue

            if action in ("insert", "delete"):
                position = plan.get("position", 0)
                try:
                    with open(abs_path, "r", encoding="utf-8") as f:
                        lines = f.readlines()
                except Exception as e:
                    results.append(
                        {
                            "plan": plan,
                            "success": False,
                            "error": f"Cannot read file: {str(e)}",
                        }
                    )
                    continue

                if position < 0 or position > len(lines):
                    results.append(
                        {
                            "plan": plan,
                            "success": False,
                            "error": f"Invalid position {position}",
                        }
                    )
                    continue

            if action == "modify":
                old_content = plan.get("old_content", "")
                if not old_content:
                    results.append(
                        {
                            "plan": plan,
                            "success": False,
                            "error": "No old_content provided for modify action",
                        }
                    )
                    continue
                try:
                    with open(abs_path, "r", encoding="utf-8") as f:
                        content = f.read()
                except Exception as e:
                    results.append(
                        {
                            "plan": plan,
                            "success": False,
                            "error": f"Cannot read file: {str(e)}",
                        }
                    )
                    continue
                if old_content not in content:
                    results.append(
                        {
                            "plan": plan,
                            "success": False,
                            "error": "old_content not found in file",
                        }
                    )
                    continue

            results.append({"plan": plan, "success": True, "error": None})

        return results


# Convenience function for quick use
def run_coordinated_mutations(
    plans: List[Dict[str, Any]], base_dir: Optional[str] = None
) -> Tuple[bool, List[Dict[str, Any]]]:
    """Execute coordinated mutations and return overall success and results.

    Args:
        plans: List of mutation plan dictionaries.
        base_dir: Base directory for file operations.

    Returns:
        Tuple of (overall_success, results_list).
    """
    runner = CoordinatedMutationRunner(base_dir)
    results = runner.execute_plans(plans)
    overall_success = all(r["success"] for r in results)
    return overall_success, results