from typing import List, Dict, Optional, Any
from evolution_engine.feasibility_estimator import FeasibilityEstimator
from evolution_engine.failure_analysis import FailureAnalyzer
from evolution_engine.goal_types import GoalType, Goal
from evolution_engine.capability_fitness_tracker import CapabilityFitnessTracker
import logging
from queue import PriorityQueue

logger = logging.getLogger(__name__)

class GoalGenerator:
    """
    Generates goals with dependency-aware feasibility estimation.
    Integrates feasibility checks before yielding goals and implements
    a feedback loop to deprioritize blocked goal types.
    Supports injection of externally generated goals via a priority queue.
    Tracks capability dependencies for each generated goal.
    """

    def __init__(self, feasibility_estimator: FeasibilityEstimator,
                 failure_analyzer: FailureAnalyzer,
                 capability_fitness_tracker: CapabilityFitnessTracker,
                 deprioritization_threshold: int = 3):
        self.feasibility_estimator = feasibility_estimator
        self.failure_analyzer = failure_analyzer
        self.capability_fitness_tracker = capability_fitness_tracker
        self.deprioritization_threshold = deprioritization_threshold
        self.blocked_goal_counts: Dict[GoalType, int] = {}
        self.deprioritized_goal_types: set = set()
        self.goal_candidates: List[Goal] = []
        self.blocked_categories: set = set()
        # Define the canonical goal schema version
        self.schema_version = "1.0"
        # Priority queue for injected goals (lower number = higher priority)
        self.injected_goals: PriorityQueue = PriorityQueue()
        # Track capabilities that are marked for deprecation
        self.deprecated_capabilities: set = set()

    def set_deprecated_capabilities(self, deprecated_capabilities: set) -> None:
        """Set the set of capability IDs that are marked for deprecation."""
        self.deprecated_capabilities = deprecated_capabilities
        logger.info(f"Deprecated capabilities updated: {deprecated_capabilities}")

    def inject_goal(self, goal_dict: Dict[str, Any]) -> None:
        """
        Inject an externally generated goal into the priority queue.
        The goal_dict should contain at minimum 'goal_type', 'description', and 'priority'.
        A default schema_version is added if not present.
        The goal is validated before being queued.
        """
        # Ensure schema_version is present
        if 'schema_version' not in goal_dict:
            goal_dict['schema_version'] = self.schema_version
        
        # Create a Goal object from the dictionary
        try:
            goal = Goal(
                goal_type=GoalType(goal_dict['goal_type']),
                description=goal_dict['description'],
                priority=goal_dict['priority'],
                schema_version=goal_dict.get('schema_version', self.schema_version)
            )
        except (KeyError, ValueError) as e:
            logger.error(f"Invalid injected goal dict: {e}")
            return
        
        # Validate the goal before queuing
        if not self._validate_goal(goal):
            logger.warning(f"Injected goal failed validation and was not queued: {goal}")
            return
        
        # Determine priority for the queue (lower number = higher priority)
        priority_map = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3}
        queue_priority = priority_map.get(goal.priority, 4)
        
        # Add to priority queue
        self.injected_goals.put((queue_priority, goal))
        logger.info(f"Injected goal queued: {goal.goal_type} - {goal.description}")

    def add_goal_candidates(self, goals: List[Goal]) -> None:
        """Add a list of candidate goals to the generator."""
        self.goal_candidates.extend(goals)

    def set_blocked_categories(self, blocked_categories: set) -> None:
        """Set the blocked categories from meta_monitor."""
        self.blocked_categories = blocked_categories

    def _get_required_capabilities(self, goal: Goal) -> List[str]:
        """
        Determine which capabilities are required to achieve a given goal.
        This is a simplified implementation - in production this would use
        a more sophisticated mapping based on goal type and context.
        """
        # Map goal types to required capabilities
        capability_map = {
            GoalType.ROOT_CAUSE_ANALYSIS: ['analytics', 'data_mining'],
            GoalType.PERFORMANCE_OPTIMIZATION: ['profiling', 'optimization'],
            GoalType.SECURITY_ENHANCEMENT: ['vulnerability_scanning', 'encryption'],
            GoalType.SCALABILITY_IMPROVEMENT: ['load_testing', 'distributed_systems'],
            GoalType.RELIABILITY_IMPROVEMENT: ['monitoring', 'fault_tolerance'],
            GoalType.FEATURE_DEVELOPMENT: ['development', 'testing'],
            GoalType.REFACTORING: ['code_analysis', 'refactoring_tools'],
            GoalType.DOCUMENTATION: ['documentation_generation', 'knowledge_base'],
            GoalType.TESTING: ['test_automation', 'coverage_analysis'],
            GoalType.DEPLOYMENT: ['ci_cd', 'containerization'],
            GoalType.MONITORING: ['metrics_collection', 'alerting'],
            GoalType.BACKUP: ['backup_systems', 'recovery'],
            GoalType.COMPLIANCE: ['audit_tools', 'policy_enforcement'],
        }
        
        # Get capabilities for this goal type, or return empty list if unknown
        return capability_map.get(goal.goal_type, [])

    def _check_deprecated_capabilities(self, required_capabilities: List[str]) -> bool:
        """
        Check if any of the required capabilities are marked for deprecation.
        Returns True if the goal should be excluded (has deprecated capabilities).
        """
        for cap_id in required_capabilities:
            if cap_id in self.deprecated_capabilities:
                logger.warning(f"Goal requires deprecated capability {cap_id}, excluding goal")
                return True
        return False

    def generate_goals(self) -> List[Goal]:
        """
        Generate goals by first emitting any injected goals from the priority queue,
        then filtering candidates through feasibility estimation.
        Deprioritizes goal types that are repeatedly blocked.
        Respects blocked categories by generating root_cause_analysis goals instead.
        Records capability dependencies for each generated goal.
        Excludes goals that require deprecated capabilities.
        Returns a list of feasible goals with schema_version included.
        """
        feasible_goals = []
        
        # First, process all injected goals from the priority queue
        while not self.injected_goals.empty():
            _, injected_goal = self.injected_goals.get()
            
            # Check if injected goal requires deprecated capabilities
            required_caps = self._get_required_capabilities(injected_goal)
            if self._check_deprecated_capabilities(required_caps):
                continue
            
            # Injected goals bypass feasibility checks but still respect blocked categories
            if injected_goal.goal_type in self.blocked_categories:
                # Generate root_cause_analysis goal instead
                root_cause_goal = Goal(
                    goal_type=GoalType.ROOT_CAUSE_ANALYSIS,
                    description=f"Root cause analysis for blocked category: {injected_goal.goal_type}",
                    priority='critical',
                    schema_version=self.schema_version
                )
                feasible_goals.append(root_cause_goal)
                # Register capability usage for the root cause goal
                root_cause_caps = self._get_required_capabilities(root_cause_goal)
                self.capability_fitness_tracker.register_goal_capability_usage(
                    root_cause_goal.id, root_cause_caps
                )
            else:
                feasible_goals.append(injected_goal)
                # Register capability usage for the injected goal
                self.capability_fitness_tracker.register_goal_capability_usage(
                    injected_goal.id, required_caps
                )
        
        # Then process regular goal candidates
        for goal in self.goal_candidates:
            # Check if goal requires deprecated capabilities
            required_caps = self._get_required_capabilities(goal)
            if self._check_deprecated_capabilities(required_caps):
                continue
            
            # Check if goal's category is blocked
            if goal.goal_type in self.blocked_categories:
                # Generate root_cause_analysis goal instead
                root_cause_goal = Goal(
                    goal_type=GoalType.ROOT_CAUSE_ANALYSIS,
                    description=f"Root cause analysis for blocked category: {goal.goal_type}",
                    priority='critical',
                    schema_version=self.schema_version
                )
                feasible_goals.append(root_cause_goal)
                # Register capability usage for the root cause goal
                root_cause_caps = self._get_required_capabilities(root_cause_goal)
                self.capability_fitness_tracker.register_goal_capability_usage(
                    root_cause_goal.id, root_cause_caps
                )
                continue

            if goal.goal_type in self.deprioritized_goal_types:
                logger.info(f"Skipping deprioritized goal type: {goal.goal_type}")
                continue

            if self.feasibility_estimator.is_feasible(goal):
                feasible_goals.append(goal)
                # Register capability usage for the feasible goal
                self.capability_fitness_tracker.register_goal_capability_usage(
                    goal.id, required_caps
                )
                self._reset_blocked_count(goal.goal_type)
            else:
                self._handle_blocked_goal(goal)

        # Add schema_version to each feasible goal (if not already set)
        for goal in feasible_goals:
            if not hasattr(goal, 'schema_version') or not goal.schema_version:
                goal.schema_version = self.schema_version

        # Self-validate each goal against the canonical schema
        validated_goals = []
        for goal in feasible_goals:
            if self._validate_goal(goal):
                validated_goals.append(goal)
            else:
                logger.warning(f"Goal {goal.goal_type} failed schema validation and was removed")

        # Clear processed candidates
        self.goal_candidates = []
        return validated_goals

    def _validate_goal(self, goal: Goal) -> bool:
        """
        Validate a goal against the canonical goal schema.
        Returns True if valid, False otherwise.
        """
        # Check required fields
        if not hasattr(goal, 'goal_type') or goal.goal_type is None:
            logger.error("Goal missing required field: goal_type")
            return False
        
        if not hasattr(goal, 'description') or not goal.description:
            logger.error("Goal missing required field: description")
            return False
        
        if not hasattr(goal, 'priority') or not goal.priority:
            logger.error("Goal missing required field: priority")
            return False
        
        if not hasattr(goal, 'schema_version') or not goal.schema_version:
            logger.error("Goal missing required field: schema_version")
            return False
        
        # Validate goal_type is a valid GoalType enum
        if not isinstance(goal.goal_type, GoalType):
            logger.error(f"Invalid goal_type: {goal.goal_type}")
            return False
        
        # Validate priority is one of the allowed values
        valid_priorities = ['low', 'medium', 'high', 'critical']
        if goal.priority not in valid_priorities:
            logger.error(f"Invalid priority: {goal.priority}")
            return False
        
        # Validate schema_version matches the expected version
        if goal.schema_version != self.schema_version:
            logger.error(f"Schema version mismatch: expected {self.schema_version}, got {goal.schema_version}")
            return False
        
        return True

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