"""Self-healing retry loop module.

Intercepts goal failures, analyzes them, generates alternative strategies,
and enqueues retries with a maximum retry count per failure pattern.
"""

import logging
from typing import Any, Callable, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from collections import defaultdict
from enum import Enum, auto

logger = logging.getLogger(__name__)


class FailureSeverity(Enum):
    """Severity classification for failures."""
    LOW = auto()
    MEDIUM = auto()
    HIGH = auto()
    CRITICAL = auto()


@dataclass
class FailurePattern:
    """Represents a pattern of failure for tracking retries."""
    goal_type: str
    failure_signature: str  # e.g., "timeout", "value_error", "connection_refused"
    retry_count: int = 0
    last_failure_context: Optional[Dict[str, Any]] = None


@dataclass
class RetryGoal:
    """A sub-goal or alternative strategy for retry."""
    original_goal_id: str
    goal_type: str
    strategy: str  # e.g., "retry_same", "alternative_approach", "decomposed_subgoal"
    parameters: Dict[str, Any]
    priority: int = 0  # Higher = more urgent


class SelfHealingRetryLoop:
    """Main self-healing retry loop orchestrator."""

    MAX_RETRIES_PER_PATTERN = 3

    def __init__(
        self,
        failure_analyzer: Callable[[Dict[str, Any]], Tuple[str, FailureSeverity, str]],
        reflection_parser: Callable[[Dict[str, Any]], Dict[str, Any]],
        goal_generator: Callable[[str, Dict[str, Any], str], List[RetryGoal]],
        orchestrator_enqueue: Callable[[RetryGoal], None],
    ):
        """
        Initialize the retry loop.

        Args:
            failure_analyzer: Function that takes failure context and returns
                (goal_type, severity, failure_signature).
            reflection_parser: Function that takes failure context and returns
                parsed reflection data.
            goal_generator: Function that takes (goal_type, context, strategy) and
                returns a list of RetryGoal objects.
            orchestrator_enqueue: Function to enqueue a RetryGoal for execution.
        """
        self._failure_analyzer = failure_analyzer
        self._reflection_parser = reflection_parser
        self._goal_generator = goal_generator
        self._orchestrator_enqueue = orchestrator_enqueue
        self._failure_patterns: Dict[str, FailurePattern] = {}
        self._retry_queue: List[RetryGoal] = []
        self._active_retries: Dict[str, int] = defaultdict(int)  # goal_id -> retry count

    def handle_goal_failure(self, goal_id: str, failure_context: Dict[str, Any]) -> bool:
        """
        Intercept a goal failure and attempt self-healing.

        Args:
            goal_id: The ID of the failed goal.
            failure_context: Contextual information about the failure.

        Returns:
            True if retry was enqueued, False if max retries exceeded or no recovery possible.
        """
        logger.info(f"Handling failure for goal {goal_id}")

        # Step 1: Analyze failure
        goal_type, severity, failure_signature = self._failure_analyzer(failure_context)
        pattern_key = f"{goal_type}:{failure_signature}"

        # Step 2: Update or create failure pattern
        if pattern_key not in self._failure_patterns:
            self._failure_patterns[pattern_key] = FailurePattern(
                goal_type=goal_type,
                failure_signature=failure_signature,
                last_failure_context=failure_context,
            )
        pattern = self._failure_patterns[pattern_key]
        pattern.retry_count += 1
        pattern.last_failure_context = failure_context

        # Step 3: Check retry limit
        if pattern.retry_count > self.MAX_RETRIES_PER_PATTERN:
            logger.warning(
                f"Max retries ({self.MAX_RETRIES_PER_PATTERN}) exceeded for pattern '{pattern_key}'. "
                f"Goal {goal_id} will not be retried."
            )
            return False

        # Step 4: Parse reflection
        try:
            reflection_data = self._reflection_parser(failure_context)
        except Exception as e:
            logger.error(f"Reflection parser failed for goal {goal_id}: {e}")
            reflection_data = {}

        # Step 5: Generate alternative strategies
        strategies = self._generate_strategies(goal_type, failure_context, reflection_data)

        if not strategies:
            logger.info(f"No alternative strategies generated for goal {goal_id}")
            return False

        # Step 6: Enqueue retry goals
        for retry_goal in strategies:
            retry_goal.original_goal_id = goal_id
            self._retry_queue.append(retry_goal)
            self._orchestrator_enqueue(retry_goal)
            self._active_retries[goal_id] += 1
            logger.debug(f"Enqueued retry goal for {goal_id}: {retry_goal.strategy}")

        return True

    def _generate_strategies(
        self,
        goal_type: str,
        failure_context: Dict[str, Any],
        reflection_data: Dict[str, Any],
    ) -> List[RetryGoal]:
        """
        Generate 2-3 smaller sub-goals or alternative strategies.

        Args:
            goal_type: The type of the failed goal.
            failure_context: Original failure context.
            reflection_data: Parsed reflection data.

        Returns:
            A list of RetryGoal objects.
        """
        strategies = []

        # Strategy 1: Retry with same approach but with backoff
        retry_same = RetryGoal(
            original_goal_id="",
            goal_type=goal_type,
            strategy="retry_same",
            parameters={
                **failure_context,
                "backoff_factor": 2.0,
                "max_attempts": 1,
            },
            priority=1,
        )
        strategies.append(retry_same)

        # Strategy 2: Alternative approach based on reflection
        if reflection_data:
            alt_params = self._derive_alternative_parameters(goal_type, failure_context, reflection_data)
            alternative = RetryGoal(
                original_goal_id="",
                goal_type=goal_type,
                strategy="alternative_approach",
                parameters=alt_params,
                priority=2,
            )
            strategies.append(alternative)

        # Strategy 3: Decompose into sub-goals
        sub_goals = self._decompose_goal(goal_type, failure_context, reflection_data)
        strategies.extend(sub_goals)

        # Limit to 3 strategies
        return strategies[:3]

    def _derive_alternative_parameters(
        self,
        goal_type: str,
        failure_context: Dict[str, Any],
        reflection_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Derive alternative parameters from reflection data."""
        # Example: change timeout, retry with different input, etc.
        alt_params = failure_context.copy()
        if "timeout" in alt_params:
            alt_params["timeout"] = alt_params["timeout"] * 2
        if "retry_strategy" in alt_params:
            alt_params["retry_strategy"] = "exponential_backoff"
        alt_params["reflection_hints"] = reflection_data.get("hints", {})
        return alt_params

    def _decompose_goal(
        self,
        goal_type: str,
        failure_context: Dict[str, Any],
        reflection_data: Dict[str, Any],
    ) -> List[RetryGoal]:
        """Decompose the goal into smaller sub-goals."""
        sub_goals = []
        # Example decomposition: split into validation and execution
        if "validate" not in goal_type:
            validate_goal = RetryGoal(
                original_goal_id="",
                goal_type=f"{goal_type}_validate",
                strategy="decomposed_subgoal",
                parameters={"validation_data": failure_context.get("data", {})},
                priority=3,
            )
            sub_goals.append(validate_goal)

        execute_goal = RetryGoal(
            original_goal_id="",
            goal_type=goal_type,
            strategy="decomposed_subgoal",
            parameters={**failure_context, "decomposed": True},
            priority=3,
        )
        sub_goals.append(execute_goal)
        return sub_goals

    def get_failure_pattern_summary(self) -> List[Dict[str, Any]]:
        """Return a summary of all tracked failure patterns."""
        return [
            {
                "goal_type": pattern.goal_type,
                "failure_signature": pattern.failure_signature,
                "retry_count": pattern.retry_count,
                "last_failure_context": pattern.last_failure_context,
            }
            for pattern in self._failure_patterns.values()
        ]

    def reset_pattern(self, goal_type: str, failure_signature: str) -> None:
        """Reset retry count for a specific failure pattern."""
        pattern_key = f"{goal_type}:{failure_signature}"
        if pattern_key in self._failure_patterns:
            self._failure_patterns[pattern_key].retry_count = 0
            logger.info(f"Reset retry count for pattern '{pattern_key}'")

    def clear_all_patterns(self) -> None:
        """Clear all tracked failure patterns."""
        self._failure_patterns.clear()
        self._active_retries.clear()
        logger.info("Cleared all failure patterns and active retries")