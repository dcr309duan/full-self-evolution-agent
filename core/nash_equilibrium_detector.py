import json
import os
from collections import deque

class NashEquilibriumDetector:
    """
    A self-contained Nash equilibrium detector that tracks mutation outcomes
    (success/failure/improvement) over a sliding window and detects when no
    single-module mutation has improved the system for M consecutive cycles.
    """

    def __init__(self, window_size=20, stagnation_cycles=10, data_file="nash_data.json"):
        self.window_size = window_size
        self.stagnation_cycles = stagnation_cycles
        self.data_file = data_file
        self.history = {}  # module_name -> deque of outcomes (0=failure, 1=success, 2=improvement)
        self.cycles_since_improvement = 0
        self._load_history()

    def _load_history(self):
        """Load history from JSON file if it exists."""
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, 'r') as f:
                    raw = json.load(f)
                for module, outcomes in raw.items():
                    self.history[module] = deque(outcomes, maxlen=self.window_size)
                self.cycles_since_improvement = raw.get('cycles_since_improvement', 0)
            except (json.JSONDecodeError, IOError, KeyError):
                self.history = {}
                self.cycles_since_improvement = 0

    def _save_history(self):
        """Save current history to JSON file."""
        try:
            serializable = {module: list(outcomes) for module, outcomes in self.history.items()}
            serializable['cycles_since_improvement'] = self.cycles_since_improvement
            with open(self.data_file, 'w') as f:
                json.dump(serializable, f)
        except IOError:
            pass  # Silently fail if file cannot be written

    def record_outcome(self, module_name, outcome):
        """
        Record a mutation outcome for a given module.
        outcome should be one of: 'failure' (0), 'success' (1), 'improvement' (2).
        """
        if module_name not in self.history:
            self.history[module_name] = deque(maxlen=self.window_size)
        
        if outcome == 'failure':
            outcome_code = 0
        elif outcome == 'success':
            outcome_code = 1
        elif outcome == 'improvement':
            outcome_code = 2
        else:
            raise ValueError("outcome must be 'failure', 'success', or 'improvement'")
        
        self.history[module_name].append(outcome_code)
        
        if outcome == 'improvement':
            self.cycles_since_improvement = 0
        else:
            self.cycles_since_improvement += 1
        
        self._save_history()

    def get_module_outcomes(self, module_name):
        """Return the list of recent outcomes for a module."""
        if module_name not in self.history:
            return []
        return list(self.history[module_name])

    def get_success_rate(self, module_name):
        """Return the success rate (including improvements) over the current window for a module."""
        outcomes = self.history.get(module_name, [])
        if len(outcomes) == 0:
            return 0.0
        successes = sum(1 for o in outcomes if o >= 1)  # success or improvement
        return successes / len(outcomes)

    def get_improvement_rate(self, module_name):
        """Return the improvement rate over the current window for a module."""
        outcomes = self.history.get(module_name, [])
        if len(outcomes) == 0:
            return 0.0
        improvements = sum(1 for o in outcomes if o == 2)
        return improvements / len(outcomes)

    def is_at_nash(self):
        """
        Detect if the system has reached a Nash equilibrium.
        Returns True if no single-module mutation has improved the system
        for M consecutive cycles (configurable, default M=10).
        """
        return self.cycles_since_improvement >= self.stagnation_cycles

    def detect_equilibrium(self):
        """
        Legacy method for backward compatibility.
        Returns (True/False, list_of_modules_in_equilibrium).
        """
        nash = self.is_at_nash()
        modules_with_data = [m for m in self.history if len(self.history[m]) > 0]
        return nash, modules_with_data if nash else []

    def is_stuck(self):
        """
        Returns a boolean flag indicating whether the system is stuck in a Nash equilibrium.
        This is a convenience method that returns True if is_at_nash returns True.
        """
        return self.is_at_nash()

    def reset(self):
        """Clear all history and reset the detector."""
        self.history = {}
        self.cycles_since_improvement = 0
        if os.path.exists(self.data_file):
            try:
                os.remove(self.data_file)
            except OSError:
                pass


# Convenience functions for external use
def detect_equilibrium(data_file="nash_data.json"):
    """
    Load the detector from file and run detection.
    Returns (True/False, list_of_modules_in_equilibrium).
    """
    detector = NashEquilibriumDetector(data_file=data_file)
    return detector.detect_equilibrium()

def is_stuck(data_file="nash_data.json"):
    """
    Convenience function that returns a boolean 'stuck' flag.
    Returns True if the system is in a Nash equilibrium (stuck).
    """
    detector = NashEquilibriumDetector(data_file=data_file)
    return detector.is_stuck()

def is_at_nash(data_file="nash_data.json"):
    """
    Convenience function that returns whether the system is at Nash equilibrium.
    """
    detector = NashEquilibriumDetector(data_file=data_file)
    return detector.is_at_nash()

def get_cycles_since_improvement(data_file="nash_data.json"):
    """
    Convenience function that returns the number of cycles since last improvement.
    """
    detector = NashEquilibriumDetector(data_file=data_file)
    return detector.cycles_since_improvement