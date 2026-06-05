from typing import Dict, Any, Optional
from dataclasses import dataclass, field


@dataclass
class CapabilityRecord:
    """Represents a tracked capability with usage and fitness metrics."""
    name: str
    usage_count: int = 0
    last_active_cycle: int = -1
    fitness_contribution: float = 0.0


class CapabilityManager:
    """Manages capability tracking, usage frequency, and fitness contributions."""

    def __init__(self):
        self._capabilities: Dict[str, CapabilityRecord] = {}

    def register_capability(self, name: str) -> None:
        """Register a new capability for tracking."""
        if name not in self._capabilities:
            self._capabilities[name] = CapabilityRecord(name=name)

    def record_usage(self, name: str, current_cycle: int) -> None:
        """Record that a capability was used in the given cycle."""
        if name not in self._capabilities:
            self.register_capability(name)
        record = self._capabilities[name]
        record.usage_count += 1
        record.last_active_cycle = current_cycle

    def update_fitness_contribution(self, name: str, contribution: float) -> None:
        """Set the fitness contribution for a capability."""
        if name in self._capabilities:
            self._capabilities[name].fitness_contribution = contribution

    def get_capability(self, name: str) -> Optional[CapabilityRecord]:
        """Retrieve the record for a specific capability."""
        return self._capabilities.get(name)

    def get_all_capabilities(self) -> Dict[str, CapabilityRecord]:
        """Return all tracked capabilities."""
        return dict(self._capabilities)

    def get_low_impact_capabilities(self, threshold_usage: int = 5, threshold_cycle_staleness: int = 10, current_cycle: int = 0) -> Dict[str, CapabilityRecord]:
        """
        Identify capabilities that are low-impact based on usage frequency and staleness.
        
        Args:
            threshold_usage: Minimum usage count to be considered non-low-impact.
            threshold_cycle_staleness: Maximum cycles since last active to be considered non-low-impact.
            current_cycle: The current cycle number to compare against last_active_cycle.
        
        Returns:
            Dictionary of capability names to records that are considered low-impact.
        """
        low_impact = {}
        for name, record in self._capabilities.items():
            is_low_usage = record.usage_count < threshold_usage
            is_stale = (current_cycle - record.last_active_cycle) > threshold_cycle_staleness
            if is_low_usage or is_stale:
                low_impact[name] = record
        return low_impact

    def reset(self) -> None:
        """Clear all tracked capabilities."""
        self._capabilities.clear()