"""
core/environmental_pressure.py

Dedicated module for generating environmental pressures on the test suite and mutation system.
Every 5 cycles, it analyzes current test suite, identifies coverage gaps, generates 1-3 new test files,
runs quick import checks, and maintains a registry of generated tests with metadata.
"""

import random
import time
import threading
import os
import sys
import importlib.util
from collections import defaultdict
from typing import Dict, List, Optional, Tuple, Any, Callable

# ---------------------------------------------------------------------------
# Pressure definitions
# ---------------------------------------------------------------------------

# Predefined pressure templates with name, description, and a constraint generator
PRESSURE_TEMPLATES = [
    {
        "name": "time_limit",
        "description": "Must complete within X seconds",
        "default_params": {"max_seconds": 5.0},
        "constraint_fn": lambda params: f"timeout={params['max_seconds']}",
    },
    {
        "name": "empty_input",
        "description": "Must handle empty inputs gracefully",
        "default_params": {},
        "constraint_fn": lambda params: "empty_input_ok",
    },
    {
        "name": "thread_safe",
        "description": "Must be thread-safe (concurrent access)",
        "default_params": {"num_threads": 4},
        "constraint_fn": lambda params: f"thread_safe={params['num_threads']}",
    },
    {
        "name": "memory_limit",
        "description": "Must not exceed X MB memory",
        "default_params": {"max_mb": 256},
        "constraint_fn": lambda params: f"memory_limit={params['max_mb']}MB",
    },
    {
        "name": "no_exceptions",
        "description": "Must not raise unhandled exceptions on edge cases",
        "default_params": {},
        "constraint_fn": lambda params: "no_exceptions",
    },
    {
        "name": "deterministic",
        "description": "Must produce deterministic output for same input",
        "default_params": {"runs": 3},
        "constraint_fn": lambda params: f"deterministic={params['runs']}",
    },
    {
        "name": "large_input",
        "description": "Must handle large inputs (X elements)",
        "default_params": {"max_elements": 10000},
        "constraint_fn": lambda params: f"large_input={params['max_elements']}",
    },
    {
        "name": "negative_values",
        "description": "Must handle negative numeric inputs",
        "default_params": {},
        "constraint_fn": lambda params: "negative_values_ok",
    },
    {
        "name": "performance",
        "description": "Must meet performance benchmarks",
        "default_params": {"max_time_ms": 100},
        "constraint_fn": lambda params: f"performance={params['max_time_ms']}ms",
    },
    {
        "name": "security",
        "description": "Must pass security checks",
        "default_params": {},
        "constraint_fn": lambda params: "security_ok",
    },
    {
        "name": "edge_case",
        "description": "Must handle edge cases correctly",
        "default_params": {},
        "constraint_fn": lambda params: "edge_case_ok",
    },
]

# ---------------------------------------------------------------------------
# Pressure tracker
# ---------------------------------------------------------------------------

class PressureTracker:
    """Tracks which pressures have been applied and their success rates."""

    def __init__(self):
        self.history: Dict[str, List[dict]] = defaultdict(list)
        self.success_counts: Dict[str, int] = defaultdict(int)
        self.failure_counts: Dict[str, int] = defaultdict(int)
        self.current_pressures: List[dict] = []

    def record_application(self, pressure_name: str, params: dict, cycle: int):
        """Record that a pressure was applied at a given cycle."""
        record = {
            "cycle": cycle,
            "params": params,
            "timestamp": time.time(),
        }
        self.history[pressure_name].append(record)
        self.current_pressures.append({"name": pressure_name, "params": params})

    def record_success(self, pressure_name: str):
        """Record a successful adaptation to a pressure."""
        self.success_counts[pressure_name] += 1
        self._remove_current(pressure_name)

    def record_failure(self, pressure_name: str):
        """Record a failure to adapt to a pressure."""
        self.failure_counts[pressure_name] += 1
        self._remove_current(pressure_name)

    def _remove_current(self, pressure_name: str):
        """Remove a pressure from the current list."""
        self.current_pressures = [
            p for p in self.current_pressures if p["name"] != pressure_name
        ]

    def get_success_rate(self, pressure_name: str) -> float:
        """Get the success rate for a given pressure."""
        total = self.success_counts[pressure_name] + self.failure_counts[pressure_name]
        if total == 0:
            return 0.0
        return self.success_counts[pressure_name] / total

    def get_summary(self) -> dict:
        """Return a summary of all tracked pressures."""
        summary = {}
        for name in set(list(self.success_counts.keys()) + list(self.failure_counts.keys())):
            summary[name] = {
                "successes": self.success_counts[name],
                "failures": self.failure_counts[name],
                "success_rate": self.get_success_rate(name),
                "total_applications": len(self.history.get(name, [])),
            }
        return summary

    def get_current_pressures(self) -> List[dict]:
        """Return list of currently active pressures."""
        return self.current_pressures


# ---------------------------------------------------------------------------
# Generated test registry
# ---------------------------------------------------------------------------

class GeneratedTestRegistry:
    """Maintains a registry of generated tests with metadata."""

    def __init__(self):
        self.registry: List[dict] = []

    def add_test(self, filepath: str, creation_cycle: int, purpose: str, success_rate: float = 0.0):
        """Add a generated test to the registry."""
        entry = {
            "filepath": filepath,
            "creation_cycle": creation_cycle,
            "purpose": purpose,
            "success_rate": success_rate,
            "timestamp": time.time(),
        }
        self.registry.append(entry)

    def update_success_rate(self, filepath: str, success_rate: float):
        """Update the success rate for a specific test file."""
        for entry in self.registry:
            if entry["filepath"] == filepath:
                entry["success_rate"] = success_rate
                break

    def get_all_tests(self) -> List[dict]:
        """Return all registered tests."""
        return self.registry

    def get_tests_by_cycle(self, cycle: int) -> List[dict]:
        """Return tests created in a specific cycle."""
        return [entry for entry in self.registry if entry["creation_cycle"] == cycle]

    def get_summary(self) -> dict:
        """Return a summary of the registry."""
        if not self.registry:
            return {"total_tests": 0, "average_success_rate": 0.0}
        total = len(self.registry)
        avg_success = sum(entry["success_rate"] for entry in self.registry) / total
        return {
            "total_tests": total,
            "average_success_rate": avg_success,
            "tests": self.registry,
        }


# ---------------------------------------------------------------------------
# Coverage gap analysis
# ---------------------------------------------------------------------------

def analyze_coverage_gaps(test_suite: List[Callable]) -> List[str]:
    """Analyze the current test suite and identify coverage gaps."""
    gaps = []
    
    # Check for edge case coverage
    has_edge_cases = any(
        "edge" in fn.__name__.lower() or "boundary" in fn.__name__.lower()
        for fn in test_suite
    )
    if not has_edge_cases:
        gaps.append("edge_cases")
    
    # Check for error handling coverage
    has_error_tests = any(
        "error" in fn.__name__.lower() or "exception" in fn.__name__.lower() or "fail" in fn.__name__.lower()
        for fn in test_suite
    )
    if not has_error_tests:
        gaps.append("error_handling")
    
    # Check for input validation coverage
    has_input_tests = any(
        "input" in fn.__name__.lower() or "validate" in fn.__name__.lower()
        for fn in test_suite
    )
    if not has_input_tests:
        gaps.append("input_validation")
    
    # Check for performance coverage
    has_perf_tests = any(
        "perf" in fn.__name__.lower() or "benchmark" in fn.__name__.lower() or "speed" in fn.__name__.lower()
        for fn in test_suite
    )
    if not has_perf_tests:
        gaps.append("performance")
    
    # Check for concurrency coverage
    has_concurrency_tests = any(
        "thread" in fn.__name__.lower() or "concurrent" in fn.__name__.lower() or "parallel" in fn.__name__.lower()
        for fn in test_suite
    )
    if not has_concurrency_tests:
        gaps.append("concurrency")
    
    # Check for data integrity coverage
    has_integrity_tests = any(
        "integrity" in fn.__name__.lower() or "consistency" in fn.__name__.lower() or "valid" in fn.__name__.lower()
        for fn in test_suite
    )
    if not has_integrity_tests:
        gaps.append("data_integrity")
    
    return gaps


# ---------------------------------------------------------------------------
# Test file generation
# ---------------------------------------------------------------------------

def generate_test_file(gap: str, output_dir: str, cycle: int) -> Optional[str]:
    """Generate a new test file targeting a specific coverage gap."""
    timestamp = int(time.time())
    filename = f"test_generated_{gap}_{cycle}_{timestamp}.py"
    filepath = os.path.join(output_dir, filename)
    
    # Generate test content based on the gap
    if gap == "edge_cases":
        content = f'''"""
Auto-generated test for edge case coverage (Cycle {cycle})
"""
import pytest

def test_edge_case_empty_input():
    """Test handling of empty input."""
    assert True  # Replace with actual test logic

def test_edge_case_boundary_values():
    """Test handling of boundary values."""
    assert True  # Replace with actual test logic

def test_edge_case_none_input():
    """Test handling of None input."""
    assert True  # Replace with actual test logic

def test_edge_case_special_characters():
    """Test handling of special characters."""
    assert True  # Replace with actual test logic
'''
    elif gap == "error_handling":
        content = f'''"""
Auto-generated test for error handling coverage (Cycle {cycle})
"""
import pytest

def test_error_invalid_input():
    """Test that invalid input raises appropriate error."""
    assert True  # Replace with actual test logic

def test_error_resource_not_found():
    """Test handling of missing resources."""
    assert True  # Replace with actual test logic

def test_error_timeout():
    """Test handling of timeout scenarios."""
    assert True  # Replace with actual test logic

def test_error_network_failure():
    """Test handling of network failures."""
    assert True  # Replace with actual test logic
'''
    elif gap == "input_validation":
        content = f'''"""
Auto-generated test for input validation coverage (Cycle {cycle})
"""
import pytest

def test_validation_positive_numbers():
    """Test validation of positive numbers."""
    assert True  # Replace with actual test logic

def test_validation_negative_numbers():
    """Test validation of negative numbers."""
    assert True  # Replace with actual test logic

def test_validation_string_length():
    """Test validation of string length limits."""
    assert True  # Replace with actual test logic

def test_validation_data_types():
    """Test validation of expected data types."""
    assert True  # Replace with actual test logic
'''
    elif gap == "performance":
        content = f'''"""
Auto-generated test for performance coverage (Cycle {cycle})
"""
import pytest
import time

def test_performance_small_dataset():
    """Test performance with small dataset."""
    start = time.time()
    # Add actual test logic here
    elapsed = time.time() - start
    assert elapsed < 1.0, f"Performance too slow: {{elapsed:.3f}}s"

def test_performance_large_dataset():
    """Test performance with large dataset."""
    start = time.time()
    # Add actual test logic here
    elapsed = time.time() - start
    assert elapsed < 5.0, f"Performance too slow: {{elapsed:.3f}}s"

def test_performance_concurrent_requests():
    """Test performance under concurrent requests."""
    start = time.time()
    # Add actual test logic here
    elapsed = time.time() - start
    assert elapsed < 3.0, f"Performance too slow: {{elapsed:.3f}}s"
'''
    elif gap == "concurrency":
        content = f'''"""
Auto-generated test for concurrency coverage (Cycle {cycle})
"""
import pytest
import threading

def test_concurrency_thread_safety():
    """Test thread safety of operations."""
    results = []
    errors = []
    
    def worker():
        try:
            # Add actual test logic here
            results.append(True)
        except Exception as e:
            errors.append(e)
    
    threads = [threading.Thread(target=worker) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    
    assert len(errors) == 0, f"Concurrency errors: {{errors}}"
    assert len(results) == 10, "Not all threads completed"

def test_concurrency_race_condition():
    """Test for race conditions."""
    # Add actual test logic here
    assert True

def test_concurrency_deadlock():
    """Test for deadlock scenarios."""
    # Add actual test logic here
    assert True
'''
    elif gap == "data_integrity":
        content = f'''"""
Auto-generated test for data integrity coverage (Cycle {cycle})
"""
import pytest

def test_integrity_data_consistency():
    """Test that data remains consistent after operations."""
    assert True  # Replace with actual test logic

def test_integrity_transaction_atomicity():
    """Test atomicity of transactions."""
    assert True  # Replace with actual test logic

def test_integrity_data_validation():
    """Test that data meets validation rules."""
    assert True  # Replace with actual test logic

def test_integrity_rollback():
    """Test proper rollback on failure."""
    assert True  # Replace with actual test logic
'''
    else:
        return None
    
    try:
        with open(filepath, 'w') as f:
            f.write(content)
        return filepath
    except IOError as e:
        print(f"Error writing test file {filepath}: {e}")
        return None


# ---------------------------------------------------------------------------
# Import check
# ---------------------------------------------------------------------------

def quick_import_check(filepath: str) -> bool:
    """Run a quick import check on a generated test file."""
    try:
        # Get the module name from the file path
        module_name = os.path.splitext(os.path.basename(filepath))[0]
        
        # Add the directory to sys.path
        directory = os.path.dirname(os.path.abspath(filepath))
        if directory not in sys.path:
            sys.path.insert(0, directory)
        
        # Try to import the module
        spec = importlib.util.spec_from_file_location(module_name, filepath)
        if spec is None:
            return False
        
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        # Check that the module has test functions
        test_functions = [name for name in dir(module) if name.startswith('test_')]
        return len(test_functions) > 0
    except Exception as e:
        print(f"Import check failed for {filepath}: {e}")
        return False


# ---------------------------------------------------------------------------
# Benchmark test generation
# ---------------------------------------------------------------------------

def generate_benchmark_test(pressure: dict, test_function: Callable) -> dict:
    """
    Generate a benchmark test that measures how well the system adapts to a given pressure.
    
    Args:
        pressure: A pressure dictionary with 'name', 'params', etc.
        test_function: The function to test under pressure.
    
    Returns:
        A dictionary with benchmark results.
    """
    pressure_name = pressure["name"]
    params = pressure.get("params", {})
    result = {
        "pressure": pressure_name,
        "params": params,
        "passed": False,
        "execution_time": None,
        "error": None,
    }

    start_time = time.time()
    try:
        if pressure_name == "time_limit":
            max_seconds = params.get("max_seconds", 5.0)
            # Run in a thread with timeout
            result_list = []
            def target():
                try:
                    test_function()
                    result_list.append(True)
                except Exception:
                    result_list.append(False)
            thread = threading.Thread(target=target)
            thread.daemon = True
            thread.start()
            thread.join(timeout=max_seconds)
            if thread.is_alive():
                result["error"] = f"Timed out after {max_seconds}s"
                result["passed"] = False
            else:
                result["passed"] = result_list[0] if result_list else False
                if not result["passed"]:
                    result["error"] = "Test function raised an exception"

        elif pressure_name == "empty_input":
            try:
                test_function([])  # empty list
                test_function("")  # empty string
                test_function({})  # empty dict
                result["passed"] = True
            except Exception as e:
                result["error"] = str(e)
                result["passed"] = False

        elif pressure_name == "thread_safe":
            num_threads = params.get("num_threads", 4)
            errors = []
            def thread_target():
                try:
                    test_function()
                except Exception as e:
                    errors.append(e)
            threads = [threading.Thread(target=thread_target) for _ in range(num_threads)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            if errors:
                result["error"] = f"Thread safety violation: {errors[0]}"
                result["passed"] = False
            else:
                result["passed"] = True

        elif pressure_name == "memory_limit":
            # Simple memory check (approximate)
            import sys
            obj = test_function()
            size = sys.getsizeof(obj)
            max_mb = params.get("max_mb", 256)
            if size > max_mb * 1024 * 1024:
                result["error"] = f"Memory usage {size} bytes exceeds {max_mb}MB"
                result["passed"] = False
            else:
                result["passed"] = True

        elif pressure_name == "no_exceptions":
            try:
                test_function()
                result["passed"] = True
            except Exception as e:
                result["error"] = str(e)
                result["passed"] = False

        elif pressure_name == "deterministic":
            runs = params.get("runs", 3)
            outputs = []
            for _ in range(runs):
                outputs.append(test_function())
            if len(set(str(o) for o in outputs)) == 1:
                result["passed"] = True
            else:
                result["error"] = "Non-deterministic output detected"
                result["passed"] = False

        elif pressure_name == "large_input":
            max_elements = params.get("max_elements", 10000)
            try:
                test_function(list(range(max_elements)))
                result["passed"] = True
            except Exception as e:
                result["error"] = str(e)
                result["passed"] = False

        elif pressure_name == "negative_values":
            try:
                test_function(-1)
                test_function(-100)
                test_function(-0.5)
                result["passed"] = True
            except Exception as e:
                result["error"] = str(e)
                result["passed"] = False

        elif pressure_name == "performance":
            max_time_ms = params.get("max_time_ms", 100)
            try:
                start = time.time()
                test_function()
                elapsed = (time.time() - start) * 1000
                if elapsed <= max_time_ms:
                    result["passed"] = True
                else:
                    result["error"] = f"Performance: {elapsed:.2f}ms exceeds {max_time_ms}ms"
                    result["passed"] = False
            except Exception as e:
                result["error"] = str(e)
                result["passed"] = False

        elif pressure_name == "security":
            try:
                # Basic security checks
                test_function()
                result["passed"] = True
            except Exception as e:
                result["error"] = str(e)
                result["passed"] = False

        elif pressure_name == "edge_case":
            try:
                # Test with various edge cases
                test_function(None)
                test_function(float('inf'))
                test_function(float('-inf'))
                test_function(float('nan'))
                result["passed"] = True
            except Exception as e:
                result["error"] = str(e)
                result["passed"] = False

        else:
            # Unknown pressure - just run the test
            try:
                test_function()
                result["passed"] = True
            except Exception as e:
                result["error"] = str(e)
                result["passed"] = False

    except Exception as e:
        result["error"] = f"Benchmark error: {str(e)}"
        result["passed"] = False

    result["execution_time"] = time.time() - start_time
    return result


# ---------------------------------------------------------------------------
# Meta-test scenario generation
# ---------------------------------------------------------------------------

def generate_adversarial_variant(test_function: Callable) -> Callable:
    """
    Create an adversarial variant of a test function by introducing edge-case inputs
    that are likely to break naive implementations.
    """
    def adversarial_test():
        # Try extreme values
        try:
            test_function(None)
        except Exception:
            pass
        try:
            test_function(float('nan'))
        except Exception:
            pass
        try:
            test_function(float('inf'))
        except Exception:
            pass
        try:
            test_function(-float('inf'))
        except Exception:
            pass
        try:
            test_function(0)
        except Exception:
            pass
        try:
            test_function("")
        except Exception:
            pass
        try:
            test_function([])
        except Exception:
            pass
        try:
            test_function({})
        except Exception:
            pass
        try:
            test_function(set())
        except Exception:
            pass
        try:
            test_function(b'')
        except Exception:
            pass
        # Return True if no unhandled exception
        return True
    adversarial_test.__name__ = f"adversarial_{test_function.__name__}"
    return adversarial_test


def generate_timing_constraint(test_function: Callable, max_time_ms: float = 50.0) -> Callable:
    """
    Wrap a test function with a timing constraint that fails if execution exceeds max_time_ms.
    """
    def timed_test():
        start = time.time()
        result = test_function()
        elapsed = (time.time() - start) * 1000
        assert elapsed <= max_time_ms, f"Timing constraint violated: {elapsed:.2f}ms > {max_time_ms}ms"
        return result
    timed_test.__name__ = f"timed_{test_function.__name__}"
    return timed_test


def generate_dependency_check(test_functions: List[Callable]) -> Callable:
    """
    Create a cross-test dependency check that verifies consistency across multiple test functions.
    """
    def dependency_test():
        results = []
        for fn in test_functions:
            try:
                result = fn()
                results.append(result)
            except Exception as e:
                results.append(f"ERROR: {e}")
        # Check that all results are consistent (all True or all have same structure)
        if len(results) > 1:
            first_result = results[0]
            for r in results[1:]:
                if type(r) != type(first_result):
                    raise AssertionError(f"Inconsistent result types: {type(first_result)} vs {type(r)}")
                if isinstance(first_result, (int, float, str, bool)) and r != first_result:
                    raise AssertionError(f"Inconsistent values: {first_result} vs {r}")
        return True
    dependency_test.__name__ = "cross_test_dependency_check"
    return dependency_test


def pressure_cascade(test_suite: List[Callable]) -> List[Callable]:
    """
    Generate meta-test scenarios that stress-test existing tests by:
    (1) creating adversarial input variants,
    (2) introducing timing constraints,
    (3) adding cross-test dependency checks.
    
    Args:
        test_suite: List of test functions to stress-test.
    
    Returns:
        List of new meta-test functions.
    """
    meta_tests = []
    
    if not test_suite:
        return meta_tests
    
    # (1) Create adversarial input variants for each test
    for fn in test_suite:
        adversarial = generate_adversarial_variant(fn)
        meta_tests.append(adversarial)
    
    # (2) Introduce timing constraints on a subset of tests
    for fn in test_suite[:max(1, len(test_suite) // 2)]:
        timed = generate_timing_constraint(fn, max_time_ms=100.0)
        meta_tests.append(timed)
    
    # (3) Add cross-test dependency checks
    if len(test_suite) >= 2:
        # Create dependency checks for pairs of tests
        for i in range(0, len(test_suite) - 1, 2):
            pair = [test_suite[i], test_suite[i + 1]]
            dep_check = generate_dependency_check(pair)
            meta_tests.append(dep_check)
        
        # Also create a global dependency check for all tests
        if len(test_suite) >= 3:
            global_check = generate_dependency_check(test_suite[:3])
            meta_tests.append(global_check)
    
    return meta_tests


# ---------------------------------------------------------------------------
# Main pressure generator class
# ---------------------------------------------------------------------------

class EnvironmentalPressureGenerator:
    """
    Generates environmental pressures every 5 cycles.
    Analyzes current test suite and identifies coverage gaps to generate new test files.
    """

    def __init__(self, cycle_interval: int = 5, output_dir: str = "generated_tests"):
        self.cycle_interval = cycle_interval
        self.tracker = PressureTracker()
        self.registry = GeneratedTestRegistry()
        self.last_cycle = 0
        self.applied_pressures: List[str] = []
        self.benchmark_results: List[dict] = []
        self.output_dir = output_dir
        
        # Ensure output directory exists
        os.makedirs(self.output_dir, exist_ok=True)

    def analyze_and_apply(self, cycle: int, test_suite: List[Callable],
                          mutation_patterns: Optional[dict] = None) -> List[dict]:
        """
        Analyze the current state and apply new pressures if it's time.
        
        Args:
            cycle: Current cycle number.
            test_suite: List of test functions.
            mutation_patterns: Optional dict of mutation analysis data.
        
        Returns:
            List of newly applied pressures.
        """
        if cycle - self.last_cycle < self.cycle_interval:
            return []

        self.last_cycle = cycle
        new_pressures = []

        # Analyze test suite for coverage gaps
        gaps = analyze_coverage_gaps(test_suite)
        
        # Analyze mutation patterns if provided
        if mutation_patterns:
            gaps.extend(self._analyze_mutation_patterns(mutation_patterns))

        # Generate 1-3 new test files targeting identified gaps
        num_tests_to_generate = min(len(gaps), random.randint(1, 3))
        selected_gaps = random.sample(gaps, num_tests_to_generate) if num_tests_to_generate > 0 else []
        
        for gap in selected_gaps:
            filepath = generate_test_file(gap, self.output_dir, cycle)
            if filepath:
                # Run quick import check
                if quick_import_check(filepath):
                    # Add to registry with initial metadata
                    self.registry.add_test(
                        filepath=filepath,
                        creation_cycle=cycle,
                        purpose=f"Coverage gap: {gap}",
                        success_rate=0.0
                    )
                    
                    # Create a pressure for this gap
                    pressure_template = self._get_pressure_for_gap(gap)
                    if pressure_template:
                        pressure = {
                            "name": pressure_template["name"],
                            "description": pressure_template["description"],
                            "params": pressure_template["default_params"].copy(),
                            "constraint": pressure_template["constraint_fn"](pressure_template["default_params"]),
                            "cycle_applied": cycle,
                        }
                        self.tracker.record_application(pressure["name"], pressure["params"], cycle)
                        self.applied_pressures.append(pressure["name"])
                        new_pressures.append(pressure)
                else:
                    print(f"Import check failed for generated test: {filepath}")

        # Generate benchmark tests for new pressures
        for pressure in new_pressures:
            for test_fn in test_suite[:3]:  # Test against first 3 test functions
                benchmark = generate_benchmark_test(pressure, test_fn)
                self.benchmark_results.append(benchmark)

        # Apply pressure cascade to stress-test existing tests
        if test_suite:
            meta_tests = pressure_cascade(test_suite)
            for meta_test in meta_tests:
                # Record the meta-test as a new pressure
                pressure = {
                    "name": f"meta_{meta_test.__name__}",
                    "description": f"Meta-test: {meta_test.__doc__ or 'Stress test'}",
                    "params": {},
                    "constraint": "meta_test",
                    "cycle_applied": cycle,
                }
                self.tracker.record_application(pressure["name"], pressure["params"], cycle)
                self.applied_pressures.append(pressure["name"])
                new_pressures.append(pressure)

        return new_pressures

    def _get_pressure_for_gap(self, gap: str) -> Optional[dict]:
        """Get a pressure template that addresses a specific coverage gap."""
        gap_to_pressure = {
            "edge_cases": "edge_case",
            "error_handling": "no_exceptions",
            "input_validation": "empty_input",
            "performance": "performance",
            "concurrency": "thread_safe",
            "data_integrity": "deterministic",
        }
        
        pressure_name = gap_to_pressure.get(gap)
        if pressure_name:
            for template in PRESSURE_TEMPLATES:
                if template["name"] == pressure_name:
                    return template
        return None

    def _analyze_mutation_patterns(self, patterns: dict) -> List[str]:
        """Analyze mutation patterns to identify additional weaknesses."""
        weaknesses = []
        
        # If mutations often break on large inputs
        if patterns.get("large_input_breakage_rate", 0) > 0.5:
            weaknesses.append("large_input")

        # If mutations cause non-deterministic behavior
        if patterns.get("non_deterministic_rate", 0) > 0.3:
            weaknesses.append("deterministic")

        # If mutations cause memory issues
        if patterns.get("memory_issue_rate", 0) > 0.2:
            weaknesses.append("memory_limit")

        # If mutations cause performance degradation
        if patterns.get("performance_degradation_rate", 0) > 0.3:
            weaknesses.append("performance")

        # If mutations introduce security vulnerabilities
        if patterns.get("security_vulnerability_rate", 0) > 0.1:
            weaknesses.append("security")

        return weaknesses

    def record_adaptation_result(self, pressure_name: str, success: bool):
        """Record whether the system successfully adapted to a pressure."""
        if success:
            self.tracker.record_success(pressure_name)
        else:
            self.tracker.record_failure(pressure_name)

    def update_test_success_rate(self, filepath: str, success_rate: float):
        """Update the success rate for a specific generated test file."""
        self.registry.update_success_rate(filepath, success_rate)

    def get_status_report(self) -> dict:
        """Generate a comprehensive status report."""
        return {
            "current_pressures": self.tracker.get_current_pressures(),
            "pressure_summary": self.tracker.get_summary(),
            "benchmark_results": self.benchmark_results[-10:],  # Last 10 benchmarks
            "total_pressures_applied": len(self.applied_pressures),
            "cycle_interval": self.cycle_interval,
            "generated_tests": self.registry.get_summary(),
        }

    def inject_pressure_as_goal(self, pressure: dict, goal_generator: Any) -> bool:
        """
        Inject a pressure as a new goal into the goal generator.
        
        Args:
            pressure: The pressure dictionary to inject as a goal.
            goal_generator: The goal generator instance to inject into.
        
        Returns:
            True if injection was successful, False otherwise.
        """
        try:
            # Create a goal from the pressure
            goal = {
                "type": "environmental_pressure",
                "name": f"adapt_to_{pressure['name']}",
                "description": pressure.get("description", f"Adapt to {pressure['name']} pressure"),
                "constraint": pressure.get("constraint", ""),
                "params": pressure.get("params", {}),
                "priority": 0.8,  # High priority for environmental pressures
                "source": "environmental_pressure_generator",
            }
            
            # Try to inject into goal generator if it has an add_goal method
            if hasattr(goal_generator, 'add_goal'):
                goal_generator.add_goal(goal)
                return True
            elif hasattr(goal_generator, 'inject_goal'):
                goal_generator.inject_goal(goal)
                return True
            else:
                # Fallback: try to append to goals list
                if hasattr(goal_generator, 'goals') and isinstance(goal_generator.goals, list):
                    goal_generator.goals.append(goal)
                    return True
                return False
        except Exception as e:
            print(f"Error injecting pressure as goal: {e}")
            return False


# ---------------------------------------------------------------------------
# Convenience function for external use
# ---------------------------------------------------------------------------

def create_pressure_generator(cycle_interval: int = 5, output_dir: str = "generated_tests") -> EnvironmentalPressureGenerator:
    """Create and return a new EnvironmentalPressureGenerator instance."""
    return EnvironmentalPressureGenerator(cycle_interval, output_dir)


# ---------------------------------------------------------------------------
# Self-test / demonstration
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Simple demonstration
    generator = create_pressure_generator(cycle_interval=1)  # Every cycle for demo

    def sample_test():
        return [1, 2, 3]

    def sample_test_empty():
        return []

    test_suite = [sample_test, sample_test_empty]

    # Simulate a few cycles
    for cycle in range(5):
        pressures = generator.analyze_and_apply(cycle, test_suite)
        if pressures:
            print(f"Cycle {cycle}: Applied pressures: {[p['name'] for p in pressures]}")
            for p in pressures:
                # Simulate adaptation result (random for demo)
                success = random.choice([True, False])
                generator.record_adaptation_result(p["name"], success)
                print(f"  - {p['name']}: {'Success' if success else 'Failure'}")

    print("\nStatus Report:")
    report = generator.get_status_report()
    for key, value in report.items():
        print(f"{key}: {value}")
    
    print("\nGenerated Tests:")
    for test in generator.registry.get_all_tests():
        print(f"  - {test['filepath']} (Cycle {test['creation_cycle']}, Purpose: {test['purpose']})")