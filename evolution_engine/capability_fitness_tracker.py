"""Capability Fitness Tracker for tracking usage and fitness of capabilities."""

import logging
import uuid
from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


class CapabilityFitnessTracker:
    """Tracks capability fitness based on downstream usage in tasks/goals.

    Maintains a registry of capabilities with unique IDs, tracks dependencies
    via a directed graph, and computes fitness scores. Supports configurable
    thresholds for deprecation and cycles before deprecation.
    """

    def __init__(self, threshold: int = 2, cycles_before_deprecation: int = 10):
        """Initialize the fitness tracker.

        Args:
            threshold: Minimum fitness score before a capability is considered
                for deprecation. Default is 2.
            cycles_before_deprecation: Number of evaluation cycles a capability
                must be below threshold before being deprecated. Default is 10.
        """
        self.threshold = threshold
        self.cycles_before_deprecation = cycles_before_deprecation

        # Registry: capability_id -> capability metadata
        self._registry: Dict[str, dict] = {}

        # Dependency graph: capability_id -> set of downstream task/goal IDs
        self._dependency_graph: Dict[str, Set[str]] = defaultdict(set)

        # Track consecutive cycles below threshold for each capability
        self._cycles_below_threshold: Dict[str, int] = defaultdict(int)

        # Track deprecation events
        self._deprecation_events: List[dict] = []

    def register_capability(self, capability_data: dict) -> str:
        """Register a new capability and return its unique ID.

        Args:
            capability_data: Dictionary with capability metadata (e.g., name, type).

        Returns:
            Unique string ID for the registered capability.
        """
        capability_id = str(uuid.uuid4())
        self._registry[capability_id] = {
            "id": capability_id,
            "data": capability_data,
            "registered_at": datetime.utcnow().isoformat(),
        }
        logger.info("Registered capability %s: %s", capability_id, capability_data.get("name", "unnamed"))
        return capability_id

    def add_dependency(self, capability_id: str, downstream_id: str) -> None:
        """Record that a downstream task/goal uses a capability.

        Args:
            capability_id: The ID of the capability.
            downstream_id: The ID of the downstream task or goal.

        Raises:
            ValueError: If capability_id is not registered.
        """
        if capability_id not in self._registry:
            raise ValueError(f"Capability {capability_id} not registered.")
        self._dependency_graph[capability_id].add(downstream_id)
        logger.debug("Added dependency: %s -> %s", capability_id, downstream_id)

    def remove_dependency(self, capability_id: str, downstream_id: str) -> None:
        """Remove a downstream dependency from a capability.

        Args:
            capability_id: The ID of the capability.
            downstream_id: The ID of the downstream task/goal to remove.

        Raises:
            ValueError: If capability_id is not registered.
        """
        if capability_id not in self._registry:
            raise ValueError(f"Capability {capability_id} not registered.")
        self._dependency_graph[capability_id].discard(downstream_id)
        logger.debug("Removed dependency: %s -> %s", capability_id, downstream_id)

    def get_fitness_score(self, capability_id: str) -> int:
        """Compute fitness score as count of downstream uses.

        Args:
            capability_id: The ID of the capability.

        Returns:
            Integer count of downstream tasks/goals using this capability.

        Raises:
            ValueError: If capability_id is not registered.
        """
        if capability_id not in self._registry:
            raise ValueError(f"Capability {capability_id} not registered.")
        return len(self._dependency_graph.get(capability_id, set()))

    def get_all_fitness_scores(self) -> Dict[str, int]:
        """Get fitness scores for all registered capabilities.

        Returns:
            Dictionary mapping capability_id to its fitness score.
        """
        return {cid: self.get_fitness_score(cid) for cid in self._registry}

    def get_capabilities_below_threshold(self) -> List[Tuple[str, int, int]]:
        """Get capabilities with fitness score below threshold.

        Returns:
            List of tuples (capability_id, fitness_score, cycles_below_threshold)
            for capabilities currently below the threshold.
        """
        results = []
        for cid in self._registry:
            score = self.get_fitness_score(cid)
            if score < self.threshold:
                self._cycles_below_threshold[cid] += 1
                results.append((cid, score, self._cycles_below_threshold[cid]))
            else:
                # Reset counter if score is back above threshold
                self._cycles_below_threshold[cid] = 0
        return results

    def deprecate_capability(self, capability_id: str) -> Optional[dict]:
        """Deprecate a capability and log the event.

        Removes the capability from the registry and dependency graph.
        Only deprecates if the capability has been below threshold for
        at least cycles_before_deprecation cycles.

        Args:
            capability_id: The ID of the capability to deprecate.

        Returns:
            Dictionary with deprecation event details, or None if not deprecated.
        """
        if capability_id not in self._registry:
            logger.warning("Attempted to deprecate unknown capability %s", capability_id)
            return None

        cycles_below = self._cycles_below_threshold.get(capability_id, 0)
        if cycles_below < self.cycles_before_deprecation:
            logger.info(
                "Capability %s not deprecated yet: %d cycles below threshold (need %d)",
                capability_id,
                cycles_below,
                self.cycles_before_deprecation,
            )
            return None

        # Record deprecation event
        event = {
            "capability_id": capability_id,
            "timestamp": datetime.utcnow().isoformat(),
            "reason": f"Fitness score below threshold for {cycles_below} cycles",
            "fitness_score": self.get_fitness_score(capability_id),
            "cycles_below_threshold": cycles_below,
        }
        self._deprecation_events.append(event)

        # Remove from registry and dependency graph
        del self._registry[capability_id]
        self._dependency_graph.pop(capability_id, None)
        self._cycles_below_threshold.pop(capability_id, None)

        logger.warning(
            "Deprecated capability %s: %s",
            capability_id,
            event["reason"],
        )
        return event

    def evaluate_and_deprecate(self) -> List[dict]:
        """Evaluate all capabilities and deprecate those below threshold.

        Returns:
            List of deprecation event dictionaries for deprecated capabilities.
        """
        deprecated = []
        below = self.get_capabilities_below_threshold()
        for cid, score, cycles in below:
            event = self.deprecate_capability(cid)
            if event:
                deprecated.append(event)
        return deprecated

    def get_deprecation_events(self) -> List[dict]:
        """Get all recorded deprecation events.

        Returns:
            List of deprecation event dictionaries.
        """
        return list(self._deprecation_events)

    def get_registered_capabilities(self) -> Dict[str, dict]:
        """Get all currently registered capabilities.

        Returns:
            Dictionary mapping capability_id to capability metadata.
        """
        return dict(self._registry)

    def get_dependency_graph(self) -> Dict[str, Set[str]]:
        """Get the current dependency graph.

        Returns:
            Dictionary mapping capability_id to set of downstream IDs.
        """
        return {cid: set(deps) for cid, deps in self._dependency_graph.items()}

    def reset(self) -> None:
        """Reset all state (registry, dependencies, counters, events)."""
        self._registry.clear()
        self._dependency_graph.clear()
        self._cycles_below_threshold.clear()
        self._deprecation_events.clear()
        logger.info("CapabilityFitnessTracker state reset.")