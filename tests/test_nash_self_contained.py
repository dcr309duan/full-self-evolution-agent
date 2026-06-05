import sys
import os

# Add parent directory to path to allow imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.nash_detector_and_forcer import NashEquilibriumDetector, MultiModuleForcer


class TestNashSelfContained:
    """Minimal self-contained test for Nash equilibrium detection and multi-module forcing."""

    def __init__(self):
        """Initialize test fixtures."""
        self.detector = NashEquilibriumDetector()
        self.forcer = MultiModuleForcer()
        self.num_modules = 2
        self.module_names = [f"module_{i}" for i in range(self.num_modules)]
        self.errors = []

    def _simulate_stable_cycle(self, success_rate=1.0):
        """Simulate a cycle where all modules have the given success rate."""
        for module_name in self.module_names:
            self.detector.record_module_result(module_name, success_rate)

    def _assert_true(self, condition, message):
        """Custom assertion that records errors."""
        if not condition:
            self.errors.append(f"AssertionError: {message}")

    def _assert_equal(self, actual, expected, message):
        """Custom assertion for equality."""
        if actual != expected:
            self.errors.append(f"AssertionError: {message} - Expected {expected}, got {actual}")

    def _assert_less(self, actual, expected, message):
        """Custom assertion for less than."""
        if not (actual < expected):
            self.errors.append(f"AssertionError: {message} - Expected {actual} < {expected}")

    def _assert_in(self, item, container, message):
        """Custom assertion for membership."""
        if item not in container:
            self.errors.append(f"AssertionError: {message} - {item} not in {container}")

    def _assert_isinstance(self, obj, expected_type, message):
        """Custom assertion for type checking."""
        if not isinstance(obj, expected_type):
            self.errors.append(f"AssertionError: {message} - Expected type {expected_type}, got {type(obj)}")

    def _assert_not_equal(self, actual, expected, message):
        """Custom assertion for inequality."""
        if actual == expected:
            self.errors.append(f"AssertionError: {message} - Values should not be equal")

    def test_nash_detection_with_two_modules(self):
        """Test detection of Nash equilibrium with a simple 2-module system."""
        # Simulate 3 stable cycles with 100% success rate
        for _ in range(3):
            self._simulate_stable_cycle(1.0)

        # Check if Nash equilibrium is detected
        self._assert_true(
            self.detector.is_nash_equilibrium(),
            "Nash equilibrium should be detected after 3 stable cycles with 2 modules"
        )

        # Verify both modules are tracked
        for module_name in self.module_names:
            history = self.detector.get_module_history(module_name)
            self._assert_equal(len(history), 3, f"Module {module_name} should have 3 history entries")
            self._assert_true(all(r == 1.0 for r in history), f"All results for {module_name} should be 1.0")

    def test_coordinated_multi_module_changes(self):
        """Test generation of coordinated multi-module changes."""
        # Simulate 3 stable cycles to trigger Nash detection
        for _ in range(3):
            self._simulate_stable_cycle(1.0)

        # Verify Nash is detected
        self._assert_true(self.detector.is_nash_equilibrium())

        # Generate forced changes
        changes = self.forcer.generate_forced_changes(self.module_names)

        # Verify changes are generated for all modules
        self._assert_equal(
            len(changes),
            self.num_modules,
            f"Should generate changes for {self.num_modules} modules"
        )

        # Verify each module has a change
        for module_name in self.module_names:
            self._assert_in(
                module_name,
                changes,
                f"Module {module_name} should have a forced change"
            )

        # Verify changes are non-empty strings
        for module_name, change in changes.items():
            self._assert_isinstance(change, str, f"Change for {module_name} should be a string")
            self._assert_true(len(change) > 0, f"Change for {module_name} should not be empty")

        # Verify changes are coordinated (different from each other)
        self._assert_not_equal(
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
        self._assert_true(self.detector.is_nash_equilibrium())

        # Record current state as baseline
        baseline_results = {}
        for module_name in self.module_names:
            baseline_results[module_name] = self.detector.get_module_history(module_name)

        # Simulate a single-module change (module_0 changes, module_1 stays)
        self.detector.record_module_result(self.module_names[0], 0.8)
        self.detector.record_module_result(self.module_names[1], 1.0)

        # Check that Nash equilibrium is no longer detected (instability)
        self._assert_false(
            self.detector.is_nash_equilibrium(),
            "Nash equilibrium should break when a single module changes"
        )

        # Verify the system does not improve (success rate drops)
        history_0 = self.detector.get_module_history(self.module_names[0])
        self._assert_less(
            history_0[-1],
            baseline_results[self.module_names[0]][-1],
            "Single-module change should not improve the system at equilibrium"
        )

        # Verify module_1 remains stable
        history_1 = self.detector.get_module_history(self.module_names[1])
        self._assert_equal(
            history_1[-1],
            1.0,
            "Unchanged module should maintain its success rate"
        )

    def _assert_false(self, condition, message):
        """Custom assertion for false condition."""
        if condition:
            self.errors.append(f"AssertionError: {message}")

    def run_all_tests(self):
        """Run all test methods and report results."""
        test_methods = [
            self.test_nash_detection_with_two_modules,
            self.test_coordinated_multi_module_changes,
            self.test_single_module_change_does_not_improve_at_equilibrium
        ]
        
        for test_method in test_methods:
            self.errors = []
            test_method()
            if self.errors:
                print(f"FAILED: {test_method.__name__}")
                for error in self.errors:
                    print(f"  {error}")
            else:
                print(f"PASSED: {test_method.__name__}")


if __name__ == '__main__':
    test_suite = TestNashSelfContained()
    test_suite.run_all_tests()