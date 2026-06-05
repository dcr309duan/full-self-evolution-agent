from typing import List, Dict, Optional, Any
from evolution_engine.feasibility_estimator import FeasibilityEstimator
from evolution_engine.failure_analysis import FailureAnalyzer
from evolution_engine.goal_types import GoalType, Goal
import logging

logger = logging.getLogger(__name__)

class GoalGenerator:
    """
    Generates goals with dependency-aware feasibility estimation.
    Integrates feasibility checks before yielding goals and implements
    a feedback loop to deprioritize blocked goal types.
    """

    def __init__(self, feasibility_estimator: FeasibilityEstimator,
                 failure_analyzer: FailureAnalyzer,
                 deprioritization_threshold: int = 3):
        self.feasibility_estimator = feasibility_estimator
        self.failure_analyzer = failure_analyzer
        self.deprioritization_threshold = deprioritization_threshold
        self.blocked_goal_counts: Dict[GoalType, int] = {}
        self.deprioritized_goal_types: set = set()
        self.goal_candidates: List[Goal] = []
        self.blocked_categories: set = set()

    def add_goal_candidates(self, goals: List[Goal]) -> None:
        """Add a list of candidate goals to the generator."""
        self.goal_candidates.extend(goals)

    def set_blocked_categories(self, blocked_categories: set) -> None:
        """Set the blocked categories from meta_monitor."""
        self.blocked_categories = blocked_categories

    def generate_goals(self) -> List[Goal]:
        """
        Generate goals by filtering candidates through feasibility estimation.
        Deprioritizes goal types that are repeatedly blocked.
        Respects blocked categories by generating root_cause_analysis goals instead.
        Returns a list of feasible goals.
        """
        feasible_goals = []
        for goal in self.goal_candidates:
            # Check if goal's category is blocked
            if goal.goal_type in self.blocked_categories:
                # Generate root_cause_analysis goal instead
                root_cause_goal = Goal(
                    goal_type=GoalType.ROOT_CAUSE_ANALYSIS,
                    description=f"Root cause analysis for blocked category: {goal.goal_type}",
                    priority='critical'
                )
                feasible_goals.append(root_cause_goal)
                continue

            if goal.goal_type in self.deprioritized_goal_types:
                logger.info(f"Skipping deprioritized goal type: {goal.goal_type}")
                continue

            if self.feasibility_estimator.is_feasible(goal):
                feasible_goals.append(goal)
                self._reset_blocked_count(goal.goal_type)
            else:
                self._handle_blocked_goal(goal)

        # Clear processed candidates
        self.goal_candidates = []
        return feasible_goals

    def _handle_blocked_goal(self, goal: Goal) -> None:
        """Log blocked goal and update deprioritization tracking."""
        self.failure_analyzer.log_failure(goal, reason="Feasibility blocked")
        self.blocked_goal_counts[goal.goal_type] = self.blocked_goal_counts.get(goal.goal_type, 0) + 1

        if self.blocked_goal_counts[goal.goal_type] >= self.deprioritization_threshold:
            self.deprioritized_goal_types.add(goal.goal_type)
            logger.warning(f"Goal type {goal.goal_type} deprioritized due to repeated blocking.")

    def _reset_blocked_count(self, goal_type: GoalType) -> None:
        """Reset blocked count for a goal type when a goal of that type succeeds."""
        if goal_type in self.blocked_goal_counts:
            del self.blocked_goal_counts[goal_type]
        # Optionally, if a goal type succeeds, remove from deprioritized set
        if goal_type in self.deprioritized_goal_types:
            self.deprioritized_goal_types.discard(goal_type)
            logger.info(f"Goal type {goal_type} re-enabled after successful feasibility.")

    def reset_deprioritization(self) -> None:
        """Reset all deprioritization tracking (e.g., after dependency resolution)."""
        self.blocked_goal_counts.clear()
        self.deprioritized_goal_types.clear()
        logger.info("Deprioritization tracking reset.")