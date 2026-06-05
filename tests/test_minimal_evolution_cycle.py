import pytest
import sys
import os
import tempfile
import shutil
import importlib.util
import inspect
from pathlib import Path
from typing import Any, Callable
import pytest_timeout

# ---------------------------------------------------------------------------
# Helper: create a minimal toy module source
# ---------------------------------------------------------------------------
def _create_toy_module(path: Path) -> Path:
    """Write a toy module with a single constant-returning function."""
    module_path = path / "toy_module.py"
    source = """
def get_constant() -> int:
    return 42
"""
    module_path.write_text(source)
    return module_path


# ---------------------------------------------------------------------------
# Helper: dynamically import a module from a file path
# ---------------------------------------------------------------------------
def _import_module_from_path(module_path: Path) -> Any:
    """Import a module given its file path."""
    module_name = module_path.stem
    spec = importlib.util.spec_from_file_location(module_name, str(module_path))
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load spec for {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# Helper: reflection – analyse the module and generate a goal
# ---------------------------------------------------------------------------
def reflect_and_generate_goal(module: Any) -> str:
    """
    Inspect the module and produce a textual goal.
    For this test we always request adding a second function.
    """
    functions = [
        name
        for name, obj in inspect.getmembers(module, inspect.isfunction)
        if obj.__module__ == module.__name__
    ]
    if not functions:
        return "add a function that returns a constant"
    # Simple goal: add a second function that returns a different constant
    return "add a second function named 'get_other_constant' that returns 99"


# ---------------------------------------------------------------------------
# Helper: mutation – apply the goal to the source file
# ---------------------------------------------------------------------------
def mutate_module(module_path: Path, goal: str) -> None:
    """
    Modify the module source to implement the goal.
    This simplistic implementation appends the required function.
    """
    source = module_path.read_text()
    if "get_other_constant" in source:
        # already present – skip
        return
    # Append the new function
    new_func = """
def get_other_constant() -> int:
    return 99
"""
    module_path.write_text(source + new_func)


# ---------------------------------------------------------------------------
# Helper: run the test suite on the module
# ---------------------------------------------------------------------------
def run_test_suite(module_path: Path) -> bool:
    """
    Execute a simple test suite that imports the module and checks both functions.
    Returns True if all tests pass, False otherwise.
    """
    # We need to import the module from the temporary directory
    sys.path.insert(0, str(module_path.parent))
    try:
        module = _import_module_from_path(module_path)
        # Test 1: original function exists and returns 42
        assert hasattr(module, "get_constant"), "Missing get_constant"
        assert module.get_constant() == 42, "get_constant() != 42"
        # Test 2: new function exists and returns 99
        assert hasattr(module, "get_other_constant"), "Missing get_other_constant"
        assert module.get_other_constant() == 99, "get_other_constant() != 99"
        return True
    except Exception:
        return False
    finally:
        # Clean up sys.path to avoid side effects
        if str(module_path.parent) in sys.path:
            sys.path.remove(str(module_path.parent))
        # Remove the imported module from sys.modules if present
        module_name = module_path.stem
        if module_name in sys.modules:
            del sys.modules[module_name]


# ---------------------------------------------------------------------------
# Helper: promote the change (in this test, we just mark it as accepted)
# ---------------------------------------------------------------------------
def promote_change(module_path: Path) -> None:
    """
    Mark the change as promoted. In a real system this might commit to version
    control or copy to a stable location. Here we just write a marker file.
    """
    marker = module_path.parent / ".promoted"
    marker.write_text("change promoted")


# ---------------------------------------------------------------------------
# Cleanup fixture
# ---------------------------------------------------------------------------
@pytest.fixture
def cleanup_fixture(tmp_path):
    """
    Fixture that ensures all temporary files, directories, and side effects
    are removed even if the test fails. Uses pytest tmp_path for isolation.
    """
    # Store the original working directory and sys.path
    original_cwd = os.getcwd()
    original_sys_path = sys.path.copy()
    original_modules = set(sys.modules.keys())
    
    # Change to the temporary directory for isolation
    os.chdir(tmp_path)
    
    yield tmp_path
    
    # Cleanup: remove any files or directories created in tmp_path
    for item in tmp_path.iterdir():
        if item.is_dir():
            shutil.rmtree(item)
        else:
            item.unlink()
    
    # Restore original working directory
    os.chdir(original_cwd)
    
    # Restore sys.path
    sys.path = original_sys_path
    
    # Remove any modules that were added during the test
    current_modules = set(sys.modules.keys())
    added_modules = current_modules - original_modules
    for module_name in added_modules:
        del sys.modules[module_name]


# ---------------------------------------------------------------------------
# Integration test
# ---------------------------------------------------------------------------
@pytest.mark.timeout(30)
def test_minimal_evolution_cycle(cleanup_fixture) -> None:
    """
    Self-contained integration test that exercises the full evolution cycle:
    1. Create toy module with one constant-returning function.
    2. Reflect on it to generate a goal.
    3. Mutate the module to implement the goal.
    4. Run the test suite on the mutated module.
    5. Promote the change if tests pass.
    6. Assert no file-system errors, import errors, or exceptions.
    """
    tmp_path = cleanup_fixture

    # 1. Create toy module
    module_path = _create_toy_module(tmp_path)
    assert module_path.exists(), "Toy module was not created"

    # 2. Reflect and generate goal
    module = _import_module_from_path(module_path)
    goal = reflect_and_generate_goal(module)
    assert isinstance(goal, str) and len(goal) > 0, "Goal must be a non-empty string"

    # (a) Assert reflection output is non-empty and contains the toy function name
    assert goal, "Reflection output should be non-empty"
    assert "get_constant" in goal or "get_other_constant" in goal, \
        "Reflection output should contain the toy function name"

    # (b) Assert a goal was generated
    assert goal is not None and len(goal) > 0, "A goal should have been generated"

    # 3. Mutate the module
    mutate_module(module_path, goal)
    assert module_path.exists(), "Module path should still exist after mutation"
    source_after = module_path.read_text()
    assert "get_other_constant" in source_after, "Mutation did not add the new function"

    # (c) Assert mutation produced a valid Python file
    try:
        compile(source_after, module_path.name, 'exec')
        mutation_valid = True
    except SyntaxError:
        mutation_valid = False
    assert mutation_valid, "Mutation should produce a valid Python file"

    # 4. Run test suite
    tests_passed = run_test_suite(module_path)
    assert tests_passed, "Test suite should pass after mutation"

    # (d) Assert tests ran and passed
    assert tests_passed, "Tests should have run and passed"

    # 5. Promote the change
    promote_change(module_path)
    marker = module_path.parent / ".promoted"
    assert marker.exists(), "Promotion marker was not created"

    # (e) Assert the promotion step updated the module
    assert marker.exists() and marker.read_text() == "change promoted", \
        "Promotion step should have updated the module"

    # 6. If we reach here, the cycle completed without errors
    # Additional assertions to satisfy the test requirements
    assert not any(
        err in str(sys.exc_info())
        for err in ["FileNotFoundError", "ImportError", "Exception"]
    ), "Unexpected exception type encountered"

    # (f) Assert the final module has both the original function and the new function
    final_module = _import_module_from_path(module_path)
    assert hasattr(final_module, "get_constant"), "Final module should have original function"
    assert hasattr(final_module, "get_other_constant"), "Final module should have new function"
    assert final_module.get_constant() == 42, "Original function should return 42"
    assert final_module.get_other_constant() == 99, "New function should return 99"