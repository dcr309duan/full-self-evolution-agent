"""Module for detecting dead or underutilized modules based on usage tracking."""

from collections import defaultdict
from typing import Dict, List, Set


class DeadModuleDetector:
    """Tracks module usage across cycles and identifies dead modules."""

    def __init__(self, history_length: int = 20, min_uses: int = 2):
        """
        Initialize the detector.

        Args:
            history_length: Number of recent cycles to consider (default 20)
            min_uses: Minimum number of uses required to be considered alive (default 2)
        """
        self._usage_history: Dict[str, List[int]] = defaultdict(list)
        self._flagged_for_deprecation: Set[str] = set()
        self._history_length = history_length
        self._min_uses = min_uses
        self._current_cycle = 0

    def record_usage(self, module_name: str) -> None:
        """
        Record that a module was used in the current cycle.

        Args:
            module_name: Name of the module being used
        """
        self._usage_history[module_name].append(self._current_cycle)
        # Trim history to keep only recent cycles
        self._usage_history[module_name] = [
            cycle for cycle in self._usage_history[module_name]
            if cycle >= self._current_cycle - self._history_length
        ]

    def get_dead_modules(self) -> List[str]:
        """
        Get modules that have been used fewer than min_uses times in the last history_length cycles.

        Returns:
            List of module names considered dead
        """
        dead_modules = []
        cutoff_cycle = self._current_cycle - self._history_length

        for module_name, cycles in self._usage_history.items():
            # Count uses in the relevant window
            recent_uses = sum(1 for cycle in cycles if cycle >= cutoff_cycle)
            if recent_uses < self._min_uses:
                dead_modules.append(module_name)

        return dead_modules

    def flag_for_deprecation(self, module_name: str) -> None:
        """
        Mark a module for removal in the next mutation cycle.

        Args:
            module_name: Name of the module to deprecate
        """
        self._flagged_for_deprecation.add(module_name)

    def get_flagged_for_deprecation(self) -> List[str]:
        """
        Get all modules currently flagged for deprecation.

        Returns:
            List of module names flagged for removal
        """
        return list(self._flagged_for_deprecation)

    def clear_deprecation_flag(self, module_name: str) -> None:
        """
        Remove a deprecation flag from a module (e.g., if it becomes active again).

        Args:
            module_name: Name of the module to unflag
        """
        self._flagged_for_deprecation.discard(module_name)

    def advance_cycle(self) -> None:
        """Advance to the next cycle number."""
        self._current_cycle += 1

    def get_current_cycle(self) -> int:
        """Get the current cycle number."""
        return self._current_cycle

    def get_usage_count(self, module_name: str, recent_only: bool = True) -> int:
        """
        Get the usage count for a specific module.

        Args:
            module_name: Name of the module
            recent_only: If True, only count uses in the last history_length cycles

        Returns:
            Number of times the module has been used
        """
        if module_name not in self._usage_history:
            return 0

        if recent_only:
            cutoff = self._current_cycle - self._history_length
            return sum(1 for cycle in self._usage_history[module_name] if cycle >= cutoff)
        else:
            return len(self._usage_history[module_name])

    def reset(self) -> None:
        """Reset all tracking data."""
        self._usage_history.clear()
        self._flagged_for_deprecation.clear()
        self._current_cycle = 0