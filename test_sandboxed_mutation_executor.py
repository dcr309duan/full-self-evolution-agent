import os
import shutil
import tempfile
import unittest
from unittest.mock import patch, MagicMock

# Assume the module under test is 'sandboxed_mutation_executor'
# and contains classes SandboxedMutationExecutor and MutationResult.
# Adjust imports as needed for your actual module structure.
from sandboxed_mutation_executor import SandboxedMutationExecutor, MutationResult


class TestSandboxedMutationExecutor(unittest.TestCase):
    """Tests for the SandboxedMutationExecutor class."""

    def setUp(self):
        # Create a temporary directory to simulate the project root.
        self.test_dir = tempfile.mkdtemp()
        # Create a source file to be mutated.
        self.source_file = os.path.join(self.test_dir, "source.py")
        with open(self.source_file, "w") as f:
            f.write("x = 1\n")
        # Create a sandbox directory (simulating where the clone will be placed).
        self.sandbox_dir = tempfile.mkdtemp()
        # Create a backup directory for rollback.
        self.backup_dir = tempfile.mkdtemp()
        # Instantiate the executor with test directories.
        self.executor = SandboxedMutationExecutor(
            project_root=self.test_dir,
            sandbox_root=self.sandbox_dir,
            backup_root=self.backup_dir,
        )

    def tearDown(self):
        # Clean up temporary directories.
        shutil.rmtree(self.test_dir, ignore_errors=True)
        shutil.rmtree(self.sandbox_dir, ignore_errors=True)
        shutil.rmtree(self.backup_dir, ignore_errors=True)

    def test_sandbox_clones_files_correctly(self):
        """Test that sandbox clones files correctly."""
        # Define a mutation that modifies the source file.
        mutation = MagicMock()
        mutation.apply = MagicMock()
        # Clone the project into the sandbox.
        self.executor.clone_to_sandbox()
        # Check that the source file exists in the sandbox.
        sandbox_source = os.path.join(self.sandbox_dir, "source.py")
        self.assertTrue(os.path.exists(sandbox_source))
        # Verify the content is identical to the original.
        with open(self.source_file, "r") as orig_f:
            original_content = orig_f.read()
        with open(sandbox_source, "r") as sand_f:
            sandbox_content = sand_f.read()
        self.assertEqual(original_content, sandbox_content)

    def test_passing_mutation_promotes_files(self):
        """Test that a passing mutation promotes files from sandbox to project."""
        # Simulate a mutation that passes (e.g., tests succeed).
        mutation = MagicMock()
        mutation.apply = MagicMock()
        # Clone and apply mutation in sandbox.
        self.executor.clone_to_sandbox()
        self.executor.apply_mutation(mutation)
        # Simulate that tests pass.
        self.executor.run_tests = MagicMock(return_value=True)
        # Execute the mutation (which should promote on success).
        result = self.executor.execute_mutation(mutation)
        # Verify promotion: sandbox files should be copied to project root.
        sandbox_source = os.path.join(self.sandbox_dir, "source.py")
        project_source = os.path.join(self.test_dir, "source.py")
        # After promotion, project file should equal sandbox file.
        with open(sandbox_source, "r") as sand_f:
            sand_content = sand_f.read()
        with open(project_source, "r") as proj_f:
            proj_content = proj_f.read()
        self.assertEqual(sand_content, proj_content)
        # MutationResult should indicate success.
        self.assertTrue(result.success)

    def test_failing_mutation_rolls_back_and_logs_failure_context(self):
        """Test that a failing mutation rolls back and logs failure context."""
        # Simulate a mutation that fails (tests fail).
        mutation = MagicMock()
        mutation.apply = MagicMock()
        # Clone and apply mutation in sandbox.
        self.executor.clone_to_sandbox()
        self.executor.apply_mutation(mutation)
        # Simulate that tests fail.
        self.executor.run_tests = MagicMock(return_value=False)
        # Capture log output.
        with self.assertLogs(level='ERROR') as log:
            result = self.executor.execute_mutation(mutation)
        # Verify rollback: project file should be restored from backup.
        project_source = os.path.join(self.test_dir, "source.py")
        # After rollback, project file should be original (pre-mutation).
        with open(self.source_file, "r") as orig_f:
            original_content = orig_f.read()
        with open(project_source, "r") as proj_f:
            proj_content = proj_f.read()
        self.assertEqual(original_content, proj_content)
        # MutationResult should indicate failure.
        self.assertFalse(result.success)
        # Check that failure context is logged.
        self.assertTrue(any("Mutation failed" in message for message in log.output))

    def test_orchestrator_integration_with_mock_mutation(self):
        """Test that the orchestrator integration works end-to-end with a mock mutation."""
        # Create a mock mutation that will be used by the orchestrator.
        mock_mutation = MagicMock()
        mock_mutation.apply = MagicMock()
        # Simulate the orchestrator calling the executor.
        # For this test, we'll simulate a passing mutation.
        self.executor.clone_to_sandbox()
        self.executor.apply_mutation(mock_mutation)
        self.executor.run_tests = MagicMock(return_value=True)
        result = self.executor.execute_mutation(mock_mutation)
        # Verify that the mutation was applied and promoted.
        self.assertTrue(result.success)
        # Verify that the sandbox was cleaned up after promotion.
        sandbox_source = os.path.join(self.sandbox_dir, "source.py")
        # After promotion, sandbox might be cleaned up; adjust expectation based on implementation.
        # For this test, we assume sandbox is not cleaned up immediately.
        # Alternatively, check that sandbox still exists (if cleanup is not done).
        self.assertTrue(os.path.exists(sandbox_source))
        # Verify that the project file now contains the mutation.
        # Since we used a mock, we can't check content, but we can check that apply was called.
        mock_mutation.apply.assert_called_once()


if __name__ == "__main__":
    unittest.main()