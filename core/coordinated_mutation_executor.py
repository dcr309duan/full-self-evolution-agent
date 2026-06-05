import os
import shutil
import tempfile
import ast
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field


@dataclass
class FileChange:
    """Represents a single file change in a coordinated mutation plan."""
    file_path: str
    new_content: str


@dataclass
class CoordinatedMutationPlan:
    """A coordinated mutation plan consisting of multiple file changes."""
    changes: List[FileChange] = field(default_factory=list)
    integration_test_command: Optional[str] = None
    test_working_dir: Optional[str] = None


@dataclass
class ValidationResult:
    """Result of validating a single modified file."""
    file_path: str
    is_valid: bool
    error_message: Optional[str] = None


@dataclass
class ExecutionResult:
    """Overall result of executing a coordinated mutation plan."""
    success: bool
    applied_changes: List[str] = field(default_factory=list)
    failed_validations: List[ValidationResult] = field(default_factory=list)
    integration_test_passed: bool = False
    integration_test_output: Optional[str] = None
    error_message: Optional[str] = None


class CoordinatedMutationExecutor:
    """
    Executes coordinated mutation plans atomically with rollback support.
    
    Steps:
    1. Accept a coordinated mutation plan (list of {file, changes})
    2. Create a temporary sandbox copy of all affected files
    3. Apply all changes to sandbox copies
    4. Validate syntax of all modified files using ast.parse()
    5. Run integration tests on the sandbox
    6. If all validations pass, atomically copy sandbox files to actual locations
    7. If any validation fails, discard sandbox and report specific failure reasons
    8. Maintain a rollback snapshot of original files
    """

    def __init__(self, project_root: str = "."):
        self.project_root = Path(project_root).resolve()
        self.sandbox_dir: Optional[Path] = None
        self.rollback_snapshots: Dict[str, Optional[str]] = {}
        self._sandbox_created = False

    def _resolve_file_path(self, relative_path: str) -> Path:
        """Resolve a relative file path to an absolute path within the project root."""
        return (self.project_root / relative_path).resolve()

    def _create_sandbox(self, affected_files: List[str]) -> Optional[Path]:
        """
        Create a temporary sandbox directory and copy affected files into it.
        Returns the sandbox path or None on failure.
        """
        try:
            sandbox = Path(tempfile.mkdtemp(prefix="coordinated_mutation_"))
            for rel_path in affected_files:
                src = self._resolve_file_path(rel_path)
                if src.exists():
                    dst = sandbox / rel_path
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, dst)
            self.sandbox_dir = sandbox
            self._sandbox_created = True
            return sandbox
        except Exception as e:
            self._cleanup_sandbox()
            return None

    def _apply_changes_to_sandbox(self, changes: List[FileChange]) -> bool:
        """
        Apply all changes to the sandbox copies.
        Returns True if all changes were applied successfully.
        """
        if not self.sandbox_dir:
            return False

        try:
            for change in changes:
                sandbox_file = self.sandbox_dir / change.file_path
                sandbox_file.parent.mkdir(parents=True, exist_ok=True)
                sandbox_file.write_text(change.new_content, encoding="utf-8")
            return True
        except Exception:
            return False

    def _validate_syntax(self, changes: List[FileChange]) -> List[ValidationResult]:
        """
        Validate the syntax of all modified files using ast.parse().
        Returns a list of validation results.
        """
        results = []
        for change in changes:
            try:
                ast.parse(change.new_content)
                results.append(ValidationResult(
                    file_path=change.file_path,
                    is_valid=True
                ))
            except SyntaxError as e:
                results.append(ValidationResult(
                    file_path=change.file_path,
                    is_valid=False,
                    error_message=f"Syntax error: {e.msg} at line {e.lineno}, offset {e.offset}"
                ))
            except Exception as e:
                results.append(ValidationResult(
                    file_path=change.file_path,
                    is_valid=False,
                    error_message=str(e)
                ))
        return results

    def _run_integration_tests(self, plan: CoordinatedMutationPlan) -> Tuple[bool, Optional[str]]:
        """
        Run integration tests on the sandbox.
        Returns (passed, output).
        """
        if not plan.integration_test_command:
            return True, None

        if not self.sandbox_dir:
            return False, "Sandbox directory not available"

        try:
            test_dir = self.sandbox_dir
            if plan.test_working_dir:
                test_dir = self.sandbox_dir / plan.test_working_dir

            result = subprocess.run(
                plan.integration_test_command,
                shell=True,
                cwd=str(test_dir),
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )

            if result.returncode == 0:
                return True, result.stdout
            else:
                return False, f"Integration tests failed:\nSTDOUT: {result.stdout}\nSTDERR: {result.stderr}"

        except subprocess.TimeoutExpired:
            return False, "Integration tests timed out after 5 minutes"
        except Exception as e:
            return False, f"Error running integration tests: {str(e)}"

    def _take_rollback_snapshot(self, affected_files: List[str]) -> bool:
        """
        Take a snapshot of the original files for rollback purposes.
        Returns True if all snapshots were taken successfully.
        """
        try:
            for rel_path in affected_files:
                src = self._resolve_file_path(rel_path)
                if src.exists():
                    self.rollback_snapshots[rel_path] = src.read_text(encoding="utf-8")
                else:
                    self.rollback_snapshots[rel_path] = None
            return True
        except Exception:
            return False

    def _atomic_copy_to_actual(self, changes: List[FileChange]) -> bool:
        """
        Atomically copy sandbox files to actual locations.
        Returns True if all files were copied successfully.
        """
        if not self.sandbox_dir:
            return False

        try:
            for change in changes:
                sandbox_file = self.sandbox_dir / change.file_path
                actual_file = self._resolve_file_path(change.file_path)
                actual_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(sandbox_file, actual_file)
            return True
        except Exception:
            return False

    def _cleanup_sandbox(self) -> None:
        """Remove the sandbox directory if it exists."""
        if self.sandbox_dir and self.sandbox_dir.exists():
            shutil.rmtree(self.sandbox_dir, ignore_errors=True)
            self.sandbox_dir = None
            self._sandbox_created = False

    def rollback(self) -> bool:
        """
        Rollback all changes using the stored snapshots.
        Returns True if rollback was successful.
        """
        if not self.rollback_snapshots:
            return False

        try:
            for rel_path, content in self.rollback_snapshots.items():
                actual_file = self._resolve_file_path(rel_path)
                if content is not None:
                    actual_file.parent.mkdir(parents=True, exist_ok=True)
                    actual_file.write_text(content, encoding="utf-8")
                else:
                    # File didn't exist before, remove it
                    if actual_file.exists():
                        actual_file.unlink()
            self.rollback_snapshots.clear()
            return True
        except Exception:
            return False

    def execute(self, plan: CoordinatedMutationPlan) -> ExecutionResult:
        """
        Execute a coordinated mutation plan atomically.
        
        Args:
            plan: The coordinated mutation plan to execute
            
        Returns:
            ExecutionResult indicating success/failure with details
        """
        result = ExecutionResult()

        if not plan.changes:
            result.success = True
            return result

        affected_files = [change.file_path for change in plan.changes]

        # Step 1: Take rollback snapshot
        if not self._take_rollback_snapshot(affected_files):
            result.error_message = "Failed to take rollback snapshot"
            return result

        # Step 2: Create sandbox
        sandbox = self._create_sandbox(affected_files)
        if sandbox is None:
            result.error_message = "Failed to create sandbox directory"
            return result

        try:
            # Step 3: Apply changes to sandbox
            if not self._apply_changes_to_sandbox(plan.changes):
                result.error_message = "Failed to apply changes to sandbox"
                self._cleanup_sandbox()
                return result

            # Step 4: Validate syntax
            validation_results = self._validate_syntax(plan.changes)
            failed_validations = [v for v in validation_results if not v.is_valid]
            result.failed_validations = failed_validations

            if failed_validations:
                result.error_message = "Syntax validation failed for some files"
                self._cleanup_sandbox()
                return result

            # Step 5: Run integration tests
            test_passed, test_output = self._run_integration_tests(plan)
            result.integration_test_passed = test_passed
            result.integration_test_output = test_output

            if not test_passed:
                result.error_message = "Integration tests failed"
                self._cleanup_sandbox()
                return result

            # Step 6: Atomic copy to actual locations
            if not self._atomic_copy_to_actual(plan.changes):
                result.error_message = "Failed to copy files to actual locations"
                self.rollback()
                self._cleanup_sandbox()
                return result

            # Success
            result.success = True
            result.applied_changes = affected_files
            self._cleanup_sandbox()
            return result

        except Exception as e:
            result.error_message = f"Unexpected error during execution: {str(e)}"
            self.rollback()
            self._cleanup_sandbox()
            return result

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._cleanup_sandbox()