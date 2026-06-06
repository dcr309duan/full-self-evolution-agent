"""Rollback Manager for automatic rollback of failed mutations.

Maintains a stack of recent mutations and automatically reverts them
if integration tests fail after application.
"""

import ast
import logging
import time
from typing import List, Tuple, Optional, Set
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

    def __init__(self, max_history: int = 100, diversity_threshold: float = 0.3):
        self._mutation_stack: List[MutationRecord] = []
        self._max_history = max_history
        self._test_runner = None  # Callable to run integration tests
        self._diversity_threshold = diversity_threshold
        self._unique_test_patterns: Set[str] = set()
        self._diversity_scores: List[float] = []

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
                # Track unique test patterns from successful mutations
                pattern_hash = hash(mutated_content[:100])  # Use first 100 chars as pattern identifier
                self._unique_test_patterns.add(str(pattern_hash))
                self._update_diversity_metric()
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
        self._unique_test_patterns.clear()
        self._diversity_scores.clear()
        logger.info("Mutation history cleared")

    @property
    def mutation_count(self) -> int:
        """Number of mutations in history."""
        return len(self._mutation_stack)

    def _update_diversity_metric(self) -> None:
        """Update diversity metric and trigger new test types if needed."""
        total_mutations = len(self._mutation_stack)
        if total_mutations == 0:
            diversity_score = 0.0
        else:
            diversity_score = len(self._unique_test_patterns) / total_mutations
        
        self._diversity_scores.append(diversity_score)
        logger.info(f"Test suite diversity score: {diversity_score:.3f} (unique patterns: {len(self._unique_test_patterns)}, total mutations: {total_mutations})")
        
        if diversity_score < self._diversity_threshold:
            logger.warning(f"Diversity score {diversity_score:.3f} below threshold {self._diversity_threshold}. Triggering generation of new test types.")
            self._trigger_new_test_types()

    def _trigger_new_test_types(self) -> None:
        """Trigger generation of new test types to increase diversity."""
        insight = {
            "event": "low_diversity",
            "diversity_score": self._diversity_scores[-1] if self._diversity_scores else 0.0,
            "threshold": self._diversity_threshold,
            "unique_patterns": len(self._unique_test_patterns),
            "total_mutations": len(self._mutation_stack),
            "priority": "high"
        }
        logger.critical(f"Test suite stagnation detected: {insight}")
        # In a real system, this would trigger the goal generator to create new test types
        # For now, we log it prominently

    def test_suite_diversity_metric(self) -> dict:
        """Get the current test suite diversity metric."""
        total_mutations = len(self._mutation_stack)
        if total_mutations == 0:
            diversity_score = 0.0
        else:
            diversity_score = len(self._unique_test_patterns) / total_mutations
        
        return {
            "diversity_score": diversity_score,
            "unique_patterns": len(self._unique_test_patterns),
            "total_mutations": total_mutations,
            "threshold": self._diversity_threshold,
            "diversity_scores": self._diversity_scores.copy()
        }