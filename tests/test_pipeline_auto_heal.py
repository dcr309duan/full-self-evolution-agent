import pytest
import time
from unittest.mock import Mock, patch, call
from pipeline_auto_heal import AutoHealer, PipelineComponent, PipelineStatus, AlertLevel

class TestPipelineAutoHeal:
    """Test suite for automatic pipeline healing functionality."""

    @pytest.fixture
    def auto_healer(self):
        """Fixture to create a fresh AutoHealer instance for each test."""
        return AutoHealer(max_retries=3, backoff_base=2, backoff_cap=60)

    @pytest.fixture
    def mock_component(self):
        """Fixture to create a mock pipeline component."""
        component = Mock(spec=PipelineComponent)
        component.name = "test_component"
        component.status = PipelineStatus.HEALTHY
        return component

    def test_p0_broken_link_triggers_retry(self, auto_healer, mock_component):
        """
        Test that a P0 broken link detection triggers automatic retry of the failed component.
        
        Verifies:
        - Component is retried after P0 failure
        - Retry attempt is logged
        - Component status is updated appropriately
        """
        # Setup: Configure component to fail once then succeed
        mock_component.execute.side_effect = [
            PipelineStatus.FAILED_P0,  # First call fails with P0
            PipelineStatus.HEALTHY     # Second call succeeds
        ]
        
        # Execute: Attempt to heal the component
        result = auto_healer.heal_component(mock_component)
        
        # Assert: Component was retried and succeeded
        assert mock_component.execute.call_count == 2
        assert result == PipelineStatus.HEALTHY
        assert auto_healer.retry_count[mock_component.name] == 1

    def test_three_consecutive_failures_escalates_to_human(self, auto_healer, mock_component):
        """
        Test that after 3 consecutive failures of the same component, 
        the system escalates to human intervention by logging a critical alert.
        
        Verifies:
        - Component is retried exactly 3 times
        - After 3 failures, a critical alert is logged
        - Component status is set to ESCALATED
        """
        # Setup: Configure component to always fail
        mock_component.execute.return_value = PipelineStatus.FAILED_P0
        
        # Mock the alert logging
        with patch.object(auto_healer, 'log_alert') as mock_log_alert:
            # Execute: Attempt to heal the component
            result = auto_healer.heal_component(mock_component)
            
            # Assert: Component was retried 3 times
            assert mock_component.execute.call_count == 3
            assert result == PipelineStatus.ESCALATED
            
            # Assert: Critical alert was logged exactly once
            mock_log_alert.assert_called_once_with(
                level=AlertLevel.CRITICAL,
                component=mock_component.name,
                message=f"Component '{mock_component.name}' failed 3 consecutive times. Escalating to human intervention."
            )

    def test_temporary_failure_with_exponential_backoff(self, auto_healer, mock_component):
        """
        Test that temporary failures (e.g., timeout) are retried with exponential backoff.
        
        Verifies:
        - Component is retried after temporary failure
        - Backoff delay increases exponentially between retries
        - Component eventually succeeds after temporary failure resolves
        """
        # Setup: Configure component to fail temporarily then succeed
        mock_component.execute.side_effect = [
            PipelineStatus.FAILED_TIMEOUT,  # First call times out
            PipelineStatus.FAILED_TIMEOUT,  # Second call times out
            PipelineStatus.HEALTHY          # Third call succeeds
        ]
        
        # Track the time between retries
        with patch('time.sleep') as mock_sleep:
            # Execute: Attempt to heal the component
            start_time = time.time()
            result = auto_healer.heal_component(mock_component)
            end_time = time.time()
            
            # Assert: Component was retried 3 times (2 failures + 1 success)
            assert mock_component.execute.call_count == 3
            assert result == PipelineStatus.HEALTHY
            
            # Assert: Exponential backoff was applied
            # Backoff times: 2^1=2, 2^2=4 seconds (base=2)
            expected_calls = [
                call(2),   # First retry delay
                call(4)    # Second retry delay
            ]
            mock_sleep.assert_has_calls(expected_calls)
            assert mock_sleep.call_count == 2

    def test_max_retries_not_exceeded(self, auto_healer, mock_component):
        """
        Test that the system does not exceed the maximum number of retries.
        
        Verifies:
        - Retry count is capped at max_retries
        - Component is not retried more than allowed
        """
        # Setup: Configure component to always fail
        mock_component.execute.return_value = PipelineStatus.FAILED_P0
        
        # Execute: Attempt to heal the component
        result = auto_healer.heal_component(mock_component)
        
        # Assert: Component was retried exactly max_retries times
        assert mock_component.execute.call_count == auto_healer.max_retries
        assert result == PipelineStatus.ESCALATED

    def test_backoff_cap_respected(self, auto_healer, mock_component):
        """
        Test that exponential backoff does not exceed the configured cap.
        
        Verifies:
        - Backoff delay is capped at backoff_cap
        - Long delays are limited to prevent excessive waiting
        """
        # Setup: Configure component to fail repeatedly
        mock_component.execute.return_value = PipelineStatus.FAILED_TIMEOUT
        
        # Override backoff cap to a small value for testing
        auto_healer.backoff_cap = 10
        
        with patch('time.sleep') as mock_sleep:
            # Execute: Attempt to heal the component
            result = auto_healer.heal_component(mock_component)
            
            # Assert: Backoff times are capped
            # With base=2 and cap=10: 2, 4, 8 (all under cap)
            for call_args in mock_sleep.call_args_list:
                delay = call_args[0][0]
                assert delay <= auto_healer.backoff_cap, f"Backoff delay {delay} exceeds cap {auto_healer.backoff_cap}"

    def test_healthy_component_not_retried(self, auto_healer, mock_component):
        """
        Test that a healthy component is not retried unnecessarily.
        
        Verifies:
        - No retry occurs for healthy components
        - Component status remains HEALTHY
        """
        # Setup: Configure component to succeed immediately
        mock_component.execute.return_value = PipelineStatus.HEALTHY
        
        # Execute: Attempt to heal the component
        result = auto_healer.heal_component(mock_component)
        
        # Assert: Component was executed only once
        assert mock_component.execute.call_count == 1
        assert result == PipelineStatus.HEALTHY

    def test_mixed_failure_types(self, auto_healer, mock_component):
        """
        Test handling of mixed failure types (P0 and temporary).
        
        Verifies:
        - System correctly distinguishes between failure types
        - Appropriate retry strategy is applied for each type
        """
        # Setup: Configure component with mixed failures
        mock_component.execute.side_effect = [
            PipelineStatus.FAILED_TIMEOUT,  # Temporary failure
            PipelineStatus.FAILED_P0,       # P0 failure
            PipelineStatus.HEALTHY          # Success
        ]
        
        with patch('time.sleep') as mock_sleep:
            # Execute: Attempt to heal the component
            result = auto_healer.heal_component(mock_component)
            
            # Assert: Component was retried appropriately
            assert mock_component.execute.call_count == 3
            assert result == PipelineStatus.HEALTHY
            
            # Assert: Backoff was applied for timeout but not for P0
            # (Assuming P0 failures don't use backoff)
            assert mock_sleep.call_count == 1  # Only timeout triggers backoff

    def test_auto_retry_mutation_engine(self, auto_healer, mock_component):
        """
        Test that the mutation engine auto-retry logic works correctly.
        
        Verifies:
        - Mutation engine is configured to fail twice then succeed
        - Retry logic triggers and pipeline eventually completes
        - Broken link reporter records the transient failure as a warning, not a bug
        """
        # Setup: Configure mutation engine to fail twice then succeed
        mock_component.execute.side_effect = [
            PipelineStatus.FAILED_MUTATION,  # First call fails with mutation error
            PipelineStatus.FAILED_MUTATION,  # Second call fails with mutation error
            PipelineStatus.HEALTHY           # Third call succeeds
        ]
        
        # Mock the broken link reporter
        with patch.object(auto_healer, 'broken_link_reporter') as mock_reporter:
            # Execute: Run the pipeline
            result = auto_healer.heal_component(mock_component)
            
            # Assert: Retry logic triggered and pipeline eventually completed
            assert mock_component.execute.call_count == 3
            assert result == PipelineStatus.HEALTHY
            assert auto_healer.retry_count[mock_component.name] == 2
            
            # Assert: Broken link reporter recorded the transient failure as a warning
            mock_reporter.record_failure.assert_called_once_with(
                component=mock_component.name,
                failure_type="mutation",
                severity="warning"
            )

    def test_escalation_after_3_failures(self, auto_healer, mock_component):
        """
        Test that after 3 consecutive mutation engine failures:
        - A critical alert is logged
        - Pipeline stops
        - Broken link reporter generates P0 bug report with escalation flag
        """
        # Setup: Configure mutation engine to fail 3 times consecutively
        mock_component.execute.side_effect = [
            PipelineStatus.FAILED_MUTATION,  # First call fails
            PipelineStatus.FAILED_MUTATION,  # Second call fails
            PipelineStatus.FAILED_MUTATION,  # Third call fails
            PipelineStatus.HEALTHY           # Would succeed if retried, but shouldn't be reached
        ]
        
        # Mock the alert logging and broken link reporter
        with patch.object(auto_healer, 'log_alert') as mock_log_alert, \
             patch.object(auto_healer, 'broken_link_reporter') as mock_reporter:
            
            # Execute: Run the pipeline
            result = auto_healer.heal_component(mock_component)
            
            # Assert: Component was retried exactly 3 times (max_retries)
            assert mock_component.execute.call_count == 3
            assert result == PipelineStatus.ESCALATED
            
            # Assert: Critical alert was logged
            mock_log_alert.assert_called_once_with(
                level=AlertLevel.CRITICAL,
                component=mock_component.name,
                message=f"Component '{mock_component.name}' failed 3 consecutive times. Escalating to human intervention."
            )
            
            # Assert: Broken link reporter generated P0 bug report with escalation flag
            mock_reporter.generate_bug_report.assert_called_once_with(
                component=mock_component.name,
                failure_type="mutation",
                severity="P0",
                escalation=True
            )

if __name__ == '__main__':
    pytest.main([__file__])