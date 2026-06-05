import unittest
import tempfile
import os
from collections import Counter
from failure_diagnosis import diagnose_failures, generate_fix_snippet, inject_fix

class TestFailureDiagnosis(unittest.TestCase):

    def setUp(self):
        # Sample mock failure logs for testing
        self.mock_logs = [
            {"error": "TypeError", "message": "unsupported operand type(s) for +: 'int' and 'str'"},
            {"error": "ValueError", "message": "invalid literal for int() with base 10: 'abc'"},
            {"error": "TypeError", "message": "unsupported operand type(s) for +: 'int' and 'str'"},
            {"error": "IndexError", "message": "list index out of range"},
            {"error": "TypeError", "message": "unsupported operand type(s) for +: 'int' and 'str'"},
            {"error": "KeyError", "message": "'missing_key'"},
        ]

    def test_most_common_error(self):
        """Test that the most common error is correctly identified."""
        result = diagnose_failures(self.mock_logs)
        expected_most_common = "TypeError"
        self.assertEqual(result["most_common_error"], expected_most_common)

    def test_fix_snippets_generated(self):
        """Test that appropriate fix snippets are generated for each error type."""
        error_types = ["TypeError", "ValueError", "IndexError", "KeyError"]
        for error in error_types:
            fix = generate_fix_snippet(error)
            self.assertIsNotNone(fix)
            self.assertIn(error, fix)

    def test_no_failures(self):
        """Test edge case: no failures."""
        result = diagnose_failures([])
        self.assertIsNone(result["most_common_error"])
        self.assertEqual(result["error_counts"], {})
        self.assertEqual(result["total_failures"], 0)

    def test_single_failure(self):
        """Test edge case: single failure."""
        single_log = [{"error": "RuntimeError", "message": "something went wrong"}]
        result = diagnose_failures(single_log)
        self.assertEqual(result["most_common_error"], "RuntimeError")
        self.assertEqual(result["total_failures"], 1)

    def test_all_different_errors(self):
        """Test edge case: all errors are different."""
        different_logs = [
            {"error": "TypeError", "message": "msg1"},
            {"error": "ValueError", "message": "msg2"},
            {"error": "IndexError", "message": "msg3"},
        ]
        result = diagnose_failures(different_logs)
        # Since all counts are 1, the most common is the first one encountered (depends on implementation)
        # We'll just check that it's one of them and counts are correct
        self.assertIn(result["most_common_error"], ["TypeError", "ValueError", "IndexError"])
        self.assertEqual(result["total_failures"], 3)

    def test_fix_injection(self):
        """Test that fix injection works correctly using a temporary file."""
        # Create a temporary Python file with a known error
        temp_content = """
def faulty_function():
    x = "10"
    y = 5
    result = x + y  # This will cause TypeError
    return result
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(temp_content)
            temp_path = f.name

        try:
            # Inject fix for TypeError
            inject_fix(temp_path, "TypeError")
            # Read the modified file
            with open(temp_path, 'r') as f:
                modified_content = f.read()
            # Check that the fix was applied (e.g., added type conversion)
            self.assertIn("int(", modified_content)  # Example fix might convert to int
        finally:
            os.unlink(temp_path)

if __name__ == '__main__':
    unittest.main()