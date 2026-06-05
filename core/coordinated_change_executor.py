"""Coordinated Change Executor

Executes a coordinated multi-file mutation plan as a single atomic transaction
with full rollback capability, integration testing, and per-file result reporting.
"""

import os
import sys
import traceback
import tempfile
import shutil
import subprocess
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path


class ChangeStatus(Enum):
    """Status of a single file change."""
    PENDING = auto()
    APPLIED = auto()
    ROLLED_BACK = auto()
    FAILED = auto()
    TEST_FAILED = auto()


@dataclass
class FileChange:
    """Describes a single file mutation within a coordinated plan."""
    file_path: str
    mutation: str  # Description or code of the mutation
    rollback_strategy: str  # How to revert this change
    status: ChangeStatus = ChangeStatus.PENDING
    error: Optional[str] = None
    backup_path: Optional[str] = None


@dataclass
class CoordinatedChangePlan:
    """A plan consisting of multiple coordinated file changes."""
    changes: List[FileChange] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExecutionResult:
    """Result of executing a coordinated change plan."""
    success: bool
    per_file_results: Dict[str, ChangeStatus]
    errors: List[str]
    test_output: Optional[str] = None
    rollback_performed: bool = False


class CoordinatedChangeExecutor:
    """Executes coordinated multi-file mutations as atomic transactions."""

    def __init__(self, project_root: Optional[str] = None, test_command: Optional[str] = None):
        self.project_root = project_root or os.getcwd()
        self.test_command = test_command or self._detect_test_command()
        self._backup_files: Dict[str, str] = {}
        self._applied_changes: List[FileChange] = []

    def _detect_test_command(self) -> str:
        """Detect the appropriate test command based on project structure."""
        if os.path.exists(os.path.join(self.project_root, "pytest.ini")):
            return "python -m pytest"
        if os.path.exists(os.path.join(self.project_root, "setup.py")):
            return "python setup.py test"
        return "python -m pytest"  # Default fallback

    def _create_backup(self, file_path: str) -> Optional[str]:
        """Create a backup of the original file content."""
        full_path = os.path.join(self.project_root, file_path)
        if not os.path.exists(full_path):
            return None

        try:
            # Create temp backup
            with tempfile.NamedTemporaryFile(mode='w', suffix='.bak', delete=False) as tmp:
                with open(full_path, 'r') as original:
                    tmp.write(original.read())
                return tmp.name
        except Exception as e:
            return None

    def _restore_from_backup(self, file_path: str, backup_path: str) -> bool:
        """Restore a file from its backup."""
        full_path = os.path.join(self.project_root, file_path)
        try:
            with open(backup_path, 'r') as backup:
                content = backup.read()
            with open(full_path, 'w') as original:
                original.write(content)
            return True
        except Exception:
            return False

    def _apply_mutation(self, change: FileChange) -> bool:
        """Apply a single mutation to a file."""
        full_path = os.path.join(self.project_root, change.file_path)
        if not os.path.exists(full_path):
            change.error = f"File not found: {full_path}"
            change.status = ChangeStatus.FAILED
            return False

        try:
            # Create backup first
            backup = self._create_backup(change.file_path)
            if backup:
                change.backup_path = backup
                self._backup_files[change.file_path] = backup

            # Apply the mutation based on strategy
            if change.rollback_strategy == "replace":
                with open(full_path, 'w') as f:
                    f.write(change.mutation)
            elif change.rollback_strategy == "append":
                with open(full_path, 'a') as f:
                    f.write("\n" + change.mutation)
            elif change.rollback_strategy == "prepend":
                with open(full_path, 'r') as f:
                    original = f.read()
                with open(full_path, 'w') as f:
                    f.write(change.mutation + "\n" + original)
            else:
                # Default: replace entire content
                with open(full_path, 'w') as f:
                    f.write(change.mutation)

            change.status = ChangeStatus.APPLIED
            self._applied_changes.append(change)
            return True

        except Exception as e:
            change.error = str(e)
            change.status = ChangeStatus.FAILED
            return False

    def _rollback_all(self) -> bool:
        """Rollback all applied changes."""
        all_rolled_back = True
        for change in self._applied_changes:
            if change.backup_path and os.path.exists(change.backup_path):
                if self._restore_from_backup(change.file_path, change.backup_path):
                    change.status = ChangeStatus.ROLLED_BACK
                else:
                    all_rolled_back = False
                    change.error = "Failed to restore from backup"
            else:
                # No backup available, mark as failed rollback
                change.status = ChangeStatus.FAILED
                all_rolled_back = False

        # Clean up backup files
        for backup_path in self._backup_files.values():
            try:
                if os.path.exists(backup_path):
                    os.unlink(backup_path)
            except Exception:
                pass

        return all_rolled_back

    def _run_tests(self) -> Tuple[bool, str]:
        """Run integration tests and return (success, output)."""
        if not self.test_command:
            return True, "No test command configured"

        try:
            result = subprocess.run(
                self.test_command.split(),
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )
            success = result.returncode == 0
            output = result.stdout + "\n" + result.stderr
            return success, output
        except subprocess.TimeoutExpired:
            return False, "Tests timed out after 5 minutes"
        except Exception as e:
            return False, f"Failed to run tests: {str(e)}"

    def execute(self, plan: CoordinatedChangePlan) -> ExecutionResult:
        """Execute a coordinated change plan atomically.

        Args:
            plan: The coordinated change plan to execute

        Returns:
            ExecutionResult with per-file granularity
        """
        errors: List[str] = []
        per_file_results: Dict[str, ChangeStatus] = {}
        rollback_performed = False

        # Phase 1: Apply all mutations
        for change in plan.changes:
            success = self._apply_mutation(change)
            per_file_results[change.file_path] = change.status
            if not success:
                errors.append(f"Failed to apply mutation to {change.file_path}: {change.error}")

        # Phase 2: If any mutation failed, rollback all
        if any(c.status == ChangeStatus.FAILED for c in plan.changes):
            rollback_performed = True
            rollback_success = self._rollback_all()
            if not rollback_success:
                errors.append("Partial rollback: some files may not have been restored")

            # Update per-file results
            for change in plan.changes:
                per_file_results[change.file_path] = change.status

            return ExecutionResult(
                success=False,
                per_file_results=per_file_results,
                errors=errors,
                rollback_performed=True
            )

        # Phase 3: Run integration tests
        test_success, test_output = self._run_tests()

        if not test_success:
            # Tests failed, rollback all changes
            rollback_performed = True
            rollback_success = self._rollback_all()
            if not rollback_success:
                errors.append("Partial rollback: some files may not have been restored")

            # Mark all changes as test failed
            for change in plan.changes:
                change.status = ChangeStatus.TEST_FAILED
                per_file_results[change.file_path] = ChangeStatus.TEST_FAILED

            errors.append("Integration tests failed after applying changes")

            return ExecutionResult(
                success=False,
                per_file_results=per_file_results,
                errors=errors,
                test_output=test_output,
                rollback_performed=True
            )

        # Phase 4: Success - clean up backups
        for backup_path in self._backup_files.values():
            try:
                if os.path.exists(backup_path):
                    os.unlink(backup_path)
            except Exception:
                pass

        return ExecutionResult(
            success=True,
            per_file_results=per_file_results,
            errors=errors,
            test_output=test_output,
            rollback_performed=False
        )

    def execute_plan_from_dict(self, plan_dict: Dict[str, Any]) -> ExecutionResult:
        """Execute a plan from a dictionary representation.

        Args:
            plan_dict: Dictionary with 'changes' list of {file, mutation, rollback_strategy}

        Returns:
            ExecutionResult
        """
        changes = []
        for change_dict in plan_dict.get("changes", []):
            change = FileChange(
                file_path=change_dict["file"],
                mutation=change_dict["mutation"],
                rollback_strategy=change_dict.get("rollback_strategy", "replace")
            )
            changes.append(change)

        plan = CoordinatedChangePlan(
            changes=changes,
            metadata=plan_dict.get("metadata", {})
        )

        return self.execute(plan)


def create_executor(project_root: Optional[str] = None, test_command: Optional[str] = None) -> CoordinatedChangeExecutor:
    """Factory function to create a CoordinatedChangeExecutor.

    Args:
        project_root: Root directory of the project (default: current working directory)
        test_command: Command to run integration tests (default: auto-detected)

    Returns:
        CoordinatedChangeExecutor instance
    """
    return CoordinatedChangeExecutor(project_root=project_root, test_command=test_command)


def execute_coordinated_change(
    changes: List[Dict[str, str]],
    project_root: Optional[str] = None,
    test_command: Optional[str] = None
) -> ExecutionResult:
    """Convenience function to execute a coordinated change.

    Args:
        changes: List of dicts with 'file', 'mutation', and optional 'rollback_strategy'
        project_root: Root directory of the project
        test_command: Command to run integration tests

    Returns:
        ExecutionResult
    """
    executor = create_executor(project_root, test_command)
    plan_dict = {"changes": changes}
    return executor.execute_plan_from_dict(plan_dict)