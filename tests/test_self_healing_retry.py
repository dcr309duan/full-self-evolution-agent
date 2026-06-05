import pytest
from unittest.mock import Mock, patch, call
from datetime import datetime

# Import the module under test - adjust import path as needed
from self_healing_retry import SelfHealingRetry, RetryStrategy, MutationResult

class TestSelfHealingRetry:
    """Comprehensive test suite for SelfHealingRetry functionality."""

    @pytest.fixture
    def retry_handler(self):
        """Fixture providing a basic SelfHealingRetry instance."""
        return SelfHealingRetry(max_retries=3)

    @pytest.fixture
    def mock_mutation(self):
        """Fixture providing a mock mutation function."""
        return Mock(return_value=MutationResult(success=True, data="mutation_result"))

    def test_successful_mutation_on_first_try(self, retry_handler, mock_mutation):
        """Test that a mutation succeeds on the first attempt without retries."""
        # Arrange
        mutation_data = {"key": "value"}
        
        # Act
        result = retry_handler.execute(mock_mutation, mutation_data)
        
        # Assert
        assert result.success is True
        assert result.data == "mutation_result"
        assert result.attempts == 1
        assert result.retry_count == 0
        mock_mutation.assert_called_once_with(mutation_data)

    def test_retry_with_different_strategy_after_failure(self, retry_handler):
        """Test that retry uses a different strategy after initial failure."""
        # Arrange
        mock_mutation = Mock()
        # First call fails, second call succeeds
        mock_mutation.side_effect = [
            MutationResult(success=False, error="First failure"),
            MutationResult(success=True, data="retry_success")
        ]
        
        # Mock strategy switching
        retry_handler.strategies = [
            RetryStrategy(name="immediate", delay=0),
            RetryStrategy(name="exponential_backoff", delay=1),
            RetryStrategy(name="linear", delay=0.5)
        ]
        
        # Act
        result = retry_handler.execute(mock_mutation, {"test": "data"})
        
        # Assert
        assert result.success is True
        assert result.data == "retry_success"
        assert result.attempts == 2
        assert result.retry_count == 1
        assert result.strategy_used == "exponential_backoff"
        assert mock_mutation.call_count == 2

    def test_escalation_after_3_failures(self, retry_handler):
        """Test that escalation occurs after 3 consecutive failures."""
        # Arrange
        mock_mutation = Mock()
        mock_mutation.side_effect = [
            MutationResult(success=False, error="Failure 1"),
            MutationResult(success=False, error="Failure 2"),
            MutationResult(success=False, error="Failure 3"),
            MutationResult(success=False, error="Failure 4")  # Should not be called
        ]
        
        # Act
        result = retry_handler.execute(mock_mutation, {"test": "data"})
        
        # Assert
        assert result.success is False
        assert result.attempts == 3
        assert result.retry_count == 2
        assert result.escalated is True
        assert result.escalation_level == "critical"
        assert mock_mutation.call_count == 3

    def test_rollback_on_each_failure(self, retry_handler):
        """Test that rollback is performed on each failure."""
        # Arrange
        mock_mutation = Mock()
        mock_rollback = Mock()
        mock_mutation.side_effect = [
            MutationResult(success=False, error="Failure 1"),
            MutationResult(success=False, error="Failure 2"),
            MutationResult(success=True, data="success")
        ]
        
        retry_handler.rollback_function = mock_rollback
        
        # Act
        result = retry_handler.execute(mock_mutation, {"test": "data"})
        
        # Assert
        assert result.success is True
        assert mock_rollback.call_count == 2  # Rollback called for each failure
        mock_rollback.assert_has_calls([
            call({"test": "data"}, attempt=1),
            call({"test": "data"}, attempt=2)
        ])

    def test_failure_logging_format(self, retry_handler):
        """Test that failure logging follows the expected format."""
        # Arrange
        mock_mutation = Mock()
        mock_mutation.side_effect = [
            MutationResult(success=False, error="First failure"),
            MutationResult(success=False, error="Second failure"),
            MutationResult(success=True, data="success")
        ]
        
        mock_logger = Mock()
        retry_handler.logger = mock_logger
        
        # Act
        result = retry_handler.execute(mock_mutation, {"test": "data"})
        
        # Assert
        assert mock_logger.warning.call_count == 2
        expected_log_format = "Mutation failed on attempt {attempt}: {error}. Strategy: {strategy}"
        
        # Check first failure log
        first_call = mock_logger.warning.call_args_list[0]
        assert "attempt 1" in str(first_call)
        assert "First failure" in str(first_call)
        assert "strategy" in str(first_call).lower()
        
        # Check second failure log
        second_call = mock_logger.warning.call_args_list[1]
        assert "attempt 2" in str(second_call)
        assert "Second failure" in str(second_call)

    def test_strategy_switching_logic(self, retry_handler):
        """Test the strategy switching logic based on failure patterns."""
        # Arrange
        mock_mutation = Mock()
        mock_mutation.side_effect = [
            MutationResult(success=False, error="Timeout error"),
            MutationResult(success=False, error="Timeout error"),
            MutationResult(success=True, data="success")
        ]
        
        # Configure strategies with different behaviors
        strategies = [
            RetryStrategy(name="immediate", delay=0, max_attempts=1),
            RetryStrategy(name="exponential_backoff", delay=1, max_attempts=2),
            RetryStrategy(name="linear", delay=0.5, max_attempts=3)
        ]
        retry_handler.strategies = strategies
        
        # Act
        result = retry_handler.execute(mock_mutation, {"test": "data"})
        
        # Assert
        assert result.success is True
        assert result.attempts == 3
        assert result.strategy_used == "exponential_backoff"
        
        # Verify strategy switching pattern
        expected_strategy_sequence = ["immediate", "exponential_backoff", "exponential_backoff"]
        assert result.strategy_sequence == expected_strategy_sequence
        
        # Verify that strategy was switched after first failure
        assert result.strategy_changes == 1

    def test_strategy_switching_with_different_error_types(self, retry_handler):
        """Test strategy switching based on different error types."""
        # Arrange
        mock_mutation = Mock()
        mock_mutation.side_effect = [
            MutationResult(success=False, error="ConnectionError"),
            MutationResult(success=False, error="TimeoutError"),
            MutationResult(success=False, error="ValueError"),
            MutationResult(success=True, data="success")
        ]
        
        retry_handler.error_strategy_map = {
            "ConnectionError": "immediate",
            "TimeoutError": "exponential_backoff",
            "ValueError": "linear"
        }
        
        # Act
        result = retry_handler.execute(mock_mutation, {"test": "data"})
        
        # Assert
        assert result.success is True
        assert result.attempts == 4
        assert result.strategy_used == "linear"
        
        # Verify strategy switching based on error types
        expected_strategies = ["immediate", "exponential_backoff", "linear", "linear"]
        assert result.strategy_sequence == expected_strategies

    def test_max_retries_exceeded_with_escalation(self, retry_handler):
        """Test that escalation happens when max retries are exceeded."""
        # Arrange
        mock_mutation = Mock()
        mock_mutation.side_effect = [
            MutationResult(success=False, error="Failure 1"),
            MutationResult(success=False, error="Failure 2"),
            MutationResult(success=False, error="Failure 3")
        ]
        
        mock_escalation_handler = Mock()
        retry_handler.escalation_handler = mock_escalation_handler
        
        # Act
        result = retry_handler.execute(mock_mutation, {"test": "data"})
        
        # Assert
        assert result.success is False
        assert result.escalated is True
        mock_escalation_handler.assert_called_once_with(
            mutation_data={"test": "data"},
            failures=3,
            last_error="Failure 3"
        )

    def test_concurrent_failure_handling(self, retry_handler):
        """Test handling of concurrent failures."""
        # Arrange
        mock_mutation = Mock()
        mock_mutation.side_effect = [
            MutationResult(success=False, error="Concurrent modification"),
            MutationResult(success=False, error="Concurrent modification"),
            MutationResult(success=True, data="success")
        ]
        
        retry_handler.concurrent_failure_strategy = "retry_with_backoff"
        
        # Act
        result = retry_handler.execute(mock_mutation, {"test": "data"})
        
        # Assert
        assert result.success is True
        assert result.concurrent_failures_handled == 2
        assert result.strategy_used == "retry_with_backoff"

    def test_partial_success_with_rollback(self, retry_handler):
        """Test partial success scenario with rollback."""
        # Arrange
        mock_mutation = Mock()
        mock_mutation.side_effect = [
            MutationResult(success=True, data="partial_1"),
            MutationResult(success=False, error="Failed on second"),
            MutationResult(success=True, data="partial_3")
        ]
        
        mock_rollback = Mock()
        retry_handler.rollback_function = mock_rollback
        
        # Act
        result = retry_handler.execute(mock_mutation, {"test": "data"})
        
        # Assert
        assert result.success is True
        assert result.data == "partial_3"
        assert result.partial_results == ["partial_1", "partial_3"]
        mock_rollback.assert_called_once()  # Rollback only for the failed attempt

    def test_custom_retry_condition(self, retry_handler):
        """Test custom retry condition logic."""
        # Arrange
        def custom_retry_condition(result):
            return result.error and "retryable" in result.error
        
        mock_mutation = Mock()
        mock_mutation.side_effect = [
            MutationResult(success=False, error="retryable error"),
            MutationResult(success=False, error="non-retryable error"),
            MutationResult(success=True, data="success")
        ]
        
        retry_handler.retry_condition = custom_retry_condition
        
        # Act
        result = retry_handler.execute(mock_mutation, {"test": "data"})
        
        # Assert
        assert result.success is False  # Second failure was non-retryable
        assert result.attempts == 2
        assert result.retry_count == 1