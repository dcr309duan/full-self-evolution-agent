"""Core feasibility estimator for the autonomous coding agent.

This module provides the FeasibilityEstimator class which evaluates whether
a given goal can be implemented given the current state of the system model,
knowledge graph, integration test coverage, and schema alignment status.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


class FeasibilityStatus(Enum):
    """Possible feasibility statuses for a goal."""
    FEASIBLE = "FEASIBLE"
    BLOCKED = "BLOCKED"
    RISKY = "RISKY"
    UNKNOWN = "UNKNOWN"


@dataclass
class FeasibilityResult:
    """Result of a feasibility estimation."""
    status: FeasibilityStatus
    score: float  # 0.0 (impossible) to 1.0 (fully feasible)
    untested_interactions: List[str] = field(default_factory=list)
    unmet_prerequisites: List[str] = field(default_factory=list)
    schema_mismatches: List[str] = field(default_factory=list)
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Component:
    """Represents a component in the system model."""
    name: str
    schema: Optional[str] = None
    integration_tests: List[str] = field(default_factory=list)
    prerequisites: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Interaction:
    """Represents an interaction between two components."""
    source: str
    target: str
    interaction_type: str = "call"
    tested: bool = False
    schema_aligned: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SystemModel:
    """Represents the current system model/knowledge graph."""
    components: Dict[str, Component] = field(default_factory=dict)
    interactions: List[Interaction] = field(default_factory=list)
    schema_registry: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


class FeasibilityEstimator:
    """Core class for estimating feasibility of goals against the current system state."""

    # Penalty weights for different factors
    UNTESTED_INTERACTION_PENALTY = 0.15
    UNMET_PREREQUISITE_PENALTY = 0.30
    SCHEMA_MISMATCH_PENALTY = 0.20
    BLOCKED_THRESHOLD = 0.4  # Scores below this result in BLOCKED status
    RISKY_THRESHOLD = 0.7    # Scores below this but above BLOCKED result in RISKY

    def __init__(self, system_model: Optional[SystemModel] = None):
        """Initialize with an optional system model.

        Args:
            system_model: The current system model/knowledge graph. If None,
                         an empty model will be created.
        """
        self.system_model = system_model or SystemModel()
        self._goal_cache: Dict[str, FeasibilityResult] = {}

    def load_system_model(self, model: SystemModel) -> None:
        """Load/replace the current system model.

        Args:
            model: The system model to load.
        """
        self.system_model = model
        self._goal_cache.clear()
        logger.info("System model loaded with %d components and %d interactions",
                     len(model.components), len(model.interactions))

    def update_system_model(self, **updates: Any) -> None:
        """Update specific parts of the system model.

        Args:
            **updates: Keyword arguments matching SystemModel fields to update.
        """
        for key, value in updates.items():
            if hasattr(self.system_model, key):
                setattr(self.system_model, key, value)
        self._goal_cache.clear()
        logger.debug("System model updated with %d changes", len(updates))

    def estimate_feasibility(self, goal: str) -> FeasibilityResult:
        """Estimate feasibility of a given goal.

        Args:
            goal: The goal description to evaluate.

        Returns:
            FeasibilityResult with status, score, and details.
        """
        # Check cache first
        if goal in self._goal_cache:
            return self._goal_cache[goal]

        logger.info("Estimating feasibility for goal: %s", goal)

        # Parse goal to identify required components and interactions
        required_components, required_interactions = self._parse_goal(goal)

        # Check integration test coverage
        untested = self._check_integration_test_coverage(required_interactions)

        # Check schema alignment
        schema_mismatches = self._check_schema_alignment(required_interactions)

        # Check prerequisites
        unmet_prereqs = self._check_prerequisites(required_components)

        # Compute feasibility score
        score = self._compute_feasibility_score(
            required_components, required_interactions,
            untested, schema_mismatches, unmet_prereqs
        )

        # Determine status
        status = self._determine_status(score, unmet_prereqs)

        result = FeasibilityResult(
            status=status,
            score=score,
            untested_interactions=untested,
            unmet_prerequisites=unmet_prereqs,
            schema_mismatches=schema_mismatches,
            details={
                "goal": goal,
                "required_components": [c.name for c in required_components],
                "required_interactions": [
                    f"{i.source}->{i.target}" for i in required_interactions
                ],
                "total_components": len(required_components),
                "total_interactions": len(required_interactions),
            }
        )

        # Cache result
        self._goal_cache[goal] = result

        logger.info("Feasibility result for '%s': %s (score=%.2f)",
                     goal, status.value, score)
        return result

    def _parse_goal(self, goal: str) -> Tuple[List[Component], List[Interaction]]:
        """Parse a goal to identify required components and their interactions.

        Args:
            goal: The goal description string.

        Returns:
            Tuple of (list of required components, list of required interactions).
        """
        # TODO: Implement proper NLP-based parsing or use a goal parser module.
        # For now, we do a simple keyword-based extraction.
        required_components: List[Component] = []
        required_interactions: List[Interaction] = []

        goal_lower = goal.lower()

        # Simple heuristic: look for component names in the goal
        for comp_name, component in self.system_model.components.items():
            if comp_name.lower() in goal_lower:
                required_components.append(component)

        # Find interactions involving required components
        required_comp_names = {c.name for c in required_components}
        for interaction in self.system_model.interactions:
            if (interaction.source in required_comp_names or
                interaction.target in required_comp_names):
                required_interactions.append(interaction)

        logger.debug("Parsed goal '%s': found %d components, %d interactions",
                     goal, len(required_components), len(required_interactions))
        return required_components, required_interactions

    def _check_integration_test_coverage(
        self, interactions: List[Interaction]
    ) -> List[str]:
        """Check integration test coverage for each cross-component interaction.

        Args:
            interactions: List of interactions to check.

        Returns:
            List of untested interaction descriptions.
        """
        untested: List[str] = []
        for interaction in interactions:
            if not interaction.tested:
                desc = f"{interaction.source} -> {interaction.target} ({interaction.interaction_type})"
                untested.append(desc)
                logger.debug("Untested interaction: %s", desc)
        return untested

    def _check_schema_alignment(
        self, interactions: List[Interaction]
    ) -> List[str]:
        """Check schema alignment status for interactions.

        Args:
            interactions: List of interactions to check.

        Returns:
            List of schema mismatch descriptions.
        """
        mismatches: List[str] = []
        for interaction in interactions:
            if not interaction.schema_aligned:
                desc = f"Schema mismatch: {interaction.source} -> {interaction.target}"
                mismatches.append(desc)
                logger.debug("Schema mismatch: %s", desc)
        return mismatches

    def _check_prerequisites(
        self, components: List[Component]
    ) -> List[str]:
        """Check if all prerequisites for components are met.

        Args:
            components: List of components to check prerequisites for.

        Returns:
            List of unmet prerequisite descriptions.
        """
        unmet: List[str] = []
        for component in components:
            for prereq in component.prerequisites:
                if prereq not in self.system_model.components:
                    desc = f"Prerequisite '{prereq}' not found for component '{component.name}'"
                    unmet.append(desc)
                    logger.debug("Unmet prerequisite: %s", desc)
        return unmet

    def _compute_feasibility_score(
        self,
        components: List[Component],
        interactions: List[Interaction],
        untested: List[str],
        schema_mismatches: List[str],
        unmet_prereqs: List[str],
    ) -> float:
        """Compute a feasibility score with penalties.

        Args:
            components: Required components.
            interactions: Required interactions.
            untested: List of untested interactions.
            schema_mismatches: List of schema mismatches.
            unmet_prereqs: List of unmet prerequisites.

        Returns:
            Feasibility score between 0.0 and 1.0.
        """
        if not components and not interactions:
            return 1.0  # No requirements means trivially feasible

        # Start with perfect score
        score = 1.0

        # Apply penalties
        total_interactions = len(interactions) or 1
        total_components = len(components) or 1

        # Penalty for untested interactions
        untested_ratio = len(untested) / total_interactions
        score -= untested_ratio * self.UNTESTED_INTERACTION_PENALTY

        # Penalty for schema mismatches
        mismatch_ratio = len(schema_mismatches) / total_interactions
        score -= mismatch_ratio * self.SCHEMA_MISMATCH_PENALTY

        # Penalty for unmet prerequisites (severe)
        prereq_ratio = len(unmet_prereqs) / total_components
        score -= prereq_ratio * self.UNMET_PREREQUISITE_PENALTY

        # Ensure score is within [0, 1]
        score = max(0.0, min(1.0, score))

        logger.debug("Feasibility score computed: %.2f", score)
        return score

    def _determine_status(
        self, score: float, unmet_prereqs: List[str]
    ) -> FeasibilityStatus:
        """Determine feasibility status based on score and prerequisites.

        Args:
            score: The computed feasibility score.
            unmet_prereqs: List of unmet prerequisites.

        Returns:
            FeasibilityStatus enum value.
        """
        # Block if any prerequisites are not met
        if unmet_prereqs:
            logger.info("Goal BLOCKED due to unmet prerequisites: %s", unmet_prereqs)
            return FeasibilityStatus.BLOCKED

        # Determine status based on score thresholds
        if score < self.BLOCKED_THRESHOLD:
            return FeasibilityStatus.BLOCKED
        elif score < self.RISKY_THRESHOLD:
            return FeasibilityStatus.RISKY
        else:
            return FeasibilityStatus.FEASIBLE

    def clear_cache(self) -> None:
        """Clear the goal feasibility cache."""
        self._goal_cache.clear()
        logger.debug("Feasibility cache cleared")

    def get_statistics(self) -> Dict[str, Any]:
        """Get statistics about the current system model and feasibility estimates.

        Returns:
            Dictionary with statistics.
        """
        return {
            "total_components": len(self.system_model.components),
            "total_interactions": len(self.system_model.interactions),
            "cached_goals": len(self._goal_cache),
            "blocked_goals": sum(
                1 for r in self._goal_cache.values()
                if r.status == FeasibilityStatus.BLOCKED
            ),
            "feasible_goals": sum(
                1 for r in self._goal_cache.values()
                if r.status == FeasibilityStatus.FEASIBLE
            ),
            "risky_goals": sum(
                1 for r in self._goal_cache.values()
                if r.status == FeasibilityStatus.RISKY
            ),
        }