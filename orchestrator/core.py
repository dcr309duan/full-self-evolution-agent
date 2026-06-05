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
        # Self-repair monitoring state
        self._strategy_switch_count: int = 0
        self._strategy_effectiveness: Dict[str, Dict[str, Dict[str, float]]] = {}  # strategy -> target -> metrics
        self._exhausted_targets: Set[str] = set()  # targets that have exhausted all strategies
        self._knowledge_gaps: List[Dict[str, Any]] = []  # knowledge gap entries
        # Store latest reflection_parser output for schema validation
        self._latest_reflection_output: Optional[Dict[str, Any]] = None

    def set_reflection_output(self, output: Dict[str, Any]) -> None:
        """Set the latest reflection_parser output for schema validation.

        Args:
            output: The latest reflection_parser output.
        """
        self._latest_reflection_output = output

    def _validate_schema_alignment(self, data: Dict[str, Any]) -> bool:
        """Validate schema alignment using the latest reflection_parser output.

        Args:
            data: The data to validate.

        Returns:
            True if validation passes, False otherwise.
        """
        if not self.config.schema_validator or not self._latest_reflection_output:
            return True  # No validation configured or no reflection output available

        try:
            # Use the reflection_parser output to validate schema alignment
            is_valid = self.config.schema_validator.validate_alignment(
                data, self._latest_reflection_output
            )
            if not is_valid:
                errors = self.config.schema_validator.get_errors(data)
                logger.error(
                    "Schema alignment validation failed for data: %s. Errors: %s",
                    data.get('id', 'unknown'),
                    errors
                )
            return is_valid
        except Exception as e:
            logger.error("Error during schema alignment validation: %s", str(e))
            return False

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

        # Self-repair monitoring: check for strategy switches
        self._monitor_strategy_switches(mutation_results)

        # Self-repair monitoring: log strategy effectiveness metrics
        self._log_strategy_effectiveness(mutation_results)

        # Self-repair monitoring: check for exhausted strategies
        self._check_exhausted_strategies(mutation_results)

        self.state = OrchestrationState.IDLE

    def _monitor_strategy_switches(self, mutation_results: List[dict]) -> None:
        """Monitor and track strategy switches that occurred during mutation cycle.

        Args:
            mutation_results: List of mutation results from the evolution loop.
        """
        strategy_switches = 0
        for result in mutation_results:
            if result.get('strategy_switch', False):
                strategy_switches += 1
                logger.info("Strategy switch detected in mutation result: %s", result.get('id', 'unknown'))

        if strategy_switches > 0:
            self._strategy_switch_count += strategy_switches
            logger.info("Total strategy switches this cycle: %d (cumulative: %d)", 
                       strategy_switches, self._strategy_switch_count)

    def _log_strategy_effectiveness(self, mutation_results: List[dict]) -> None:
        """Log and track strategy effectiveness metrics per strategy per target.

        Args:
            mutation_results: List of mutation results from the evolution loop.
        """
        for result in mutation_results:
            strategy = result.get('strategy', 'unknown')
            target = result.get('target', 'unknown')
            success = result.get('success', False)
            
            # Initialize nested dictionaries if not present
            if strategy not in self._strategy_effectiveness:
                self._strategy_effectiveness[strategy] = {}
            if target not in self._strategy_effectiveness[strategy]:
                self._strategy_effectiveness[strategy][target] = {
                    'attempts': 0,
                    'successes': 0,
                    'failures': 0,
                    'success_rate': 0.0
                }
            
            # Update metrics
            metrics = self._strategy_effectiveness[strategy][target]
            metrics['attempts'] += 1
            if success:
                metrics['successes'] += 1
            else:
                metrics['failures'] += 1
            
            # Calculate success rate
            if metrics['attempts'] > 0:
                metrics['success_rate'] = metrics['successes'] / metrics['attempts']
            
            logger.debug(
                "Strategy effectiveness: strategy='%s', target='%s', attempts=%d, successes=%d, success_rate=%.2f",
                strategy, target, metrics['attempts'], metrics['successes'], metrics['success_rate']
            )

    def _check_exhausted_strategies(self, mutation_results: List[dict]) -> None:
        """Check if any target has exhausted all available strategies.

        Args:
            mutation_results: List of mutation results from the evolution loop.
        """
        # Collect all targets and their used strategies
        target_strategies: Dict[str, Set[str]] = defaultdict(set)
        for result in mutation_results:
            target = result.get('target', 'unknown')
            strategy = result.get('strategy', 'unknown')
            target_strategies[target].add(strategy)

        # Get all available strategies from the system
        all_strategies = self._get_available_strategies()

        # Check each target for exhaustion
        for target, used_strategies in target_strategies.items():
            if target not in self._exhausted_targets:
                # Check if all strategies have been tried on this target
                if used_strategies == all_strategies:
                    self._exhausted_targets.add(target)
                    logger.warning(
                        "Target '%s' has exhausted all available strategies. Marking for manual intervention.",
                        target
                    )
                    
                    # Generate knowledge gap entry
                    gap_entry = {
                        'target': target,
                        'type': 'strategy_exhaustion',
                        'description': f"Target '{target}' has exhausted all {len(all_strategies)} available strategies without success",
                        'tried_strategies': list(used_strategies),
                        'timestamp': self._get_current_timestamp(),
                        'severity': 'high'
                    }
                    self._knowledge_gaps.append(gap_entry)
                    
                    # Mark target for manual intervention
                    self._mark_target_for_intervention(target, gap_entry)

    def _get_available_strategies(self) -> Set[str]:
        """Get the set of all available strategies in the system.

        Returns:
            Set of strategy names.
        """
        # This would typically come from configuration or system registry
        # For now, we derive it from the strategy_effectiveness tracking
        return set(self._strategy_effectiveness.keys())

    def _get_current_timestamp(self) -> str:
        """Get current timestamp for logging purposes.

        Returns:
            Current timestamp as string.
        """
        from datetime import datetime
        return datetime.now().isoformat()

    def _mark_target_for_intervention(self, target: str, gap_entry: Dict[str, Any]) -> None:
        """Mark a target as requiring manual intervention and log the knowledge gap.

        Args:
            target: The target that requires intervention.
            gap_entry: The knowledge gap entry describing the issue.
        """
        logger.warning(
            "MANUAL INTERVENTION REQUIRED: Target '%s' has exhausted all strategies. "
            "Knowledge gap entry generated: %s",
            target,
            gap_entry['description']
        )
        
        # Store the intervention requirement for external systems to query
        if not hasattr(self, '_intervention_required'):
            self._intervention_required = {}
        self._intervention_required[target] = {
            'timestamp': gap_entry['timestamp'],
            'gap_entry': gap_entry,
            'resolved': False
        }

    def get_strategy_switch_count(self) -> int:
        """Get the total number of strategy switches detected.

        Returns:
            Total strategy switch count.
        """
        return self._strategy_switch_count

    def get_strategy_effectiveness(self) -> Dict[str, Dict[str, Dict[str, float]]]:
        """Get the strategy effectiveness metrics.

        Returns:
            Dictionary of strategy effectiveness metrics.
        """
        return self._strategy_effectiveness

    def get_exhausted_targets(self) -> Set[str]:
        """Get the set of targets that have exhausted all strategies.

        Returns:
            Set of exhausted target names.
        """
        return self._exhausted_targets

    def get_knowledge_gaps(self) -> List[Dict[str, Any]]:
        """Get the list of knowledge gap entries.

        Returns:
            List of knowledge gap dictionaries.
        """
        return self._knowledge_gaps

    def get_intervention_required(self) -> Dict[str, Dict[str, Any]]:
        """Get the targets requiring manual intervention.

        Returns:
            Dictionary of targets requiring intervention with details.
        """
        return getattr(self, '_intervention_required', {})

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
                
                # Validate schema alignment before mutation
                if not self._validate_schema_alignment(goal.to_dict()):
                    logger.error(
                        "Schema alignment validation failed for goal '%s'. Skipping mutation cycle.",
                        goal.description
                    )
                    continue
                
                result = self.config.goal_queue.execute_goal(goal)
                
                if result.get('success', True):
                    # Re-validate schema integrity after successful mutation
                    if not self._validate_schema_alignment(result):
                        logger.warning(
                            "Schema integrity check failed after successful mutation for goal '%s'. "
                            "Rolling back or logging diagnostic.",
                            goal.description
                        )
                        # Log detailed diagnostic information
                        diagnostic = {
                            'goal_id': goal.id,
                            'goal_description': goal.description,
                            'result': result,
                            'validation_errors': self.config.schema_validator.get_errors(result) if self.config.schema_validator else []
                        }
                        logger.error("Schema integrity diagnostic: %s", diagnostic)
                    else:
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
        # Reset self-repair monitoring state
        self._strategy_switch_count = 0
        self._strategy_effectiveness.clear()
        self._exhausted_targets.clear()
        self._knowledge_gaps.clear()
        if hasattr(self, '_intervention_required'):
            del self._intervention_required