from typing import List, Dict, Any
import json
import os
from collections import deque

class MetaParameterScheduler:
    """
    Maintains a sliding window of mutation success/failure outcomes and dynamically
    adjusts mutation rate and goal acceptance threshold based on recent performance.
    """

    DEFAULT_MUTATION_RATE = 0.1
    DEFAULT_GOAL_THRESHOLD = 0.5
    WINDOW_SIZE = 10
    LOW_SUCCESS_THRESHOLD = 0.3
    HIGH_SUCCESS_THRESHOLD = 0.7
    MUTATION_RATE_DECREASE_FACTOR = 0.8
    MUTATION_RATE_INCREASE_FACTOR = 1.1
    THRESHOLD_INCREASE_FACTOR = 1.1
    THRESHOLD_DECREASE_FACTOR = 0.95
    PERSISTENCE_FILE = "meta_parameters.json"

    def __init__(self, mutation_rate: float = None, goal_threshold: float = None):
        self.mutation_rate = mutation_rate if mutation_rate is not None else self.DEFAULT_MUTATION_RATE
        self.goal_threshold = goal_threshold if goal_threshold is not None else self.DEFAULT_GOAL_THRESHOLD
        self.history: deque = deque(maxlen=self.WINDOW_SIZE)

    def record_outcome(self, success: bool) -> None:
        """
        Record a mutation outcome and adjust parameters based on recent success rate.
        """
        self.history.append(success)
        if len(self.history) == self.WINDOW_SIZE:
            self._adjust_parameters()

    def _adjust_parameters(self) -> None:
        """Adjust mutation rate and goal threshold based on success rate over the window."""
        success_rate = self._calculate_success_rate()
        if success_rate < self.LOW_SUCCESS_THRESHOLD:
            self.mutation_rate *= self.MUTATION_RATE_DECREASE_FACTOR
            self.goal_threshold *= self.THRESHOLD_INCREASE_FACTOR
        elif success_rate > self.HIGH_SUCCESS_THRESHOLD:
            self.mutation_rate *= self.MUTATION_RATE_INCREASE_FACTOR
            self.goal_threshold *= self.THRESHOLD_DECREASE_FACTOR
        self._persist_parameters()

    def _calculate_success_rate(self) -> float:
        """Calculate the success rate over the current window."""
        if not self.history:
            return 0.0
        return sum(self.history) / len(self.history)

    def get_current_params(self) -> Dict[str, float]:
        """Return the current mutation rate and goal threshold."""
        return {
            "mutation_rate": self.mutation_rate,
            "goal_threshold": self.goal_threshold
        }

    def get_history(self) -> List[bool]:
        """Return the list of recorded outcomes (most recent first)."""
        return list(self.history)

    def _persist_parameters(self) -> None:
        """Save current parameters and history to a JSON file."""
        data = {
            "mutation_rate": self.mutation_rate,
            "goal_threshold": self.goal_threshold,
            "history": list(self.history)
        }
        with open(self.PERSISTENCE_FILE, "w") as f:
            json.dump(data, f, indent=2)

    def load_from_file(self, filepath: str = None) -> None:
        """Load parameters and history from a JSON file."""
        filepath = filepath or self.PERSISTENCE_FILE
        if os.path.exists(filepath):
            with open(filepath, "r") as f:
                data = json.load(f)
            self.mutation_rate = data.get("mutation_rate", self.DEFAULT_MUTATION_RATE)
            self.goal_threshold = data.get("goal_threshold", self.DEFAULT_GOAL_THRESHOLD)
            self.history = deque(data.get("history", []), maxlen=self.WINDOW_SIZE)