import pytest
import tempfile
import os
import shutil
import subprocess
import sys

# Add the project root to the path so that we can import the modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from src.simulation_pipeline import SimulationPipeline
from src.mutation_proposer import MutationProposer
from src.sandbox import Sandbox


@pytest.fixture
def setup_test_environment():
    """
    Fixture to set up a temporary test environment with a multi-module project.
    Returns the path to the temporary project directory.
    """
    temp_dir = tempfile.mkdtemp()
    
    # Create a simple multi-module Python project with dependencies
    project_dir = os.path.join(temp_dir, 'test_project')
    os.makedirs(project_dir)
    
    # Create module_a.py
    with open(os.path.join(project_dir, 'module_a.py'), 'w') as f:
        f.write("""
def add(a, b):
    return a + b

def subtract(a, b):
    return a - b
""")
    
    # Create module_b.py that depends on module_a
    with open(os.path.join(project_dir, 'module_b.py'), 'w') as f:
        f.write("""
from module_a import add, subtract

def multiply(a, b):
    return a * b

def complex_operation(a, b, c):
    return add(a, b) * subtract(c, 0)
""")
    
    # Create module_c.py that depends on module_b
    with open(os.path.join(project_dir, 'module_c.py'), 'w') as f:
        f.write("""
from module_b import multiply, complex_operation

def calculate_total(a, b, c):
    return multiply(a, b) + complex_operation(a, b, c)
""")
    
    # Create a test file
    test_dir = os.path.join(project_dir, 'tests')
    os.makedirs(test_dir)
    with open(os.path.join(test_dir, 'test_modules.py'), 'w') as f:
        f.write("""
from module_a import add, subtract
from module_b import multiply, complex_operation
from module_c import calculate_total

def test_add():
    assert add(2, 3) == 5

def test_subtract():
    assert subtract(5, 3) == 2

def test_multiply():
    assert multiply(4, 5) == 20

def test_complex_operation():
    assert complex_operation(2, 3, 5) == 25

def test_calculate_total():
    assert calculate_total(2, 3, 5) == 45
""")
    
    yield project_dir
    
    # Cleanup
    shutil.rmtree(temp_dir)


def test_full_simulation_pipeline(setup_test_environment):
    """
    Integration test for the full simulation pipeline.
    """
    project_dir = setup_test_environment
    sandbox = Sandbox(project_dir)
    pipeline = SimulationPipeline(project_dir)
    mutation_proposer = MutationProposer()
    
    # Step 1: Create a multi-module test scenario with dependencies
    # (Already done in the fixture)
    
    # Step 2: Propose a valid mutation
    # A valid mutation: changing '+' to '-' in module_a.py
    valid_mutation = mutation_proposer.propose_mutation(
        file_path=os.path.join(project_dir, 'module_a.py'),
        original_code="def add(a, b):\n    return a + b",
        mutated_code="def add(a, b):\n    return a - b"
    )
    
    # Step 3: Run simulation and verify it returns predicted pass
    # Since we're changing the add function, tests that use add should fail
    # But we're testing the pipeline, so we expect the simulation to run and return a result
    simulation_result = pipeline.run_simulation(valid_mutation)
    assert simulation_result is not None
    # The mutation should cause test failures, so predicted pass should be False
    assert simulation_result.predicted_pass == False, "Valid mutation should cause test failures"
    
    # Step 4: Propose an invalid mutation (one that doesn't change behavior)
    # An invalid mutation: changing a comment or whitespace
    invalid_mutation = mutation_proposer.propose_mutation(
        file_path=os.path.join(project_dir, 'module_a.py'),
        original_code="# This is a comment\n",
        mutated_code="# This is a modified comment\n"
    )
    
    # Step 5: Run simulation and verify it returns predicted fail
    # Since the mutation doesn't change behavior, tests should still pass
    simulation_result = pipeline.run_simulation(invalid_mutation)
    assert simulation_result is not None
    # The mutation should not cause test failures, so predicted pass should be True
    assert simulation_result.predicted_pass == True, "Invalid mutation should not cause test failures"
    
    # Step 6: Verify no files were modified outside the sandbox
    # Check that the original project files are unchanged
    assert not sandbox.has_files_been_modified_outside(), "Files were modified outside the sandbox"
    
    # Additional verification: check that the sandbox directory exists and is clean
    assert os.path.exists(sandbox.sandbox_dir), "Sandbox directory should exist"
    
    # Verify that the original project files are intact
    with open(os.path.join(project_dir, 'module_a.py'), 'r') as f:
        original_content = f.read()
    assert "def add(a, b):\n    return a + b" in original_content, "Original file should not be modified"


def test_simulation_pipeline_with_edge_cases(setup_test_environment):
    """
    Test edge cases in the simulation pipeline.
    """
    project_dir = setup_test_environment
    pipeline = SimulationPipeline(project_dir)
    mutation_proposer = MutationProposer()
    
    # Test with a mutation that doesn't change any file (empty mutation)
    empty_mutation = mutation_proposer.propose_mutation(
        file_path=os.path.join(project_dir, 'module_a.py'),
        original_code="",
        mutated_code=""
    )
    
    # This should still run and return a result
    simulation_result = pipeline.run_simulation(empty_mutation)
    assert simulation_result is not None
    
    # Test with a mutation that introduces a syntax error
    syntax_error_mutation = mutation_proposer.propose_mutation(
        file_path=os.path.join(project_dir, 'module_a.py'),
        original_code="def add(a, b):\n    return a + b",
        mutated_code="def add(a, b):\n    return a + b +"  # Syntax error
    )
    
    # The simulation should handle this gracefully
    simulation_result = pipeline.run_simulation(syntax_error_mutation)
    assert simulation_result is not None
    # Syntax errors should cause test failures
    assert simulation_result.predicted_pass == False, "Syntax error mutation should cause test failures"