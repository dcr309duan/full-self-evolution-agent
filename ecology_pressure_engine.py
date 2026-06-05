#!/usr/bin/env python3
"""
ecology_pressure_engine.py

A standalone module for defining, evaluating, and generating environmental pressures
for test suites. No external dependencies beyond Python standard library.

Environmental pressures represent constraints or requirements that a test suite
should satisfy, such as minimum coverage, mutation diversity, performance bounds, etc.
"""

import hashlib
import math
import random
import time
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

# ---------------------------------------------------------------------------
# Pressure Registry
# ---------------------------------------------------------------------------

# Each pressure is a dict with keys:
#   name: str
#   description: str
#   severity: float (0.0 = low, 1.0 = critical)
#   evaluate: Callable[[dict], float]  # returns 0.0 (fail) to 1.0 (pass)
#   generate_template: Callable[[], str]  # returns a test template string

_pressure_registry: List[Dict[str, Any]] = []


def register_pressure(
    name: str,
    description: str,
    severity: float,
    evaluate: Callable[[Dict[str, Any]], float],
    generate_template: Callable[[], str],
) -> None:
    """Register a new environmental pressure."""
    _pressure_registry.append({
        "name": name,
        "description": description,
        "severity": max(0.0, min(1.0, severity)),
        "evaluate": evaluate,
        "generate_template": generate_template,
    })


def get_pressure(name: str) -> Optional[Dict[str, Any]]:
    """Retrieve a pressure by name."""
    for p in _pressure_registry:
        if p["name"] == name:
            return p
    return None


def list_pressures() -> List[str]:
    """Return names of all registered pressures."""
    return [p["name"] for p in _pressure_registry]


def clear_pressures() -> None:
    """Remove all registered pressures (useful for testing)."""
    _pressure_registry.clear()


# ---------------------------------------------------------------------------
# Built-in pressure: Test Coverage Minimum
# ---------------------------------------------------------------------------

def _evaluate_coverage(test_suite: Dict[str, Any]) -> float:
    """
    Evaluate test coverage pressure.
    Expects test_suite to have a 'coverage' key (float 0-100).
    Returns 1.0 if coverage >= 80, scales linearly below that.
    """
    coverage = test_suite.get("coverage", 0.0)
    if coverage >= 80.0:
        return 1.0
    elif coverage <= 0.0:
        return 0.0
    else:
        return coverage / 80.0


def _generate_coverage_template() -> str:
    """Generate a test template that helps increase coverage."""
    module_name = f"module_{random.randint(1000,9999)}"
    return (
        f"import unittest\n"
        f"from {module_name} import *\n\n"
        f"class TestCoverage(unittest.TestCase):\n"
        f"    def test_coverage_increase(self):\n"
        f"        # TODO: Add test cases to increase coverage\n"
        f"        self.assertTrue(True)\n\n"
        f"if __name__ == '__main__':\n"
        f"    unittest.main()\n"
    )


register_pressure(
    name="test_coverage_minimum",
    description="Requires test coverage >= 80%",
    severity=0.9,
    evaluate=_evaluate_coverage,
    generate_template=_generate_coverage_template,
)


# ---------------------------------------------------------------------------
# Built-in pressure: Mutation Diversity Requirement
# ---------------------------------------------------------------------------

def _evaluate_mutation_diversity(test_suite: Dict[str, Any]) -> float:
    """
    Evaluate mutation diversity pressure.
    Expects test_suite to have a 'mutation_score' key (float 0-100).
    Returns 1.0 if score >= 70, scales linearly below.
    """
    score = test_suite.get("mutation_score", 0.0)
    if score >= 70.0:
        return 1.0
    elif score <= 0.0:
        return 0.0
    else:
        return score / 70.0


def _generate_mutation_template() -> str:
    """Generate a test template for mutation diversity."""
    return (
        f"import unittest\n"
        f"import random\n\n"
        f"class TestMutationDiversity(unittest.TestCase):\n"
        f"    def test_mutant_killing(self):\n"
        f"        # TODO: Add assertions that kill mutants\n"
        f"        result = some_function(random.randint(0,100))\n"
        f"        self.assertIsNotNone(result)\n\n"
        f"if __name__ == '__main__':\n"
        f"    unittest.main()\n"
    )


register_pressure(
    name="mutation_diversity_requirement",
    description="Requires mutation score >= 70%",
    severity=0.8,
    evaluate=_evaluate_mutation_diversity,
    generate_template=_generate_mutation_template,
)


# ---------------------------------------------------------------------------
# Built-in pressure: Performance Constraints
# ---------------------------------------------------------------------------

def _evaluate_performance(test_suite: Dict[str, Any]) -> float:
    """
    Evaluate performance pressure.
    Expects test_suite to have 'avg_test_time' (float seconds) and
    'max_test_time' (float seconds).
    Returns 1.0 if avg < 0.5 and max < 2.0, scales down otherwise.
    """
    avg_time = test_suite.get("avg_test_time", 10.0)
    max_time = test_suite.get("max_test_time", 10.0)

    avg_ok = max(0.0, 1.0 - avg_time / 0.5) if avg_time > 0 else 0.0
    max_ok = max(0.0, 1.0 - max_time / 2.0) if max_time > 0 else 0.0

    return min(1.0, (avg_ok + max_ok) / 2.0)


def _generate_performance_template() -> str:
    """Generate a test template for performance constraints."""
    return (
        f"import unittest\n"
        f"import time\n\n"
        f"class TestPerformance(unittest.TestCase):\n"
        f"    def test_execution_time(self):\n"
        f"        start = time.time()\n"
        f"        # TODO: Call the function to test\n"
        f"        result = some_function()\n"
        f"        elapsed = time.time() - start\n"
        f"        self.assertLess(elapsed, 0.5)\n\n"
        f"if __name__ == '__main__':\n"
        f"    unittest.main()\n"
    )


register_pressure(
    name="performance_constraints",
    description="Requires avg test time < 0.5s and max < 2.0s",
    severity=0.7,
    evaluate=_evaluate_performance,
    generate_template=_generate_performance_template,
)


# ---------------------------------------------------------------------------
# Built-in pressure: Edge Case Coverage
# ---------------------------------------------------------------------------

def _evaluate_edge_cases(test_suite: Dict[str, Any]) -> float:
    """
    Evaluate edge case coverage pressure.
    Expects test_suite to have 'edge_case_count' (int) and
    'total_edge_cases' (int).
    Returns proportion covered.
    """
    covered = test_suite.get("edge_case_count", 0)
    total = test_suite.get("total_edge_cases", 1)
    if total <= 0:
        return 1.0
    return min(1.0, covered / total)


def _generate_edge_case_template() -> str:
    """Generate a test template for edge cases."""
    return (
        f"import unittest\n\n"
        f"class TestEdgeCases(unittest.TestCase):\n"
        f"    def test_empty_input(self):\n"
        f"        # TODO: Test with empty input\n"
        f"        self.assertRaises(ValueError, some_function, '')\n\n"
        f"    def test_large_input(self):\n"
        f"        # TODO: Test with very large input\n"
        f"        large_input = 'x' * 10000\n"
        f"        result = some_function(large_input)\n"
        f"        self.assertIsNotNone(result)\n\n"
        f"if __name__ == '__main__':\n"
        f"    unittest.main()\n"
    )


register_pressure(
    name="edge_case_coverage",
    description="Requires coverage of all identified edge cases",
    severity=0.6,
    evaluate=_evaluate_edge_cases,
    generate_template=_generate_edge_case_template,
)


# ---------------------------------------------------------------------------
# Built-in pressure: Regression Test Presence
# ---------------------------------------------------------------------------

def _evaluate_regression(test_suite: Dict[str, Any]) -> float:
    """
    Evaluate regression test presence pressure.
    Expects test_suite to have 'regression_test_count' (int).
    Returns 1.0 if count >= 5, scales linearly below.
    """
    count = test_suite.get("regression_test_count", 0)
    if count >= 5:
        return 1.0
    elif count <= 0:
        return 0.0
    else:
        return count / 5.0


def _generate_regression_template() -> str:
    """Generate a test template for regression tests."""
    return (
        f"import unittest\n\n"
        f"class TestRegression(unittest.TestCase):\n"
        f"    def test_regression_scenario_1(self):\n"
        f"        # TODO: Add regression test for known bug #1\n"
        f"        self.assertTrue(True)\n\n"
        f"if __name__ == '__main__':\n"
        f"    unittest.main()\n"
    )


register_pressure(
    name="regression_test_presence",
    description="Requires at least 5 regression tests",
    severity=0.5,
    evaluate=_evaluate_regression,
    generate_template=_generate_regression_template,
)


# ---------------------------------------------------------------------------
# Evaluation Functions
# ---------------------------------------------------------------------------

def evaluate_test_suite(
    test_suite: Dict[str, Any],
    pressure_names: Optional[List[str]] = None,
) -> Dict[str, float]:
    """
    Evaluate a test suite against registered pressures.

    Args:
        test_suite: Dict with keys expected by pressure evaluators.
        pressure_names: Optional list of pressure names to evaluate.
                        If None, evaluates all registered pressures.

    Returns:
        Dict mapping pressure names to scores (0.0 to 1.0).
    """
    results: Dict[str, float] = {}
    pressures_to_evaluate = _pressure_registry

    if pressure_names is not None:
        pressures_to_evaluate = [
            p for p in _pressure_registry if p["name"] in pressure_names
        ]

    for pressure in pressures_to_evaluate:
        try:
            score = pressure["evaluate"](test_suite)
            results[pressure["name"]] = max(0.0, min(1.0, score))
        except Exception as e:
            results[pressure["name"]] = 0.0

    return results


def evaluate_test_suite_weighted(
    test_suite: Dict[str, Any],
    pressure_names: Optional[List[str]] = None,
) -> Tuple[float, Dict[str, float]]:
    """
    Evaluate test suite and return a weighted overall score.

    Returns:
        Tuple of (overall_score, individual_scores).
    """
    scores = evaluate_test_suite(test_suite, pressure_names)
    if not scores:
        return 1.0, {}

    total_weight = 0.0
    weighted_sum = 0.0

    for pressure in _pressure_registry:
        name = pressure["name"]
        if name in scores:
            weight = pressure["severity"]
            weighted_sum += scores[name] * weight
            total_weight += weight

    if total_weight == 0.0:
        return 0.0, scores

    overall = weighted_sum / total_weight
    return overall, scores


# ---------------------------------------------------------------------------
# Template Generation
# ---------------------------------------------------------------------------

def generate_missing_pressure_templates(
    test_suite: Dict[str, Any],
    threshold: float = 0.5,
    max_templates: int = 5,
) -> List[Tuple[str, str, str]]:
    """
    Generate test templates for pressures that are below the threshold.

    Args:
        test_suite: Dict with test suite data.
        threshold: Score below which a pressure is considered 'missing'.
        max_templates: Maximum number of templates to generate.

    Returns:
        List of tuples: (pressure_name, pressure_description, template_code).
    """
    scores = evaluate_test_suite(test_suite)
    templates: List[Tuple[str, str, str]] = []

    for pressure in _pressure_registry:
        if len(templates) >= max_templates:
            break
        name = pressure["name"]
        score = scores.get(name, 0.0)
        if score < threshold:
            template_code = pressure["generate_template"]()
            templates.append((name, pressure["description"], template_code))

    return templates


def generate_all_templates() -> List[Tuple[str, str, str]]:
    """Generate templates for all registered pressures."""
    templates: List[Tuple[str, str, str]] = []
    for pressure in _pressure_registry:
        template_code = pressure["generate_template"]()
        templates.append((pressure["name"], pressure["description"], template_code))
    return templates


# ---------------------------------------------------------------------------
# Utility: Create a default test suite profile
# ---------------------------------------------------------------------------

def create_default_test_suite() -> Dict[str, Any]:
    """
    Create a default test suite dict with typical keys.
    Useful for testing or as a starting point.
    """
    return {
        "coverage": 0.0,
        "mutation_score": 0.0,
        "avg_test_time": 10.0,
        "max_test_time": 10.0,
        "edge_case_count": 0,
        "total_edge_cases": 10,
        "regression_test_count": 0,
        "test_count": 0,
        "pass_rate": 1.0,
    }


# ---------------------------------------------------------------------------
# Utility: Generate a unique pressure ID (for tracking)
# ---------------------------------------------------------------------------

def generate_pressure_id(pressure_name: str, seed: Optional[str] = None) -> str:
    """Generate a deterministic unique ID for a pressure instance."""
    raw = f"{pressure_name}:{seed or str(time.time())}"
    return hashlib.sha256(raw.encode()).hexdigest()[:12]


# ---------------------------------------------------------------------------
# Self-test (if run directly)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("Ecology Pressure Engine Self-Test")
    print("=" * 40)

    # List registered pressures
    print(f"Registered pressures: {list_pressures()}")

    # Create a default test suite
    suite = create_default_test_suite()
    print(f"Default suite: {suite}")

    # Evaluate
    overall, scores = evaluate_test_suite_weighted(suite)
    print(f"Weighted score: {overall:.3f}")
    for name, score in scores.items():
        print(f"  {name}: {score:.3f}")

    # Generate missing templates
    templates = generate_missing_pressure_templates(suite, threshold=0.5, max_templates=3)
    print(f"\nGenerated {len(templates)} missing pressure templates:")
    for name, desc, code in templates:
        print(f"\n--- {name}: {desc} ---")
        print(code[:200] + "...")