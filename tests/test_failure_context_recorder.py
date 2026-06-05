"""Tests for the failure_context_recorder module."""

import ast
import os
import sys
import tempfile
import unittest
from unittest.mock import patch, MagicMock, mock_open

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mutation_testing.failure_context_recorder import (
    FailureContext,
    capture_failure_context,
    generate_reproducible_example,
    FailureContextRecorder
)
from mutation_testing.failure_analysis import FailureAnalyzer


class TestFailureContextRecorder(unittest.TestCase):
    """Test suite for failure context recording functionality."""

    def setUp(self):
        """Set up test fixtures."""
        # Create a mock target file with known AST
        self.mock_source_code = """
def add(a, b):
    return a + b

def multiply(x, y):
    return x * y
"""
        self.mock_file_path = "/fake/path/target_module.py"
        self.mock_ast = ast.parse(self.mock_source_code)
        
        # Sample mutation failure data
        self.failure_data = {
            "mutant_id": "MUT-001",
            "mutant_type": "ArithmeticOperatorReplacement",
            "original_code": "a + b",
            "mutated_code": "a - b",
            "test_name": "test_add_positive_numbers",
            "test_file": "tests/test_target_module.py",
            "test_output": "FAIL: test_add_positive_numbers (tests.test_target_module.TestMathOperations)\n"
                          "AssertionError: Expected 5 but got -1\n"
                          "Expected: 5\n"
                          "Actual: -1\n"
                          "Traceback (most recent call last):\n"
                          "  File \"tests/test_target_module.py\", line 15, in test_add_positive_numbers\n"
                          "    self.assertEqual(add(2, 3), 5)\n"
                          "AssertionError: -1 != 5",
            "line_number": 2,
            "column_offset": 4,
            "end_line_number": 2,
            "end_column_offset": 9
        }

    def test_failure_context_creation(self):
        """Test that FailureContext is created with all required fields."""
        context = FailureContext(
            mutant_id=self.failure_data["mutant_id"],
            mutant_type=self.failure_data["mutant_type"],
            original_code=self.failure_data["original_code"],
            mutated_code=self.failure_data["mutated_code"],
            test_name=self.failure_data["test_name"],
            test_file=self.failure_data["test_file"],
            test_output=self.failure_data["test_output"],
            source_file=self.mock_file_path,
            source_code=self.mock_source_code,
            line_number=self.failure_data["line_number"],
            column_offset=self.failure_data["column_offset"],
            end_line_number=self.failure_data["end_line_number"],
            end_column_offset=self.failure_data["end_column_offset"]
        )
        
        # Verify all required fields are present
        self.assertEqual(context.mutant_id, "MUT-001")
        self.assertEqual(context.mutant_type, "ArithmeticOperatorReplacement")
        self.assertEqual(context.original_code, "a + b")
        self.assertEqual(context.mutated_code, "a - b")
        self.assertEqual(context.test_name, "test_add_positive_numbers")
        self.assertEqual(context.test_file, "tests/test_target_module.py")
        self.assertIn("AssertionError", context.test_output)
        self.assertEqual(context.source_file, self.mock_file_path)
        self.assertEqual(context.source_code, self.mock_source_code)
        self.assertEqual(context.line_number, 2)
        self.assertEqual(context.column_offset, 4)
        self.assertEqual(context.end_line_number, 2)
        self.assertEqual(context.end_column_offset, 9)

    def test_failure_context_to_dict(self):
        """Test that FailureContext can be converted to dictionary."""
        context = FailureContext(
            mutant_id="MUT-001",
            mutant_type="ArithmeticOperatorReplacement",
            original_code="a + b",
            mutated_code="a - b",
            test_name="test_add_positive_numbers",
            test_file="tests/test_target_module.py",
            test_output="AssertionError: Expected 5 but got -1",
            source_file=self.mock_file_path,
            source_code=self.mock_source_code,
            line_number=2,
            column_offset=4,
            end_line_number=2,
            end_column_offset=9
        )
        
        context_dict = context.to_dict()
        
        # Verify dictionary contains all required fields
        required_fields = [
            "mutant_id", "mutant_type", "original_code", "mutated_code",
            "test_name", "test_file", "test_output", "source_file",
            "source_code", "line_number", "column_offset",
            "end_line_number", "end_column_offset"
        ]
        
        for field in required_fields:
            self.assertIn(field, context_dict, f"Missing field: {field}")
        
        self.assertEqual(context_dict["mutant_id"], "MUT-001")
        self.assertEqual(context_dict["line_number"], 2)

    def test_capture_failure_context(self):
        """Test capturing failure context from failure data."""
        with patch("builtins.open", mock_open(read_data=self.mock_source_code)):
            context = capture_failure_context(
                failure_data=self.failure_data,
                source_file=self.mock_file_path
            )
        
        # Verify captured context
        self.assertIsInstance(context, FailureContext)
        self.assertEqual(context.mutant_id, "MUT-001")
        self.assertEqual(context.mutant_type, "ArithmeticOperatorReplacement")
        self.assertEqual(context.original_code, "a + b")
        self.assertEqual(context.mutated_code, "a - b")
        self.assertEqual(context.test_name, "test_add_positive_numbers")
        self.assertEqual(context.test_file, "tests/test_target_module.py")
        self.assertIn("AssertionError", context.test_output)
        self.assertEqual(context.source_file, self.mock_file_path)
        self.assertEqual(context.source_code, self.mock_source_code)
        self.assertEqual(context.line_number, 2)
        self.assertEqual(context.column_offset, 4)

    def test_capture_failure_context_file_not_found(self):
        """Test handling of missing source file."""
        with patch("builtins.open", side_effect=FileNotFoundError):
            context = capture_failure_context(
                failure_data=self.failure_data,
                source_file="/nonexistent/path.py"
            )
        
        self.assertIsNone(context)

    def test_generate_reproducible_example(self):
        """Test generation of reproducible example from failure context."""
        context = FailureContext(
            mutant_id="MUT-001",
            mutant_type="ArithmeticOperatorReplacement",
            original_code="a + b",
            mutated_code="a - b",
            test_name="test_add_positive_numbers",
            test_file="tests/test_target_module.py",
            test_output="AssertionError: Expected 5 but got -1\n"
                       "Expected: 5\n"
                       "Actual: -1",
            source_file=self.mock_file_path,
            source_code=self.mock_source_code,
            line_number=2,
            column_offset=4,
            end_line_number=2,
            end_column_offset=9
        )
        
        reproducible_example = generate_reproducible_example(context)
        
        # Verify the generated example is valid Python
        try:
            ast.parse(reproducible_example)
        except SyntaxError as e:
            self.fail(f"Generated reproducible example is not valid Python: {e}")
        
        # Verify example contains key components
        self.assertIn("MUT-001", reproducible_example)
        self.assertIn("ArithmeticOperatorReplacement", reproducible_example)
        self.assertIn("a + b", reproducible_example)
        self.assertIn("a - b", reproducible_example)
        self.assertIn("test_add_positive_numbers", reproducible_example)
        self.assertIn("AssertionError", reproducible_example)
        self.assertIn(self.mock_file_path, reproducible_example)

    def test_reproducible_example_execution(self):
        """Test that the generated reproducible example can be executed."""
        context = FailureContext(
            mutant_id="MUT-002",
            mutant_type="BinaryOperatorReplacement",
            original_code="x * y",
            mutated_code="x / y",
            test_name="test_multiply_numbers",
            test_file="tests/test_target_module.py",
            test_output="AssertionError: Expected 15 but got 0.6\n"
                       "Expected: 15\n"
                       "Actual: 0.6",
            source_file=self.mock_file_path,
            source_code=self.mock_source_code,
            line_number=5,
            column_offset=4,
            end_line_number=5,
            end_column_offset=9
        )
        
        reproducible_example = generate_reproducible_example(context)
        
        # Execute the generated example in a temporary directory
        with tempfile.TemporaryDirectory() as tmp_dir:
            example_file = os.path.join(tmp_dir, "reproducible_example.py")
            with open(example_file, "w") as f:
                f.write(reproducible_example)
            
            # Execute the example
            try:
                exec_globals = {}
                exec(reproducible_example, exec_globals)
            except Exception as e:
                self.fail(f"Reproducible example execution failed: {e}")

    def test_failure_context_recorder_integration(self):
        """Test integration with FailureContextRecorder class."""
        recorder = FailureContextRecorder()
        
        # Record multiple failures
        with patch("builtins.open", mock_open(read_data=self.mock_source_code)):
            recorder.record_failure(
                failure_data=self.failure_data,
                source_file=self.mock_file_path
            )
            
            additional_failure = {
                "mutant_id": "MUT-002",
                "mutant_type": "BinaryOperatorReplacement",
                "original_code": "x * y",
                "mutated_code": "x / y",
                "test_name": "test_multiply_numbers",
                "test_file": "tests/test_target_module.py",
                "test_output": "AssertionError: Expected 15 but got 0.6",
                "line_number": 5,
                "column_offset": 4,
                "end_line_number": 5,
                "end_column_offset": 9
            }
            
            recorder.record_failure(
                failure_data=additional_failure,
                source_file=self.mock_file_path
            )
        
        # Verify recorded failures
        recorded_failures = recorder.get_recorded_failures()
        self.assertEqual(len(recorded_failures), 2)
        self.assertEqual(recorded_failures[0].mutant_id, "MUT-001")
        self.assertEqual(recorded_failures[1].mutant_id, "MUT-002")
        
        # Verify generated reproducible examples
        examples = recorder.get_reproducible_examples()
        self.assertEqual(len(examples), 2)
        
        # Verify each example is valid Python
        for example in examples:
            try:
                ast.parse(example)
            except SyntaxError as e:
                self.fail(f"Reproducible example is not valid Python: {e}")

    def test_integration_with_failure_analysis(self):
        """Test integration with failure analysis module."""
        # Create a mock FailureAnalyzer
        analyzer = MagicMock(spec=FailureAnalyzer)
        analyzer.analyze_failure.return_value = {
            "root_cause": "Arithmetic operator replacement",
            "severity": "high",
            "impacted_tests": ["test_add_positive_numbers"]
        }
        
        # Create failure context
        context = FailureContext(
            mutant_id="MUT-001",
            mutant_type="ArithmeticOperatorReplacement",
            original_code="a + b",
            mutated_code="a - b",
            test_name="test_add_positive_numbers",
            test_file="tests/test_target_module.py",
            test_output="AssertionError: Expected 5 but got -1",
            source_file=self.mock_file_path,
            source_code=self.mock_source_code,
            line_number=2,
            column_offset=4,
            end_line_number=2,
            end_column_offset=9
        )
        
        # Analyze failure using the analyzer
        analysis_result = analyzer.analyze_failure(context)
        
        # Verify analysis results
        self.assertIsNotNone(analysis_result)
        self.assertEqual(analysis_result["root_cause"], "Arithmetic operator replacement")
        self.assertEqual(analysis_result["severity"], "high")
        self.assertIn("test_add_positive_numbers", analysis_result["impacted_tests"])
        
        # Verify the analyzer was called with the correct context
        analyzer.analyze_failure.assert_called_once_with(context)

    def test_failure_context_recorder_clear(self):
        """Test clearing recorded failures."""
        recorder = FailureContextRecorder()
        
        with patch("builtins.open", mock_open(read_data=self.mock_source_code)):
            recorder.record_failure(
                failure_data=self.failure_data,
                source_file=self.mock_file_path
            )
        
        self.assertEqual(len(recorder.get_recorded_failures()), 1)
        
        recorder.clear_failures()
        self.assertEqual(len(recorder.get_recorded_failures()), 0)
        self.assertEqual(len(recorder.get_reproducible_examples()), 0)

    def test_failure_context_with_empty_test_output(self):
        """Test handling of empty test output."""
        failure_data = self.failure_data.copy()
        failure_data["test_output"] = ""
        
        with patch("builtins.open", mock_open(read_data=self.mock_source_code)):
            context = capture_failure_context(
                failure_data=failure_data,
                source_file=self.mock_file_path
            )
        
        self.assertIsNotNone(context)
        self.assertEqual(context.test_output, "")

    def test_generate_reproducible_example_without_test_output(self):
        """Test reproducible example generation without test output."""
        context = FailureContext(
            mutant_id="MUT-003",
            mutant_type="ConditionalBoundaryReplacement",
            original_code="if x < 10:",
            mutated_code="if x <= 10:",
            test_name="test_boundary_condition",
            test_file="tests/test_target_module.py",
            test_output="",
            source_file=self.mock_file_path,
            source_code=self.mock_source_code,
            line_number=1,
            column_offset=0,
            end_line_number=1,
            end_column_offset=10
        )
        
        reproducible_example = generate_reproducible_example(context)
        
        # Verify it's still valid Python
        try:
            ast.parse(reproducible_example)
        except SyntaxError as e:
            self.fail(f"Generated example without test output is not valid Python: {e}")
        
        self.assertIn("No test output captured", reproducible_example)


if __name__ == "__main__":
    unittest.main()