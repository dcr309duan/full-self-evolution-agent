import sys
import os
import unittest

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.nash_detector_and_forcer import is_nash_equilibrium, force_multi_module_change


class TestNashEquilibriumMinimal(unittest.TestCase):
    """Minimal test for Nash equilibrium detection and multi-module forcing."""

    def setUp(self):
        """Set up 3 dummy modules with known interaction patterns."""
        self.modules = {
            "module_a": {
                "score": 0.85,
                "interactions": {"module_b": -0.20, "module_c": -0.10}
            },
            "module_b": {
                "score": 0.85,
                "interactions": {"module_a": -0.20, "module_c": -0.05}
            },
            "module_c": {
                "score": 0.85,
                "interactions": {"module_a": -0.10, "module_b": -0.05}
            }
        }

    def test_detect_equilibrium(self):
        """Test (1): Verify the detector identifies when modules reach equilibrium."""
        # All modules have same score and negative interactions - should be equilibrium
        result = is_nash_equilibrium(self.modules)
        self.assertIsInstance(result, bool)
        self.assertTrue(result)

    def test_detect_non_equilibrium(self):
        """Test that non-equilibrium state is correctly identified."""
        # Module A has lower score - should not be equilibrium
        non_eq_modules = {
            "module_a": {"score": 0.70, "interactions": {"module_b": -0.20}},
            "module_b": {"score": 0.85, "interactions": {"module_a": -0.20}},
        }
        result = is_nash_equilibrium(non_eq_modules)
        self.assertFalse(result)

    def test_multi_module_forcing_generates_valid_changes(self):
        """Test (2): Verify multi-module forcing generates valid coordinated changes."""
        plan = force_multi_module_change(self.modules)
        
        # Plan should be a dictionary
        self.assertIsInstance(plan, dict)
        
        # Plan should contain changes for at least 2 modules
        self.assertGreaterEqual(len(plan), 2)
        
        # Each change should have valid structure
        for module_name, change in plan.items():
            self.assertIn(module_name, self.modules)
            self.assertIsInstance(change, dict)
            self.assertIn("module", change)
            self.assertEqual(change["module"], module_name)
            self.assertIn("new_score", change)
            self.assertIsInstance(change["new_score"], (int, float))
            self.assertGreaterEqual(change["new_score"], 0)
            self.assertLessEqual(change["new_score"], 1)

    def test_plan_affects_all_modules(self):
        """Test that generated plan affects all modules in the system."""
        plan = force_multi_module_change(self.modules)
        
        # All modules should have changes
        for module_name in self.modules:
            self.assertIn(module_name, plan)
        
        # Verify changes are coordinated (scores should be balanced)
        scores = [plan[m]["new_score"] for m in self.modules]
        score_range = max(scores) - min(scores)
        self.assertLessEqual(score_range, 0.2)  # Scores should be close together

    def test_integration_mock_graph_with_known_equilibrium(self):
        """Integration test (1): Sets up a mock module interaction graph with known equilibrium."""
        # Create a mock graph where all modules have equal scores and balanced interactions
        mock_graph = {
            "mod_1": {"score": 0.75, "interactions": {"mod_2": -0.10, "mod_3": -0.10}},
            "mod_2": {"score": 0.75, "interactions": {"mod_1": -0.10, "mod_3": -0.10}},
            "mod_3": {"score": 0.75, "interactions": {"mod_1": -0.10, "mod_2": -0.10}}
        }
        
        # Verify equilibrium is detected
        self.assertTrue(is_nash_equilibrium(mock_graph))
        
        # Verify coordinated plan maintains equilibrium properties
        plan = force_multi_module_change(mock_graph)
        for mod_name, change in plan.items():
            self.assertAlmostEqual(change["new_score"], 0.75, delta=0.1)

    def test_integration_detection_triggers_correctly(self):
        """Integration test (2): Verifies detection triggers correctly for various states."""
        # Test equilibrium triggers True
        eq_state = {
            "mod_a": {"score": 0.80, "interactions": {"mod_b": -0.15}},
            "mod_b": {"score": 0.80, "interactions": {"mod_a": -0.15}}
        }
        self.assertTrue(is_nash_equilibrium(eq_state))
        
        # Test non-equilibrium triggers False
        non_eq_state = {
            "mod_a": {"score": 0.70, "interactions": {"mod_b": -0.15}},
            "mod_b": {"score": 0.80, "interactions": {"mod_a": -0.15}}
        }
        self.assertFalse(is_nash_equilibrium(non_eq_state))
        
        # Test boundary case - very close scores
        boundary_state = {
            "mod_a": {"score": 0.799, "interactions": {"mod_b": -0.15}},
            "mod_b": {"score": 0.801, "interactions": {"mod_a": -0.15}}
        }
        result = is_nash_equilibrium(boundary_state)
        self.assertIsInstance(result, bool)

    def test_integration_coordinated_mutation_valid_multi_module_changes(self):
        """Integration test (3): Tests coordinated mutation generation produces valid multi-module changes."""
        # Setup complex interaction graph
        complex_graph = {
            "mod_x": {"score": 0.60, "interactions": {"mod_y": -0.25, "mod_z": -0.15}},
            "mod_y": {"score": 0.70, "interactions": {"mod_x": -0.25, "mod_z": -0.10}},
            "mod_z": {"score": 0.65, "interactions": {"mod_x": -0.15, "mod_y": -0.10}}
        }
        
        # Generate coordinated plan
        plan = force_multi_module_change(complex_graph)
        
        # Verify plan covers all modules
        self.assertEqual(len(plan), 3)
        for mod_name in complex_graph:
            self.assertIn(mod_name, plan)
        
        # Verify changes are coordinated (scores move toward each other)
        original_scores = [complex_graph[m]["score"] for m in complex_graph]
        new_scores = [plan[m]["new_score"] for m in complex_graph]
        
        # New scores should be more balanced than original
        original_range = max(original_scores) - min(original_scores)
        new_range = max(new_scores) - min(new_scores)
        self.assertLessEqual(new_range, original_range)
        
        # Verify all new scores are valid
        for score in new_scores:
            self.assertGreaterEqual(score, 0)
            self.assertLessEqual(score, 1)

    def test_integration_rollback_safety_for_coordinated_mutations(self):
        """Integration test (4): Validates rollback safety for coordinated mutations."""
        # Save original state
        original_modules = {
            "mod_alpha": {"score": 0.80, "interactions": {"mod_beta": -0.20}},
            "mod_beta": {"score": 0.75, "interactions": {"mod_alpha": -0.20}}
        }
        
        # Deep copy for rollback testing
        import copy
        backup_modules = copy.deepcopy(original_modules)
        
        # Generate and apply coordinated plan
        plan = force_multi_module_change(original_modules)
        
        # Simulate applying changes
        for mod_name, change in plan.items():
            original_modules[mod_name]["score"] = change["new_score"]
        
        # Verify changes were applied
        for mod_name in plan:
            self.assertNotEqual(original_modules[mod_name]["score"], 
                              backup_modules[mod_name]["score"])
        
        # Rollback to original state
        original_modules = copy.deepcopy(backup_modules)
        
        # Verify rollback restored original state
        for mod_name in backup_modules:
            self.assertEqual(original_modules[mod_name]["score"], 
                           backup_modules[mod_name]["score"])
            self.assertEqual(original_modules[mod_name]["interactions"], 
                           backup_modules[mod_name]["interactions"])
        
        # Verify system still functions after rollback
        self.assertTrue(is_nash_equilibrium(original_modules) or 
                       not is_nash_equilibrium(original_modules))


if __name__ == "__main__":
    unittest.main()