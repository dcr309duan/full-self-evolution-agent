import unittest
from unittest.mock import patch, MagicMock
import sys
import os

# Add parent directory to path to allow imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core import nash_detector
from core import multi_module_forcer


class TestNashSelfContained(unittest.TestCase):
    """Minimal self-contained test for Nash equilibrium detection and multi-module forcing."""

    def setUp(self):
        """Set up test fixtures."""
        self.detector = nash_detector.NashEquilibriumDetector()
        self.forcer = multi_module_forcer.MultiModuleForcer()
        self.num_modules = 5
        self.module_names = [f"module_{i}" for i in range(self.num_modules)]

    def _simulate_stable_cycle(self, success_rate=1.0):
        """Simulate a cycle where all modules have the given success rate."""
        for module_name in self.module_names:
            self.detector.record_module_result(module_name, success_rate)

    def test_nash_detection_after_three_stable_cycles(self):
        """Test that Nash equilibrium is detected after 3 stable cycles."""
        # Simulate 3 stable cycles with 100% success rate
        for _ in range(3):
            self._simulate_stable_cycle(1.0)

        # Check if Nash equilibrium is detected
        self.assertTrue(
            self.detector.is_nash_equilibrium(),
            "Nash equilibrium should be detected after 3 stable cycles"
        )

    def test_forced_multi_module_change_generation(self):
        """Test that forced multi-module changes are generated after Nash detection."""
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

    def test_no_nash_before_three_cycles(self):
        """Test that Nash is not detected before 3 stable cycles."""
        # Simulate only 2 stable cycles
        for _ in range(2):
            self._simulate_stable_cycle(1.0)

        # Nash should not be detected yet
        self.assertFalse(
            self.detector.is_nash_equilibrium(),
            "Nash equilibrium should not be detected before 3 stable cycles"
        )

    def test_nash_resets_on_instability(self):
        """Test that Nash detection resets when instability occurs."""
        # Simulate 2 stable cycles
        for _ in range(2):
            self._simulate_stable_cycle(1.0)

        # Introduce instability
        self._simulate_stable_cycle(0.5)

        # Nash should not be detected
        self.assertFalse(
            self.detector.is_nash_equilibrium(),
            "Nash equilibrium should reset on instability"
        )

    def test_forced_changes_with_mocked_detector(self):
        """Test forced changes using mocked detector output."""
        # Mock the detector to always indicate Nash equilibrium
        with patch.object(self.detector, 'is_nash_equilibrium', return_value=True):
            # Generate forced changes
            changes = self.forcer.generate_forced_changes(self.module_names)

            # Verify changes are generated
            self.assertEqual(len(changes), self.num_modules)

            # Verify each change is a non-empty string
            for module_name, change in changes.items():
                self.assertIsInstance(change, str)
                self.assertTrue(len(change) > 0, f"Change for {module_name} should not be empty")


if __name__ == '__main__':
    unittest.main()