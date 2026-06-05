"""mutation_engine/engine.py - Main mutation engine loop with validator integration."""

import logging
from typing import Any, Callable, Optional

from mutation_engine.validator import MutationValidator, ValidationPhase
from mutation_engine.strategy import MutationStrategy, StrategyManager
from mutation_engine.compensator import Compensator

logger = logging.getLogger(__name__)


class MutationEngine:
    """Core engine that applies mutations with validation and strategy management."""

    def __init__(
        self,
        strategy_manager: StrategyManager,
        validator: MutationValidator,
        compensator: Compensator,
        max_consecutive_failures: int = 3,
    ):
        self.strategy_manager = strategy_manager
        self.validator = validator
        self.compensator = compensator
        self.max_consecutive_failures = max_consecutive_failures
        self.consecutive_failures = 0
        self.mutation_count = 0
        self.success_count = 0
        self.failure_count = 0

    def run_mutation_cycle(self, target: Any, context: Optional[dict] = None) -> bool:
        """Execute one mutation cycle: validate, mutate, commit.

        Args:
            target: The object or data to mutate.
            context: Optional context dictionary for validation.

        Returns:
            True if mutation was applied successfully, False otherwise.
        """
        context = context or {}
        strategy = self.strategy_manager.get_current_strategy()

        # Phase 1: Pre-mutation validation
        pre_result = self.validator.validate(target, ValidationPhase.PRE_MUTATION, context)
        if not pre_result.passed:
            logger.warning(
                "Pre-mutation validation failed: %s | phase: %s",
                pre_result.message,
                pre_result.phase,
            )
            self._handle_validation_failure(target, context)
            return False

        # Phase 2: Apply mutation
        try:
            mutated_target = strategy.apply_mutation(target, context)
        except Exception as exc:
            logger.error("Mutation application error: %s", exc)
            self._handle_validation_failure(target, context)
            return False

        # Phase 3: Post-mutation validation
        post_result = self.validator.validate(mutated_target, ValidationPhase.POST_MUTATION, context)
        if not post_result.passed:
            logger.warning(
                "Post-mutation validation failed: %s | phase: %s",
                post_result.message,
                post_result.phase,
            )
            self._handle_validation_failure(target, context)
            return False

        # Phase 4: Commit validation
        commit_result = self.validator.validate(mutated_target, ValidationPhase.COMMIT, context)
        if not commit_result.passed:
            logger.warning(
                "Commit validation failed: %s | phase: %s",
                commit_result.message,
                commit_result.phase,
            )
            self._handle_validation_failure(target, context)
            return False

        # Phase 5: Check for side effects
        side_effects = self.validator.detect_side_effects(mutated_target, context)
        if side_effects:
            logger.info("Side effects detected, attempting compensation")
            try:
                compensated_target = self.compensator.generate_fixes(mutated_target, side_effects, context)
                # Apply original mutation plus compensating modifications as atomic commit
                self._commit_mutation(compensated_target, context)
                self.consecutive_failures = 0
                self.success_count += 1
                self.mutation_count += 1
                logger.info(
                    "Mutation with compensation applied successfully | total: %d, success: %d, failures: %d",
                    self.mutation_count,
                    self.success_count,
                    self.failure_count,
                )
                return True
            except Exception as exc:
                logger.error("Compensation failed: %s. Rolling back mutation.", exc)
                # Rollback the entire mutation
                self._handle_validation_failure(target, context)
                return False

        # No side effects - commit the mutation directly
        self._commit_mutation(mutated_target, context)
        self.consecutive_failures = 0
        self.success_count += 1
        self.mutation_count += 1

        logger.info(
            "Mutation applied successfully | total: %d, success: %d, failures: %d",
            self.mutation_count,
            self.success_count,
            self.failure_count,
        )
        return True

    def _handle_validation_failure(self, target: Any, context: dict) -> None:
        """Handle a validation failure: log, increment counter, optionally switch strategy."""
        self.consecutive_failures += 1
        self.failure_count += 1
        self.mutation_count += 1

        logger.info(
            "Validation failure #%d consecutive | total failures: %d",
            self.consecutive_failures,
            self.failure_count,
        )

        if self.consecutive_failures >= self.max_consecutive_failures:
            logger.warning(
                "Max consecutive failures (%d) reached. Switching strategy.",
                self.max_consecutive_failures,
            )
            self.strategy_manager.switch_strategy(target, context)
            self.consecutive_failures = 0

    def _commit_mutation(self, mutated_target: Any, context: dict) -> None:
        """Commit the mutated target. Override in subclasses for custom commit logic."""
        # Default: replace the original target in context if present
        if "original" in context:
            context["original"] = mutated_target
        logger.debug("Mutation committed.")