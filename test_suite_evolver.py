import os
import sys
import importlib.util
import ast
import tempfile
import shutil
from pathlib import Path
from typing import List, Optional, Set

class TestSuiteEvolver:
    """
    A minimal, self-contained module that scans the tests/ directory for existing test files,
    identifies untested modules, generates new test files for untested modules,
    validates them by import, and rolls back on failure.
    """

    def __init__(self, project_root: str = "."):
        self.project_root = Path(project_root).resolve()
        self.tests_dir = self.project_root / "tests"
        self.source_dirs = [self.project_root / "core", self.project_root / "utils", self.project_root]
        self._ensure_tests_dir()

    def _ensure_tests_dir(self):
        """Ensure the tests directory exists."""
        self.tests_dir.mkdir(parents=True, exist_ok=True)
        # Ensure __init__.py exists
        init_file = self.tests_dir / "__init__.py"
        if not init_file.exists():
            init_file.write_text("")

    def scan_existing_test_files(self) -> List[Path]:
        """Scan the tests/ directory for existing test files (test_*.py)."""
        if not self.tests_dir.exists():
            return []
        return sorted(self.tests_dir.glob("test_*.py"))

    def get_all_python_modules(self) -> Set[str]:
        """Get all .py files in the project (excluding tests and __init__)."""
        modules = set()
        for src_dir in self.source_dirs:
            if src_dir.exists():
                for py_file in src_dir.rglob("*.py"):
                    if py_file.name == "__init__.py":
                        continue
                    if "tests" in py_file.parts:
                        continue
                    # Get module name relative to project root
                    rel_path = py_file.relative_to(self.project_root)
                    module_name = str(rel_path.with_suffix("")).replace(os.sep, ".")
                    modules.add(module_name)
        return modules

    def get_tested_modules(self) -> Set[str]:
        """Extract module names imported in existing test files."""
        tested = set()
        for test_file in self.scan_existing_test_files():
            try:
                tree = ast.parse(test_file.read_text())
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            tested.add(alias.name)
                    elif isinstance(node, ast.ImportFrom):
                        if node.module:
                            tested.add(node.module)
            except SyntaxError:
                continue
        return tested

    def identify_untested_modules(self) -> List[str]:
        """Identify modules that have no corresponding test file."""
        all_modules = self.get_all_python_modules()
        tested_modules = self.get_tested_modules()
        untested = []
        for mod in sorted(all_modules):
            # Check if a test file exists for this module
            test_file_name = f"test_{mod.split('.')[-1]}.py"
            test_file_path = self.tests_dir / test_file_name
            if not test_file_path.exists() and mod not in tested_modules:
                untested.append(mod)
        return untested

    def generate_test_file(self, module_name: str) -> Optional[Path]:
        """Generate a simple test file for an untested module using a template."""
        test_file_name = f"test_{module_name.split('.')[-1]}.py"
        test_file_path = self.tests_dir / test_file_name

        # Template for the test file
        template = f'''"""
Auto-generated test for {module_name}
"""
import pytest
import {module_name}


class Test{module_name.split(".")[-1].capitalize()}:
    """Test class for {module_name}."""

    def test_import(self):
        """Test that the module can be imported."""
        assert {module_name} is not None

    def test_basic_functionality(self):
        """Basic functionality test - placeholder."""
        # TODO: Add actual tests for {module_name}
        pass
'''
        test_file_path.write_text(template)
        return test_file_path

    def validate_test_file(self, test_file_path: Path) -> bool:
        """Validate the generated test file by importing it."""
        try:
            # Add project root to sys.path
            sys.path.insert(0, str(self.project_root))
            # Try to import the test module
            spec = importlib.util.spec_from_file_location(
                test_file_path.stem, str(test_file_path)
            )
            if spec is None or spec.loader is None:
                return False
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return True
        except Exception:
            return False
        finally:
            # Clean up sys.path
            if str(self.project_root) in sys.path:
                sys.path.remove(str(self.project_root))

    def rollback_test_file(self, test_file_path: Path):
        """Roll back by deleting the generated test file."""
        if test_file_path.exists():
            test_file_path.unlink()
            print(f"Rolled back: removed {test_file_path}")

    def evolve_test_suite(self) -> List[str]:
        """
        Main method: scan, identify untested modules, generate tests, validate, rollback on failure.
        Returns a list of successfully generated test module names.
        """
        successful = []
        untested = self.identify_untested_modules()
        if not untested:
            print("No untested modules found.")
            return successful

        for module_name in untested:
            test_file_path = self.generate_test_file(module_name)
            if test_file_path is None:
                continue
            if self.validate_test_file(test_file_path):
                successful.append(module_name)
                print(f"Successfully generated test for {module_name}")
            else:
                self.rollback_test_file(test_file_path)
                print(f"Failed to validate test for {module_name}, rolled back")
        return successful


if __name__ == "__main__":
    evolver = TestSuiteEvolver()
    evolver.evolve_test_suite()