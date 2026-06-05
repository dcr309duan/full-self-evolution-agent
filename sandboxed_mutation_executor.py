import os
import sys
import json
import shutil
import tempfile
import subprocess
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

class SandboxedMutationExecutor:
    """
    Executes mutations in a sandboxed environment to safely test changes before promotion.
    """

    CORE_MODULES = [
        "mutation_engine.py",
        "evolution_orchestrator.py",
        "dependency_graph.py"
    ]

    def __init__(self, project_root: str, log_file: str = "mutation_log.json"):
        self.project_root = Path(project_root).resolve()
        self.log_file = Path(log_file).resolve()
        self.temp_dir: Optional[tempfile.TemporaryDirectory] = None
        self.cloned_dir: Optional[Path] = None

    def execute_mutation(self, mutation_spec: Dict) -> bool:
        """
        Execute a mutation in a sandboxed environment.

        Args:
            mutation_spec: Dictionary containing:
                - 'target_files': List of file paths to modify
                - 'diff': String containing the unified diff to apply
                - 'test_pattern': Optional test discovery pattern

        Returns:
            True if mutation was promoted, False if rolled back.
        """
        target_files = mutation_spec.get("target_files", [])
        diff_content = mutation_spec.get("diff", "")
        test_pattern = mutation_spec.get("test_pattern", "test_*.py")

        if not target_files or not diff_content:
            logger.error("Mutation spec missing target_files or diff")
            return False

        # Step 1: Create sandbox
        if not self._create_sandbox():
            return False

        try:
            # Step 2: Clone core modules
            if not self._clone_core_modules():
                self._rollback()
                return False

            # Step 3: Apply mutation
            if not self._apply_mutation(target_files, diff_content):
                self._rollback()
                return False

            # Step 4: Run tests
            test_passed, test_output = self._run_tests(test_pattern)

            # Step 5: Handle result
            if test_passed:
                self._promote(target_files)
                self._log_success(mutation_spec, test_output)
                return True
            else:
                self._log_failure(mutation_spec, test_output)
                self._rollback()
                return False

        except Exception as e:
            logger.error(f"Unexpected error during mutation execution: {e}")
            self._rollback()
            return False

    def _create_sandbox(self) -> bool:
        """Create a temporary directory for sandboxed execution."""
        try:
            self.temp_dir = tempfile.TemporaryDirectory(prefix="mutation_sandbox_")
            self.cloned_dir = Path(self.temp_dir.name) / "cloned_modules"
            self.cloned_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"Created sandbox at {self.temp_dir.name}")
            return True
        except Exception as e:
            logger.error(f"Failed to create sandbox: {e}")
            return False

    def _clone_core_modules(self) -> bool:
        """Clone core modules into the sandbox."""
        try:
            for module in self.CORE_MODULES:
                src = self.project_root / module
                dst = self.cloned_dir / module
                if src.exists():
                    shutil.copy2(src, dst)
                    logger.info(f"Cloned {module} to sandbox")
                else:
                    logger.warning(f"Core module {module} not found at {src}")
            return True
        except Exception as e:
            logger.error(f"Failed to clone core modules: {e}")
            return False

    def _apply_mutation(self, target_files: List[str], diff_content: str) -> bool:
        """Apply the mutation diff to the cloned files."""
        try:
            # Write diff to a temporary file
            diff_file = Path(self.temp_dir.name) / "mutation.diff"
            diff_file.write_text(diff_content)

            # Apply patch using git apply or patch command
            result = subprocess.run(
                ["git", "apply", "--directory", str(self.cloned_dir), str(diff_file)],
                capture_output=True,
                text=True,
                cwd=self.project_root
            )

            if result.returncode != 0:
                # Fallback to patch command
                result = subprocess.run(
                    ["patch", "-d", str(self.cloned_dir), "-p1", "-i", str(diff_file)],
                    capture_output=True,
                    text=True
                )

            if result.returncode != 0:
                logger.error(f"Failed to apply mutation: {result.stderr}")
                return False

            logger.info("Mutation applied successfully")
            return True

        except Exception as e:
            logger.error(f"Error applying mutation: {e}")
            return False

    def _run_tests(self, test_pattern: str) -> Tuple[bool, str]:
        """Run tests related to the modified modules."""
        try:
            # Discover and run tests
            test_command = [
                sys.executable, "-m", "pytest",
                "--tb=short",
                "--no-header",
                "-q",
                f"--rootdir={self.cloned_dir}",
                f"--ignore={self.cloned_dir / '.git'}",
                f"-k={test_pattern}",
                str(self.cloned_dir)
            ]

            result = subprocess.run(
                test_command,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )

            test_output = f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
            test_passed = result.returncode == 0

            if test_passed:
                logger.info("All tests passed")
            else:
                logger.error(f"Tests failed with exit code {result.returncode}")

            return test_passed, test_output

        except subprocess.TimeoutExpired:
            logger.error("Test execution timed out")
            return False, "Test execution timed out after 5 minutes"
        except Exception as e:
            logger.error(f"Error running tests: {e}")
            return False, str(e)

    def _promote(self, target_files: List[str]) -> None:
        """Copy modified files back to the live directory."""
        try:
            for file_path in target_files:
                src = self.cloned_dir / file_path
                dst = self.project_root / file_path
                if src.exists():
                    shutil.copy2(src, dst)
                    logger.info(f"Promoted {file_path} to live directory")
                else:
                    logger.warning(f"Modified file {file_path} not found in sandbox")
        except Exception as e:
            logger.error(f"Error during promotion: {e}")

    def _rollback(self) -> None:
        """Clean up the sandbox directory."""
        try:
            if self.temp_dir:
                self.temp_dir.cleanup()
                self.temp_dir = None
                self.cloned_dir = None
                logger.info("Sandbox cleaned up (rollback completed)")
        except Exception as e:
            logger.error(f"Error during rollback: {e}")

    def _log_success(self, mutation_spec: Dict, test_output: str) -> None:
        """Log successful mutation execution."""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "status": "SUCCESS",
            "mutation_spec": mutation_spec,
            "test_output": test_output[:500],  # Truncate to avoid huge logs
            "promoted": True
        }
        self._append_to_log(log_entry)

    def _log_failure(self, mutation_spec: Dict, test_output: str) -> None:
        """Log failed mutation execution with full context."""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "status": "FAILURE",
            "mutation_spec": mutation_spec,
            "test_output": test_output,
            "diff": mutation_spec.get("diff", ""),
            "rolled_back": True
        }
        self._append_to_log(log_entry)

    def _append_to_log(self, log_entry: Dict) -> None:
        """Append a log entry to the JSON log file."""
        try:
            # Ensure log directory exists
            self.log_file.parent.mkdir(parents=True, exist_ok=True)

            # Read existing log
            existing_logs = []
            if self.log_file.exists():
                with open(self.log_file, 'r') as f:
                    try:
                        existing_logs = json.load(f)
                    except json.JSONDecodeError:
                        existing_logs = []

            # Append new entry
            existing_logs.append(log_entry)

            # Write back
            with open(self.log_file, 'w') as f:
                json.dump(existing_logs, f, indent=2)

            logger.info(f"Logged mutation result to {self.log_file}")

        except Exception as e:
            logger.error(f"Failed to write log entry: {e}")


# Convenience function for simple usage
def execute_mutation(mutation_spec: Dict, project_root: str = ".") -> bool:
    """
    Convenience function to execute a mutation in a sandboxed environment.

    Args:
        mutation_spec: Dictionary with mutation specification
        project_root: Root directory of the project

    Returns:
        True if mutation was promoted, False otherwise
    """
    executor = SandboxedMutationExecutor(project_root)
    return executor.execute_mutation(mutation_spec)


if __name__ == "__main__":
    # Example usage
    logging.basicConfig(level=logging.INFO)

    sample_mutation = {
        "target_files": ["mutation_engine.py"],
        "diff": """--- a/mutation_engine.py
+++ b/mutation_engine.py
@@ -1,5 +1,6 @@
 def mutate(code):
-    return code.upper()
+    # Test mutation
+    return code.lower()
""",
        "test_pattern": "test_mutation_engine"
    }

    success = execute_mutation(sample_mutation, project_root=".")
    print(f"Mutation {'promoted' if success else 'rolled back'}")