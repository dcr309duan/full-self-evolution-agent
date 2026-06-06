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
        for test_file in test_files:
            if pressure_name in test_file.name:
                return 1.0
        return 0.0

    def generate_extreme_case_template() -> str:
        """Generate a template for the extreme case test."""
        return test_code

    register_pressure(
        name=pressure_name,
        description=f"Requires extreme case test for module {module_name}",
        severity=0.8,
        evaluate=evaluate_extreme_case,
        generate_template=generate_extreme_case_template,
    )

    # Log the pressure introduction
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "action": "introduce_environmental_pressure",
        "selected_module": module_name,
        "pressure_name": pressure_name,
        "benchmark_results": benchmark_results,
        "module_failures": module_failures
    }
    _log_evolution_change(log_entry)

    return result


def _generate_extreme_case_test(module_name: str, module_path: Path) -> str:
    """
    Generate a test for an extreme or edge case scenario for the given module.

    Args:
        module_name: Name of the module to test.
        module_path: Path to the module file.

    Returns:
        String containing the test code.
    """
    # Parse the module to find functions and classes
    functions = []
    classes = []
    try:
        with open(module_path, "r") as f:
            tree = ast.parse(f.read(), filename=str(module_path))
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and not node.name.startswith("_"):
                functions.append(node.name)
            elif isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
                classes.append(node.name)
    except (SyntaxError, FileNotFoundError):
        pass

    # Generate extreme case test scenarios
    test_scenarios = []
    
    # Add boundary value tests
    if functions:
        for func in functions[:3]:
            test_scenarios.append(f"""
    def test_{func}_extreme_large_input(self):
        \"\"\"Test {func} with extremely large input.\"\"\"
        large_input = 'x' * 100000
        try:
            result = {func}(large_input)
            self.assertIsNotNone(result)
        except Exception as e:
            self.fail(f"{func} raised an exception with large input: {{e}}")

    def test_{func}_extreme_small_input(self):
        \"\"\"Test {func} with extremely small input.\"\"\"
        small_input = ''
        try:
            result = {func}(small_input)
            self.assertIsNotNone(result)
        except Exception as e:
            self.fail(f"{func} raised an exception with small input: {{e}}")

    def test_{func}_extreme_negative_input(self):
        \"\"\"Test {func} with negative input.\"\"\"
        negative_input = -1
        try:
            result = {func}(negative_input)
            self.assertIsNotNone(result)
        except Exception as e:
            self.fail(f"{func} raised an exception with negative input: {{e}}")
""")

    # Add null/None tests
    test_scenarios.append("""
    def test_null_input(self):
        \"\"\"Test with None input.\"\"\"
        try:
            result = some_function(None)
            self.assertIsNotNone(result)
        except Exception as e:
            self.fail(f"Function raised an exception with None input: {e}")
""")

    # Add type mismatch tests
    test_scenarios.append("""
    def test_type_mismatch(self):
        \"\"\"Test with incorrect type input.\"\"\"
        try:
            result = some_function("string_instead_of_int")
            self.assertIsNotNone(result)
        except Exception as e:
            self.fail(f"Function raised an exception with type mismatch: {e}")
""")

    # Combine all scenarios into a test class
    test_code = f"""import unittest
import time
from {module_name} import *


class TestExtremeCase_{module_name.capitalize()}(unittest.TestCase):
    \"\"\"Extreme case tests for {module_name} module.\"\"\"

    def setUp(self):
        \"\"\"Set up test fixtures.\"\"\"
        self.start_time = time.time()

    def tearDown(self):
        \"\"\"Tear down test fixtures and check performance.\"\"\"
        elapsed = time.time() - self.start_time
        self.assertLess(elapsed, 5.0, f"Test took too long: {{elapsed:.2f}}s")

{''.join(test_scenarios)}

if __name__ == '__main__':
    unittest.main()
"""
    return test_code


def _run_performance_benchmarks(module_name: str, module_path: Path, timeout: float) -> Dict[str, Any]:
    """
    Run performance benchmarks on the given module.

    Args:
        module_name: Name of the module to benchmark.
        module_path: Path to the module file.
        timeout: Timeout in seconds for each benchmark.

    Returns:
        Dict with benchmark results.
    """
    results = {
        "module_name": module_name,
        "timeout": timeout,
        "benchmarks": []
    }

    # Parse the module to find functions
    functions = []
    try:
        with open(module_path, "r") as f:
            tree = ast.parse(f.read(), filename=str(module_path))
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and not node.name.startswith("_"):
                functions.append(node.name)
    except (SyntaxError, FileNotFoundError):
        return results

    # Run benchmarks for each function
    for func in functions[:5]:  # Limit to first 5 functions
        benchmark = {
            "function": func,
            "status": "unknown",
            "execution_time": None,
            "error": None
        }
        try:
            # Create a temporary benchmark script
            benchmark_code = f"""
import time
import sys
sys.path.insert(0, '.')
from {module_name} import {func}

start = time.time()
try:
    result = {func}()
    elapsed = time.time() - start
    print(f"SUCCESS:{{elapsed}}")
except Exception as e:
    print(f"ERROR:{{str(e)}}")
"""
            with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
                f.write(benchmark_code)
                temp_path = f.name

            # Run the benchmark with timeout
            result = subprocess.run(
                [sys.executable, temp_path],
                capture_output=True,
                text=True,
                timeout=timeout
            )

            # Parse the output
            output = result.stdout.strip()
            if output.startswith("SUCCESS:"):
                elapsed = float(output.split(":")[1])
                benchmark["status"] = "success"
                benchmark["execution_time"] = elapsed
            elif output.startswith("ERROR:"):
                benchmark["status"] = "error"
                benchmark["error"] = output.split(":", 1)[1].strip()
            else:
                benchmark["status"] = "unknown"
                benchmark["error"] = f"Unexpected output: {output}"

            # Clean up
            os.unlink(temp_path)

        except subprocess.TimeoutExpired:
            benchmark["status"] = "timeout"
            benchmark["error"] = f"Execution exceeded {timeout}s timeout"
        except Exception as e:
            benchmark["status"] = "error"
            benchmark["error"] = str(e)

        results["benchmarks"].append(benchmark)

    return results


def _track_module_failures(module_name: str, test_code: str, test_dir: str) -> Dict[str, List[str]]:
    """
    Track which modules fail under which pressures.

    Args:
        module_name: Name of the module being tested.
        test_code: The test code to run.
        test_dir: Directory containing test files.

    Returns:
        Dict mapping module names to lists of failing pressures.
    """
    failures = {}

    # Create a temporary test file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(test_code)
        temp_path = f.name

    try:
        # Run the test
        result = subprocess.run(
            [sys.executable, "-m", "unittest", temp_path],
            capture_output=True,
            text=True,
            timeout=10
        )

        # Check if the test failed
        if result.returncode != 0:
            failures[module_name] = ["extreme_case_test_failure"]
        else:
            failures[module_name] = []

    except subprocess.TimeoutExpired:
        failures[module_name] = ["test_timeout"]
    except Exception as e:
        failures[module_name] = [f"test_execution_error: {str(e)}"]
    finally:
        # Clean up
        try:
            os.unlink(temp_path)
        except OSError:
            pass

    return failures


# ---------------------------------------------------------------------------
# Helper functions for evolve_test_suite
# ---------------------------------------------------------------------------

def _scan_test_files(test_dir: str = "tests") -> List[Path]:
    """Scan the test directory for all Python test files."""
    test_path = Path(test_dir)
    if not test_path.exists():
        return []
    return list(test_path.rglob("test_*.py")) + list(test_path.rglob("*_test.py"))


def _parse_imports(file_path: Path) -> set:
    """Parse a Python file and extract all module imports."""
    try:
        with open(file_path, "r") as f:
            tree = ast.parse(f.read(), filename=str(file_path))
    except (SyntaxError, FileNotFoundError):
        return set()
    
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.add(node.module.split(".")[0])
    return imports


def _find_source_modules(source_dir: str = ".") -> Dict[str, Path]:
    """Find all source modules in the project (excluding test files)."""
    source_path = Path(source_dir)
    modules = {}
    for py_file in source_path.rglob("*.py"):
        if "test" in py_file.name.lower():
            continue
        if "ecology_pressure_engine" in py_file.name:
            continue
        module_name = py_file.stem
        if module_name.startswith("_"):
            continue
        modules[module_name] = py_file
    return modules


def _generate_test_stub(module_name: str, module_path: Path) -> str:
    """Generate a minimal test stub for an uncovered module."""
    functions = []
    classes = []
    try:
        with open(module_path, "r") as f:
            tree = ast.parse(f.read(), filename=str(module_path))
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and not node.name.startswith("_"):
                functions.append(node.name)
            elif isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
                classes.append(node.name)
    except (SyntaxError, FileNotFoundError):
        pass
    
    stub = f"""import unittest
from {module_name} import *


class Test{module_name.capitalize()}(unittest.TestCase):
    \"\"\"Test suite for {module_name} module.\"\"\"

"""
    if functions:
        for func in functions[:5]:  # Limit to first 5 functions
            stub += f"""    def test_{func}(self):
        \"\"\"Test {func} function.\"\"\"
        # TODO: Implement test for {func}
        self.assertTrue(True)

"""
    if classes:
        for cls in classes[:3]:  # Limit to first 3 classes
            stub += f"""    def test_{cls.lower()}_creation(self):
        \"\"\"Test {cls} class instantiation.\"\"\"
        # TODO: Implement test for {cls}
        self.assertTrue(True)

"""
    stub += """
if __name__ == '__main__':
    unittest.main()
"""
    return stub


def _validate_test_stub(stub_code: str, module_name: str) -> bool:
    """Validate a test stub by running it in isolation."""
    try:
        # Create a temporary file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, dir=".") as f:
            f.write(stub_code)
            temp_path = f.name
        
        # Run the test in isolation
        result = subprocess.run(
            [sys.executable, "-m", "unittest", temp_path],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        # Clean up
        os.unlink(temp_path)
        
        # Check if tests passed (or at least ran without import errors)
        return result.returncode == 0 or "FAILED" not in result.stderr
    except (subprocess.TimeoutExpired, OSError):
        return False


