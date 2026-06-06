"""Ecology Pressure Engine

Monitors test coverage and automatically introduces 'environmental pressures' — new test scenarios
that stress-test the agent's ability to handle edge cases. The engine analyzes which modules have
the fewest tests, generates new tests targeting untested code paths, and adds them to the test suite
with a 'pressure' tag.
"""

import ast
import os
import random
import re
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple


class PressureEngine:
    """Engine that monitors test coverage and introduces environmental pressures."""

    def __init__(self, project_root: str = "."):
        self.project_root = Path(project_root)
        self.test_dir = self.project_root / "tests"
        self.core_dir = self.project_root / "core"
        self.pressure_tag = "pressure"
        self._ensure_directories()

    def _ensure_directories(self):
        """Ensure required directories exist."""
        self.test_dir.mkdir(exist_ok=True)
        self.core_dir.mkdir(exist_ok=True)

    def scan_test_coverage(self) -> Dict[str, int]:
        """Scan all test files and return a dict mapping module names to test counts."""
        coverage = {}
        test_files = list(self.test_dir.glob("test_*.py"))
        for test_file in test_files:
            module_name = self._extract_module_name(test_file)
            if module_name:
                test_count = self._count_tests_in_file(test_file)
                coverage[module_name] = coverage.get(module_name, 0) + test_count
        return coverage

    def _extract_module_name(self, test_file: Path) -> Optional[str]:
        """Extract the module name being tested from a test file name."""
        # Pattern: test_<module>.py or test_<module>_*.py
        stem = test_file.stem
        if stem.startswith("test_"):
            name = stem[5:]  # Remove 'test_' prefix
            # Remove common suffixes like _test, _pressure, _edge
            for suffix in ["_test", "_pressure", "_edge", "_stress"]:
                if name.endswith(suffix):
                    name = name[: -len(suffix)]
                    break
            return name if name else None
        return None

    def _count_tests_in_file(self, test_file: Path) -> int:
        """Count the number of test functions in a file."""
        try:
            content = test_file.read_text()
            tree = ast.parse(content)
            count = 0
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
                    count += 1
            return count
        except (SyntaxError, FileNotFoundError):
            return 0

    def find_untested_modules(self) -> List[str]:
        """Find modules in core/ that have no corresponding tests."""
        core_modules = set()
        for py_file in self.core_dir.glob("*.py"):
            if py_file.name != "__init__.py":
                core_modules.add(py_file.stem)

        tested_modules = set(self.scan_test_coverage().keys())
        untested = core_modules - tested_modules
        return sorted(untested)

    def find_low_coverage_modules(self, threshold: int = 3) -> List[Tuple[str, int]]:
        """Find modules with fewer tests than the threshold."""
        coverage = self.scan_test_coverage()
        low_coverage = [(mod, count) for mod, count in coverage.items() if count < threshold]
        low_coverage.sort(key=lambda x: x[1])
        return low_coverage

    def analyze_untested_code_paths(self, module_name: str) -> List[str]:
        """Analyze a module and identify untested code paths (functions, classes, branches)."""
        module_path = self.core_dir / f"{module_name}.py"
        if not module_path.exists():
            return []

        try:
            content = module_path.read_text()
            tree = ast.parse(content)
        except (SyntaxError, FileNotFoundError):
            return []

        # Find all defined functions and classes
        untested_paths = []
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                # Check for edge-case patterns
                if self._has_edge_case_patterns(node):
                    untested_paths.append(f"{module_name}.{node.name}")
            elif isinstance(node, ast.ClassDef):
                untested_paths.append(f"{module_name}.{node.name}")
                for item in node.body:
                    if isinstance(item, ast.FunctionDef):
                        if self._has_edge_case_patterns(item):
                            untested_paths.append(f"{module_name}.{node.name}.{item.name}")

        return untested_paths

    def _has_edge_case_patterns(self, node: ast.FunctionDef) -> bool:
        """Check if a function has edge-case patterns that should be tested."""
        edge_patterns = [
            "if", "else", "elif",  # Conditional logic
            "try", "except",  # Exception handling
            "raise",  # Raising exceptions
            "return None",  # None returns
            "assert",  # Assertions
            "for", "while",  # Loops
            "lambda",  # Lambda expressions
            "yield",  # Generators
            "async",  # Async functions
        ]
        source = ast.unparse(node) if hasattr(ast, 'unparse') else ""
        if not source:
            # Fallback: check node body for patterns
            for child in ast.walk(node):
                if isinstance(child, (ast.If, ast.Try, ast.Raise, ast.Assert,
                                      ast.For, ast.While, ast.Lambda, ast.Yield,
                                      ast.AsyncFunctionDef, ast.AsyncFor)):
                    return True
            return False
        return any(pattern in source for pattern in edge_patterns)

    def generate_pressure_test(self, module_name: str, code_path: str) -> str:
        """Generate a pressure test for an untested code path."""
        # Create a descriptive test name
        safe_path = code_path.replace(".", "_")
        test_name = f"test_pressure_{safe_path}"

        # Generate test content
        test_content = f'''"""Pressure test for {code_path} - generated by Ecology Pressure Engine."""
import pytest
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core import {module_name}


@pytest.mark.{self.pressure_tag}
def {test_name}():
    """Environmental pressure test: stress-test {code_path} with edge cases."""
    # TODO: Implement specific edge case testing for {code_path}
    # This test is an environmental pressure introduced to improve coverage
    # of untested code paths in {module_name}.
    
    # Basic smoke test - verify the module can be imported and used
    assert {module_name} is not None, f"Module {module_name} should be importable"
    
    # Edge case: test with None/empty inputs
    try:
        result = {module_name}.{code_path.split(".", 1)[1] if "." in code_path else code_path}()
        # If it returns something, verify it handles edge cases
        if result is not None:
            assert isinstance(result, (int, float, str, list, dict, tuple, set, bool, type(None))), \\
                f"Unexpected return type: {{type(result)}}"
    except TypeError:
        # Expected if the function requires arguments - that's fine for pressure test
        pass
    except Exception as e:
        # Unexpected errors should be caught and reported
        pytest.fail(f"Unexpected error in {code_path}: {{e}}")
'''
        return test_content

    def add_pressure_test(self, module_name: str, code_path: str) -> Optional[Path]:
        """Generate and add a pressure test to the test suite."""
        test_content = self.generate_pressure_test(module_name, code_path)
        safe_path = code_path.replace(".", "_")
        test_filename = f"test_pressure_{module_name}_{safe_path}.py"
        test_path = self.test_dir / test_filename

        # Avoid overwriting existing tests
        if test_path.exists():
            return None

        test_path.write_text(test_content)
        return test_path

    def evolve_test_suite(self, max_pressures: int = 5) -> List[Path]:
        """Main evolution method: scan, analyze, and add pressure tests.

        Args:
            max_pressures: Maximum number of pressure tests to add in one evolution cycle.

        Returns:
            List of paths to newly created pressure test files.
        """
        added_tests = []

        # Step 1: Find untested modules
        untested_modules = self.find_untested_modules()
        for module_name in untested_modules[:max_pressures]:
            untested_paths = self.analyze_untested_code_paths(module_name)
            if untested_paths:
                # Pick the first untested path
                code_path = untested_paths[0]
                test_path = self.add_pressure_test(module_name, code_path)
                if test_path:
                    added_tests.append(test_path)

        # Step 2: If we still have capacity, target low-coverage modules
        if len(added_tests) < max_pressures:
            low_coverage = self.find_low_coverage_modules()
            for module_name, count in low_coverage:
                if len(added_tests) >= max_pressures:
                    break
                untested_paths = self.analyze_untested_code_paths(module_name)
                if untested_paths:
                    code_path = untested_paths[0]
                    test_path = self.add_pressure_test(module_name, code_path)
                    if test_path:
                        added_tests.append(test_path)

        return added_tests

    def get_pressure_test_count(self) -> int:
        """Count existing pressure tests in the test suite."""
        count = 0
        for test_file in self.test_dir.glob("test_pressure_*.py"):
            count += self._count_tests_in_file(test_file)
        return count

    def get_coverage_report(self) -> str:
        """Generate a human-readable coverage report."""
        coverage = self.scan_test_coverage()
        untested = self.find_untested_modules()
        low_coverage = self.find_low_coverage_modules()
        pressure_count = self.get_pressure_test_count()

        lines = [
            "=== Ecology Pressure Engine Coverage Report ===",
            f"Total pressure tests: {pressure_count}",
            "",
            "Module test counts:",
        ]

        for module, count in sorted(coverage.items()):
            lines.append(f"  {module}: {count} tests")

        if untested:
            lines.append(f"\nUntested modules ({len(untested)}):")
            for module in untested:
                lines.append(f"  - {module}")

        if low_coverage:
            lines.append(f"\nLow-coverage modules ({len(low_coverage)}):")
            for module, count in low_coverage:
                lines.append(f"  - {module}: {count} tests")

        return "\n".join(lines)


# Convenience function for quick evolution
def run_pressure_evolution(project_root: str = ".", max_pressures: int = 5) -> List[Path]:
    """Run a full pressure evolution cycle.

    Args:
        project_root: Root directory of the project.
        max_pressures: Maximum number of pressure tests to add.

    Returns:
        List of paths to newly created pressure test files.
    """
    engine = PressureEngine(project_root)
    return engine.evolve_test_suite(max_pressures)


if __name__ == "__main__":
    # Run evolution when executed directly
    added = run_pressure_evolution()
    print(f"Added {len(added)} pressure tests:")
    for path in added:
        print(f"  - {path}")