from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
import logging

from agents.feasibility_estimator import FeasibilityEstimator, FeasibilityResult

logger = logging.getLogger(__name__)

@dataclass
class Goal:
    """Represents a goal with feasibility tracking."""
    id: str
    description: str
    prerequisites: List[str] = field(default_factory=list)
    feasibility_score: float = 1.0
    is_blocked: bool = False
    block_reason: Optional[str] = None
    parent_goal_id: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "description": self.description,
            "prerequisites": self.prerequisites,
            "feasibility_score": self.feasibility_score,
            "is_blocked": self.is_blocked,
            "block_reason": self.block_reason,
            "parent_goal_id": self.parent_goal_id,
            "created_at": self.created_at.isoformat(),
            "metadata": self.metadata
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Goal":
        return cls(
            id=data["id"],
            description=data["description"],
            prerequisites=data.get("prerequisites", []),
            feasibility_score=data.get("feasibility_score", 1.0),
            is_blocked=data.get("is_blocked", False),
            block_reason=data.get("block_reason"),
            parent_goal_id=data.get("parent_goal_id"),
            created_at=datetime.fromisoformat(data["created_at"]) if "created_at" in data else datetime.utcnow(),
            metadata=data.get("metadata", {})
        )


class GoalGenerator:
    """
    Generates and manages goals with feasibility checking.
    Integrates with FeasibilityEstimator to ensure goals are achievable.
    """

    def __init__(self, feasibility_estimator: Optional[FeasibilityEstimator] = None):
        self.feasibility_estimator = feasibility_estimator or FeasibilityEstimator()
        self.goal_queue: List[Goal] = []
        self.completed_goals: List[Goal] = []
        self.failed_goals: List[Goal] = []

    def generate_goal(self, description: str, prerequisites: Optional[List[str]] = None,
                      parent_goal_id: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> Optional[Goal]:
        """
        Generate a new goal after checking feasibility.
        Returns the goal if feasible, None if blocked and cannot be decomposed.
        """
        goal_id = f"goal_{datetime.utcnow().timestamp()}_{len(self.goal_queue) + len(self.completed_goals) + len(self.failed_goals)}"
        
        goal = Goal(
            id=goal_id,
            description=description,
            prerequisites=prerequisites or [],
            parent_goal_id=parent_goal_id,
            metadata=metadata or {}
        )

        # Check feasibility
        feasibility_result = self._check_feasibility(goal)
        goal.feasibility_score = feasibility_result.score
        goal.is_blocked = not feasibility_result.is_feasible
        goal.block_reason = feasibility_result.reason

        if feasibility_result.is_feasible:
            logger.info(f"Goal {goal_id} is feasible (score: {feasibility_result.score:.2f}). Adding to queue.")
            self.goal_queue.append(goal)
            return goal
        else:
            logger.warning(f"Goal {goal_id} is blocked: {feasibility_result.reason}")
            # Try to decompose into smaller steps
            decomposed_goals = self._decompose_goal(goal, feasibility_result)
            if decomposed_goals:
                logger.info(f"Decomposed goal {goal_id} into {len(decomposed_goals)} sub-goals.")
                for sub_goal in decomposed_goals:
                    self.goal_queue.append(sub_goal)
                return goal  # Return the parent goal with updated status
            else:
                logger.error(f"Goal {goal_id} cannot be achieved and cannot be decomposed.")
                self.failed_goals.append(goal)
                return None

    def _check_feasibility(self, goal: Goal) -> FeasibilityResult:
        """Check feasibility using the estimator."""
        if self.feasibility_estimator:
            return self.feasibility_estimator.estimate(goal)
        # Default: assume feasible if no estimator
        return FeasibilityResult(
            is_feasible=True,
            score=1.0,
            reason="No feasibility estimator configured"
        )

    def _decompose_goal(self, goal: Goal, feasibility_result: FeasibilityResult) -> List[Goal]:
        """
        Attempt to decompose a blocked goal into smaller sub-goals.
        Returns a list of sub-goals that have their prerequisites met.
        """
        if not feasibility_result.blocked_prerequisites:
            logger.debug(f"No specific blocked prerequisites identified for goal {goal.id}. Cannot decompose.")
            return []

        sub_goals = []
        for prereq in feasibility_result.blocked_prerequisites:
            # Create a sub-goal to satisfy the prerequisite
            sub_goal = Goal(
                id=f"{goal.id}_sub_{len(sub_goals)}",
                description=f"Resolve prerequisite: {prereq}",
                prerequisites=[],  # Assume this prerequisite itself has no blockers
                parent_goal_id=goal.id,
                metadata={"original_goal": goal.description, "prerequisite": prereq}
            )
            # Check if the sub-goal itself is feasible
            sub_feasibility = self._check_feasibility(sub_goal)
            sub_goal.feasibility_score = sub_feasibility.score
            sub_goal.is_blocked = not sub_feasibility.is_feasible
            sub_goal.block_reason = sub_feasibility.reason if not sub_feasibility.is_feasible else None

            if sub_feasibility.is_feasible:
                sub_goals.append(sub_goal)
                logger.info(f"Created sub-goal {sub_goal.id} for prerequisite '{prereq}' (feasible).")
            else:
                logger.warning(f"Sub-goal {sub_goal.id} for prerequisite '{prereq}' is also blocked: {sub_feasibility.reason}")
                # Optionally, we could recursively decompose further, but limit to one level for now
                # Recursive decomposition could be added here if needed

        return sub_goals

    def get_next_goal(self) -> Optional[Goal]:
        """Get the next feasible goal from the queue."""
        while self.goal_queue:
            goal = self.goal_queue.pop(0)
            # Re-check feasibility in case conditions changed
            feasibility = self._check_feasibility(goal)
            goal.feasibility_score = feasibility.score
            if feasibility.is_feasible:
                return goal
            else:
                logger.info(f"Goal {goal.id} is no longer feasible. Attempting to decompose again.")
                decomposed = self._decompose_goal(goal, feasibility)
                if decomposed:
                    self.goal_queue.extend(decomposed)
                else:
                    self.failed_goals.append(goal)
        return None

    def complete_goal(self, goal: Goal) -> None:
        """Mark a goal as completed."""
        goal.is_blocked = False
        goal.feasibility_score = 1.0
        self.completed_goals.append(goal)
        logger.info(f"Goal {goal.id} completed.")

    def fail_goal(self, goal: Goal, reason: str) -> None:
        """Mark a goal as failed."""
        goal.is_blocked = True
        goal.block_reason = reason
        self.failed_goals.append(goal)
        logger.error(f"Goal {goal.id} failed: {reason}")

    def get_queue_status(self) -> Dict[str, Any]:
        """Get a summary of the goal queue status."""
        return {
            "queue_length": len(self.goal_queue),
            "completed": len(self.completed_goals),
            "failed": len(self.failed_goals),
            "average_feasibility": (
                sum(g.feasibility_score for g in self.goal_queue) / len(self.goal_queue)
                if self.goal_queue else 0.0
            ),
            "blocked_goals": [g.id for g in self.goal_queue if g.is_blocked]
        }