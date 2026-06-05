import os
import sys
import tempfile
import shutil
import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path

# Add the parent directory to sys.path to import the project modules
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import the components of the pipeline
from core.reflection_parser import ReflectionParser
from core.goal_generator import GoalGenerator
from core.mutation_engine import MutationEngine
from core.test_runner import TestRunner
from core.promotion import PromotionLogic
from core.orchestrator import Orchestrator
from core.triage import TriageEngine
from core.meta_monitor import MetaMonitor
from core.reprioritization import ReprioritizationEngine
from core.hypothesis_generator import HypothesisGenerator


class TestCoreEvolutionLoop(unittest.TestCase):
    """End-to-end integration test for the core evolution loop."""

    def setUp(self):
        """Set up a sandboxed temporary directory for the test."""
        self.test_dir = tempfile.mkdtemp()
        self.sandbox_path = Path(self.test_dir)

        # Create necessary subdirectories
        (self.sandbox_path / "logs").mkdir(exist_ok=True)
        (self.sandbox_path / "mutations").mkdir(exist_ok=True)
        (self.sandbox_path / "tests").mkdir(exist_ok=True)
        (self.sandbox_path / "modules").mkdir(exist_ok=True)
        (self.sandbox_path / "archive").mkdir(exist_ok=True)

        # Create a mock mutation engine that returns a known valid mutation
        self.mock_mutation_engine = MagicMock(spec=MutationEngine)
        self.mock_mutation_engine.generate_mutation.return_value = {
            "mutation_id": "test_mutation_001",
            "code": "def add(a, b): return a + b",
            "description": "Simple addition function",
            "valid": True
        }

        # Initialize pipeline components
        self.reflection_parser = ReflectionParser(sandbox_path=self.sandbox_path)
        self.goal_generator = GoalGenerator(sandbox_path=self.sandbox_path)
        self.test_runner = TestRunner(sandbox_path=self.sandbox_path)
        self.promotion_logic = PromotionLogic(sandbox_path=self.sandbox_path)
        self.triage_engine = TriageEngine(sandbox_path=self.sandbox_path)
        self.meta_monitor = MetaMonitor(sandbox_path=self.sandbox_path)
        self.reprioritization_engine = ReprioritizationEngine(sandbox_path=self.sandbox_path)
        self.hypothesis_generator = HypothesisGenerator(sandbox_path=self.sandbox_path)
        self.orchestrator = Orchestrator(
            sandbox_path=self.sandbox_path,
            triage_engine=self.triage_engine,
            triage_interval=1,  # Short interval for testing
            meta_monitor=self.meta_monitor,
            reprioritization_engine=self.reprioritization_engine,
            hypothesis_generator=self.hypothesis_generator
        )

    def tearDown(self):
        """Clean up the sandbox directory after the test."""
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_full_pipeline_execution(self):
        """Test the complete evolution pipeline from reflection to promotion."""
        try:
            # Step 1: Reflection Parser
            reflection_data = {"content": "Improve the add function to handle negative numbers"}
            parsed_reflection = self.reflection_parser.parse(reflection_data)
            self.assertIsNotNone(parsed_reflection, "Reflection parser returned None")
            self.assertIn("goal", parsed_reflection, "Parsed reflection missing 'goal' key")
            self.assertEqual(
                parsed_reflection["goal"],
                "Improve the add function to handle negative numbers",
                f"Unexpected goal: {parsed_reflection['goal']}"
            )
            # Assertion 1: reflection_parser returns valid JSON with required keys
            self.assertIsInstance(parsed_reflection, dict, 
                "Step 1 FAILED: reflection_parser should return a dict, got {type(parsed_reflection).__name__}")
            self.assertIn("current_assessment", parsed_reflection,
                "Step 1 FAILED: reflection_parser result missing 'current_assessment' key. Keys present: " + 
                str(list(parsed_reflection.keys())))
            self.assertIn("key_gaps", parsed_reflection,
                "Step 1 FAILED: reflection_parser result missing 'key_gaps' key. Keys present: " + 
                str(list(parsed_reflection.keys())))
            self.assertIn("next_priority", parsed_reflection,
                "Step 1 FAILED: reflection_parser result missing 'next_priority' key. Keys present: " + 
                str(list(parsed_reflection.keys())))
            self.assertIsInstance(parsed_reflection["key_gaps"], list,
                "Step 1 FAILED: 'key_gaps' should be a list, got {type(parsed_reflection['key_gaps']).__name__}")
            self.assertIsInstance(parsed_reflection["next_priority"], str,
                "Step 1 FAILED: 'next_priority' should be a string, got {type(parsed_reflection['next_priority']).__name__}")
            print("✓ Reflection parser step passed")

            # Step 2: Goal Generator
            goal = self.goal_generator.generate_goal(parsed_reflection)
            self.assertIsNotNone(goal, "Goal generator returned None")
            self.assertIn("description", goal, "Goal missing 'description' key")
            self.assertIn("constraints", goal, "Goal missing 'constraints' key")
            self.assertIsInstance(goal["constraints"], list, "Constraints should be a list")
            # Assertion 2: goal_generator produces a goal that matches one of the key_gaps
            self.assertIsInstance(goal, dict,
                "Step 2 FAILED: goal_generator should return a dict, got {type(goal).__name__}")
            self.assertIn("goal_text", goal,
                "Step 2 FAILED: goal missing 'goal_text' key. Keys present: " + str(list(goal.keys())))
            goal_text = goal.get("goal_text", "")
            key_gaps = parsed_reflection.get("key_gaps", [])
            goal_matches_gap = any(gap.lower() in goal_text.lower() or goal_text.lower() in gap.lower() 
                                  for gap in key_gaps)
            self.assertTrue(goal_matches_gap,
                "Step 2 FAILED: Goal '{goal_text}' does not match any key_gaps: {key_gaps}. "
                "The generated goal should address one of the identified gaps.")
            print("✓ Goal generator step passed")

            # Step 3: Mutation Engine (using mock)
            mutation = self.mock_mutation_engine.generate_mutation(goal)
            self.assertIsNotNone(mutation, "Mutation engine returned None")
            self.assertEqual(mutation["mutation_id"], "test_mutation_001", "Unexpected mutation ID")
            self.assertTrue(mutation["valid"], "Mutation should be valid")
            self.assertIn("code", mutation, "Mutation missing 'code' key")
            # Assertion 3: mutation_engine in mock mode returns a valid mutation dict with required keys
            self.assertIsInstance(mutation, dict,
                "Step 3 FAILED: mutation_engine should return a dict, got {type(mutation).__name__}")
            self.assertIn("file", mutation,
                "Step 3 FAILED: mutation missing 'file' key. Keys present: " + str(list(mutation.keys())))
            self.assertIn("change", mutation,
                "Step 3 FAILED: mutation missing 'change' key. Keys present: " + str(list(mutation.keys())))
            self.assertIn("rollback", mutation,
                "Step 3 FAILED: mutation missing 'rollback' key. Keys present: " + str(list(mutation.keys())))
            self.assertIsInstance(mutation["file"], str,
                "Step 3 FAILED: 'file' should be a string, got {type(mutation['file']).__name__}")
            self.assertIsInstance(mutation["change"], str,
                "Step 3 FAILED: 'change' should be a string, got {type(mutation['change']).__name__}")
            self.assertIsInstance(mutation["rollback"], str,
                "Step 3 FAILED: 'rollback' should be a string, got {type(mutation['rollback']).__name__}")
            print("✓ Mutation engine step passed")

            # Step 4: Test Runner
            test_results = self.test_runner.run_tests(mutation)
            self.assertIsNotNone(test_results, "Test runner returned None")
            self.assertIn("passed", test_results, "Test results missing 'passed' key")
            self.assertIn("failed", test_results, "Test results missing 'failed' key")
            self.assertIn("errors", test_results, "Test results missing 'errors' key")
            self.assertIsInstance(test_results["passed"], list, "Passed tests should be a list")
            self.assertIsInstance(test_results["failed"], list, "Failed tests should be a list")
            self.assertIsInstance(test_results["errors"], list, "Errors should be a list")
            # Assertion 4: test_runner executes the mutation and returns a test result
            self.assertIsInstance(test_results, dict,
                "Step 4 FAILED: test_runner should return a dict, got {type(test_results).__name__}")
            self.assertIn("test_result", test_results,
                "Step 4 FAILED: test_results missing 'test_result' key. Keys present: " + str(list(test_results.keys())))
            test_result = test_results.get("test_result", "")
            self.assertIn(test_result, ["passed", "failed", "error"],
                "Step 4 FAILED: 'test_result' should be one of 'passed', 'failed', or 'error', got '{test_result}'")
            print("✓ Test runner step passed")

            # Step 5: Promotion Logic
            promotion_result = self.promotion_logic.evaluate(mutation, test_results)
            self.assertIsNotNone(promotion_result, "Promotion logic returned None")
            self.assertIn("promoted", promotion_result, "Promotion result missing 'promoted' key")
            self.assertIn("reason", promotion_result, "Promotion result missing 'reason' key")
            self.assertIsInstance(promotion_result["promoted"], bool, "Promoted should be a boolean")
            # Assertion 5: promotion logic correctly promotes or reverts based on test result
            self.assertIsInstance(promotion_result, dict,
                "Step 5 FAILED: promotion_logic should return a dict, got {type(promotion_result).__name__}")
            self.assertIn("action", promotion_result,
                "Step 5 FAILED: promotion_result missing 'action' key. Keys present: " + str(list(promotion_result.keys())))
            action = promotion_result.get("action", "")
            test_result = test_results.get("test_result", "")
            if test_result == "passed":
                self.assertEqual(action, "promote",
                    "Step 5 FAILED: When test_result is 'passed', action should be 'promote', got '{action}'")
            else:
                self.assertEqual(action, "revert",
                    "Step 5 FAILED: When test_result is '{test_result}', action should be 'revert', got '{action}'")
            print("✓ Promotion logic step passed")

            # Step 6: Verify all steps produced expected outputs
            self.assertTrue(
                parsed_reflection["goal"] == "Improve the add function to handle negative numbers",
                "Reflection goal mismatch"
            )
            self.assertTrue(
                len(goal["constraints"]) > 0,
                "Goal should have at least one constraint"
            )
            self.assertTrue(
                mutation["valid"],
                "Mutation should be marked as valid"
            )
            self.assertTrue(
                len(test_results["passed"]) + len(test_results["failed"]) + len(test_results["errors"]) > 0,
                "Test results should contain at least one test outcome"
            )
            self.assertIsInstance(
                promotion_result["promoted"],
                bool,
                "Promotion result should be boolean"
            )

            print("\n✓ All pipeline steps completed successfully")
        finally:
            # Ensure sandbox directory is cleaned up even if test fails
            if os.path.exists(self.test_dir):
                shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_pipeline_with_invalid_mutation(self):
        """Test the pipeline handles invalid mutations gracefully."""
        try:
            # Override mock to return invalid mutation
            self.mock_mutation_engine.generate_mutation.return_value = {
                "mutation_id": "invalid_mutation",
                "code": "",
                "description": "Empty mutation",
                "valid": False
            }

            # Run through the pipeline
            reflection_data = {"content": "Fix the broken function"}
            parsed_reflection = self.reflection_parser.parse(reflection_data)
            goal = self.goal_generator.generate_goal(parsed_reflection)
            mutation = self.mock_mutation_engine.generate_mutation(goal)

            # Assert invalid mutation is handled
            self.assertFalse(mutation["valid"], "Mutation should be marked as invalid")
            self.assertEqual(mutation["code"], "", "Invalid mutation should have empty code")

            # Test runner should handle invalid mutation
            with self.assertRaises(ValueError) as context:
                self.test_runner.run_tests(mutation)
            self.assertIn("invalid", str(context.exception).lower(), "Error should mention invalid mutation")

            print("✓ Invalid mutation handling passed")
        finally:
            # Ensure sandbox directory is cleaned up even if test fails
            if os.path.exists(self.test_dir):
                shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_pipeline_with_missing_goal(self):
        """Test the pipeline handles missing goal gracefully."""
        try:
            reflection_data = {"content": ""}
            parsed_reflection = self.reflection_parser.parse(reflection_data)

            # Goal generator should handle empty reflection
            with self.assertRaises(ValueError) as context:
                self.goal_generator.generate_goal(parsed_reflection)
            self.assertIn("goal", str(context.exception).lower(), "Error should mention missing goal")

            print("✓ Missing goal handling passed")
        finally:
            # Ensure sandbox directory is cleaned up even if test fails
            if os.path.exists(self.test_dir):
                shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_self_validating_pipeline(self):
        """Test that the test itself fails with clear diagnostic if any step is broken.
        
        This test temporarily corrupts the reflection parser output to verify that
        the test assertions properly detect and report failures.
        """
        try:
            # Temporarily corrupt the reflection parser output
            original_parse = self.reflection_parser.parse
            def corrupted_parse(data):
                result = original_parse(data)
                # Corrupt the result by removing required keys
                if isinstance(result, dict):
                    result.pop("current_assessment", None)
                    result.pop("key_gaps", None)
                    result.pop("next_priority", None)
                return result
            
            self.reflection_parser.parse = corrupted_parse
            
            # Attempt to run the pipeline - this should fail with clear diagnostic
            reflection_data = {"content": "Improve the add function to handle negative numbers"}
            parsed_reflection = self.reflection_parser.parse(reflection_data)
            
            # This assertion should fail with a clear message about missing keys
            with self.assertRaises(AssertionError) as context:
                self.assertIn("current_assessment", parsed_reflection,
                    "Step 1 FAILED: reflection_parser result missing 'current_assessment' key. Keys present: " + 
                    str(list(parsed_reflection.keys())))
            
            error_message = str(context.exception)
            self.assertIn("Step 1 FAILED", error_message, 
                "Error message should contain step identification")
            self.assertIn("current_assessment", error_message,
                "Error message should mention the missing key")
            self.assertIn("key_gaps", error_message,
                "Error message should mention other missing keys")
            
            print("✓ Self-validating test passed - corrupted reflection parser correctly detected")
            
        finally:
            # Restore original parser
            self.reflection_parser.parse = original_parse
            # Ensure sandbox directory is cleaned up even if test fails
            if os.path.exists(self.test_dir):
                shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_triage_integration(self):
        """Test the triage integration: creates a sandbox with a known broken module,
        runs the orchestrator with a short triage interval, and verifies the broken
        module gets archived after 3 cycles."""
        try:
            # Create a known broken module
            broken_module_path = self.sandbox_path / "modules" / "broken_module.py"
            with open(broken_module_path, 'w') as f:
                f.write("def broken_function():\n    return 1/0  # This will always fail\n")
            
            # Create a test for the broken module
            test_file_path = self.sandbox_path / "tests" / "test_broken_module.py"
            with open(test_file_path, 'w') as f:
                f.write("""
import sys
sys.path.insert(0, '..')
from modules.broken_module import broken_function

def test_broken_function():
    assert broken_function() == 1, "Expected 1"
""")
            
            # Initialize the triage engine with the broken module
            self.triage_engine.register_module("broken_module", broken_module_path)
            
            # Run the orchestrator for 3 cycles
            for cycle in range(3):
                self.orchestrator.run_cycle()
            
            # Verify the broken module has been archived
            archived_path = self.sandbox_path / "archive" / "broken_module.py"
            self.assertTrue(
                archived_path.exists(),
                f"Broken module should be archived after 3 cycles, but {archived_path} does not exist"
            )
            
            # Verify the original module is no longer in the modules directory
            self.assertFalse(
                broken_module_path.exists(),
                f"Broken module should no longer be in modules directory after archiving"
            )
            
            # Verify the triage engine has recorded the archiving
            triage_log = self.sandbox_path / "logs" / "triage.log"
            self.assertTrue(
                triage_log.exists(),
                "Triage log should exist after archiving"
            )
            
            with open(triage_log, 'r') as f:
                log_content = f.read()
                self.assertIn(
                    "archived",
                    log_content.lower(),
                    "Triage log should contain 'archived' for the broken module"
                )
                self.assertIn(
                    "broken_module",
                    log_content,
                    "Triage log should mention the broken module name"
                )
            
            print("✓ Triage integration test passed - broken module correctly archived after 3 cycles")
            
        finally:
            # Ensure sandbox directory is cleaned up even if test fails
            if os.path.exists(self.test_dir):
                shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_file_creation_failure_pattern_detection(self):
        """Integration test that verifies the meta_monitor detects a pattern of 3 consecutive
        failing goals in the 'file_creation' category, triggers reprioritization to block
        file_creation goals, generates a root cause hypothesis, and allows a new file_creation
        goal after hypothesis generation."""
        try:
            # Step 1: Create 3 consecutive failing goals in 'file_creation' category
            for i in range(3):
                goal_data = {
                    "goal_id": f"file_creation_goal_{i+1}",
                    "category": "file_creation",
                    "description": f"Test file creation goal {i+1}",
                    "status": "failed",
                    "failure_reason": "Test failure for pattern detection"
                }
                self.meta_monitor.record_goal(goal_data)
            
            # Step 2: Verify meta_monitor detects the pattern
            pattern_detected = self.meta_monitor.detect_pattern(
                category="file_creation",
                pattern_type="consecutive_failures",
                threshold=3
            )
            self.assertTrue(
                pattern_detected,
                "MetaMonitor should detect pattern of 3 consecutive failures in file_creation category"
            )
            
            # Verify the pattern is recorded in the meta_monitor's state
            pattern_state = self.meta_monitor.get_pattern_state("file_creation")
            self.assertIsNotNone(
                pattern_state,
                "Pattern state should exist for file_creation category"
            )
            self.assertEqual(
                pattern_state["consecutive_failures"],
                3,
                f"Expected 3 consecutive failures, got {pattern_state['consecutive_failures']}"
            )
            print("✓ Pattern detection verified - 3 consecutive failures detected")
            
            # Step 3: Verify reprioritization blocks file_creation goals
            reprioritization_result = self.reprioritization_engine.evaluate(
                category="file_creation",
                pattern_state=pattern_state
            )
            self.assertIsNotNone(
                reprioritization_result,
                "Reprioritization should return a result"
            )
            self.assertTrue(
                reprioritization_result["blocked"],
                "Reprioritization should block file_creation goals after 3 consecutive failures"
            )
            self.assertEqual(
                reprioritization_result["blocked_category"],
                "file_creation",
                f"Blocked category should be 'file_creation', got '{reprioritization_result['blocked_category']}'"
            )
            self.assertIn(
                "reason",
                reprioritization_result,
                "Reprioritization result should include a reason"
            )
            
            # Verify that attempting to create a new file_creation goal is blocked
            new_goal_data = {
                "goal_id": "blocked_file_creation_goal",
                "category": "file_creation",
                "description": "This goal should be blocked"
            }
            is_blocked = self.reprioritization_engine.is_goal_blocked(new_goal_data)
            self.assertTrue(
                is_blocked,
                "New file_creation goal should be blocked by reprioritization"
            )
            print("✓ Reprioritization verified - file_creation goals are blocked")
            
            # Step 4: Verify a root cause hypothesis is generated
            hypothesis = self.hypothesis_generator.generate_hypothesis(
                category="file_creation",
                pattern_state=pattern_state,
                reprioritization_result=reprioritization_result
            )
            self.assertIsNotNone(
                hypothesis,
                "Hypothesis generator should produce a hypothesis"
            )
            self.assertIn(
                "hypothesis_text",
                hypothesis,
                "Hypothesis should contain 'hypothesis_text' key"
            )
            self.assertIn(
                "root_cause",
                hypothesis,
                "Hypothesis should contain 'root_cause' key"
            )
            self.assertIn(
                "confidence",
                hypothesis,
                "Hypothesis should contain 'confidence' key"
            )
            self.assertGreater(
                hypothesis["confidence"],
                0,
                "Hypothesis confidence should be greater than 0"
            )
            self.assertLessEqual(
                hypothesis["confidence"],
                1.0,
                "Hypothesis confidence should be less than or equal to 1.0"
            )
            
            # Verify the hypothesis is logged
            hypothesis_log = self.sandbox_path / "logs" / "hypothesis.log"
            self.assertTrue(
                hypothesis_log.exists(),
                "Hypothesis log should exist after hypothesis generation"
            )
            with open(hypothesis_log, 'r') as f:
                log_content = f.read()
                self.assertIn(
                    "file_creation",
                    log_content,
                    "Hypothesis log should mention file_creation category"
                )
                self.assertIn(
                    hypothesis["hypothesis_text"],
                    log_content,
                    "Hypothesis log should contain the generated hypothesis text"
                )
            print("✓ Root cause hypothesis generated and logged")
            
            # Step 5: Verify that after hypothesis generation, a new file_creation goal can be attempted
            # Simulate hypothesis resolution
            resolution_result = self.hypothesis_generator.resolve_hypothesis(hypothesis["hypothesis_id"])
            self.assertTrue(
                resolution_result["resolved"],
                "Hypothesis should be resolvable"
            )
            
            # Clear the pattern state to allow new attempts
            self.meta_monitor.clear_pattern_state("file_creation")
            
            # Verify the reprioritization is updated
            updated_reprioritization = self.reprioritization_engine.evaluate(
                category="file_creation",
                pattern_state=self.meta_monitor.get_pattern_state("file_creation")
            )
            self.assertFalse(
                updated_reprioritization["blocked"],
                "After hypothesis resolution, file_creation goals should no longer be blocked"
            )
            
            # Attempt a new file_creation goal
            new_goal_data = {
                "goal_id": "new_file_creation_goal",
                "category": "file_creation",
                "description": "New file creation goal after hypothesis resolution"
            }
            is_blocked = self.reprioritization_engine.is_goal_blocked(new_goal_data)
            self.assertFalse(
                is_blocked,
                "New file_creation goal should be allowed after hypothesis resolution"
            )
            
            # Verify the goal can be processed
            goal_accepted = self.goal_generator.accept_goal(new_goal_data)
            self.assertTrue(
                goal_accepted,
                "Goal generator should accept the new file_creation goal"
            )
            
            # Verify the orchestrator can process the new goal
            cycle_result = self.orchestrator.process_goal(new_goal_data)
            self.assertIsNotNone(
                cycle_result,
                "Orchestrator should process the new file_creation goal"
            )
            self.assertIn(
                "status",
                cycle_result,
                "Cycle result should include a status"
            )
            self.assertEqual(
                cycle_result["status"],
                "processed",
                f"Expected status 'processed', got '{cycle_result['status']}'"
            )
            
            print("✓ New file_creation goal successfully attempted after hypothesis generation")
            print("\n✓ Complete file_creation failure pattern detection integration test passed")
            
        finally:
            # Ensure sandbox directory is cleaned up even if test fails
            if os.path.exists(self.test_dir):
                shutil.rmtree(self.test_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)