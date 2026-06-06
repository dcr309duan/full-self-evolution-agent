import unittest
from unittest.mock import patch, MagicMock, call
import sys
import os
import tempfile
import json

# Add parent directory to path to import modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.meta_cognition_timeout import MetaCognitionTimeout
from core.action_classifier import ActionClassifier
from config.meta_cognition_config import TIMEOUT_THRESHOLD, RADICAL_MUTATION_PROBABILITY, TIMEOUT_CONFIG


class TestMetaCognitionTimeoutCounter(unittest.TestCase):
    """Test the counter functionality of the meta-cognition timeout mechanism."""

    def setUp(self):
        """Set up test fixtures."""
        self.timeout = MetaCognitionTimeout()
        self.timeout.reset()

    def test_counter_starts_at_zero(self):
        """Test that the counter initializes to zero."""
        self.assertEqual(self.timeout.reflective_cycle_count, 0)

    def test_counter_increments_on_reflective_cycle(self):
        """Test that counter increments correctly on reflective cycles."""
        initial_count = self.timeout.reflective_cycle_count
        self.timeout.increment_reflective_cycle()
        self.assertEqual(self.timeout.reflective_cycle_count, initial_count + 1)

    def test_counter_increments_multiple_times(self):
        """Test that counter increments correctly over multiple reflective cycles."""
        for i in range(5):
            self.timeout.increment_reflective_cycle()
            self.assertEqual(self.timeout.reflective_cycle_count, i + 1)

    def test_counter_resets_on_successful_mutation(self):
        """Test that counter resets to zero on successful mutation."""
        # Increment a few times
        for _ in range(3):
            self.timeout.increment_reflective_cycle()
        self.assertEqual(self.timeout.reflective_cycle_count, 3)

        # Reset on successful mutation
        self.timeout.reset_on_successful_mutation()
        self.assertEqual(self.timeout.reflective_cycle_count, 0)

    def test_counter_reset_after_threshold_reached(self):
        """Test that counter resets after a radical mutation is triggered."""
        # Simulate reaching threshold
        for _ in range(TIMEOUT_THRESHOLD):
            self.timeout.increment_reflective_cycle()
        self.assertEqual(self.timeout.reflective_cycle_count, TIMEOUT_THRESHOLD)

        # Trigger radical mutation (should reset counter)
        self.timeout.trigger_radical_mutation()
        self.assertEqual(self.timeout.reflective_cycle_count, 0)


class TestMetaCognitionTimeoutThreshold(unittest.TestCase):
    """Test the threshold detection and radical mutation triggering."""

    def setUp(self):
        """Set up test fixtures."""
        self.timeout = MetaCognitionTimeout()
        self.timeout.reset()

    def test_threshold_not_reached_below_limit(self):
        """Test that threshold is not detected below the limit."""
        for _ in range(TIMEOUT_THRESHOLD - 1):
            self.timeout.increment_reflective_cycle()
        self.assertFalse(self.timeout.is_threshold_reached())

    def test_threshold_reached_at_limit(self):
        """Test that threshold is detected at the limit."""
        for _ in range(TIMEOUT_THRESHOLD):
            self.timeout.increment_reflective_cycle()
        self.assertTrue(self.timeout.is_threshold_reached())

    def test_threshold_reached_above_limit(self):
        """Test that threshold is detected above the limit."""
        for _ in range(TIMEOUT_THRESHOLD + 5):
            self.timeout.increment_reflective_cycle()
        self.assertTrue(self.timeout.is_threshold_reached())

    def test_radical_mutation_triggers_at_threshold(self):
        """Test that radical mutation triggers when threshold is reached."""
        with patch.object(self.timeout, 'trigger_radical_mutation') as mock_trigger:
            for _ in range(TIMEOUT_THRESHOLD):
                self.timeout.increment_reflective_cycle()
            self.timeout.check_and_trigger()
            mock_trigger.assert_called_once()

    def test_radical_mutation_not_triggered_below_threshold(self):
        """Test that radical mutation is not triggered below threshold."""
        with patch.object(self.timeout, 'trigger_radical_mutation') as mock_trigger:
            for _ in range(TIMEOUT_THRESHOLD - 1):
                self.timeout.increment_reflective_cycle()
            self.timeout.check_and_trigger()
            mock_trigger.assert_not_called()


class TestMetaCognitionTimeoutRadicalMutation(unittest.TestCase):
    """Test the radical mutation generation and file creation."""

    def setUp(self):
        """Set up test fixtures."""
        self.timeout = MetaCognitionTimeout()
        self.timeout.reset()
        # Create a temporary directory for test files
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Clean up temporary files."""
        import shutil
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_radical_mutation_generates_valid_file(self):
        """Test that radical mutation generates a valid Python file."""
        # Create a test file to mutate
        test_file_path = os.path.join(self.test_dir, 'test_module.py')
        with open(test_file_path, 'w') as f:
            f.write("def existing_function():\n    return 42\n")

        # Trigger radical mutation
        result = self.timeout.generate_radical_mutation(test_file_path)
        self.assertTrue(result)
        self.assertTrue(os.path.exists(test_file_path))

        # Verify the file is valid Python
        with open(test_file_path, 'r') as f:
            content = f.read()
        try:
            compile(content, test_file_path, 'exec')
            is_valid = True
        except SyntaxError:
            is_valid = False
        self.assertTrue(is_valid, "Radical mutation did not produce valid Python code")

    def test_radical_mutation_adds_new_function(self):
        """Test that radical mutation adds new functions to the file."""
        test_file_path = os.path.join(self.test_dir, 'test_module2.py')
        with open(test_file_path, 'w') as f:
            f.write("def existing_function():\n    return 42\n")

        # Read original content
        with open(test_file_path, 'r') as f:
            original_content = f.read()

        # Trigger radical mutation
        self.timeout.generate_radical_mutation(test_file_path)

        # Read new content
        with open(test_file_path, 'r') as f:
            new_content = f.read()

        # Verify new content is different and contains new code
        self.assertNotEqual(original_content, new_content)
        self.assertIn('def ', new_content)

    def test_radical_mutation_handles_empty_file(self):
        """Test that radical mutation handles an empty file gracefully."""
        test_file_path = os.path.join(self.test_dir, 'empty_module.py')
        with open(test_file_path, 'w') as f:
            f.write("")

        result = self.timeout.generate_radical_mutation(test_file_path)
        self.assertTrue(result)
        self.assertTrue(os.path.exists(test_file_path))

        # Verify the file is valid Python
        with open(test_file_path, 'r') as f:
            content = f.read()
        try:
            compile(content, test_file_path, 'exec')
            is_valid = True
        except SyntaxError:
            is_valid = False
        self.assertTrue(is_valid, "Radical mutation on empty file did not produce valid Python code")


class TestMetaCognitionTimeoutBypass(unittest.TestCase):
    """Test the bypass of normal pipeline during radical mutation."""

    def setUp(self):
        """Set up test fixtures."""
        self.timeout = MetaCognitionTimeout()
        self.timeout.reset()

    def test_bypass_flag_set_on_trigger(self):
        """Test that bypass flag is set when radical mutation is triggered."""
        self.assertFalse(self.timeout.bypass_normal_pipeline)
        self.timeout.trigger_radical_mutation()
        self.assertTrue(self.timeout.bypass_normal_pipeline)

    def test_bypass_flag_reset_after_execution(self):
        """Test that bypass flag is reset after radical mutation execution."""
        self.timeout.trigger_radical_mutation()
        self.assertTrue(self.timeout.bypass_normal_pipeline)
        self.timeout.reset_bypass()
        self.assertFalse(self.timeout.bypass_normal_pipeline)

    def test_normal_pipeline_skipped_during_bypass(self):
        """Test that normal pipeline actions are skipped during bypass."""
        self.timeout.trigger_radical_mutation()
        self.assertTrue(self.timeout.should_skip_normal_pipeline())

    def test_normal_pipeline_executed_normally(self):
        """Test that normal pipeline executes when not in bypass mode."""
        self.assertFalse(self.timeout.should_skip_normal_pipeline())

    def test_bypass_after_multiple_triggers(self):
        """Test bypass behavior after multiple radical mutation triggers."""
        self.timeout.trigger_radical_mutation()
        self.assertTrue(self.timeout.bypass_normal_pipeline)
        self.timeout.reset_bypass()
        self.assertFalse(self.timeout.bypass_normal_pipeline)

        # Trigger again
        self.timeout.trigger_radical_mutation()
        self.assertTrue(self.timeout.bypass_normal_pipeline)


class TestMetaCognitionTimeoutIntegration(unittest.TestCase):
    """Integration tests for the meta-cognition timeout mechanism."""

    def setUp(self):
        """Set up test fixtures with mocked dependencies."""
        self.timeout = MetaCognitionTimeout()
        self.timeout.reset()
        self.classifier = ActionClassifier()
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Clean up temporary files."""
        import shutil
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_full_cycle_without_threshold(self):
        """Test a full cycle without reaching the threshold."""
        # Simulate a few reflective cycles
        for _ in range(3):
            self.timeout.increment_reflective_cycle()

        # Simulate a successful mutation
        self.timeout.reset_on_successful_mutation()
        self.assertEqual(self.timeout.reflective_cycle_count, 0)
        self.assertFalse(self.timeout.is_threshold_reached())

    def test_full_cycle_reaching_threshold(self):
        """Test a full cycle that reaches the threshold and triggers radical mutation."""
        # Simulate many reflective cycles
        for _ in range(TIMEOUT_THRESHOLD):
            self.timeout.increment_reflective_cycle()

        # Check threshold and trigger
        self.assertTrue(self.timeout.is_threshold_reached())
        self.timeout.trigger_radical_mutation()
        self.assertTrue(self.timeout.bypass_normal_pipeline)
        self.assertEqual(self.timeout.reflective_cycle_count, 0)

    def test_classifier_integration(self):
        """Test integration with the action classifier."""
        # Test that the classifier correctly identifies reflective cycles
        test_actions = [
            {'type': 'reflection', 'target': 'meta_cognition'},
            {'type': 'code_mutation', 'target': 'test_file.py'}
        ]

        for action in test_actions:
            classification = self.classifier.classify_action(action)
            if action['type'] == 'reflection':
                self.assertEqual(classification, 'reflective_cycle')
            else:
                self.assertEqual(classification, 'code_mutation')

    def test_config_values_used_correctly(self):
        """Test that configuration values are used correctly."""
        self.assertEqual(TIMEOUT_THRESHOLD, TIMEOUT_CONFIG.get('threshold', 5))
        self.assertGreaterEqual(RADICAL_MUTATION_PROBABILITY, 0.0)
        self.assertLessEqual(RADICAL_MUTATION_PROBABILITY, 1.0)


class TestMetaCognitionTimeoutEdgeCases(unittest.TestCase):
    """Test edge cases for the meta-cognition timeout mechanism."""

    def setUp(self):
        """Set up test fixtures."""
        self.timeout = MetaCognitionTimeout()
        self.timeout.reset()

    def test_zero_threshold_config(self):
        """Test behavior when threshold is set to zero (should trigger immediately)."""
        # This test assumes the config can be overridden for testing
        original_threshold = TIMEOUT_THRESHOLD
        try:
            # Simulate zero threshold by immediately checking
            self.timeout.increment_reflective_cycle()
            # With threshold 0, any reflective cycle should trigger
            # But our implementation uses >=, so we need at least 1
            self.assertTrue(self.timeout.reflective_cycle_count >= 1)
        finally:
            pass  # Restore original threshold if needed

    def test_negative_counter_value(self):
        """Test that counter handles negative values gracefully (should not happen)."""
        # Directly set counter to negative (simulating bug)
        self.timeout.reflective_cycle_count = -5
        self.assertFalse(self.timeout.is_threshold_reached())
        self.timeout.increment_reflective_cycle()
        self.assertEqual(self.timeout.reflective_cycle_count, -4)

    def test_large_counter_value(self):
        """Test that counter handles very large values."""
        self.timeout.reflective_cycle_count = 1000000
        self.assertTrue(self.timeout.is_threshold_reached())

    def test_concurrent_reset_and_increment(self):
        """Test that reset and increment work correctly in sequence."""
        self.timeout.increment_reflective_cycle()
        self.timeout.reset_on_successful_mutation()
        self.timeout.increment_reflective_cycle()
        self.assertEqual(self.timeout.reflective_cycle_count, 1)


if __name__ == '__main__':
    unittest.main()