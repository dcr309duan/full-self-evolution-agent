from datetime import datetime, timedelta
import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import json
import html

from src.failure_cluster_analyzer import (
    FailureClusterAnalyzer,
    FailureCluster,
    ClusterConfig,
    ClusterDashboard,
    ClusterOrchestratorIntegration
)
from src.orchestrator import Orchestrator

# Sample failure data for testing
SAMPLE_FAILURES = [
    {
        "error_type": "ValueError",
        "module": "data_processor",
        "line": 42,
        "timestamp": datetime(2024, 1, 15, 10, 30, 0),
        "traceback": "Traceback: ValueError: invalid literal for int()"
    },
    {
        "error_type": "ValueError",
        "module": "data_processor",
        "line": 42,
        "timestamp": datetime(2024, 1, 15, 10, 31, 0),
        "traceback": "Traceback: ValueError: invalid literal for int()"
    },
    {
        "error_type": "TypeError",
        "module": "api_handler",
        "line": 87,
        "timestamp": datetime(2024, 1, 15, 10, 32, 0),
        "traceback": "Traceback: TypeError: unsupported operand type(s)"
    },
    {
        "error_type": "ValueError",
        "module": "data_processor",
        "line": 42,
        "timestamp": datetime(2024, 1, 15, 10, 33, 0),
        "traceback": "Traceback: ValueError: invalid literal for int()"
    }
]

@pytest.fixture
def cluster_config():
    return ClusterConfig(
        similarity_threshold=0.8,
        time_decay_hours=24,
        min_cluster_size=3,
        max_clusters=10,
        dashboard_output_dir=Path("/tmp/test_dashboards")
    )

@pytest.fixture
def analyzer(cluster_config):
    return FailureClusterAnalyzer(config=cluster_config)

@pytest.fixture
def mock_orchestrator():
    orchestrator = Mock(spec=Orchestrator)
    orchestrator.auto_fix = MagicMock(return_value={"status": "success", "fix_applied": True})
    return orchestrator

class TestFailureClustering:
    """Test clustering of same error type in same module."""

    def test_same_error_same_module_clustering(self, analyzer):
        """Test that identical errors in the same module are clustered together."""
        for failure in SAMPLE_FAILURES[:3]:  # First 3 failures
            analyzer.add_failure(failure)
        
        clusters = analyzer.get_clusters()
        
        # Should have at least one cluster for the ValueError in data_processor
        value_error_clusters = [
            c for c in clusters 
            if c.error_type == "ValueError" and c.module == "data_processor"
        ]
        assert len(value_error_clusters) >= 1
        assert value_error_clusters[0].failure_count >= 2

    def test_different_error_types_separate_clusters(self, analyzer):
        """Test that different error types create separate clusters."""
        for failure in SAMPLE_FAILURES:
            analyzer.add_failure(failure)
        
        clusters = analyzer.get_clusters()
        cluster_types = [(c.error_type, c.module) for c in clusters]
        
        assert ("ValueError", "data_processor") in cluster_types
        assert ("TypeError", "api_handler") in cluster_types

    def test_cluster_merging_same_signature(self, analyzer):
        """Test that failures with same error signature are merged into one cluster."""
        # Add multiple identical failures
        for _ in range(5):
            analyzer.add_failure(SAMPLE_FAILURES[0])
        
        clusters = analyzer.get_clusters()
        value_error_clusters = [
            c for c in clusters 
            if c.error_type == "ValueError" and c.module == "data_processor"
        ]
        
        assert len(value_error_clusters) == 1
        assert value_error_clusters[0].failure_count == 5

class TestTimeDecay:
    """Test clustering across cycles with time decay."""

    def test_recent_failures_weighted_higher(self, analyzer):
        """Test that recent failures have higher weight in clustering."""
        old_failure = SAMPLE_FAILURES[0].copy()
        old_failure["timestamp"] = datetime(2024, 1, 1, 10, 0, 0)
        
        recent_failure = SAMPLE_FAILURES[0].copy()
        recent_failure["timestamp"] = datetime(2024, 1, 15, 10, 35, 0)
        
        analyzer.add_failure(old_failure)
        analyzer.add_failure(recent_failure)
        
        clusters = analyzer.get_clusters()
        assert len(clusters) > 0
        # Recent failure should have higher weight
        assert clusters[0].weighted_score > 0

    def test_old_failures_decay_over_time(self, analyzer):
        """Test that old failures decay and may not form clusters."""
        # Add failures older than decay threshold
        old_failures = []
        for i in range(5):
            failure = SAMPLE_FAILURES[0].copy()
            failure["timestamp"] = datetime(2024, 1, 1, 10, 0, 0) - timedelta(hours=i*24)
            old_failures.append(failure)
        
        for failure in old_failures:
            analyzer.add_failure(failure)
        
        clusters = analyzer.get_clusters()
        # Old failures should have decayed significantly
        if clusters:
            assert all(c.weighted_score < 0.5 for c in clusters)

    def test_time_decay_affects_cluster_priority(self, analyzer):
        """Test that time decay affects cluster priority ordering."""
        # Add recent failures
        for i in range(3):
            failure = SAMPLE_FAILURES[0].copy()
            failure["timestamp"] = datetime(2024, 1, 15, 10, 30, 0) + timedelta(minutes=i)
            analyzer.add_failure(failure)
        
        # Add older failures
        for i in range(3):
            failure = SAMPLE_FAILURES[1].copy()
            failure["timestamp"] = datetime(2024, 1, 10, 10, 30, 0) + timedelta(minutes=i)
            analyzer.add_failure(failure)
        
        clusters = analyzer.get_clusters()
        # Recent clusters should have higher priority
        if len(clusters) >= 2:
            assert clusters[0].timestamp > clusters[1].timestamp

class TestThresholdTriggering:
    """Test threshold triggering for cluster formation."""

    def test_min_cluster_size_threshold(self, analyzer):
        """Test that clusters below minimum size are not formed."""
        # Add only 2 failures (min_cluster_size=3)
        analyzer.add_failure(SAMPLE_FAILURES[0])
        analyzer.add_failure(SAMPLE_FAILURES[1])
        
        clusters = analyzer.get_clusters()
        # Should not form a cluster with only 2 failures
        assert len(clusters) == 0

    def test_similarity_threshold_prevents_mismatch(self, analyzer):
        """Test that similarity threshold prevents incorrect clustering."""
        different_failure = {
            "error_type": "KeyError",
            "module": "data_processor",
            "line": 42,
            "timestamp": datetime(2024, 1, 15, 10, 30, 0),
            "traceback": "Traceback: KeyError: 'missing_key'"
        }
        
        analyzer.add_failure(SAMPLE_FAILURES[0])
        analyzer.add_failure(different_failure)
        
        clusters = analyzer.get_clusters()
        # Different error types should not cluster together
        for cluster in clusters:
            assert cluster.error_type != "KeyError" or cluster.failure_count < 2

    def test_threshold_triggers_alert(self, analyzer):
        """Test that threshold crossing triggers alert."""
        alert_triggered = False
        
        def alert_callback(cluster):
            nonlocal alert_triggered
            alert_triggered = True
        
        analyzer.on_cluster_threshold_reached(alert_callback)
        
        # Add enough failures to trigger threshold
        for _ in range(5):
            analyzer.add_failure(SAMPLE_FAILURES[0])
        
        assert alert_triggered

class TestDashboardGeneration:
    """Test dashboard generation produces valid HTML."""

    def test_dashboard_generates_html(self, analyzer, tmp_path):
        """Test that dashboard generation creates HTML file."""
        # Add some failures
        for failure in SAMPLE_FAILURES:
            analyzer.add_failure(failure)
        
        dashboard = ClusterDashboard(analyzer, output_dir=tmp_path)
        dashboard.generate()
        
        # Check that HTML file was created
        html_files = list(tmp_path.glob("*.html"))
        assert len(html_files) > 0

    def test_dashboard_html_is_valid(self, analyzer, tmp_path):
        """Test that generated HTML is valid."""
        for failure in SAMPLE_FAILURES:
            analyzer.add_failure(failure)
        
        dashboard = ClusterDashboard(analyzer, output_dir=tmp_path)
        html_content = dashboard.generate_html()
        
        # Check basic HTML structure
        assert "<!DOCTYPE html>" in html_content
        assert "<html" in html_content
        assert "</html>" in html_content
        assert "<head>" in html_content
        assert "<body>" in html_content

    def test_dashboard_contains_cluster_data(self, analyzer, tmp_path):
        """Test that dashboard contains cluster information."""
        for failure in SAMPLE_FAILURES:
            analyzer.add_failure(failure)
        
        dashboard = ClusterDashboard(analyzer, output_dir=tmp_path)
        html_content = dashboard.generate_html()
        
        # Check for cluster data in HTML
        assert "ValueError" in html_content
        assert "data_processor" in html_content
        assert "failure_count" in html_content or "Failures" in html_content

    def test_dashboard_responsive_design(self, analyzer, tmp_path):
        """Test that dashboard has responsive design elements."""
        for failure in SAMPLE_FAILURES:
            analyzer.add_failure(failure)
        
        dashboard = ClusterDashboard(analyzer, output_dir=tmp_path)
        html_content = dashboard.generate_html()
        
        # Check for responsive design indicators
        assert "viewport" in html_content
        assert "width=device-width" in html_content

class TestOrchestratorIntegration:
    """Test integration with orchestrator auto-fix."""

    def test_auto_fix_triggered_on_cluster(self, analyzer, mock_orchestrator):
        """Test that auto-fix is triggered when cluster is formed."""
        integration = ClusterOrchestratorIntegration(
            analyzer=analyzer,
            orchestrator=mock_orchestrator
        )
        
        # Add failures to trigger cluster and auto-fix
        for _ in range(5):
            analyzer.add_failure(SAMPLE_FAILURES[0])
        
        integration.process_clusters()
        
        # Verify auto-fix was called
        mock_orchestrator.auto_fix.assert_called_once()

    def test_auto_fix_with_cluster_data(self, analyzer, mock_orchestrator):
        """Test that auto-fix receives cluster data."""
        integration = ClusterOrchestratorIntegration(
            analyzer=analyzer,
            orchestrator=mock_orchestrator
        )
        
        for _ in range(5):
            analyzer.add_failure(SAMPLE_FAILURES[0])
        
        integration.process_clusters()
        
        # Check that auto-fix was called with cluster data
        call_args = mock_orchestrator.auto_fix.call_args
        assert call_args is not None
        cluster_data = call_args[0][0]
        assert "error_type" in cluster_data
        assert "module" in cluster_data
        assert "failure_count" in cluster_data

    def test_auto_fix_handles_multiple_clusters(self, analyzer, mock_orchestrator):
        """Test that auto-fix handles multiple clusters."""
        integration = ClusterOrchestratorIntegration(
            analyzer=analyzer,
            orchestrator=mock_orchestrator
        )
        
        # Create multiple clusters
        for _ in range(5):
            analyzer.add_failure(SAMPLE_FAILURES[0])
            analyzer.add_failure(SAMPLE_FAILURES[2])
        
        integration.process_clusters()
        
        # Verify auto-fix was called for each cluster
        assert mock_orchestrator.auto_fix.call_count >= 2

    def test_auto_fix_error_handling(self, analyzer):
        """Test that auto-fix errors are handled gracefully."""
        failing_orchestrator = Mock(spec=Orchestrator)
        failing_orchestrator.auto_fix = MagicMock(side_effect=Exception("Auto-fix failed"))
        
        integration = ClusterOrchestratorIntegration(
            analyzer=analyzer,
            orchestrator=failing_orchestrator
        )
        
        for _ in range(5):
            analyzer.add_failure(SAMPLE_FAILURES[0])
        
        # Should not raise exception
        integration.process_clusters()

    def test_integration_cluster_priority(self, analyzer, mock_orchestrator):
        """Test that clusters are processed in priority order."""
        integration = ClusterOrchestratorIntegration(
            analyzer=analyzer,
            orchestrator=mock_orchestrator
        )
        
        # Add high priority cluster (recent, many failures)
        for _ in range(5):
            failure = SAMPLE_FAILURES[0].copy()
            failure["timestamp"] = datetime.now()
            analyzer.add_failure(failure)
        
        # Add low priority cluster (older, fewer failures)
        for _ in range(3):
            failure = SAMPLE_FAILURES[2].copy()
            failure["timestamp"] = datetime.now() - timedelta(days=7)
            analyzer.add_failure(failure)
        
        integration.process_clusters()
        
        # High priority cluster should be processed first
        call_args_list = mock_orchestrator.auto_fix.call_args_list
        if len(call_args_list) >= 2:
            first_cluster = call_args_list[0][0][0]
            second_cluster = call_args_list[1][0][0]
            assert first_cluster["failure_count"] >= second_cluster["failure_count"]

    def test_integration_dashboard_update(self, analyzer, mock_orchestrator, tmp_path):
        """Test that dashboard is updated after auto-fix."""
        integration = ClusterOrchestratorIntegration(
            analyzer=analyzer,
            orchestrator=mock_orchestrator,
            dashboard_output_dir=tmp_path
        )
        
        for _ in range(5):
            analyzer.add_failure(SAMPLE_FAILURES[0])
        
        integration.process_clusters()
        
        # Check that dashboard was updated
        html_files = list(tmp_path.glob("*.html"))
        assert len(html_files) > 0

if __name__ == "__main__":
    pytest.main([__file__, "-v"])