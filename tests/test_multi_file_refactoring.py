import os
import sys
import tempfile
import shutil
import ast
import unittest
from pathlib import Path

# Adjust import path to include the project root
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import the modules to be tested
# These are placeholder imports; adjust to match actual module names in your project
from refactoring_tools.dependency_graph import DependencyGraph
from refactoring_tools.circular_import_detector import CircularImportDetector
from refactoring_tools.function_mover import FunctionMover
from refactoring_tools.rename_across_files import RenameAcrossFiles
from refactoring_tools.code_smell_detector import CodeSmellDetector
from refactoring_tools.rollback_manager import RollbackManager


class TestMultiFileRefactoring(unittest.TestCase):
    """Comprehensive test suite for multi-file analysis and refactoring."""

    def setUp(self):
        """Create a temporary test project with multiple inter-dependent files."""
        self.test_dir = tempfile.mkdtemp()
        self.project_root = Path(self.test_dir)
        self._create_test_project()

    def tearDown(self):
        """Clean up the temporary test project."""
        shutil.rmtree(self.test_dir)

    def _create_test_project(self):
        """Create a structured test project with inter-dependent Python files."""
        # File: utils.py
        utils_code = """
def helper_function():
    return "helper"

def add(a, b):
    return a + b
"""
        (self.project_root / 'utils.py').write_text(utils_code)

        # File: math_ops.py
        math_ops_code = """
from utils import add, helper_function

def multiply(a, b):
    return a * b

def compute_sum(a, b):
    return add(a, b)

def compute_and_log(a, b):
    result = add(a, b)
    log = helper_function()
    return result, log
"""
        (self.project_root / 'math_ops.py').write_text(math_ops_code)

        # File: data_processor.py
        data_processor_code = """
from math_ops import multiply, compute_sum
from utils import helper_function

def process_data(x, y):
    product = multiply(x, y)
    total = compute_sum(x, y)
    return product, total

def log_processing(x, y):
    msg = helper_function()
    product, total = process_data(x, y)
    return f"{msg}: product={product}, sum={total}"
"""
        (self.project_root / 'data_processor.py').write_text(data_processor_code)

        # File: main.py
        main_code = """
from data_processor import process_data, log_processing
from math_ops import compute_sum

def main():
    result = process_data(3, 4)
    print(result)
    print(log_processing(3, 4))

if __name__ == "__main__":
    main()
"""
        (self.project_root / 'main.py').write_text(main_code)

        # File: circular_a.py (introduces circular import)
        circular_a_code = """
from circular_b import func_b

def func_a():
    return func_b()
"""
        (self.project_root / 'circular_a.py').write_text(circular_a_code)

        # File: circular_b.py (completes the circular import)
        circular_b_code = """
from circular_a import func_a

def func_b():
    return "b"
"""
        (self.project_root / 'circular_b.py').write_text(circular_b_code)

        # File: smell_example.py (contains code smells)
        smell_code = """
import os
import sys

def long_function():
    a = 1
    b = 2
    c = 3
    d = 4
    e = 5
    f = 6
    g = 7
    h = 8
    i = 9
    j = 10
    k = 11
    l = 12
    m = 13
    n = 14
    o = 15
    p = 16
    q = 17
    r = 18
    s = 19
    t = 20
    return a + b + c + d + e + f + g + h + i + j + k + l + m + n + o + p + q + r + s + t

def duplicate_code():
    x = 5
    y = 10
    z = x + y
    return z

def duplicate_code_again():
    x = 5
    y = 10
    z = x + y
    return z

def too_many_arguments(a, b, c, d, e, f, g, h, i, j):
    return a + b + c + d + e + f + g + h + i + j
"""
        (self.project_root / 'smell_example.py').write_text(smell_code)

    # ----------------------------------------------------------------------
    # Tests for Dependency Graph
    # ----------------------------------------------------------------------
    def test_build_dependency_graph(self):
        """Test building a dependency graph from the project."""
        dep_graph = DependencyGraph(self.project_root)
        graph = dep_graph.build()
        # Check that 'utils.py' is a dependency of 'math_ops.py'
        self.assertIn('utils.py', graph.get('math_ops.py', []))
        # Check that 'math_ops.py' is a dependency of 'data_processor.py'
        self.assertIn('math_ops.py', graph.get('data_processor.py', []))
        # Check that 'data_processor.py' is a dependency of 'main.py'
        self.assertIn('data_processor.py', graph.get('main.py', []))

    def test_dependency_graph_no_circular(self):
        """Test that the dependency graph does not include circular dependencies by default."""
        dep_graph = DependencyGraph(self.project_root)
        graph = dep_graph.build()
        # Ensure no self-loops or immediate circular references in non-circular files
        for module, deps in graph.items():
            for dep in deps:
                self.assertNotIn(module, graph.get(dep, []))

    # ----------------------------------------------------------------------
    # Tests for Circular Import Detection
    # ----------------------------------------------------------------------
    def test_detect_circular_imports(self):
        """Test detection of circular imports in the project."""
        detector = CircularImportDetector(self.project_root)
        cycles = detector.detect()
        # Expect at least one cycle involving circular_a.py and circular_b.py
        cycle_found = False
        for cycle in cycles:
            if 'circular_a.py' in cycle and 'circular_b.py' in cycle:
                cycle_found = True
                break
        self.assertTrue(cycle_found, "Circular import between circular_a.py and circular_b.py not detected")

    def test_no_false_positive_circular_imports(self):
        """Test that non-circular imports are not flagged."""
        detector = CircularImportDetector(self.project_root)
        cycles = detector.detect()
        # Ensure that 'utils.py' is not part of any cycle
        for cycle in cycles:
            self.assertNotIn('utils.py', cycle, "False positive circular import detected for utils.py")

    # ----------------------------------------------------------------------
    # Tests for Moving a Function Between Files with Import Updates
    # ----------------------------------------------------------------------
    def test_move_function_between_files(self):
        """Test moving a function from one file to another and updating imports."""
        mover = FunctionMover(self.project_root)
        # Move 'helper_function' from utils.py to math_ops.py
        success = mover.move_function('utils.py', 'helper_function', 'math_ops.py')
        self.assertTrue(success, "Function move operation failed")

        # Verify that 'helper_function' is no longer in utils.py
        utils_ast = ast.parse((self.project_root / 'utils.py').read_text())
        utils_functions = [node.name for node in ast.walk(utils_ast) if isinstance(node, ast.FunctionDef)]
        self.assertNotIn('helper_function', utils_functions)

        # Verify that 'helper_function' is now in math_ops.py
        math_ops_ast = ast.parse((self.project_root / 'math_ops.py').read_text())
        math_ops_functions = [node.name for node in ast.walk(math_ops_ast) if isinstance(node, ast.FunctionDef)]
        self.assertIn('helper_function', math_ops_functions)

        # Verify that imports in other files are updated
        # data_processor.py imports helper_function from utils, should now import from math_ops
        data_processor_code = (self.project_root / 'data_processor.py').read_text()
        self.assertIn('from math_ops import helper_function', data_processor_code)
        self.assertNotIn('from utils import helper_function', data_processor_code)

        # math_ops.py should have a self-import removed if it imported from itself
        math_ops_code = (self.project_root / 'math_ops.py').read_text()
        self.assertNotIn('from math_ops import', math_ops_code)

    def test_move_function_updates_all_references(self):
        """Test that moving a function updates all references across files."""
        mover = FunctionMover(self.project_root)
        mover.move_function('utils.py', 'helper_function', 'math_ops.py')
        # Check main.py still works (it indirectly uses helper_function via data_processor)
        main_code = (self.project_root / 'main.py').read_text()
        # main.py does not directly import helper_function, but it imports from data_processor
        # which should have updated import
        self.assertIn('from math_ops import helper_function', (self.project_root / 'data_processor.py').read_text())

    # ----------------------------------------------------------------------
    # Tests for Renaming Across Files
    # ----------------------------------------------------------------------
    def test_rename_function_across_files(self):
        """Test renaming a function and updating all references across files."""
        renamer = RenameAcrossFiles(self.project_root)
        # Rename 'add' to 'sum_numbers' in utils.py
        success = renamer.rename('utils.py', 'add', 'sum_numbers')
        self.assertTrue(success, "Rename operation failed")

        # Verify that the function definition is updated in utils.py
        utils_code = (self.project_root / 'utils.py').read_text()
        self.assertIn('def sum_numbers', utils_code)
        self.assertNotIn('def add', utils_code)

        # Verify that all references in other files are updated
        for file_name in ['math_ops.py', 'data_processor.py']:
            file_code = (self.project_root / file_name).read_text()
            self.assertIn('sum_numbers', file_code)
            self.assertNotIn('add', file_code)

    def test_rename_class_across_files(self):
        """Test renaming a class and updating all references across files."""
        # First, add a class to utils.py for testing
        utils_code = (self.project_root / 'utils.py').read_text()
        utils_code += "\n\nclass MyClass:\n    pass\n"
        (self.project_root / 'utils.py').write_text(utils_code)

        # Add usage in math_ops.py
        math_ops_code = (self.project_root / 'math_ops.py').read_text()
        math_ops_code += "\nfrom utils import MyClass\nobj = MyClass()\n"
        (self.project_root / 'math_ops.py').write_text(math_ops_code)

        renamer = RenameAcrossFiles(self.project_root)
        success = renamer.rename('utils.py', 'MyClass', 'RenamedClass')
        self.assertTrue(success, "Class rename operation failed")

        # Verify class definition updated
        utils_code = (self.project_root / 'utils.py').read_text()
        self.assertIn('class RenamedClass', utils_code)
        self.assertNotIn('class MyClass', utils_code)

        # Verify references updated
        math_ops_code = (self.project_root / 'math_ops.py').read_text()
        self.assertIn('RenamedClass', math_ops_code)
        self.assertNotIn('MyClass', math_ops_code)

    # ----------------------------------------------------------------------
    # Tests for Code Smell Detection
    # ----------------------------------------------------------------------
    def test_detect_long_function(self):
        """Test detection of long functions."""
        detector = CodeSmellDetector(self.project_root)
        smells = detector.detect()
        long_func_smells = [s for s in smells if s.smell_type == 'long_function' and s.file == 'smell_example.py']
        self.assertTrue(any('long_function' in s.name for s in long_func_smells),
                        "Long function not detected")

    def test_detect_duplicate_code(self):
        """Test detection of duplicate code."""
        detector = CodeSmellDetector(self.project_root)
        smells = detector.detect()
        duplicate_smells = [s for s in smells if s.smell_type == 'duplicate_code']
        # There are two duplicate functions in smell_example.py
        self.assertTrue(len(duplicate_smells) >= 1, "Duplicate code not detected")

    def test_detect_too_many_arguments(self):
        """Test detection of functions with too many arguments."""
        detector = CodeSmellDetector(self.project_root)
        smells = detector.detect()
        many_args_smells = [s for s in smells if s.smell_type == 'too_many_arguments']
        self.assertTrue(any('too_many_arguments' in s.name for s in many_args_smells),
                        "Function with too many arguments not detected")

    # ----------------------------------------------------------------------
    # Tests for Rollback on Failure
    # ----------------------------------------------------------------------
    def test_rollback_on_move_failure(self):
        """Test that a failed move operation rolls back all changes."""
        # Backup original content
        original_utils = (self.project_root / 'utils.py').read_text()
        original_math_ops = (self.project_root / 'math_ops.py').read_text()

        mover = FunctionMover(self.project_root)
        # Attempt to move a non-existent function to trigger failure
        success = mover.move_function('utils.py', 'non_existent_func', 'math_ops.py')
        self.assertFalse(success, "Move should have failed for non-existent function")

        # Verify that files are unchanged
        self.assertEqual((self.project_root / 'utils.py').read_text(), original_utils)
        self.assertEqual((self.project_root / 'math_ops.py').read_text(), original_math_ops)

    def test_rollback_on_rename_failure(self):
        """Test that a failed rename operation rolls back all changes."""
        original_utils = (self.project_root / 'utils.py').read_text()
        original_math_ops = (self.project_root / 'math_ops.py').read_text()

        renamer = RenameAcrossFiles(self.project_root)
        # Attempt to rename a non-existent function
        success = renamer.rename('utils.py', 'non_existent', 'new_name')
        self.assertFalse(success, "Rename should have failed for non-existent function")

        # Verify files unchanged
        self.assertEqual((self.project_root / 'utils.py').read_text(), original_utils)
        self.assertEqual((self.project_root / 'math_ops.py').read_text(), original_math_ops)

    def test_rollback_manager(self):
        """Test the RollbackManager directly."""
        manager = RollbackManager()
        # Simulate a series of changes
        file_path = self.project_root / 'test_rollback.txt'
        file_path.write_text("original content")

        # Record a change
        manager.record_change(str(file_path), "original content", "new content")
        # Apply the change
        file_path.write_text("new content")
        self.assertEqual(file_path.read_text(), "new content")

        # Rollback
        manager.rollback()
        self.assertEqual(file_path.read_text(), "original content")

    def test_rollback_on_exception_during_move(self):
        """Test that if an exception occurs during move, rollback is triggered."""
        mover = FunctionMover(self.project_root)
        # Backup original content
        original_utils = (self.project_root / 'utils.py').read_text()
        original_math_ops = (self.project_root / 'math_ops.py').read_text()

        # Simulate an error by making a file read-only temporarily
        (self.project_root / 'math_ops.py').chmod(0o444)  # read-only
        try:
            success = mover.move_function('utils.py', 'helper_function', 'math_ops.py')
            self.assertFalse(success, "Move should have failed due to permission error")
        finally:
            # Restore permissions
            (self.project_root / 'math_ops.py').chmod(0o644)

        # Verify files are unchanged
        self.assertEqual((self.project_root / 'utils.py').read_text(), original_utils)
        self.assertEqual((self.project_root / 'math_ops.py').read_text(), original_math_ops)


if __name__ == '__main__':
    unittest.main()