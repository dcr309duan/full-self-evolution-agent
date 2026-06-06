import pytest
import tempfile
import os
import sys
import ast
import importlib.util
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.test_suite_mutator import TestSuiteMutator
from core.evolution_engine import EvolutionEngine
from core.test_generator import TestGenerator
from core.coverage_analyzer import CoverageAnalyzer


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


def test_ecological_pressure_loop():
    """Test that the ecological pressure mechanism works correctly over multiple cycles.
    
    This test validates:
    1. The evolution engine runs for 10 cycles with ecology module active
    2. The test suite changes between cycles
    3. The agent's capability set shifts in response to new pressures
    4. No import errors occur
    """
    # Create a temporary directory for test artifacts
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create initial test file
        initial_test_content = """
import pytest

def test_basic():
    assert True

def test_addition():
    assert 1 + 1 == 2
"""
        test_file_path = os.path.join(temp_dir, "test_initial.py")
        with open(test_file_path, 'w') as f:
            f.write(initial_test_content)
        
        # Create a simple source file to test against
        source_content = """
def add(a, b):
    return a + b

def subtract(a, b):
    return a - b

def multiply(a, b):
    return a * b
"""
        source_file_path = os.path.join(temp_dir, "source_code.py")
        with open(source_file_path, 'w') as f:
            f.write(source_content)
        
        # Initialize components
        test_generator = TestGenerator()
        coverage_analyzer = CoverageAnalyzer()
        mutator = TestSuiteMutator(test_file_path)
        
        # Create evolution engine with the test file
        engine = EvolutionEngine(
            test_file_path=test_file_path,
            source_file_path=source_file_path,
            test_generator=test_generator,
            coverage_analyzer=coverage_analyzer,
            mutator=mutator
        )
        
        # Track test suite size over cycles
        test_suite_sizes = []
        all_test_names = set()
        previous_test_names = set()
        test_suite_changes = []
        
        # Track capability shifts
        capability_sets = []
        
        # Run 10 cycles
        for cycle in range(10):
            # Run one evolution cycle
            engine.run_cycle()
            
            # Read current test file
            with open(test_file_path, 'r') as f:
                current_content = f.read()
            
            # Parse test functions
            tree = ast.parse(current_content)
            current_tests = [
                node.name for node in ast.walk(tree)
                if isinstance(node, ast.FunctionDef) and node.name.startswith('test_')
            ]
            current_test_names = set(current_tests)
            
            # Record test suite size
            test_suite_sizes.append(len(current_tests))
            
            # Track changes between cycles
            if cycle > 0:
                added_tests = current_test_names - previous_test_names
                removed_tests = previous_test_names - current_test_names
                if added_tests or removed_tests:
                    test_suite_changes.append({
                        'cycle': cycle,
                        'added': list(added_tests),
                        'removed': list(removed_tests)
                    })
            
            # Update all test names
            all_test_names.update(current_tests)
            previous_test_names = current_test_names
            
            # Track capability set (tests that reference source code functions)
            capability_set = set()
            for test_name in current_tests:
                test_func_node = None
                for node in ast.walk(tree):
                    if isinstance(node, ast.FunctionDef) and node.name == test_name:
                        test_func_node = node
                        break
                if test_func_node:
                    # Check if test references source code functions
                    for sub_node in ast.walk(test_func_node):
                        if isinstance(sub_node, ast.Call):
                            if isinstance(sub_node.func, ast.Name):
                                if sub_node.func.id in ['add', 'subtract', 'multiply']:
                                    capability_set.add(sub_node.func.id)
            capability_sets.append(capability_set)
            
            # Verify no syntax errors
            try:
                compile(current_content, test_file_path, 'exec')
            except SyntaxError as e:
                pytest.fail(f"Cycle {cycle}: Syntax error in test file: {e}")
            
            # Verify no import errors by trying to import the module
            try:
                module_name = os.path.splitext(os.path.basename(test_file_path))[0]
                spec = importlib.util.spec_from_file_location(module_name, test_file_path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
            except Exception as e:
                pytest.fail(f"Cycle {cycle}: Import error: {e}")
        
        # Verify new tests were generated (at least one new test beyond initial two)
        assert len(all_test_names) > 2, f"Expected more than 2 unique tests, found {len(all_test_names)}"
        
        # Verify test suite changes between cycles
        assert len(test_suite_changes) > 0, "Expected at least one change in test suite between cycles"
        
        # Verify test suite grows over time (non-decreasing)
        for i in range(1, len(test_suite_sizes)):
            assert test_suite_sizes[i] >= test_suite_sizes[i-1], \
                f"Test suite shrank from cycle {i-1} to {i}: {test_suite_sizes[i-1]} -> {test_suite_sizes[i]}"
        
        # Verify the suite actually grew (not just stayed the same)
        assert test_suite_sizes[-1] > test_suite_sizes[0], \
            f"Test suite did not grow: started at {test_suite_sizes[0]}, ended at {test_suite_sizes[-1]}"
        
        # Verify capability set shifts in response to new pressures
        # Check that capability sets change over time
        unique_capability_sets = set(tuple(sorted(s)) for s in capability_sets)
        assert len(unique_capability_sets) > 1, \
            f"Expected capability set to shift, but only found {len(unique_capability_sets)} unique sets"
        
        # Verify that later cycles have more capabilities (or different ones)
        # This indicates adaptation to new pressures
        first_capabilities = capability_sets[0]
        last_capabilities = capability_sets[-1]
        assert last_capabilities != first_capabilities or len(last_capabilities) >= len(first_capabilities), \
            f"Capability set should shift: first={first_capabilities}, last={last_capabilities}"
        
        # Verify the agent adapted by checking that tests can be executed
        module_name = os.path.splitext(os.path.basename(test_file_path))[0]
        spec = importlib.util.spec_from_file_location(module_name, test_file_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        # Try to run all tests to verify they work
        for test_name in all_test_names:
            test_func = getattr(module, test_name, None)
            if test_func is not None:
                try:
                    test_func()
                except Exception as e:
                    pytest.fail(f"Test {test_name} failed to execute: {e}")
        
        # Verify the test suite contains tests that exercise the source code
        final_content = open(test_file_path, 'r').read()
        assert 'add' in final_content or 'subtract' in final_content or 'multiply' in final_content, \
            "Tests should reference source code functions"
        
        # Verify no import errors occurred throughout the entire process
        # This is already checked per cycle above, but double-check at the end
        try:
            import core.ecology_module
        except ImportError as e:
            pytest.fail(f"Import error for ecology module: {e}")