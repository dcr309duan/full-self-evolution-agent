import unittest
from unittest.mock import patch, MagicMock
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from meta_mutation_selector import MetaMutationSelector

class TestMetaMutationSelector(unittest.TestCase):
    """Unit tests for MetaMutationSelector."""

    def setUp(self):
        """Set up a mock log and selector instance for testing."""
        self.mock_log = MagicMock()
        self.mock_log.get_recent_outcomes.return_value = ['A', 'B', 'C', 'D'] * 12 + ['A', 'B']  # 50 outcomes
        self.selector = MetaMutationSelector(log=self.mock_log)
        self.selector.mutation_types = ['A', 'B', 'C', 'D']

    def test_parse_last_50_outcomes(self):
        """Test that the selector correctly parses the last 50 outcomes from a mock log."""
        outcomes = self.selector.parse_last_n_outcomes(n=50)
        self.assertEqual(len(outcomes), 50)
        self.assertListEqual(outcomes, ['A', 'B', 'C', 'D'] * 12 + ['A', 'B'])

    def test_decision_forest_trains_without_error(self):
        """Test that the decision forest trains without error on synthetic data."""
        X = np.random.rand(100, 5)
        y = np.random.choice(['A', 'B', 'C', 'D'], size=100)
        self.selector.train_forest(X, y)
        self.assertIsInstance(self.selector.forest, RandomForestClassifier)

    def test_predict_highest_yield_returns_valid_mutation_type(self):
        """Test that predict_highest_yield() returns a valid mutation type."""
        self.selector.forest = RandomForestClassifier()
        X_train = np.random.rand(100, 5)
        y_train = np.random.choice(['A', 'B', 'C', 'D'], size=100)
        self.selector.forest.fit(X_train, y_train)

        X_test = np.random.rand(1, 5)
        predicted = self.selector.predict_highest_yield(X_test)
        self.assertIn(predicted, self.selector.mutation_types)

    def test_bias_injection_changes_probabilities(self):
        """Test that bias injection changes mutation probabilities."""
        original_probs = np.array([0.25, 0.25, 0.25, 0.25])
        self.selector.inject_bias(bias_vector=[0.5, 0.2, 0.2, 0.1])
        biased_probs = self.selector.get_mutation_probabilities()
        self.assertFalse(np.array_equal(original_probs, biased_probs))

    def test_fewer_than_50_outcomes(self):
        """Test handling of fewer than 50 outcomes available."""
        self.mock_log.get_recent_outcomes.return_value = ['A', 'B', 'C'] * 10  # 30 outcomes
        outcomes = self.selector.parse_last_n_outcomes(n=50)
        self.assertEqual(len(outcomes), 30)
        self.assertListEqual(outcomes, ['A', 'B', 'C'] * 10)

    def test_all_same_type_outcomes(self):
        """Test handling when all outcomes are the same type."""
        self.mock_log.get_recent_outcomes.return_value = ['A'] * 50
        outcomes = self.selector.parse_last_n_outcomes(n=50)
        self.assertEqual(len(outcomes), 50)
        self.assertTrue(all(o == 'A' for o in outcomes))

    def test_empty_outcomes(self):
        """Test handling of empty outcomes list."""
        self.mock_log.get_recent_outcomes.return_value = []
        outcomes = self.selector.parse_last_n_outcomes(n=50)
        self.assertEqual(len(outcomes), 0)

    def test_mixed_validity_outcomes(self):
        """Test handling of outcomes with mixed valid/invalid types."""
        self.mock_log.get_recent_outcomes.return_value = ['A', 'B', 'X', 'C', 'D', 'Y'] * 8 + ['A', 'B']
        outcomes = self.selector.parse_last_n_outcomes(n=50)
        self.assertEqual(len(outcomes), 50)
        for outcome in outcomes:
            self.assertIn(outcome, self.selector.mutation_types)

if __name__ == '__main__':
    unittest.main()