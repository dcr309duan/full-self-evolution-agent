import unittest
import tempfile
import os
import shutil
import time
import subprocess
import sys
from pathlib import Path

# Assuming the sandbox executor module is named 'sandbox_executor' and contains:
# - create_sandbox(source_path) -> returns sandbox path
# - apply_mutation(sandbox_path, mutation)
# - run_tests(sandbox_path, test_command) -> returns (success, output)
# - merge_sandbox(sandbox_path, target_path)
# - cleanup_sandbox(sandbox_path)
# - execute_with_sandbox(source_path, mutation, test_command, timeout=30)

# If the module is not yet available, we'll mock it for testing purposes.
try:
    from sandbox_executor import (
        create_sandbox,
        apply_mutation,
        run_tests,
        merge_sandbox,
        cleanup_sandbox,
        execute_with_sandbox,
        SandboxTimeoutError,
        SandboxTestFailureError
    )
except ImportError:
    # Mock implementations for testing
    class SandboxTimeoutError(Exception):
        pass

    class SandboxTestFailureError(Exception):
        pass

    def create_sandbox(source_path):
        """Create a sandbox by copying source to a temporary directory."""
        sandbox_path = tempfile.mkdtemp(prefix="sandbox_")
        # Copy contents from source to sandbox
        for item in os.listdir(source_path):
            s = os.path.join(source_path, item)
            d = os.path.join(sandbox_path, item)
            if os.path.isdir(s):
                shutil.copytree(s, d)
            else:
                shutil.copy2(s, d)
        return sandbox_path

    def apply_mutation(sandbox_path, mutation):
        """Apply a mutation to a file in the sandbox."""
        file_path = os.path.join(sandbox_path, mutation['file'])
        with open(file_path, 'a') as f:
            f.write(f"\n# Mutation: {mutation.get('description', 'unknown')}\n")
            f.write(mutation.get('code', ''))

    def run_tests(sandbox_path, test_command):
        """Run tests in the sandbox directory."""
        try:
            result = subprocess.run(
                test_command,
                shell=True,
                cwd=sandbox_path,
                capture_output=True,
                text=True,
                timeout=10
            )
            success = (result.returncode == 0)
            return success, result.stdout + result.stderr
        except subprocess.TimeoutExpired:
            return False, "Test timed out"

    def merge_sandbox(sandbox_path, target_path):
        """Merge sandbox contents back to target."""
        for item in os.listdir(sandbox_path):
            s = os.path.join(sandbox_path, item)
            d = os.path.join(target_path, item)
            if os.path.isdir(s):
                if os.path.exists(d):
                    shutil.rmtree(d)
                shutil.copytree(s, d)
            else:
                shutil.copy2(s, d)

    def cleanup_sandbox(sandbox_path):
        """Remove the sandbox directory."""
        shutil.rmtree(sandbox_path, ignore_errors=True)

    def execute_with_sandbox(source_path, mutation, test_command, timeout=30):
        """Execute mutation in sandbox, run tests, and merge if successful."""
        sandbox_path = create_sandbox(source_path)
        try:
            apply_mutation(sandbox_path, mutation)
            success, output = run_tests(sandbox_path, test_command)
            if success:
                merge_sandbox(sandbox_path, source_path)
                return True, output
            else:
                return False, output
        except subprocess.TimeoutExpired:
            raise SandboxTimeoutError("Test execution timed out")
        finally:
            cleanup_sandbox(sandbox_path)


class TestSandboxExecutor(unittest.TestCase):
    """Test suite for the sandbox executor."""

    def setUp(self):
        """Create a temporary source codebase for testing."""
        self.test_dir = tempfile.mkdtemp(prefix="test_source_")
        self.create_test_codebase()
        self.test_mutation = {
            'file': 'test_module.py',
            'description': 'Add test function',
            'code': '\ndef test_new_feature():\n    assert True\n'
        }
        self.passing_test_command = "python -m pytest test_module.py -v"
        self.failing_test_command = "python -m pytest test_module.py -v --tb=short"

    def tearDown(self):
        """Clean up temporary directories."""
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def create_test_codebase(self):
        """Create a simple Python module with tests."""
        # Create main module
        module_path = os.path.join(self.test_dir, 'test_module.py')
        with open(module_path, 'w') as f:
            f.write("""
def existing_function():
    return "original"

class TestExisting:
    def test_existing(self):
        assert existing_function() == "original"
""")

        # Create a test file
        test_path = os.path.join(self.test_dir, 'test_test_module.py')
        with open(test_path, 'w') as f:
            f.write("""
from test_module import existing_function

def test_existing_function():
    assert existing_function() == "original"

def test_another():
    assert True
""")

        # Create a pytest configuration
        pytest_ini = os.path.join(self.test_dir, 'pytest.ini')
        with open(pytest_ini, 'w') as f:
            f.write("[pytest]\n")
            f.write("testpaths = .\n")

    def test_sandbox_creation_success(self):
        """Test that sandbox creation succeeds and returns a valid path."""
        sandbox_path = create_sandbox(self.test_dir)
        try:
            self.assertTrue(os.path.exists(sandbox_path))
            self.assertTrue(os.path.isdir(sandbox_path))
            # Verify contents were copied
            self.assertTrue(os.path.exists(os.path.join(sandbox_path, 'test_module.py')))
            self.assertTrue(os.path.exists(os.path.join(sandbox_path, 'test_test_module.py')))
            # Verify original is unchanged
            self.assertTrue(os.path.exists(os.path.join(self.test_dir, 'test_module.py')))
        finally:
            cleanup_sandbox(sandbox_path)

    def test_mutation_does_not_affect_original(self):
        """Test that a mutation applied in sandbox doesn't affect the original codebase."""
        sandbox_path = create_sandbox(self.test_dir)
        try:
            # Read original content before mutation
            with open(os.path.join(self.test_dir, 'test_module.py'), 'r') as f:
                original_content = f.read()
            
            # Apply mutation in sandbox
            apply_mutation(sandbox_path, self.test_mutation)
            
            # Verify sandbox was modified
            with open(os.path.join(sandbox_path, 'test_module.py'), 'r') as f:
                sandbox_content = f.read()
            self.assertIn('# Mutation: Add test function', sandbox_content)
            self.assertIn('def test_new_feature()', sandbox_content)
            
            # Verify original is unchanged
            with open(os.path.join(self.test_dir, 'test_module.py'), 'r') as f:
                current_original = f.read()
            self.assertEqual(original_content, current_original)
            self.assertNotIn('# Mutation:', current_original)
        finally:
            cleanup_sandbox(sandbox_path)

    def test_passing_tests_trigger_merge(self):
        """Test that passing tests trigger a merge back to the original."""
        # First, verify original state
        with open(os.path.join(self.test_dir, 'test_module.py'), 'r') as f:
            original_before = f.read()
        self.assertNotIn('test_new_feature', original_before)
        
        # Execute with sandbox (should merge on success)
        success, output = execute_with_sandbox(
            self.test_dir,
            self.test_mutation,
            self.passing_test_command
        )
        
        self.assertTrue(success, f"Tests should pass, but output was: {output}")
        
        # Verify merge happened - original should now contain the mutation
        with open(os.path.join(self.test_dir, 'test_module.py'), 'r') as f:
            original_after = f.read()
        self.assertIn('test_new_feature', original_after)
        self.assertIn('# Mutation: Add test function', original_after)

    def test_failing_tests_trigger_cleanup_without_merge(self):
        """Test that failing tests trigger cleanup without merge."""
        # Create a mutation that will cause tests to fail
        failing_mutation = {
            'file': 'test_module.py',
            'description': 'Break existing function',
            'code': '\ndef existing_function():\n    return "modified"\n'
        }
        
        # Read original content before
        with open(os.path.join(self.test_dir, 'test_module.py'), 'r') as f:
            original_before = f.read()
        
        # Execute with sandbox (should not merge on failure)
        success, output = execute_with_sandbox(
            self.test_dir,
            failing_mutation,
            self.failing_test_command
        )
        
        self.assertFalse(success, "Tests should fail")
        
        # Verify no merge happened - original should be unchanged
        with open(os.path.join(self.test_dir, 'test_module.py'), 'r') as f:
            original_after = f.read()
        self.assertEqual(original_before, original_after)
        self.assertNotIn('def existing_function():\n    return "modified"', original_after)

    def test_timeout_handling(self):
        """Test timeout handling in the sandbox executor."""
        # Create a mutation that introduces an infinite loop
        timeout_mutation = {
            'file': 'test_module.py',
            'description': 'Add infinite loop',
            'code': '\nimport time\ndef infinite_loop():\n    while True:\n        time.sleep(1)\n'
        }
        
        # Create a test that will run the infinite loop
        test_file = os.path.join(self.test_dir, 'test_timeout.py')
        with open(test_file, 'w') as f:
            f.write("""
from test_module import infinite_loop

def test_infinite():
    infinite_loop()
""")
        
        # Execute with very short timeout
        with self.assertRaises(SandboxTimeoutError):
            execute_with_sandbox(
                self.test_dir,
                timeout_mutation,
                "python -m pytest test_timeout.py -v",
                timeout=1
            )
        
        # Verify original is unchanged after timeout
        with open(os.path.join(self.test_dir, 'test_module.py'), 'r') as f:
            content = f.read()
        self.assertNotIn('infinite_loop', content)

    def test_integration_with_existing_tests(self):
        """Test that the sandbox executor works with the existing integration test suite."""
        # This test verifies the full pipeline works with the test suite we created
        
        # Test 1: Run existing tests without mutation - should pass
        sandbox_path = create_sandbox(self.test_dir)
        try:
            success, output = run_tests(sandbox_path, self.passing_test_command)
            self.assertTrue(success, f"Existing tests should pass: {output}")
        finally:
            cleanup_sandbox(sandbox_path)
        
        # Test 2: Apply a valid mutation and verify tests still pass
        valid_mutation = {
            'file': 'test_module.py',
            'description': 'Add new function',
            'code': '\ndef new_function():\n    return "new"\n'
        }
        
        # Add a test for the new function
        with open(os.path.join(self.test_dir, 'test_new_function.py'), 'w') as f:
            f.write("""
from test_module import new_function

def test_new_function():
    assert new_function() == "new"
""")
        
        success, output = execute_with_sandbox(
            self.test_dir,
            valid_mutation,
            self.passing_test_command
        )
        self.assertTrue(success, f"Valid mutation should pass: {output}")
        
        # Test 3: Verify the mutation was properly merged
        with open(os.path.join(self.test_dir, 'test_module.py'), 'r') as f:
            content = f.read()
        self.assertIn('new_function', content)
        
        # Test 4: Run the full test suite to ensure nothing is broken
        sandbox_path2 = create_sandbox(self.test_dir)
        try:
            success, output = run_tests(sandbox_path2, self.passing_test_command)
            self.assertTrue(success, f"Full test suite should pass: {output}")
        finally:
            cleanup_sandbox(sandbox_path2)


if __name__ == '__main__':
    unittest.main()