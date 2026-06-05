import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from src.health_dashboard import HealthDashboard
from src.rollback_manager import RollbackManager
from src.sandbox_manager import SandboxManager
from src.orchestrator import Orchestrator

@pytest.fixture
def health_dashboard():
    return HealthDashboard(window_size=100, lockdown_threshold=0.2)

@pytest.fixture
def mock_orchestrator():
    orchestrator = Mock(spec=Orchestrator)
    orchestrator.lockdown = False
    return orchestrator

@pytest.fixture
def sample_failures():
    return [
        {"module": "auth", "timestamp": datetime.now() - timedelta(minutes=5), "type": "timeout"},
        {"module": "auth", "timestamp": datetime.now() - timedelta(minutes=4), "type": "error"},
        {"module": "db", "timestamp": datetime.now() - timedelta(minutes=3), "type": "connection_error"},
        {"module": "cache", "timestamp": datetime.now() - timedelta(minutes=2), "type": "timeout"},
        {"module": "auth", "timestamp": datetime.now() - timedelta(minutes=1), "type": "error"},
    ]

class TestRollingWindowCalculation:
    def test_rolling_window_with_synthetic_failures(self, health_dashboard, sample_failures):
        """Test that rolling window correctly calculates failure rates with synthetic data."""
        for failure in sample_failures:
            health_dashboard.record_failure(failure["module"], failure["type"])
        
        window_stats = health_dashboard.get_window_stats()
        assert window_stats["total_requests"] == 100  # default window size
        assert window_stats["failure_count"] == 5
        assert window_stats["failure_rate"] == 0.05

    def test_rolling_window_eviction(self, health_dashboard):
        """Test that old failures are evicted from the rolling window."""
        old_failure = {"module": "test", "timestamp": datetime.now() - timedelta(hours=2)}
        health_dashboard.record_failure("test", "error", timestamp=old_failure["timestamp"])
        
        # Add recent failures to fill window
        for i in range(10):
            health_dashboard.record_failure("test", "error")
        
        window_stats = health_dashboard.get_window_stats()
        assert window_stats["failure_count"] == 10  # old failure should be evicted

class TestLockdownTriggers:
    def test_lockdown_trigger_at_exactly_20_percent(self, health_dashboard, mock_orchestrator):
        """Test that lockdown triggers when failure rate reaches exactly 20%."""
        health_dashboard.set_orchestrator(mock_orchestrator)
        
        # Record 20 failures out of 100 requests (20%)
        for i in range(20):
            health_dashboard.record_failure("test", "error")
        
        # Record 80 successful requests
        for i in range(80):
            health_dashboard.record_success("test")
        
        assert health_dashboard.should_lockdown() == True
        assert health_dashboard.lockdown_active == True

    def test_lockdown_not_triggered_below_threshold(self, health_dashboard, mock_orchestrator):
        """Test that lockdown does not trigger below 20% threshold."""
        health_dashboard.set_orchestrator(mock_orchestrator)
        
        # Record 19 failures out of 100 requests (19%)
        for i in range(19):
            health_dashboard.record_failure("test", "error")
        
        for i in range(81):
            health_dashboard.record_success("test")
        
        assert health_dashboard.should_lockdown() == False
        assert health_dashboard.lockdown_active == False

class TestLockdownLifts:
    def test_lockdown_lifts_when_rate_drops_below_threshold(self, health_dashboard, mock_orchestrator):
        """Test that lockdown lifts when failure rate drops below threshold."""
        health_dashboard.set_orchestrator(mock_orchestrator)
        
        # Trigger lockdown with 20% failure rate
        for i in range(20):
            health_dashboard.record_failure("test", "error")
        for i in range(80):
            health_dashboard.record_success("test")
        
        assert health_dashboard.should_lockdown() == True
        
        # Simulate recovery - replace failures with successes
        health_dashboard.clear_window()
        for i in range(100):
            health_dashboard.record_success("test")
        
        assert health_dashboard.should_lockdown() == False
        assert health_dashboard.lockdown_active == False

    def test_lockdown_persists_while_above_threshold(self, health_dashboard, mock_orchestrator):
        """Test that lockdown persists while failure rate remains above threshold."""
        health_dashboard.set_orchestrator(mock_orchestrator)
        
        # Trigger lockdown
        for i in range(25):
            health_dashboard.record_failure("test", "error")
        for i in range(75):
            health_dashboard.record_success("test")
        
        assert health_dashboard.should_lockdown() == True
        
        # Add more successes but still above 20%
        for i in range(5):
            health_dashboard.record_success("test")
        
        # Now 25 failures out of 105 = ~23.8%
        assert health_dashboard.should_lockdown() == True

class TestCrossModuleFailureCorrelation:
    def test_cross_module_correlation_detection(self, health_dashboard):
        """Test detection of correlated failures across modules."""
        # Simulate correlated failures in auth and db modules
        for i in range(5):
            health_dashboard.record_failure("auth", "timeout")
            health_dashboard.record_failure("db", "connection_error")
        
        correlations = health_dashboard.get_cross_module_correlations()
        assert ("auth", "db") in correlations
        assert correlations[("auth", "db")] >= 0.8  # High correlation

    def test_no_correlation_independent_failures(self, health_dashboard):
        """Test that independent failures show no correlation."""
        health_dashboard.record_failure("auth", "error")
        health_dashboard.record_failure("cache", "timeout")
        health_dashboard.record_failure("db", "connection_error")
        
        correlations = health_dashboard.get_cross_module_correlations()
        assert len(correlations) == 0  # No significant correlations

class TestSandboxErrorTracking:
    def test_sandbox_error_recording(self, health_dashboard):
        """Test that sandbox errors are properly tracked."""
        sandbox_errors = [
            {"sandbox_id": "sb-1", "error_type": "timeout", "timestamp": datetime.now()},
            {"sandbox_id": "sb-2", "error_type": "crash", "timestamp": datetime.now()},
            {"sandbox_id": "sb-1", "error_type": "timeout", "timestamp": datetime.now()},
        ]
        
        for error in sandbox_errors:
            health_dashboard.record_sandbox_error(error["sandbox_id"], error["error_type"])
        
        sandbox_stats = health_dashboard.get_sandbox_stats()
        assert sandbox_stats["sb-1"]["error_count"] == 2
        assert sandbox_stats["sb-2"]["error_count"] == 1
        assert sandbox_stats["sb-1"]["error_types"]["timeout"] == 2

    def test_sandbox_error_threshold(self, health_dashboard):
        """Test that sandbox error threshold triggers alerts."""
        # Record enough errors to trigger sandbox alert
        for i in range(10):
            health_dashboard.record_sandbox_error("sb-1", "timeout")
        
        assert health_dashboard.sandbox_needs_attention("sb-1") == True
        assert health_dashboard.sandbox_needs_attention("sb-2") == False

class TestRollbackFrequencyRecording:
    def test_rollback_frequency_tracking(self, health_dashboard):
        """Test that rollback frequencies are properly recorded."""
        rollback_manager = RollbackManager()
        health_dashboard.set_rollback_manager(rollback_manager)
        
        # Simulate rollbacks
        rollback_manager.record_rollback("deploy-1", "auth")
        rollback_manager.record_rollback("deploy-2", "db")
        rollback_manager.record_rollback("deploy-3", "auth")
        
        rollback_stats = health_dashboard.get_rollback_stats()
        assert rollback_stats["auth"] == 2
        assert rollback_stats["db"] == 1

    def test_rollback_frequency_alert(self, health_dashboard):
        """Test that high rollback frequency triggers alerts."""
        rollback_manager = RollbackManager()
        health_dashboard.set_rollback_manager(rollback_manager)
        
        # Record many rollbacks for a module
        for i in range(5):
            rollback_manager.record_rollback(f"deploy-{i}", "auth")
        
        assert health_dashboard.rollback_frequency_exceeds_threshold("auth") == True
        assert health_dashboard.rollback_frequency_exceeds_threshold("db") == False

class TestOrchestratorIntegration:
    def test_orchestrator_lockdown_behavior(self, health_dashboard, mock_orchestrator):
        """Test integration with orchestrator lockdown behavior."""
        health_dashboard.set_orchestrator(mock_orchestrator)
        
        # Trigger lockdown condition
        for i in range(20):
            health_dashboard.record_failure("test", "error")
        for i in range(80):
            health_dashboard.record_success("test")
        
        health_dashboard.evaluate_and_apply_lockdown()
        
        # Verify orchestrator was called to initiate lockdown
        mock_orchestrator.initiate_lockdown.assert_called_once()
        assert mock_orchestrator.lockdown == True

    def test_orchestrator_lockdown_lift(self, health_dashboard, mock_orchestrator):
        """Test that orchestrator lockdown is lifted correctly."""
        health_dashboard.set_orchestrator(mock_orchestrator)
        
        # First trigger lockdown
        for i in range(20):
            health_dashboard.record_failure("test", "error")
        for i in range(80):
            health_dashboard.record_success("test")
        
        health_dashboard.evaluate_and_apply_lockdown()
        mock_orchestrator.initiate_lockdown.assert_called_once()
        
        # Now recover
        health_dashboard.clear_window()
        for i in range(100):
            health_dashboard.record_success("test")
        
        health_dashboard.evaluate_and_apply_lockdown()
        mock_orchestrator.lift_lockdown.assert_called_once()

    def test_orchestrator_no_action_when_stable(self, health_dashboard, mock_orchestrator):
        """Test that no lockdown action is taken when system is stable."""
        health_dashboard.set_orchestrator(mock_orchestrator)
        
        # Normal operation with low failure rate
        for i in range(5):
            health_dashboard.record_failure("test", "error")
        for i in range(95):
            health_dashboard.record_success("test")
        
        health_dashboard.evaluate_and_apply_lockdown()
        
        mock_orchestrator.initiate_lockdown.assert_not_called()
        mock_orchestrator.lift_lockdown.assert_not_called()