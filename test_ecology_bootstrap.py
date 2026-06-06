import os
import sys
import tempfile
import unittest

# Ensure the parent directory is on the path so we can import ecology_minimal_core
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import ecology_minimal_core as emc
except ImportError:
    raise ImportError(
        "ecology_minimal_core module not found. Ensure it is in the same directory."
    )


class TestEcologyBootstrap(unittest.TestCase):
    """Standalone test for ecology_minimal_core bootstrap."""

    def test_import_and_self_test(self):
        """Verify the module imports and its self-test runs without error."""
        try:
            result = emc.run_self_test()
            self.assertTrue(result, "Self-test returned False")
        except Exception as e:
            self.fail(f"Self-test raised an exception: {e}")

    def test_engine_modifies_file(self):
        """Create a temporary file and verify the engine can modify it."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write("x = 1\n")
            temp_path = f.name

        try:
            # Attempt to run the engine on the temporary file
            engine = emc.EcologyEngine()
            result = engine.process_file(temp_path)
            self.assertIsNotNone(result, "Engine returned None")

            # Read back the file and verify it was modified
            with open(temp_path, 'r') as f:
                content = f.read()
            self.assertNotEqual(content, "x = 1\n", "File was not modified by engine")
        finally:
            os.unlink(temp_path)

    def test_engine_creates_new_file(self):
        """Verify the engine can create a new file from scratch."""
        with tempfile.TemporaryDirectory() as tmpdir:
            new_path = os.path.join(tmpdir, "generated_test.py")
            engine = emc.EcologyEngine()
            result = engine.create_file(new_path, content="initial content")
            self.assertTrue(os.path.exists(new_path), "Engine did not create the file")
            with open(new_path, 'r') as f:
                content = f.read()
            self.assertIn("initial content", content, "Created file content mismatch")


if __name__ == "__main__":
    unittest.main()