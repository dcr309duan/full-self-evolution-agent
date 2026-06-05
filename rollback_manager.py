"""Rollback Manager for automatic rollback of failed mutations.

Maintains a stack of recent mutations and automatically reverts them
if integration tests fail after application.
"""

import ast
import logging
import time
from typing import List, Tuple, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class MutationRecord:
    """Record of a single mutation."""
    module: str
    original_content: str
    timestamp: float
    rollback_status: Optional[bool] = None


class RollbackManager:
    """Manages automatic rollback of mutations on integration test failure."""

    def __init__(self, max_history: int = 100):
        self._mutation_stack: List[MutationRecord] = []
        self._max_history = max_history
        self._test_runner = None  # Callable to run integration tests

    def set_test_runner(self, runner):
        """Set the callable that runs integration tests and returns bool."""
        self._test_runner = runner

    def record_mutation(self, module: str, original_content: str) -> MutationRecord:
        """Record a mutation before applying it."""
        record = MutationRecord(
            module=module,
            original_content=original_content,
            timestamp=time.time()
        )
        self._mutation_stack.append(record)
        # Keep stack within max_history
        if len(self._mutation_stack) > self._max_history:
            self._mutation_stack.pop(0)
        return record

    def apply_and_test(self, module: str, original_content: str, mutated_content: str) -> bool:
        """Apply mutation, run tests, rollback on failure.

        Returns True if mutation succeeded (tests passed), False otherwise.
        """
        record = self.record_mutation(module, original_content)
        success = False

        try:
            # Apply mutation by writing mutated content
            with open(module, 'w', encoding='utf-8') as f:
                f.write(mutated_content)

            # Run integration tests
            if self._test_runner is None:
                raise RuntimeError("Test runner not set. Call set_test_runner() first.")

            tests_passed = self._test_runner()

            if tests_passed:
                success = True
                record.rollback_status = False
                logger.info(f"Mutation applied successfully to {module}")
            else:
                self._rollback(record)
                record.rollback_status = True
                logger.warning(f"Tests failed, rolled back mutation on {module}")

        except Exception as e:
            # Ensure rollback on any error
            self._rollback(record)
            record.rollback_status = True
            logger.error(f"Error during mutation application: {e}")
            self._log_failure(record, type(e).__name__)
        finally:
            if not success:
                self._log_failure(record, "TestFailure" if not tests_passed else "UnknownError")

        return success

    def _rollback(self, record: MutationRecord) -> None:
        """Revert module to original content using AST-based rewriting."""
        try:
            # Parse original content to validate it's valid Python
            ast.parse(record.original_content)
            # Write original content back
            with open(record.module, 'w', encoding='utf-8') as f:
                f.write(record.original_content)
            logger.info(f"Rolled back {record.module} to original state")
        except SyntaxError as e:
            logger.error(f"Original content of {record.module} is invalid Python: {e}")
            raise
        except IOError as e:
            logger.error(f"Failed to write rollback for {record.module}: {e}")
            raise

    def _log_failure(self, record: MutationRecord, error_type: str) -> None:
        """Log failure as high-priority insight for goal generator."""
        insight = {
            "module": record.module,
            "error_type": error_type,
            "timestamp": record.timestamp,
            "rollback_status": record.rollback_status,
            "priority": "high"
        }
        logger.critical(f"Mutation failure insight: {insight}")
        # In a real system, this would be sent to the goal generator
        # For now, we log it prominently

    def get_recent_mutations(self, count: int = 10) -> List[MutationRecord]:
        """Get the most recent mutations."""
        return list(self._mutation_stack[-count:])

    def clear_history(self) -> None:
        """Clear mutation history."""
        self._mutation_stack.clear()
        logger.info("Mutation history cleared")

    @property
    def mutation_count(self) -> int:
        """Number of mutations in history."""
        return len(self._mutation_stack)