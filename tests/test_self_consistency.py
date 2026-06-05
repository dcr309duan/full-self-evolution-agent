import os
import sys
import json
import tempfile
import shutil
import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path

# Add parent directory to path to import project modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import project modules (adjust imports based on actual project structure)
try:
    from mutation_engine import MutationEngine
    from reflection_parser import ReflectionParser
    from goal_generator import GoalGenerator
except ImportError:
    # Mock modules for testing if not available
    MutationEngine = MagicMock()
    ReflectionParser = MagicMock()
    GoalGenerator = MagicMock()


class TestSelfConsistency(unittest.TestCase):
    """Test suite for self-consistency checks across mutation, reflection, and goal generation."""

    def setUp(self):
        """Set up test environment with temporary directory and mock state."""
        self.test_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        os.chdir(self.test_dir)
        
        # Create a sample file structure for testing
        self.sample_file = Path(self.test_dir) / "sample.py"
        self.sample_file.write_text("def hello():\n    return 'world'\n")
        
        # Initialize components with test configuration
        self.mutation_engine = MutationEngine(workspace=self.test_dir)
        self.reflection_parser = ReflectionParser()
        self.goal_generator = GoalGenerator()
        
        # Track mutations for rollback testing
        self.mutation_history = []

    def tearDown(self):
        """Clean up temporary directory."""
        os.chdir(self.original_cwd)
        shutil.rmtree(self.test_dir)

    # ========== Mutation Engine Consistency Tests ==========

    def test_mutation_output_matches_actual_code_state(self):
        """Verify that generated mutations match actual file contents."""
        # Create a mutation that adds a new function
        original_content = self.sample_file.read_text()
        mutation_result = self.mutation_engine.generate_mutation(
            file_path=str(self.sample_file),
            mutation_type="add_function",
            function_name="new_func",
            function_body="return 42"
        )
        
        # Check that the mutation output matches the actual file state
        current_content = self.sample_file.read_text()
        self.assertIn("new_func", current_content,
                      "Mutation engine output should be reflected in actual file")
        self.assertNotEqual(original_content, current_content,
                           "File content should change after mutation")
        
        # Verify the mutation engine's recorded state matches reality
        if hasattr(self.mutation_engine, 'get_last_mutation'):
            last_mutation = self.mutation_engine.get_last_mutation()
            self.assertEqual(last_mutation['file_path'], str(self.sample_file))
            self.assertEqual(last_mutation['new_content'], current_content)

    def test_mutation_consistency_with_multiple_files(self):
        """Test mutation consistency across multiple files."""
        # Create additional files
        file2 = Path(self.test_dir) / "utils.py"
        file2.write_text("def helper():\n    pass\n")
        
        # Apply mutations to both files
        mut1 = self.mutation_engine.generate_mutation(
            file_path=str(self.sample_file),
            mutation_type="modify_function",
            function_name="hello",
            new_body="return 'modified'"
        )
        mut2 = self.mutation_engine.generate_mutation(
            file_path=str(file2),
            mutation_type="add_function",
            function_name="new_helper",
            function_body="return True"
        )
        
        # Verify both files reflect the mutations
        self.assertIn("modified", self.sample_file.read_text())
        self.assertIn("new_helper", file2.read_text())

    def test_mutation_rollback_on_failure(self):
        """Test that mutations are rolled back if consistency check fails."""
        original_content = self.sample_file.read_text()
        
        # Simulate a mutation that would fail consistency check
        with self.assertRaises(Exception):
            self.mutation_engine.generate_mutation(
                file_path=str(self.sample_file),
                mutation_type="invalid_mutation",
                force_failure=True  # Assume this triggers failure
            )
        
        # Verify file is unchanged after failed mutation
        current_content = self.sample_file.read_text()
        self.assertEqual(original_content, current_content,
                        "File should be unchanged after failed mutation")

    # ========== Reflection Parser Consistency Tests ==========

    def test_reflection_parser_output_matches_code_structure(self):
        """Verify reflection parser output matches actual code structure."""
        # Parse the sample file
        parsed_structure = self.reflection_parser.parse_file(str(self.sample_file))
        
        # Verify the parsed structure matches actual code
        self.assertIn("hello", parsed_structure.get('functions', []),
                     "Parser should detect 'hello' function")
        self.assertEqual(
            parsed_structure['functions']['hello']['return_type'],
            'str',
            "Parser should correctly identify return type"
        )
        
        # Modify the file and verify parser reflects changes
        self.sample_file.write_text("def goodbye():\n    return 'bye'\n")
        updated_structure = self.reflection_parser.parse_file(str(self.sample_file))
        self.assertIn("goodbye", updated_structure.get('functions', []),
                     "Parser should detect new function after modification")
        self.assertNotIn("hello", updated_structure.get('functions', []),
                        "Parser should no longer detect removed function")

    def test_reflection_parser_class_detection(self):
        """Test reflection parser correctly identifies class structures."""
        class_file = Path(self.test_dir) / "classes.py"
        class_file.write_text("""
class MyClass:
    def method1(self):
        pass
    
    def method2(self, x):
        return x * 2
""")
        
        parsed = self.reflection_parser.parse_file(str(class_file))
        self.assertIn("MyClass", parsed.get('classes', []))
        self.assertIn("method1", parsed['classes']['MyClass']['methods'])
        self.assertIn("method2", parsed['classes']['MyClass']['methods'])

    def test_reflection_parser_import_detection(self):
        """Test reflection parser correctly identifies imports."""
        import_file = Path(self.test_dir) / "imports.py"
        import_file.write_text("""
import os
import sys
from pathlib import Path
from typing import List, Optional
""")
        
        parsed = self.reflection_parser.parse_file(str(import_file))
        self.assertIn("os", parsed.get('imports', []))
        self.assertIn("sys", parsed.get('imports', []))
        self.assertIn("Path", parsed.get('imports', []))

    # ========== Goal Generator Consistency Tests ==========

    def test_goal_generator_output_achievable_given_capabilities(self):
        """Verify generated goals are achievable given current capabilities."""
        # Define current capabilities
        current_capabilities = {
            'has_functions': ['hello'],
            'has_classes': [],
            'has_imports': [],
            'code_complexity': 'low'
        }
        
        # Generate goals based on capabilities
        goals = self.goal_generator.generate_goals(
            current_state=current_capabilities,
            target_improvement="add_error_handling"
        )
        
        # Verify goals are achievable
        for goal in goals:
            self.assertTrue(
                self._is_goal_achievable(goal, current_capabilities),
                f"Goal '{goal['description']}' should be achievable"
            )
        
        # Test with limited capabilities
        limited_capabilities = {
            'has_functions': [],
            'has_classes': [],
            'has_imports': [],
            'code_complexity': 'minimal'
        }
        limited_goals = self.goal_generator.generate_goals(
            current_state=limited_capabilities,
            target_improvement="add_complex_feature"
        )
        
        # Goals should be simpler when capabilities are limited
        for goal in limited_goals:
            self.assertLessEqual(
                goal.get('complexity', 0),
                5,  # Assume complexity scale 1-10
                "Goals should have limited complexity with minimal capabilities"
            )

    def test_goal_generator_incremental_improvement(self):
        """Test that goals suggest incremental improvements."""
        capabilities = {
            'has_functions': ['basic_func'],
            'has_classes': [],
            'has_imports': ['os'],
            'code_complexity': 'low'
        }
        
        goals = self.goal_generator.generate_goals(
            current_state=capabilities,
            target_improvement="add_testing"
        )
        
        # Verify goals build on existing capabilities
        for goal in goals:
            if 'dependency' in goal:
                self.assertIn(
                    goal['dependency'],
                    capabilities['has_functions'] + capabilities['has_classes'],
                    f"Goal dependency '{goal['dependency']}' should exist in capabilities"
                )

    # ========== Rollback Trigger Tests ==========

    def test_rollback_trigger_reverts_last_mutation_on_failure(self):
        """Test that rollback trigger reverts last mutation when checks fail."""
        # Store initial state
        initial_content = self.sample_file.read_text()
        
        # Apply a mutation
        self.mutation_engine.generate_mutation(
            file_path=str(self.sample_file),
            mutation_type="modify_function",
            function_name="hello",
            new_body="return 'modified'"
        )
        modified_content = self.sample_file.read_text()
        self.assertNotEqual(initial_content, modified_content)
        
        # Simulate a consistency check failure
        with patch.object(self.mutation_engine, 'check_consistency', return_value=False):
            rollback_success = self._trigger_rollback(
                component="mutation_engine",
                last_mutation_id=self.mutation_engine.get_last_mutation_id()
            )
            self.assertTrue(rollback_success, "Rollback should succeed")
        
        # Verify rollback reverted the change
        current_content = self.sample_file.read_text()
        self.assertEqual(initial_content, current_content,
                        "Content should be reverted to initial state after rollback")

    def test_rollback_trigger_with_multiple_mutations(self):
        """Test rollback correctly handles multiple mutations."""
        # Apply two mutations
        self.mutation_engine.generate_mutation(
            file_path=str(self.sample_file),
            mutation_type="add_function",
            function_name="func1",
            function_body="return 1"
        )
        content_after_first = self.sample_file.read_text()
        
        self.mutation_engine.generate_mutation(
            file_path=str(self.sample_file),
            mutation_type="add_function",
            function_name="func2",
            function_body="return 2"
        )
        content_after_second = self.sample_file.read_text()
        
        # Rollback only the last mutation
        rollback_success = self._trigger_rollback(
            component="mutation_engine",
            last_mutation_id=self.mutation_engine.get_last_mutation_id()
        )
        self.assertTrue(rollback_success)
        
        # Verify only the last mutation was reverted
        current_content = self.sample_file.read_text()
        self.assertEqual(content_after_first, current_content,
                        "Only the last mutation should be reverted")
        self.assertIn("func1", current_content,
                     "First mutation should still be present")

    def test_rollback_trigger_with_reflection_failure(self):
        """Test rollback when reflection parser detects inconsistency."""
        # Apply mutation
        self.mutation_engine.generate_mutation(
            file_path=str(self.sample_file),
            mutation_type="modify_function",
            function_name="hello",
            new_body="return 'modified'"
        )
        
        # Simulate reflection parser finding inconsistency
        with patch.object(self.reflection_parser, 'validate_consistency', return_value=False):
            rollback_success = self._trigger_rollback(
                component="reflection_parser",
                last_mutation_id=self.mutation_engine.get_last_mutation_id()
            )
            self.assertTrue(rollback_success)
        
        # Verify rollback occurred
        self.assertNotIn("modified", self.sample_file.read_text())

    def test_rollback_trigger_with_goal_generator_failure(self):
        """Test rollback when goal generator determines goal is unachievable."""
        # Apply mutation that creates a complex feature
        self.mutation_engine.generate_mutation(
            file_path=str(self.sample_file),
            mutation_type="add_complex_feature",
            feature_name="machine_learning"
        )
        
        # Goal generator determines this is unachievable
        with patch.object(self.goal_generator, 'is_goal_achievable', return_value=False):
            rollback_success = self._trigger_rollback(
                component="goal_generator",
                last_mutation_id=self.mutation_engine.get_last_mutation_id()
            )
            self.assertTrue(rollback_success)
        
        # Verify rollback occurred
        self.assertNotIn("machine_learning", self.sample_file.read_text())

    def test_rollback_trigger_cleanup(self):
        """Test that rollback properly cleans up state."""
        # Apply mutation
        self.mutation_engine.generate_mutation(
            file_path=str(self.sample_file),
            mutation_type="add_function",
            function_name="temp_func",
            function_body="pass"
        )
        
        mutation_id = self.mutation_engine.get_last_mutation_id()
        
        # Perform rollback
        self._trigger_rollback(
            component="mutation_engine",
            last_mutation_id=mutation_id
        )
        
        # Verify mutation history is cleaned up
        self.assertNotIn(
            mutation_id,
            self.mutation_engine.get_mutation_history(),
            "Rolled back mutation should be removed from history"
        )

    # ========== Helper Methods ==========

    def _is_goal_achievable(self, goal, capabilities):
        """Check if a goal is achievable given current capabilities."""
        # This is a simplified check - implement based on actual logic
        required_capabilities = goal.get('requires', [])
        for req in required_capabilities:
            if req not in capabilities.get('has_functions', []) and \
               req not in capabilities.get('has_classes', []):
                return False
        
        # Check complexity constraints
        if goal.get('complexity', 0) > 7 and capabilities.get('code_complexity') == 'minimal':
            return False
            
        return True

    def _trigger_rollback(self, component, last_mutation_id):
        """Trigger rollback for the specified component."""
        # This should implement the actual rollback logic
        # For testing, we simulate the rollback
        if component == "mutation_engine":
            return self.mutation_engine.rollback_mutation(last_mutation_id)
        elif component == "reflection_parser":
            # Rollback via reflection parser
            return self.mutation_engine.rollback_mutation(last_mutation_id)
        elif component == "goal_generator":
            # Rollback via goal generator
            return self.mutation_engine.rollback_mutation(last_mutation_id)
        return False


class TestSelfConsistencyIntegration(unittest.TestCase):
    """Integration tests for self-consistency across all components."""

    def setUp(self):
        """Set up integration test environment."""
        self.test_dir = tempfile.mkdtemp()
        self.sample_file = Path(self.test_dir) / "main.py"
        self.sample_file.write_text("""
def existing_function():
    return "original"

class ExistingClass:
    def method(self):
        pass
""")
        
        # Initialize all components
        self.mutation_engine = MutationEngine(workspace=self.test_dir)
        self.reflection_parser = ReflectionParser()
        self.goal_generator = GoalGenerator()

    def tearDown(self):
        """Clean up integration test environment."""
        shutil.rmtree(self.test_dir)

    def test_full_consistency_workflow(self):
        """Test complete self-consistency workflow."""
        # Step 1: Generate mutation
        mutation_result = self.mutation_engine.generate_mutation(
            file_path=str(self.sample_file),
            mutation_type="add_function",
            function_name="new_function",
            function_body="return 'new'"
        )
        
        # Step 2: Verify mutation matches file state
        file_content = self.sample_file.read_text()
        self.assertIn("new_function", file_content)
        
        # Step 3: Verify reflection parser matches
        parsed = self.reflection_parser.parse_file(str(self.sample_file))
        self.assertIn("new_function", parsed.get('functions', []))
        
        # Step 4: Verify goal generator considers this achievable
        capabilities = {
            'has_functions': ['existing_function', 'new_function'],
            'has_classes': ['ExistingClass'],
            'code_complexity': 'medium'
        }
        goals = self.goal_generator.generate_goals(
            current_state=capabilities,
            target_improvement="add_error_handling"
        )
        
        # Step 5: If any check fails, trigger rollback
        all_checks_pass = (
            self._verify_mutation_consistency(mutation_result, file_content) and
            self._verify_reflection_consistency(parsed, file_content) and
            self._verify_goal_consistency(goals, capabilities)
        )
        
        if not all_checks_pass:
            self.mutation_engine.rollback_mutation(
                self.mutation_engine.get_last_mutation_id()
            )
            self.fail("Consistency check failed, mutation rolled back")
        
        self.assertTrue(all_checks_pass, "All consistency checks should pass")

    def _verify_mutation_consistency(self, mutation_result, actual_content):
        """Verify mutation result matches actual file content."""
        # Implement actual verification logic
        return mutation_result is not None and "new_function" in actual_content

    def _verify_reflection_consistency(self, parsed_structure, actual_content):
        """Verify reflection parser output matches actual code."""
        # Implement actual verification logic
        return "new_function" in parsed_structure.get('functions', [])

    def _verify_goal_consistency(self, goals, capabilities):
        """Verify goals are achievable given capabilities."""
        # Implement actual verification logic
        return len(goals) > 0


if __name__ == '__main__':
    unittest.main()