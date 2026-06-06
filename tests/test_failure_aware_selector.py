import unittest
import numpy as np
from unittest.mock import MagicMock, patch

# Import the module under test
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from core.failure_aware_selector import FailureAwareSelector, FeatureVectorExtractor

class TestFailureAwareSelector(unittest.TestCase):
    """Comprehensive tests for the FailureAwareSelector class."""

    def setUp(self):
        """Set up test fixtures."""
        self.selector = FailureAwareSelector()
        self.extractor = FeatureVectorExtractor()

    def test_classifier_trains_on_sample_failure_data(self):
        """Test that the classifier trains correctly on sample failure data."""
        # Create sample training data with failures and successes
        X_train = [
            {'complexity': 0.8, 'size': 100, 'depth': 5, 'num_params': 3, 'has_loops': True},
            {'complexity': 0.2, 'size': 20, 'depth': 1, 'num_params': 1, 'has_loops': False},
            {'complexity': 0.6, 'size': 50, 'depth': 3, 'num_params': 2, 'has_loops': True},
        ]
        y_train = [0, 1, 0]  # 0 = failure, 1 = success

        # Train the classifier
        self.selector.train(X_train, y_train)

        # Verify the classifier is trained
        self.assertIsNotNone(self.selector.classifier)
        self.assertTrue(hasattr(self.selector.classifier, 'predict_proba'))

    def test_predict_success_returns_float_between_0_and_1(self):
        """Test that predict_success returns a float between 0 and 1."""
        # Train with sample data first
        X_train = [
            {'complexity': 0.8, 'size': 100, 'depth': 5, 'num_params': 3, 'has_loops': True},
            {'complexity': 0.2, 'size': 20, 'depth': 1, 'num_params': 1, 'has_loops': False},
        ]
        y_train = [0, 1]
        self.selector.train(X_train, y_train)

        # Test prediction
        test_mutation = {'complexity': 0.5, 'size': 60, 'depth': 3, 'num_params': 2, 'has_loops': False}
        prediction = self.selector.predict_success(test_mutation)

        # Verify prediction is a float between 0 and 1
        self.assertIsInstance(prediction, float)
        self.assertGreaterEqual(prediction, 0.0)
        self.assertLessEqual(prediction, 1.0)

    def test_threshold_rejection_works_correctly(self):
        """Test that threshold-based rejection works correctly."""
        # Set a specific threshold
        self.selector.threshold = 0.5

        # Mock the predict_success method to return controlled values
        with patch.object(self.selector, 'predict_success') as mock_predict:
            # Test rejection when prediction is below threshold
            mock_predict.return_value = 0.3
            result = self.selector.should_reject({'test': 'mutation'})
            self.assertTrue(result)

            # Test acceptance when prediction is above threshold
            mock_predict.return_value = 0.7
            result = self.selector.should_reject({'test': 'mutation'})
            self.assertFalse(result)

            # Test boundary at threshold
            mock_predict.return_value = 0.5
            result = self.selector.should_reject({'test': 'mutation'})
            self.assertFalse(result)  # Should accept at threshold

    def test_feature_vector_extraction_with_mock_mutation_context(self):
        """Test feature vector extraction with a mock mutation context."""
        # Create a mock mutation context
        mock_context = {
            'mutation': {
                'complexity': 0.7,
                'size': 150,
                'depth': 4,
                'num_params': 2,
                'has_loops': True
            },
            'parent_fitness': 0.85,
            'generation': 10,
            'mutation_type': 'gaussian'
        }

        # Extract features
        features = self.extractor.extract(mock_context)

        # Verify the feature vector has the expected structure
        self.assertIsInstance(features, dict)
        self.assertIn('complexity', features)
        self.assertIn('size', features)
        self.assertIn('depth', features)
        self.assertIn('num_params', features)
        self.assertIn('has_loops', features)

        # Verify feature values
        self.assertEqual(features['complexity'], 0.7)
        self.assertEqual(features['size'], 150)
        self.assertEqual(features['depth'], 4)
        self.assertEqual(features['num_params'], 2)
        self.assertTrue(features['has_loops'])

    def test_empty_training_data(self):
        """Test edge case: empty training data."""
        # Attempt to train with empty data
        with self.assertRaises(ValueError):
            self.selector.train([], [])

        # Verify no classifier was set
        self.assertIsNone(self.selector.classifier)

    def test_single_class_training_data(self):
        """Test edge case: training data with only one class."""
        # Create training data with only successes
        X_train = [
            {'complexity': 0.3, 'size': 30, 'depth': 2, 'num_params': 1, 'has_loops': False},
            {'complexity': 0.4, 'size': 40, 'depth': 2, 'num_params': 2, 'has_loops': False},
        ]
        y_train = [1, 1]  # All successes

        # Train the classifier
        self.selector.train(X_train, y_train)

        # Verify classifier is trained (should handle single class gracefully)
        self.assertIsNotNone(self.selector.classifier)

        # Test prediction on single class data
        test_mutation = {'complexity': 0.5, 'size': 50, 'depth': 3, 'num_params': 2, 'has_loops': True}
        prediction = self.selector.predict_success(test_mutation)
        self.assertIsInstance(prediction, float)
        self.assertGreaterEqual(prediction, 0.0)
        self.assertLessEqual(prediction, 1.0)

    def test_all_successes_training_data(self):
        """Test edge case: training data with all successes."""
        # Create training data with only successes
        X_train = [
            {'complexity': 0.1, 'size': 10, 'depth': 1, 'num_params': 1, 'has_loops': False},
            {'complexity': 0.2, 'size': 20, 'depth': 1, 'num_params': 1, 'has_loops': False},
            {'complexity': 0.3, 'size': 30, 'depth': 2, 'num_params': 2, 'has_loops': False},
        ]
        y_train = [1, 1, 1]  # All successes

        # Train the classifier
        self.selector.train(X_train, y_train)

        # Verify classifier is trained
        self.assertIsNotNone(self.selector.classifier)

        # Test prediction - should predict high success probability
        test_mutation = {'complexity': 0.5, 'size': 50, 'depth': 3, 'num_params': 2, 'has_loops': True}
        prediction = self.selector.predict_success(test_mutation)
        self.assertGreater(prediction, 0.5)  # Should predict success

    def test_feature_vector_extraction_missing_fields(self):
        """Test feature extraction with missing fields in context."""
        # Create a context with missing fields
        incomplete_context = {
            'mutation': {
                'complexity': 0.5,
                # Missing 'size', 'depth', 'num_params', 'has_loops'
            }
        }

        # Extract features - should handle missing fields gracefully
        features = self.extractor.extract(incomplete_context)

        # Verify default values are used for missing fields
        self.assertEqual(features['complexity'], 0.5)
        self.assertEqual(features['size'], 0)  # Default value
        self.assertEqual(features['depth'], 0)  # Default value
        self.assertEqual(features['num_params'], 0)  # Default value
        self.assertFalse(features['has_loops'])  # Default value

    def test_selector_update_with_new_data(self):
        """Test that the selector can be updated with new training data."""
        # Initial training
        X_initial = [
            {'complexity': 0.8, 'size': 100, 'depth': 5, 'num_params': 3, 'has_loops': True},
            {'complexity': 0.2, 'size': 20, 'depth': 1, 'num_params': 1, 'has_loops': False},
        ]
        y_initial = [0, 1]
        self.selector.train(X_initial, y_initial)

        # Get initial prediction
        test_mutation = {'complexity': 0.5, 'size': 60, 'depth': 3, 'num_params': 2, 'has_loops': False}
        initial_prediction = self.selector.predict_success(test_mutation)

        # Update with new data
        X_new = [
            {'complexity': 0.6, 'size': 80, 'depth': 4, 'num_params': 2, 'has_loops': True},
            {'complexity': 0.4, 'size': 40, 'depth': 2, 'num_params': 1, 'has_loops': False},
        ]
        y_new = [0, 1]
        self.selector.update(X_new, y_new)

        # Get updated prediction
        updated_prediction = self.selector.predict_success(test_mutation)

        # Verify the prediction changed after update
        self.assertNotEqual(initial_prediction, updated_prediction)

    def test_selector_reset(self):
        """Test that the selector can be reset to initial state."""
        # Train the selector
        X_train = [
            {'complexity': 0.8, 'size': 100, 'depth': 5, 'num_params': 3, 'has_loops': True},
            {'complexity': 0.2, 'size': 20, 'depth': 1, 'num_params': 1, 'has_loops': False},
        ]
        y_train = [0, 1]
        self.selector.train(X_train, y_train)

        # Verify it's trained
        self.assertIsNotNone(self.selector.classifier)

        # Reset the selector
        self.selector.reset()

        # Verify it's back to initial state
        self.assertIsNone(self.selector.classifier)
        self.assertEqual(len(self.selector.training_data), 0)

if __name__ == '__main__':
    unittest.main()