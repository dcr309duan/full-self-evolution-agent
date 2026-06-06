import os
import sys
import tempfile
import shutil
import importlib.util

# Ensure the parent directory is on the path so we can import test_suite_evolver
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from test_suite_evolver import TestSuiteEvolver


@pytest.fixture
def temp_test_dir():
    """Create a temporary directory with a few test files to simulate tests/."""
    tmpdir = tempfile.mkdtemp()
    # Create a couple of test files
    test_file1 = os.path.join(tmpdir, "test_example1.py")
    with open(test_file1, "w") as f:
        f.write("def test_one():\n    assert 1 == 1\n")
    test_file2 = os.path.join(tmpdir, "test_example2.py")
    with open(test_file2, "w") as f:
        f.write("def test_two():\n    assert 2 == 2\n")
    yield tmpdir
    shutil.rmtree(tmpdir)


def test_scan_tests_directory(temp_test_dir):
    """Test that TestSuiteEvolver can scan the tests/ directory."""
    evolver = TestSuiteEvolver(test_dir=temp_test_dir)
    test_files = evolver.scan_tests()
    assert len(test_files) == 2
    assert any("test_example1.py" in f for f in test_files)
    assert any("test_example2.py" in f for f in test_files)


def test_generates_valid_importable_file(temp_test_dir):
    """Test that the generated test file can be imported."""
    evolver = TestSuiteEvolver(test_dir=temp_test_dir)
    output_path = os.path.join(temp_test_dir, "generated_test.py")
    evolver.generate_test_file(output_path)
    # Try to import the generated file
    spec = importlib.util.spec_from_file_location("generated_test", output_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    # Verify it has a test function
    assert hasattr(mod, "test_generated")
    # Clean up
    os.remove(output_path)


def test_cleans_up_after_itself(temp_test_dir):
    """Test that the evolver cleans up generated files."""
    evolver = TestSuiteEvolver(test_dir=temp_test_dir)
    output_path = os.path.join(temp_test_dir, "generated_test.py")
    evolver.generate_test_file(output_path)
    assert os.path.exists(output_path)
    evolver.cleanup()
    assert not os.path.exists(output_path)


def test_handles_all_tested_case(temp_test_dir):
    """Test that the evolver handles the case when all modules are already tested."""
    # First, generate a test file that covers everything
    evolver = TestSuiteEvolver(test_dir=temp_test_dir)
    output_path = os.path.join(temp_test_dir, "generated_test.py")
    evolver.generate_test_file(output_path)
    # Now try to generate again - should handle gracefully
    evolver2 = TestSuiteEvolver(test_dir=temp_test_dir)
    result = evolver2.generate_test_file(output_path)
    # Should not raise an error, and should indicate nothing new to test
    assert result is None or result == "All modules already tested"
    # Clean up
    os.remove(output_path)