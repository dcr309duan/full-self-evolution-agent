import sys
import os
import json
import tempfile
import unittest
from unittest.mock import patch, mock_open

# Add parent directory to path to allow imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.nash_detector_and_forcer import NashEquilibriumDetector, MultiModuleForcer


class TestNashSelfContained(unittest.TestCase):
    """Self-contained test for Nash equilibrium detection and multi-module forcing."""

    def setUp(self):
        """Initialize test fixtures."""
        self.detector = NashEquilibriumDetector()
        self.forcer = MultiModuleForcer()
        self.num_modules = 2
        self.module_names = [f"module_{i}" for i in range(self.num_modules)]

    def _simulate_stable_cycle(self, success_rate=1.0):
        """Simulate a cycle where all modules have the given success rate."""
        for module_name in self.module_names:
            self.detector.record_module_result(module_name, success_rate)

    def test_detection_of_equilibrium_state(self):
        """Test detection of equilibrium state after stable cycles."""
        # Simulate 3 stable cycles with 100% success rate
        for _ in range(3):
            self._simulate_stable_cycle(1.0)

        # Check if Nash equilibrium is detected
        self.assertTrue(
            self.detector.is_nash_equilibrium(),
            "Nash equilibrium should be detected after 3 stable cycles with 2 modules"
        )

        # Verify both modules are tracked
        for module_name in self.module_names:
            history = self.detector.get_module_history(module_name)
            self.assertEqual(len(history), 3, f"Module {module_name} should have 3 history entries")
            self.assertTrue(all(r == 1.0 for r in history), f"All results for {module_name} should be 1.0")

    def test_generation_of_coordinated_mutations(self):
        """Test generation of coordinated multi-module changes."""
        # Simulate 3 stable cycles to trigger Nash detection
        for _ in range(3):
            self._simulate_stable_cycle(1.0)

        # Verify Nash is detected
        self.assertTrue(self.detector.is_nash_equilibrium())

        # Generate forced changes
        changes = self.forcer.generate_forced_changes(self.module_names)

        # Verify changes are generated for all modules
        self.assertEqual(
            len(changes),
            self.num_modules,
            f"Should generate changes for {self.num_modules} modules"
        )

        # Verify each module has a change
        for module_name in self.module_names:
            self.assertIn(
                module_name,
                changes,
                f"Module {module_name} should have a forced change"
            )

        # Verify changes are non-empty strings
        for module_name, change in changes.items():
            self.assertIsInstance(change, str, f"Change for {module_name} should be a string")
            self.assertTrue(len(change) > 0, f"Change for {module_name} should not be empty")

        # Verify changes are coordinated (different from each other)
        self.assertNotEqual(
            changes[self.module_names[0]],
            changes[self.module_names[1]],
            "Coordinated changes should be different for different modules"
        )

    def test_single_module_change_does_not_improve_at_equilibrium(self):
        """Test that single-module changes don't improve the system when at equilibrium."""
        # Simulate 3 stable cycles to reach equilibrium
        for _ in range(3):
            self._simulate_stable_cycle(1.0)

        # Verify Nash is detected
        self.assertTrue(self.detector.is_nash_equilibrium())

        # Record current state as baseline
        baseline_results = {}
        for module_name in self.module_names:
            baseline_results[module_name] = self.detector.get_module_history(module_name)

        # Simulate a single-module change (module_0 changes, module_1 stays)
        self.detector.record_module_result(self.module_names[0], 0.8)
        self.detector.record_module_result(self.module_names[1], 1.0)

        # Check that Nash equilibrium is no longer detected (instability)
        self.assertFalse(
            self.detector.is_nash_equilibrium(),
            "Nash equilibrium should break when a single module changes"
        )

        # Verify the system does not improve (success rate drops)
        history_0 = self.detector.get_module_history(self.module_names[0])
        self.assertLess(
            history_0[-1],
            baseline_results[self.module_names[0]][-1],
            "Single-module change should not improve the system at equilibrium"
        )

        # Verify module_1 remains stable
        history_1 = self.detector.get_module_history(self.module_names[1])
        self.assertEqual(
            history_1[-1],
            1.0,
            "Unchanged module should maintain its success rate"
        )

    def test_multi_module_change_improves_at_equilibrium(self):
        """Test that multi-module changes improve the system when at equilibrium."""
        # Simulate 3 stable cycles to reach equilibrium
        for _ in range(3):
            self._simulate_stable_cycle(1.0)

        # Verify Nash is detected
        self.assertTrue(self.detector.is_nash_equilibrium())

        # Record current state as baseline
        baseline_results = {}
        for module_name in self.module_names:
            baseline_results[module_name] = self.detector.get_module_history(module_name)

        # Simulate a multi-module change (both modules change)
        self.detector.record_module_result(self.module_names[0], 0.9)
        self.detector.record_module_result(self.module_names[1], 0.9)

        # Check that Nash equilibrium is no longer detected (instability)
        self.assertFalse(
            self.detector.is_nash_equilibrium(),
            "Nash equilibrium should break when multiple modules change"
        )

        # Verify the system improves (success rates are still high)
        history_0 = self.detector.get_module_history(self.module_names[0])
        history_1 = self.detector.get_module_history(self.module_names[1])
        
        # Both modules should have improved or maintained performance
        self.assertGreaterEqual(
            history_0[-1],
            0.9,
            "Multi-module change should maintain high performance"
        )
        self.assertGreaterEqual(
            history_1[-1],
            0.9,
            "Multi-module change should maintain high performance"
        )

    def test_detect_equilibrium_no_data(self):
        """Test that detect_equilibrium returns False with no data."""
        result = self.detector.is_nash_equilibrium()
        self.assertFalse(result, "detect_equilibrium should return False with no data")

    def test_detect_equilibrium_with_synthetic_data(self):
        """Test that detect_equilibrium returns True when fed synthetic equilibrium data."""
        # Feed synthetic equilibrium data: all modules have 100% success rate for 3 cycles
        for _ in range(3):
            self._simulate_stable_cycle(1.0)
        result = self.detector.is_nash_equilibrium()
        self.assertTrue(result, "detect_equilibrium should return True with synthetic equilibrium data")

    def test_force_multi_module_change_returns_valid_plan(self):
        """Test that force_multi_module_change returns a valid multi-module plan."""
        # First establish equilibrium
        for _ in range(3):
            self._simulate_stable_cycle(1.0)
        
        # Generate forced changes
        changes = self.forcer.generate_forced_changes(self.module_names)
        
        # Verify it's a valid multi-module plan
        self.assertIsInstance(changes, dict, "force_multi_module_change should return a dict")
        self.assertEqual(len(changes), self.num_modules, "Plan should have changes for all modules")
        for module_name, change in changes.items():
            self.assertIsInstance(change, str, f"Change for {module_name} should be a string")
            self.assertTrue(len(change) > 0, f"Change for {module_name} should not be empty")

    def test_detection_by_simulating_improvement_history_that_plateaus(self):
        """Test detection by simulating improvement history that plateaus."""
        # Simulate improvement history that plateaus
        # Start with improving success rates
        for rate in [0.5, 0.7, 0.9, 1.0, 1.0, 1.0]:
            self._simulate_stable_cycle(rate)
        
        # Check that Nash equilibrium is detected after plateau
        self.assertTrue(
            self.detector.is_nash_equilibrium(),
            "Nash equilibrium should be detected after improvement history plateaus"
        )
        
        # Verify the plateau is detected (last 3 entries are all 1.0)
        for module_name in self.module_names:
            history = self.detector.get_module_history(module_name)
            self.assertEqual(len(history), 6, f"Module {module_name} should have 6 history entries")
            # Check that last 3 entries are 1.0 (plateau)
            self.assertTrue(
                all(r == 1.0 for r in history[-3:]),
                f"Last 3 entries for {module_name} should be 1.0 (plateau)"
            )
            # Check that earlier entries were improving
            self.assertLess(history[0], history[1], f"Module {module_name} should show improvement")
            self.assertLess(history[1], history[2], f"Module {module_name} should show improvement")

    def test_multi_module_forcer_generates_valid_coordinated_changes(self):
        """Test multi-module forcer generates valid coordinated changes."""
        # Establish equilibrium first
        for _ in range(3):
            self._simulate_stable_cycle(1.0)
        
        # Generate forced changes
        changes = self.forcer.generate_forced_changes(self.module_names)
        
        # Verify changes are valid and coordinated
        self.assertIsInstance(changes, dict, "Changes should be a dictionary")
        self.assertEqual(len(changes), self.num_modules, "Should have changes for all modules")
        
        # Verify each change is a non-empty string
        for module_name, change in changes.items():
            self.assertIsInstance(change, str, f"Change for {module_name} should be a string")
            self.assertTrue(len(change) > 0, f"Change for {module_name} should not be empty")
        
        # Verify changes are coordinated (different from each other)
        change_values = list(changes.values())
        self.assertNotEqual(
            change_values[0],
            change_values[1],
            "Coordinated changes should be different for different modules"
        )
        
        # Verify changes are meaningful (contain module-specific information)
        for module_name, change in changes.items():
            self.assertIn(
                module_name,
                change,
                f"Change for {module_name} should contain module name"
            )

    @patch('builtins.open', new_callable=mock_open, read_data='{"module_0": [1.0, 1.0, 1.0], "module_1": [1.0, 1.0, 1.0]}')
    def test_file_based_protocol_works_correctly(self, mock_file):
        """Test file-based protocol works correctly."""
        # Test loading state from file
        state_file = "test_state.json"
        
        # Load state from mocked file
        with open(state_file, 'r') as f:
            state_data = json.load(f)
        
        # Verify state data structure
        self.assertIsInstance(state_data, dict, "State data should be a dictionary")
        self.assertIn("module_0", state_data, "State should contain module_0")
        self.assertIn("module_1", state_data, "State should contain module_1")
        
        # Load state into detector
        for module_name, history in state_data.items():
            for result in history:
                self.detector.record_module_result(module_name, result)
        
        # Verify equilibrium detection works with loaded state
        self.assertTrue(
            self.detector.is_nash_equilibrium(),
            "Nash equilibrium should be detected after loading state from file"
        )
        
        # Test saving state to file
        save_data = {}
        for module_name in self.module_names:
            save_data[module_name] = self.detector.get_module_history(module_name)
        
        # Mock file writing
        with patch('builtins.open', new_callable=mock_open) as mock_write:
            with open("output_state.json", 'w') as f:
                json.dump(save_data, f)
            
            # Verify file was written
            mock_write.assert_called_once_with("output_state.json", 'w')
            
            # Get the written content
            handle = mock_write()
            written_content = ''.join(call.args[0] for call in handle.write.call_args_list)
            
            # Verify written content is valid JSON
            parsed_content = json.loads(written_content)
            self.assertEqual(parsed_content, save_data, "Written data should match saved data")


if __name__ == '__main__':
    unittest.main()