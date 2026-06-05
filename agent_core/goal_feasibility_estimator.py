"""Goal Feasibility Estimator for the agent core.

This module evaluates pending goals from the goal generator against the
dependency graph to determine their feasibility. It assigns a score (0.0-1.0)
based on dependency satisfaction, blocks goals below a threshold, and
re-prioritizes the backlog to favor high-feasibility, near-completion goals.
"""

import logging
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

# Default feasibility threshold below which goals are blocked
DEFAULT_FEASIBILITY_THRESHOLD = 0.5


class GoalFeasibilityEstimator:
    """Estimates feasibility of pending goals based on dependency graph."""

    def __init__(
        self,
        dependency_graph: Optional[Dict[str, List[str]]] = None,
        threshold: float = DEFAULT_FEASIBILITY_THRESHOLD,
    ):
        """
        Initialize the estimator.

        Args:
            dependency_graph: Mapping from goal ID to list of prerequisite goal IDs.
            threshold: Minimum feasibility score to allow a goal to proceed.
        """
        self.dependency_graph = dependency_graph or {}
        self.threshold = threshold
        self._blocked_goals: Set[str] = set()

    def parse_pending_goals(self, pending_goals: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Parse and validate pending goals from the goal generator.

        Args:
            pending_goals: List of goal dicts, each expected to have at least an 'id' key.

        Returns:
            List of valid goal dicts.
        """
        parsed = []
        for goal in pending_goals:
            if not isinstance(goal, dict):
                logger.warning("Skipping non-dict goal: %s", goal)
                continue
            if 'id' not in goal:
                logger.warning("Skipping goal without 'id': %s", goal)
                continue
            parsed.append(goal)
        return parsed

    def check_unmet_prerequisites(
        self, goal_id: str, completed_goals: Set[str]
    ) -> List[str]:
        """
        Check which prerequisites of a goal are unmet.

        Args:
            goal_id: The ID of the goal to check.
            completed_goals: Set of goal IDs that have been completed.

        Returns:
            List of prerequisite goal IDs that are not yet completed.
        """
        prerequisites = self.dependency_graph.get(goal_id, [])
        unmet = [prereq for prereq in prerequisites if prereq not in completed_goals]
        return unmet

    def compute_feasibility_score(
        self, goal_id: str, completed_goals: Set[str]
    ) -> float:
        """
        Compute a feasibility score (0.0-1.0) for a goal.

        The score is based on the proportion of satisfied prerequisites.
        A goal with no prerequisites gets a score of 1.0.

        Args:
            goal_id: The ID of the goal to evaluate.
            completed_goals: Set of goal IDs that have been completed.

        Returns:
            Feasibility score between 0.0 and 1.0.
        """
        prerequisites = self.dependency_graph.get(goal_id, [])
        if not prerequisites:
            return 1.0
        satisfied = sum(1 for prereq in prerequisites if prereq in completed_goals)
        return satisfied / len(prerequisites)

    def block_low_feasibility_goals(
        self,
        goals: List[Dict[str, Any]],
        completed_goals: Set[str],
    ) -> List[Dict[str, Any]]:
        """
        Identify and block goals with feasibility below the threshold.

        Blocked goals are recorded in self._blocked_goals and removed from the
        returned list.

        Args:
            goals: List of goal dicts to evaluate.
            completed_goals: Set of goal IDs that have been completed.

        Returns:
            List of goals that are not blocked.
        """
        allowed = []
        for goal in goals:
            goal_id = goal['id']
            score = self.compute_feasibility_score(goal_id, completed_goals)
            goal['feasibility_score'] = score
            if score < self.threshold:
                self._blocked_goals.add(goal_id)
                logger.info(
                    "Blocked goal '%s' due to low feasibility score: %.2f",
                    goal_id,
                    score,
                )
            else:
                allowed.append(goal)
        return allowed

    def reprioritize_backlog(
        self,
        goals: List[Dict[str, Any]],
        completed_goals: Set[str],
        pipeline_stages: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Re-prioritize goals so that those with higher feasibility and closer to
        completing the end-to-end pipeline are scheduled first.

        Sorting key: (feasibility_score descending, pipeline_proximity descending)
        where pipeline_proximity is the number of completed prerequisites (higher
        means closer to completion).

        Args:
            goals: List of goal dicts to reorder.
            completed_goals: Set of goal IDs that have been completed.
            pipeline_stages: Optional ordered list of pipeline stage IDs. If provided,
                goals later in the pipeline are considered closer to completion.

        Returns:
            Reordered list of goal dicts.
        """
        def sort_key(goal: Dict[str, Any]) -> Tuple[float, float]:
            goal_id = goal['id']
            score = goal.get('feasibility_score', self.compute_feasibility_score(goal_id, completed_goals))
            # Proximity: number of satisfied prerequisites (higher is better)
            prerequisites = self.dependency_graph.get(goal_id, [])
            satisfied_count = sum(1 for p in prerequisites if p in completed_goals)
            # If pipeline_stages provided, also consider stage index (later stage = higher priority)
            if pipeline_stages and goal_id in pipeline_stages:
                stage_index = pipeline_stages.index(goal_id)
                # Normalize to 0-1 range (later stages get higher value)
                stage_proximity = (stage_index + 1) / len(pipeline_stages)
            else:
                stage_proximity = 0.0
            # Combined proximity: average of satisfied prerequisites and stage proximity
            proximity = (satisfied_count / max(len(prerequisites), 1) + stage_proximity) / 2.0
            return (score, proximity)

        # Sort descending by score then proximity
        return sorted(goals, key=sort_key, reverse=True)

    def evaluate_and_prioritize(
        self,
        pending_goals: List[Dict[str, Any]],
        completed_goals: Set[str],
        pipeline_stages: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Full pipeline: parse, check, score, block, and re-prioritize goals.

        Args:
            pending_goals: Raw list of goal dicts from the goal generator.
            completed_goals: Set of goal IDs that have been completed.
            pipeline_stages: Optional ordered list of pipeline stage IDs.

        Returns:
            Prioritized list of feasible goals.
        """
        parsed = self.parse_pending_goals(pending_goals)
        allowed = self.block_low_feasibility_goals(parsed, completed_goals)
        prioritized = self.reprioritize_backlog(allowed, completed_goals, pipeline_stages)
        return prioritized

    def get_blocked_goals(self) -> Set[str]:
        """Return the set of currently blocked goal IDs."""
        return self._blocked_goals.copy()

    def clear_blocked_goals(self) -> None:
        """Clear the record of blocked goals."""
        self._blocked_goals.clear()