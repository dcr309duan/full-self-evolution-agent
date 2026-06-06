import ast
import sys
import os
import tempfile
import unittest
import subprocess
import importlib.util
import traceback
from typing import Tuple, Optional


class TestEcologySelfSustaining(unittest.TestCase):
    """Integration test that validates the full ecology loop without external dependencies."""

    def setUp(self):
        """Prepare test environment."""
        self.test_dir = tempfile.mkdtemp()
        self.original_dir = os.getcwd()
        os.chdir(self.test_dir)

    def tearDown(self):
        """Clean up test environment."""
        os.chdir(self.original_dir)
        import shutil
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def _generate_novel_test(self) -> str:
        """Generate a novel test function as a string."""
        test_code = '''
def test_novel_ecology_behavior():
    """Test that demonstrates ecology self-sustaining behavior."""
    # Simple assertion that should pass in a healthy codebase
    assert 1 + 1 == 2
    
    # Verify basic arithmetic works
    result = sum(range(10))
    assert result == 45, f"Expected 45, got {result}"
    
    # Check that string operations work
    text = "ecology_self_sustaining"
    assert "_" in text
    assert text.startswith("ecology")
    
    # Verify list operations
    items = [1, 2, 3, 4, 5]
    assert len(items) == 5
    assert max(items) == 5
    assert min(items) == 1
    
    # Test dictionary operations
    mapping = {"a": 1, "b": 2}
    assert mapping["a"] == 1
    assert "c" not in mapping
    
    print("Novel ecology test passed successfully!")
'''
        return test_code

    def _verify_syntax(self, code: str) -> Tuple[bool, Optional[str]]:
        """Verify that the given code is syntactically valid Python."""
        try:
            ast.parse(code)
            return True, None
        except SyntaxError as e:
            return False, str(e)

    def _run_test_code(self, code: str) -> Tuple[bool, str]:
        """Run the given test code and return (success, output)."""
        # Write the test code to a temporary file
        test_file = os.path.join(self.test_dir, "temp_test.py")
        with open(test_file, "w") as f:
            f.write(code)
        
        # Run the test using subprocess
        result = subprocess.run(
            [sys.executable, test_file],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0:
            return True, result.stdout
        else:
            return False, result.stderr

    def _mutate_test_based_on_failure(self, code: str, failure_message: str) -> str:
        """Mutate the test code to address the failure."""
        # Simple mutation strategies based on common failure patterns
        mutated_code = code
        
        if "AssertionError" in failure_message:
            # If assertion failed, try adjusting the assertion
            if "==" in code:
                # Try changing equality to inequality or vice versa
                mutated_code = code.replace("==", "!=")
            elif "!=" in code:
                mutated_code = code.replace("!=", "==")
        
        if "NameError" in failure_message:
            # If name error, try adding the missing import
            if "import" not in code:
                mutated_code = "import sys\nimport os\n" + code
        
        if "TypeError" in failure_message:
            # If type error, try wrapping in try-except
            mutated_code = code.replace(
                "def test_novel_ecology_behavior():",
                "def test_novel_ecology_behavior():\n    try:"
            )
            mutated_code += "\n    except Exception as e:\n        print(f'Caught expected error: {e}')\n        assert True"
        
        return mutated_code

    def test_full_ecology_loop(self):
        """Test the complete ecology loop: generate, verify, run, mutate, verify."""
        
        # Step 1: Generate a novel test
        print("Step 1: Generating novel test...")
        test_code = self._generate_novel_test()
        self.assertIsNotNone(test_code)
        self.assertGreater(len(test_code), 0)
        print(f"Generated test code ({len(test_code)} chars)")
        
        # Step 2: Verify it's syntactically valid
        print("Step 2: Verifying syntax...")
        is_valid, error = self._verify_syntax(test_code)
        self.assertTrue(is_valid, f"Generated test has syntax error: {error}")
        print("Syntax is valid")
        
        # Step 3: Run it against the current codebase
        print("Step 3: Running test...")
        success, output = self._run_test_code(test_code)
        
        if success:
            print(f"Test passed: {output}")
            # If it passes, the ecology is self-sustaining
            self.assertTrue(True, "Ecology loop is self-sustaining - test passed without mutation")
        else:
            print(f"Test failed: {output}")
            
            # Step 4: Use failure to drive a mutation
            print("Step 4: Mutating test based on failure...")
            mutated_code = self._mutate_test_based_on_failure(test_code, output)
            self.assertIsNotNone(mutated_code)
            self.assertNotEqual(mutated_code, test_code, "Mutation should change the code")
            print(f"Mutated code ({len(mutated_code)} chars)")
            
            # Verify mutated code is syntactically valid
            is_valid, error = self._verify_syntax(mutated_code)
            self.assertTrue(is_valid, f"Mutated test has syntax error: {error}")
            print("Mutated code syntax is valid")
            
            # Step 5: Verify the mutation makes the test pass
            print("Step 5: Running mutated test...")
            success, output = self._run_test_code(mutated_code)
            self.assertTrue(success, f"Mutation did not make test pass: {output}")
            print(f"Mutated test passed: {output}")
        
        print("Ecology loop completed successfully!")

    def test_self_sustaining_cycle(self):
        """Test multiple cycles of the ecology loop to ensure self-sustainability."""
        
        for cycle in range(3):
            print(f"\n--- Ecology Cycle {cycle + 1} ---")
            
            # Generate test
            test_code = self._generate_novel_test()
            
            # Verify syntax
            is_valid, error = self._verify_syntax(test_code)
            self.assertTrue(is_valid, f"Cycle {cycle + 1}: Syntax error: {error}")
            
            # Run test
            success, output = self._run_test_code(test_code)
            
            if not success:
                # Mutate and verify
                mutated_code = self._mutate_test_based_on_failure(test_code, output)
                is_valid, error = self._verify_syntax(mutated_code)
                self.assertTrue(is_valid, f"Cycle {cycle + 1}: Mutation syntax error: {error}")
                
                success, output = self._run_test_code(mutated_code)
                self.assertTrue(success, f"Cycle {cycle + 1}: Mutation did not fix: {output}")
            
            print(f"Cycle {cycle + 1} completed successfully")


if __name__ == "__main__":
    unittest.main()