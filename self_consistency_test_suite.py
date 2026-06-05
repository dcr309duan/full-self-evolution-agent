"""Self-consistency test suite for introspection modules.

This module implements automated consistency checking across the introspection pipeline:
1. Reflection parser -> Goal generator -> Parse validation
2. Goal generator -> Mutation engine pre-mutation validator -> Consumability check
3. Self-registration as mandatory pre-commit hook in mutation engine
4. Failure handling with rollback and logging
"""

import logging
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import traceback

# Internal imports (assumed to be available in the environment)
from reflection_parser import ReflectionParser, ParseError
from goal_generator import GoalGenerator
from mutation_engine import MutationEngine, MutationError
from failure_analysis import FailureAnalyzer

logger = logging.getLogger(__name__)


class TestResult(Enum):
    PASS = "pass"
    FAIL = "fail"
    ERROR = "error"


@dataclass
class TestCase:
    """Represents a single test case in the consistency suite."""
    reflection_input: str
    parsed_output: Optional[Dict[str, Any]] = None
    generated_goals: Optional[List[str]] = None
    validation_result: Optional[bool] = None
    result: TestResult = TestResult.PASS
    error_message: Optional[str] = None
    traceback_info: Optional[str] = None


@dataclass
class TestSuiteState:
    """Maintains state for the test suite across reflection cycles."""
    test_history: List[TestCase] = field(default_factory=list)
    consecutive_failures: int = 0
    last_rollback_id: Optional[str] = None
    is_registered: bool = False


class SelfConsistencyTestSuite:
    """Implements self-consistency testing for introspection modules."""

    def __init__(
        self,
        reflection_parser: ReflectionParser,
        goal_generator: GoalGenerator,
        mutation_engine: MutationEngine,
        failure_analyzer: FailureAnalyzer,
        max_consecutive_failures: int = 3
    ):
        self.parser = reflection_parser
        self.goal_generator = goal_generator
        self.mutation_engine = mutation_engine
        self.failure_analyzer = failure_analyzer
        self.max_consecutive_failures = max_consecutive_failures
        self.state = TestSuiteState()
        self._register_hooks()

    def _register_hooks(self) -> None:
        """Register the test suite as a mandatory pre-commit hook in the mutation engine."""
        try:
            self.mutation_engine.register_pre_commit_hook(
                hook_name="self_consistency_test",
                hook_function=self._pre_commit_hook,
                mandatory=True
            )
            self.state.is_registered = True
            logger.info("Self-consistency test suite registered as mandatory pre-commit hook.")
        except Exception as e:
            logger.error(f"Failed to register pre-commit hook: {e}")
            raise

    def _pre_commit_hook(self, mutation_context: Dict[str, Any]) -> bool:
        """Pre-commit hook that runs the test suite before each mutation commit."""
        try:
            test_case = self._generate_test_case(mutation_context)
            self._run_test_case(test_case)
            self.state.test_history.append(test_case)

            if test_case.result == TestResult.FAIL:
                self._handle_failure(test_case, mutation_context)
                return False
            elif test_case.result == TestResult.ERROR:
                self._handle_error(test_case, mutation_context)
                return False

            self.state.consecutive_failures = 0
            return True

        except Exception as e:
            logger.error(f"Pre-commit hook execution failed: {e}")
            return False

    def _generate_test_case(self, context: Dict[str, Any]) -> TestCase:
        """Automatically generate a test case from the current reflection cycle context."""
        reflection_input = context.get("reflection_output", "")
        return TestCase(reflection_input=reflection_input)

    def _run_test_case(self, test_case: TestCase) -> None:
        """Execute the full test pipeline for a single test case."""
        try:
            # Step 1: Pipe reflection parser output through goal generator
            test_case.parsed_output = self.parser.parse(test_case.reflection_input)
            test_case.generated_goals = self.goal_generator.generate(test_case.parsed_output)

            # Verify no parse errors in generated goals
            for goal in test_case.generated_goals:
                try:
                    self.parser.parse(goal)
                except ParseError as e:
                    test_case.result = TestResult.FAIL
                    test_case.error_message = f"Parse error in generated goal: {e}"
                    test_case.traceback_info = traceback.format_exc()
                    return

            # Step 2: Pipe goal generator output through mutation engine's pre-mutation validator
            validation_result = self.mutation_engine.validate_pre_mutation(test_case.generated_goals)
            test_case.validation_result = validation_result

            if not validation_result:
                test_case.result = TestResult.FAIL
                test_case.error_message = "Goal generator output failed pre-mutation validation"
                return

            test_case.result = TestResult.PASS

        except ParseError as e:
            test_case.result = TestResult.FAIL
            test_case.error_message = f"Parse error in reflection input: {e}"
            test_case.traceback_info = traceback.format_exc()
        except Exception as e:
            test_case.result = TestResult.ERROR
            test_case.error_message = f"Unexpected error during test execution: {e}"
            test_case.traceback_info = traceback.format_exc()

    def _handle_failure(self, test_case: TestCase, mutation_context: Dict[str, Any]) -> None:
        """Handle test failure by triggering rollback and logging."""
        self.state.consecutive_failures += 1

        try:
            # Trigger rollback of the last mutation
            rollback_id = self.mutation_engine.rollback_last_mutation()
            self.state.last_rollback_id = rollback_id

            # Log failure to the failure analysis module
            failure_data = {
                "test_case": test_case,
                "mutation_context": mutation_context,
                "rollback_id": rollback_id,
                "consecutive_failures": self.state.consecutive_failures
            }
            self.failure_analyzer.log_failure(failure_data)

            logger.warning(
                f"Self-consistency test failed. Rollback triggered (ID: {rollback_id}). "
                f"Consecutive failures: {self.state.consecutive_failures}"
            )

            # If consecutive failures exceed threshold, escalate
            if self.state.consecutive_failures >= self.max_consecutive_failures:
                self._escalate_failure()

        except Exception as e:
            logger.error(f"Failed to handle test failure properly: {e}")
            raise

    def _handle_error(self, test_case: TestCase, mutation_context: Dict[str, Any]) -> None:
        """Handle test error (unexpected exceptions) with rollback and logging."""
        try:
            rollback_id = self.mutation_engine.rollback_last_mutation()
            self.state.last_rollback_id = rollback_id

            error_data = {
                "test_case": test_case,
                "mutation_context": mutation_context,
                "rollback_id": rollback_id,
                "error_type": "unexpected_error"
            }
            self.failure_analyzer.log_error(error_data)

            logger.error(
                f"Self-consistency test encountered an error. Rollback triggered (ID: {rollback_id}). "
                f"Error: {test_case.error_message}"
            )

        except Exception as e:
            logger.error(f"Failed to handle test error properly: {e}")
            raise

    def _escalate_failure(self) -> None:
        """Escalate when consecutive failures exceed threshold."""
        escalation_data = {
            "consecutive_failures": self.state.consecutive_failures,
            "max_allowed": self.max_consecutive_failures,
            "last_rollback_id": self.state.last_rollback_id,
            "recent_test_cases": self.state.test_history[-self.max_consecutive_failures:]
        }
        self.failure_analyzer.escalate_failure(escalation_data)
        logger.critical(
            f"Escalating failure: {self.state.consecutive_failures} consecutive failures "
            f"(max allowed: {self.max_consecutive_failures})"
        )

    def run_full_test_suite(self) -> Dict[str, Any]:
        """Run a comprehensive test suite across all registered test cases."""
        results = {
            "total": len(self.state.test_history),
            "passed": 0,
            "failed": 0,
            "errors": 0,
            "details": []
        }

        for test_case in self.state.test_history:
            result_entry = {
                "reflection_input": test_case.reflection_input[:100],  # Truncate for logging
                "result": test_case.result.value,
                "error": test_case.error_message
            }
            results["details"].append(result_entry)

            if test_case.result == TestResult.PASS:
                results["passed"] += 1
            elif test_case.result == TestResult.FAIL:
                results["failed"] += 1
            else:
                results["errors"] += 1

        return results

    def get_test_statistics(self) -> Dict[str, Any]:
        """Get statistics about the test suite execution."""
        return {
            "total_tests_run": len(self.state.test_history),
            "consecutive_failures": self.state.consecutive_failures,
            "is_registered": self.state.is_registered,
            "last_rollback_id": self.state.last_rollback_id,
            "max_consecutive_failures": self.max_consecutive_failures
        }

    def reset_state(self) -> None:
        """Reset the test suite state (useful for testing or recovery)."""
        self.state = TestSuiteState()
        logger.info("Self-consistency test suite state has been reset.")


# Convenience function for creating and initializing the test suite
def create_test_suite(
    parser: ReflectionParser,
    goal_generator: GoalGenerator,
    mutation_engine: MutationEngine,
    failure_analyzer: FailureAnalyzer,
    **kwargs
) -> SelfConsistencyTestSuite:
    """Factory function to create and initialize the self-consistency test suite."""
    suite = SelfConsistencyTestSuite(
        reflection_parser=parser,
        goal_generator=goal_generator,
        mutation_engine=mutation_engine,
        failure_analyzer=failure_analyzer,
        **kwargs
    )
    return suite