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
import json
import ast
import subprocess
import tempfile
from pathlib import Path
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

# ---------------------------------------------------------------------------
# Import and delegate to ecology_minimal_core
# ---------------------------------------------------------------------------

try:
    from ecology_minimal_core import (
        EcologyMinimalCore,
        TestSuiteEvolver,
        evaluate_test_suite as core_evaluate,
        generate_novel_test_suite as core_generate_novel,
        register_pressure as core_register_pressure,
        get_pressure as core_get_pressure,
        list_pressures as core_list_pressures,
        clear_pressures as core_clear_pressures,
        generate_missing_pressure_templates as core_generate_templates,
        generate_all_templates as core_generate_all_templates,
        introduce_novel_constraint as core_introduce_constraint,
        inject_test_into_existing_suite as core_inject_test,
        _pressure_registry as core_registry,
    )
    _minimal_core_available = True
except ImportError:
    _minimal_core_available = False
    # Define stub classes/functions if minimal core not available
    class EcologyMinimalCore:
        """Stub implementation when ecology_minimal_core is not available."""
        def __init__(self, *args, **kwargs):
            pass
        def run_self_test(self) -> bool:
            return False
        def get_status(self) -> Dict[str, Any]:
            return {"status": "unavailable"}
    
    class TestSuiteEvolver:
        """Stub implementation when ecology_minimal_core is not available."""
        def __init__(self, *args, **kwargs):
            pass
        def evolve(self, test_suite: Dict[str, Any]) -> Dict[str, Any]:
            return test_suite
    
    def core_evaluate(test_suite, pressure_names=None):
        return {}
    
    def core_generate_novel(existing_suite, num_tests=3, uniqueness_threshold=0.3, output_dir=None):
        return []
    
    def core_register_pressure(name, description, severity, evaluate, generate_template):
        pass
    
    def core_get_pressure(name):
        return None
    
    def core_list_pressures():
        return []
    
    def core_clear_pressures():
        pass
    
    def core_generate_templates(test_suite, threshold=0.5, max_templates=5):
        return []
    
    def core_generate_all_templates():
        return []
    
    def core_introduce_constraint():
        return ""
    
    def core_inject_test(test_file_path, num_tests=1, uniqueness_threshold=0.3):
        return []
    
    core_registry = []

# ---------------------------------------------------------------------------
# Import TestSuiteMutator with fallback
# ---------------------------------------------------------------------------

try:
    from test_suite_evolution import TestSuiteMutator
except ImportError:
    try:
        # Fallback import path
        from core.test_suite_evolution import TestSuiteMutator
    except ImportError:
        # Simple stub if import fails
        class TestSuiteMutator:
            """Stub implementation when TestSuiteMutator is not available."""
            
            def __init__(self, *args, **kwargs):
                pass
            
            def mutate(self, test_suite: Dict[str, Any]) -> Dict[str, Any]:
                """Return the test suite unchanged."""
                return test_suite
            
            def evolve(self, test_suite: Dict[str, Any]) -> Dict[str, Any]:
                """Return the test suite unchanged."""
                return test_suite

# ---------------------------------------------------------------------------
# Import EcologyEngine (consolidated)
# ---------------------------------------------------------------------------

try:
    from ecology_engine import EcologyEngine
    _ecology_engine_available = True
except ImportError:
    _ecology_engine_available = False
    # Stub for EcologyEngine if not available
    class EcologyEngine:
        """Stub implementation when ecology_engine is not available."""
        def __init__(self, *args, **kwargs):
            pass
        def run_self_test(self) -> bool:
            return False
        def get_status(self) -> Dict[str, Any]:
            return {"status": "unavailable"}
        def evaluate_test_suite(self, test_suite: Dict[str, Any], pressure_names: Optional[List[str]] = None) -> Dict[str, float]:
            return {}
        def generate_novel_test_suite(self, existing_suite: Dict[str, Any], num_tests: int = 3, uniqueness_threshold: float = 0.3, output_dir: Optional[str] = None) -> List[str]:
            return []
        def introduce_novel_constraint(self) -> str:
            return ""
        def inject_test_into_existing_suite(self, test_file_path: str, num_tests: int = 1, uniqueness_threshold: float = 0.3) -> List[str]:
            return []
        def register_pressure(self, name: str, description: str, severity: float, evaluate: Callable[[Dict[str, Any]], float], generate_template: Callable[[], str]) -> None:
            pass
        def get_pressure(self, name: str) -> Optional[Dict[str, Any]]:
            return None
        def list_pressures(self) -> List[str]:
            return []
        def clear_pressures(self) -> None:
            pass
        def generate_missing_pressure_templates(self, test_suite: Dict[str, Any], threshold: float = 0.5, max_templates: int = 5) -> List[Tuple[str, str, str]]:
            return []
        def generate_all_templates(self) -> List[Tuple[str, str, str]]:
            return []
        def introduce_environmental_pressure(self, test_dir: str = "tests", source_dir: str = ".", output_dir: Optional[str] = None, timeout: float = 5.0) -> Dict[str, Any]:
            return {"errors": ["EcologyEngine not available"]}
        def evolve_test_suite(self, test_dir: str = "tests", source_dir: str = ".", output_dir: Optional[str] = None, max_stubs: int = 5) -> Dict[str, Any]:
            return {"errors": ["EcologyEngine not available"]}

# ---------------------------------------------------------------------------
# Pressure Registry (delegates to minimal core)
# ---------------------------------------------------------------------------

_pressure_registry = core_registry


def register_pressure(
    name: str,
    description: str,
    severity: float,
    evaluate: Callable[[Dict[str, Any]], float],
    generate_template: Callable[[], str],
) -> None:
    """Register a new environmental pressure (delegates to minimal core)."""
    core_register_pressure(name, description, severity, evaluate, generate_template)


def get_pressure(name: str) -> Optional[Dict[str, Any]]:
    """Retrieve a pressure by name (delegates to minimal core)."""
    return core_get_pressure(name)


def list_pressures() -> List[str]:
    """Return names of all registered pressures (delegates to minimal core)."""
    return core_list_pressures()


def clear_pressures() -> None:
    """Remove all registered pressures (delegates to minimal core)."""
    core_clear_pressures()


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
# Evaluation Functions (delegate to minimal core)
# ---------------------------------------------------------------------------

def evaluate_test_suite(
    test_suite: Dict[str, Any],
    pressure_names: Optional[List[str]] = None,
) -> Dict[str, float]:
    """
    Evaluate a test suite against registered pressures (delegates to minimal core).

    Args:
        test_suite: Dict with keys expected by pressure evaluators.
        pressure_names: Optional list of pressure names to evaluate.
                        If None, evaluates all registered pressures.

    Returns:
        Dict mapping pressure names to scores (0.0 to 1.0).
    """
    return core_evaluate(test_suite, pressure_names)


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
# Template Generation (delegate to minimal core)
# ---------------------------------------------------------------------------

def generate_missing_pressure_templates(
    test_suite: Dict[str, Any],
    threshold: float = 0.5,
    max_templates: int = 5,
) -> List[Tuple[str, str, str]]:
    """
    Generate test templates for pressures that are below the threshold (delegates to minimal core).

    Args:
        test_suite: Dict with test suite data.
        threshold: Score below which a pressure is considered 'missing'.
        max_templates: Maximum number of templates to generate.

    Returns:
        List of tuples: (pressure_name, pressure_description, template_code).
    """
    return core_generate_templates(test_suite, threshold, max_templates)


def generate_all_templates() -> List[Tuple[str, str, str]]:
    """Generate templates for all registered pressures (delegates to minimal core)."""
    return core_generate_all_templates()


# ---------------------------------------------------------------------------
# Novel Test Suite Generation (delegate to minimal core)
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
    return core_generate_novel(existing_suite, num_tests, uniqueness_threshold, output_dir)


# ---------------------------------------------------------------------------
# New Method: introduce_novel_constraint (delegate to minimal core)
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
    return core_introduce_constraint()


# ---------------------------------------------------------------------------
# New Method: inject_test_into_existing_suite (delegate to minimal core)
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
    return core_inject_test(test_file_path, num_tests, uniqueness_threshold)


# ---------------------------------------------------------------------------
# New Method: generate_new_benchmark
# ---------------------------------------------------------------------------

def generate_new_benchmark(
    output_dir: str = "tests",
    coverage_gaps: Optional[Dict[str, List[str]]] = None,
    num_edge_cases: int = 5,
) -> Dict[str, Any]:
    """
    Create a new test file with randomized edge cases based on current coverage gaps.
    Includes import validation before writing.

    Args:
        output_dir: Directory to write the new benchmark test file.
        coverage_gaps: Optional dict mapping module names to lists of uncovered functions/classes.
                       If None, scans the source directory to identify gaps.
        num_edge_cases: Number of edge case tests to generate.

    Returns:
        Dict with results: {
            "test_file_path": str,
            "module_name": str,
            "edge_cases_generated": int,
            "import_valid": bool,
            "validation_errors": List[str]
        }
    """
    result = {
        "test_file_path": "",
        "module_name": "",
        "edge_cases_generated": 0,
        "import_valid": False,
        "validation_errors": []
    }

    # Step 1: Identify coverage gaps if not provided
    if coverage_gaps is None:
        coverage_gaps = _identify_coverage_gaps()

    if not coverage_gaps:
        result["validation_errors"].append("No coverage gaps identified")
        return result

    # Step 2: Randomly select a module with coverage gaps
    module_name = random.choice(list(coverage_gaps.keys()))
    uncovered_items = coverage_gaps[module_name]
    result["module_name"] = module_name

    # Step 3: Generate randomized edge case tests
    edge_case_tests = []
    for i in range(num_edge_cases):
        edge_case = _generate_random_edge_case(module_name, uncovered_items)
        edge_case_tests.append(edge_case)

    # Step 4: Build the test file content
    test_code = _build_benchmark_test_file(module_name, edge_case_tests)

    # Step 5: Validate imports before writing
    import_valid, validation_errors = _validate_imports(test_code, module_name)
    result["import_valid"] = import_valid
    result["validation_errors"] = validation_errors

    if not import_valid:
        # Attempt to fix import issues
        test_code = _fix_imports(test_code, module_name)
        import_valid, validation_errors = _validate_imports(test_code, module_name)
        result["import_valid"] = import_valid
        result["validation_errors"] = validation_errors

    # Step 6: Write the test file
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    test_file_name = f"benchmark_{module_name}_{random.randint(1000,9999)}.py"
    test_file_path = output_path / test_file_name

    try:
        with open(test_file_path, "w") as f:
            f.write(test_code)
        result["test_file_path"] = str(test_file_path)
        result["edge_cases_generated"] = len(edge_case_tests)
    except OSError as e:
        result["validation_errors"].append(f"Failed to write test file: {str(e)}")

    # Log the benchmark generation
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "action": "generate_new_benchmark",
        "module_name": module_name,
        "test_file_path": result["test_file_path"],
        "edge_cases_generated": result["edge_cases_generated"],
        "import_valid": result["import_valid"]
    }
    _log_evolution_change(log_entry)

    return result


def _identify_coverage_gaps(source_dir: str = ".") -> Dict[str, List[str]]:
    """
    Identify coverage gaps by scanning source modules and comparing with existing tests.

    Args:
        source_dir: Directory containing source modules.

    Returns:
        Dict mapping module names to lists of uncovered functions/classes.
    """
    gaps = {}
    source_modules = _find_source_modules(source_dir)
    test_files = _scan_test_files()

    for module_name, module_path in source_modules.items():
        # Parse the module to find functions and classes
        module_items = []
        try:
            with open(module_path, "r") as f:
                tree = ast.parse(f.read(), filename=str(module_path))
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and not node.name.startswith("_"):
                    module_items.append(node.name)
                elif isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
                    module_items.append(node.name)
        except (SyntaxError, FileNotFoundError):
            continue

        # Check which items are covered by existing tests
        uncovered_items = []
        for item in module_items:
            covered = False
            for test_file in test_files:
                try:
                    with open(test_file, "r") as f:
                        test_content = f.read()
                    if item in test_content:
                        covered = True
                        break
                except (OSError, UnicodeDecodeError):
                    continue
            if not covered:
                uncovered_items.append(item)

        if uncovered_items:
            gaps[module_name] = uncovered_items

    return gaps


def _generate_random_edge_case(module_name: str, uncovered_items: List[str]) -> str:
    """
    Generate a random edge case test for an uncovered item.

    Args:
        module_name: Name of the module being tested.
        uncovered_items: List of uncovered functions/classes.

    Returns:
        String containing the edge case test code.
    """
    if not uncovered_items:
        item = "some_function"
    else:
        item = random.choice(uncovered_items)

    edge_case_types = [
        "empty_input",
        "large_input",
        "negative_input",
        "null_input",
        "type_mismatch",
        "boundary_value",
        "special_characters",
        "max_int",
        "min_int",
        "float_precision"
    ]

    edge_case_type = random.choice(edge_case_types)

    test_templates = {
        "empty_input": f"""
    def test_{item}_empty_input(self):
        \"\"\"Test {item} with empty input.\"\"\"
        try:
            result = {item}('')
            self.assertIsNotNone(result)
        except Exception as e:
            self.fail(f"{item} raised an exception with empty input: {{e}}")
""",
        "large_input": f"""
    def test_{item}_large_input(self):
        \"\"\"Test {item} with large input.\"\"\"
        large_input = 'x' * 100000
        try:
            result = {item}(large_input)
            self.assertIsNotNone(result)
        except Exception as e:
            self.fail(f"{item} raised an exception with large input: {{e}}")
""",
        "negative_input": f"""
    def test_{item}_negative_input(self):
        \"\"\"Test {item} with negative input.\"\"\"
        try:
            result = {item}(-1)
            self.assertIsNotNone(result)
        except Exception as e:
            self.fail(f"{item} raised an exception with negative input: {{e}}")
""",
        "null_input": f"""
    def test_{item}_null_input(self):
        \"\"\"Test {item} with None input.\"\"\"
        try:
            result = {item}(None)
            self.assertIsNotNone(result)
        except Exception as e:
            self.fail(f"{item} raised an exception with None input: {{e}}")
""",
        "type_mismatch": f"""
    def test_{item}_type_mismatch(self):
        \"\"\"Test {item} with incorrect type input.\"\"\"
        try:
            result = {item}("string_instead_of_int")
            self.assertIsNotNone(result)
        except Exception as e:
            self.fail(f"{item} raised an exception with type mismatch: {{e}}")
""",
        "boundary_value": f"""
    def test_{item}_boundary_value(self):
        \"\"\"Test {item} with boundary value.\"\"\"
        try:
            result = {item}(0)
            self.assertIsNotNone(result)
        except Exception as e:
            self.fail(f"{item} raised an exception with boundary value: {{e}}")
""",
        "special_characters": f"""
    def test_{item}_special_characters(self):
        \"\"\"Test {item} with special characters.\"\"\"
        special_input = '!@#$%^&*()_+-=[]{{}}|;:,.<>?'
        try:
            result = {item}(special_input)
            self.assertIsNotNone(result)
        except Exception as e:
            self.fail(f"{item} raised an exception with special characters: {{e}}")
""",
        "max_int": f"""
    def test_{item}_max_int(self):
        \"\"\"Test {item} with maximum integer value.\"\"\"
        try:
            result = {item}(sys.maxsize)
            self.assertIsNotNone(result)
        except Exception as e:
            self.fail(f"{item} raised an exception with max int: {{e}}")
""",
        "min_int": f"""
    def test_{item}_min_int(self):
        \"\"\"Test {item} with minimum integer value.\"\"\"
        try:
            result = {item}(-sys.maxsize - 1)
            self.assertIsNotNone(result)
        except Exception as e:
            self.fail(f"{item} raised an exception with min int: {{e}}")
""",
        "float_precision": f"""
    def test_{item}_float_precision(self):
        \"\"\"Test {item} with floating point precision edge case.\"\"\"
        try:
            result = {item}(0.1 + 0.2)
            self.assertIsNotNone(result)
        except Exception as e:
            self.fail(f"{item} raised an exception with float precision: {{e}}")
"""
    }

    return test_templates.get(edge_case_type, test_templates["empty_input"])


def _build_benchmark_test_file(module_name: str, edge_case_tests: List[str]) -> str:
    """
    Build a complete benchmark test file from edge case tests.

    Args:
        module_name: Name of the module being tested.
        edge_case_tests: List of edge case test code strings.

    Returns:
        String containing the complete test file content.
    """
    test_code = f"""import unittest
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from {module_name} import *


class TestBenchmark_{module_name.capitalize()}(unittest.TestCase):
    \"\"\"Benchmark tests for {module_name} module with randomized edge cases.\"\"\"

    def setUp(self):
        \"\"\"Set up test fixtures.\"\"\"
        self.start_time = time.time()

    def tearDown(self):
        \"\"\"Tear down test fixtures and check performance.\"\"\"
        elapsed = time.time() - self.start_time
        self.assertLess(elapsed, 5.0, f"Test took too long: {{elapsed:.2f}}s")

{''.join(edge_case_tests)}

if __name__ == '__main__':
    unittest.main()
"""
    return test_code


def _validate_imports(test_code: str, module_name: str) -> Tuple[bool, List[str]]:
    """
    Validate that the imports in the test code are valid.

    Args:
        test_code: The test code to validate.
        module_name: The name of the module being imported.

    Returns:
        Tuple of (is_valid, list_of_errors).
    """
    errors = []

    # Check if the module exists
    try:
        __import__(module_name)
    except ImportError:
        errors.append(f"Module '{module_name}' could not be imported")
        return False, errors

    # Try to parse the test code
    try:
        ast.parse(test_code)
    except SyntaxError as e:
        errors.append(f"Syntax error in test code: {str(e)}")
        return False, errors

    # Try to compile the test code
    try:
        compile(test_code, "<test>", "exec")
    except Exception as e:
        errors.append(f"Compilation error: {str(e)}")
        return False, errors

    return True, errors


def _fix_imports(test_code: str, module_name: str) -> str:
    """
    Attempt to fix import issues in the test code.

    Args:
        test_code: The test code to fix.
        module_name: The name of the module being imported.

    Returns:
        Fixed test code string.
    """
    # Add sys.path manipulation to help find the module
    fixed_code = test_code.replace(
        f"from {module_name} import *",
        f"""import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, '.')
from {module_name} import *"""
    )
    return fixed_code


# ---------------------------------------------------------------------------
# New Method: introduce_environmental_pressure
# ---------------------------------------------------------------------------

def introduce_environmental_pressure(
    test_dir: str = "tests",
    source_dir: str = ".",
    output_dir: Optional[str] = None,
    timeout: float = 5.0,
) -> Dict[str, Any]:
    """
    Introduce a new environmental pressure by:
    1. Randomly selecting a module from the source directory.
    2. Creating a new test that tests an extreme or edge case scenario not currently covered.
    3. Adding performance benchmarks with timeouts.
    4. Tracking which modules fail under which pressures.

    This creates the 'evolving fitness landscape' without requiring new external modules.

    Args:
        test_dir: Directory containing test files.
        source_dir: Directory containing source modules.
        output_dir: Directory to write new test files. If None, uses test_dir.
        timeout: Timeout in seconds for performance benchmarks.

    Returns:
        Dict with pressure introduction results: {
            "selected_module": str,
            "pressure_name": str,
            "test_code": str,
            "benchmark_results": dict,
            "module_failures": dict
        }
    """
    result = {
        "selected_module": "",
        "pressure_name": "",
        "test_code": "",
        "benchmark_results": {},
        "module_failures": {}
    }

    # Step 1: Randomly select a module from the source directory
    source_modules = _find_source_modules(source_dir)
    if not source_modules:
        result["errors"] = ["No source modules found"]
        return result

    module_name = random.choice(list(source_modules.keys()))
    module_path = source_modules[module_name]
    result["selected_module"] = module_name

    # Step 2: Create a new test that tests an extreme or edge case scenario
    # Generate a unique pressure name
    pressure_name = f"extreme_case_{module_name}_{random.randint(1000,9999)}"
    result["pressure_name"] = pressure_name

    # Generate test code for extreme/edge case
    test_code = _generate_extreme_case_test(module_name, module_path)
    result["test_code"] = test_code

    # Step 3: Add performance benchmarks with timeouts
    benchmark_results = _run_performance_benchmarks(module_name, module_path, timeout)
    result["benchmark_results"] = benchmark_results

    # Step 4: Track which modules fail under which pressures
    module_failures = _track_module_failures(module_name, test_code, test_dir)
    result["module_failures"] = module_failures

    # Write the test file if output_dir is specified
    output_path = Path(output_dir) if output_dir else Path(test_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    test_file_path = output_path / f"test_{pressure_name}.py"
    try:
        with open(test_file_path, "w") as f:
            f.write(test_code)
    except OSError as e:
        result["errors"] = [f"Failed to write test file: {str(e)}"]

    # Register the new pressure
    def evaluate_extreme_case(test_suite: Dict[str, Any]) -> float:
        """Evaluate the extreme case pressure."""
        # Check if the test suite contains the extreme case test
        test_files = _scan_test_files(test_dir)
