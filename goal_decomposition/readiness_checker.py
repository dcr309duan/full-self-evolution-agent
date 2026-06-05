"""Readiness checker for goal decomposition components.

Evaluates the readiness of each component based on test coverage,
interface completeness, and existing implementation status.
"""

from typing import Dict, Optional
from dataclasses import dataclass, field

from goal_decomposition.schema_extractor import SchemaExtractor
from goal_decomposition.test_suite import TestSuite


@dataclass
class ReadinessResult:
    """Result of a readiness check for a single component."""
    component_name: str
    test_coverage: float = 0.0
    interface_completeness: float = 0.0
    has_existing_implementation: bool = False
    readiness_score: float = 0.0
    details: Dict[str, any] = field(default_factory=dict)


class ReadinessChecker:
    """Evaluates readiness of components based on multiple criteria."""

    # Weights for each factor in the readiness score
    TEST_COVERAGE_WEIGHT = 0.4
    INTERFACE_COMPLETENESS_WEIGHT = 0.4
    IMPLEMENTATION_WEIGHT = 0.2

    def __init__(
        self,
        test_suite: Optional[TestSuite] = None,
        schema_extractor: Optional[SchemaExtractor] = None,
    ):
        """Initialize with optional test suite and schema extractor.

        Args:
            test_suite: TestSuite instance for checking test coverage
            schema_extractor: SchemaExtractor instance for checking interfaces
        """
        self.test_suite = test_suite or TestSuite()
        self.schema_extractor = schema_extractor or SchemaExtractor()

    def check_component(
        self,
        component_name: str,
        existing_implementations: Optional[Dict[str, bool]] = None,
    ) -> ReadinessResult:
        """Check readiness of a single component.

        Args:
            component_name: Name of the component to check
            existing_implementations: Optional dict mapping component names
                to whether they have existing implementations

        Returns:
            ReadinessResult with all readiness metrics
        """
        result = ReadinessResult(component_name=component_name)

        # 1. Check test coverage from test suite
        test_coverage = self.test_suite.get_coverage(component_name)
        result.test_coverage = test_coverage
        result.details["test_count"] = self.test_suite.get_test_count(component_name)

        # 2. Verify interface completeness from schema extractor
        interface_completeness = self.schema_extractor.get_completeness(component_name)
        result.interface_completeness = interface_completeness
        result.details["interface_details"] = self.schema_extractor.get_interface_details(component_name)

        # 3. Check for existing implementations
        if existing_implementations:
            result.has_existing_implementation = existing_implementations.get(component_name, False)
        else:
            # Try to detect implementation automatically
            result.has_existing_implementation = self._detect_implementation(component_name)

        # 4. Assign readiness score
        result.readiness_score = self._calculate_readiness_score(result)

        return result

    def check_all_components(
        self,
        component_names: list[str],
        existing_implementations: Optional[Dict[str, bool]] = None,
    ) -> Dict[str, ReadinessResult]:
        """Check readiness of multiple components.

        Args:
            component_names: List of component names to check
            existing_implementations: Optional dict mapping component names
                to whether they have existing implementations

        Returns:
            Dict mapping component names to their ReadinessResult
        """
        results = {}
        for name in component_names:
            results[name] = self.check_component(name, existing_implementations)
        return results

    def _calculate_readiness_score(self, result: ReadinessResult) -> float:
        """Calculate overall readiness score from individual metrics.

        Score is a weighted combination of:
        - Test coverage (40%)
        - Interface completeness (40%)
        - Implementation status (20%)

        Args:
            result: ReadinessResult with individual metrics

        Returns:
            Float between 0.0 and 1.0
        """
        score = (
            result.test_coverage * self.TEST_COVERAGE_WEIGHT
            + result.interface_completeness * self.INTERFACE_COMPLETENESS_WEIGHT
            + (1.0 if result.has_existing_implementation else 0.0)
            * self.IMPLEMENTATION_WEIGHT
        )
        return min(max(score, 0.0), 1.0)

    def _detect_implementation(self, component_name: str) -> bool:
        """Attempt to detect if an implementation exists for the component.

        This is a simple heuristic check. Override in subclasses for
        more sophisticated detection.

        Args:
            component_name: Name of the component

        Returns:
            True if implementation appears to exist, False otherwise
        """
        # Basic heuristic: check if there's a module with the component name
        try:
            __import__(f"goal_decomposition.{component_name}")
            return True
        except (ImportError, ValueError):
            return False

    def get_summary(self, results: Dict[str, ReadinessResult]) -> Dict[str, any]:
        """Generate a summary of readiness results.

        Args:
            results: Dict of component names to ReadinessResult

        Returns:
            Dict with summary statistics
        """
        if not results:
            return {
                "total_components": 0,
                "average_readiness": 0.0,
                "ready_components": [],
                "needs_work": [],
            }

        scores = [r.readiness_score for r in results.values()]
        average = sum(scores) / len(scores)

        return {
            "total_components": len(results),
            "average_readiness": round(average, 3),
            "ready_components": [
                name for name, r in results.items()
                if r.readiness_score >= 0.7
            ],
            "needs_work": [
                name for name, r in results.items()
                if r.readiness_score < 0.7
            ],
        }