import json
import os
from collections import deque

class NashEquilibriumDetector:
    """
    A self-contained Nash equilibrium detector that tracks module interaction
    success rates over a sliding window and detects when the system has
    converged (no single module improves by >5% in 3 consecutive cycles).
    """

    def __init__(self, window_size=20, improvement_threshold=0.05, stagnation_cycles=3, data_file="nash_data.json"):
        self.window_size = window_size
        self.improvement_threshold = improvement_threshold
        self.stagnation_cycles = stagnation_cycles
        self.data_file = data_file
        self.history = {}  # module_name -> deque of success rates
        self._load_history()

    def _load_history(self):
        """Load history from JSON file if it exists."""
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, 'r') as f:
                    raw = json.load(f)
                for module, rates in raw.items():
                    self.history[module] = deque(rates, maxlen=self.window_size)
            except (json.JSONDecodeError, IOError):
                self.history = {}

    def _save_history(self):
        """Save current history to JSON file."""
        try:
            serializable = {module: list(rates) for module, rates in self.history.items()}
            with open(self.data_file, 'w') as f:
                json.dump(serializable, f)
        except IOError:
            pass  # Silently fail if file cannot be written

    def record_success_rate(self, module_name, success_rate):
        """
        Record a success rate for a given module.
        success_rate should be a float between 0.0 and 1.0.
        """
        if module_name not in self.history:
            self.history[module_name] = deque(maxlen=self.window_size)
        self.history[module_name].append(success_rate)
        self._save_history()

    def get_average_success_rate(self, module_name):
        """Return the average success rate over the current window for a module."""
        if module_name not in self.history or len(self.history[module_name]) == 0:
            return 0.0
        return sum(self.history[module_name]) / len(self.history[module_name])

    def get_improvement(self, module_name):
        """
        Calculate the improvement in average success rate over the last two
        halves of the window. Returns None if insufficient data.
        """
        rates = self.history.get(module_name, [])
        if len(rates) < 4:  # Need at least 4 data points for meaningful comparison
            return None
        mid = len(rates) // 2
        first_half = rates[:mid]
        second_half = rates[mid:]
        if len(first_half) == 0 or len(second_half) == 0:
            return None
        avg_first = sum(first_half) / len(first_half)
        avg_second = sum(second_half) / len(second_half)
        if avg_first == 0:
            return float('inf') if avg_second > 0 else 0.0
        return (avg_second - avg_first) / avg_first

    def detect_nash(self):
        """
        Detect if the system has reached a Nash equilibrium.
        Returns (True/False, list_of_candidate_modules).
        True if no module has improved by >5% in the last 3 consecutive cycles.
        Candidate modules are those with the lowest recent improvement.
        """
        if not self.history:
            return False, []

        # Check each module for stagnation
        stagnant_modules = []
        for module, rates in self.history.items():
            if len(rates) < self.stagnation_cycles + 1:
                continue  # Not enough data to judge
            recent_improvements = []
            for i in range(1, self.stagnation_cycles + 1):
                if len(rates) >= i + 1:
                    prev = rates[-(i+1)]
                    curr = rates[-i]
                    if prev == 0:
                        improvement = float('inf') if curr > 0 else 0.0
                    else:
                        improvement = (curr - prev) / prev
                    recent_improvements.append(improvement)
            if all(imp <= self.improvement_threshold for imp in recent_improvements):
                stagnant_modules.append(module)

        # If all modules with sufficient data are stagnant, consider it Nash
        modules_with_data = [m for m in self.history if len(self.history[m]) >= self.stagnation_cycles + 1]
        if len(modules_with_data) == 0:
            return False, []

        all_stagnant = len(stagnant_modules) == len(modules_with_data)
        if not all_stagnant:
            return False, []

        # Identify candidate modules for coordinated change (those with lowest recent improvement)
        candidate_modules = []
        for module in modules_with_data:
            rates = self.history[module]
            if len(rates) >= 2:
                recent_improvement = (rates[-1] - rates[-2]) / max(rates[-2], 0.001)
                candidate_modules.append((module, recent_improvement))
        candidate_modules.sort(key=lambda x: x[1])  # Sort by improvement (ascending)
        candidates = [m[0] for m in candidate_modules[:max(1, len(candidate_modules)//2)]]

        return True, candidates

    def is_stuck(self):
        """
        Returns a boolean flag indicating whether the system is stuck in a Nash equilibrium.
        This is a convenience method that returns True if detect_nash returns True.
        """
        nash_detected, _ = self.detect_nash()
        return nash_detected

    def reset(self):
        """Clear all history and reset the detector."""
        self.history = {}
        if os.path.exists(self.data_file):
            try:
                os.remove(self.data_file)
            except OSError:
                pass


# Convenience function for external use
def detect_nash(data_file="nash_data.json"):
    """
    Load the detector from file and run detection.
    Returns (True/False, list_of_candidate_modules).
    """
    detector = NashEquilibriumDetector(data_file=data_file)
    return detector.detect_nash()

def is_stuck(data_file="nash_data.json"):
    """
    Convenience function that returns a boolean 'stuck' flag.
    Returns True if the system is in a Nash equilibrium (stuck).
    """
    detector = NashEquilibriumDetector(data_file=data_file)
    return detector.is_stuck()