from typing import List, Dict, Any, Optional
from agent_core.feasibility_estimator import FeasibilityEstimator
from agent_core.dependency_graph import DependencyGraph
from agent_core.backlog import Backlog
from agent_core.goal_executor import GoalExecutor
import logging

logger = logging.getLogger(__name__)


class Orchestrator:
    """
    Orchestrates goal execution by integrating feasibility checks,
    dependency management, and backlog prioritization.
    """

    def __init__(
        self,
        feasibility_estimator: FeasibilityEstimator,
        dependency_graph: DependencyGraph,
        backlog: Backlog,
        goal_executor: GoalExecutor,
    ):
        self.feasibility_estimator = feasibility_estimator
        self.dependency_graph = dependency_graph
        self.backlog = backlog
        self.goal_executor = goal_executor

    def run_cycle(self) -> None:
        """
        Execute one full cycle: check feasibility, execute goals, update dependencies,
        and re-prioritize the backlog.
        """
        goals = self.backlog.get_pending_goals()
        if not goals:
            logger.info("No pending goals in backlog.")
            return

        for goal in goals:
            self._process_goal(goal)

        self._update_dependencies()
        self._reprioritize_backlog()

    def _process_goal(self, goal: Dict[str, Any]) -> None:
        """
        Check feasibility of a goal and execute if possible.
        If blocked, log the reason and skip.
        """
        goal_id = goal.get("id", "unknown")
        logger.info(f"Processing goal: {goal_id}")

        if not self.feasibility_estimator.is_feasible(goal):
            reason = self.feasibility_estimator.get_blocking_reason(goal)
            logger.warning(f"Goal {goal_id} is blocked: {reason}")
            self.backlog.mark_blocked(goal_id, reason)
            return

        try:
            self.goal_executor.execute(goal)
            logger.info(f"Goal {goal_id} completed successfully.")
            self.backlog.mark_completed(goal_id)
        except Exception as e:
            logger.error(f"Goal {goal_id} failed during execution: {e}")
            self.backlog.mark_failed(goal_id, str(e))

    def _update_dependencies(self) -> None:
        """
        After each cycle, update the dependency graph by marking prerequisites
        as satisfied for all completed goals.
        """
        completed_goals = self.backlog.get_completed_goals()
        for goal in completed_goals:
            goal_id = goal.get("id")
            if goal_id:
                self.dependency_graph.mark_prerequisites_satisfied(goal_id)
                logger.debug(f"Dependencies updated for goal: {goal_id}")

    def _reprioritize_backlog(self) -> None:
        """
        Re-prioritize the backlog based on updated dependency status and feasibility.
        """
        self.backlog.reprioritize()
        logger.info("Backlog re-prioritized.")