import unittest
from unittest.mock import patch, MagicMock
from core.coordinated_mutation_planner import CoordinatedMutationPlanner

class TestCoordinatedMutation(unittest.TestCase):
    def setUp(self):
        self.planner = CoordinatedMutationPlanner()
        
        # Create mock modules
        self.module_a = MagicMock()
        self.module_a.name = "module_a"
        self.module_a.f = MagicMock(return_value=1)
        
        self.module_b = MagicMock()
        self.module_b.name = "module_b"
        self.module_b.g = MagicMock(side_effect=lambda: self.module_a.f() + 1)
        
        self.modules = {"module_a": self.module_a, "module_b": self.module_b}

    def test_plan_generation(self):
        """Test that coordinated plan is generated correctly"""
        plan = self.planner.generate_coordinated_mutations(self.modules)
        
        self.assertIsNotNone(plan)
        self.assertIn("module_a", plan)
        self.assertIn("module_b", plan)
        
        # Verify module_a plan changes f() to return 2
        self.assertEqual(plan["module_a"]["target"], "f")
        self.assertEqual(plan["module_a"]["new_return_value"], 2)
        
        # Verify module_b plan updates g() to use new return value
        self.assertEqual(plan["module_b"]["target"], "g")
        self.assertTrue("2" in str(plan["module_b"]["new_implementation"]) or 
                       "new_return_value" in str(plan["module_b"]["new_implementation"]))

    def test_atomic_application(self):
        """Test that plan is applied atomically and both modules change"""
        # Generate and apply plan
        plan = self.planner.generate_coordinated_mutations(self.modules)
        result = self.planner.apply_plan_atomically(self.modules, plan)
        
        self.assertTrue(result)
        
        # Verify module_a changed
        self.assertEqual(self.module_a.f(), 2)
        
        # Verify module_b changed and uses new return value
        self.assertEqual(self.module_b.g(), 3)  # f() returns 2, so g() returns 3

    def test_rollback_on_failure(self):
        """Test that changes are reverted if second module change fails"""
        # Generate plan
        plan = self.planner.generate_coordinated_mutations(self.modules)
        
        # Simulate failure in module_b change
        with patch.object(self.planner, '_apply_single_mutation', side_effect=[
            True,  # module_a succeeds
            False  # module_b fails
        ]):
            result = self.planner.apply_plan_atomically(self.modules, plan)
            
            self.assertFalse(result)
            
            # Verify module_a was reverted
            self.assertEqual(self.module_a.f(), 1)
            
            # Verify module_b was not changed
            self.assertEqual(self.module_b.g(), 2)  # f() still returns 1

    def test_rollback_restores_original_state(self):
        """Test that rollback completely restores original state"""
        original_a_return = self.module_a.f()
        original_b_return = self.module_b.g()
        
        plan = self.planner.generate_coordinated_mutations(self.modules)
        
        # Force failure during application
        with patch.object(self.planner, '_apply_single_mutation', return_value=False):
            result = self.planner.apply_plan_atomically(self.modules, plan)
            
            self.assertFalse(result)
            
            # Verify complete restoration
            self.assertEqual(self.module_a.f(), original_a_return)
            self.assertEqual(self.module_b.g(), original_b_return)

if __name__ == '__main__':
    unittest.main()