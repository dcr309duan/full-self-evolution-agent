"""Core orchestrator for integrating failure pattern mining into the evolution loop."""

from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
import logging

from .miner import FailurePatternMiner, FailurePattern
from ..evolution.goal_queue import GoalQueue, Goal, GoalPriority
from ..schema_alignment import SchemaValidator, SchemaConverter

logger = logging.getLogger(__name__)

# Threshold for automatic refactoring goal generation
PATTERN_FREQUENCY_THRESHOLD = 0.30


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

        self.state = OrchestrationState.IDLE

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