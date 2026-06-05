"""Goal Feasibility Estimator (Dependency-Aware)

Refactored capability #16: before accepting a goal, parse it to identify required
capabilities/modules, query the dependency graph for prerequisites, verify all
prerequisites are complete, log blocked goals with missing dependencies to the
failure analysis module, and return a feasibility score that penalizes incomplete
dependencies.
"""

from typing import Dict, List, Tuple, Optional, Any
import logging

from evolution_engine.dependency_graph import DependencyGraph
from evolution_engine.failure_analysis import FailureAnalysisModule

logger = logging.getLogger(__name__)


class GoalFeasibilityEstimator:
    """Estimates feasibility of goals with dependency awareness."""

    def __init__(self, dependency_graph: DependencyGraph, failure_analysis: FailureAnalysisModule):
        self.dependency_graph = dependency_graph
        self.failure_analysis = failure_analysis
        self._goal_parser = GoalParser()

    def check_dependency_prerequisites(self, goal: Any) -> Tuple[bool, List[str]]:
        """
        Check if all prerequisites for a goal are complete.

        Args:
            goal: The goal object or string to evaluate.

        Returns:
            Tuple of (feasible: bool, missing_deps: list of missing prerequisite identifiers)
        """
        required_capabilities = self._goal_parser.extract_required_capabilities(goal)
        missing_deps = []

        for capability in required_capabilities:
            prerequisites = self.dependency_graph.get_prerequisites(capability)
            for prereq in prerequisites:
                if not self.dependency_graph.is_complete(prereq):
                    missing_deps.append(prereq)

        if missing_deps:
            logger.warning(f"Goal blocked by missing dependencies: {missing_deps}")
            self.failure_analysis.log_blocked_goal(goal, missing_deps)
            return False, missing_deps

        return True, []

    def estimate_feasibility(self, goal: Any) -> float:
        """
        Compute a feasibility score for the given goal.

        The score is 1.0 if all dependencies are satisfied, otherwise it is
        penalized proportionally to the number of missing dependencies.

        Args:
            goal: The goal object or string.

        Returns:
            A float between 0.0 (infeasible) and 1.0 (fully feasible).
        """
        feasible, missing_deps = self.check_dependency_prerequisites(goal)
        if feasible:
            return 1.0

        # Penalize: each missing dependency reduces score by 0.2, minimum 0.0
        penalty = min(len(missing_deps) * 0.2, 1.0)
        return max(0.0, 1.0 - penalty)


class GoalParser:
    """Parses goals to extract required capabilities/modules."""

    def extract_required_capabilities(self, goal: Any) -> List[str]:
        """
        Extract a list of required capability/module identifiers from a goal.

        Supports:
        - String goals: parsed as comma/space separated capability names.
        - Dict goals: expects a 'requires' key with a list of strings.
        - Objects with a 'requires' attribute (list of strings).

        Args:
            goal: The goal representation.

        Returns:
            List of capability identifiers (strings).
        """
        if isinstance(goal, str):
            # Simple parsing: split by commas or whitespace
            tokens = goal.replace(",", " ").split()
            return [t.strip() for t in tokens if t.strip()]

        if isinstance(goal, dict):
            raw = goal.get("requires", [])
            if isinstance(raw, list):
                return [str(r) for r in raw]
            return [str(raw)]

        if hasattr(goal, "requires"):
            raw = goal.requires
            if isinstance(raw, list):
                return [str(r) for r in raw]
            return [str(raw)]

        logger.warning(f"Unrecognized goal format: {type(goal)}. Returning empty requirements.")
        return []