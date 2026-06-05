"""Core orchestrator for integrating failure pattern mining into the evolution loop."""

from typing import List, Optional, Dict, Any, Set
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
import logging

from .miner import FailurePatternMiner, FailurePattern
from ..evolution.goal_queue import GoalQueue, Goal, GoalPriority
from ..schema_alignment import SchemaValidator, SchemaConverter
from planner.dependency_graph import DependencyGraph

logger = logging.getLogger(__name__)

# Threshold for automatic refactoring goal generation
PATTERN_FREQUENCY_THRESHOLD = 0.30

# Maximum retry count for blocked goals
MAX_BLOCKED_RETRY_COUNT = 3


class OrchestrationState(Enum):
    """States for the orchestration loop."""
    IDLE = "idle"
    MUTATING = "mutating"
    MINING = "mining"
    REFACTORING = "refactoring"


@dataclass
class OrchestrationConfig:
    """Configuration for the orchestrator."""
    pattern_miner: FailurePatternMiner
    goal_queue: GoalQueue
    min_samples_for_pattern: int = 5
    auto_refactoring_enabled: bool = True
    max_refactoring_goals_per_cycle: int = 3
    schema_validator: Optional[SchemaValidator] = None
    schema_converter: Optional[SchemaConverter] = None


class EvolutionOrchestrator:
    """Integrates failure pattern mining into the evolution loop.

    After each mutation cycle, the miner is called to update pattern statistics.
    If a pattern exceeds the frequency threshold, a high-priority refactoring goal
    is automatically generated and injected into the goal queue.
    """

    def __init__(self, config: OrchestrationConfig):
        self.config = config
        self.state = OrchestrationState.IDLE
        self._patterns_seen_this_cycle: List[FailurePattern] = []
        self._refactoring_goals_generated: int = 0
        self._dependency_graph = DependencyGraph()
        self._pending_goals: List[Goal] = []
        self._blocked_goals: Dict[str, int] = {}  # goal_id -> retry_count
        self._completed_goals: Set[str] = set()  # set of completed goal IDs

    def after_mutation_cycle(self, mutation_results: List[dict]) -> None:
        """Called after each mutation cycle to mine patterns and generate goals.

        Args:
            mutation_results: List of mutation results from the evolution loop.
                Each result should contain at least 'success' and 'failure_data' keys.
        """
        self.state = OrchestrationState.MINING
        self._patterns_seen_this_cycle.clear()
        self._refactoring_goals_generated = 0

        # Extract failure data from mutation results
        failure_data_list = []
        for result in mutation_results:
            if not result.get('success', True):
                failure_data = result.get('failure_data')
                if failure_data:
                    # Validate and convert failure_data before processing
                    if self.config.schema_validator and self.config.schema_converter:
                        if not self.config.schema_validator.validate(failure_data):
                            logger.warning(
                                "Schema mismatch in failure_data: %s",
                                self.config.schema_validator.get_errors(failure_data)
                            )
                            failure_data = self.config.schema_converter.convert(failure_data)
                    failure_data_list.append(failure_data)

        if not failure_data_list:
            logger.debug("No failures to mine in this cycle.")
            self.state = OrchestrationState.IDLE
            return

        # Update pattern statistics with new failure data
        for failure_data in failure_data_list:
            patterns = self.config.pattern_miner.mine_patterns(failure_data)
            self._patterns_seen_this_cycle.extend(patterns)

        # Check for patterns exceeding threshold
        if self.config.auto_refactoring_enabled:
            self._check_and_generate_refactoring_goals()

        # Rebuild dependency graph from current capability list
        self._rebuild_dependency_graph()

        self.state = OrchestrationState.IDLE

    def _rebuild_dependency_graph(self) -> None:
        """Rebuild the dependency graph from the current capability list."""
        # Get current capabilities from the goal queue
        capabilities = self.config.goal_queue.get_capabilities()
        
        # Clear and rebuild the dependency graph
        self._dependency_graph.clear()
        for capability in capabilities:
            self._dependency_graph.add_capability(capability)
        
        logger.info("Dependency graph rebuilt with %d capabilities", len(capabilities))

    def execute_goals(self) -> None:
        """Execute goals respecting dependency constraints."""
        self.state = OrchestrationState.REFACTORING
        
        # Re-evaluate dependency graph after any goal completions
        self._re_evaluate_dependencies()
        
        # Get ready goals from the dependency graph
        ready_goals = self._dependency_graph.get_ready_goals()
        
        # Execute ready goals
        for goal in ready_goals:
            if goal.id not in self._completed_goals:
                logger.info("Executing ready goal: %s", goal.description)
                result = self.config.goal_queue.execute_goal(goal)
                
                if result.get('success', True):
                    self._completed_goals.add(goal.id)
                    # Re-evaluate dependencies after completion
                    self._re_evaluate_dependencies()
                else:
                    # Check if failure is due to missing dependencies
                    if self._is_dependency_failure(goal, result):
                        logger.info("Goal '%s' is BLOCKED due to missing dependencies", goal.description)
                        self._handle_blocked_goal(goal)
                    else:
                        logger.error("Goal '%s' FAILED: %s", goal.description, result.get('error', 'Unknown error'))
        
        # Move blocked goals to pending queue
        all_goals = self.config.goal_queue.get_all_goals()
        for goal in all_goals:
            if goal.id not in self._completed_goals and goal.id not in self._pending_goals:
                self._pending_goals.append(goal)
                logger.info("Goal moved to pending queue: %s", goal.description)
        
        # Log dependency status
        self._log_dependency_status()
        
        self.state = OrchestrationState.IDLE

    def _re_evaluate_dependencies(self) -> None:
        """Re-evaluate the dependency graph after goal completions."""
        # Update the dependency graph with completed goals
        for goal_id in self._completed_goals:
            self._dependency_graph.mark_goal_completed(goal_id)
        
        # Check if any blocked goals are now unblocked
        unblocked_goals = []
        for goal in self._pending_goals:
            if self._dependency_graph.is_goal_ready(goal):
                unblocked_goals.append(goal)
                logger.info("Goal '%s' is now unblocked", goal.description)
        
        # Remove unblocked goals from pending and reset their retry count
        for goal in unblocked_goals:
            self._pending_goals.remove(goal)
            if goal.id in self._blocked_goals:
                del self._blocked_goals[goal.id]

    def _is_dependency_failure(self, goal: Goal, result: Dict[str, Any]) -> bool:
        """Check if a goal failure is due to missing dependencies.
        
        Args:
            goal: The goal that failed
            result: The execution result
            
        Returns:
            True if the failure is due to missing dependencies
        """
        # Check if the error message indicates missing dependencies
        error_msg = result.get('error', '').lower()
        dependency_keywords = ['dependency', 'missing', 'unmet', 'prerequisite', 'required']
        
        if any(keyword in error_msg for keyword in dependency_keywords):
            return True
        
        # Check if the goal has dependencies that are not yet completed
        dependencies = self._dependency_graph.get_dependencies(goal)
        if dependencies:
            for dep in dependencies:
                if dep.id not in self._completed_goals:
                    return True
        
        return False

    def _handle_blocked_goal(self, goal: Goal) -> None:
        """Handle a blocked goal with retry logic.
        
        Args:
            goal: The blocked goal
        """
        goal_id = goal.id
        
        # Initialize or increment retry count
        if goal_id not in self._blocked_goals:
            self._blocked_goals[goal_id] = 0
        
        self._blocked_goals[goal_id] += 1
        retry_count = self._blocked_goals[goal_id]
        
        if retry_count > MAX_BLOCKED_RETRY_COUNT:
            logger.warning(
                "Goal '%s' has exceeded maximum retry count (%d). Marking as permanently blocked.",
                goal.description,
                MAX_BLOCKED_RETRY_COUNT
            )
            # Remove from pending and mark as failed
            if goal in self._pending_goals:
                self._pending_goals.remove(goal)
            self._completed_goals.add(goal_id)  # Mark as completed to avoid infinite loop
        else:
            logger.info(
                "Goal '%s' is blocked (retry %d/%d). Will retry on next cycle.",
                goal.description,
                retry_count,
                MAX_BLOCKED_RETRY_COUNT
            )

    def _log_dependency_status(self) -> None:
        """Log the current dependency status and any re-prioritization decisions."""
        logger.info("=== Dependency Status ===")
        logger.info("Pending goals count: %d", len(self._pending_goals))
        logger.info("Ready goals count: %d", len(self._dependency_graph.get_ready_goals()))
        logger.info("Completed goals count: %d", len(self._completed_goals))
        
        # Log blocked goals
        for goal in self._pending_goals:
            dependencies = self._dependency_graph.get_dependencies(goal)
            if dependencies:
                retry_count = self._blocked_goals.get(goal.id, 0)
                logger.info(
                    "Goal '%s' is blocked by dependencies: %s (retry %d/%d)",
                    goal.description,
                    [dep.description for dep in dependencies],
                    retry_count,
                    MAX_BLOCKED_RETRY_COUNT
                )
        
        # Log any re-prioritization decisions
        if self._pending_goals:
            logger.info("Re-prioritization decision: %d goals are pending due to unmet dependencies",
                       len(self._pending_goals))

    def _check_and_generate_refactoring_goals(self) -> None:
        """Check pattern frequencies and generate refactoring goals if threshold exceeded."""
        pattern_frequencies = self._compute_pattern_frequencies()

        for pattern, frequency in pattern_frequencies.items():
            if frequency >= PATTERN_FREQUENCY_THRESHOLD:
                if self._refactoring_goals_generated >= self.config.max_refactoring_goals_per_cycle:
                    logger.info(
                        "Reached max refactoring goals per cycle (%d). Skipping pattern: %s",
                        self.config.max_refactoring_goals_per_cycle,
                        pattern
                    )
                    break

                goal = self._create_refactoring_goal(pattern, frequency)
                # Validate and convert goal before adding to queue
                if self.config.schema_validator and self.config.schema_converter:
                    if not self.config.schema_validator.validate(goal):
                        logger.warning(
                            "Schema mismatch in goal: %s",
                            self.config.schema_validator.get_errors(goal)
                        )
                        goal = self.config.schema_converter.convert(goal)
                self.config.goal_queue.add_goal(goal)
                self._refactoring_goals_generated += 1

                logger.info(
                    "Generated high-priority refactoring goal for pattern '%s' (frequency: %.2f)",
                    pattern.description,
                    frequency
                )

    def _compute_pattern_frequencies(self) -> dict:
        """Compute frequency of each pattern seen this cycle.

        Returns:
            Dictionary mapping FailurePattern to its frequency (0.0 to 1.0).
        """
        if not self._patterns_seen_this_cycle:
            return {}

        pattern_counts = defaultdict(int)
        total_patterns = len(self._patterns_seen_this_cycle)

        for pattern in self._patterns_seen_this_cycle:
            pattern_counts[pattern] += 1

        return {
            pattern: count / total_patterns
            for pattern, count in pattern_counts.items()
        }

    def _create_refactoring_goal(self, pattern: FailurePattern, frequency: float) -> Goal:
        """Create a high-priority refactoring goal for a pattern.

        Args:
            pattern: The failure pattern that triggered the goal.
            frequency: The observed frequency of the pattern.

        Returns:
            A Goal instance with high priority and refactoring description.
        """
        description = (
            f"Auto-generated refactoring: Pattern '{pattern.description}' "
            f"observed at {frequency:.1%} frequency. "
            f"Suggested fix: {pattern.suggested_fix}"
        )

        return Goal(
            description=description,
            priority=GoalPriority.HIGH,
            metadata={
                'source': 'failure_pattern_miner',
                'pattern_id': pattern.id,
                'pattern_description': pattern.description,
                'frequency': frequency,
                'suggested_fix': pattern.suggested_fix,
            }
        )

    def get_state(self) -> OrchestrationState:
        """Get the current state of the orchestrator."""
        return self.state

    def reset_cycle(self) -> None:
        """Reset cycle-specific tracking data."""
        self._patterns_seen_this_cycle.clear()
        self._refactoring_goals_generated = 0
        self._pending_goals.clear()
        self._blocked_goals.clear()
        self._completed_goals.clear()