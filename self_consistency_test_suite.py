"""Self-consistency test suite for introspection modules.

This module implements automated consistency checking across the introspection pipeline:
1. Reflection parser -> Goal generator -> Parse validation
2. Goal generator -> Mutation engine pre-mutation validator -> Consumability check
3. Self-registration as mandatory pre-commit hook in mutation engine
4. Failure handling with rollback and logging
5. Schema alignment layer for generating test cases
"""

import logging
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import traceback
import json
import os

# Internal imports (assumed to be available in the environment)
from reflection_parser import ReflectionParser, ParseError
from goal_generator import GoalGenerator
from mutation_engine import MutationEngine, MutationError
from failure_analysis import FailureAnalyzer
from schema_alignment_layer import SchemaAlignmentLayer, AlignmentError

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
    transformation_rules: Dict[str, Any] = field(default_factory=dict)


class SelfConsistencyTestSuite:
    """Implements self-consistency testing for introspection modules."""

    def __init__(
        self,
        reflection_parser: ReflectionParser,
        goal_generator: GoalGenerator,
        mutation_engine: MutationEngine,
        failure_analyzer: FailureAnalyzer,
        schema_alignment: SchemaAlignmentLayer,
        max_consecutive_failures: int = 3,
        rules_file: str = "transformation_rules.json"
    ):
        self.parser = reflection_parser
        self.goal_generator = goal_generator
        self.mutation_engine = mutation_engine
        self.failure_analyzer = failure_analyzer
        self.schema_alignment = schema_alignment
        self.max_consecutive_failures = max_consecutive_failures
        self.rules_file = rules_file
        self.state = TestSuiteState()
        self._register_hooks()
        self._load_transformation_rules()

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
        """Automatically generate a test case from the current reflection cycle context using schema alignment."""
        reflection_input = context.get("reflection_output", "")
        
        # Use schema alignment to transform reflection output to goal generator input
        try:
            aligned_input = self.schema_alignment.align_reflection_to_goal_generator(reflection_input)
            test_case = TestCase(reflection_input=aligned_input)
        except AlignmentError as e:
            logger.warning(f"Schema alignment failed for reflection input: {e}")
            test_case = TestCase(reflection_input=reflection_input)
        
        return test_case

    def _run_test_case(self, test_case: TestCase) -> None:
        """Execute the full test pipeline for a single test case."""
        try:
            # Step 1: Pipe reflection parser output through goal generator
            test_case.parsed_output = self.parser.parse(test_case.reflection_input)
            
            # Use schema alignment to transform parsed output to goal generator input
            try:
                aligned_parsed = self.schema_alignment.align_parsed_to_goal_generator(test_case.parsed_output)
            except AlignmentError as e:
                test_case.result = TestResult.FAIL
                test_case.error_message = f"Schema alignment failed for parsed output: {e}"
                test_case.traceback_info = traceback.format_exc()
                return
            
            test_case.generated_goals = self.goal_generator.generate(aligned_parsed)

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
            # Use schema alignment to transform goal generator output to mutation engine input
            try:
                aligned_goals = self.schema_alignment.align_goals_to_mutation_engine(test_case.generated_goals)
            except AlignmentError as e:
                test_case.result = TestResult.FAIL
                test_case.error_message = f"Schema alignment failed for goals: {e}"
                test_case.traceback_info = traceback.format_exc()
                return
            
            validation_result = self.mutation_engine.validate_pre_mutation(aligned_goals)
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

    def _load_transformation_rules(self) -> None:
        """Load transformation rules from file if it exists."""
        if os.path.exists(self.rules_file):
            try:
                with open(self.rules_file, 'r') as f:
                    self.state.transformation_rules = json.load(f)
                logger.info(f"Loaded transformation rules from {self.rules_file}")
            except Exception as e:
                logger.error(f"Failed to load transformation rules: {e}")
                self.state.transformation_rules = {}

    def _save_transformation_rules(self) -> None:
        """Save transformation rules to file."""
        try:
            with open(self.rules_file, 'w') as f:
                json.dump(self.state.transformation_rules, f, indent=2)
            logger.info(f"Saved transformation rules to {self.rules_file}")
        except Exception as e:
            logger.error(f"Failed to save transformation rules: {e}")

    def test_schema_alignment_reflection_to_goal(self) -> bool:
        """Test that schema alignment correctly transforms reflection output to goal generator input."""
        try:
            test_reflection = "Test reflection output"
            aligned = self.schema_alignment.align_reflection_to_goal_generator(test_reflection)
            # Verify the aligned output is valid for goal generator
            parsed = self.parser.parse(aligned)
            self.goal_generator.generate(parsed)
            logger.info("Schema alignment reflection to goal: PASS")
            return True
        except Exception as e:
            logger.error(f"Schema alignment reflection to goal: FAIL - {e}")
            return False

    def test_schema_alignment_goals_to_mutation(self) -> bool:
        """Test that schema alignment correctly transforms goal generator output to mutation engine input."""
        try:
            test_goals = ["Test goal 1", "Test goal 2"]
            aligned = self.schema_alignment.align_goals_to_mutation_engine(test_goals)
            # Verify the aligned output is valid for mutation engine
            self.mutation_engine.validate_pre_mutation(aligned)
            logger.info("Schema alignment goals to mutation: PASS")
            return True
        except Exception as e:
            logger.error(f"Schema alignment goals to mutation: FAIL - {e}")
            return False

    def test_auto_adaptation_on_mismatch(self) -> bool:
        """Test that auto-adaptation triggers when mismatches are detected."""
        try:
            # Simulate a mismatch scenario
            test_reflection = "Invalid reflection format"
            try:
                self.schema_alignment.align_reflection_to_goal_generator(test_reflection)
                # If no exception, check if adaptation was triggered
                if self.schema_alignment.last_adaptation_triggered:
                    logger.info("Auto-adaptation on mismatch: PASS")
                    return True
                else:
                    logger.warning("Auto-adaptation on mismatch: No adaptation triggered")
                    return False
            except AlignmentError:
                # If alignment fails, adaptation should have been triggered
                if self.schema_alignment.last_adaptation_triggered:
                    logger.info("Auto-adaptation on mismatch: PASS")
                    return True
                else:
                    logger.warning("Auto-adaptation on mismatch: No adaptation triggered")
                    return False
        except Exception as e:
            logger.error(f"Auto-adaptation on mismatch: FAIL - {e}")
            return False

    def test_transformation_rules_persistence(self) -> bool:
        """Test that transformation rules are persisted and reloaded correctly."""
        try:
            # Save current rules
            original_rules = self.state.transformation_rules.copy()
            self._save_transformation_rules()
            
            # Clear and reload
            self.state.transformation_rules = {}
            self._load_transformation_rules()
            
            # Verify reloaded rules match original
            if self.state.transformation_rules == original_rules:
                logger.info("Transformation rules persistence: PASS")
                return True
            else:
                logger.warning("Transformation rules persistence: Rules mismatch")
                return False
        except Exception as e:
            logger.error(f"Transformation rules persistence: FAIL - {e}")
            return False

    def run_full_test_suite(self) -> Dict[str, Any]:
        """Run a comprehensive test suite across all registered test cases."""
        results = {
            "total": len(self.state.test_history),
            "passed": 0,
            "failed": 0,
            "errors": 0,
            "details": [],
            "schema_alignment_tests": {}
        }

        # Run schema alignment specific tests
        results["schema_alignment_tests"]["reflection_to_goal"] = self.test_schema_alignment_reflection_to_goal()
        results["schema_alignment_tests"]["goals_to_mutation"] = self.test_schema_alignment_goals_to_mutation()
        results["schema_alignment_tests"]["auto_adaptation"] = self.test_auto_adaptation_on_mismatch()
        results["schema_alignment_tests"]["rules_persistence"] = self.test_transformation_rules_persistence()

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
            "max_consecutive_failures": self.max_consecutive_failures,
            "transformation_rules_count": len(self.state.transformation_rules)
        }

    def reset_state(self) -> None:
        """Reset the test suite state (useful for testing or recovery)."""
        self.state = TestSuiteState()
        self._load_transformation_rules()
        logger.info("Self-consistency test suite state has been reset.")


# Convenience function for creating and initializing the test suite
def create_test_suite(
    parser: ReflectionParser,
    goal_generator: GoalGenerator,
    mutation_engine: MutationEngine,
    failure_analyzer: FailureAnalyzer,
    schema_alignment: SchemaAlignmentLayer,
    **kwargs
) -> SelfConsistencyTestSuite:
    """Factory function to create and initialize the self-consistency test suite."""
    suite = SelfConsistencyTestSuite(
        reflection_parser=parser,
        goal_generator=goal_generator,
        mutation_engine=mutation_engine,
        failure_analyzer=failure_analyzer,
        schema_alignment=schema_alignment,
        **kwargs
    )
    return suite