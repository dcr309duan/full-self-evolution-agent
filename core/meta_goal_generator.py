import logging
from collections import deque
from typing import List, Optional
import random

logger = logging.getLogger(__name__)

class MetaGoalGenerator:
    """
    Generates meta-goals to guide the goal generation process.
    Tracks goal type distribution and mutation success rate to detect
    stagnation and inject disruptive goals when necessary.
    """

    def __init__(self, window_size: int = 10, plateau_threshold: int = 5):
        """
        Initialize the meta-goal generator.

        Args:
            window_size: Number of recent cycles to track for goal type distribution.
            plateau_threshold: Number of cycles without improvement to consider a plateau.
        """
        self.window_size = window_size
        self.plateau_threshold = plateau_threshold
        self.goal_types: deque = deque(maxlen=window_size)  # 'incremental' or 'radical'
        self.success_rates: deque = deque(maxlen=window_size)  # float values
        self.disruptive_actions: List[str] = [
            "remove_most_used_module",
            "set_contradictory_objective",
            "randomly_corrupt_module"
        ]
        self.injection_log: List[dict] = []

    def record_goal_type(self, goal_type: str) -> None:
        """Record the type of goal generated."""
        if goal_type not in ('incremental', 'radical'):
            raise ValueError("Goal type must be 'incremental' or 'radical'")
        self.goal_types.append(goal_type)

    def record_success_rate(self, rate: float) -> None:
        """Record the mutation success rate for the current cycle."""
        if not 0.0 <= rate <= 1.0:
            raise ValueError("Success rate must be between 0.0 and 1.0")
        self.success_rates.append(rate)

    def get_radical_goal_ratio(self) -> float:
        """Calculate the proportion of radical goals in the current window."""
        if not self.goal_types:
            return 0.0
        radical_count = sum(1 for g in self.goal_types if g == 'radical')
        return radical_count / len(self.goal_types)

    def is_success_rate_plateaued(self) -> bool:
        """
        Detect if the success rate has plateaued (no improvement for plateau_threshold cycles).
        Returns True if plateaued, False otherwise.
        """
        if len(self.success_rates) < self.plateau_threshold:
            return False

        # Check last plateau_threshold rates for no improvement
        recent_rates = list(self.success_rates)[-self.plateau_threshold:]
        # Consider plateaued if the maximum rate in the window is not higher than the first
        return max(recent_rates) <= recent_rates[0] + 1e-6  # small tolerance for floating point

    def should_inject_disruptive_goal(self) -> bool:
        """
        Determine if a disruptive goal should be injected.
        Conditions: radical goals < 20% OR success rate plateaued.
        """
        radical_ratio = self.get_radical_goal_ratio()
        plateaued = self.is_success_rate_plateaued()

        condition_radical_low = radical_ratio < 0.2
        condition_plateau = plateaued

        if condition_radical_low or condition_plateau:
            logger.info(
                f"Disruptive injection conditions met: radical_ratio={radical_ratio:.2f}, "
                f"plateaued={plateaued}"
            )
            return True
        return False

    def inject_disruptive_goal(self) -> str:
        """
        Forcibly inject a disruptive goal by selecting a random disruptive action.
        Logs the injection event.
        Returns the selected disruptive action.
        """
        action = random.choice(self.disruptive_actions)
        injection_event = {
            "action": action,
            "radical_ratio": self.get_radical_goal_ratio(),
            "success_rates": list(self.success_rates),
            "goal_types": list(self.goal_types)
        }
        self.injection_log.append(injection_event)
        logger.info(f"Injected disruptive goal: {action}")
        return action

    def get_injection_log(self) -> List[dict]:
        """Return the log of injection events for analysis."""
        return self.injection_log

    def clear_history(self) -> None:
        """Clear all tracked history (goal types and success rates)."""
        self.goal_types.clear()
        self.success_rates.clear()
        logger.info("Meta-goal generator history cleared.")