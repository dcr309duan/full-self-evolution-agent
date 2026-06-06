import unittest
import tempfile
import os
import json
from unittest.mock import patch, MagicMock

# Adjust imports based on your project structure
from core.failure_memory import FailureMemory
from core.prompt_mutation_engine import PromptMutationEngine


class TestFailureMemory(unittest.TestCase):
    """Comprehensive tests for FailureMemory module."""

    def setUp(self):
        # Create a temporary directory for persistence tests
        self.temp_dir = tempfile.mkdtemp()
        self.memory_path = os.path.join(self.temp_dir, "failure_memory.json")
        self.memory = FailureMemory(memory_path=self.memory_path, window_size=5)

    def tearDown(self):
        # Clean up temporary directory
        for root, dirs, files in os.walk(self.temp_dir, topdown=False):
            for name in files:
                os.remove(os.path.join(root, name))
            for name in dirs:
                os.rmdir(os.path.join(root, name))
        os.rmdir(self.temp_dir)

    def test_record_failure_different_error_types(self):
        """Test recording failures with different error types."""
        error_types = ["SyntaxError", "TypeError", "ValueError", "RuntimeError", "ImportError"]
        for error_type in error_types:
            self.memory.record_failure(
                error_type=error_type,
                error_message=f"Test {error_type} occurred",
                context={"test": True}
            )
        lessons = self.memory.get_lessons()
        self.assertEqual(len(lessons), 5)
        recorded_types = [lesson["error_type"] for lesson in lessons]
        for error_type in error_types:
            self.assertIn(error_type, recorded_types)

    def test_get_lessons_returns_only_recent_entries_within_window(self):
        """Test that get_lessons() returns only recent entries within window."""
        # Record 10 failures (window size is 5)
        for i in range(10):
            self.memory.record_failure(
                error_type="TestError",
                error_message=f"Failure {i}",
                context={"index": i}
            )
        lessons = self.memory.get_lessons()
        self.assertEqual(len(lessons), 5)
        # The last 5 should be indices 5-9
        indices = [lesson["context"]["index"] for lesson in lessons]
        self.assertEqual(indices, [5, 6, 7, 8, 9])

    def test_persistence_across_reloads(self):
        """Test that failures persist across reloads of FailureMemory."""
        # Record some failures
        self.memory.record_failure(
            error_type="SyntaxError",
            error_message="Syntax error in code",
            context={"file": "test.py"}
        )
        self.memory.record_failure(
            error_type="TypeError",
            error_message="Type mismatch",
            context={"variable": "x"}
        )
        # Create a new instance pointing to the same file
        memory2 = FailureMemory(memory_path=self.memory_path, window_size=5)
        lessons = memory2.get_lessons()
        self.assertEqual(len(lessons), 2)
        self.assertEqual(lessons[0]["error_type"], "SyntaxError")
        self.assertEqual(lessons[1]["error_type"], "TypeError")

    def test_clear_old_entries_removes_beyond_window(self):
        """Test that clear_old_entries() removes entries beyond the window."""
        # Record 10 failures
        for i in range(10):
            self.memory.record_failure(
                error_type="TestError",
                error_message=f"Failure {i}",
                context={"index": i}
            )
        # Manually call clear_old_entries (should be called automatically, but test explicitly)
        self.memory.clear_old_entries()
        lessons = self.memory.get_lessons()
        self.assertEqual(len(lessons), 5)
        # Verify only the last 5 remain
        indices = [lesson["context"]["index"] for lesson in lessons]
        self.assertEqual(indices, [5, 6, 7, 8, 9])

    def test_integration_with_prompt_mutation_engine(self):
        """Test integration with prompt_mutation_engine to verify lessons appear in prompts."""
        # Record some failures
        self.memory.record_failure(
            error_type="SyntaxError",
            error_message="Missing closing parenthesis",
            context={"code_snippet": "def foo(x:"}
        )
        self.memory.record_failure(
            error_type="TypeError",
            error_message="Cannot concatenate str and int",
            context={"operation": "str + int"}
        )
        # Create a PromptMutationEngine instance with this memory
        engine = PromptMutationEngine(failure_memory=self.memory)
        # Generate a prompt
        prompt = engine.generate_prompt(base_prompt="Write a function that adds two numbers.")
        # Check that lessons are included in the prompt
        self.assertIn("Missing closing parenthesis", prompt)
        self.assertIn("Cannot concatenate str and int", prompt)
        self.assertIn("SyntaxError", prompt)
        self.assertIn("TypeError", prompt)

    def test_empty_memory_returns_empty_lessons(self):
        """Test that an empty memory returns an empty list of lessons."""
        lessons = self.memory.get_lessons()
        self.assertEqual(lessons, [])

    def test_record_failure_without_context(self):
        """Test recording a failure without optional context."""
        self.memory.record_failure(
            error_type="RuntimeError",
            error_message="Something went wrong"
        )
        lessons = self.memory.get_lessons()
        self.assertEqual(len(lessons), 1)
        self.assertEqual(lessons[0]["error_type"], "RuntimeError")
        self.assertEqual(lessons[0]["error_message"], "Something went wrong")
        self.assertNotIn("context", lessons[0])

    def test_window_size_respected_after_clear(self):
        """Test that window size is respected after clearing old entries."""
        # Record exactly window_size + 1 failures
        for i in range(6):
            self.memory.record_failure(
                error_type="TestError",
                error_message=f"Failure {i}",
                context={"index": i}
            )
        self.memory.clear_old_entries()
        lessons = self.memory.get_lessons()
        self.assertEqual(len(lessons), 5)
        indices = [lesson["context"]["index"] for lesson in lessons]
        self.assertEqual(indices, [1, 2, 3, 4, 5])

    def test_multiple_records_same_error_type(self):
        """Test recording multiple failures of the same error type."""
        for i in range(3):
            self.memory.record_failure(
                error_type="SyntaxError",
                error_message=f"Syntax error {i}",
                context={"attempt": i}
            )
        lessons = self.memory.get_lessons()
        self.assertEqual(len(lessons), 3)
        messages = [lesson["error_message"] for lesson in lessons]
        self.assertIn("Syntax error 0", messages)
        self.assertIn("Syntax error 1", messages)
        self.assertIn("Syntax error 2", messages)


if __name__ == "__main__":
    unittest.main()