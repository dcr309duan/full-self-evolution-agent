"""
ecology_core.py - Core ecology engine for test suite evolution.

Provides the foundational classes for test suite evolution:
- TestSuiteScanner: Discovers test files and measures coverage.
- EnvironmentalPressureGenerator: Creates new test scenarios.
- FitnessLandscapeModifier: Introduces new benchmarks.
- EcologyEngine: Orchestrates the above components.
"""

import ast
import os
import random
import string
import sys
import textwrap
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------

def _random_name(prefix: str = "test") -> str:
    """Generate a random test function name."""
    suffix = ''.join(random.choices(string.ascii_lowercase, k=8))
    return f"{prefix}_{suffix}"


def _indent(code: str, level: int = 1) -> str:
    """Indent code block by `level` levels (4 spaces each)."""
    return textwrap.indent(code, "    " * level)


# ---------------------------------------------------------------------------
# TestSuiteScanner
# ---------------------------------------------------------------------------

class TestSuiteScanner:
    """
    Discovers test files in a given directory and measures basic coverage
    of functions/classes defined in the source modules.
    """

    def __init__(self, test_dir: str = "tests", src_dir: str = "src"):
        self.test_dir = Path(test_dir)
        self.src_dir = Path(src_dir)

    def discover_test_files(self) -> List[Path]:
        """Return all Python files in the test directory."""
        if not self.test_dir.exists():
            return []
        return sorted(self.test_dir.rglob("test_*.py"))

    def discover_source_files(self) -> List[Path]:
        """Return all Python files in the source directory."""
        if not self.src_dir.exists():
            return []
        return sorted(self.src_dir.rglob("*.py"))

    def extract_function_names(self, filepath: Path) -> List[str]:
        """Extract top-level function and method names from a Python file."""
        try:
            tree = ast.parse(filepath.read_text(), filename=str(filepath))
        except SyntaxError:
            return []
        names: List[str] = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                names.append(node.name)
            elif isinstance(node, ast.ClassDef):
                names.append(node.name)
        return names

    def extract_test_function_names(self, filepath: Path) -> List[str]:
        """Extract test function names (starting with 'test_') from a file."""
        all_funcs = self.extract_function_names(filepath)
        return [f for f in all_funcs if f.startswith("test_")]

    def measure_coverage(self) -> Dict[str, Any]:
        """
        Measure coverage by comparing source functions against test functions.
        Returns a dict with keys: total_source, total_tests, covered, uncovered, ratio.
        """
        source_funcs: Set[str] = set()
        for sf in self.discover_source_files():
            source_funcs.update(self.extract_function_names(sf))

        test_funcs: Set[str] = set()
        for tf in self.discover_test_files():
            test_funcs.update(self.extract_test_function_names(tf))

        # Simple heuristic: a source function is "covered" if there exists a test
        # function whose name contains the source function name (case-insensitive).
        covered: Set[str] = set()
        uncovered: Set[str] = set()
        for sfunc in source_funcs:
            # Skip dunder methods
            if sfunc.startswith("__") and sfunc.endswith("__"):
                continue
            # Check if any test function references this source function
            found = False
            for tfunc in test_funcs:
                if sfunc.lower() in tfunc.lower():
                    found = True
                    break
            if found:
                covered.add(sfunc)
            else:
                uncovered.add(sfunc)

        total_source = len(covered) + len(uncovered)
        ratio = len(covered) / total_source if total_source > 0 else 0.0

        return {
            "total_source": total_source,
            "total_tests": len(test_funcs),
            "covered": sorted(covered),
            "uncovered": sorted(uncovered),
            "ratio": round(ratio, 4),
        }

    def scan(self) -> Dict[str, Any]:
        """Convenience method: discover + measure."""
        return {
            "test_files": [str(p) for p in self.discover_test_files()],
            "source_files": [str(p) for p in self.discover_source_files()],
            "coverage": self.measure_coverage(),
        }


# ---------------------------------------------------------------------------
# EnvironmentalPressureGenerator
# ---------------------------------------------------------------------------

class EnvironmentalPressureGenerator:
    """
    Generates new test scenarios (test functions) based on uncovered code
    or random mutations of existing tests.
    """

    def __init__(self, scanner: Optional[TestSuiteScanner] = None):
        self.scanner = scanner or TestSuiteScanner()

    def generate_test_for_function(self, func_name: str, module_name: str = "unknown") -> str:
        """
        Generate a minimal pytest test function for a given source function.
        Returns the source code of the test as a string.
        """
        test_code = f"""\
def {_random_name("test")}():
    \"\"\"Auto-generated test for {func_name} from {module_name}.\"\"\"
    # TODO: Replace with actual import and assertion
    # from {module_name.replace('/', '.').replace('.py', '')} import {func_name}
    # result = {func_name}()
    # assert result is not None
    pass
"""
        return test_code

    def generate_random_test(self) -> str:
        """Generate a random test function with arbitrary logic."""
        ops = ["+", "-", "*", "//"]
        a = random.randint(1, 100)
        b = random.randint(1, 100)
        op = random.choice(ops)
        expected = eval(f"{a} {op} {b}")
        test_code = f"""\
def {_random_name("test")}():
    \"\"\"Randomly generated arithmetic test.\"\"\"
    assert {a} {op} {b} == {expected}
"""
        return test_code

    def generate_pressure_tests(self, coverage_data: Dict[str, Any]) -> List[str]:
        """
        Generate new test functions for uncovered functions.
        Returns a list of test function source strings.
        """
        tests: List[str] = []
        for func_name in coverage_data.get("uncovered", []):
            test_code = self.generate_test_for_function(func_name)
            tests.append(test_code)
        # Also add a few random tests for diversity
        for _ in range(min(3, len(coverage_data.get("uncovered", [])) + 1)):
            tests.append(self.generate_random_test())
        return tests


# ---------------------------------------------------------------------------
# FitnessLandscapeModifier
# ---------------------------------------------------------------------------

class FitnessLandscapeModifier:
    """
    Introduces new benchmarks (performance tests) into the test suite.
    Benchmarks are simple timing-based tests that ensure performance
    doesn't regress.
    """

    def __init__(self, benchmark_dir: str = "benchmarks"):
        self.benchmark_dir = Path(benchmark_dir)

    def ensure_benchmark_dir(self) -> None:
        """Create the benchmark directory if it doesn't exist."""
        self.benchmark_dir.mkdir(parents=True, exist_ok=True)

    def generate_benchmark_test(self, target_func: str = "example_func") -> str:
        """
        Generate a benchmark test using pytest-benchmark or a simple time check.
        Returns the source code as a string.
        """
        benchmark_code = f"""\
import time

def {_random_name("benchmark")}(benchmark):
    \"\"\"Benchmark for {target_func}.\"\"\"
    # TODO: Replace with actual import and call
    # from mymodule import {target_func}
    def setup():
        pass

    def run():
        # {target_func}()
        pass

    benchmark(run)
"""
        return benchmark_code

    def generate_performance_test(self, threshold_ms: float = 100.0) -> str:
        """
        Generate a simple performance test that asserts execution time.
        """
        perf_code = f"""\
import time

def {_random_name("test_perf")}():
    \"\"\"Performance test with threshold {threshold_ms} ms.\"\"\"
    start = time.perf_counter()
    # TODO: Replace with actual operation
    # result = some_function()
    elapsed_ms = (time.perf_counter() - start) * 1000
    assert elapsed_ms < {threshold_ms}, f"Took {{elapsed_ms:.2f}}ms, expected <{threshold_ms}ms"
"""
        return perf_code

    def introduce_benchmarks(self, count: int = 3) -> List[str]:
        """
        Create a set of new benchmark/performance tests.
        Returns list of source code strings.
        """
        self.ensure_benchmark_dir()
        tests: List[str] = []
        for i in range(count):
            if i % 2 == 0:
                tests.append(self.generate_benchmark_test(f"func_{i}"))
            else:
                tests.append(self.generate_performance_test(threshold_ms=50.0 + i * 25))
        return tests


# ---------------------------------------------------------------------------
# EcologyEngine
# ---------------------------------------------------------------------------

class EcologyEngine:
    """
    Core engine that orchestrates test suite evolution using:
    - TestSuiteScanner
    - EnvironmentalPressureGenerator
    - FitnessLandscapeModifier
    """

    def __init__(
        self,
        test_dir: str = "tests",
        src_dir: str = "src",
        benchmark_dir: str = "benchmarks",
    ):
        self.scanner = TestSuiteScanner(test_dir=test_dir, src_dir=src_dir)
        self.pressure_gen = EnvironmentalPressureGenerator(scanner=self.scanner)
        self.landscape_mod = FitnessLandscapeModifier(benchmark_dir=benchmark_dir)
        self.history: List[Dict[str, Any]] = []

    def evolve(self, output_dir: Optional[str] = None) -> Dict[str, Any]:
        """
        Run one evolution cycle:
        1. Scan test suite and measure coverage.
        2. Generate pressure tests for uncovered functions.
        3. Introduce new benchmarks.
        4. Write generated tests to output directory (or test directory).
        Returns a summary dict.
        """
        scan_result = self.scanner.scan()
        coverage = scan_result["coverage"]

        # Generate new tests
        new_tests = self.pressure_gen.generate_pressure_tests(coverage)
        new_benchmarks = self.landscape_mod.introduce_benchmarks(count=2)

        # Determine output directory
        out_dir = Path(output_dir) if output_dir else self.scanner.test_dir
        out_dir.mkdir(parents=True, exist_ok=True)

        # Write generated tests to files
        written_files: List[str] = []
        if new_tests:
            pressure_file = out_dir / f"_generated_pressure_{len(self.history)}.py"
            with open(pressure_file, "w") as f:
                f.write("# Auto-generated pressure tests\n")
                f.write("import pytest\n\n")
                for test_code in new_tests:
                    f.write(test_code + "\n")
            written_files.append(str(pressure_file))

        if new_benchmarks:
            bm_file = out_dir / f"_generated_benchmarks_{len(self.history)}.py"
            with open(bm_file, "w") as f:
                f.write("# Auto-generated benchmarks\n")
                f.write("import pytest\n\n")
                for bm_code in new_benchmarks:
                    f.write(bm_code + "\n")
            written_files.append(str(bm_file))

        # Record history
        cycle_record = {
            "cycle": len(self.history),
            "coverage_before": coverage,
            "tests_generated": len(new_tests),
            "benchmarks_generated": len(new_benchmarks),
            "written_files": written_files,
        }
        self.history.append(cycle_record)

        return cycle_record

    def get_summary(self) -> Dict[str, Any]:
        """Return a summary of all evolution cycles."""
        return {
            "total_cycles": len(self.history),
            "history": self.history,
            "current_coverage": self.scanner.measure_coverage(),
        }


# ---------------------------------------------------------------------------
# Convenience entry point
# ---------------------------------------------------------------------------

def run_evolution(
    test_dir: str = "tests",
    src_dir: str = "src",
    output_dir: Optional[str] = None,
    cycles: int = 1,
) -> Dict[str, Any]:
    """
    Run the ecology engine for a given number of cycles.
    Returns the final summary.
    """
    engine = EcologyEngine(test_dir=test_dir, src_dir=src_dir)
    for _ in range(cycles):
        engine.evolve(output_dir=output_dir)
    return engine.get_summary()


if __name__ == "__main__":
    # Quick demo when run directly
    print("Running ecology_core.py demo...")
    summary = run_evolution(cycles=2)
    print(f"Completed {summary['total_cycles']} evolution cycle(s).")
    print(f"Current coverage ratio: {summary['current_coverage']['ratio']:.2%}")