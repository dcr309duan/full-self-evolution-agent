import ast
import importlib
import importlib.util
import os
import sys
import traceback
from pathlib import Path
from typing import List, Optional, Set


class TestImportValidator:
    """
    Validates that newly created test files can be imported without errors
    before they are added to the test suite. This prevents the import
    failures that have occurred in past evolution attempts.
    """

    def __init__(self, project_root: Optional[str] = None):
        self.project_root = project_root or os.getcwd()
        self._failed_imports: Set[str] = set()

    def validate_new_tests(self, test_paths: List[str]) -> List[str]:
        """
        Validate a list of test file paths by attempting to import each one.

        Args:
            test_paths: List of absolute or relative paths to test files

        Returns:
            List of paths that passed validation (can be safely imported)
        """
        valid_tests = []
        for test_path in test_paths:
            if self._validate_single_test(test_path):
                valid_tests.append(test_path)
            else:
                self._failed_imports.add(test_path)
        return valid_tests

    def _validate_single_test(self, test_path: str) -> bool:
        """Attempt to import a single test file and return True if successful."""
        abs_path = os.path.abspath(test_path)
        if not os.path.exists(abs_path):
            print(f"[TestImportValidator] File does not exist: {abs_path}")
            return False

        # First, do a static syntax check using ast.parse
        try:
            with open(abs_path, "r") as f:
                source = f.read()
            ast.parse(source)
        except SyntaxError as e:
            print(f"[TestImportValidator] Syntax error in {test_path}: {e}")
            return False

        # Now attempt a dynamic import
        try:
            # Get the module name from the file path
            module_name = self._path_to_module_name(abs_path)

            # Ensure the project root is in sys.path
            if self.project_root not in sys.path:
                sys.path.insert(0, self.project_root)

            # Import the module
            spec = importlib.util.spec_from_file_location(module_name, abs_path)
            if spec is None:
                print(f"[TestImportValidator] Could not create spec for {test_path}")
                return False

            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            # Clean up: remove the module from sys.modules to avoid side effects
            if module_name in sys.modules:
                del sys.modules[module_name]

            print(f"[TestImportValidator] Successfully validated: {test_path}")
            return True

        except Exception as e:
            print(f"[TestImportValidator] Import failed for {test_path}:")
            traceback.print_exc()
            return False

    def _path_to_module_name(self, abs_path: str) -> str:
        """Convert an absolute file path to a Python module name."""
        rel_path = os.path.relpath(abs_path, self.project_root)
        # Remove .py extension
        if rel_path.endswith(".py"):
            rel_path = rel_path[:-3]
        # Replace path separators with dots
        module_name = rel_path.replace(os.sep, ".")
        return module_name

    def get_failed_imports(self) -> List[str]:
        """Return the list of test files that failed validation."""
        return list(self._failed_imports)

    def clear_failed_imports(self) -> None:
        """Clear the record of failed imports."""
        self._failed_imports.clear()


def validate_new_tests(test_paths: List[str], project_root: Optional[str] = None) -> List[str]:
    """
    Convenience function to validate new test files.

    Args:
        test_paths: List of paths to test files to validate
        project_root: Root directory of the project (defaults to current working directory)

    Returns:
        List of test file paths that passed validation
    """
    validator = TestImportValidator(project_root)
    return validator.validate_new_tests(test_paths)


# Example usage when run as a script
if __name__ == "__main__":
    # If called directly, validate test files passed as command-line arguments
    import sys as _sys
    if len(_sys.argv) > 1:
        test_files = _sys.argv[1:]
        valid = validate_new_tests(test_files)
        print(f"\nValidation complete.")
        print(f"  Valid tests: {len(valid)}")
        print(f"  Failed tests: {len(test_files) - len(valid)}")
        if valid:
            print(f"  Valid files: {valid}")
        _sys.exit(0 if len(valid) == len(test_files) else 1)
    else:
        print("Usage: python integration_test_runner.py <test_file1.py> [test_file2.py ...]")
        _sys.exit(1)