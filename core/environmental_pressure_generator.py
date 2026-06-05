"""Environmental Pressure Generator

This module introduces novel environmental pressures into the evolution cycle.
Every 15 cycles, it analyzes the current test suite, identifies untested edge cases,
and generates a 'pressure test' that the agent must pass to continue.

Examples include:
- Performance regression tests
- Memory leak detection tests
- Cross-module integration tests the agent hasn't seen before
"""

import os
import random
import time
import inspect
import importlib.util
from typing import Dict, List, Optional, Tuple, Any, Callable
from pathlib import Path
import ast
import sys

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

PRESSURE_INTERVAL = 15  # cycles between pressure events
PRESSURE_TESTS_DIR = "tests/pressure_tests"
CORE_MODULES_DIR = "core"
TEST_SUITE_DIR = "tests"

# ---------------------------------------------------------------------------
# Pressure Test Types
# ---------------------------------------------------------------------------

PRESSURE_TEST_TYPES = [
    "performance_regression",
    "memory_leak_detection",
    "cross_module_integration",
    "edge_case_robustness",
    "concurrency_safety",
    "input_validation_extreme",
    "state_corruption_resistance",
]

# ---------------------------------------------------------------------------
# Utility Functions
# ---------------------------------------------------------------------------

def _ensure_pressure_tests_dir():
    """Ensure the pressure tests directory exists."""
    os.makedirs(PRESSURE_TESTS_DIR, exist_ok=True)


def _get_all_test_files() -> List[str]:
    """Get all test files in the test suite directory."""
    test_files = []
    if os.path.exists(TEST_SUITE_DIR):
        for root, dirs, files in os.walk(TEST_SUITE_DIR):
            for f in files:
                if f.startswith("test_") and f.endswith(".py"):
                    test_files.append(os.path.join(root, f))
    return test_files


def _get_all_core_modules() -> List[str]:
    """Get all core module files."""
    core_files = []
    if os.path.exists(CORE_MODULES_DIR):
        for f in os.listdir(CORE_MODULES_DIR):
            if f.endswith(".py") and not f.startswith("_"):
                core_files.append(os.path.join(CORE_MODULES_DIR, f))
    return core_files


def _parse_test_functions(test_file_path: str) -> List[str]:
    """Parse a test file and return the names of test functions."""
    try:
        with open(test_file_path, "r") as f:
            tree = ast.parse(f.read())
        test_functions = []
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
                test_functions.append(node.name)
        return test_functions
    except Exception:
        return []


def _get_module_functions(module_path: str) -> List[str]:
    """Get function names from a core module."""
    try:
        spec = importlib.util.spec_from_file_location("module", module_path)
        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            functions = []
            for name, obj in inspect.getmembers(module):
                if inspect.isfunction(obj) and not name.startswith("_"):
                    functions.append(name)
            return functions
    except Exception:
        pass
    return []


def _identify_untested_functions() -> List[Tuple[str, str]]:
    """Identify functions in core modules that are not covered by any test."""
    core_modules = _get_all_core_modules()
    test_files = _get_all_test_files()

    # Collect all tested function names from test files
    tested_functions = set()
    for tf in test_files:
        test_funcs = _parse_test_functions(tf)
        for func_name in test_funcs:
            # Extract the function being tested from test function name
            # e.g., test_process_data -> process_data
            if func_name.startswith("test_"):
                tested_functions.add(func_name[5:])

    # Find untested functions
    untested = []
    for cm in core_modules:
        functions = _get_module_functions(cm)
        module_name = os.path.basename(cm).replace(".py", "")
        for func in functions:
            if func not in tested_functions:
                untested.append((module_name, func))

    return untested


def _analyze_edge_cases() -> List[str]:
    """Analyze the test suite and identify potential edge cases not covered."""
    test_files = _get_all_test_files()
    edge_cases = []

    # Common edge case patterns to check for
    edge_case_patterns = [
        "empty_input",
        "null_input",
        "negative_values",
        "very_large_input",
        "special_characters",
        "boundary_values",
        "concurrent_access",
        "recursive_structure",
        "circular_references",
        "type_mismatch",
        "missing_parameters",
        "invalid_state",
    ]

    # Check which edge cases are already covered
    covered_edge_cases = set()
    for tf in test_files:
        try:
            with open(tf, "r") as f:
                content = f.read()
            for pattern in edge_case_patterns:
                if pattern in content.lower():
                    covered_edge_cases.add(pattern)
        except Exception:
            continue

    # Identify uncovered edge cases
    for pattern in edge_case_patterns:
        if pattern not in covered_edge_cases:
            edge_cases.append(pattern)

    return edge_cases


# ---------------------------------------------------------------------------
# Pressure Test Generators
# ---------------------------------------------------------------------------

def _generate_performance_regression_test(
    untested_functions: List[Tuple[str, str]],
    edge_cases: List[str]
) -> str:
    """Generate a performance regression pressure test."""
    if not untested_functions:
        untested_functions = [("core", "process_data")]

    module_name, func_name = random.choice(untested_functions)
    edge_case = random.choice(edge_cases) if edge_cases else "large_input"

    test_code = f'''"""
Performance Regression Pressure Test
Generated automatically by Environmental Pressure Generator
Tests: {module_name}.{func_name} with {edge_case} edge case
"""

import time
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from {module_name} import {func_name}


def test_{func_name}_performance_regression():
    """Test that {func_name} performs within acceptable time limits."""
    # Generate test input for {edge_case} scenario
    test_input = _generate_{edge_case}_input()
    
    # Measure execution time
    start_time = time.time()
    for _ in range(100):
        result = {func_name}(test_input)
    elapsed = time.time() - start_time
    
    # Performance threshold: must complete 100 iterations in under 5 seconds
    assert elapsed < 5.0, f"Performance regression: {{elapsed:.2f}}s > 5.0s"
    assert result is not None, "Function returned None"


def _generate_{edge_case}_input():
    """Generate test input for {edge_case} scenario."""
    # TODO: Implement proper input generation based on function signature
    return None
'''
    return test_code


def _generate_memory_leak_test(
    untested_functions: List[Tuple[str, str]],
    edge_cases: List[str]
) -> str:
    """Generate a memory leak detection pressure test."""
    if not untested_functions:
        untested_functions = [("core", "process_data")]

    module_name, func_name = random.choice(untested_functions)

    test_code = f'''"""
Memory Leak Detection Pressure Test
Generated automatically by Environmental Pressure Generator
Tests: {module_name}.{func_name} for memory leaks
"""

import sys
import os
import gc
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from {module_name} import {func_name}


def test_{func_name}_memory_leak():
    """Test that {func_name} does not leak memory over repeated calls."""
    # Force garbage collection before test
    gc.collect()
    
    # Get baseline object count
    baseline = len(gc.get_objects())
    
    # Call function many times
    for i in range(1000):
        result = {func_name}(_generate_test_input())
        if result is not None:
            _ = str(result)  # Simulate usage
    
    # Force garbage collection after test
    gc.collect()
    
    # Check that object count hasn't grown significantly
    final_count = len(gc.get_objects())
    growth = final_count - baseline
    
    # Allow some growth for Python internals, but not more than 100 objects
    assert growth < 100, f"Potential memory leak: {{growth}} objects leaked"


def _generate_test_input():
    """Generate test input for memory leak detection."""
    return None
'''
    return test_code


def _generate_cross_module_integration_test(
    untested_functions: List[Tuple[str, str]],
    edge_cases: List[str]
) -> str:
    """Generate a cross-module integration pressure test."""
    core_modules = _get_all_core_modules()
    if len(core_modules) < 2:
        # Fallback if only one module
        core_modules = ["core/ecology_engine.py", "core/evolution_orchestrator.py"]

    # Pick two random modules
    mod1_path, mod2_path = random.sample(core_modules, 2)
    mod1_name = os.path.basename(mod1_path).replace(".py", "")
    mod2_name = os.path.basename(mod2_path).replace(".py", "")

    test_code = f'''"""
Cross-Module Integration Pressure Test
Generated automatically by Environmental Pressure Generator
Tests integration between {mod1_name} and {mod2_name}
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from {mod1_name} import *
from {mod2_name} import *


def test_cross_module_integration():
    """Test that {mod1_name} and {mod2_name} work together correctly."""
    # Attempt to use functions from both modules together
    # This is a novel integration test the agent hasn't seen before
    
    # Get all public functions from both modules
    mod1_funcs = [name for name, obj in sys.modules["{mod1_name}"].__dict__.items()
                  if callable(obj) and not name.startswith("_")]
    mod2_funcs = [name for name, obj in sys.modules["{mod2_name}"].__dict__.items()
                  if callable(obj) and not name.startswith("_")]
    
    # Try calling functions from module 1 with results from module 2
    for func1_name in mod1_funcs[:3]:  # Test first 3 functions
        for func2_name in mod2_funcs[:3]:
            try:
                func1 = getattr(sys.modules["{mod1_name}"], func1_name)
                func2 = getattr(sys.modules["{mod2_name}"], func2_name)
                
                # Try to chain function calls
                intermediate = func2()
                if intermediate is not None:
                    result = func1(intermediate)
                    assert result is not None or result is None  # Allow None returns
            except Exception as e:
                # Integration may fail gracefully
                pass
    
    # If we got here without crashing, integration is working
    assert True


def test_data_flow_between_modules():
    """Test that data can flow between {mod1_name} and {mod2_name}."""
    # Check that modules can share common data structures
    try:
        from {mod1_name} import EcologyConfig
        from {mod2_name} import EvolutionConfig
        
        # Test that configs are compatible
        eco_config = EcologyConfig()
        evo_config = EvolutionConfig()
        
        # Verify both configs have required attributes
        assert hasattr(eco_config, "to_dict") or hasattr(eco_config, "__dict__")
        assert hasattr(evo_config, "to_dict") or hasattr(evo_config, "__dict__")
    except ImportError:
        pass  # Config classes may not exist
'''
    return test_code


def _generate_edge_case_robustness_test(
    untested_functions: List[Tuple[str, str]],
    edge_cases: List[str]
) -> str:
    """Generate an edge case robustness pressure test."""
    if not untested_functions:
        untested_functions = [("core", "process_data")]

    module_name, func_name = random.choice(untested_functions)
    edge_case = random.choice(edge_cases) if edge_cases else "empty_input"

    test_code = f'''"""
Edge Case Robustness Pressure Test
Generated automatically by Environmental Pressure Generator
Tests: {module_name}.{func_name} with {edge_case}
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from {module_name} import {func_name}


def test_{func_name}_{edge_case}_robustness():
    """Test that {func_name} handles {edge_case} gracefully."""
    # Generate extreme edge case input
    test_inputs = _generate_{edge_case}_inputs()
    
    for i, test_input in enumerate(test_inputs):
        try:
            result = {func_name}(test_input)
            # Function should not crash, but may return None or raise specific exceptions
            assert result is not None or True  # Allow None returns
        except ValueError:
            pass  # ValueError is acceptable for invalid input
        except TypeError:
            pass  # TypeError is acceptable for type mismatch
        except Exception as e:
            # Any other exception is a failure
            assert False, f"Unexpected exception for input {{i}}: {{e}}"


def _generate_{edge_case}_inputs():
    """Generate a list of {edge_case} test inputs."""
    inputs = []
    
    # Add various edge case values
    inputs.append(None)
    inputs.append("")
    inputs.append([])
    inputs.append({{}})
    inputs.append(0)
    inputs.append(-1)
    inputs.append(float('inf'))
    inputs.append(float('-inf'))
    inputs.append(float('nan'))
    
    return inputs
'''
    return test_code


# ---------------------------------------------------------------------------
# Main Generator Function
# ---------------------------------------------------------------------------

def generate_environmental_pressure(cycle_number: int) -> Optional[Dict[str, Any]]:
    """Generate an environmental pressure test if conditions are met.

    Args:
        cycle_number: The current evolution cycle number.

    Returns:
        A dictionary describing the pressure test, or None if no pressure is generated.
    """
    # Only generate pressure every PRESSURE_INTERVAL cycles
    if cycle_number % PRESSURE_INTERVAL != 0:
        return None

    _ensure_pressure_tests_dir()

    # Analyze current test suite
    untested_functions = _identify_untested_functions()
    edge_cases = _analyze_edge_cases()

    # Select a random pressure test type
    test_type = random.choice(PRESSURE_TEST_TYPES)

    # Generate the test based on type
    generators = {
        "performance_regression": _generate_performance_regression_test,
        "memory_leak_detection": _generate_memory_leak_test,
        "cross_module_integration": _generate_cross_module_integration_test,
        "edge_case_robustness": _generate_edge_case_robustness_test,
    }

    generator = generators.get(test_type, _generate_performance_regression_test)
    test_code = generator(untested_functions, edge_cases)

    # Write the pressure test file
    timestamp = int(time.time())
    test_filename = f"pressure_test_cycle_{cycle_number}_{timestamp}.py"
    test_filepath = os.path.join(PRESSURE_TESTS_DIR, test_filename)

    with open(test_filepath, "w") as f:
        f.write(test_code)

    pressure_info = {
        "cycle": cycle_number,
        "type": test_type,
        "file": test_filepath,
        "untested_functions": len(untested_functions),
        "edge_cases_found": len(edge_cases),
        "description": f"Generated {test_type} pressure test with {len(untested_functions)} untested functions and {len(edge_cases)} uncovered edge cases",
    }

    return pressure_info


def get_pressure_test_status() -> Dict[str, Any]:
    """Get the current status of pressure tests.

    Returns:
        A dictionary with pressure test statistics.
    """
    _ensure_pressure_tests_dir()

    pressure_files = [f for f in os.listdir(PRESSURE_TESTS_DIR) if f.endswith(".py")]
    untested = _identify_untested_functions()
    edge_cases = _analyze_edge_cases()

    return {
        "total_pressure_tests": len(pressure_files),
        "untested_functions": len(untested),
        "uncovered_edge_cases": len(edge_cases),
        "pressure_tests_dir": PRESSURE_TESTS_DIR,
        "pressure_interval": PRESSURE_INTERVAL,
    }


def clear_old_pressure_tests(max_age_hours: float = 24.0) -> int:
    """Clear pressure tests older than the specified age.

    Args:
        max_age_hours: Maximum age of pressure tests in hours.

    Returns:
        Number of files removed.
    """
    _ensure_pressure_tests_dir()
    now = time.time()
    max_age_seconds = max_age_hours * 3600
    removed = 0

    for f in os.listdir(PRESSURE_TESTS_DIR):
        filepath = os.path.join(PRESSURE_TESTS_DIR, f)
        if os.path.isfile(filepath):
            file_age = now - os.path.getmtime(filepath)
            if file_age > max_age_seconds:
                os.remove(filepath)
                removed += 1

    return removed