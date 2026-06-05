from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


class StrategySelector:
    """
    Manages mutation strategies for target modules.
    Maintains a list of available strategies, accepts recommendations from
    FailurePatternClassifier, and implements strategy switching logic.
    """

    AVAILABLE_STRATEGIES: List[str] = [
        'ast_rewrite',
        'wrapper_inject',
        'monkey_patch',
        'config_change'
    ]

    def __init__(self) -> None:
        # Maps target module -> list of strategies already tried
        self._tried_strategies: Dict[str, List[str]] = {}
        # Maps target module -> current active strategy (or None)
        self._current_strategies: Dict[str, Optional[str]] = {}

    def register_target(self, target: str) -> None:
        """Ensure a target module is tracked."""
        if target not in self._tried_strategies:
            self._tried_strategies[target] = []
            self._current_strategies[target] = None
            logger.info("Registered target '%s' for strategy selection.", target)

    def accept_recommendation(self, target: str, recommended_strategy: Optional[str]) -> None:
        """
        Accept a strategy recommendation from FailurePatternClassifier.
        If the recommendation is valid and not yet tried for the target, set it as current.
        Otherwise, fall back to the next untried strategy.
        """
        self.register_target(target)

        if recommended_strategy and recommended_strategy in self.AVAILABLE_STRATEGIES:
            if recommended_strategy not in self._tried_strategies[target]:
                self._set_strategy(target, recommended_strategy)
                logger.info("Accepted recommendation: strategy '%s' for target '%s'.", recommended_strategy, target)
                return
            else:
                logger.info("Recommended strategy '%s' already tried for '%s'. Switching.", recommended_strategy, target)

        # Fall back to next untried strategy
        self._switch_to_next(target)

    def _switch_to_next(self, target: str) -> None:
        """Pick the next untried strategy for the target module."""
        self.register_target(target)
        tried = self._tried_strategies[target]
        for strategy in self.AVAILABLE_STRATEGIES:
            if strategy not in tried:
                self._set_strategy(target, strategy)
                logger.info("Strategy switch: selected '%s' for target '%s'.", strategy, target)
                return
        # All strategies tried – set to None
        self._set_strategy(target, None)
        logger.warning("No untried strategies left for target '%s'.", target)

    def _set_strategy(self, target: str, strategy: Optional[str]) -> None:
        """Set the current strategy and record it as tried."""
        if strategy is not None:
            self._tried_strategies[target].append(strategy)
        self._current_strategies[target] = strategy

    def get_current_strategy(self, target: str) -> Optional[str]:
        """Expose the current strategy for a given target."""
        return self._current_strategies.get(target)

    def get_tried_strategies(self, target: str) -> List[str]:
        """Return list of strategies already tried for a target."""
        return self._tried_strategies.get(target, [])

    def reset_target(self, target: str) -> None:
        """Clear all tracked data for a target (e.g., for a fresh mutation cycle)."""
        if target in self._tried_strategies:
            del self._tried_strategies[target]
        if target in self._current_strategies:
            del self._current_strategies[target]
        logger.info("Reset strategy state for target '%s'.", target)