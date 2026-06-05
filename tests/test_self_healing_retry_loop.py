import unittest
from unittest.mock import Mock, patch, MagicMock
from self_healing_retry_loop import SelfHealingRetryLoop
from failure_analysis import FailureAnalyzer
from goal_generation import GoalGenerator

class TestSelfHealingRetryLoop(unittest.TestCase):
    def setUp(self):
        self.mock_failure_analyzer = Mock(spec=FailureAnalyzer)
        self.mock_goal_generator = Mock(spec=GoalGenerator)
        self.retry_loop = SelfHealingRetryLoop(
            failure_analyzer=self.mock_failure_analyzer,
            goal_generator=self.mock_goal_generator,
            max_retries=3
        )

    def test_failed_goal_triggers_sub_goal_generation(self):
        """Test that a failed goal triggers sub-goal generation."""
        # Arrange
        original_goal = "Complete project report"
        failure_context = {"error": "Missing data", "timestamp": "2024-01-01"}
        self.mock_failure_analyzer.analyze_failure.return_value = {
            "root_cause": "data_missing",
            "severity": "high"
        }
        self.mock_goal_generator.generate_sub_goal.return_value = "Gather missing data from source"

        # Act
        result = self.retry_loop.execute_with_retry(original_goal, failure_context)

        # Assert
        self.mock_failure_analyzer.analyze_failure.assert_called_once_with(failure_context)
        self.mock_goal_generator.generate_sub_goal.assert_called_once_with(
            original_goal, 
            self.mock_failure_analyzer.analyze_failure.return_value
        )
        self.assertIsNotNone(result)

    def test_sub_goals_different_from_original_approach(self):
        """Test that sub-goals are different from the original approach."""
        # Arrange
        original_goal = "Send email to client"
        failure_context = {"error": "SMTP connection failed"}
        
        # Mock different sub-goals on each call
        self.mock_failure_analyzer.analyze_failure.return_value = {
            "root_cause": "network_issue",
            "severity": "medium"
        }
        self.mock_goal_generator.generate_sub_goal.side_effect = [
            "Use alternative SMTP server",
            "Queue email for later delivery",
            "Send via API instead"
        ]

        # Act
        sub_goals = []
        for _ in range(3):
            result = self.retry_loop.execute_with_retry(original_goal, failure_context)
            if result and result.get('sub_goal'):
                sub_goals.append(result['sub_goal'])

        # Assert - each sub-goal should be different from original and from each other
        for sg in sub_goals:
            self.assertNotEqual(sg, original_goal)
        self.assertEqual(len(set(sub_goals)), len(sub_goals), "Sub-goals should be unique")

    def test_three_retry_limit_enforced(self):
        """Test that the 3-retry limit is enforced."""
        # Arrange
        original_goal = "Process payment"
        failure_context = {"error": "Payment gateway timeout"}
        
        self.mock_failure_analyzer.analyze_failure.return_value = {
            "root_cause": "gateway_timeout",
            "severity": "high"
        }
        self.mock_goal_generator.generate_sub_goal.return_value = "Retry payment with delay"

        # Act
        result = self.retry_loop.execute_with_retry(original_goal, failure_context)

        # Assert
        self.assertEqual(self.mock_goal_generator.generate_sub_goal.call_count, 3)
        self.assertIsNotNone(result)
        self.assertTrue(result.get('max_retries_reached', False))

    def test_different_failure_patterns_separate_counters(self):
        """Test that different failure patterns have separate retry counters."""
        # Arrange
        goal = "Update database"
        failure_pattern_a = {"error": "Connection timeout", "pattern": "timeout"}
        failure_pattern_b = {"error": "Duplicate entry", "pattern": "duplicate"}
        
        self.mock_failure_analyzer.analyze_failure.side_effect = lambda ctx: {
            "root_cause": ctx.get("pattern", "unknown"),
            "severity": "medium"
        }
        self.mock_goal_generator.generate_sub_goal.return_value = "Alternative approach"

        # Act - fail with pattern A three times
        for _ in range(3):
            self.retry_loop.execute_with_retry(goal, failure_pattern_a)
        
        # Then fail with pattern B once
        result_b = self.retry_loop.execute_with_retry(goal, failure_pattern_b)

        # Assert - pattern B should still have retries available
        self.assertFalse(result_b.get('max_retries_reached', False))
        self.assertEqual(self.mock_goal_generator.generate_sub_goal.call_count, 4)

    def test_integration_with_failure_analysis_module(self):
        """Test integration with the failure analysis module."""
        # Arrange
        original_goal = "Deploy application"
        failure_context = {
            "error": "Build failed",
            "log": "Error: dependency not found",
            "stack_trace": "at build.py:42"
        }
        
        # Mock the failure analyzer to return detailed analysis
        expected_analysis = {
            "root_cause": "missing_dependency",
            "severity": "critical",
            "affected_components": ["build_system", "package_manager"],
            "recommended_action": "Update package.json"
        }
        self.mock_failure_analyzer.analyze_failure.return_value = expected_analysis
        self.mock_goal_generator.generate_sub_goal.return_value = "Fix dependency and rebuild"

        # Act
        result = self.retry_loop.execute_with_retry(original_goal, failure_context)

        # Assert
        self.mock_failure_analyzer.analyze_failure.assert_called_with(failure_context)
        self.assertEqual(result.get('analysis'), expected_analysis)
        self.assertEqual(result.get('sub_goal'), "Fix dependency and rebuild")

    def test_successful_retry_resets_counter_for_pattern(self):
        """Test that successful retries reset the counter for that pattern."""
        # Arrange
        goal = "Send notification"
        failure_context = {"error": "Service unavailable", "pattern": "service_down"}
        
        self.mock_failure_analyzer.analyze_failure.return_value = {
            "root_cause": "service_down",
            "severity": "high"
        }
        
        # First two attempts fail, third succeeds
        self.mock_goal_generator.generate_sub_goal.side_effect = [
            "Use backup service",
            "Retry with delay",
            "Notification sent successfully"  # This one succeeds
        ]

        # Act - fail twice, succeed on third
        for i in range(2):
            self.retry_loop.execute_with_retry(goal, failure_context)
        
        # Third attempt succeeds
        result = self.retry_loop.execute_with_retry(goal, failure_context)
        
        # Now simulate a new failure for the same pattern
        self.mock_goal_generator.generate_sub_goal.side_effect = [
            "Alternative notification method",
            "Queue for later"
        ]
        new_failure_context = {"error": "Service unavailable again", "pattern": "service_down"}
        new_result = self.retry_loop.execute_with_retry(goal, new_failure_context)

        # Assert - counter should be reset, so we should have retries available
        self.assertFalse(new_result.get('max_retries_reached', False))
        self.assertEqual(self.mock_goal_generator.generate_sub_goal.call_count, 5)  # 3 + 2

    def test_empty_failure_context(self):
        """Test edge case with empty failure context."""
        # Arrange
        original_goal = "Simple task"
        empty_context = {}
        
        self.mock_failure_analyzer.analyze_failure.return_value = {
            "root_cause": "unknown",
            "severity": "low"
        }
        self.mock_goal_generator.generate_sub_goal.return_value = "Retry with default settings"

        # Act
        result = self.retry_loop.execute_with_retry(original_goal, empty_context)

        # Assert
        self.assertIsNotNone(result)
        self.mock_failure_analyzer.analyze_failure.assert_called_with(empty_context)

    def test_malformed_input(self):
        """Test edge case with malformed input."""
        # Arrange
        invalid_goals = [None, 123, [], {"invalid": "type"}, ""]
        
        for invalid_goal in invalid_goals:
            with self.subTest(goal=invalid_goal):
                # Act & Assert
                with self.assertRaises((ValueError, TypeError)):
                    self.retry_loop.execute_with_retry(invalid_goal, {"error": "test"})

    def test_malformed_failure_context(self):
        """Test edge case with malformed failure context."""
        # Arrange
        original_goal = "Test goal"
        invalid_contexts = [None, "string", 123, ["list"]]
        
        for invalid_context in invalid_contexts:
            with self.subTest(context=invalid_context):
                # Act & Assert
                with self.assertRaises((ValueError, TypeError)):
                    self.retry_loop.execute_with_retry(original_goal, invalid_context)

    def test_retry_counter_reset_after_success(self):
        """Test that retry counter resets after a successful execution."""
        # Arrange
        goal = "Complete task"
        failure_context = {"error": "Temporary failure", "pattern": "temp_failure"}
        
        self.mock_failure_analyzer.analyze_failure.return_value = {
            "root_cause": "temp_failure",
            "severity": "low"
        }
        
        # First two calls return sub-goals (failures), third returns success
        self.mock_goal_generator.generate_sub_goal.side_effect = [
            "Retry approach 1",
            "Retry approach 2",
            "Success"  # This indicates success
        ]

        # Act - two failures then success
        self.retry_loop.execute_with_retry(goal, failure_context)
        self.retry_loop.execute_with_retry(goal, failure_context)
        success_result = self.retry_loop.execute_with_retry(goal, failure_context)
        
        # Now test with same pattern again
        self.mock_goal_generator.generate_sub_goal.side_effect = [
            "New retry approach"
        ]
        new_result = self.retry_loop.execute_with_retry(goal, failure_context)

        # Assert - counter should be reset after success
        self.assertEqual(success_result.get('status'), 'success')
        self.assertFalse(new_result.get('max_retries_reached', False))

if __name__ == '__main__':
    unittest.main()