import unittest
from unittest.mock import Mock, patch
import pandas as pd
from datetime import datetime, timedelta
from collections import Counter

# Assuming the module to be tested is 'failure_miner' in the parent directory
import sys
sys.path.insert(0, '..')
from failure_miner import FailurePatternMiner, FailureLog, Pattern, Bottleneck, RefactoringGoal

class TestFailurePatternMiner(unittest.TestCase):
    """Test suite for the FailurePatternMiner class."""

    def setUp(self):
        """Set up test fixtures."""
        self.miner = FailurePatternMiner()
        
        # Sample failure logs for testing
        self.sample_logs = [
            FailureLog(
                timestamp=datetime(2024, 1, 1, 10, 0, 0),
                component="auth_service",
                message="Connection timeout to database",
                severity="ERROR",
                stack_trace="Error: Connection timeout\n  at db.connect()"
            ),
            FailureLog(
                timestamp=datetime(2024, 1, 1, 10, 5, 0),
                component="auth_service",
                message="Connection timeout to database",
                severity="ERROR",
                stack_trace="Error: Connection timeout\n  at db.connect()"
            ),
            FailureLog(
                timestamp=datetime(2024, 1, 1, 10, 10, 0),
                component="api_gateway",
                message="Rate limit exceeded for user 123",
                severity="WARNING",
                stack_trace="Warning: Rate limit\n  at rate_limiter.check()"
            ),
            FailureLog(
                timestamp=datetime(2024, 1, 1, 10, 15, 0),
                component="auth_service",
                message="Connection timeout to database",
                severity="ERROR",
                stack_trace="Error: Connection timeout\n  at db.connect()"
            ),
            FailureLog(
                timestamp=datetime(2024, 1, 1, 10, 20, 0),
                component="payment_service",
                message="Invalid payment amount: -50.00",
                severity="ERROR",
                stack_trace="Error: Invalid amount\n  at payment.validate()"
            ),
        ]

    def test_aggregate_multiple_failure_logs(self):
        """Test aggregation of multiple failure logs into patterns."""
        # Act
        aggregated = self.miner.aggregate_logs(self.sample_logs)
        
        # Assert
        self.assertIsInstance(aggregated, dict)
        self.assertIn("auth_service", aggregated)
        self.assertIn("api_gateway", aggregated)
        self.assertIn("payment_service", aggregated)
        
        # Check that auth_service has 3 occurrences of the same pattern
        auth_patterns = aggregated["auth_service"]
        self.assertEqual(len(auth_patterns), 1)  # Only one unique pattern
        pattern = auth_patterns[0]
        self.assertEqual(pattern.count, 3)
        self.assertEqual(pattern.message, "Connection timeout to database")
        
        # Check other services have correct counts
        self.assertEqual(len(aggregated["api_gateway"]), 1)
        self.assertEqual(aggregated["api_gateway"][0].count, 1)
        self.assertEqual(len(aggregated["payment_service"]), 1)
        self.assertEqual(aggregated["payment_service"][0].count, 1)

    def test_pattern_extraction_with_known_failure_messages(self):
        """Test pattern extraction with known failure messages."""
        # Arrange
        known_messages = [
            "Connection timeout to database",
            "Rate limit exceeded for user 123",
            "Invalid payment amount: -50.00"
        ]
        
        # Act
        patterns = self.miner.extract_patterns(self.sample_logs)
        
        # Assert
        self.assertEqual(len(patterns), 3)
        
        # Check each pattern has correct attributes
        pattern_messages = [p.message for p in patterns]
        for msg in known_messages:
            self.assertIn(msg, pattern_messages)
        
        # Verify pattern details
        timeout_pattern = [p for p in patterns if "timeout" in p.message][0]
        self.assertEqual(timeout_pattern.component, "auth_service")
        self.assertEqual(timeout_pattern.severity, "ERROR")
        self.assertTrue(timeout_pattern.is_recurring)
        
        # Check rate limit pattern
        rate_pattern = [p for p in patterns if "Rate limit" in p.message][0]
        self.assertEqual(rate_pattern.component, "api_gateway")
        self.assertEqual(rate_pattern.severity, "WARNING")
        
        # Check payment pattern
        payment_pattern = [p for p in patterns if "payment" in p.message][0]
        self.assertEqual(payment_pattern.component, "payment_service")
        self.assertEqual(payment_pattern.severity, "ERROR")

    def test_statistics_computation(self):
        """Test computation of statistics from failure patterns."""
        # Arrange
        patterns = self.miner.extract_patterns(self.sample_logs)
        
        # Act
        stats = self.miner.compute_statistics(patterns)
        
        # Assert
        self.assertIsInstance(stats, dict)
        
        # Check total failures
        self.assertEqual(stats["total_failures"], 5)
        
        # Check failure rate (assuming 20 minute window)
        expected_rate = 5 / (20 * 60)  # 5 failures per 20 minutes
        self.assertAlmostEqual(stats["failure_rate"], expected_rate, places=4)
        
        # Check most frequent component
        self.assertEqual(stats["most_frequent_component"], "auth_service")
        
        # Check severity distribution
        self.assertEqual(stats["severity_distribution"]["ERROR"], 4)
        self.assertEqual(stats["severity_distribution"]["WARNING"], 1)
        
        # Check pattern frequency
        self.assertEqual(stats["pattern_frequency"]["Connection timeout to database"], 3)
        self.assertEqual(stats["pattern_frequency"]["Rate limit exceeded for user 123"], 1)
        self.assertEqual(stats["pattern_frequency"]["Invalid payment amount: -50.00"], 1)

    def test_bottleneck_identification_using_mock_self_model(self):
        """Test bottleneck identification using a mock self-model."""
        # Arrange
        # Create a mock self-model that returns predefined bottleneck scores
        mock_self_model = Mock()
        mock_self_model.identify_bottlenecks.return_value = [
            Bottleneck(
                component="auth_service",
                severity_score=0.9,
                impact_score=0.8,
                frequency_score=0.7,
                recommendation="Optimize database connection pooling"
            ),
            Bottleneck(
                component="payment_service",
                severity_score=0.6,
                impact_score=0.5,
                frequency_score=0.3,
                recommendation="Add input validation for payment amounts"
            )
        ]
        
        # Replace the miner's self-model with the mock
        self.miner.self_model = mock_self_model
        
        patterns = self.miner.extract_patterns(self.sample_logs)
        
        # Act
        bottlenecks = self.miner.identify_bottlenecks(patterns)
        
        # Assert
        self.assertEqual(len(bottlenecks), 2)
        
        # Check auth_service bottleneck
        auth_bottleneck = [b for b in bottlenecks if b.component == "auth_service"][0]
        self.assertEqual(auth_bottleneck.severity_score, 0.9)
        self.assertEqual(auth_bottleneck.impact_score, 0.8)
        self.assertEqual(auth_bottleneck.frequency_score, 0.7)
        self.assertIn("database", auth_bottleneck.recommendation.lower())
        
        # Check payment_service bottleneck
        payment_bottleneck = [b for b in bottlenecks if b.component == "payment_service"][0]
        self.assertEqual(payment_bottleneck.severity_score, 0.6)
        self.assertIn("validation", payment_bottleneck.recommendation.lower())
        
        # Verify mock was called correctly
        mock_self_model.identify_bottlenecks.assert_called_once_with(patterns)

    def test_refactoring_goal_generation_for_simulated_pattern(self):
        """Test refactoring goal generation for a simulated pattern."""
        # Arrange
        simulated_pattern = Pattern(
            component="auth_service",
            message="Connection timeout to database",
            severity="ERROR",
            count=10,
            first_occurrence=datetime(2024, 1, 1, 10, 0, 0),
            last_occurrence=datetime(2024, 1, 1, 10, 30, 0),
            stack_trace="Error: Connection timeout\n  at db.connect()"
        )
        
        # Act
        goals = self.miner.generate_refactoring_goals([simulated_pattern])
        
        # Assert
        self.assertIsInstance(goals, list)
        self.assertGreater(len(goals), 0)
        
        # Check goal structure
        goal = goals[0]
        self.assertIsInstance(goal, RefactoringGoal)
        self.assertEqual(goal.component, "auth_service")
        self.assertIsNotNone(goal.description)
        self.assertIsNotNone(goal.priority)
        self.assertIsNotNone(goal.estimated_effort)
        
        # Verify goal content
        self.assertIn("database", goal.description.lower())
        self.assertIn("timeout", goal.description.lower())
        self.assertTrue(0 <= goal.priority <= 1)
        self.assertIsInstance(goal.estimated_effort, (int, float))
        self.assertGreater(goal.estimated_effort, 0)
        
        # Check that multiple goals can be generated
        if len(goals) > 1:
            second_goal = goals[1]
            self.assertNotEqual(goal.description, second_goal.description)

    def test_empty_logs_handling(self):
        """Test handling of empty failure logs."""
        # Act
        patterns = self.miner.extract_patterns([])
        stats = self.miner.compute_statistics(patterns)
        bottlenecks = self.miner.identify_bottlenecks(patterns)
        goals = self.miner.generate_refactoring_goals(patterns)
        
        # Assert
        self.assertEqual(len(patterns), 0)
        self.assertEqual(stats["total_failures"], 0)
        self.assertEqual(len(bottlenecks), 0)
        self.assertEqual(len(goals), 0)

    def test_single_log_handling(self):
        """Test handling of a single failure log."""
        # Arrange
        single_log = [FailureLog(
            timestamp=datetime(2024, 1, 1, 10, 0, 0),
            component="test_service",
            message="Test failure message",
            severity="ERROR",
            stack_trace="Error: Test\n  at test.function()"
        )]
        
        # Act
        patterns = self.miner.extract_patterns(single_log)
        stats = self.miner.compute_statistics(patterns)
        
        # Assert
        self.assertEqual(len(patterns), 1)
        self.assertEqual(patterns[0].count, 1)
        self.assertEqual(stats["total_failures"], 1)
        self.assertEqual(stats["most_frequent_component"], "test_service")

if __name__ == '__main__':
    unittest.main()