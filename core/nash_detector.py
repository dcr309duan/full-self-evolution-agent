from collections import deque, defaultdict
from datetime import datetime
import json
import os

class NashEquilibriumDetector:
    """
    Self-contained Nash equilibrium detector.
    Tracks module performance over the last N cycles, detects when no single-module
    mutation improves the system for 3+ consecutive attempts.
    Uses only standard library (collections, json, datetime).
    Exposes is_at_nash() method and get_stable_modules() list.
    """

    def __init__(self, module_names=None, state_file="nash_state.json", window_size=20, consecutive_failures=3):
        """
        Initialize the detector with module names.
        
        Args:
            module_names: List of module names to track (optional, loaded from file if not provided)
            state_file: Path to JSON file for state persistence
            window_size: Number of recent cycles to track per module
            consecutive_failures: Number of consecutive attempts without improvement to detect Nash
        """
        self.state_file = state_file
        self.module_names = module_names or []
        self.window_size = window_size
        self.consecutive_failures = consecutive_failures
        self.mutation_success = defaultdict(lambda: deque(maxlen=self.window_size))
        self.module_success_rates = {}
        self.nash_detected = False
        self.stable_modules = []
        self.consecutive_no_improvement = 0
        self.system_failing_goals = False
        self.load_state()

    def record_mutation_outcome(self, module_name, improved):
        """
        Record the outcome of a mutation for a specific module.
        
        Args:
            module_name: Name of the module that mutated
            improved: Whether the mutation improved the system
        """
        self.mutation_success[module_name].append(improved)
        self._update_module_success_rate(module_name)
        self.save_state()

    def _update_module_success_rate(self, module_name):
        """Update the success rate for a module based on its sliding window."""
        history = self.mutation_success.get(module_name, deque())
        if len(history) > 0:
            success_count = sum(1 for outcome in history if outcome)
            self.module_success_rates[module_name] = success_count / len(history)
        else:
            self.module_success_rates[module_name] = 0.0

    def set_system_goal_status(self, goals_failing):
        """
        Set whether the system is currently failing its goals.
        
        Args:
            goals_failing: True if the system is failing goals, False otherwise
        """
        self.system_failing_goals = goals_failing

    def is_at_nash(self):
        """
        Detect if the system is at Nash equilibrium.
        
        Checks if no single module has had a successful mutation in the last N consecutive attempts
        while the system is still failing goals.
        
        Returns:
            True if Nash equilibrium is detected, False otherwise
        """
        if not self.module_names:
            return False

        # Check if any module has had a successful mutation in the last N attempts
        any_improvement = False
        for module_name in self.module_names:
            history = self.mutation_success.get(module_name, deque())
            recent_history = list(history)[-self.consecutive_failures:] if len(history) >= self.consecutive_failures else list(history)
            if any(outcome for outcome in recent_history):
                any_improvement = True
                break

        # Update consecutive no improvement counter
        if any_improvement:
            self.consecutive_no_improvement = 0
        else:
            self.consecutive_no_improvement += 1

        # Detect Nash: no improvements in last N consecutive attempts AND system still failing goals
        self.nash_detected = (
            self.consecutive_no_improvement >= self.consecutive_failures and
            self.system_failing_goals
        )

        if self.nash_detected:
            self.stable_modules = list(self.module_names)
        else:
            self.stable_modules = []

        self.save_state()
        return self.nash_detected

    def get_stable_modules(self):
        """
        Get the list of modules that are at equilibrium.
        
        Returns:
            List of module names that are at equilibrium
        """
        return list(self.stable_modules)

    def add_module(self, module_name):
        """
        Add a module to the detector.
        
        Args:
            module_name: Name of the module to add
        """
        if module_name not in self.module_names:
            self.module_names.append(module_name)
            self.module_success_rates[module_name] = 0.0
        self.save_state()

    def remove_module(self, module_name):
        """
        Remove a module from the detector.
        
        Args:
            module_name: Name of the module to remove
        """
        if module_name in self.module_names:
            self.module_names.remove(module_name)
        if module_name in self.mutation_success:
            del self.mutation_success[module_name]
        if module_name in self.module_success_rates:
            del self.module_success_rates[module_name]
        if module_name in self.stable_modules:
            self.stable_modules.remove(module_name)
        self.save_state()

    def get_module_success_rates(self):
        """
        Get the success rates for all modules.
        
        Returns:
            Dictionary mapping module names to their success rates
        """
        return dict(self.module_success_rates)

    def get_nash_state(self):
        """
        Get the current Nash equilibrium state information.
        
        Returns:
            Dictionary containing Nash equilibrium state information
        """
        return {
            'nash': self.nash_detected,
            'stable_modules': self.get_stable_modules(),
            'module_success_rates': self.get_module_success_rates(),
            'consecutive_no_improvement': self.consecutive_no_improvement,
            'system_failing_goals': self.system_failing_goals,
            'module_names': list(self.module_names),
            'consecutive_failures': self.consecutive_failures
        }

    def save_state(self):
        """Save the current state to a JSON file."""
        state = {
            'module_names': list(self.module_names),
            'module_success_rates': dict(self.module_success_rates),
            'nash_detected': self.nash_detected,
            'stable_modules': list(self.stable_modules),
            'consecutive_no_improvement': self.consecutive_no_improvement,
            'system_failing_goals': self.system_failing_goals,
            'mutation_success': {k: list(v) for k, v in self.mutation_success.items()},
            'window_size': self.window_size,
            'consecutive_failures': self.consecutive_failures
        }
        try:
            with open(self.state_file, 'w') as f:
                json.dump(state, f, indent=2)
        except (IOError, OSError) as e:
            print(f"Warning: Could not save state to {self.state_file}: {e}")

    def load_state(self):
        """Load the state from a JSON file if it exists."""
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, 'r') as f:
                    state = json.load(f)
                self.module_names = state.get('module_names', [])
                self.module_success_rates = state.get('module_success_rates', {})
                self.nash_detected = state.get('nash_detected', False)
                self.stable_modules = state.get('stable_modules', [])
                self.consecutive_no_improvement = state.get('consecutive_no_improvement', 0)
                self.system_failing_goals = state.get('system_failing_goals', False)
                self.window_size = state.get('window_size', 20)
                self.consecutive_failures = state.get('consecutive_failures', 3)
                mutation_data = state.get('mutation_success', {})
                for module, history in mutation_data.items():
                    self.mutation_success[module] = deque(history, maxlen=self.window_size)
            except (json.JSONDecodeError, IOError, OSError) as e:
                print(f"Warning: Could not load state from {self.state_file}: {e}")

    def reset(self):
        """Reset all tracking data and clear the state file."""
        self.module_names = []
        self.mutation_success.clear()
        self.module_success_rates = {}
        self.nash_detected = False
        self.stable_modules = []
        self.consecutive_no_improvement = 0
        self.system_failing_goals = False
        if os.path.exists(self.state_file):
            try:
                os.remove(self.state_file)
            except OSError as e:
                print(f"Warning: Could not remove state file {self.state_file}: {e}")


def detect_nash():
    """
    Detect if the system is at Nash equilibrium.
    
    Returns:
        Tuple of (bool, dict) where bool is True if Nash equilibrium is detected,
        and dict contains the Nash equilibrium state information
    """
    detector = NashEquilibriumDetector()
    is_nash = detector.is_at_nash()
    state = detector.get_nash_state()
    return is_nash, state


def get_stable_modules():
    """
    Get the list of modules that are at equilibrium.
    
    Returns:
        List of module names that are at equilibrium
    """
    detector = NashEquilibriumDetector()
    return detector.get_stable_modules()


def run_test_mode():
    """Simple test mode that can run standalone."""
    print("Running NashEquilibriumDetector in test mode...")
    
    detector = NashEquilibriumDetector(state_file="test_nash_state.json")
    
    print("\nTest 1: Create test data")
    detector.add_module("module_a")
    detector.add_module("module_b")
    detector.add_module("module_c")
    print(f"  Created detector with {len(detector.module_names)} modules")
    print(f"  Module names: {detector.module_names}")
    print("  PASSED")
    
    print("\nTest 2: Record mutation outcomes and check Nash equilibrium")
    
    # Record unsuccessful mutations (no improvement)
    for _ in range(3):
        detector.record_mutation_outcome("module_a", False)
        detector.record_mutation_outcome("module_b", False)
        detector.record_mutation_outcome("module_c", False)
    
    # System is failing goals
    detector.set_system_goal_status(True)
    
    is_nash = detector.is_at_nash()
    print(f"  Nash after 1 cycle: {is_nash}")
    assert not is_nash, "Should not be Nash after 1 cycle"
    
    for _ in range(2):
        detector.record_mutation_outcome("module_a", False)
        detector.record_mutation_outcome("module_b", False)
        detector.record_mutation_outcome("module_c", False)
        is_nash = detector.is_at_nash()
    
    print(f"  Nash after 3 cycles: {is_nash}")
    assert is_nash, "Should be Nash after 3 cycles with no success and failing goals"
    print("  PASSED")
    
    print("\nTest 3: Check stable modules")
    stable_modules = detector.get_stable_modules()
    print(f"  Stable modules: {stable_modules}")
    assert len(stable_modules) > 0, "Should have at least one stable module"
    print("  PASSED")
    
    print("\nTest 4: Test successful mutation breaks Nash")
    detector.record_mutation_outcome("module_a", True)
    is_nash = detector.is_at_nash()
    print(f"  Nash after success: {is_nash}")
    assert not is_nash, "Should not be Nash after a successful mutation"
    print("  PASSED")
    
    print("\nTest 5: Test system not failing goals")
    detector.reset()
    detector.add_module("module_a")
    detector.add_module("module_b")
    detector.set_system_goal_status(False)
    
    for _ in range(3):
        detector.record_mutation_outcome("module_a", False)
        detector.record_mutation_outcome("module_b", False)
        is_nash = detector.is_at_nash()
    
    print(f"  Nash with goals not failing: {is_nash}")
    assert not is_nash, "Should not be Nash if goals are not failing"
    print("  PASSED")
    
    print("\nTest 6: Test add and remove modules")
    detector.add_module("module_d")
    print(f"  Module names after add: {detector.module_names}")
    assert "module_d" in detector.module_names, "module_d should be added"
    
    detector.remove_module("module_d")
    print(f"  Module names after remove: {detector.module_names}")
    assert "module_d" not in detector.module_names, "module_d should be removed"
    print("  PASSED")
    
    print("\nTest 7: Test state persistence")
    detector.reset()
    detector.add_module("module_x")
    detector.add_module("module_y")
    detector.record_mutation_outcome("module_x", True)
    detector.record_mutation_outcome("module_y", False)
    detector.save_state()
    
    # Create a new detector and load state
    detector2 = NashEquilibriumDetector(state_file="test_nash_state.json")
    print(f"  Loaded module names: {detector2.module_names}")
    print(f"  Loaded success rates: {detector2.get_module_success_rates()}")
    assert "module_x" in detector2.module_names, "module_x should be loaded"
    assert "module_y" in detector2.module_names, "module_y should be loaded"
    print("  PASSED")
    
    print("\nTest 8: Test detect_nash() function")
    is_nash, state = detect_nash()
    print(f"  detect_nash() returned: ({is_nash}, {state})")
    assert isinstance(is_nash, bool), "Should return bool"
    assert isinstance(state, dict), "Should return dict"
    assert 'nash' in state, "State should contain 'nash'"
    assert 'stable_modules' in state, "State should contain 'stable_modules'"
    assert 'module_success_rates' in state, "State should contain 'module_success_rates'"
    assert 'consecutive_no_improvement' in state, "State should contain 'consecutive_no_improvement'"
    assert 'system_failing_goals' in state, "State should contain 'system_failing_goals'"
    print("  PASSED")
    
    print("\nTest 9: Test get_stable_modules() function")
    stable = get_stable_modules()
    print(f"  get_stable_modules() returned: {stable}")
    assert isinstance(stable, list), "Should return a list"
    print("  PASSED")
    
    print("\nTest 10: Test reset clears everything")
    detector.reset()
    is_nash = detector.is_at_nash()
    stable_modules = detector.get_stable_modules()
    print(f"  Nash after reset: {is_nash}")
    print(f"  Stable modules after reset: {stable_modules}")
    assert not is_nash, "After reset should not be in Nash"
    assert len(stable_modules) == 0, "Stable modules should be empty after reset"
    assert len(detector.module_names) == 0, "Module names should be empty after reset"
    assert not os.path.exists("test_nash_state.json"), "State file should be removed"
    print("  PASSED")
    
    print("\nAll tests passed!")
    
    # Clean up test file
    if os.path.exists("test_nash_state.json"):
        os.remove("test_nash_state.json")


if __name__ == "__main__":
    run_test_mode()