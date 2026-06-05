import unittest
from unittest.mock import patch, MagicMock
import copy
import sys
import os

# Add parent directory to path to import the module under test
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from recursive_sandbox import RecursiveSandbox, SandboxState, SandboxError


class TestRecursiveSandbox(unittest.TestCase):
    """Comprehensive test suite for RecursiveSandbox."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.initial_state = {"data": {"value": 1, "items": [1, 2, 3]}, "config": {"enabled": True}}
        self.sandbox = RecursiveSandbox(self.initial_state)
    
    def test_clone_creates_isolated_copies(self):
        """Test that cloning creates isolated copies that don't share state."""
        clone = self.sandbox.clone()
        
        # Verify clone has same initial state
        self.assertEqual(clone.state, self.sandbox.state)
        
        # Modify original - clone should be unaffected
        self.sandbox.state["data"]["value"] = 999
        self.assertNotEqual(clone.state["data"]["value"], self.sandbox.state["data"]["value"])
        self.assertEqual(clone.state["data"]["value"], 1)
        
        # Modify clone - original should be unaffected
        clone.state["data"]["items"].append(4)
        self.assertNotIn(4, self.sandbox.state["data"]["items"])
        
        # Verify deep copy behavior for nested structures
        self.assertIsNot(clone.state["data"], self.sandbox.state["data"])
        self.assertIsNot(clone.state["data"]["items"], self.sandbox.state["data"]["items"])
    
    def test_mutations_applied_correctly_to_clones(self):
        """Test that mutations are applied correctly to cloned sandboxes."""
        clone = self.sandbox.clone()
        
        # Apply mutation to clone
        mutation_result = clone.apply_mutation({"data": {"value": 42, "items": [4, 5, 6]}})
        self.assertTrue(mutation_result)
        self.assertEqual(clone.state["data"]["value"], 42)
        self.assertEqual(clone.state["data"]["items"], [4, 5, 6])
        
        # Original should remain unchanged
        self.assertEqual(self.sandbox.state["data"]["value"], 1)
        self.assertEqual(self.sandbox.state["data"]["items"], [1, 2, 3])
        
        # Test partial mutation
        clone2 = self.sandbox.clone()
        clone2.apply_mutation({"config": {"enabled": False}})
        self.assertFalse(clone2.state["config"]["enabled"])
        self.assertTrue(self.sandbox.state["config"]["enabled"])
    
    def test_test_suite_runs_on_clones(self):
        """Test that test suite runs correctly on cloned sandboxes."""
        clone = self.sandbox.clone()
        
        # Define a test suite that checks state
        def test_suite(state):
            return state["data"]["value"] == 1 and state["config"]["enabled"]
        
        # Test should pass on clone with initial state
        result = clone.run_tests(test_suite)
        self.assertTrue(result)
        
        # Modify clone and test again
        clone.apply_mutation({"data": {"value": 2}})
        result = clone.run_tests(test_suite)
        self.assertFalse(result)
        
        # Test with multiple test functions
        def test_value_positive(state):
            return state["data"]["value"] > 0
        
        def test_items_not_empty(state):
            return len(state["data"]["items"]) > 0
        
        results = clone.run_tests([test_value_positive, test_items_not_empty])
        self.assertTrue(all(results))
        
        # Test with failing test
        def test_fail(state):
            return False
        
        result = clone.run_tests(test_fail)
        self.assertFalse(result)
    
    def test_merge_only_on_pass(self):
        """Test that merge only happens when tests pass."""
        # Create clone and modify it
        clone = self.sandbox.clone()
        clone.apply_mutation({"data": {"value": 5}})
        
        # Define passing test
        def passing_test(state):
            return state["data"]["value"] == 5
        
        # Merge should succeed when tests pass
        merge_result = self.sandbox.merge(clone, passing_test)
        self.assertTrue(merge_result)
        self.assertEqual(self.sandbox.state["data"]["value"], 5)
        
        # Reset sandbox
        self.sandbox = RecursiveSandbox(self.initial_state)
        clone2 = self.sandbox.clone()
        clone2.apply_mutation({"data": {"value": 10}})
        
        # Define failing test
        def failing_test(state):
            return state["data"]["value"] < 5
        
        # Merge should fail when tests fail
        merge_result = self.sandbox.merge(clone2, failing_test)
        self.assertFalse(merge_result)
        self.assertEqual(self.sandbox.state["data"]["value"], 1)  # Original unchanged
    
    def test_rollback_restores_previous_state(self):
        """Test that rollback restores the sandbox to its previous state."""
        # Save initial state
        initial_state = copy.deepcopy(self.sandbox.state)
        
        # Apply some changes
        self.sandbox.apply_mutation({"data": {"value": 100}})
        self.assertEqual(self.sandbox.state["data"]["value"], 100)
        
        # Rollback
        rollback_result = self.sandbox.rollback()
        self.assertTrue(rollback_result)
        self.assertEqual(self.sandbox.state, initial_state)
        
        # Test multiple rollbacks
        self.sandbox.apply_mutation({"data": {"value": 200}})
        self.sandbox.apply_mutation({"data": {"value": 300}})
        self.sandbox.rollback()
        self.assertEqual(self.sandbox.state["data"]["value"], 200)
        self.sandbox.rollback()
        self.assertEqual(self.sandbox.state["data"]["value"], 1)
        
        # Test rollback with no history
        self.sandbox.rollback()  # Should not error
        self.assertEqual(self.sandbox.state["data"]["value"], 1)
    
    def test_rollback_triggers_on_immediate_test_failure_after_merge(self):
        """Test that rollback triggers automatically when tests fail immediately after merge."""
        # Create clone and modify
        clone = self.sandbox.clone()
        clone.apply_mutation({"data": {"value": 50}})
        
        # This test should pass initially but fail after merge
        def initially_passing_test(state):
            return state["data"]["value"] == 50
        
        # Perform merge with auto-rollback on failure
        merge_result = self.sandbox.merge_with_rollback(clone, initially_passing_test)
        self.assertTrue(merge_result)
        self.assertEqual(self.sandbox.state["data"]["value"], 50)
        
        # Now simulate a scenario where merge succeeds but subsequent test fails
        # Reset sandbox
        self.sandbox = RecursiveSandbox(self.initial_state)
        clone2 = self.sandbox.clone()
        clone2.apply_mutation({"data": {"value": 75}})
        
        # Define a test that passes on clone but would fail after merge due to side effects
        def test_with_side_effects(state):
            # This test passes, but after merge we check again and it fails
            return True
        
        # Mock to simulate immediate failure after merge
        original_merge = self.sandbox.merge
        
        def mock_merge_with_rollback(clone, test_func):
            # First do the merge
            result = original_merge(clone, test_func)
            if result:
                # Immediately run a test that fails
                def failing_post_merge_test(state):
                    return state["data"]["value"] < 50
                
                if not failing_post_merge_test(self.sandbox.state):
                    # Rollback
                    self.sandbox.rollback()
                    return False
            return result
        
        with patch.object(self.sandbox, 'merge', mock_merge_with_rollback):
            result = self.sandbox.merge(clone2, test_with_side_effects)
            self.assertFalse(result)
            self.assertEqual(self.sandbox.state["data"]["value"], 1)  # Should be rolled back
    
    def test_merge_with_rollback_method(self):
        """Test the merge_with_rollback method directly."""
        # Test case where merge succeeds and post-merge test passes
        clone = self.sandbox.clone()
        clone.apply_mutation({"data": {"value": 2}})
        
        def passing_test(state):
            return state["data"]["value"] == 2
        
        def passing_post_test(state):
            return state["data"]["value"] > 0
        
        result = self.sandbox.merge_with_rollback(clone, passing_test, passing_post_test)
        self.assertTrue(result)
        self.assertEqual(self.sandbox.state["data"]["value"], 2)
        
        # Test case where merge succeeds but post-merge test fails
        self.sandbox = RecursiveSandbox(self.initial_state)
        clone2 = self.sandbox.clone()
        clone2.apply_mutation({"data": {"value": 100}})
        
        def failing_post_test(state):
            return state["data"]["value"] < 50
        
        result = self.sandbox.merge_with_rollback(clone2, passing_test, failing_post_test)
        self.assertFalse(result)
        self.assertEqual(self.sandbox.state["data"]["value"], 1)  # Rolled back
    
    def test_nested_sandbox_operations(self):
        """Test recursive sandbox operations with nested sandboxes."""
        # Create a sandbox that contains another sandbox
        inner_sandbox = RecursiveSandbox({"inner_value": 1})
        outer_state = {"outer": self.sandbox, "inner": inner_sandbox}
        outer_sandbox = RecursiveSandbox(outer_state)
        
        # Clone outer sandbox
        outer_clone = outer_sandbox.clone()
        
        # Verify isolation
        outer_sandbox.state["outer"].apply_mutation({"data": {"value": 999}})
        self.assertEqual(outer_clone.state["outer"].state["data"]["value"], 1)
        
        # Test merge with nested sandboxes
        outer_clone.state["inner"].apply_mutation({"inner_value": 42})
        merge_result = outer_sandbox.merge(outer_clone, lambda s: s["inner"].state["inner_value"] == 42)
        self.assertTrue(merge_result)
        self.assertEqual(outer_sandbox.state["inner"].state["inner_value"], 42)


if __name__ == '__main__':
    unittest.main()