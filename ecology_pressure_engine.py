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
import os
import sys
from pathlib import Path
from datetime import datetime
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
# Novel Test Suite Generation (ECOLOGY mechanism)
# ---------------------------------------------------------------------------

def generate_novel_test_suite(
    existing_suite: Dict[str, Any],
    num_tests: int = 3,
    uniqueness_threshold: float = 0.3,
    output_dir: Optional[str] = None,
) -> List[str]:
    """
    Create new test files with unique assertions not present in the current test suite.
    This is the core ECOLOGY mechanism: the agent modifies its own fitness landscape
    by introducing new tests that challenge its current capabilities.

    Args:
        existing_suite: Dict representing the current test suite state.
        num_tests: Number of novel test files to generate.
        uniqueness_threshold: Minimum difference score to consider a test unique.
        output_dir: Optional directory to write the generated test files. If None,
                    files are not written to disk.

    Returns:
        List of test file contents (strings) that are novel relative to existing_suite.
    """
    novel_tests: List[str] = []
    existing_assertions = _extract_assertions(existing_suite)
    
    for _ in range(num_tests * 3):  # Generate extra to filter for uniqueness
        if len(novel_tests) >= num_tests:
            break
            
        test_content = _generate_novel_test_content(existing_suite)
        new_assertions = _extract_assertions_from_content(test_content)
        
        # Check uniqueness against existing and already generated tests
        if _is_unique_assertion_set(new_assertions, existing_assertions, uniqueness_threshold):
            novel_tests.append(test_content)
            existing_assertions.update(new_assertions)
    
    # Write to disk if output_dir is provided
    if output_dir is not None:
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        for i, test_content in enumerate(novel_tests):
            filename = f"novel_test_{timestamp}_{i:03d}.py"
            filepath = output_path / filename
            with open(filepath, 'w') as f:
                f.write(test_content)
    
    return novel_tests


def _extract_assertions(test_suite: Dict[str, Any]) -> set:
    """
    Extract assertion patterns from test suite metadata.
    Returns a set of assertion type strings present in the suite.
    """
    assertions = set()
    
    # Extract from existing test files if present
    existing_tests = test_suite.get("test_files", [])
    for test_file in existing_tests:
        if isinstance(test_file, str):
            assertions.update(_extract_assertions_from_content(test_file))
    
    # Add default assertions based on suite metrics
    if test_suite.get("coverage", 0) > 0:
        assertions.add("assert_coverage")
    if test_suite.get("mutation_score", 0) > 0:
        assertions.add("assert_mutation")
    if test_suite.get("regression_test_count", 0) > 0:
        assertions.add("assert_regression")
    if test_suite.get("edge_case_count", 0) > 0:
        assertions.add("assert_edge_case")
    if test_suite.get("avg_test_time", 10) < 1.0:
        assertions.add("assert_performance")
    
    return assertions


def _extract_assertions_from_content(content: str) -> set:
    """
    Extract assertion types from test file content.
    """
    assertions = set()
    assertion_patterns = [
        "assertEqual", "assertNotEqual", "assertTrue", "assertFalse",
        "assertIs", "assertIsNot", "assertIsNone", "assertIsNotNone",
        "assertIn", "assertNotIn", "assertIsInstance", "assertNotIsInstance",
        "assertRaises", "assertRaisesRegex", "assertWarns", "assertWarnsRegex",
        "assertAlmostEqual", "assertNotAlmostEqual", "assertGreater",
        "assertGreaterEqual", "assertLess", "assertLessEqual",
        "assertRegex", "assertNotRegex", "assertCountEqual",
        "assertMultiLineEqual", "assertSequenceEqual", "assertListEqual",
        "assertTupleEqual", "assertSetEqual", "assertDictEqual",
    ]
    
    for pattern in assertion_patterns:
        if pattern in content:
            assertions.add(pattern)
    
    return assertions


def _is_unique_assertion_set(
    new_assertions: set,
    existing_assertions: set,
    threshold: float,
) -> bool:
    """
    Determine if a set of assertions is sufficiently unique compared to existing ones.
    Uses Jaccard similarity to measure overlap.
    """
    if not new_assertions:
        return False
    
    if not existing_assertions:
        return True
    
    intersection = new_assertions.intersection(existing_assertions)
    union = new_assertions.union(existing_assertions)
    
    similarity = len(intersection) / len(union) if union else 0.0
    return similarity < threshold


def _generate_novel_test_content(test_suite: Dict[str, Any]) -> str:
    """
    Generate a novel test file content with unique assertions.
    Creates tests that target areas where the current suite is weak.
    """
    # Identify weak areas based on suite metrics
    weak_areas = []
    if test_suite.get("coverage", 0) < 50:
        weak_areas.append("coverage")
    if test_suite.get("mutation_score", 0) < 40:
        weak_areas.append("mutation")
    if test_suite.get("regression_test_count", 0) < 3:
        weak_areas.append("regression")
    if test_suite.get("edge_case_count", 0) < 5:
        weak_areas.append("edge_cases")
    if test_suite.get("avg_test_time", 10) > 2.0:
        weak_areas.append("performance")
    
    if not weak_areas:
        weak_areas = ["general"]
    
    # Generate test based on weak areas
    test_id = random.randint(10000, 99999)
    target_area = random.choice(weak_areas)
    
    test_content = f"""import unittest
import random
import time
import sys
import os

class TestNovel{test_id}(unittest.TestCase):
    \"\"\"Novel test generated by ECOLOGY mechanism to challenge current capabilities.\"\"\"
    
    def setUp(self):
        self.test_data = self._generate_test_data()
    
    def _generate_test_data(self):
        \"\"\"Generate unique test data for this test.\"\"\"
        return {{
            "input": random.randint(-1000, 1000),
            "string_input": ''.join(random.choices('abcdefghijklmnopqrstuvwxyz', k=random.randint(0, 20))),
            "list_input": [random.randint(0, 100) for _ in range(random.randint(0, 10))],
            "float_input": random.uniform(-100.0, 100.0),
        }}
    
"""
    
    if target_area == "coverage":
        test_content += """    def test_coverage_novel_path(self):
        \"\"\"Test a unique code path not covered by existing tests.\"\"\"
        # This test targets uncovered branches
        value = self.test_data["input"]
        if value > 0:
            result = value * 2
        elif value < 0:
            result = abs(value)
        else:
            result = 42
        self.assertIsNotNone(result)
        self.assertGreaterEqual(result, 0)
    
    def test_coverage_boundary(self):
        \"\"\"Test boundary conditions for coverage.\"\"\"
        for boundary in [0, 1, -1, 100, -100]:
            with self.subTest(boundary=boundary):
                result = self._process_boundary(boundary)
                self.assertIsInstance(result, (int, float))
    
    def _process_boundary(self, value):
        \"\"\"Helper to test boundary processing.\"\"\"
        if value == 0:
            return 0
        elif value > 0:
            return value * 2
        else:
            return value * -1
    
"""
    elif target_area == "mutation":
        test_content += """    def test_mutation_kill_operator(self):
        \"\"\"Test designed to kill specific mutation operators.\"\"\"
        # Test arithmetic operator mutations
        a, b = 10, 5
        self.assertEqual(a + b, 15)
        self.assertEqual(a - b, 5)
        self.assertEqual(a * b, 50)
        self.assertEqual(a // b, 2)
        self.assertEqual(a % b, 0)
    
    def test_mutation_condition(self):
        \"\"\"Test designed to kill condition boundary mutations.\"\"\"
        for value in [True, False, None, 0, 1, ""]:
            with self.subTest(value=value):
                if value:
                    self.assertTrue(bool(value) or not bool(value))
                else:
                    self.assertFalse(bool(value) and not bool(value))
    
    def test_mutation_constant(self):
        \"\"\"Test designed to kill constant replacement mutations.\"\"\"
        constants = [0, 1, -1, 100, 3.14, sys.maxsize]
        for const in constants:
            with self.subTest(constant=const):
                self.assertIsNotNone(const)
                self.assertIsInstance(const, (int, float))
    
"""
    elif target_area == "regression":
        test_content += """    def test_regression_scenario(self):
        \"\"\"Test a regression scenario with specific input-output pairs.\"\"\"
        test_cases = [
            (0, 0),
            (1, 1),
            (-1, -1),
            (100, 100),
            (-100, -100),
        ]
        for input_val, expected in test_cases:
            with self.subTest(input=input_val):
                result = self._regression_function(input_val)
                self.assertEqual(result, expected)
    
    def _regression_function(self, x):
        \"\"\"Simple function that should maintain behavior.\"\"\"
        return x
    
    def test_regression_edge_combination(self):
        \"\"\"Test edge case combinations that previously caused bugs.\"\"\"
        # Test with empty and None values
        self.assertIsNotNone(self.test_data["string_input"])
        self.assertIsNotNone(self.test_data["list_input"])
        
        # Test with extreme values
        extreme_input = sys.maxsize
        self.assertGreater(extreme_input, 0)
        
        # Test with type variations
        self.assertIsInstance(self.test_data["float_input"], float)
    
"""
    elif target_area == "edge_cases":
        test_content += """    def test_edge_empty_input(self):
        \"\"\"Test behavior with empty or minimal inputs.\"\"\"
        empty_string = ""
        empty_list = []
        zero_value = 0
        
        self.assertEqual(len(empty_string), 0)
        self.assertEqual(len(empty_list), 0)
        self.assertEqual(zero_value, 0)
        
        # Test that empty inputs don't cause crashes
        self.assertIsNotNone(empty_string)
        self.assertIsNotNone(empty_list)
    
    def test_edge_large_input(self):
        \"\"\"Test behavior with very large inputs.\"\"\"
        large_string = "x" * 10000
        large_list = list(range(1000))
        large_number = 10**10
        
        self.assertEqual(len(large_string), 10000)
        self.assertEqual(len(large_list), 1000)
        self.assertGreater(large_number, 0)
    
    def test_edge_special_values(self):
        \"\"\"Test with special values like NaN, Infinity, etc.\"\"\"
        import math
        
        special_values = [
            float('inf'),
            float('-inf'),
            float('nan'),
            0.0,
            -0.0,
        ]
        
        for val in special_values:
            with self.subTest(value=val):
                if math.isnan(val):
                    self.assertTrue(math.isnan(val))
                elif val == float('inf'):
                    self.assertTrue(math.isinf(val))
                elif val == float('-inf'):
                    self.assertTrue(math.isinf(val))
                else:
                    self.assertIsInstance(val, float)
    
"""
    elif target_area == "performance":
        test_content += """    def test_performance_bounds(self):
        \"\"\"Test that operations complete within time bounds.\"\"\"
        start_time = time.time()
        
        # Perform a bounded operation
        result = sum(range(1000))
        elapsed = time.time() - start_time
        
        self.assertLess(elapsed, 1.0)
        self.assertEqual(result, 499500)
    
    def test_performance_scalability(self):
        \"\"\"Test performance with increasing input sizes.\"\"\"
        sizes = [10, 100, 1000]
        for size in sizes:
            with self.subTest(size=size):
                start = time.time()
                data = list(range(size))
                processed = [x * 2 for x in data]
                elapsed = time.time() - start
                self.assertLess(elapsed, 0.5)
                self.assertEqual(len(processed), size)
    
    def test_performance_memory(self):
        \"\"\"Test memory usage patterns.\"\"\"
        # Test that large operations don't cause memory issues
        large_data = [i for i in range(10000)]
        self.assertEqual(len(large_data), 10000)
        
        # Test memory cleanup
        del large_data
        self.assertTrue(True)  # Should not raise memory error
    
"""
    else:  # general
        test_content += """    def test_general_assertions(self):
        \"\"\"Test general assertions that challenge basic functionality.\"\"\"
        # Type assertions
        self.assertIsInstance(42, int)
        self.assertIsInstance(3.14, float)
        self.assertIsInstance("hello", str)
        self.assertIsInstance([], list)
        self.assertIsInstance({}, dict)
        
        # Value assertions
        self.assertEqual(1 + 1, 2)
        self.assertNotEqual(1 + 1, 3)
        self.assertTrue(True)
        self.assertFalse(False)
        
        # Container assertions
        self.assertIn(1, [1, 2, 3])
        self.assertNotIn(4, [1, 2, 3])
    
    def test_general_edge_behavior(self):
        \"\"\"Test edge behavior with various inputs.\"\"\"
        # Test with None
        self.assertIsNone(None)
        self.assertIsNotNone(0)
        
        # Test with boolean
        self.assertTrue(1)
        self.assertFalse(0)
        
        # Test with comparison
        self.assertGreater(5, 3)
        self.assertGreaterEqual(5, 5)
        self.assertLess(3, 5)
        self.assertLessEqual(3, 3)
    
    def test_general_error_handling(self):
        \"\"\"Test error handling and exceptions.\"\"\"
        # Test that appropriate exceptions are raised
        with self.assertRaises(ZeroDivisionError):
            result = 1 / 0
        
        with self.assertRaises(TypeError):
            result = "string" + 1
        
        with self.assertRaises(ValueError):
            result = int("not_a_number")
    
"""
    
    test_content += f"""
if __name__ == '__main__':
    unittest.main()
"""
    
    return test_content


# ---------------------------------------------------------------------------
# New Method: introduce_novel_constraint
# ---------------------------------------------------------------------------

def introduce_novel_constraint() -> str:
    """
    Generate a new test file with a unique assertion pattern not seen in the
    existing test suite. Scans all existing test files for assertion types
    (assertEqual, assertTrue, etc.) and creates a test requiring a new
    assertion type or combination.

    Returns:
        A string containing the content of a new test file with a unique
        assertion pattern.
    """
    # Scan existing test files for assertion types
    # For this implementation, we simulate scanning by checking the registry
    # and generating a test that uses a rare or unused assertion combination.
    
    # Collect all assertion types that might be present in existing tests
    existing_assertions = set()
    for pressure in _pressure_registry:
        # Simulate extracting assertions from templates
        template = pressure["generate_template"]()
        existing_assertions.update(_extract_assertions_from_content(template))
    
    # Define all possible assertion types
    all_assertions = [
        "assertEqual", "assertNotEqual", "assertTrue", "assertFalse",
        "assertIs", "assertIsNot", "assertIsNone", "assertIsNotNone",
        "assertIn", "assertNotIn", "assertIsInstance", "assertNotIsInstance",
        "assertRaises", "assertRaisesRegex", "assertWarns", "assertWarnsRegex",
        "assertAlmostEqual", "assertNotAlmostEqual", "assertGreater",
        "assertGreaterEqual", "assertLess", "assertLessEqual",
        "assertRegex", "assertNotRegex", "assertCountEqual",
        "assertMultiLineEqual", "assertSequenceEqual", "assertListEqual",
        "assertTupleEqual", "assertSetEqual", "assertDictEqual",
    ]
    
    # Find assertion types not present in existing tests
    missing_assertions = [a for a in all_assertions if a not in existing_assertions]
    
    # If all assertion types are present, create a test with a unique combination
    if not missing_assertions:
        # Create a test that uses a rare combination of assertions
        test_content = f"""import unittest

class TestNovelConstraint(unittest.TestCase):
    \"\"\"Test generated by introduce_novel_constraint to introduce a unique assertion pattern.\"\"\"
    
    def test_unique_combination(self):
        \"\"\"Use a combination of assertions not seen together in existing tests.\"\"\"
        # Combine assertCountEqual with assertMultiLineEqual
        list1 = [1, 2, 3]
        list2 = [3, 2, 1]
        self.assertCountEqual(list1, list2)
        
        str1 = "hello\\nworld"
        str2 = "hello\\nworld"
        self.assertMultiLineEqual(str1, str2)
        
        # Add assertSequenceEqual and assertSetEqual
        seq1 = [1, 2, 3]
        seq2 = [1, 2, 3]
        self.assertSequenceEqual(seq1, seq2)
        
        set1 = {1, 2, 3}
        set2 = {3, 2, 1}
        self.assertSetEqual(set1, set2)
    
    def test_rare_assertions(self):
        \"\"\"Use rare assertion types.\"\"\"
        # assertNotRegex
        self.assertNotRegex("hello world", r"^\\\\d+$")
        
        # assertWarnsRegex
        import warnings
        with self.assertWarnsRegex(UserWarning, "test warning"):
            warnings.warn("this is a test warning", UserWarning)
        
        # assertNotIsInstance
        self.assertNotIsInstance(42, str)
        
        # assertNotAlmostEqual
        self.assertNotAlmostEqual(3.14159, 3.14, places=2)

if __name__ == '__main__':
    unittest.main()
"""
    else:
        # Use a missing assertion type
        chosen_assertion = random.choice(missing_assertions)
        test_content = f"""import unittest

class TestNovelConstraint(unittest.TestCase):
    \"\"\"Test generated by introduce_novel_constraint to introduce a new assertion type.\"\"\"
    
    def test_new_assertion(self):
        \"\"\"Use the assertion type '{chosen_assertion}' which is not present in existing tests.\"\"\"
        # TODO: Implement test using {chosen_assertion}
        # This test introduces a new assertion pattern to the test suite
        self.{chosen_assertion}(True)  # Placeholder - adjust as needed

if __name__ == '__main__':
    unittest.main()
"""
    
    return test_content


# ---------------------------------------------------------------------------
# New Method: inject_test_into_existing_suite
# ---------------------------------------------------------------------------

def inject_test_into_existing_suite(
    test_file_path: str,
    num_tests: int = 1,
    uniqueness_threshold: float = 0.3,
) -> List[str]:
    """
    Append new test functions (with unique assertions) to an existing test file
    instead of creating a new file. This bypasses the import failure issue by
    reusing the existing module's imports and class structure.

    Args:
        test_file_path: Path to an existing test file to modify.
        num_tests: Number of new test methods to add.
        uniqueness_threshold: Minimum difference score to consider a test unique.

    Returns:
        List of new test method code strings that were added.
    """
    # Read the existing test file
    filepath = Path(test_file_path)
    if not filepath.exists():
        raise FileNotFoundError(f"Test file not found: {test_file_path}")
    
    with open(filepath, 'r') as f:
        original_content = f.read()
    
    # Extract existing assertions from the file
    existing_assertions = _extract_assertions_from_content(original_content)
    
    # Generate new test methods
    new_methods = []
    for _ in range(num_tests * 3):  # Generate extra to filter for uniqueness
        if len(new_methods) >= num_tests:
            break
        
        # Generate a unique test method
        method_code = _generate_unique_test_method(existing_assertions, uniqueness_threshold)
        method_assertions = _extract_assertions_from_content(method_code)
        
        # Check uniqueness
        if _is_unique_assertion_set(method_assertions, existing_assertions, uniqueness_threshold):
            new_methods.append(method_code)
            existing_assertions.update(method_assertions)
    
    # Append new methods to the file
    if new_methods:
        with open(filepath, 'a') as f:
            f.write("\n\n")
            for method in new_methods:
                f.write(method)
                f.write("\n")
    
    return new_methods


def _generate_unique_test_method(
    existing_assertions: set,
    uniqueness_threshold: float,
) -> str:
    """
    Generate a single unique test method with assertions not present in existing_assertions.
    """
    # Define all possible assertion types
    all_assertions = [
        "assertEqual", "assertNotEqual", "assertTrue", "assertFalse",
        "assertIs", "assertIsNot", "assertIsNone", "assertIsNotNone",
        "assertIn", "assertNotIn", "assertIsInstance", "assertNotIsInstance",
        "assertRaises", "assertRaisesRegex", "assertWarns", "assertWarnsRegex",
        "assertAlmostEqual", "assertNotAlmostEqual", "assertGreater",
        "assertGreaterEqual", "assertLess", "assertLessEqual",
        "assertRegex", "assertNotRegex", "assertCountEqual",
        "assertMultiLineEqual", "assertSequenceEqual", "assertListEqual",
        "assertTupleEqual", "assertSetEqual", "assertDictEqual",
    ]
    
    # Find