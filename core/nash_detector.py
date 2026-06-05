import json
import os
import sys
from collections import defaultdict, deque

class NashEquilibriumDetector:
    """
    Minimal, self-contained Nash equilibrium detector.
    Tracks module interaction frequencies and success rates over a sliding window of last 20 cycles.
    Detects Nash equilibrium by checking if no single module change improves the system.
    Uses a heuristic: if all modules' success rates have been stable within 5% for 5+ cycles, declare equilibrium.
    """

    def __init__(self, module_names):
        """
        Initialize the detector with module names.
        
        Args:
            module_names: List of module names to track
        """
        if not module_names:
            raise ValueError("module_names list cannot be empty")
        
        self.module_names = list(module_names)
        
        # Module interaction frequencies: module_name -> {other_module: frequency}
        self.interaction_frequencies = {}
        
        # Module success rates: module_name -> deque of success rates over last 20 cycles
        self.success_rates = {}
        
        # Current success rate for each module (average over window)
        self.current_success_rates = {}
        
        # Sliding window size
        self.window_size = 20
        
        # Stability threshold (5%)
        self.stability_threshold = 0.05
        
        # Number of consecutive stable cycles required for equilibrium
        self.stability_cycles_required = 5
        
        # Counter for consecutive cycles where all modules are stable
        self.stable_cycles_count = 0
        
        # Flag indicating if equilibrium has been detected
        self._equilibrium_detected = False
        
        # List of modules that are at equilibrium
        self._modules_at_equilibrium = []
        
        # Initialize data structures
        for module_name in self.module_names:
            self.success_rates[module_name] = deque(maxlen=self.window_size)
            self.current_success_rates[module_name] = 0.0
            self.interaction_frequencies[module_name] = {}
            for other_module in self.module_names:
                if other_module != module_name:
                    self.interaction_frequencies[module_name][other_module] = 0.0

    def update_interaction_frequency(self, module_a, module_b, frequency):
        """
        Update the interaction frequency between two modules.
        
        Args:
            module_a: First module name
            module_b: Second module name
            frequency: Interaction frequency value
        """
        if module_a in self.interaction_frequencies and module_b in self.interaction_frequencies[module_a]:
            self.interaction_frequencies[module_a][module_b] = frequency
        if module_b in self.interaction_frequencies and module_a in self.interaction_frequencies[module_b]:
            self.interaction_frequencies[module_b][module_a] = frequency

    def get_interaction_frequency(self, module_a, module_b):
        """
        Get the interaction frequency between two modules.
        
        Args:
            module_a: First module name
            module_b: Second module name
            
        Returns:
            Interaction frequency value
        """
        if module_a in self.interaction_frequencies and module_b in self.interaction_frequencies[module_a]:
            return self.interaction_frequencies[module_a][module_b]
        return 0.0

    def record_success_rate(self, module_name, success_rate):
        """
        Record a success rate for a module.
        
        Args:
            module_name: Name of the module
            success_rate: Success rate value (0.0 to 1.0)
        """
        if module_name in self.success_rates:
            self.success_rates[module_name].append(success_rate)
            # Update current success rate as average over window
            if self.success_rates[module_name]:
                self.current_success_rates[module_name] = sum(self.success_rates[module_name]) / len(self.success_rates[module_name])

    def is_module_stable(self, module_name):
        """
        Check if a module's success rate has been stable within the threshold.
        
        Args:
            module_name: Name of the module to check
            
        Returns:
            True if module is stable, False otherwise
        """
        if module_name not in self.success_rates:
            return False
        
        rates = list(self.success_rates[module_name])
        if len(rates) < 2:
            return False
        
        # Check if all rates in the window are within 5% of each other
        min_rate = min(rates)
        max_rate = max(rates)
        
        # Avoid division by zero
        if max_rate == 0:
            return True
        
        return (max_rate - min_rate) / max_rate <= self.stability_threshold

    def increment_cycle(self):
        """Advance to the next evaluation cycle and update equilibrium detection."""
        # Check stability of all modules
        all_stable = True
        self._modules_at_equilibrium = []
        
        for module_name in self.module_names:
            if self.is_module_stable(module_name):
                self._modules_at_equilibrium.append(module_name)
            else:
                all_stable = False
        
        if all_stable and len(self._modules_at_equilibrium) == len(self.module_names):
            self.stable_cycles_count += 1
        else:
            self.stable_cycles_count = 0
        
        # Check if equilibrium condition is met
        if self.stable_cycles_count >= self.stability_cycles_required:
            self._equilibrium_detected = True
        else:
            self._equilibrium_detected = False

    def is_nash_equilibrium(self):
        """
        Check if the system is at Nash equilibrium.
        
        Returns:
            Tuple of (is_equilibrium, list_of_modules_at_equilibrium)
        """
        return (self._equilibrium_detected, self._modules_at_equilibrium.copy())

    def get_equilibrium_state(self):
        """
        Get the current equilibrium state information.
        
        Returns:
            Dictionary containing equilibrium state information
        """
        is_eq, modules_eq = self.is_nash_equilibrium()
        return {
            'equilibrium': is_eq,
            'modules_at_equilibrium': modules_eq,
            'stable_cycles_count': self.stable_cycles_count,
            'stability_cycles_required': self.stability_cycles_required,
            'current_success_rates': dict(self.current_success_rates),
            'interaction_frequencies': {k: dict(v) for k, v in self.interaction_frequencies.items()},
            'window_size': self.window_size,
            'stability_threshold': self.stability_threshold
        }

    def save_state(self, filepath):
        """
        Save the current state to a JSON file.
        
        Args:
            filepath: Path to save the JSON file
        """
        state = {
            'module_names': self.module_names,
            'interaction_frequencies': {k: dict(v) for k, v in self.interaction_frequencies.items()},
            'success_rates': {k: list(v) for k, v in self.success_rates.items()},
            'current_success_rates': dict(self.current_success_rates),
            'window_size': self.window_size,
            'stability_threshold': self.stability_threshold,
            'stability_cycles_required': self.stability_cycles_required,
            'stable_cycles_count': self.stable_cycles_count,
            '_equilibrium_detected': self._equilibrium_detected,
            '_modules_at_equilibrium': list(self._modules_at_equilibrium)
        }
        
        with open(filepath, 'w') as f:
            json.dump(state, f, indent=2)

    def load_state(self, filepath):
        """
        Load state from a JSON file.
        
        Args:
            filepath: Path to load the JSON file from
        """
        with open(filepath, 'r') as f:
            state = json.load(f)
        
        self.module_names = state['module_names']
        self.interaction_frequencies = {k: dict(v) for k, v in state['interaction_frequencies'].items()}
        self.success_rates = {k: deque(v, maxlen=self.window_size) for k, v in state['success_rates'].items()}
        self.current_success_rates = dict(state['current_success_rates'])
        self.window_size = state['window_size']
        self.stability_threshold = state['stability_threshold']
        self.stability_cycles_required = state['stability_cycles_required']
        self.stable_cycles_count = state['stable_cycles_count']
        self._equilibrium_detected = state['_equilibrium_detected']
        self._modules_at_equilibrium = list(state['_modules_at_equilibrium'])

    def reset(self):
        """Reset all tracking data."""
        self.interaction_frequencies.clear()
        self.success_rates.clear()
        self.current_success_rates.clear()
        self.stable_cycles_count = 0
        self._equilibrium_detected = False
        self._modules_at_equilibrium = []
        
        for module_name in self.module_names:
            self.success_rates[module_name] = deque(maxlen=self.window_size)
            self.current_success_rates[module_name] = 0.0
            self.interaction_frequencies[module_name] = {}
            for other_module in self.module_names:
                if other_module != module_name:
                    self.interaction_frequencies[module_name][other_module] = 0.0

    def set_stability_threshold(self, threshold):
        """
        Set the stability threshold for detecting equilibrium.
        
        Args:
            threshold: Float representing the maximum allowed variation (default 0.05)
        """
        if threshold < 0 or threshold > 1:
            raise ValueError("Stability threshold must be between 0 and 1")
        self.stability_threshold = threshold

    def set_stability_cycles_required(self, cycles):
        """
        Set the number of consecutive stable cycles required for equilibrium.
        
        Args:
            cycles: Number of cycles (must be positive)
        """
        if cycles < 1:
            raise ValueError("Stability cycles required must be at least 1")
        self.stability_cycles_required = cycles

    def set_window_size(self, size):
        """
        Set the sliding window size for tracking success rates.
        
        Args:
            size: Window size (must be positive)
        """
        if size < 1:
            raise ValueError("Window size must be at least 1")
        self.window_size = size
        # Recreate deques with new size
        for module_name in self.module_names:
            old_rates = list(self.success_rates.get(module_name, []))
            self.success_rates[module_name] = deque(old_rates, maxlen=size)

    def detect_equilibrium(self, module_stats):
        """
        Detect if the system is at Nash equilibrium based on module stats.
        
        Args:
            module_stats: Dictionary mapping module names to their success rates
            
        Returns:
            True if equilibrium is detected, False otherwise
        """
        for module_name, success_rate in module_stats.items():
            self.record_success_rate(module_name, success_rate)
        self.increment_cycle()
        return self._equilibrium_detected

    def get_stable_modules(self):
        """
        Get the list of modules that are currently at equilibrium.
        
        Returns:
            List of module names that are stable
        """
        return self._modules_at_equilibrium.copy()


def record_mutation_impact(module_name, impact_score):
    """
    Record the impact of a mutation on a module.
    
    Args:
        module_name: Name of the module
        impact_score: Impact score value (0.0 to 1.0)
    """
    global _mutation_impacts
    if '_mutation_impacts' not in globals():
        _mutation_impacts = {}
    if module_name not in _mutation_impacts:
        _mutation_impacts[module_name] = deque(maxlen=20)
    _mutation_impacts[module_name].append(impact_score)


def detect_nash_equilibrium():
    """
    Detect if the system is at Nash equilibrium based on recorded mutation impacts.
    
    Returns:
        True if equilibrium is detected, False otherwise
    """
    global _mutation_impacts
    if '_mutation_impacts' not in globals() or not _mutation_impacts:
        return False
    
    # Check if all modules have stable impact scores within 5% threshold
    all_stable = True
    for module_name, impacts in _mutation_impacts.items():
        if len(impacts) < 2:
            all_stable = False
            continue
        impacts_list = list(impacts)
        min_impact = min(impacts_list)
        max_impact = max(impacts_list)
        if max_impact > 0 and (max_impact - min_impact) / max_impact > 0.05:
            all_stable = False
            break
    
    return all_stable


def get_stable_modules():
    """
    Get the list of modules that are currently stable.
    
    Returns:
        List of module names that are stable
    """
    global _mutation_impacts
    if '_mutation_impacts' not in globals() or not _mutation_impacts:
        return []
    
    stable_modules = []
    for module_name, impacts in _mutation_impacts.items():
        if len(impacts) >= 2:
            impacts_list = list(impacts)
            min_impact = min(impacts_list)
            max_impact = max(impacts_list)
            if max_impact == 0 or (max_impact - min_impact) / max_impact <= 0.05:
                stable_modules.append(module_name)
    
    return stable_modules


def run_test_mode():
    """Simple test mode that can run standalone."""
    print("Running NashEquilibriumDetector in test mode...")
    
    # Create detector with test modules
    detector = NashEquilibriumDetector(
        module_names=["module_a", "module_b", "module_c"]
    )
    
    # Test 1: Initial state
    print("\nTest 1: Initial state")
    is_eq, modules_eq = detector.is_nash_equilibrium()
    print(f"  Equilibrium: {is_eq}")
    print(f"  Modules at equilibrium: {modules_eq}")
    assert not is_eq, "Initial state should not be in equilibrium"
    print("  PASSED")
    
    # Test 2: Record varying success rates (should not trigger equilibrium)
    print("\nTest 2: Record varying success rates (should not trigger equilibrium)")
    for cycle in range(3):
        detector.record_success_rate("module_a", 0.8 + (cycle * 0.05))
        detector.record_success_rate("module_b", 0.7 + (cycle * 0.03))
        detector.record_success_rate("module_c", 0.9 - (cycle * 0.04))
        detector.increment_cycle()
    
    is_eq, modules_eq = detector.is_nash_equilibrium()
    print(f"  Equilibrium: {is_eq}")
    print(f"  Modules at equilibrium: {modules_eq}")
    assert not is_eq, "Varying rates should prevent equilibrium"
    print("  PASSED")
    
    # Test 3: Record stable success rates (should trigger equilibrium after 5 cycles)
    print("\nTest 3: Record stable success rates (should trigger equilibrium after 5 cycles)")
    for cycle in range(6):
        detector.record_success_rate("module_a", 0.85)
        detector.record_success_rate("module_b", 0.75)
        detector.record_success_rate("module_c", 0.90)
        detector.increment_cycle()
    
    is_eq, modules_eq = detector.is_nash_equilibrium()
    print(f"  Equilibrium: {is_eq}")
    print(f"  Modules at equilibrium: {modules_eq}")
    assert is_eq, "Stable rates should trigger equilibrium"
    assert len(modules_eq) == 3, "All modules should be at equilibrium"
    print("  PASSED")
    
    # Test 4: JSON persistence
    print("\nTest 4: JSON persistence")
    detector.save_state("test_state.json")
    detector.reset()
    is_eq, modules_eq = detector.is_nash_equilibrium()
    print(f"  After reset - Equilibrium: {is_eq}")
    assert not is_eq, "After reset should not be in equilibrium"
    
    detector.load_state("test_state.json")
    is_eq, modules_eq = detector.is_nash_equilibrium()
    print(f"  After load - Equilibrium: {is_eq}")
    assert is_eq, "After load should be in equilibrium"
    print("  PASSED")
    
    # Test 5: Reset and verify
    print("\nTest 5: Reset")
    detector.reset()
    is_eq, modules_eq = detector.is_nash_equilibrium()
    print(f"  Equilibrium: {is_eq}")
    print(f"  Modules at equilibrium: {modules_eq}")
    assert not is_eq, "After reset should not be in equilibrium"
    print("  PASSED")
    
    # Test 6: Partial stability (only some modules stable)
    print("\nTest 6: Partial stability (only some modules stable)")
    for cycle in range(6):
        detector.record_success_rate("module_a", 0.85)
        detector.record_success_rate("module_b", 0.75)
        detector.record_success_rate("module_c", 0.90 + (cycle * 0.02))  # Varying
        detector.increment_cycle()
    
    is_eq, modules_eq = detector.is_nash_equilibrium()
    print(f"  Equilibrium: {is_eq}")
    print(f"  Modules at equilibrium: {modules_eq}")
    assert not is_eq, "Partial stability should not trigger equilibrium"
    assert len(modules_eq) == 2, "Only two modules should be stable"
    print("  PASSED")
    
    # Test 7: detect_equilibrium API
    print("\nTest 7: detect_equilibrium API")
    detector.reset()
    for cycle in range(6):
        module_stats = {
            "module_a": 0.85,
            "module_b": 0.75,
            "module_c": 0.90
        }
        result = detector.detect_equilibrium(module_stats)
    print(f"  Equilibrium detected: {result}")
    assert result, "detect_equilibrium should return True after stable cycles"
    print("  PASSED")
    
    # Test 8: get_stable_modules API
    print("\nTest 8: get_stable_modules API")
    stable_modules = detector.get_stable_modules()
    print(f"  Stable modules: {stable_modules}")
    assert len(stable_modules) == 3, "All modules should be stable"
    print("  PASSED")
    
    # Test 9: record_mutation_impact, detect_nash_equilibrium, get_stable_modules
    print("\nTest 9: Module-level functions")
    # Reset global state
    global _mutation_impacts
    _mutation_impacts = {}
    
    # Record varying impacts (should not be equilibrium)
    for i in range(3):
        record_mutation_impact("module_a", 0.8 + (i * 0.05))
        record_mutation_impact("module_b", 0.7 + (i * 0.03))
        record_mutation_impact("module_c", 0.9 - (i * 0.04))
    
    eq_result = detect_nash_equilibrium()
    print(f"  Equilibrium with varying impacts: {eq_result}")
    assert not eq_result, "Varying impacts should not be equilibrium"
    
    # Record stable impacts (should be equilibrium)
    for i in range(6):
        record_mutation_impact("module_a", 0.85)
        record_mutation_impact("module_b", 0.75)
        record_mutation_impact("module_c", 0.90)
    
    eq_result = detect_nash_equilibrium()
    print(f"  Equilibrium with stable impacts: {eq_result}")
    assert eq_result, "Stable impacts should be equilibrium"
    
    stable_modules = get_stable_modules()
    print(f"  Stable modules: {stable_modules}")
    assert len(stable_modules) == 3, "All modules should be stable"
    print("  PASSED")
    
    # Clean up test file
    if os.path.exists("test_state.json"):
        os.remove("test_state.json")
    
    print("\nAll tests passed!")


if __name__ == "__main__":
    run_test_mode()