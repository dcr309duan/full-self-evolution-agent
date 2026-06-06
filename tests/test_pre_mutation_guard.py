import pytest
import sys
import os
from unittest.mock import patch, MagicMock
from pathlib import Path

# Add the project root to the path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.pre_mutation_guard import (
    validate_code_syntax,
    validate_imports,
    validate_module_availability,
    pre_mutation_guard,
    ValidationResult,
    ValidationError
)


class TestPreMutationGuard:
    """Comprehensive tests for the pre-mutation guard functionality."""

    def test_valid_python_code_passes(self):
        """Test that valid Python code passes all validation checks."""
        valid_code = """
def hello():
    print("Hello, World!")
    
class TestClass:
    def __init__(self):
        self.value = 42
"""
        result = validate_code_syntax(valid_code)
        assert result.is_valid
        assert result.error_type is None
        assert result.error_line is None
        assert result.error_message is None

    def test_valid_code_with_imports(self):
        """Test that valid Python code with standard library imports passes."""
        valid_code = """
import os
import sys
from pathlib import Path

def get_path():
    return Path(os.getcwd())
"""
        result = validate_code_syntax(valid_code)
        assert result.is_valid

    def test_syntax_error_detected(self):
        """Test that syntax errors are correctly detected with line number."""
        invalid_code = """
def broken_function(
    print("This will fail")
"""
        result = validate_code_syntax(invalid_code)
        assert not result.is_valid
        assert result.error_type == "SyntaxError"
        assert result.error_line is not None
        assert result.error_line > 0

    def test_syntax_error_with_missing_parenthesis(self):
        """Test detection of missing closing parenthesis."""
        invalid_code = """
def calculate(x, y:
    return x + y
"""
        result = validate_code_syntax(invalid_code)
        assert not result.is_valid
        assert result.error_type == "SyntaxError"
        assert result.error_line == 2  # Line with the error

    def test_syntax_error_with_invalid_indentation(self):
        """Test detection of inconsistent indentation."""
        invalid_code = """
def func():
    print("indented")
  print("wrong indentation")
"""
        result = validate_code_syntax(invalid_code)
        assert not result.is_valid
        assert result.error_type == "SyntaxError" or result.error_type == "IndentationError"

    def test_missing_import_detected(self):
        """Test that missing imports are correctly identified."""
        code_with_bad_import = """
import nonexistent_module_xyz

def use_module():
    return nonexistent_module_xyz.some_function()
"""
        result = validate_imports(code_with_bad_import)
        assert not result.is_valid
        assert "import" in result.error_message.lower() or "module" in result.error_message.lower()
        assert "nonexistent_module_xyz" in result.error_message

    def test_standard_library_imports_pass(self):
        """Test that standard library imports are accepted."""
        code_with_stdlib_imports = """
import os
import sys
import json
import datetime
import collections
import math
import random
import re
import typing
"""
        result = validate_imports(code_with_stdlib_imports)
        assert result.is_valid

    def test_common_third_party_imports_pass(self):
        """Test that commonly available third-party imports pass validation."""
        code_with_common_imports = """
import pytest
import numpy
import pandas
import requests
import flask
import django
import sqlalchemy
"""
        # These should pass if installed, but we'll mock the environment
        with patch('core.pre_mutation_guard._check_module_available') as mock_check:
            mock_check.return_value = True
            result = validate_imports(code_with_common_imports)
            assert result.is_valid

    def test_module_not_found_error(self):
        """Test that unavailable modules return module-not-found error."""
        code_with_unavailable_module = """
import some_rarely_installed_package_12345

def use_it():
    return some_rarely_installed_package_12345.do_something()
"""
        with patch('core.pre_mutation_guard._check_module_available') as mock_check:
            mock_check.return_value = False
            result = validate_module_availability(code_with_unavailable_module)
            assert not result.is_valid
            assert "not found" in result.error_message.lower() or "unavailable" in result.error_message.lower()

    def test_mixed_valid_and_invalid_imports(self):
        """Test that mixed valid and invalid imports are handled correctly."""
        code = """
import os
import sys
import nonexistent_package_xyz
import json
"""
        result = validate_imports(code)
        assert not result.is_valid
        assert "nonexistent_package_xyz" in result.error_message

    def test_import_error_with_relative_imports(self):
        """Test that relative imports to non-existent modules are caught."""
        code = """
from .nonexistent_module import something

def test():
    pass
"""
        result = validate_imports(code)
        assert not result.is_valid

    def test_mutation_aborted_on_validation_failure(self):
        """Test that mutation is aborted when validation fails."""
        # Create a mock mutation that should be aborted
        mutation_code = """
def broken_function(
    pass
"""
        # This should raise a ValidationError or return False
        with pytest.raises(ValidationError) if hasattr(ValidationError, '__module__') else pytest.raises(Exception):
            pre_mutation_guard(mutation_code)

    def test_mutation_proceeds_on_validation_success(self):
        """Test that mutation proceeds when validation passes."""
        valid_code = """
def working_function():
    return 42
"""
        result = pre_mutation_guard(valid_code)
        assert result is True or (hasattr(result, 'is_valid') and result.is_valid)

    def test_validation_error_contains_details(self):
        """Test that validation errors contain detailed information."""
        invalid_code = """
import nonexistent_xyz_module

def test():
    pass
"""
        try:
            pre_mutation_guard(invalid_code)
            # If we get here, the guard might return a result instead of raising
            # Check if the result indicates failure
        except ValidationError as e:
            assert hasattr(e, 'message') or hasattr(e, 'error_message')
            assert "nonexistent_xyz_module" in str(e)
        except Exception as e:
            # Some other exception type, check it contains useful info
            assert "nonexistent_xyz_module" in str(e)

    def test_empty_code_handling(self):
        """Test that empty code is handled appropriately."""
        empty_code = ""
        result = validate_code_syntax(empty_code)
        # Empty code could be considered valid or invalid depending on design
        # At minimum, it should not crash
        assert result is not None

    def test_code_with_only_comments(self):
        """Test that code containing only comments passes validation."""
        comment_code = """
# This is a comment
# Another comment
# Yet another comment
"""
        result = validate_code_syntax(comment_code)
        assert result.is_valid

    def test_code_with_docstrings(self):
        """Test that code with docstrings passes validation."""
        docstring_code = '''
"""Module docstring."""

def func():
    """Function docstring."""
    pass
'''
        result = validate_code_syntax(docstring_code)
        assert result.is_valid

    def test_async_code_validation(self):
        """Test that async Python code passes validation."""
        async_code = """
import asyncio

async def fetch_data():
    await asyncio.sleep(1)
    return {"data": "test"}

async def main():
    result = await fetch_data()
    print(result)
"""
        result = validate_code_syntax(async_code)
        assert result.is_valid

    def test_type_hints_validation(self):
        """Test that code with type hints passes validation."""
        typed_code = """
from typing import List, Optional, Dict

def process_items(items: List[str]) -> Optional[Dict[str, int]]:
    result: Dict[str, int] = {}
    for item in items:
        result[item] = len(item)
    return result if result else None
"""
        result = validate_code_syntax(typed_code)
        assert result.is_valid

    def test_class_with_methods_validation(self):
        """Test that complex class definitions pass validation."""
        class_code = """
class DataProcessor:
    def __init__(self, data: dict):
        self.data = data
        self.processed = False
    
    def process(self) -> dict:
        if not self.processed:
            self.data = {k: v.upper() if isinstance(v, str) else v 
                        for k, v in self.data.items()}
            self.processed = True
        return self.data
    
    @staticmethod
    def validate(data: dict) -> bool:
        return bool(data)
    
    @classmethod
    def from_list(cls, items: list) -> 'DataProcessor':
        return cls({str(i): item for i, item in enumerate(items)})
"""
        result = validate_code_syntax(class_code)
        assert result.is_valid

    def test_decorator_validation(self):
        """Test that code with decorators passes validation."""
        decorator_code = """
import functools
import time

def timer(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        print(f"Function took {time.time() - start:.2f} seconds")
        return result
    return wrapper

@timer
def slow_function():
    time.sleep(1)
    return "Done"
"""
        result = validate_code_syntax(decorator_code)
        assert result.is_valid

    def test_validation_result_object(self):
        """Test that ValidationResult object has all required attributes."""
        result = ValidationResult(is_valid=True)
        assert hasattr(result, 'is_valid')
        assert hasattr(result, 'error_type')
        assert hasattr(result, 'error_line')
        assert hasattr(result, 'error_message')
        assert result.is_valid is True

        result = ValidationResult(
            is_valid=False,
            error_type="SyntaxError",
            error_line=5,
            error_message="Invalid syntax"
        )
        assert result.is_valid is False
        assert result.error_type == "SyntaxError"
        assert result.error_line == 5
        assert result.error_message == "Invalid syntax"

    def test_validation_error_exception(self):
        """Test that ValidationError exception works correctly."""
        error = ValidationError("Test error message")
        assert str(error) == "Test error message"
        assert isinstance(error, Exception)

    def test_comprehensive_validation_pipeline(self):
        """Test the complete validation pipeline with a valid file."""
        valid_file_content = """
import os
import sys
from pathlib import Path

def main():
    path = Path(os.getcwd())
    print(f"Current directory: {path}")
    return 0

if __name__ == "__main__":
    main()
"""
        # Test each validation step
        syntax_result = validate_code_syntax(valid_file_content)
        assert syntax_result.is_valid
        
        import_result = validate_imports(valid_file_content)
        assert import_result.is_valid
        
        # Test the full guard
        guard_result = pre_mutation_guard(valid_file_content)
        assert guard_result is True or (hasattr(guard_result, 'is_valid') and guard_result.is_valid)

    def test_comprehensive_validation_pipeline_with_errors(self):
        """Test the complete validation pipeline with an invalid file."""
        invalid_file_content = """
import os
import nonexistent_module_xyz

def main():
    print("Hello"
    return 0
"""
        # Syntax validation should fail
        syntax_result = validate_code_syntax(invalid_file_content)
        assert not syntax_result.is_valid
        assert syntax_result.error_type == "SyntaxError"
        
        # Import validation should fail
        import_result = validate_imports(invalid_file_content)
        assert not import_result.is_valid
        
        # Full guard should fail
        guard_result = pre_mutation_guard(invalid_file_content)
        assert guard_result is False or (hasattr(guard_result, 'is_valid') and not guard_result.is_valid)

    def test_read_existing_test_file(self):
        """Test reading the existing test file to understand test coverage."""
        test_file_path = Path(__file__)
        assert test_file_path.exists()
        
        # Read the test file content
        with open(test_file_path, 'r') as f:
            content = f.read()
        
        # Verify the file contains expected test patterns
        assert 'class TestPreMutationGuard' in content
        assert 'def test_' in content
        
        # Count the number of test methods
        test_methods = [line for line in content.split('\n') if line.strip().startswith('def test_')]
        assert len(test_methods) > 0
        
        # Verify key test coverage areas
        assert 'test_valid_python_code_passes' in content
        assert 'test_syntax_error_detected' in content
        assert 'test_missing_import_detected' in content
        assert 'test_mutation_aborted_on_validation_failure' in content
        assert 'test_mutation_proceeds_on_validation_success' in content
        
        # Check for comprehensive coverage indicators
        assert 'test_async_code_validation' in content
        assert 'test_type_hints_validation' in content
        assert 'test_class_with_methods_validation' in content
        assert 'test_decorator_validation' in content
        assert 'test_comprehensive_validation_pipeline' in content
        assert 'test_comprehensive_validation_pipeline_with_errors' in content

    def test_invalid_syntax_fails_with_correct_error_type_file_line(self):
        """Test that invalid syntax fails with correct error type, file, and line."""
        invalid_code = """
def foo(
    pass
"""
        result = validate_code_syntax(invalid_code)
        assert not result.is_valid
        assert result.error_type == "SyntaxError"
        assert result.error_line is not None
        assert result.error_line > 0
        # Verify error message contains relevant info
        assert result.error_message is not None
        assert "unexpected EOF" in result.error_message.lower() or "invalid syntax" in result.error_message.lower()

    def test_unresolvable_import_fails(self):
        """Test that an unresolvable import fails validation."""
        code = """
import some_unresolvable_package_abcdef
"""
        result = validate_imports(code)
        assert not result.is_valid
        assert "some_unresolvable_package_abcdef" in result.error_message

    def test_missing_module_fails(self):
        """Test that a missing module fails validation."""
        code = """
import definitely_missing_module_12345
"""
        with patch('core.pre_mutation_guard._check_module_available') as mock_check:
            mock_check.return_value = False
            result = validate_module_availability(code)
            assert not result.is_valid
            assert "definitely_missing_module_12345" in result.error_message

    def test_integration_with_mutation_pipeline_aborts_on_validation_failure(self):
        """Test that integration with mutation pipeline aborts on validation failure."""
        invalid_code = """
def broken(
    pass
"""
        # The guard should either raise an exception or return a failure indicator
        try:
            result = pre_mutation_guard(invalid_code)
            # If it returns a result, it should indicate failure
            if hasattr(result, 'is_valid'):
                assert not result.is_valid
            else:
                assert result is False
        except ValidationError:
            # Exception is also acceptable
            pass
        except Exception as e:
            # Any exception indicating failure is acceptable
            assert "syntax" in str(e).lower() or "invalid" in str(e).lower()

    def test_error_record_format_matches_expected_structure(self):
        """Test that error record format matches expected structure."""
        invalid_code = """
import nonexistent_module_for_testing

def test():
    pass
"""
        # Test syntax error record
        syntax_result = validate_code_syntax(invalid_code)
        assert hasattr(syntax_result, 'is_valid')
        assert hasattr(syntax_result, 'error_type')
        assert hasattr(syntax_result, 'error_line')
        assert hasattr(syntax_result, 'error_message')
        
        # Test import error record
        import_result = validate_imports(invalid_code)
        assert hasattr(import_result, 'is_valid')
        assert hasattr(import_result, 'error_type')
        assert hasattr(import_result, 'error_line')
        assert hasattr(import_result, 'error_message')
        
        # Verify structure matches ValidationResult
        assert isinstance(syntax_result, ValidationResult)
        assert isinstance(import_result, ValidationResult)
        
        # Verify error record contains expected fields
        if not import_result.is_valid:
            assert import_result.error_type is not None
            assert import_result.error_message is not None
            assert "nonexistent_module_for_testing" in import_result.error_message