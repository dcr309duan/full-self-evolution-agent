import pytest
import os
import sys
import tempfile
import importlib.util

# Ensure the core module is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from core.test_suite_evolver import generate_test_file, validate_imports, rollback_test_file


class TestTestSuiteEvolver:
    """Unit tests for test_suite_evolver module."""

    def setup_method(self):
        """Create a temporary directory for test artifacts."""
        self.temp_dir = tempfile.mkdtemp()
        self.test_file_path = os.path.join(self.temp_dir, 'test_generated.py')

    def teardown_method(self):
        """Clean up temporary directory."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_generate_test_file_creates_file(self):
        """Test that generate_test_file creates a valid Python test file."""
        test_content = """
import pytest

def test_example():
    assert 1 + 1 == 2
"""
        result = generate_test_file(self.test_file_path, test_content)
        assert result is True
        assert os.path.exists(self.test_file_path)

        # Verify the file is valid Python
        with open(self.test_file_path, 'r') as f:
            content = f.read()
        compile(content, self.test_file_path, 'exec')

    def test_validate_imports_valid(self):
        """Test that validate_imports returns True for valid imports."""
        test_content = """
import pytest
import os
import sys
"""
        # Write the content to a file first
        with open(self.test_file_path, 'w') as f:
            f.write(test_content)
        
        result = validate_imports(self.test_file_path)
        assert result is True

    def test_validate_imports_invalid(self):
        """Test that validate_imports returns False for invalid imports."""
        test_content = """
import nonexistent_module_xyz_123
"""
        with open(self.test_file_path, 'w') as f:
            f.write(test_content)
        
        result = validate_imports(self.test_file_path)
        assert result is False

    def test_rollback_test_file_removes_file(self):
        """Test that rollback_test_file removes the file if it exists."""
        # Create the file first
        with open(self.test_file_path, 'w') as f:
            f.write("# test content")
        assert os.path.exists(self.test_file_path)
        
        rollback_test_file(self.test_file_path)
        assert not os.path.exists(self.test_file_path)

    def test_rollback_test_file_nonexistent(self):
        """Test that rollback_test_file handles nonexistent file gracefully."""
        # Ensure file does not exist
        if os.path.exists(self.test_file_path):
            os.remove(self.test_file_path)
        
        # Should not raise an exception
        rollback_test_file(self.test_file_path)

    def test_generate_and_validate_cycle(self):
        """Test the full cycle: generate, validate, and rollback if validation fails."""
        # Generate a test file with invalid import
        invalid_content = """
import pytest
import nonexistent_module_xyz_123

def test_broken():
    pass
"""
        generate_test_file(self.test_file_path, invalid_content)
        assert os.path.exists(self.test_file_path)
        
        # Validate imports - should fail
        is_valid = validate_imports(self.test_file_path)
        assert is_valid is False
        
        # Rollback
        rollback_test_file(self.test_file_path)
        assert not os.path.exists(self.test_file_path)

    def test_generate_and_validate_success_cycle(self):
        """Test the full cycle where validation passes and file is kept."""
        valid_content = """
import pytest
import os

def test_valid():
    assert True
"""
        generate_test_file(self.test_file_path, valid_content)
        assert os.path.exists(self.test_file_path)
        
        # Validate imports - should pass
        is_valid = validate_imports(self.test_file_path)
        assert is_valid is True
        
        # File should remain after successful validation
        assert os.path.exists(self.test_file_path)
        
        # Clean up
        os.remove(self.test_file_path)

    def test_generate_test_file_with_pytest_import(self):
        """Test that generated file can be imported as a pytest module."""
        test_content = """
import pytest

def test_addition():
    assert 2 + 2 == 4

def test_subtraction():
    assert 5 - 3 == 2
"""
        generate_test_file(self.test_file_path, test_content)
        
        # Try to load the module
        spec = importlib.util.spec_from_file_location("test_generated", self.test_file_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        # Verify the functions exist
        assert hasattr(module, 'test_addition')
        assert hasattr(module, 'test_subtraction')

    def test_validate_imports_with_custom_module(self):
        """Test validation with a custom module that exists in the project."""
        test_content = """
import pytest
from core.test_suite_evolver import generate_test_file
"""
        with open(self.test_file_path, 'w') as f:
            f.write(test_content)
        
        result = validate_imports(self.test_file_path)
        assert result is True

    def test_rollback_after_failed_generation(self):
        """Test that rollback works even if file was partially written."""
        # Simulate a failed generation by writing incomplete content
        with open(self.test_file_path, 'w') as f:
            f.write("import pytest\n")
            f.write("def test_incomplete():")
            # Intentionally not closing the function
        
        assert os.path.exists(self.test_file_path)
        rollback_test_file(self.test_file_path)
        assert not os.path.exists(self.test_file_path)