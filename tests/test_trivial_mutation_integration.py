import os
import tempfile
import shutil
import unittest
import sys

class TestTrivialMutationIntegration(unittest.TestCase):
    def setUp(self):
        # Create a temporary directory for the test
        self.test_dir = tempfile.mkdtemp()
        # Create a simple test file with a function
        self.test_file_path = os.path.join(self.test_dir, "example.py")
        with open(self.test_file_path, "w") as f:
            f.write("def add(a, b):\n    return a + b\n")

    def tearDown(self):
        # Clean up the temporary directory
        shutil.rmtree(self.test_dir)

    def test_trivial_mutation(self):
        # Read the original content
        with open(self.test_file_path, "r") as f:
            original_content = f.read()

        # Apply a trivial mutation: add a comment to the function
        mutated_content = original_content.replace(
            "def add(a, b):",
            "def add(a, b):  # mutated"
        )

        # Write the mutated content back
        with open(self.test_file_path, "w") as f:
            f.write(mutated_content)

        # Verify the mutation was applied correctly
        with open(self.test_file_path, "r") as f:
            new_content = f.read()

        expected_content = "def add(a, b):  # mutated\n    return a + b\n"
        self.assertEqual(new_content, expected_content)

def run_test_with_retry():
    consecutive_passes = 0
    max_attempts = 100  # Safety limit to prevent infinite loops
    
    for attempt in range(1, max_attempts + 1):
        print(f"\n--- Attempt {attempt} ---")
        
        # Create a test suite and run it
        suite = unittest.TestLoader().loadTestsFromTestCase(TestTrivialMutationIntegration)
        runner = unittest.TextTestRunner(verbosity=2)
        result = runner.run(suite)
        
        if result.wasSuccessful():
            consecutive_passes += 1
            print(f"Test passed! Consecutive passes: {consecutive_passes}")
            if consecutive_passes >= 3:
                print("Test passed 3 consecutive times. Exiting.")
                return True
        else:
            consecutive_passes = 0
            print(f"Test failed. Consecutive passes reset to 0.")
            
            # Analyze the error
            for test_case, traceback in result.failures + result.errors:
                error_message = str(traceback)
                print(f"\nError analysis:")
                
                if "ImportError" in error_message or "ModuleNotFoundError" in error_message:
                    print("  - Import error detected. Check module dependencies and PYTHONPATH.")
                elif "PermissionError" in error_message or "OSError" in error_message:
                    print("  - File permission or OS error detected. Check file permissions and disk space.")
                elif "FileNotFoundError" in error_message:
                    print("  - File not found error. Check file paths and existence.")
                elif "AssertionError" in error_message:
                    print("  - Assertion error. The mutation may not have been applied correctly.")
                    # Add debugging output
                    print(f"  - Debug: Test file path: {test_case.test_file_path}")
                    try:
                        with open(test_case.test_file_path, 'r') as f:
                            print(f"  - Debug: Current file content:\n{f.read()}")
                    except Exception as e:
                        print(f"  - Debug: Could not read file: {e}")
                else:
                    print(f"  - Unknown error type. Full traceback:\n{error_message}")
    
    print(f"Failed to achieve 3 consecutive passes after {max_attempts} attempts.")
    return False

def run_trivial_mutation_test():
    """Run the trivial mutation test and return True if it passes."""
    suite = unittest.TestLoader().loadTestsFromTestCase(TestTrivialMutationIntegration)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return result.wasSuccessful()

if __name__ == "__main__":
    # Run the trivial mutation test first to check if new features should be blocked
    print("Running trivial mutation test to check if new features should be blocked...")
    if not run_trivial_mutation_test():
        print("ERROR: Trivial mutation test failed. New features are blocked until this test passes.")
        sys.exit(1)
    
    print("Trivial mutation test passed. Proceeding with full test suite...")
    success = run_test_with_retry()
    sys.exit(0 if success else 1)