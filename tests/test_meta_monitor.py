import pytest
from unittest.mock import patch, MagicMock
from src.meta_monitor import MetaMonitor, FailureRecord, RootCauseHypothesis

@pytest.fixture
def monitor():
    return MetaMonitor()

class TestMetaMonitor:
    def test_single_failure_does_not_trigger(self, monitor):
        """Test that a single failure in any category does not trigger reprioritization."""
        monitor.record_failure("execution", "Test error 1")
        assert not monitor.should_reprioritize("execution")

    def test_two_consecutive_failures_do_not_trigger(self, monitor):
        """Test that two consecutive failures in the same category do not trigger reprioritization."""
        monitor.record_failure("execution", "Test error 1")
        monitor.record_failure("execution", "Test error 2")
        assert not monitor.should_reprioritize("execution")

    def test_three_consecutive_failures_trigger_reprioritization(self, monitor):
        """Test that three consecutive failures in the same category trigger reprioritization."""
        monitor.record_failure("execution", "Test error 1")
        monitor.record_failure("execution", "Test error 2")
        monitor.record_failure("execution", "Test error 3")
        assert monitor.should_reprioritize("execution")

    def test_success_resets_counter(self, monitor):
        """Test that a successful operation resets the failure counter for that category."""
        monitor.record_failure("execution", "Test error 1")
        monitor.record_failure("execution", "Test error 2")
        monitor.record_success("execution")
        assert not monitor.should_reprioritize("execution")

    def test_different_categories_tracked_independently(self, monitor):
        """Test that failure counters for different categories are tracked independently."""
        monitor.record_failure("execution", "Test error 1")
        monitor.record_failure("execution", "Test error 2")
        monitor.record_failure("execution", "Test error 3")
        monitor.record_failure("planning", "Test error 1")
        monitor.record_failure("planning", "Test error 2")
        
        assert monitor.should_reprioritize("execution")
        assert not monitor.should_reprioritize("planning")

    def test_root_cause_hypothesis_generated_with_valid_structure(self, monitor):
        """Test that generated root cause hypothesis has the expected structure."""
        monitor.record_failure("execution", "Test error 1")
        monitor.record_failure("execution", "Test error 2")
        monitor.record_failure("execution", "Test error 3")
        
        hypothesis = monitor.generate_root_cause_hypothesis("execution")
        
        assert isinstance(hypothesis, RootCauseHypothesis)
        assert hasattr(hypothesis, 'category')
        assert hasattr(hypothesis, 'confidence')
        assert hasattr(hypothesis, 'description')
        assert hasattr(hypothesis, 'suggested_actions')
        assert hypothesis.category == "execution"
        assert 0.0 <= hypothesis.confidence <= 1.0
        assert isinstance(hypothesis.description, str) and len(hypothesis.description) > 0
        assert isinstance(hypothesis.suggested_actions, list) and len(hypothesis.suggested_actions) > 0