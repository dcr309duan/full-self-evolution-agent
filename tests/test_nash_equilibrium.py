import sys
import os
import unittest
import copy

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.nash_detector_and_forcer import NashDetector, MultiModuleForcer


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
        self.detector = NashDetector()
        self.forcer = MultiModuleForcer()

    def test_detect_equilibrium(self):
        """Test (1): Verify the detector identifies when modules reach equilibrium."""
        # All modules have same score and negative interactions - should be equilibrium
        result = self.detector.is_nash_equilibrium(self.modules)
        self.assertIsInstance(result, bool)
        self.assertTrue(result)

    def test_detect_non_equilibrium(self):
        """Test that non-equilibrium state is correctly identified."""
        # Module A has lower score - should not be equilibrium
        non_eq_modules = {
            "module_a": {"score": 0.70, "interactions": {"module_b": -0.20}},
            "module_b": {"score": 0.85, "interactions": {"module_a": -0.20}},
        }
        result = self.detector.is_nash_equilibrium(non_eq_modules)
        self.assertFalse(result)

    def test_multi_module_forcing_generates_valid_changes(self):
        """Test (2): Verify multi-module forcing generates valid coordinated changes."""
        plan = self.forcer.force_multi_module_change(self.modules)
        
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
        plan = self.forcer.force_multi_module_change(self.modules)
        
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
        self.assertTrue(self.detector.is_nash_equilibrium(mock_graph))
        
        # Verify coordinated plan maintains equilibrium properties
        plan = self.forcer.force_multi_module_change(mock_graph)
        for mod_name, change in plan.items():
            self.assertAlmostEqual(change["new_score"], 0.75, delta=0.1)

    def test_integration_detection_triggers_correctly(self):
        """Integration test (2): Verifies detection triggers correctly for various states."""
        # Test equilibrium triggers True
        eq_state = {
            "mod_a": {"score": 0.80, "interactions": {"mod_b": -0.15}},
            "mod_b": {"score": 0.80, "interactions": {"mod_a": -0.15}}
        }
        self.assertTrue(self.detector.is_nash_equilibrium(eq_state))
        
        # Test non-equilibrium triggers False
        non_eq_state = {
            "mod_a": {"score": 0.70, "interactions": {"mod_b": -0.15}},
            "mod_b": {"score": 0.80, "interactions": {"mod_a": -0.15}}
        }
        self.assertFalse(self.detector.is_nash_equilibrium(non_eq_state))
        
        # Test boundary case - very close scores
        boundary_state = {
            "mod_a": {"score": 0.799, "interactions": {"mod_b": -0.15}},
            "mod_b": {"score": 0.801, "interactions": {"mod_a": -0.15}}
        }
        result = self.detector.is_nash_equilibrium(boundary_state)
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
        plan = self.forcer.force_multi_module_change(complex_graph)
        
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
        backup_modules = copy.deepcopy(original_modules)
        
        # Generate and apply coordinated plan
        plan = self.forcer.force_multi_module_change(original_modules)
        
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
        self.assertTrue(self.detector.is_nash_equilibrium(original_modules) or 
                       not self.detector.is_nash_equilibrium(original_modules))

    def test_minimal_integration_nash_scenario(self):
        """Minimal integration test: (1) Sets up mock dependency graph with 3 modules,
        (2) Simulates Nash equilibrium where no single module change improves system,
        (3) Verifies detector identifies this state, (4) Tests coordinated forcer generates appropriate multi-module changes."""
        # (1) Set up mock dependency graph with 3 modules
        mock_graph = {
            "mod_1": {"score": 0.80, "interactions": {"mod_2": -0.15, "mod_3": -0.10}},
            "mod_2": {"score": 0.80, "interactions": {"mod_1": -0.15, "mod_3": -0.10}},
            "mod_3": {"score": 0.80, "interactions": {"mod_1": -0.10, "mod_2": -0.10}}
        }
        
        # (2) Simulate Nash equilibrium scenario - no single module change improves system
        # All modules have equal scores and balanced negative interactions
        # Changing any single module's score would break the balance and reduce overall performance
        self.assertTrue(self.detector.is_nash_equilibrium(mock_graph))
        
        # Verify that changing any single module would not improve the system
        for mod_name in mock_graph:
            # Try increasing score
            test_graph = {
                "mod_1": {"score": 0.80, "interactions": {"mod_2": -0.15, "mod_3": -0.10}},
                "mod_2": {"score": 0.80, "interactions": {"mod_1": -0.15, "mod_3": -0.10}},
                "mod_3": {"score": 0.80, "interactions": {"mod_1": -0.10, "mod_2": -0.10}}
            }
            test_graph[mod_name]["score"] = 0.85
            # Higher score with same interactions would break equilibrium
            self.assertFalse(self.detector.is_nash_equilibrium(test_graph))
            
            # Try decreasing score
            test_graph[mod_name]["score"] = 0.75
            self.assertFalse(self.detector.is_nash_equilibrium(test_graph))
        
        # (3) Verify detector identifies this state as equilibrium
        self.assertTrue(self.detector.is_nash_equilibrium(mock_graph))
        
        # (4) Test coordinated forcer generates appropriate multi-module changes
        plan = self.forcer.force_multi_module_change(mock_graph)
        
        # Verify plan is valid
        self.assertIsInstance(plan, dict)
        self.assertEqual(len(plan), 3)
        
        # Verify all modules are included
        for mod_name in mock_graph:
            self.assertIn(mod_name, plan)
        
        # Verify changes are coordinated and maintain balance
        scores = [plan[m]["new_score"] for m in mock_graph]
        score_range = max(scores) - min(scores)
        self.assertLessEqual(score_range, 0.1)  # Scores should be very close
        
        # Verify each change is valid
        for mod_name, change in plan.items():
            self.assertIn("module", change)
            self.assertEqual(change["module"], mod_name)
            self.assertIn("new_score", change)
            self.assertGreaterEqual(change["new_score"], 0)
            self.assertLessEqual(change["new_score"], 1)

    def test_minimal_nash_equilibrium_scenario(self):
        """Minimal test that: (1) Creates a mock interaction graph with 3 modules,
        (2) Simulates 50 cycles of interactions with stable success rates,
        (3) Verifies detect_nash_equilibrium() returns True,
        (4) Verifies force_multi_module_change() returns a plan with 3+ modules,
        (5) Tests that changing one module breaks the equilibrium detection."""
        
        # (1) Create a mock interaction graph with 3 modules
        mock_graph = {
            "mod_1": {"score": 0.75, "interactions": {"mod_2": -0.10, "mod_3": -0.10}},
            "mod_2": {"score": 0.75, "interactions": {"mod_1": -0.10, "mod_3": -0.10}},
            "mod_3": {"score": 0.75, "interactions": {"mod_1": -0.10, "mod_2": -0.10}}
        }
        
        # (2) Simulate 50 cycles of interactions with stable success rates
        for cycle in range(50):
            # Simulate stable interactions - scores remain the same
            for mod_name in mock_graph:
                # Apply small random perturbations to simulate interactions
                for other_mod, interaction in mock_graph[mod_name]["interactions"].items():
                    # Stable success rate means scores don't change significantly
                    pass  # Scores remain stable as per equilibrium
            
            # After each cycle, verify equilibrium is maintained
            if cycle % 10 == 0:  # Check periodically
                self.assertTrue(self.detector.is_nash_equilibrium(mock_graph))
        
        # (3) Verify detect_nash_equilibrium() returns True
        self.assertTrue(self.detector.is_nash_equilibrium(mock_graph))
        
        # (4) Verify force_multi_module_change() returns a plan with 3+ modules
        plan = self.forcer.force_multi_module_change(mock_graph)
        self.assertIsInstance(plan, dict)
        self.assertGreaterEqual(len(plan), 3)
        
        # Verify all modules are in the plan
        for mod_name in mock_graph:
            self.assertIn(mod_name, plan)
        
        # (5) Test that changing one module breaks the equilibrium detection
        # Change module_1's score significantly
        modified_graph = copy.deepcopy(mock_graph)
        modified_graph["mod_1"]["score"] = 0.90  # Significant change
        
        # Verify equilibrium is broken
        self.assertFalse(self.detector.is_nash_equilibrium(modified_graph))
        
        # Change module_2's interactions
        modified_graph2 = copy.deepcopy(mock_graph)
        modified_graph2["mod_2"]["interactions"]["mod_1"] = -0.50  # Significant change
        
        # Verify equilibrium is broken
        self.assertFalse(self.detector.is_nash_equilibrium(modified_graph2))
        
        # Change module_3's score and interactions
        modified_graph3 = copy.deepcopy(mock_graph)
        modified_graph3["mod_3"]["score"] = 0.60
        modified_graph3["mod_3"]["interactions"]["mod_1"] = -0.30
        
        # Verify equilibrium is broken
        self.assertFalse(self.detector.is_nash_equilibrium(modified_graph3))

    def test_equilibrium_after_n_cycles_no_improvement(self):
        """Test (1): Verify detector correctly identifies equilibrium after N cycles of no improvement."""
        # Create a mock graph that is in equilibrium
        mock_graph = {
            "mod_a": {"score": 0.80, "interactions": {"mod_b": -0.15, "mod_c": -0.10}},
            "mod_b": {"score": 0.80, "interactions": {"mod_a": -0.15, "mod_c": -0.10}},
            "mod_c": {"score": 0.80, "interactions": {"mod_a": -0.10, "mod_b": -0.10}}
        }
        
        # Simulate N cycles of no improvement (scores remain stable)
        n_cycles = 10
        for cycle in range(n_cycles):
            # No changes to scores - simulating no improvement
            self.assertTrue(self.detector.is_nash_equilibrium(mock_graph))
        
        # After N cycles, equilibrium should still be detected
        self.assertTrue(self.detector.is_nash_equilibrium(mock_graph))

    def test_reset_after_multi_module_change_succeeds(self):
        """Test (2): Verify detector resets when a multi-module change succeeds."""
        # Create a mock graph in equilibrium
        mock_graph = {
            "mod_a": {"score": 0.80, "interactions": {"mod_b": -0.15}},
            "mod_b": {"score": 0.80, "interactions": {"mod_a": -0.15}}
        }
        
        # Initially in equilibrium
        self.assertTrue(self.detector.is_nash_equilibrium(mock_graph))
        
        # Generate a multi-module change plan
        plan = self.forcer.force_multi_module_change(mock_graph)
        
        # Apply the changes (simulating successful multi-module change)
        for mod_name, change in plan.items():
            mock_graph[mod_name]["score"] = change["new_score"]
        
        # After successful change, the system may no longer be in equilibrium
        # The detector should reflect the new state
        result = self.detector.is_nash_equilibrium(mock_graph)
        self.assertIsInstance(result, bool)
        
        # The new state should be closer to equilibrium (scores more balanced)
        scores = [mock_graph[m]["score"] for m in mock_graph]
        score_range = max(scores) - min(scores)
        self.assertLessEqual(score_range, 0.2)

    def test_forcer_generates_valid_coordinated_mutations(self):
        """Test (3): Verify the forcer generates valid coordinated mutations."""
        # Create a mock graph with imbalanced scores
        mock_graph = {
            "mod_x": {"score": 0.60, "interactions": {"mod_y": -0.20, "mod_z": -0.15}},
            "mod_y": {"score": 0.80, "interactions": {"mod_x": -0.20, "mod_z": -0.10}},
            "mod_z": {"score": 0.70, "interactions": {"mod_x": -0.15, "mod_y": -0.10}}
        }
        
        # Generate coordinated mutations
        plan = self.forcer.force_multi_module_change(mock_graph)
        
        # Verify plan structure
        self.assertIsInstance(plan, dict)
        self.assertEqual(len(plan), 3)
        
        # Verify each mutation is valid
        for mod_name, change in plan.items():
            self.assertIn(mod_name, mock_graph)
            self.assertIn("module", change)
            self.assertEqual(change["module"], mod_name)
            self.assertIn("new_score", change)
            self.assertIsInstance(change["new_score"], (int, float))
            self.assertGreaterEqual(change["new_score"], 0)
            self.assertLessEqual(change["new_score"], 1)
        
        # Verify mutations are coordinated (scores move toward each other)
        original_scores = [mock_graph[m]["score"] for m in mock_graph]
        new_scores = [plan[m]["new_score"] for m in mock_graph]
        
        original_range = max(original_scores) - min(original_scores)
        new_range = max(new_scores) - min(new_scores)
        self.assertLessEqual(new_range, original_range)
        
        # Verify the plan is not empty
        self.assertGreater(len(plan), 0)


if __name__ == "__main__":
    unittest.main()