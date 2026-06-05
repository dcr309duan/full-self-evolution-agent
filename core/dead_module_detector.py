"""Dead Module Detector - Integrates with Capability Bankruptcy Engine.

Instead of performing separate archival decisions, this module feeds usage data
to the bankruptcy engine's scoring system. It tracks module usage over the last
50 cycles and provides aggregated statistics.
"""

from collections import defaultdict, deque
from typing import Dict, List, Optional


class DeadModuleDetector:
    """Tracks module usage and feeds data to the Capability Bankruptcy Engine.

    Rather than independently deciding to archive modules, this detector
    collects and reports usage statistics so the bankruptcy engine can
    incorporate them into its scoring.
    """

    def __init__(self, max_history_cycles: int = 50):
        self.max_history_cycles = max_history_cycles
        # module_name -> deque of (cycle_number, usage_count) for last N cycles
        self._usage_history: Dict[str, deque] = defaultdict(
            lambda: deque(maxlen=max_history_cycles)
        )
        self._current_cycle = 0

    def record_usage(self, module_name: str, cycle: Optional[int] = None) -> None:
        """Record a single usage event for a module at a given cycle.

        Args:
            module_name: The name of the module being used.
            cycle: The cycle number (defaults to internal counter).
        """
        if cycle is None:
            cycle = self._current_cycle

        # Find or create the entry for this cycle
        history = self._usage_history[module_name]
        if history and history[-1][0] == cycle:
            # Increment existing cycle entry
            count = history[-1][1] + 1
            history[-1] = (cycle, count)
        else:
            history.append((cycle, 1))

    def advance_cycle(self) -> None:
        """Advance the internal cycle counter (called by orchestrator)."""
        self._current_cycle += 1

    def get_usage_stats(self) -> Dict[str, int]:
        """Return dict of module -> total usage_count for the last 50 cycles.

        Returns:
            Dictionary mapping module names to their total usage count
            over the tracked history window.
        """
        stats: Dict[str, int] = {}
        for module_name, history in self._usage_history.items():
            total = sum(count for _, count in history)
            if total > 0:
                stats[module_name] = total
        return stats

    def get_module_usage(self, module_name: str) -> int:
        """Get total usage count for a specific module over the history window.

        Args:
            module_name: The module to query.

        Returns:
            Total usage count, or 0 if module has no recorded usage.
        """
        history = self._usage_history.get(module_name)
        if not history:
            return 0
        return sum(count for _, count in history)

    def get_recent_usage(self, module_name: str, cycles: int = 10) -> int:
        """Get usage count for a module over the most recent N cycles.

        Args:
            module_name: The module to query.
            cycles: Number of recent cycles to consider (default 10).

        Returns:
            Usage count in the specified window.
        """
        history = self._usage_history.get(module_name)
        if not history:
            return 0
        # Only consider entries within the last `cycles` cycles
        cutoff = self._current_cycle - cycles
        recent = [(c, cnt) for c, cnt in history if c >= cutoff]
        return sum(cnt for _, cnt in recent)

    def get_all_modules(self) -> List[str]:
        """Return list of all modules that have been tracked."""
        return list(self._usage_history.keys())

    def reset(self) -> None:
        """Clear all usage history (for testing or full reset)."""
        self._usage_history.clear()
        self._current_cycle = 0