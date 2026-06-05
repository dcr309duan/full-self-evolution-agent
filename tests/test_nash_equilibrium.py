import sys
import os
import unittest
from unittest.mock import Mock, patch

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.nash_detector import is_nash_equilibrium
from core.multi_module_forcer import force_multi_module_change


class TestNashEquilibriumMinimal(unittest.TestCase):
    """Minimal integration test for Nash equilibrium detection and multi-module forcing."""

    def test_detect_equilibrium_with_mock_data(self):
        """Test (1): detect equilibrium with mock interaction data."""
        mock_data = {
            "module_a": {"score": 0.85, "interactions": {"module_b": -0.20}},
            "module_b": {"score": 0.85, "interactions": {"module_a": -0.20}},
        }
        result = is_nash_equilibrium(mock_data)
        self.assertIsInstance(result, bool)
        self.assertTrue(result)

    def test_generate_multi_module_plan(self):
        """Test (2): generate multi-module plan."""
        mock_data = {
            "module_x": {"score": 0.70, "interactions": {"module_y": -0.15, "module_z": 0.10}},
            "module_y": {"score": 0.70, "interactions": {"module_x": -0.15, "module_z": -0.05}},
            "module_z": {"score": 0.70, "interactions": {"module_x": 0.10, "module_y": -0.05}},
        }
        plan = force_multi_module_change(mock_data)
        self.assertIsInstance(plan, dict)
        self.assertGreaterEqual(len(plan), 2)

    def test_plan_affects_multiple_modules(self):
        """Test (3): verify plan affects multiple modules."""
        mock_data = {
            "module_a": {"score": 0.70, "interactions": {"module_b": -0.15, "module_c": 0.10}},
            "module_b": {"score": 0.70, "interactions": {"module_a": -0.15, "module_c": -0.05}},
            "module_c": {"score": 0.70, "interactions": {"module_a": 0.10, "module_b": -0.05}},
        }
        plan = force_multi_module_change(mock_data)
        # Verify plan contains changes for at least 2 different modules
        module_keys = set(plan.keys())
        self.assertGreaterEqual(len(module_keys), 2)
        # Verify each change is a dict with expected structure
        for module, change in plan.items():
            self.assertIsInstance(change, dict)
            self.assertIn("module", change)
            self.assertEqual(change["module"], module)


if __name__ == "__main__":
    unittest.main()