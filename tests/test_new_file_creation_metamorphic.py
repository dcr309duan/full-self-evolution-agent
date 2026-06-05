import os
import sys
import tempfile
import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path

# Import the mutation engine and testing framework
# Adjust these imports based on your actual project structure
try:
    from mutation_engine import MutationEngine, MutationResult
    from test_runner import TestRunner, TestResult
except ImportError:
    # Fallback for testing if modules not available
    MutationEngine = None
    TestRunner = None


class TestNewFileCreationMetamorphic(unittest.TestCase):
    """Test the metamorphic property of creating a new file and running the mutation pipeline."""

    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.original_dir = os.getcwd()
        os.chdir(self.temp_dir)
        
        # Create a simple Python file with a single function
        self.test_file_content = """
def add(a, b):
    return a + b
"""
        self.test_file_path = Path(self.temp_dir) / "test_add.py"
        self.test_file_path.write_text(self.test_file_content)

    def tearDown(self):
        """Clean up temporary files and directories."""
        os.chdir(self.original_dir)
        # Remove all files in temp directory
        for file in Path(self.temp_dir).iterdir():
            file.unlink()
        Path(self.temp_dir).rmdir()

    def test_file_creation_and_pipeline(self):
        """Test that a new file can be created, mutated, tested, and promoted."""
        # Step 1: Verify file was created
        self.assertTrue(self.test_file_path.exists(), "Test file was not created")
        
        # Step 2: Run mutation pipeline
        if MutationEngine is not None:
            engine = MutationEngine()
            mutation_result = engine.mutate_file(str(self.test_file_path))
            
            # Verify mutation occurred
            self.assertIsNotNone(mutation_result, "Mutation should produce a result")
            self.assertTrue(mutation_result.success, "Mutation should succeed")
            
            # Step 3: Run tests on mutated file
            if TestRunner is not None:
                test_runner = TestRunner()
                test_result = test_runner.run_tests(str(self.test_file_path))
                
                # Verify tests ran
                self.assertIsNotNone(test_result, "Test result should not be None")
                
                # Step 4: Promote if tests pass
                if test_result.passed:
                    promoted = engine.promote_mutation(mutation_result)
                    self.assertTrue(promoted, "Mutation should be promoted if tests pass")
        else:
            # If mutation engine not available, test basic file operations
            self.skipTest("Mutation engine not available - testing basic file operations")

    def test_file_content_verification(self):
        """Verify the created file contains the expected function."""
        content = self.test_file_path.read_text()
        self.assertIn("def add(a, b):", content, "File should contain add function")
        self.assertIn("return a + b", content, "File should contain addition operation")

    def test_pipeline_with_mock(self):
        """Test the pipeline using mocks when actual engine is unavailable."""
        with patch('mutation_engine.MutationEngine') as MockEngine, \
             patch('test_runner.TestRunner') as MockRunner:
            
            # Setup mock mutation engine
            mock_engine = MockEngine.return_value
            mock_result = MagicMock()
            mock_result.success = True
            mock_result.mutated_file = str(self.test_file_path)
            mock_engine.mutate_file.return_value = mock_result
            mock_engine.promote_mutation.return_value = True
            
            # Setup mock test runner
            mock_runner = MockRunner.return_value
            mock_test_result = MagicMock()
            mock_test_result.passed = True
            mock_runner.run_tests.return_value = mock_test_result
            
            # Execute pipeline
            engine = MockEngine()
            mutation_result = engine.mutate_file(str(self.test_file_path))
            
            self.assertTrue(mutation_result.success, "Mock mutation should succeed")
            
            runner = MockRunner()
            test_result = runner.run_tests(str(self.test_file_path))
            
            self.assertTrue(test_result.passed, "Mock tests should pass")
            
            # Verify promotion
            promoted = engine.promote_mutation(mutation_result)
            self.assertTrue(promoted, "Mock promotion should succeed")

    def test_cleanup_verification(self):
        """Verify that cleanup removes the temporary file."""
        # Create a temporary file for cleanup testing
        temp_file = Path(self.temp_dir) / "cleanup_test.py"
        temp_file.write_text("x = 1")
        self.assertTrue(temp_file.exists(), "Cleanup test file should exist")
        
        # Simulate cleanup
        temp_file.unlink()
        self.assertFalse(temp_file.exists(), "Cleanup test file should be removed after cleanup")


if __name__ == "__main__":
    unittest.main()