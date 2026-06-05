from typing import Callable, Optional, Dict, Any
from enum import Enum
import time
import logging
from dataclasses import dataclass, field
from evolution_engine.rollback import RollbackManager

logger = logging.getLogger(__name__)

class MutationStrategy(Enum):
    """Available mutation strategies for self-healing."""
    SMALLER_SCOPE = "smaller_scope"
    DIFFERENT_MODULE = "different_module"
    DIFFERENT_TYPE = "different_type"

class HealLevel(Enum):
    """Escalation levels for self-healing."""
    LEVEL_1 = 1  # Retry with same strategy
    LEVEL_2 = 2  # Switch to smaller scope
    LEVEL_3 = 3  # Switch to different module or type
    ESCALATED = 4  # Full escalation

@dataclass
class MutationAttempt:
    """Tracks a single mutation attempt."""
    mutation_id: str
    strategy: MutationStrategy
    failure_count: int = 0
    last_error: Optional[str] = None
    timestamp: float = field(default_factory=time.time)

class SelfHealingRetry:
    """
    Wraps mutation execution with retry logic, tracks failures,
    and implements strategy switching with escalation.
    """

    def __init__(self, max_retries: int = 3, rollback_manager: Optional[RollbackManager] = None):
        self.max_retries = max_retries
        self.rollback_manager = rollback_manager or RollbackManager()
        self.attempts: Dict[str, MutationAttempt] = {}
        self.heal_level: HealLevel = HealLevel.LEVEL_1
        self._current_strategy: MutationStrategy = MutationStrategy.SMALLER_SCOPE

    def execute_with_retry(self, mutation_func: Callable, mutation_id: str, **kwargs) -> Any:
        """
        Execute a mutation with retry logic and strategy switching.
        
        Args:
            mutation_func: The mutation function to execute
            mutation_id: Unique identifier for this mutation attempt
            **kwargs: Additional arguments passed to mutation_func
            
        Returns:
            The result of the successful mutation execution
            
        Raises:
            Exception: If all retries and strategies fail
        """
        attempt = self._get_or_create_attempt(mutation_id)
        
        for retry_count in range(self.max_retries + 1):
            try:
                result = mutation_func(**kwargs)
                self._on_success(attempt)
                return result
            except Exception as e:
                self._on_failure(attempt, str(e))
                logger.warning(f"Mutation {mutation_id} failed (attempt {retry_count + 1}/{self.max_retries + 1}): {e}")
                
                if retry_count < self.max_retries:
                    self._apply_healing_strategy(attempt)
                else:
                    self._escalate(attempt)
                    raise

    def _get_or_create_attempt(self, mutation_id: str) -> MutationAttempt:
        """Get existing attempt or create a new one."""
        if mutation_id not in self.attempts:
            self.attempts[mutation_id] = MutationAttempt(
                mutation_id=mutation_id,
                strategy=self._current_strategy
            )
        return self.attempts[mutation_id]

    def _on_success(self, attempt: MutationAttempt) -> None:
        """Handle successful mutation execution."""
        attempt.failure_count = 0
        attempt.last_error = None
        self.heal_level = HealLevel.LEVEL_1
        logger.info(f"Mutation {attempt.mutation_id} succeeded after {attempt.failure_count} failures")

    def _on_failure(self, attempt: MutationAttempt, error: str) -> None:
        """Handle mutation failure."""
        attempt.failure_count += 1
        attempt.last_error = error
        logger.debug(f"Mutation {attempt.mutation_id} failure count: {attempt.failure_count}")

    def _apply_healing_strategy(self, attempt: MutationAttempt) -> None:
        """Apply appropriate healing strategy based on failure count."""
        if attempt.failure_count >= 3:
            self._switch_strategy(attempt)
        
        if self.heal_level == HealLevel.LEVEL_1:
            self._retry_same_strategy(attempt)
        elif self.heal_level == HealLevel.LEVEL_2:
            self._apply_smaller_scope(attempt)
        elif self.heal_level == HealLevel.LEVEL_3:
            self._apply_different_module_or_type(attempt)

    def _switch_strategy(self, attempt: MutationAttempt) -> None:
        """Switch to next available strategy."""
        if self._current_strategy == MutationStrategy.SMALLER_SCOPE:
            self._current_strategy = MutationStrategy.DIFFERENT_MODULE
            self.heal_level = HealLevel.LEVEL_2
        elif self._current_strategy == MutationStrategy.DIFFERENT_MODULE:
            self._current_strategy = MutationStrategy.DIFFERENT_TYPE
            self.heal_level = HealLevel.LEVEL_3
        else:
            self.heal_level = HealLevel.ESCALATED
        
        attempt.strategy = self._current_strategy
        logger.info(f"Switching to strategy: {self._current_strategy.value}")

    def _retry_same_strategy(self, attempt: MutationAttempt) -> None:
        """Retry with the same strategy."""
        logger.info(f"Retrying mutation {attempt.mutation_id} with same strategy")
        time.sleep(1)  # Brief delay before retry

    def _apply_smaller_scope(self, attempt: MutationAttempt) -> None:
        """Apply smaller scope strategy."""
        logger.info(f"Applying smaller scope for mutation {attempt.mutation_id}")
        # Implementation would reduce mutation scope
        # For example, limiting to fewer files or lines
        pass

    def _apply_different_module_or_type(self, attempt: MutationAttempt) -> None:
        """Apply different module or mutation type strategy."""
        logger.info(f"Switching module/type for mutation {attempt.mutation_id}")
        # Implementation would change target module or mutation type
        pass

    def _escalate(self, attempt: MutationAttempt) -> None:
        """Escalate after max retries exhausted."""
        self.heal_level = HealLevel.ESCALATED
        logger.error(f"Escalating mutation {attempt.mutation_id} after {attempt.failure_count} failures")
        
        # Integrate with rollback mechanism
        self.rollback_manager.rollback_mutation(attempt.mutation_id)
        
        # Reset for next attempt
        self._reset_for_retry(attempt)

    def _reset_for_retry(self, attempt: MutationAttempt) -> None:
        """Reset state for potential future retry."""
        attempt.failure_count = 0
        attempt.last_error = None
        self._current_strategy = MutationStrategy.SMALLER_SCOPE
        self.heal_level = HealLevel.LEVEL_1

    def get_failure_count(self, mutation_id: str) -> int:
        """Get failure count for a specific mutation."""
        attempt = self.attempts.get(mutation_id)
        return attempt.failure_count if attempt else 0

    def get_current_strategy(self) -> MutationStrategy:
        """Get the current active strategy."""
        return self._current_strategy

    def get_heal_level(self) -> HealLevel:
        """Get the current healing escalation level."""
        return self.heal_level

    def reset(self) -> None:
        """Reset all tracking data."""
        self.attempts.clear()
        self.heal_level = HealLevel.LEVEL_1
        self._current_strategy = MutationStrategy.SMALLER_SCOPE