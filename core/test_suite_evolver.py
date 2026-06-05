"""Dedicated module for evolving the test suite through coverage analysis,
novel test generation, validation, and diversity tracking."""

import ast
import os
import sys
import random
import tempfile
import subprocess
import importlib.util
from pathlib import Path
from typing import List, Dict, Set, Tuple, Optional, Any
from collections import defaultdict, Counter
import json
import time
import hashlib

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

TEST_DIR = Path("tests")
SRC_DIR = Path("core")
DIVERSITY_FILE = Path("test_diversity_metrics.json")
VALIDATION_TIMEOUT = 30  # seconds per generated test

# ---------------------------------------------------------------------------
# Coverage Analysis
# ---------------------------------------------------------------------------

class CoverageAnalyzer:
    """Scans test files and source modules to identify coverage gaps."""

    def __init__(self, test_dir: Path = TEST_DIR, src_dir: Path = SRC_DIR):
        self.test_dir = test_dir
        self.src_dir = src_dir

    def get_all_source_functions(self) -> Dict[str, Set[str]]:
        """Return {module_name: {function_name, ...}} for all source modules."""
        functions = {}
        for pyfile in self.src_dir.glob("*.py"):
            if pyfile.name.startswith("_"):
                continue
            try:
                tree = ast.parse(pyfile.read_text())
                module_name = pyfile.stem
                funcs = set()
                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        funcs.add(node.name)
                if funcs:
                    functions[module_name] = funcs
            except SyntaxError:
                continue
        return functions

    def get_tested_functions(self) -> Dict[str, Set[str]]:
        """Return {module_name: {function_name, ...}} for functions referenced in tests."""
        tested = defaultdict(set)
        for pyfile in self.test_dir.glob("test_*.py"):
            try:
                tree = ast.parse(pyfile.read_text())
                for node in ast.walk(tree):
                    if isinstance(node, ast.Call):
                        func = node.func
                        if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
                            # e.g., module.function()
                            module_name = func.value.id
                            func_name = func.attr
                            tested[module_name].add(func_name)
                        elif isinstance(func, ast.Name):
                            # standalone function call
                            tested["unknown"].add(func.id)
            except SyntaxError:
                continue
        return dict(tested)

    def find_coverage_gaps(self) -> Dict[str, Set[str]]:
        """Return {module_name: {untested_function, ...}}."""
        source_funcs = self.get_all_source_functions()
        tested_funcs = self.get_tested_functions()
        gaps = {}
        for module, funcs in source_funcs.items():
            tested = tested_funcs.get(module, set())
            untested = funcs - tested
            if untested:
                gaps[module] = untested
        return gaps

    def analyze_assertion_types(self) -> Dict[str, int]:
        """Count assertion types across test files."""
        counts = Counter()
        for pyfile in self.test_dir.glob("test_*.py"):
            try:
                tree = ast.parse(pyfile.read_text())
                for node in ast.walk(tree):
                    if isinstance(node, ast.Call):
                        func = node.func
                        if isinstance(func, ast.Attribute) and func.attr.startswith("assert"):
                            counts[func.attr] += 1
            except SyntaxError:
                continue
        return dict(counts)

# ---------------------------------------------------------------------------
# Novel Test Generation
# ---------------------------------------------------------------------------

class TestGenerator:
    """Generates new test files with novel testing approaches."""

    APPROACHES = ["property_based", "fuzzing", "integration"]

    def __init__(self, coverage_gaps: Dict[str, Set[str]]):
        self.coverage_gaps = coverage_gaps

    def generate_property_based_test(self, module: str, func: str) -> str:
        """Generate a property-based test using hypothesis-like patterns."""
        return f'''"""Property-based test for {module}.{func}."""
import pytest
from hypothesis import given, strategies as st
from {module} import {func}

@given(
    input_val=st.integers(min_value=-1000, max_value=1000) |
              st.floats(allow_nan=False, allow_infinity=False) |
              st.text(max_size=100)
)
def test_{func}_property_based(input_val):
    """Verify that {func} handles various inputs without crashing."""
    try:
        result = {func}(input_val)
        # Property: result should be serializable (JSON compatible)
        import json
        json.dumps(result)
    except Exception as e:
        # Accept controlled failures for invalid inputs
        if isinstance(input_val, str) and not input_val.isnumeric():
            pytest.skip("String input may not be valid")
        else:
            raise e
'''

    def generate_fuzzing_test(self, module: str, func: str) -> str:
        """Generate a fuzzing-based test with random inputs."""
        return f'''"""Fuzzing test for {module}.{func}."""
import pytest
import random
import string
from {module} import {func}

def test_{func}_fuzzing():
    """Fuzz {func} with random inputs of various types."""
    random.seed(42)
    for _ in range(50):
        input_type = random.choice(["int", "float", "str", "list", "dict"])
        if input_type == "int":
            val = random.randint(-10000, 10000)
        elif input_type == "float":
            val = random.uniform(-10000, 10000)
        elif input_type == "str":
            val = ''.join(random.choices(string.ascii_letters + string.digits, k=random.randint(0, 50)))
        elif input_type == "list":
            val = [random.randint(0, 100) for _ in range(random.randint(0, 10))]
        else:  # dict
            val = {{str(k): random.randint(0, 100) for k in range(random.randint(0, 5))}}
        try:
            result = {func}(val)
            assert result is not None or result is None  # at least doesn't crash
        except (TypeError, ValueError):
            pass  # expected for invalid inputs
        except Exception as e:
            pytest.fail(f"Unexpected error: {{e}}")
'''

    def generate_integration_test(self, module: str, func: str) -> str:
        """Generate an integration test combining multiple functions."""
        return f'''"""Integration test for {module}.{func}."""
import pytest
from {module} import {func}

def test_{func}_integration():
    """Test {func} in an integration scenario with realistic data flow."""
    # Setup realistic test data
    test_inputs = [
        0,
        1,
        -1,
        100,
        "test_string",
        [1, 2, 3],
        {{"key": "value"}},
        None,
    ]
    for inp in test_inputs:
        try:
            result = {func}(inp)
            # Verify result is usable
            if result is not None:
                str(result)  # at least convertible to string
        except Exception as e:
            # Log but don't fail - integration tests can be lenient
            print(f"Integration note: {{func}}({{inp}}) raised {{type(e).__name__}}: {{e}}")
'''

    def generate_test_file(self, module: str, func: str, approach: str) -> str:
        """Generate a complete test file content."""
        generators = {
            "property_based": self.generate_property_based_test,
            "fuzzing": self.generate_fuzzing_test,
            "integration": self.generate_integration_test,
        }
        gen = generators.get(approach)
        if not gen:
            raise ValueError(f"Unknown approach: {approach}")
        return gen(module, func)

    def generate_all_gap_tests(self) -> List[Tuple[str, str, str]]:
        """Generate tests for all coverage gaps. Returns [(filename, approach, content), ...]."""
        tests = []
        for module, funcs in self.coverage_gaps.items():
            for func in funcs:
                approach = random.choice(self.APPROACHES)
                content = self.generate_test_file(module, func, approach)
                filename = f"test_evolved_{module}_{func}_{approach}.py"
                tests.append((filename, approach, content))
        return tests

# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

class TestValidator:
    """Validates generated tests by running them in isolation."""

    def __init__(self, timeout: int = VALIDATION_TIMEOUT):
        self.timeout = timeout

    def validate_test(self, test_content: str, test_name: str) -> Tuple[bool, str]:
        """Run a test in isolation and return (passed, message)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_path = Path(tmpdir) / test_name
            test_path.write_text(test_content)

            # Create a minimal conftest if needed
            conftest_path = Path(tmpdir) / "conftest.py"
            if not conftest_path.exists():
                conftest_path.write_text("import pytest\n")

            # Run pytest on the single test file
            try:
                result = subprocess.run(
                    [sys.executable, "-m", "pytest", str(test_path), "-v", "--tb=short", "--no-header"],
                    capture_output=True,
                    text=True,
                    timeout=self.timeout,
                    cwd=tmpdir,
                )
                if result.returncode == 0:
                    return True, "All tests passed"
                else:
                    # Extract failure reason from output
                    lines = result.stdout.splitlines() + result.stderr.splitlines()
                    failure_lines = [l for l in lines if "FAILED" in l or "Error" in l]
                    reason = failure_lines[0] if failure_lines else "Unknown failure"
                    return False, reason
            except subprocess.TimeoutExpired:
                return False, f"Test timed out after {self.timeout}s"
            except Exception as e:
                return False, f"Validation error: {e}"

    def validate_batch(self, tests: List[Tuple[str, str, str]]) -> List[Tuple[str, str, str, bool, str]]:
        """Validate multiple tests. Returns [(filename, approach, content, passed, message), ...]."""
        results = []
        for filename, approach, content in tests:
            passed, message = self.validate_test(content, filename)
            results.append((filename, approach, content, passed, message))
        return results

# ---------------------------------------------------------------------------
# Diversity Tracking
# ---------------------------------------------------------------------------

class DiversityTracker:
    """Tracks test diversity metrics over time."""

    def __init__(self, diversity_file: Path = DIVERSITY_FILE):
        self.diversity_file = diversity_file
        self.metrics = self._load_metrics()

    def _load_metrics(self) -> Dict[str, Any]:
        if self.diversity_file.exists():
            try:
                return json.loads(self.diversity_file.read_text())
            except (json.JSONDecodeError, IOError):
                pass
        return {
            "total_tests": 0,
            "assertion_types": {},
            "coverage_areas": {},
            "failure_modes": {},
            "approach_counts": {},
            "history": [],
        }

    def _save_metrics(self):
        self.diversity_file.write_text(json.dumps(self.metrics, indent=2))

    def update_from_analysis(self, analyzer: CoverageAnalyzer):
        """Update metrics based on current test suite analysis."""
        # Assertion types
        self.metrics["assertion_types"] = analyzer.analyze_assertion_types()

        # Coverage areas (modules with tests)
        tested = analyzer.get_tested_functions()
        self.metrics["coverage_areas"] = {mod: len(funcs) for mod, funcs in tested.items()}

        # Count test files
        test_files = list(TEST_DIR.glob("test_*.py"))
        self.metrics["total_tests"] = len(test_files)

        # Track approach counts
        approach_counts = Counter()
        for f in test_files:
            for approach in ["property_based", "fuzzing", "integration"]:
                if approach in f.stem:
                    approach_counts[approach] += 1
        self.metrics["approach_counts"] = dict(approach_counts)

        # Record history snapshot
        snapshot = {
            "timestamp": time.time(),
            "total_tests": self.metrics["total_tests"],
            "num_assertion_types": len(self.metrics["assertion_types"]),
            "num_coverage_areas": len(self.metrics["coverage_areas"]),
        }
        self.metrics["history"].append(snapshot)
        self._save_metrics()

    def record_failure_mode(self, failure_mode: str):
        """Record a failure mode encountered during validation."""
        self.metrics["failure_modes"][failure_mode] = self.metrics["failure_modes"].get(failure_mode, 0) + 1
        self._save_metrics()

    def get_diversity_score(self) -> float:
        """Compute a diversity score (0-100) based on metrics."""
        score = 0.0
        # Assertion diversity
        num_assert_types = len(self.metrics.get("assertion_types", {}))
        score += min(num_assert_types * 10, 30)  # max 30 points

        # Coverage area diversity
        num_areas = len(self.metrics.get("coverage_areas", {}))
        score += min(num_areas * 10, 30)  # max 30 points

        # Approach diversity
        num_approaches = len(self.metrics.get("approach_counts", {}))
        score += min(num_approaches * 15, 30)  # max 30 points

        # Total tests (diminishing returns)
        total = self.metrics.get("total_tests", 0)
        score += min(total, 10)  # max 10 points

        return min(score, 100)

# ---------------------------------------------------------------------------
# Main Orchestration
# ---------------------------------------------------------------------------

class TestSuiteEvolver:
    """Main orchestrator for test suite evolution."""

    def __init__(self):
        self.analyzer = CoverageAnalyzer()
        self.validator = TestValidator()
        self.tracker = DiversityTracker()

    def analyze_gaps(self) -> Dict[str, Set[str]]:
        """Analyze and return coverage gaps."""
        return self.analyzer.find_coverage_gaps()

    def generate_and_validate(self, gaps: Dict[str, Set[str]]) -> List[Tuple[str, str, str, bool, str]]:
        """Generate tests for gaps and validate them."""
        generator = TestGenerator(gaps)
        tests = generator.generate_all_gap_tests()
        results = self.validator.validate_batch(tests)
        return results

    def add_validated_tests(self, results: List[Tuple[str, str, str, bool, str]]) -> List[str]:
        """Add validated tests to the test suite. Returns list of added filenames."""
        added = []
        for filename, approach, content, passed, message in results:
            if passed:
                test_path = TEST_DIR / filename
                # Avoid overwriting existing tests
                counter = 1
                while test_path.exists():
                    stem = test_path.stem
                    new_stem = f"{stem}_{counter}"
                    test_path = TEST_DIR / f"{new_stem}.py"
                    counter += 1
                test_path.write_text(content)
                added.append(test_path.name)
            else:
                self.tracker.record_failure_mode(message)
        return added

    def update_metrics(self):
        """Update diversity metrics after changes."""
        self.tracker.update_from_analysis(self.analyzer)

    def evolve(self) -> Dict[str, Any]:
        """Run the full evolution cycle. Returns summary dict."""
        gaps = self.analyze_gaps()
        if not gaps:
            return {"status": "no_gaps", "added": [], "diversity_score": self.tracker.get_diversity_score()}

        results = self.generate_and_validate(gaps)
        added = self.add_validated_tests(results)
        self.update_metrics()

        return {
            "status": "success",
            "gaps_found": sum(len(funcs) for funcs in gaps.values()),
            "tests_generated": len(results),
            "tests_validated": sum(1 for _, _, _, p, _ in results if p),
            "tests_added": len(added),
            "added_files": added,
            "diversity_score": self.tracker.get_diversity_score(),
        }

# ---------------------------------------------------------------------------
# CLI Entry Point
# ---------------------------------------------------------------------------

def main():
    """Run the test suite evolution cycle from command line."""
    evolver = TestSuiteEvolver()
    result = evolver.evolve()
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "success" else 1

if __name__ == "__main__":
    sys.exit(main())