import json
import os
from datetime import datetime
from collections import deque

class PlasticityStabilityScheduler:
    """
    Tracks mutation outcomes and dynamically adjusts mutation_rate and
    goal_acceptance_threshold based on consecutive successes or failures.
    """

    def __init__(self, initial_mutation_rate=0.5, initial_threshold=0.5, window_size=10, log_path="logs/meta_parameter_history.jsonl"):
        self.mutation_rate = initial_mutation_rate
        self.threshold = initial_threshold
        self.window_size = window_size
        self.log_path = log_path
        self.outcomes = deque(maxlen=window_size)
        self.cycle = 0

        # Ensure log directory exists
        os.makedirs(os.path.dirname(self.log_path), exist_ok=True)

    def record_outcome(self, success: bool):
        """Record a single mutation outcome (True for success, False for failure)."""
        self.outcomes.append(success)
        self.cycle += 1
        self._check_and_adjust()

    def _check_and_adjust(self):
        """Check for 3 consecutive failures or successes and adjust parameters."""
        if len(self.outcomes) < 3:
            return

        # Get last 3 outcomes
        last_three = list(self.outcomes)[-3:]

        if all(not outcome for outcome in last_three):
            # 3 consecutive failures
            old_rate = self.mutation_rate
            old_threshold = self.threshold

            self.mutation_rate = max(0.1, self.mutation_rate * 0.8)
            self.threshold = min(0.9, self.threshold * 1.1)

            self._log_adjustment("3 consecutive failures", old_rate, old_threshold)

        elif all(outcome for outcome in last_three):
            # 3 consecutive successes
            old_rate = self.mutation_rate
            old_threshold = self.threshold

            self.mutation_rate = min(0.9, self.mutation_rate * 1.2)
            self.threshold = max(0.1, self.threshold * 0.9)

            self._log_adjustment("3 consecutive successes", old_rate, old_threshold)

    def _log_adjustment(self, reason: str, old_rate: float, old_threshold: float):
        """Log the adjustment to the JSONL file."""
        entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "cycle": self.cycle,
            "old_mutation_rate": round(old_rate, 4),
            "new_mutation_rate": round(self.mutation_rate, 4),
            "old_goal_acceptance_threshold": round(old_threshold, 4),
            "new_goal_acceptance_threshold": round(self.threshold, 4),
            "trigger_reason": reason
        }

        with open(self.log_path, "a") as f:
            f.write(json.dumps(entry) + "\n")

    def get_state(self):
        """Return current parameter values."""
        return {
            "mutation_rate": self.mutation_rate,
            "goal_acceptance_threshold": self.threshold,
            "cycle": self.cycle,
            "recent_outcomes": list(self.outcomes)
        }