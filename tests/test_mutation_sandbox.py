import unittest
import tempfile
import os
import sys
import shutil
import subprocess
import time
from pathlib import Path

# Ensure the core module is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from core.mutation_sandbox import MutationSandbox
from core.sandbox_runner import SandboxRunner


class TestMutationSandbox(unittest.TestCase):
    """Test suite for the mutation sandbox validation system."""

    def setUp(self):
        """Create a temporary directory for sandbox tests."""
        self.test_dir = tempfile.mkdtemp()
        self.sandbox = MutationSandbox(work_dir=self.test_dir)
        self.runner = SandboxRunner(work_dir=self.test_dir)

    def tearDown(self):
        """Clean up temporary directory."""
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_valid_code_passes(self):
        """Test that syntactically and semantically valid code passes validation."""
        valid_code = """
def add(a, b):
    return a + b

result = add(2, 3)
print(result)
"""
        result = self.sandbox.validate(valid_code)
        self.assertTrue(result['valid'], f"Valid code should pass: {result.get('error')}")
        self.assertIsNone(result.get('error'))

    def test_syntax_error_is_caught(self):
        """Test that SyntaxError is properly caught and reported."""
        invalid_code = """
def broken_function(x):
    if x > 0
        return x
"""
        result = self.sandbox.validate(invalid_code)
        self.assertFalse(result['valid'])
        self.assertIn('SyntaxError', result.get('error', ''))

    def test_import_error_caught(self):
        """Test that ImportError for non-existent modules is caught."""
        code_with_bad_import = """
import non_existent_module_xyz
print("This should not run")
"""
        result = self.sandbox.validate(code_with_bad_import)
        self.assertFalse(result['valid'])
        self.assertIn('ImportError', result.get('error', ''))

    def test_name_error_caught(self):
        """Test that NameError for undefined variables is caught."""
        code_with_undefined_var = """
print(undefined_variable_12345)
"""
        result = self.sandbox.validate(code_with_undefined_var)
        self.assertFalse(result['valid'])
        self.assertIn('NameError', result.get('error', ''))

    def test_temp_files_cleaned_up(self):
        """Test that temporary files are cleaned up after validation."""
        code = "x = 1"
        # Count temp files before
        before_files = set(os.listdir(self.test_dir))
        self.sandbox.validate(code)
        # Count temp files after
        after_files = set(os.listdir(self.test_dir))
        # No new files should remain (the temp file should be cleaned)
        self.assertEqual(before_files, after_files,
                         "Temporary files should be cleaned up after validation")

    def test_timeout_mechanism(self):
        """Test that the timeout mechanism works for long-running code."""
        infinite_loop_code = """
while True:
    pass
"""
        # Use a very short timeout (0.1 seconds) to ensure it triggers
        result = self.sandbox.validate(infinite_loop_code, timeout=0.1)
        self.assertFalse(result['valid'])
        self.assertIn('Timeout', result.get('error', ''))

    def test_actual_files_not_modified(self):
        """Test that actual files on disk are not modified during validation."""
        # Create a real file to monitor
        real_file_path = os.path.join(self.test_dir, "important_data.txt")
        original_content = "This is important data that should not change."
        with open(real_file_path, 'w') as f:
            f.write(original_content)

        # Code that tries to modify the file
        malicious_code = f"""
import os
os.chmod("{real_file_path}", 0o777)
with open("{real_file_path}", 'w') as f:
    f.write("MODIFIED BY MUTATION")
"""
        result = self.sandbox.validate(malicious_code)
        # The validation may pass or fail depending on sandbox restrictions,
        # but the actual file should remain unchanged
        with open(real_file_path, 'r') as f:
            final_content = f.read()
        self.assertEqual(final_content, original_content,
                         "Actual files should not be modified during validation")

    def test_runner_valid_code(self):
        """Test that SandboxRunner correctly runs valid code."""
        valid_code = "print('hello from sandbox')"
        result = self.runner.run(valid_code)
        self.assertTrue(result['success'])
        self.assertIn('hello from sandbox', result.get('stdout', ''))

    def test_runner_syntax_error(self):
        """Test that SandboxRunner catches syntax errors."""
        invalid_code = "if True print('bad')"
        result = self.runner.run(invalid_code)
        self.assertFalse(result['success'])
        self.assertIn('SyntaxError', result.get('stderr', ''))

    def test_runner_timeout(self):
        """Test that SandboxRunner enforces timeouts."""
        infinite_code = "while True: pass"
        result = self.runner.run(infinite_code, timeout=0.1)
        self.assertFalse(result['success'])
        self.assertIn('timeout', result.get('error', '').lower())

    def test_runner_import_error(self):
        """Test that SandboxRunner catches import errors."""
        bad_import_code = "import nonexistent_module_abc"
        result = self.runner.run(bad_import_code)
        self.assertFalse(result['success'])
        self.assertIn('ImportError', result.get('stderr', ''))

    def test_runner_name_error(self):
        """Test that SandboxRunner catches name errors."""
        undefined_var_code = "print(undefined_var)"
        result = self.runner.run(undefined_var_code)
        self.assertFalse(result['success'])
        self.assertIn('NameError', result.get('stderr', ''))


if __name__ == '__main__':
    unittest.main()