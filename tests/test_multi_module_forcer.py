import unittest
import sys
import os
import tempfile
import shutil
import json

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.multi_module_forcer import MultiModuleForcer


class TestMultiModuleForcer(unittest.TestCase):
    """Test suite for MultiModuleForcer using only standard library imports."""

    def setUp(self):
        """Create a temporary directory structure for testing."""
        self.test_dir = tempfile.mkdtemp()
        self.module_dir = os.path.join(self.test_dir, "modules")
        os.makedirs(self.module_dir)

        # Create mock module files
        self._create_mock_module("module_a", {"metric": 0.5, "threshold": 0.3})
        self._create_mock_module("module_b", {"metric": 0.7, "threshold": 0.4})
        self._create_mock_module("module_c", {"metric": 0.2, "threshold": 0.6})

        # Initialize the forcer
        self.forcer = MultiModuleForcer(module_dir=self.module_dir)

    def tearDown(self):
        """Clean up temporary directory."""
        shutil.rmtree(self.test_dir)

    def _create_mock_module(self, name, config):
        """Create a mock module file with given configuration."""
        module_path = os.path.join(self.module_dir, f"{name}.json")
        with open(module_path, 'w') as f:
            json.dump(config, f)

    def _read_module_config(self, name):
        """Read a module's configuration from its file."""
        module_path = os.path.join(self.module_dir, f"{name}.json")
        with open(module_path, 'r') as f:
            return json.load(f)

    def test_force_multi_module_change_returns_dict_with_at_least_two_entries_when_nash_detected(self):
        """Test that force_multi_module_change returns a dict with at least 2 module entries when nash is detected."""
        # Set up modules in Nash equilibrium state
        self._create_mock_module("module_a", {"metric": 0.5, "threshold": 0.5})
        self._create_mock_module("module_b", {"metric": 0.5, "threshold": 0.5})
        self._create_mock_module("module_c", {"metric": 0.5, "threshold": 0.5})

        # Reinitialize forcer with updated modules
        self.forcer = MultiModuleForcer(module_dir=self.module_dir)

        # Force multi-module change and get the result
        result = self.forcer.force_multi_module_change()

        # Verify result is a dict with at least 2 module entries
        self.assertIsInstance(result, dict, "Result should be a dict")
        self.assertGreaterEqual(len(result), 2, "Dict should have at least 2 module entries")

        # Verify each entry has expected structure
        for module_name, changes in result.items():
            self.assertIn("metric", changes, f"Changes for {module_name} should include 'metric'")
            self.assertIn("threshold", changes, f"Changes for {module_name} should include 'threshold'")

    def test_force_multi_module_change_returns_empty_dict_when_no_nash(self):
        """Test that force_multi_module_change returns an empty dict when no nash is detected."""
        # Modules are already set up with different metrics (no Nash equilibrium)
        result = self.forcer.force_multi_module_change()

        # Verify result is an empty dict
        self.assertIsInstance(result, dict, "Result should be a dict")
        self.assertEqual(len(result), 0, "Dict should be empty when no Nash equilibrium is detected")

        # Verify no modules were modified
        config_a = self._read_module_config("module_a")
        config_b = self._read_module_config("module_b")
        config_c = self._read_module_config("module_c")

        self.assertEqual(config_a["metric"], 0.5, "Module A should remain unchanged")
        self.assertEqual(config_b["metric"], 0.7, "Module B should remain unchanged")
        self.assertEqual(config_c["metric"], 0.2, "Module C should remain unchanged")

    def test_equilibrium_detection_triggers_coordinated_change(self):
        """Test that detecting equilibrium triggers a coordinated change across modules."""
        # Set up modules in equilibrium state
        self._create_mock_module("module_a", {"metric": 0.5, "threshold": 0.5})
        self._create_mock_module("module_b", {"metric": 0.5, "threshold": 0.5})
        self._create_mock_module("module_c", {"metric": 0.5, "threshold": 0.5})

        # Reinitialize forcer with updated modules
        self.forcer = MultiModuleForcer(module_dir=self.module_dir)

        # Force a check and get the result
        result = self.forcer.check_and_force()

        # Verify that coordinated change occurred
        self.assertTrue(result, "Coordinated change should be triggered when equilibrium is detected")

        # Verify modules were modified
        config_a = self._read_module_config("module_a")
        config_b = self._read_module_config("module_b")
        config_c = self._read_module_config("module_c")

        # All modules should have been changed
        self.assertNotEqual(config_a["metric"], 0.5, "Module A should have been modified")
        self.assertNotEqual(config_b["metric"], 0.5, "Module B should have been modified")
        self.assertNotEqual(config_c["metric"], 0.5, "Module C should have been modified")

    def test_atomic_application_works(self):
        """Test that atomic application of changes works correctly."""
        # Prepare changes to apply atomically
        changes = {
            "module_a": {"metric": 0.9, "threshold": 0.8},
            "module_b": {"metric": 0.1, "threshold": 0.2}
        }

        # Apply changes atomically
        success = self.forcer.apply_atomic(changes)

        # Verify atomic application succeeded
        self.assertTrue(success, "Atomic application should succeed")

        # Verify changes were applied
        config_a = self._read_module_config("module_a")
        config_b = self._read_module_config("module_b")
        config_c = self._read_module_config("module_c")

        self.assertEqual(config_a["metric"], 0.9, "Module A metric should be updated")
        self.assertEqual(config_a["threshold"], 0.8, "Module A threshold should be updated")
        self.assertEqual(config_b["metric"], 0.1, "Module B metric should be updated")
        self.assertEqual(config_b["threshold"], 0.2, "Module B threshold should be updated")
        # Module C should remain unchanged
        self.assertEqual(config_c["metric"], 0.2, "Module C should remain unchanged")
        self.assertEqual(config_c["threshold"], 0.6, "Module C should remain unchanged")

    def test_atomic_application_rollback_on_failure(self):
        """Test that atomic application rolls back changes on failure."""
        # Prepare changes where one will fail (non-existent module)
        changes = {
            "module_a": {"metric": 0.9},
            "nonexistent_module": {"metric": 0.5}  # This should cause failure
        }

        # Attempt atomic application
        success = self.forcer.apply_atomic(changes)

        # Verify atomic application failed
        self.assertFalse(success, "Atomic application should fail when a module doesn't exist")

        # Verify no changes were applied (rollback)
        config_a = self._read_module_config("module_a")
        self.assertEqual(config_a["metric"], 0.5, "Module A should have been rolled back")

    def test_system_escapes_equilibrium(self):
        """Test that the system can escape equilibrium when forced."""
        # Set up modules in a stable equilibrium
        self._create_mock_module("module_a", {"metric": 0.5, "threshold": 0.5})
        self._create_mock_module("module_b", {"metric": 0.5, "threshold": 0.5})
        self._create_mock_module("module_c", {"metric": 0.5, "threshold": 0.5})

        # Reinitialize forcer
        self.forcer = MultiModuleForcer(module_dir=self.module_dir)

        # Force the system multiple times to escape equilibrium
        for _ in range(3):
            self.forcer.check_and_force()

        # Verify system has escaped equilibrium
        configs = [
            self._read_module_config("module_a"),
            self._read_module_config("module_b"),
            self._read_module_config("module_c")
        ]

        # Check that at least one module has changed significantly
        metrics = [c["metric"] for c in configs]
        self.assertFalse(
            all(m == 0.5 for m in metrics),
            "System should have escaped equilibrium - at least one module should differ"
        )

        # Verify the system is no longer in equilibrium
        self.assertFalse(
            self.forcer.is_in_equilibrium(),
            "System should not be in equilibrium after forcing"
        )

    def test_no_equilibrium_no_change(self):
        """Test that no change is triggered when system is not in equilibrium."""
        # Modules are already set up with different metrics
        result = self.forcer.check_and_force()

        # No change should be triggered
        self.assertFalse(result, "No coordinated change should be triggered when not in equilibrium")

        # Verify no modules were modified
        config_a = self._read_module_config("module_a")
        config_b = self._read_module_config("module_b")
        config_c = self._read_module_config("module_c")

        self.assertEqual(config_a["metric"], 0.5, "Module A should remain unchanged")
        self.assertEqual(config_b["metric"], 0.7, "Module B should remain unchanged")
        self.assertEqual(config_c["metric"], 0.2, "Module C should remain unchanged")


if __name__ == '__main__':
    unittest.main()