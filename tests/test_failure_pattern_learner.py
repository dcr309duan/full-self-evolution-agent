import unittest
import json
import os
import tempfile
from unittest.mock import MagicMock, patch
from collections import Counter

# Assuming the module is named 'failure_pattern_learner' and contains
# FailurePatternLearner class and ErrorType enum
from failure_pattern_learner import FailurePatternLearner, ErrorType


class TestFailurePatternLearnerIntegration(unittest.TestCase):
    """Integration tests for FailurePatternLearner with mock mutation engine."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_mutation_engine = MagicMock()
        # Configure mock mutation engine to return specific operators
        self.mock_mutation_engine.get_operators.return_value = [
            'operator_a', 'operator_b', 'operator_c', 'operator_d', 'operator_e'
        ]
        self.learner = FailurePatternLearner(self.mock_mutation_engine)
        # Create a temporary file for persistence testing
        self.temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.json')
        self.temp_file.close()

    def tearDown(self):
        """Clean up test fixtures."""
        if os.path.exists(self.temp_file.name):
            os.unlink(self.temp_file.name)

    def _simulate_failures(self, learner, failure_counts):
        """
        Simulate failures with given counts per error type.
        
        Args:
            learner: FailurePatternLearner instance
            failure_counts: dict mapping ErrorType to count of failures
        """
        for error_type, count in failure_counts.items():
            for _ in range(count):
                # Simulate a failure with a random operator
                operator = self.mock_mutation_engine.get_operators()[0]
                learner.record_failure(operator, error_type)

    def test_initialization(self):
        """Test that the learner initializes correctly with mock engine."""
        self.assertIsNotNone(self.learner)
        self.assertEqual(len(self.learner.operator_stats), 5)
        for op in self.mock_mutation_engine.get_operators():
            self.assertIn(op, self.learner.operator_stats)
            self.assertEqual(self.learner.operator_stats[op]['total'], 0)
            self.assertEqual(self.learner.operator_stats[op]['failures'], 0)

    def test_error_type_classification_accuracy(self):
        """Test that error type classification is accurate after 50 failures."""
        failure_counts = {
            ErrorType.IMPORT_ERROR: 10,
            ErrorType.TYPE_MISMATCH: 15,
            ErrorType.INFINITE_LOOP: 5,
            ErrorType.OTHER: 20
        }
        self._simulate_failures(self.learner, failure_counts)

        # Verify total failures recorded
        total_failures = sum(failure_counts.values())
        self.assertEqual(self.learner.total_failures, total_failures)

        # Verify error type counts
        for error_type, count in failure_counts.items():
            self.assertEqual(
                self.learner.error_type_counts[error_type],
                count,
                f"Error type {error_type} count mismatch"
            )

        # Verify classification accuracy (should be 100% since we're recording directly)
        # In a real system, this would test the classifier, but here we test recording
        for operator in self.mock_mutation_engine.get_operators():
            stats = self.learner.operator_stats[operator]
            # Since we always use operator_a, it should have all failures
            if operator == 'operator_a':
                self.assertEqual(stats['failures'], total_failures)
                self.assertEqual(stats['total'], total_failures)
            else:
                self.assertEqual(stats['failures'], 0)
                self.assertEqual(stats['total'], 0)

    def test_operator_weight_adjustments(self):
        """Test that operator weights are adjusted correctly based on failure rates."""
        # Simulate failures to create specific failure rates
        # operator_a: 100% failure rate (should be disabled)
        # operator_b: 80% failure rate (should be disabled)
        # operator_c: 50% failure rate (should be halved)
        # operator_d: 30% failure rate (should remain unchanged)
        # operator_e: 0% failure rate (should remain unchanged)

        # Record failures for each operator
        for i in range(10):
            self.learner.record_failure('operator_a', ErrorType.OTHER)
        for i in range(8):
            self.learner.record_failure('operator_b', ErrorType.OTHER)
            self.learner.record_success('operator_b')  # 2 successes
        for i in range(5):
            self.learner.record_failure('operator_c', ErrorType.OTHER)
            self.learner.record_success('operator_c')  # 5 successes
        for i in range(3):
            self.learner.record_failure('operator_d', ErrorType.OTHER)
            self.learner.record_success('operator_d')  # 7 successes
        for i in range(10):
            self.learner.record_success('operator_e')  # 0 failures

        # Apply weight adjustments
        self.learner.adjust_weights()

        # Verify operator_a is disabled (failure rate 100% > 70%)
        self.assertEqual(self.learner.operator_weights['operator_a'], 0.0)

        # Verify operator_b is disabled (failure rate 80% > 70%)
        self.assertEqual(self.learner.operator_weights['operator_b'], 0.0)

        # Verify operator_c is halved (failure rate 50% > 40%)
        expected_weight_c = 0.5  # Assuming initial weight is 1.0
        self.assertAlmostEqual(self.learner.operator_weights['operator_c'], expected_weight_c)

        # Verify operator_d remains unchanged (failure rate 30% <= 40%)
        self.assertEqual(self.learner.operator_weights['operator_d'], 1.0)

        # Verify operator_e remains unchanged (failure rate 0% <= 40%)
        self.assertEqual(self.learner.operator_weights['operator_e'], 1.0)

    def test_persistence_to_json(self):
        """Test that learner state is correctly persisted to JSON file."""
        # Simulate some failures
        failure_counts = {
            ErrorType.IMPORT_ERROR: 5,
            ErrorType.TYPE_MISMATCH: 3,
            ErrorType.INFINITE_LOOP: 2,
            ErrorType.OTHER: 4
        }
        self._simulate_failures(self.learner, failure_counts)

        # Persist to JSON file
        self.learner.save_to_file(self.temp_file.name)

        # Verify file exists and is valid JSON
        self.assertTrue(os.path.exists(self.temp_file.name))
        with open(self.temp_file.name, 'r') as f:
            saved_data = json.load(f)

        # Verify key data is present
        self.assertIn('operator_stats', saved_data)
        self.assertIn('error_type_counts', saved_data)
        self.assertIn('total_failures', saved_data)
        self.assertIn('operator_weights', saved_data)

        # Verify data integrity
        self.assertEqual(saved_data['total_failures'], sum(failure_counts.values()))
        for error_type, count in failure_counts.items():
            self.assertEqual(
                saved_data['error_type_counts'][error_type.name],
                count
            )

    def test_reload_from_persisted_state(self):
        """Test that reloading from persisted state restores correct weights."""
        # Simulate failures with specific patterns
        for i in range(10):
            self.learner.record_failure('operator_a', ErrorType.OTHER)
        for i in range(5):
            self.learner.record_failure('operator_b', ErrorType.OTHER)
            self.learner.record_success('operator_b')

        # Save state
        self.learner.save_to_file(self.temp_file.name)

        # Create a new learner instance and load from file
        new_learner = FailurePatternLearner(self.mock_mutation_engine)
        new_learner.load_from_file(self.temp_file.name)

        # Verify operator stats are restored
        self.assertEqual(
            new_learner.operator_stats['operator_a']['failures'],
            self.learner.operator_stats['operator_a']['failures']
        )
        self.assertEqual(
            new_learner.operator_stats['operator_b']['total'],
            self.learner.operator_stats['operator_b']['total']
        )

        # Verify error type counts are restored
        for error_type in ErrorType:
            self.assertEqual(
                new_learner.error_type_counts[error_type],
                self.learner.error_type_counts[error_type]
            )

        # Verify weights are restored (should be same as before adjustment)
        # Note: We didn't call adjust_weights, so weights should be initial values
        for operator in self.mock_mutation_engine.get_operators():
            self.assertEqual(
                new_learner.operator_weights[operator],
                self.learner.operator_weights[operator]
            )

        # Now test that adjust_weights works correctly on loaded data
        new_learner.adjust_weights()
        # operator_a should be disabled (100% failure rate)
        self.assertEqual(new_learner.operator_weights['operator_a'], 0.0)
        # operator_b should be halved (50% failure rate > 40%)
        self.assertAlmostEqual(new_learner.operator_weights['operator_b'], 0.5)

    def test_invalid_file_handling(self):
        """Test that loading from non-existent file raises appropriate error."""
        with self.assertRaises(FileNotFoundError):
            self.learner.load_from_file('/nonexistent/path.json')


if __name__ == '__main__':
    unittest.main()