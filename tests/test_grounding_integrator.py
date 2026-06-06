import os
import sys
import tempfile
import shutil
import pytest
from unittest.mock import patch, MagicMock

# Adjust path to import the module under test
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from core.grounding_test_integrator import GroundingTestIntegrator
from core.test_registry import TestRegistry


@pytest.fixture
def temp_workspace():
    """Create a temporary workspace for test artifacts."""
    tmpdir = tempfile.mkdtemp()
    yield tmpdir
    shutil.rmtree(tmpdir)


@pytest.fixture
def mock_capability():
    """Return a mock capability object simulating an accepted capability."""
    cap = MagicMock()
    cap.name = "test_capability_alpha"
    cap.code = "def test_capability_alpha():\n    return 42\n"
    cap.metadata = {"author": "test", "version": "1.0.0"}
    return cap


@pytest.fixture
def integrator(temp_workspace):
    """Create a GroundingTestIntegrator instance pointing to the temp workspace."""
    return GroundingTestIntegrator(workspace=temp_workspace)


@pytest.fixture
def registry(temp_workspace):
    """Create a TestRegistry instance for verification."""
    return TestRegistry(registry_path=os.path.join(temp_workspace, "test_registry.json"))


def test_integration_happy_path(integrator, mock_capability, registry, temp_workspace):
    """
    Test the full happy path: accept capability, generate test, run it, verify registry.
    """
    # (1) Simulate capability acceptance
    integrator.on_capability_accepted(mock_capability)

    # (2) The integrator should have generated a test file
    test_file_path = os.path.join(temp_workspace, "tests", f"test_{mock_capability.name}.py")
    assert os.path.exists(test_file_path), f"Test file not generated at {test_file_path}"

    # (3) Run the generated test using pytest
    result = pytest.main([test_file_path, "--tb=short", "--quiet"])
    # Expect success (exit code 0)
    assert result == 0, f"Generated test failed with exit code {result}"

    # (4) Verify the test registry was updated with the new test entry
    registry.load()
    assert mock_capability.name in registry.get_all_test_names(), "Capability not registered in test registry"

    # (5) Verify registry contains correct metadata
    entry = registry.get_test_entry(mock_capability.name)
    assert entry is not None
    assert entry["status"] == "passed"
    assert entry["test_file"] == test_file_path


def test_rollback_on_failing_test(integrator, mock_capability, registry, temp_workspace):
    """
    Test the rollback path: inject a failing test and verify the capability is rolled back.
    """
    # (1) Simulate capability acceptance
    integrator.on_capability_accepted(mock_capability)

    # (2) Manually modify the generated test to force a failure
    test_file_path = os.path.join(temp_workspace, "tests", f"test_{mock_capability.name}.py")
    with open(test_file_path, "a") as f:
        f.write("\n\ndef test_forced_failure():\n    assert False, 'Intentional failure for rollback test'\n")

    # (3) Run the modified test (should fail)
    result = pytest.main([test_file_path, "--tb=short", "--quiet"])
    assert result != 0, "Expected test failure but got success"

    # (4) Verify the integrator triggers rollback (e.g., removes test file, reverts registry)
    # The integrator should have a rollback method; call it explicitly or check side effects
    integrator.rollback_capability(mock_capability.name)

    # (5) Verify test file is removed
    assert not os.path.exists(test_file_path), f"Test file was not removed after rollback: {test_file_path}"

    # (6) Verify registry entry is removed or marked as rolled back
    registry.load()
    entry = registry.get_test_entry(mock_capability.name)
    assert entry is None or entry.get("status") == "rolled_back", \
        "Capability was not properly rolled back in registry"


def test_registry_update_on_successful_test(integrator, mock_capability, registry, temp_workspace):
    """
    Verify that the registry is updated correctly after a successful test run.
    """
    # (1) Accept capability
    integrator.on_capability_accepted(mock_capability)

    # (2) Run the generated test
    test_file_path = os.path.join(temp_workspace, "tests", f"test_{mock_capability.name}.py")
    result = pytest.main([test_file_path, "--tb=short", "--quiet"])
    assert result == 0

    # (3) Check registry for correct status and timestamp
    registry.load()
    entry = registry.get_test_entry(mock_capability.name)
    assert entry["status"] == "passed"
    assert "timestamp" in entry
    assert "duration" in entry

    # (4) Verify that the test is listed in the registry's test names
    assert mock_capability.name in registry.get_all_test_names()


def test_multiple_capabilities(integrator, registry, temp_workspace):
    """
    Test handling of multiple capability acceptances sequentially.
    """
    cap1 = MagicMock()
    cap1.name = "cap_one"
    cap1.code = "def cap_one():\n    return 1\n"
    cap1.metadata = {}

    cap2 = MagicMock()
    cap2.name = "cap_two"
    cap2.code = "def cap_two():\n    return 2\n"
    cap2.metadata = {}

    # Accept both capabilities
    integrator.on_capability_accepted(cap1)
    integrator.on_capability_accepted(cap2)

    # Verify both test files exist
    test1_path = os.path.join(temp_workspace, "tests", f"test_{cap1.name}.py")
    test2_path = os.path.join(temp_workspace, "tests", f"test_{cap2.name}.py")
    assert os.path.exists(test1_path)
    assert os.path.exists(test2_path)

    # Run both tests
    result1 = pytest.main([test1_path, "--tb=short", "--quiet"])
    result2 = pytest.main([test2_path, "--tb=short", "--quiet"])
    assert result1 == 0
    assert result2 == 0

    # Verify registry contains both
    registry.load()
    all_tests = registry.get_all_test_names()
    assert cap1.name in all_tests
    assert cap2.name in all_tests


def test_rollback_cleans_generated_files(integrator, mock_capability, temp_workspace):
    """
    Ensure rollback removes all generated artifacts (test file, any cache).
    """
    integrator.on_capability_accepted(mock_capability)
    test_file_path = os.path.join(temp_workspace, "tests", f"test_{mock_capability.name}.py")
    assert os.path.exists(test_file_path)

    # Trigger rollback
    integrator.rollback_capability(mock_capability.name)

    # Verify test file is gone
    assert not os.path.exists(test_file_path)

    # Verify no leftover files in the tests directory
    tests_dir = os.path.join(temp_workspace, "tests")
    if os.path.exists(tests_dir):
        remaining_files = os.listdir(tests_dir)
        # Only allow __pycache__ or .pyc files to remain
        for f in remaining_files:
            assert f.endswith(".pyc") or f == "__pycache__", f"Unexpected leftover file: {f}"