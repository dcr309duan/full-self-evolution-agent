"""Orchestrator module integrating feasibility estimation into goal execution flow."""

from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
import logging

from goal_feasibility_estimator import GoalFeasibilityEstimator

logger = logging.getLogger(__name__)

@dataclass
class Goal:
    """Represents a goal to be executed."""
    id: str
    description: str
    complexity: float = 1.0  # Default complexity
    sub_goals: List['Goal'] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

class Orchestrator:
    """Orchestrates goal execution with feasibility checking."""

    def __init__(self, capabilities: List[str], history: List[Dict[str, Any]]):
        """
        Initialize the orchestrator.

        Args:
            capabilities: List of available capabilities
            history: Execution history for context
        """
        self.estimator = GoalFeasibilityEstimator()
        self.capabilities = capabilities
        self.history = history
        self.execution_queue: List[Goal] = []
        self.blocked_goals: List[Tuple[Goal, str]] = []  # (goal, reason)

    def execute_with_feasibility_check(self, goal: Goal) -> bool:
        """
        Execute a goal after performing feasibility check.
        Returns True if goal was executed, False if blocked or adjusted.

        Args:
            goal: The goal to execute

        Returns:
            bool: Whether the goal was successfully executed
        """
        probability = self.estimator.estimate_success_probability(
            goal, self.capabilities, self.history
        )

        logger.info(f"Goal '{goal.id}' feasibility probability: {probability:.2f}")

        if probability < 0.2:
            reason = f"Feasibility probability {probability:.2f} below threshold 0.2"
            logger.warning(f"Blocking goal '{goal.id}': {reason}")
            self.blocked_goals.append((goal, reason))
            return False

        elif 0.2 <= probability < 0.5:
            logger.info(f"Adjusting goal '{goal.id}' due to low feasibility ({probability:.2f})")
            adjusted_goal = self._adjust_goal_complexity(goal)
            return self._execute_goal(adjusted_goal)

        else:
            logger.info(f"Executing goal '{goal.id}' with high feasibility ({probability:.2f})")
            return self._execute_goal(goal)

    def _adjust_goal_complexity(self, goal: Goal) -> Goal:
        """
        Adjust goal complexity by splitting into sub-goals or reducing scope.

        Args:
            goal: The goal to adjust

        Returns:
            Goal: Adjusted goal with reduced complexity
        """
        # Split into sub-goals if complexity is high
        if goal.complexity > 0.7:
            sub_goals = self._split_goal(goal)
            goal.sub_goals = sub_goals
            goal.complexity = 0.5  # Reduce complexity after splitting
            logger.info(f"Split goal '{goal.id}' into {len(sub_goals)} sub-goals")
        else:
            # Reduce scope by lowering complexity
            goal.complexity = min(goal.complexity * 0.7, 0.5)
            logger.info(f"Reduced complexity of goal '{goal.id}' to {goal.complexity:.2f}")

        return goal

    def _split_goal(self, goal: Goal) -> List[Goal]:
        """
        Split a complex goal into smaller sub-goals.

        Args:
            goal: The goal to split

        Returns:
            List[Goal]: List of sub-goals
        """
        # Simple splitting logic - can be enhanced based on goal structure
        sub_goals = []
        num_sub_goals = max(2, int(goal.complexity * 4))  # More sub-goals for higher complexity

        for i in range(num_sub_goals):
            sub_goal = Goal(
                id=f"{goal.id}_sub_{i}",
                description=f"Sub-goal {i+1} of {goal.description}",
                complexity=goal.complexity / num_sub_goals,
                metadata={"parent_goal_id": goal.id}
            )
            sub_goals.append(sub_goal)

        return sub_goals

    def _execute_goal(self, goal: Goal) -> bool:
        """
        Execute the actual goal logic.
        This is a placeholder for the real execution logic.

        Args:
            goal: The goal to execute

        Returns:
            bool: Whether execution was successful
        """
        # Placeholder for actual execution logic
        logger.info(f"Executing goal '{goal.id}': {goal.description}")

        # Execute sub-goals if they exist
        if goal.sub_goals:
            for sub_goal in goal.sub_goals:
                success = self._execute_goal(sub_goal)
                if not success:
                    logger.error(f"Sub-goal '{sub_goal.id}' failed")
                    return False

        # Update history with execution result
        self.history.append({
            "goal_id": goal.id,
            "complexity": goal.complexity,
            "status": "executed"
        })

        return True

    def add_to_queue(self, goal: Goal) -> None:
        """
        Add a goal to the execution queue after feasibility estimation.
        If blocked, log the decision and optionally trigger a capability acquisition sub-goal.
        The estimator's decision is recorded in the task metadata for future analysis.
        """
        # Perform feasibility estimation before enqueuing
        probability = self.estimator.estimate_success_probability(
            goal, self.capabilities, self.history
        )
        
        # Record the estimator's decision in the goal's metadata
        goal.metadata["feasibility_probability"] = probability
        goal.metadata["feasibility_threshold"] = 0.2
        goal.metadata["feasibility_decision"] = "blocked" if probability < 0.2 else "allowed"
        
        if probability < 0.2:
            reason = f"Feasibility probability {probability:.2f} below threshold 0.2"
            logger.warning(f"Blocking goal '{goal.id}' from queue: {reason}")
            self.blocked_goals.append((goal, reason))
            
            # Optionally trigger a capability acquisition sub-goal
            acquisition_goal = Goal(
                id=f"{goal.id}_capability_acquisition",
                description=f"Acquire capabilities needed for {goal.description}",
                complexity=0.3,
                metadata={
                    "parent_goal_id": goal.id,
                    "type": "capability_acquisition",
                    "original_feasibility": probability
                }
            )
            logger.info(f"Triggering capability acquisition sub-goal '{acquisition_goal.id}' for blocked goal '{goal.id}'")
            self.execution_queue.append(acquisition_goal)
        else:
            logger.info(f"Adding goal '{goal.id}' to execution queue with feasibility {probability:.2f}")
            self.execution_queue.append(goal)

    def process_queue(self) -> None:
        """Process all goals in the execution queue."""
        while self.execution_queue:
            goal = self.execution_queue.pop(0)
            self.execute_with_feasibility_check(goal)

    def get_blocked_goals(self) -> List[Tuple[Goal, str]]:
        """Get list of blocked goals with reasons."""
        return self.blocked_goals

    def clear_blocked_goals(self) -> None:
        """Clear the list of blocked goals."""
        self.blocked_goals.clear()
        logger.info("Cleared blocked goals list")

    def _needs_multi_file_analysis(self, goal: Goal) -> bool:
        """
        Check if a goal requires multi-file analysis based on its description and metadata.

        Args:
            goal: The goal to check

        Returns:
            bool: True if multi-file analysis is needed
        """
        # Check if the goal description mentions multiple files or cross-file changes
        multi_file_keywords = ["multiple files", "cross-file", "across files", "refactor", "restructure"]
        description_lower = goal.description.lower()
        
        if any(keyword in description_lower for keyword in multi_file_keywords):
            return True
        
        # Check metadata for explicit multi-file flag
        if goal.metadata.get("multi_file", False):
            return True
        
        # Check if goal has sub-goals that might require multi-file analysis
        if goal.sub_goals:
            for sub_goal in goal.sub_goals:
                if self._needs_multi_file_analysis(sub_goal):
                    return True
        
        return False

    def _execute_multi_file_refactoring(self, goal: Goal) -> bool:
        """
        Execute a multi-file refactoring goal.

        Args:
            goal: The multi-file refactoring goal to execute

        Returns:
            bool: Whether the refactoring was successful
        """
        logger.info(f"Executing multi-file refactoring for goal '{goal.id}': {goal.description}")
        
        # Create multi-file refactoring sub-goals
        refactoring_sub_goals = [
            Goal(
                id=f"{goal.id}_analyze",
                description=f"Analyze files for {goal.description}",
                complexity=0.3,
                metadata={"type": "multi_file_analysis", "parent_goal_id": goal.id}
            ),
            Goal(
                id=f"{goal.id}_refactor",
                description=f"Perform refactoring for {goal.description}",
                complexity=0.5,
                metadata={"type": "multi_file_refactoring", "parent_goal_id": goal.id}
            ),
            Goal(
                id=f"{goal.id}_verify",
                description=f"Verify refactoring results for {goal.description}",
                complexity=0.2,
                metadata={"type": "verification", "parent_goal_id": goal.id}
            )
        ]
        
        # Execute the sub-goals
        for sub_goal in refactoring_sub_goals:
            success = self._execute_goal(sub_goal)
            if not success:
                logger.error(f"Multi-file refactoring sub-goal '{sub_goal.id}' failed")
                return False
        
        # Update history with multi-file refactoring result
        self.history.append({
            "goal_id": goal.id,
            "type": "multi_file_refactoring",
            "status": "completed",
            "sub_goals": [sg.id for sg in refactoring_sub_goals]
        })
        
        return True

    def execute_with_feasibility_check(self, goal: Goal) -> bool:
        """
        Execute a goal after performing feasibility check.
        Returns True if goal was executed, False if blocked or adjusted.

        Args:
            goal: The goal to execute

        Returns:
            bool: Whether the goal was successfully executed
        """
        # Check if multi-file analysis is needed
        if self._needs_multi_file_analysis(goal):
            logger.info(f"Goal '{goal.id}' requires multi-file analysis")
            
            # Check if multi_file_refactoring capability is available
            if "multi_file_refactoring" in self.capabilities:
                logger.info(f"Using multi-file refactoring for goal '{goal.id}'")
                return self._execute_multi_file_refactoring(goal)
            else:
                logger.warning(f"Multi-file refactoring capability not available for goal '{goal.id}'")
                # Fall back to regular execution
                return self._execute_goal(goal)
        
        probability = self.estimator.estimate_success_probability(
            goal, self.capabilities, self.history
        )

        logger.info(f"Goal '{goal.id}' feasibility probability: {probability:.2f}")

        if probability < 0.2:
            reason = f"Feasibility probability {probability:.2f} below threshold 0.2"
            logger.warning(f"Blocking goal '{goal.id}': {reason}")
            self.blocked_goals.append((goal, reason))
            return False

        elif 0.2 <= probability < 0.5:
            logger.info(f"Adjusting goal '{goal.id}' due to low feasibility ({probability:.2f})")
            adjusted_goal = self._adjust_goal_complexity(goal)
            return self._execute_goal(adjusted_goal)

        else:
            logger.info(f"Executing goal '{goal.id}' with high feasibility ({probability:.2f})")
            return self._execute_goal(goal)

    def add_to_queue(self, goal: Goal) -> None:
        """
        Add a goal to the execution queue after feasibility estimation.
        If blocked, log the decision and optionally trigger a capability acquisition sub-goal.
        The estimator's decision is recorded in the task metadata for future analysis.
        """
        # Check if multi-file analysis is needed
        if self._needs_multi_file_analysis(goal):
            logger.info(f"Goal '{goal.id}' requires multi-file analysis")
            goal.metadata["multi_file_required"] = True
            
            # Check if multi_file_refactoring capability is available
            if "multi_file_refactoring" not in self.capabilities:
                logger.warning(f"Multi-file refactoring capability not available for goal '{goal.id}'")
                # Add capability acquisition sub-goal
                acquisition_goal = Goal(
                    id=f"{goal.id}_multi_file_capability_acquisition",
                    description=f"Acquire multi-file refactoring capability for {goal.description}",
                    complexity=0.4,
                    metadata={
                        "parent_goal_id": goal.id,
                        "type": "capability_acquisition",
                        "target_capability": "multi_file_refactoring"
                    }
                )
                logger.info(f"Triggering multi-file capability acquisition sub-goal '{acquisition_goal.id}'")
                self.execution_queue.append(acquisition_goal)
        
        # Perform feasibility estimation before enqueuing
        probability = self.estimator.estimate_success_probability(
            goal, self.capabilities, self.history
        )
        
        # Record the estimator's decision in the goal's metadata
        goal.metadata["feasibility_probability"] = probability
        goal.metadata["feasibility_threshold"] = 0.2
        goal.metadata["feasibility_decision"] = "blocked" if probability < 0.2 else "allowed"
        
        if probability < 0.2:
            reason = f"Feasibility probability {probability:.2f} below threshold 0.2"
            logger.warning(f"Blocking goal '{goal.id}' from queue: {reason}")
            self.blocked_goals.append((goal, reason))
            
            # Optionally trigger a capability acquisition sub-goal
            acquisition_goal = Goal(
                id=f"{goal.id}_capability_acquisition",
                description=f"Acquire capabilities needed for {goal.description}",
                complexity=0.3,
                metadata={
                    "parent_goal_id": goal.id,
                    "type": "capability_acquisition",
                    "original_feasibility": probability
                }
            )
            logger.info(f"Triggering capability acquisition sub-goal '{acquisition_goal.id}' for blocked goal '{goal.id}'")
            self.execution_queue.append(acquisition_goal)
        else:
            logger.info(f"Adding goal '{goal.id}' to execution queue with feasibility {probability:.2f}")
            self.execution_queue.append(goal)