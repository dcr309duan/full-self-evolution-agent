from typing import Dict, List, Set, Optional, Callable
import logging
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class GoalStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    BLOCKED = "blocked_by_unmet_dependencies"
    FAILED = "failed"


@dataclass
class Goal:
    id: str
    description: str
    dependencies: Set[str] = field(default_factory=set)
    status: GoalStatus = GoalStatus.PENDING
    execute: Optional[Callable] = None  # Function to execute the goal


class DependencyGraph:
    def __init__(self):
        self.goals: Dict[str, Goal] = {}
        self.blocked_goals: Set[str] = set()

    def add_goal(self, goal: Goal) -> None:
        self.goals[goal.id] = goal

    def get_dependencies(self, goal_id: str) -> Set[str]:
        if goal_id in self.goals:
            return self.goals[goal_id].dependencies
        return set()

    def are_dependencies_met(self, goal_id: str) -> bool:
        """Check if all dependencies for a goal are completed."""
        goal = self.goals.get(goal_id)
        if not goal:
            return False
        for dep_id in goal.dependencies:
            dep_goal = self.goals.get(dep_id)
            if not dep_goal or dep_goal.status != GoalStatus.COMPLETED:
                return False
        return True

    def mark_met(self, goal_id: str) -> None:
        """Mark a goal as completed and remove from blocked set if present."""
        if goal_id in self.goals:
            self.goals[goal_id].status = GoalStatus.COMPLETED
            self.blocked_goals.discard(goal_id)

    def get_blocked_goals(self) -> List[str]:
        """Return list of currently blocked goal IDs."""
        return list(self.blocked_goals)

    def add_blocked_goal(self, goal_id: str) -> None:
        """Add a goal to the blocked set."""
        self.blocked_goals.add(goal_id)


class GoalExecutionPipeline:
    def __init__(self, graph: DependencyGraph):
        self.graph = graph
        self.execution_order: List[str] = []

    def verify_prerequisites(self, goal_id: str) -> bool:
        """Verify that all prerequisites for a goal are met."""
        if not self.graph.are_dependencies_met(goal_id):
            logger.info(f"Goal '{goal_id}' blocked by unmet dependencies")
            self.graph.add_blocked_goal(goal_id)
            self.graph.goals[goal_id].status = GoalStatus.BLOCKED
            return False
        return True

    def execute_goal(self, goal_id: str) -> bool:
        """Execute a single goal after verifying prerequisites."""
        goal = self.graph.goals.get(goal_id)
        if not goal:
            logger.error(f"Goal '{goal_id}' not found")
            return False

        # Step 1: Verify prerequisites
        if not self.verify_prerequisites(goal_id):
            return False

        # Step 2: Mark as in progress and execute
        goal.status = GoalStatus.IN_PROGRESS
        logger.info(f"Executing goal: {goal_id} - {goal.description}")

        try:
            if goal.execute:
                goal.execute()
            # Step 3: Mark as completed
            self.graph.mark_met(goal_id)
            logger.info(f"Goal '{goal_id}' completed successfully")
            self.execution_order.append(goal_id)

            # Step 4: Re-evaluate blocked goals
            self.re_evaluate_blocked_goals()
            return True

        except Exception as e:
            goal.status = GoalStatus.FAILED
            logger.error(f"Goal '{goal_id}' failed: {e}")
            return False

    def re_evaluate_blocked_goals(self) -> None:
        """Re-evaluate all blocked goals to see if they can now proceed."""
        blocked_goals = self.graph.get_blocked_goals()
        if not blocked_goals:
            return

        logger.info(f"Re-evaluating {len(blocked_goals)} blocked goals")
        for goal_id in blocked_goals.copy():
            if self.graph.are_dependencies_met(goal_id):
                logger.info(f"Goal '{goal_id}' dependencies now met, attempting execution")
                self.execute_goal(goal_id)

    def run_pipeline(self, goal_ids: List[str]) -> None:
        """Run the execution pipeline for a list of goals."""
        logger.info("Starting goal execution pipeline")
        for goal_id in goal_ids:
            self.execute_goal(goal_id)

        # Final check for any remaining blocked goals
        remaining_blocked = self.graph.get_blocked_goals()
        if remaining_blocked:
            logger.warning(f"Pipeline completed with {len(remaining_blocked)} blocked goals: {remaining_blocked}")