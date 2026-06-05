import pytest
import tempfile
import os
import sys
import ast
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.test_suite_mutator import TestSuiteMutator


@pytest.fixture
def temp_test_file():
    """Create a temporary test file for mutation testing."""
    content = """
import pytest

def test_existing():
    assert True

def test_another():
    assert 1 + 1 == 2
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(content)
        temp_path = f.name
    
    yield temp_path
    
    # Cleanup
    if os.path.exists(temp_path):
        os.unlink(temp_path)
    # Also cleanup any __pycache__ that might have been created
    cache_dir = os.path.join(os.path.dirname(temp_path), '__pycache__')
    if os.path.exists(cache_dir):
        for cache_file in os.listdir(cache_dir):
            os.unlink(os.path.join(cache_dir, cache_file))
        os.rmdir(cache_dir)


def test_test_suite_mutation(temp_test_file):
    """Test that TestSuiteMutator correctly adds new test functions."""
    # Create mutator instance
    mutator = TestSuiteMutator(temp_test_file)
    
    # Run mutation
    mutator.mutate()
    
    # Read the modified file
    with open(temp_test_file, 'r') as f:
        modified_content = f.read()
    
    # Parse the modified file to find test functions
    tree = ast.parse(modified_content)
    test_functions = [
        node.name for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name.startswith('test_')
    ]
    
    # Verify new test functions were added
    assert len(test_functions) > 2, f"Expected more than 2 test functions, found {len(test_functions)}"
    assert 'test_existing' in test_functions
    assert 'test_another' in test_functions
    
    # Verify the new tests are runnable by importing the module
    module_name = os.path.splitext(os.path.basename(temp_test_file))[0]
    spec = importlib.util.spec_from_file_location(module_name, temp_test_file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    
    # Verify all test functions can be called
    for func_name in test_functions:
        test_func = getattr(module, func_name)
        test_func()  # This will raise an exception if the test fails
    
    # Verify no syntax errors in the modified file
    try:
        compile(modified_content, temp_test_file, 'exec')
    except SyntaxError as e:
        pytest.fail(f"Modified file has syntax error: {e}")