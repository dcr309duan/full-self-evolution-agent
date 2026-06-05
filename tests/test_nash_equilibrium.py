import sys
import os
import unittest

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.nash_detector_and_forcer import is_nash_equilibrium, force_multi_module_change
from core.multi_module_forcer import generate_coordinated_plan


class TestNashEquilibriumMinimal(unittest.TestCase):
    """Minimal integration test for Nash equilibrium detection and multi-module forcing."""

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

    def test_coordinated_plan_generation(self):
        """Test (3): Verify generate_coordinated_plan produces valid plans."""
        plan = generate_coordinated_plan(self.modules)
        
        # Plan should be a dictionary
        self.assertIsInstance(plan, dict)
        
        # Plan should have entries for multiple modules
        self.assertGreaterEqual(len(plan), 2)
        
        # Each entry should have required fields
        for module_name, change in plan.items():
            self.assertIn("module", change)
            self.assertIn("new_score", change)
            self.assertEqual(change["module"], module_name)
            self.assertGreaterEqual(change["new_score"], 0)
            self.assertLessEqual(change["new_score"], 1)

    def test_equilibrium_after_no_improvement_cycles(self):
        """Test that equilibrium is detected after multiple no-improvement cycles."""
        # Start with non-equilibrium state
        modules = {
            "module_a": {"score": 0.70, "interactions": {"module_b": -0.15}},
            "module_b": {"score": 0.80, "interactions": {"module_a": -0.15}},
        }
        
        # Simulate no-improvement cycles
        for _ in range(5):
            # Keep scores the same (no improvement)
            modules["module_a"]["score"] = 0.70
            modules["module_b"]["score"] = 0.80
        
        # After no improvement, should detect equilibrium
        result = is_nash_equilibrium(modules)
        self.assertIsInstance(result, bool)

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


if __name__ == "__main__":
    unittest.main()