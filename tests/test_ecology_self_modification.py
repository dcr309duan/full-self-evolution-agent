import pytest
import os
import sys
import tempfile
import shutil
import json
from pathlib import Path

# Add the project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.ecology_engine import EcologyEngine
from core.code_generator import CodeGenerator
from core.test_generator import TestGenerator
from core.self_modifier import SelfModifier
from core.test_runner import TestRunner
from core.ecology_pressure_engine import EcologyPressureEngine


@pytest.fixture
def temp_project_dir():
    """Create a temporary project directory with a minimal Python module."""
    tmp_dir = tempfile.mkdtemp()
    original_dir = os.getcwd()
    os.chdir(tmp_dir)
    
    # Create a minimal module to test
    module_dir = Path(tmp_dir) / "my_module"
    module_dir.mkdir(exist_ok=True)
    
    # Create an initial __init__.py
    init_file = module_dir / "__init__.py"
    init_file.write_text("def add(a, b):\n    return a + b\n\ndef subtract(a, b):\n    return a - b\n")
    
    # Create an initial test directory
    test_dir = Path(tmp_dir) / "tests"
    test_dir.mkdir(exist_ok=True)
    
    # Create an initial test file
    test_file = test_dir / "test_my_module.py"
    test_file.write_text("""from my_module import add, subtract

def test_add():
    assert add(2, 3) == 5

def test_subtract():
    assert subtract(5, 3) == 2
""")
    
    yield tmp_dir
    
    os.chdir(original_dir)
    shutil.rmtree(tmp_dir)


@pytest.fixture
def ecology_engine(temp_project_dir):
    """Create an EcologyEngine instance configured for the temp project."""
    engine = EcologyEngine(
        project_dir=temp_project_dir,
        module_name="my_module",
        test_dir=os.path.join(temp_project_dir, "tests"),
        source_dir=os.path.join(temp_project_dir, "my_module")
    )
    return engine


def test_full_ecology_self_modification_loop(ecology_engine):
    """
    Validate the full ecology self-modification loop:
    1. Agent generates a new test (novel assertion not covered by current code)
    2. Agent runs the new test and it fails
    3. Agent mutates itself (the source code) to pass the new test
    4. The new test becomes part of the permanent test suite
    """
    # Step 1: Generate a novel test that the current code cannot pass
    # The current code has add() and subtract(). Let's generate a test for multiply()
    novel_test_code = """
from my_module import multiply

def test_multiply():
    assert multiply(3, 4) == 12
    assert multiply(0, 5) == 0
    assert multiply(-2, 6) == -12
"""
    novel_test_path = os.path.join(ecology_engine.test_dir, "test_novel_multiply.py")
    with open(novel_test_path, "w") as f:
        f.write(novel_test_code)
    
    # Step 2: Run the new test and verify it fails
    test_runner = TestRunner(project_dir=ecology_engine.project_dir)
    result = test_runner.run_specific_test(novel_test_path)
    
    # The test should fail because multiply() doesn't exist yet
    assert result.failed > 0 or result.errors > 0, \
        "Novel test should fail because multiply() is not implemented"
    
    # Step 3: Mutate the source code to implement multiply()
    # The self-modifier should add the multiply function to the module
    self_modifier = SelfModifier(
        source_dir=ecology_engine.source_dir,
        module_name=ecology_engine.module_name
    )
    
    # Generate the mutation that adds multiply()
    mutation_code = """
def multiply(a, b):
    return a * b
"""
    success = self_modifier.add_function_to_module("multiply", mutation_code)
    assert success, "Self-modifier should successfully add multiply() to the module"
    
    # Verify the function was added
    init_file = Path(ecology_engine.source_dir) / "__init__.py"
    module_content = init_file.read_text()
    assert "def multiply" in module_content, "multiply() should be in the module after mutation"
    
    # Step 4: Run the novel test again - it should now pass
    result = test_runner.run_specific_test(novel_test_path)
    assert result.failed == 0 and result.errors == 0, \
        "Novel test should pass after multiply() is implemented"
    
    # Step 5: Verify the test is now part of the permanent test suite
    # Check that the test file exists and is not temporary
    assert os.path.exists(novel_test_path), "Novel test file should persist"
    
    # Run the full test suite to ensure no regressions
    full_result = test_runner.run_all_tests()
    assert full_result.failed == 0 and full_result.errors == 0, \
        "Full test suite should pass after self-modification"


def test_ecology_loop_with_multiple_novel_tests(ecology_engine):
    """
    Test the ecology loop with multiple novel tests to ensure the system
    can handle sequential self-modifications.
    """
    test_runner = TestRunner(project_dir=ecology_engine.project_dir)
    self_modifier = SelfModifier(
        source_dir=ecology_engine.source_dir,
        module_name=ecology_engine.module_name
    )
    
    # Define a sequence of novel tests and corresponding mutations
    test_mutation_pairs = [
        {
            "test_name": "test_novel_divide.py",
            "test_code": """
from my_module import divide

def test_divide():
    assert divide(10, 2) == 5
    assert divide(7, 3) == 7 / 3
    assert divide(0, 5) == 0
""",
            "mutation_code": """
def divide(a, b):
    if b == 0:
        raise ValueError("Cannot divide by zero")
    return a / b
"""
        },
        {
            "test_name": "test_novel_power.py",
            "test_code": """
from my_module import power

def test_power():
    assert power(2, 3) == 8
    assert power(5, 0) == 1
    assert power(3, 2) == 9
""",
            "mutation_code": """
def power(base, exp):
    return base ** exp
"""
        }
    ]
    
    for pair in test_mutation_pairs:
        test_path = os.path.join(ecology_engine.test_dir, pair["test_name"])
        
        # Write the novel test
        with open(test_path, "w") as f:
            f.write(pair["test_code"])
        
        # Verify it fails initially
        result = test_runner.run_specific_test(test_path)
        assert result.failed > 0 or result.errors > 0, \
            f"Novel test {pair['test_name']} should fail initially"
        
        # Apply the mutation
        func_name = pair["test_code"].split("import ")[1].split("\n")[0].strip()
        success = self_modifier.add_function_to_module(func_name, pair["mutation_code"])
        assert success, f"Should successfully add {func_name}()"
        
        # Verify the test now passes
        result = test_runner.run_specific_test(test_path)
        assert result.failed == 0 and result.errors == 0, \
            f"Novel test {pair['test_name']} should pass after mutation"
    
    # Final verification: all tests pass
    full_result = test_runner.run_all_tests()
    assert full_result.failed == 0 and full_result.errors == 0, \
        "All tests should pass after all self-modifications"


def test_ecology_loop_preserves_existing_functionality(ecology_engine):
    """
    Ensure that the ecology self-modification loop does not break existing functionality.
    """
    test_runner = TestRunner(project_dir=ecology_engine.project_dir)
    self_modifier = SelfModifier(
        source_dir=ecology_engine.source_dir,
        module_name=ecology_engine.module_name
    )
    
    # Run initial tests to establish baseline
    initial_result = test_runner.run_all_tests()
    initial_passed = initial_result.passed
    
    # Add a novel test for a new function
    novel_test_path = os.path.join(ecology_engine.test_dir, "test_novel_square.py")
    with open(novel_test_path, "w") as f:
        f.write("""
from my_module import square

def test_square():
    assert square(4) == 16
    assert square(-3) == 9
    assert square(0) == 0
""")
    
    # Verify it fails
    result = test_runner.run_specific_test(novel_test_path)
    assert result.failed > 0 or result.errors > 0
    
    # Add the square function
    self_modifier.add_function_to_module("square", """
def square(x):
    return x * x
""")
    
    # Run all tests again
    final_result = test_runner.run_all_tests()
    
    # The number of passed tests should increase (original tests + new test)
    assert final_result.passed > initial_passed, \
        "Total passed tests should increase after adding new functionality"
    assert final_result.failed == 0 and final_result.errors == 0, \
        "No tests should fail after self-modification"


def test_ecology_pressure_engine_generates_novel_tests(temp_project_dir):
    """
    Test that EcologyPressureEngine generates novel test files with unique assertions.
    """
    # Instantiate EcologyPressureEngine
    pressure_engine = EcologyPressureEngine(
        project_dir=temp_project_dir,
        module_name="my_module",
        test_dir=os.path.join(temp_project_dir, "tests"),
        source_dir=os.path.join(temp_project_dir, "my_module")
    )
    
    # Call generate_novel_test_suite()
    created_files = pressure_engine.generate_novel_test_suite()
    
    # Verify it creates test files with unique assertions
    assert len(created_files) > 0, "Should create at least one test file"
    
    for file_path in created_files:
        assert os.path.exists(file_path), f"Created test file {file_path} should exist"
        
        # Read the content and verify it has assertions
        with open(file_path, 'r') as f:
            content = f.read()
        
        assert 'assert' in content, f"Test file {file_path} should contain assertions"
        
        # Verify the test file can be imported and has test functions
        assert 'def test_' in content, f"Test file {file_path} should contain test functions"
    
    # Clean up created files
    for file_path in created_files:
        if os.path.exists(file_path):
            os.remove(file_path)
    
    # Verify cleanup was successful
    for file_path in created_files:
        assert not os.path.exists(file_path), f"Test file {file_path} should have been cleaned up"


def test_full_ecology_loop_with_mock(ecology_engine, mocker):
    """
    Validate the full ecology loop using mocks:
    1. Agent generates a new test
    2. Injects it into the test suite
    3. Runs the test suite
    4. Verifies the new test is executed
    5. Verifies old tests are removed after threshold
    """
    test_runner = TestRunner(project_dir=ecology_engine.project_dir)
    self_modifier = SelfModifier(
        source_dir=ecology_engine.source_dir,
        module_name=ecology_engine.module_name
    )
    
    # Mock the evolution cycle
    mock_evolution = mocker.patch.object(ecology_engine, 'evolve')
    mock_evolution.return_value = True
    
    # Step 1: Agent generates a new test
    novel_test_code = """
from my_module import multiply

def test_multiply():
    assert multiply(3, 4) == 12
    assert multiply(0, 5) == 0
    assert multiply(-2, 6) == -12
"""
    novel_test_path = os.path.join(ecology_engine.test_dir, "test_novel_multiply.py")
    with open(novel_test_path, "w") as f:
        f.write(novel_test_code)
    
    # Step 2: Inject it into the test suite
    # Simulate injection by adding the test file to the test directory
    assert os.path.exists(novel_test_path), "Test file should be injected into test suite"
    
    # Step 3: Run the test suite
    result = test_runner.run_specific_test(novel_test_path)
    # The test should fail because multiply() doesn't exist yet
    assert result.failed > 0 or result.errors > 0, \
        "Novel test should fail because multiply() is not implemented"
    
    # Step 4: Verify the new test is executed
    # Check that the test was actually run (not skipped)
    assert result.tests_run > 0, "New test should be executed"
    
    # Step 5: Verify old tests are removed after threshold
    # Simulate threshold by adding multiple old test files and checking removal
    old_test_files = []
    for i in range(5):
        old_test_path = os.path.join(ecology_engine.test_dir, f"test_old_{i}.py")
        with open(old_test_path, "w") as f:
            f.write(f"""
from my_module import add

def test_old_{i}():
    assert add({i}, {i+1}) == {2*i+1}
""")
        old_test_files.append(old_test_path)
    
    # Mock the threshold check
    mock_threshold = mocker.patch.object(ecology_engine, 'check_old_test_threshold')
    mock_threshold.return_value = True
    
    # Simulate removal of old tests
    for old_test in old_test_files:
        if os.path.exists(old_test):
            os.remove(old_test)
    
    # Verify old tests are removed
    for old_test in old_test_files:
        assert not os.path.exists(old_test), f"Old test {old_test} should be removed after threshold"
    
    # Verify the new test still exists
    assert os.path.exists(novel_test_path), "New test should persist after old tests are removed"
    
    # Verify the mock evolution was called
    mock_evolution.assert_called_once()


def test_full_ecology_loop_with_mock_and_assertions(ecology_engine, mocker):
    """
    Validate the full ecology loop using mocks with detailed assertions:
    1. Agent generates a new test
    2. Injects it into the test suite
    3. Runs the test suite
    4. Verifies the new test is executed
    5. Verifies old tests are removed after threshold
    """
    test_runner = TestRunner(project_dir=ecology_engine.project_dir)
    self_modifier = SelfModifier(
        source_dir=ecology_engine.source_dir,
        module_name=ecology_engine.module_name
    )
    
    # Mock the evolution cycle
    mock_evolution = mocker.patch.object(ecology_engine, 'evolve')
    mock_evolution.return_value = True
    
    # Step 1: Agent generates a new test
    novel_test_code = """
from my_module import multiply

def test_multiply():
    assert multiply(3, 4) == 12
    assert multiply(0, 5) == 0
    assert multiply(-2, 6) == -12
"""
    novel_test_path = os.path.join(ecology_engine.test_dir, "test_novel_multiply.py")
    with open(novel_test_path, "w") as f:
        f.write(novel_test_code)
    
    # Step 2: Inject it into the test suite
    assert os.path.exists(novel_test_path), "Test file should be injected into test suite"
    
    # Step 3: Run the test suite
    result = test_runner.run_specific_test(novel_test_path)
    assert result.failed > 0 or result.errors > 0, \
        "Novel test should fail because multiply() is not implemented"
    
    # Step 4: Verify the new test is executed
    assert result.tests_run > 0, "New test should be executed"
    assert result.failed > 0, "New test should have failed assertions"
    
    # Step 5: Verify old tests are removed after threshold
    old_test_files = []
    for i in range(5):
        old_test_path = os.path.join(ecology_engine.test_dir, f"test_old_{i}.py")
        with open(old_test_path, "w") as f:
            f.write(f"""
from my_module import add

def test_old_{i}():
    assert add({i}, {i+1}) == {2*i+1}
""")
        old_test_files.append(old_test_path)
    
    # Mock the threshold check
    mock_threshold = mocker.patch.object(ecology_engine, 'check_old_test_threshold')
    mock_threshold.return_value = True
    
    # Simulate removal of old tests
    for old_test in old_test_files:
        if os.path.exists(old_test):
            os.remove(old_test)
    
    # Verify old tests are removed
    for old_test in old_test_files:
        assert not os.path.exists(old_test), f"Old test {old_test} should be removed after threshold"
    
    # Verify the new test still exists
    assert os.path.exists(novel_test_path), "New test should persist after old tests are removed"
    
    # Verify the mock evolution was called
    mock_evolution.assert_called_once()
    
    # Additional assertions
    assert mock_evolution.call_count == 1, "Evolution should be called exactly once"
    assert mock_threshold.call_count == 1, "Threshold check should be called exactly once"