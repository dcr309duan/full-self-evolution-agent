import unittest
from unittest.mock import MagicMock, patch
import sys
import os

# Add parent directory to path to import core modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.multi_module_forcer import force_coordinated_changes


class TestMultiModuleForceIntegration(unittest.TestCase):
    """Integration tests for multi-module forcing with equilibrium detection."""

    def setUp(self):
        """Set up 3 interdependent mock modules."""
        # Create mock modules with interdependencies
        self.module_a = MagicMock()
        self.module_a.name = "module_a"
        self.module_a.state = {"value": 10, "status": "active"}
        self.module_a.dependencies = ["module_b"]

        self.module_b = MagicMock()
        self.module_b.name = "module_b"
        self.module_b.state = {"value": 20, "status": "active"}
        self.module_b.dependencies = ["module_c"]

        self.module_c = MagicMock()
        self.module_c.name = "module_c"
        self.module_c.state = {"value": 30, "status": "active"}
        self.module_c.dependencies = ["module_a"]

        # Define equilibrium data that triggers detection
        self.equilibrium_data = {
            "equilibrium_detected": True,
            "modules": ["module_a", "module_b", "module_c"],
            "strategy": "cooperative",
            "equilibrium_point": {
                "module_a": {"value": 15},
                "module_b": {"value": 25},
                "module_c": {"value": 35}
            }
        }

    def test_force_coordinated_changes_with_equilibrium(self):
        """Test that coordinated changes are generated when equilibrium is detected."""
        changes = force_coordinated_changes(self.equilibrium_data)
        
        # Verify changes are generated
        self.assertIsNotNone(changes)
        self.assertIsInstance(changes, list)
        self.assertGreater(len(changes), 0)
        
        # Verify all 3 modules are included in the plan
        modules_in_plan = set(change["module"] for change in changes)
        self.assertIn("module_a", modules_in_plan)
        self.assertIn("module_b", modules_in_plan)
        self.assertIn("module_c", modules_in_plan)
        
        # Validate plan structure for each change
        for change in changes:
            self.assertIn("module", change)
            self.assertIn("change_type", change)
            self.assertIn("target_value", change)
            self.assertIn("priority", change)
            self.assertIn("dependencies", change)
            
            # Verify module names are valid
            self.assertIn(change["module"], ["module_a", "module_b", "module_c"])
            
            # Verify change types are valid
            self.assertIn(change["change_type"], ["adjust", "rebalance", "optimize"])
            
            # Verify target values are numeric
            self.assertIsInstance(change["target_value"], (int, float))
            
            # Verify priorities are numeric
            self.assertIsInstance(change["priority"], (int, float))
            
            # Verify dependencies are lists
            self.assertIsInstance(change["dependencies"], list)

    def test_force_coordinated_changes_no_equilibrium(self):
        """Test that no changes are generated when equilibrium is not detected."""
        no_equilibrium_data = {
            "equilibrium_detected": False,
            "modules": ["module_a", "module_b", "module_c"],
            "strategy": "cooperative"
        }
        changes = force_coordinated_changes(no_equilibrium_data)
        self.assertIsNone(changes)

    def test_force_coordinated_changes_empty_data(self):
        """Test that empty data returns no changes."""
        empty_data = {}
        changes = force_coordinated_changes(empty_data)
        self.assertIsNone(changes)

    def test_force_coordinated_changes_partial_modules(self):
        """Test with only some modules in equilibrium data."""
        partial_data = {
            "equilibrium_detected": True,
            "modules": ["module_a", "module_c"],
            "strategy": "cooperative",
            "equilibrium_point": {
                "module_a": {"value": 15},
                "module_c": {"value": 35}
            }
        }
        changes = force_coordinated_changes(partial_data)
        self.assertIsNotNone(changes)
        self.assertGreater(len(changes), 0)
        
        # Verify only specified modules are in plan
        modules_in_plan = set(change["module"] for change in changes)
        self.assertIn("module_a", modules_in_plan)
        self.assertNotIn("module_b", modules_in_plan)
        self.assertIn("module_c", modules_in_plan)

    def test_force_coordinated_changes_plan_structure(self):
        """Validate the complete plan structure."""
        changes = force_coordinated_changes(self.equilibrium_data)
        
        # Verify plan is a list of dictionaries
        self.assertIsInstance(changes, list)
        for change in changes:
            self.assertIsInstance(change, dict)
            
            # Verify all required keys exist
            required_keys = ["module", "change_type", "target_value", "priority", "dependencies"]
            for key in required_keys:
                self.assertIn(key, change, f"Missing key: {key}")
            
            # Verify no extra keys
            allowed_keys = set(required_keys)
            actual_keys = set(change.keys())
            self.assertEqual(actual_keys, allowed_keys, f"Unexpected keys: {actual_keys - allowed_keys}")
            
            # Verify data types
            self.assertIsInstance(change["module"], str)
            self.assertIsInstance(change["change_type"], str)
            self.assertIsInstance(change["target_value"], (int, float))
            self.assertIsInstance(change["priority"], (int, float))
            self.assertIsInstance(change["dependencies"], list)
            
            # Verify dependencies are strings
            for dep in change["dependencies"]:
                self.assertIsInstance(dep, str)


if __name__ == '__main__':
    unittest.main()