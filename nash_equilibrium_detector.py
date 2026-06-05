"""Module for detecting Nash equilibrium in the mutation system.

Tracks mutation history and test results across modules to detect when
the system has reached a stable state (Nash equilibrium). In this context,
a Nash equilibrium means no module can unilaterally improve its performance
through mutation, given the current state of all other modules.
"""

from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set
import logging

logger = logging.getLogger(__name__)


@dataclass
class MutationRecord:
    """Record of a single mutation attempt."""
    module_name: str
    passed: bool
    cycle_number: int
    mutation_id: Optional[str] = None


@dataclass
class ModuleState:
    """Tracks mutation history for a single module."""
    recent_mutations: deque = field(default_factory=lambda: deque(maxlen=100))
    consecutive_failures: int = 0
    last_successful_cycle: Optional[int] = None
    total_attempts: int = 0
    total_successes: int = 0


class NashEquilibriumDetector:
    """Detects when the system has reached a Nash equilibrium.

    A Nash equilibrium is declared when no module has had a successful
    mutation for K consecutive cycles (configurable, default 5).
    """

    def __init__(self, k: int = 5, history_size: int = 100):
        """Initialize the detector.

        Args:
            k: Number of consecutive cycles with no successful mutations
               before declaring Nash equilibrium. Defaults to 5.
            history_size: Maximum number of mutation records to keep per module.
               Defaults to 100.

        Raises:
            ValueError: If k < 1 or history_size < 1.
        """
        if k < 1:
            raise ValueError(f"k must be >= 1, got {k}")
        if history_size < 1:
            raise ValueError(f"history_size must be >= 1, got {history_size}")

        self.k = k
        self.history_size = history_size
        self._module_states: Dict[str, ModuleState] = defaultdict(
            lambda: ModuleState(
                recent_mutations=deque(maxlen=history_size)
            )
        )
        self._current_cycle = 0
        self._cycles_without_success = 0
        self._is_equilibrium = False
        self._equilibrium_cycle: Optional[int] = None

    @property
    def current_cycle(self) -> int:
        """Get the current cycle number."""
        return self._current_cycle

    @property
    def cycles_without_success(self) -> int:
        """Get the number of consecutive cycles with no successful mutations."""
        return self._cycles_without_success

    @property
    def is_equilibrium(self) -> bool:
        """Check if Nash equilibrium has been declared."""
        return self._is_equilibrium

    @property
    def equilibrium_cycle(self) -> Optional[int]:
        """Get the cycle when equilibrium was declared, or None."""
        return self._equilibrium_cycle

    def record_mutation(self, module_name: str, passed: bool,
                        mutation_id: Optional[str] = None) -> None:
        """Record a mutation attempt for a module.

        Args:
            module_name: Name of the module that attempted mutation.
            passed: Whether the mutation passed all tests.
            mutation_id: Optional unique identifier for the mutation.
        """
        state = self._module_states[module_name]
        record = MutationRecord(
            module_name=module_name,
            passed=passed,
            cycle_number=self._current_cycle,
            mutation_id=mutation_id
        )
        state.recent_mutations.append(record)
        state.total_attempts += 1

        if passed:
            state.consecutive_failures = 0
            state.last_successful_cycle = self._current_cycle
            state.total_successes += 1
        else:
            state.consecutive_failures += 1

    def advance_cycle(self) -> bool:
        """Advance to the next cycle and check for equilibrium.

        Returns:
            True if Nash equilibrium was just declared, False otherwise.
        """
        self._current_cycle += 1

        # Check if any module had a successful mutation in the previous cycle
        had_success = any(
            state.last_successful_cycle == self._current_cycle - 1
            for state in self._module_states.values()
        )

        if had_success:
            self._cycles_without_success = 0
            self._is_equilibrium = False
            self._equilibrium_cycle = None
        else:
            self._cycles_without_success += 1
            if (self._cycles_without_success >= self.k
                    and not self._is_equilibrium):
                self._is_equilibrium = True
                self._equilibrium_cycle = self._current_cycle
                logger.info(
                    "Nash equilibrium declared at cycle %d after %d cycles "
                    "without any successful mutations",
                    self._current_cycle, self._cycles_without_success
                )
                return True

        return False

    def get_module_state(self, module_name: str) -> Optional[ModuleState]:
        """Get the state for a specific module.

        Args:
            module_name: Name of the module.

        Returns:
            ModuleState if the module exists, None otherwise.
        """
        return self._module_states.get(module_name)

    def get_all_module_states(self) -> Dict[str, ModuleState]:
        """Get states for all tracked modules.

        Returns:
            Dictionary mapping module names to their states.
        """
        return dict(self._module_states)

    def get_modules_with_recent_success(self, cycles: int = 1) -> Set[str]:
        """Get modules that had a successful mutation within the last N cycles.

        Args:
            cycles: Number of cycles to look back. Defaults to 1.

        Returns:
            Set of module names with recent successful mutations.
        """
        threshold = self._current_cycle - cycles
        return {
            name for name, state in self._module_states.items()
            if state.last_successful_cycle is not None
            and state.last_successful_cycle >= threshold
        }

    def get_modules_with_consecutive_failures(self, min_failures: int = 3
                                              ) -> Set[str]:
        """Get modules with at least N consecutive failures.

        Args:
            min_failures: Minimum number of consecutive failures. Defaults to 3.

        Returns:
            Set of module names meeting the criteria.
        """
        return {
            name for name, state in self._module_states.items()
            if state.consecutive_failures >= min_failures
        }

    def get_equilibrium_summary(self) -> Dict:
        """Get a summary of the current equilibrium state.

        Returns:
            Dictionary with equilibrium information.
        """
        return {
            "is_equilibrium": self._is_equilibrium,
            "current_cycle": self._current_cycle,
            "cycles_without_success": self._cycles_without_success,
            "k_threshold": self.k,
            "equilibrium_cycle": self._equilibrium_cycle,
            "total_modules_tracked": len(self._module_states),
            "modules_with_success": list(
                self.get_modules_with_recent_success(cycles=self.k)
            ),
            "modules_struggling": list(
                self.get_modules_with_consecutive_failures()
            )
        }

    def reset(self) -> None:
        """Reset all tracking data and equilibrium state."""
        self._module_states.clear()
        self._current_cycle = 0
        self._cycles_without_success = 0
        self._is_equilibrium = False
        self._equilibrium_cycle = None
        logger.debug("Nash equilibrium detector reset")

    def __repr__(self) -> str:
        return (
            f"NashEquilibriumDetector(k={self.k}, "
            f"cycle={self._current_cycle}, "
            f"equilibrium={self._is_equilibrium})"
        )