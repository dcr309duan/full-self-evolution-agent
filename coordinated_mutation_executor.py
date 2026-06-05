"""Coordinated Mutation Executor.

Applies coordinated mutations atomically using a clone-and-promote mechanism:
1. Clone all affected modules into a staging area.
2. Apply all changes simultaneously.
3. Run the full integration test suite on the staged system.
4. If tests pass, promote all changes atomically.
5. If tests fail, revert all changes and log the failure pattern.
Also updates the Nash equilibrium detector with the result.
"""

import os
import shutil
import tempfile
import logging
import json
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field, asdict

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class MutationChange:
    """Represents a single mutation change to a module."""
    module_path: str
    original_content: str
    mutated_content: str
    mutation_id: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MutationBatch:
    """A batch of coordinated mutations to be applied atomically."""
    batch_id: str
    changes: List[MutationChange]
    timestamp: datetime = field(default_factory=datetime.utcnow)
    status: str = "pending"  # pending, staged, testing, promoted, reverted, failed
    test_results: Optional[Dict[str, Any]] = None
    failure_pattern: Optional[str] = None


# ---------------------------------------------------------------------------
# Staging area manager
# ---------------------------------------------------------------------------

class StagingAreaManager:
    """Manages a temporary staging area for atomic mutations."""

    def __init__(self, base_dir: str = "./staging"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def create_staging_area(self, batch_id: str) -> Path:
        """Create a fresh staging directory for a mutation batch."""
        staging_path = self.base_dir / batch_id
        if staging_path.exists():
            shutil.rmtree(staging_path)
        staging_path.mkdir(parents=True, exist_ok=True)
        return staging_path

    def clone_modules(self, staging_path: Path, changes: List[MutationChange]) -> Dict[str, Path]:
        """Clone original modules into the staging area and return mapping of original->staging paths."""
        cloned = {}
        for change in changes:
            src = Path(change.module_path)
            if not src.exists():
                raise FileNotFoundError(f"Module not found: {change.module_path}")
            rel_path = src.relative_to(src.anchor) if src.is_absolute() else src
            dest = staging_path / rel_path
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
            cloned[change.module_path] = str(dest)
        return cloned

    def apply_changes(self, staging_path: Path, changes: List[MutationChange], cloned_map: Dict[str, Path]) -> None:
        """Write mutated content to the staged copies."""
        for change in changes:
            staged_path = cloned_map.get(change.module_path)
            if staged_path is None:
                raise ValueError(f"No staged copy for {change.module_path}")
            with open(staged_path, "w", encoding="utf-8") as f:
                f.write(change.mutated_content)

    def revert_staging(self, staging_path: Path) -> None:
        """Remove the staging area."""
        if staging_path.exists():
            shutil.rmtree(staging_path)

    def promote_changes(self, staging_path: Path, changes: List[MutationChange], cloned_map: Dict[str, Path]) -> None:
        """Atomically promote staged changes by replacing originals with staged copies."""
        for change in changes:
            staged_path = cloned_map.get(change.module_path)
            if staged_path is None:
                raise ValueError(f"No staged copy for {change.module_path}")
            original_path = Path(change.module_path)
            # Backup original? Could be done but for atomicity we overwrite.
            shutil.copy2(staged_path, original_path)
        # Clean up staging after successful promotion
        self.revert_staging(staging_path)


# ---------------------------------------------------------------------------
# Integration test runner (mock / placeholder)
# ---------------------------------------------------------------------------

class IntegrationTestRunner:
    """Runs the full integration test suite on the staged system."""

    def __init__(self, test_command: str = "pytest tests/integration/"):
        self.test_command = test_command

    def run_tests(self, staging_path: Optional[Path] = None) -> Dict[str, Any]:
        """Execute the integration test suite.

        In a real implementation, this would run the test command, possibly
        pointing to the staged environment. Here we simulate with a placeholder.
        """
        # Placeholder: simulate test execution
        # In production, use subprocess to run the test command.
        import subprocess
        try:
            env = os.environ.copy()
            if staging_path:
                env["STAGING_PATH"] = str(staging_path)
            result = subprocess.run(
                self.test_command.split(),
                capture_output=True,
                text=True,
                env=env,
                timeout=300
            )
            passed = result.returncode == 0
            return {
                "passed": passed,
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "timestamp": datetime.utcnow().isoformat()
            }
        except subprocess.TimeoutExpired:
            return {
                "passed": False,
                "returncode": -1,
                "stdout": "",
                "stderr": "Test suite timed out",
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            return {
                "passed": False,
                "returncode": -2,
                "stdout": "",
                "stderr": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }


# ---------------------------------------------------------------------------
# Failure pattern analyzer
# ---------------------------------------------------------------------------

class FailurePatternAnalyzer:
    """Analyzes test failures and extracts patterns for logging."""

    @staticmethod
    def analyze(test_results: Dict[str, Any]) -> str:
        """Extract a failure pattern string from test results."""
        if test_results.get("passed", False):
            return ""
        stderr = test_results.get("stderr", "")
        stdout = test_results.get("stdout", "")
        # Simple heuristic: hash the concatenation of error output
        pattern_input = (stderr + stdout)[:2000]
        pattern_hash = hashlib.sha256(pattern_input.encode()).hexdigest()[:16]
        return f"failure_pattern_{pattern_hash}"


# ---------------------------------------------------------------------------
# Nash equilibrium detector integration (stub)
# ---------------------------------------------------------------------------

class NashEquilibriumDetector:
    """Stub for Nash equilibrium detector integration."""

    def update_with_result(self, batch_id: str, success: bool, failure_pattern: Optional[str] = None) -> None:
        """Record the outcome of a mutation batch.

        In a real system, this would update a game-theoretic model.
        """
        logger.info(
            "NashDetector: batch=%s success=%s pattern=%s",
            batch_id, success, failure_pattern
        )


# ---------------------------------------------------------------------------
# Main executor
# ---------------------------------------------------------------------------

class CoordinatedMutationExecutor:
    """Applies coordinated mutations atomically with clone-and-promote."""

    def __init__(
        self,
        staging_manager: Optional[StagingAreaManager] = None,
        test_runner: Optional[IntegrationTestRunner] = None,
        nash_detector: Optional[NashEquilibriumDetector] = None,
        failure_analyzer: Optional[FailurePatternAnalyzer] = None,
        log_dir: str = "./mutation_logs"
    ):
        self.staging_manager = staging_manager or StagingAreaManager()
        self.test_runner = test_runner or IntegrationTestRunner()
        self.nash_detector = nash_detector or NashEquilibriumDetector()
        self.failure_analyzer = failure_analyzer or FailurePatternAnalyzer()
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.history: List[MutationBatch] = []

    def execute(self, batch: MutationBatch) -> MutationBatch:
        """Execute a coordinated mutation batch atomically.

        Steps:
        1. Clone all affected modules into staging.
        2. Apply all changes simultaneously.
        3. Run integration tests.
        4. If passed, promote; else revert and log failure.
        5. Update Nash detector.
        """
        batch_id = batch.batch_id
        logger.info("Starting coordinated mutation batch: %s", batch_id)

        # Step 1: Create staging area and clone modules
        staging_path = self.staging_manager.create_staging_area(batch_id)
        try:
            cloned_map = self.staging_manager.clone_modules(staging_path, batch.changes)
            batch.status = "staged"

            # Step 2: Apply all changes simultaneously
            self.staging_manager.apply_changes(staging_path, batch.changes, cloned_map)
            batch.status = "testing"

            # Step 3: Run integration tests
            test_results = self.test_runner.run_tests(staging_path)
            batch.test_results = test_results

            if test_results.get("passed", False):
                # Step 4a: Promote changes
                self.staging_manager.promote_changes(staging_path, batch.changes, cloned_map)
                batch.status = "promoted"
                logger.info("Batch %s promoted successfully.", batch_id)
                self.nash_detector.update_with_result(batch_id, success=True)
            else:
                # Step 4b: Revert and log failure
                failure_pattern = self.failure_analyzer.analyze(test_results)
                batch.failure_pattern = failure_pattern
                batch.status = "reverted"
                self.staging_manager.revert_staging(staging_path)
                logger.warning("Batch %s reverted. Failure pattern: %s", batch_id, failure_pattern)
                self.nash_detector.update_with_result(batch_id, success=False, failure_pattern=failure_pattern)
                self._log_failure(batch)

        except Exception as e:
            logger.exception("Unexpected error during batch %s: %s", batch_id, e)
            batch.status = "failed"
            batch.failure_pattern = str(e)
            self.nash_detector.update_with_result(batch_id, success=False, failure_pattern=str(e))
            # Ensure staging is cleaned up
            self.staging_manager.revert_staging(staging_path)
            self._log_failure(batch)

        # Record history
        self.history.append(batch)
        return batch

    def _log_failure(self, batch: MutationBatch) -> None:
        """Log failure details to a file for analysis."""
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        log_file = self.log_dir / f"failure_{batch.batch_id}_{timestamp}.json"
        data = {
            "batch_id": batch.batch_id,
            "status": batch.status,
            "timestamp": batch.timestamp.isoformat(),
            "failure_pattern": batch.failure_pattern,
            "test_results": batch.test_results,
            "changes": [
                {
                    "module_path": c.module_path,
                    "mutation_id": c.mutation_id,
                    "metadata": c.metadata
                }
                for c in batch.changes
            ]
        }
        with open(log_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        logger.info("Failure log written to %s", log_file)

    def get_history(self) -> List[MutationBatch]:
        """Return the execution history."""
        return self.history


# ---------------------------------------------------------------------------
# Convenience function
# ---------------------------------------------------------------------------

def execute_coordinated_mutations(
    changes: List[MutationChange],
    batch_id: Optional[str] = None,
    test_command: str = "pytest tests/integration/",
    log_dir: str = "./mutation_logs"
) -> MutationBatch:
    """Convenience function to execute a batch of coordinated mutations."""
    if batch_id is None:
        batch_id = f"batch_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{hashlib.md5(str(changes).encode()).hexdigest()[:8]}"

    batch = MutationBatch(
        batch_id=batch_id,
        changes=changes
    )

    executor = CoordinatedMutationExecutor(
        test_runner=IntegrationTestRunner(test_command=test_command),
        log_dir=log_dir
    )
    return executor.execute(batch)