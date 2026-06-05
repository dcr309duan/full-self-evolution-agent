import pytest
import time
import json
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Dict, List, Tuple, Optional

# Import the module under test
from performance_monitor import (
    PerformanceMonitor,
    MetricCollector,
    SlidingWindow,
    FailurePatternAnalyzer,
    OptimizationGoalGenerator,
    DashboardReportGenerator
)

class TestMetricCollectionAndAggregation:
    """Integration tests for metric collection and aggregation functionality."""
    
    @pytest.fixture
    def metric_collector(self):
        return MetricCollector()
    
    def test_collect_single_metric(self, metric_collector):
        """Test collecting a single metric value."""
        metric_collector.collect("response_time", 150.0, tags={"endpoint": "/api/users"})
        metrics = metric_collector.get_metrics("response_time")
        assert len(metrics) == 1
        assert metrics[0]["value"] == 150.0
        assert metrics[0]["tags"]["endpoint"] == "/api/users"
    
    def test_collect_multiple_metrics(self, metric_collector):
        """Test collecting multiple metric types."""
        metrics_data = [
            ("response_time", 120.0),
            ("cpu_usage", 45.5),
            ("memory_usage", 1024.0),
            ("error_rate", 0.02)
        ]
        for name, value in metrics_data:
            metric_collector.collect(name, value)
        
        for name, _ in metrics_data:
            assert len(metric_collector.get_metrics(name)) > 0
    
    def test_aggregation_basic(self, metric_collector):
        """Test basic aggregation functions."""
        values = [100.0, 200.0, 300.0, 400.0, 500.0]
        for v in values:
            metric_collector.collect("test_metric", v)
        
        aggregation = metric_collector.aggregate("test_metric")
        assert aggregation["count"] == 5
        assert aggregation["sum"] == 1500.0
        assert aggregation["avg"] == 300.0
        assert aggregation["min"] == 100.0
        assert aggregation["max"] == 500.0
    
    def test_aggregation_with_tags(self, metric_collector):
        """Test aggregation with tag filtering."""
        for i in range(10):
            metric_collector.collect(
                "response_time", 
                100.0 + i * 10, 
                tags={"endpoint": "/api/users", "method": "GET"}
            )
            metric_collector.collect(
                "response_time", 
                200.0 + i * 10, 
                tags={"endpoint": "/api/posts", "method": "POST"}
            )
        
        users_agg = metric_collector.aggregate("response_time", tags={"endpoint": "/api/users"})
        posts_agg = metric_collector.aggregate("response_time", tags={"endpoint": "/api/posts"})
        
        assert users_agg["avg"] == 145.0  # Average of 100-190
        assert posts_agg["avg"] == 245.0  # Average of 200-290
    
    def test_aggregation_time_range(self, metric_collector):
        """Test aggregation within a specific time range."""
        now = datetime.now()
        for i in range(5):
            metric_collector.collect(
                "test_metric", 
                float(i * 100),
                timestamp=now - timedelta(minutes=i)
            )
        
        # Aggregate last 3 minutes
        recent_agg = metric_collector.aggregate(
            "test_metric", 
            start_time=now - timedelta(minutes=3)
        )
        assert recent_agg["count"] == 3  # Should include 3 most recent
        assert recent_agg["avg"] == 200.0  # Average of 200, 300, 400


class TestSlidingWindowCalculations:
    """Integration tests for sliding window calculations."""
    
    @pytest.fixture
    def sliding_window(self):
        return SlidingWindow(window_size=10, interval=1)
    
    def test_sliding_window_basic(self, sliding_window):
        """Test basic sliding window operations."""
        for i in range(15):
            sliding_window.add(i * 10.0)
        
        assert len(sliding_window.get_window()) == 10
        assert sliding_window.get_window()[-1] == 140.0  # Last value
    
    def test_sliding_window_average(self, sliding_window):
        """Test sliding window average calculation."""
        for i in range(10):
            sliding_window.add(float(i * 10))
        
        assert sliding_window.average() == 45.0  # Average of 0-90
    
    def test_sliding_window_percentile(self, sliding_window):
        """Test percentile calculations on sliding window."""
        for i in range(10):
            sliding_window.add(float(i * 10))
        
        assert sliding_window.percentile(50) == 45.0  # Median
        assert sliding_window.percentile(90) == 81.0  # 90th percentile
        assert sliding_window.percentile(99) == 89.1  # 99th percentile
    
    def test_sliding_window_rate(self, sliding_window):
        """Test rate calculation over sliding window."""
        for i in range(10):
            sliding_window.add(float(i * 10))
        
        rate = sliding_window.rate()
        assert rate > 0  # Should have positive rate
    
    def test_sliding_window_rolling_aggregation(self, sliding_window):
        """Test rolling aggregation over sliding window."""
        # Simulate time-series data
        timestamps = [datetime.now() + timedelta(seconds=i) for i in range(20)]
        values = [100.0 + i * 5 for i in range(20)]
        
        for ts, val in zip(timestamps, values):
            sliding_window.add(val, timestamp=ts)
        
        rolling_avg = sliding_window.rolling_average(window=5)
        assert len(rolling_avg) > 0
        assert all(isinstance(x, float) for x in rolling_avg)


class TestFailurePatternPerformanceCorrelation:
    """Integration tests for correlation between failure patterns and performance."""
    
    @pytest.fixture
    def performance_monitor(self):
        return PerformanceMonitor()
    
    def test_correlation_detection(self, performance_monitor):
        """Test detecting correlation between failures and performance degradation."""
        # Simulate failure events
        failure_events = [
            {"timestamp": datetime.now() - timedelta(minutes=5), "type": "timeout", "count": 10},
            {"timestamp": datetime.now() - timedelta(minutes=4), "type": "error_500", "count": 5},
            {"timestamp": datetime.now() - timedelta(minutes=3), "type": "timeout", "count": 8},
        ]
        
        # Simulate performance metrics
        performance_metrics = [
            {"timestamp": datetime.now() - timedelta(minutes=5), "response_time": 500.0},
            {"timestamp": datetime.now() - timedelta(minutes=4), "response_time": 450.0},
            {"timestamp": datetime.now() - timedelta(minutes=3), "response_time": 480.0},
            {"timestamp": datetime.now() - timedelta(minutes=2), "response_time": 200.0},
            {"timestamp": datetime.now() - timedelta(minutes=1), "response_time": 150.0},
        ]
        
        correlation = performance_monitor.analyze_correlation(
            failure_events, performance_metrics
        )
        
        assert correlation["coefficient"] > 0.5  # Strong positive correlation
        assert correlation["significance"] < 0.05  # Statistically significant
    
    def test_pattern_recognition(self, performance_monitor):
        """Test recognizing failure patterns from performance data."""
        # Generate pattern data
        pattern_data = {
            "timeout_spikes": [
                {"time": datetime.now() - timedelta(hours=i), "count": 15 + (i % 3) * 10}
                for i in range(24)
            ],
            "error_rate": [
                {"time": datetime.now() - timedelta(hours=i), "rate": 0.05 + (i % 4) * 0.02}
                for i in range(24)
            ]
        }
        
        patterns = performance_monitor.recognize_patterns(pattern_data)
        assert len(patterns) > 0
        assert any(p["type"] == "periodic" for p in patterns)
    
    def test_correlation_with_lag(self, performance_monitor):
        """Test correlation with time lag between failure and performance impact."""
        # Failures occur before performance degradation
        failure_times = [datetime.now() - timedelta(minutes=10 + i) for i in range(5)]
        perf_times = [datetime.now() - timedelta(minutes=8 + i) for i in range(5)]
        
        failures = [{"timestamp": t, "type": "error"} for t in failure_times]
        metrics = [{"timestamp": t, "response_time": 400.0 + i * 50} for i, t in enumerate(perf_times)]
        
        correlation = performance_monitor.analyze_correlation_with_lag(failures, metrics)
        assert correlation["lag_minutes"] == 2  # Expected lag
        assert correlation["coefficient"] > 0.7


class TestOptimizationGoalGeneration:
    """Integration tests for optimization goal generation."""
    
    @pytest.fixture
    def goal_generator(self):
        return OptimizationGoalGenerator()
    
    def test_goal_generation_basic(self, goal_generator):
        """Test basic optimization goal generation."""
        performance_data = {
            "response_time": {"avg": 250.0, "p95": 500.0, "p99": 800.0},
            "error_rate": {"avg": 0.03, "max": 0.08},
            "cpu_usage": {"avg": 65.0, "max": 90.0}
        }
        
        goals = goal_generator.generate_goals(performance_data)
        assert len(goals) > 0
        assert any(g["metric"] == "response_time" for g in goals)
        assert any(g["metric"] == "error_rate" for g in goals)
    
    def test_goal_prioritization(self, goal_generator):
        """Test goal prioritization based on impact."""
        performance_data = {
            "response_time": {"avg": 500.0, "p95": 1000.0},
            "error_rate": {"avg": 0.10, "max": 0.25},
            "throughput": {"avg": 100, "min": 50}
        }
        
        goals = goal_generator.generate_goals(performance_data)
        priorities = [g["priority"] for g in goals]
        assert priorities == sorted(priorities)  # Should be sorted by priority
    
    def test_goal_specificity(self, goal_generator):
        """Test that generated goals are specific and measurable."""
        performance_data = {
            "response_time": {"avg": 300.0, "p95": 600.0},
            "error_rate": {"avg": 0.05}
        }
        
        goals = goal_generator.generate_goals(performance_data)
        for goal in goals:
            assert "target" in goal
            assert "current" in goal
            assert "threshold" in goal
            assert isinstance(goal["target"], (int, float))
    
    def test_goal_achievable_check(self, goal_generator):
        """Test checking if goals are achievable."""
        performance_data = {
            "response_time": {"avg": 200.0, "p95": 400.0},
            "error_rate": {"avg": 0.02}
        }
        
        goals = goal_generator.generate_goals(performance_data)
        for goal in goals:
            assert "achievable" in goal
            assert isinstance(goal["achievable"], bool)


class TestDashboardReportFormat:
    """Integration tests for dashboard report format and completeness."""
    
    @pytest.fixture
    def report_generator(self):
        return DashboardReportGenerator()
    
    def test_report_structure(self, report_generator):
        """Test that report has correct structure."""
        performance_data = {
            "metrics": {
                "response_time": {"avg": 200.0, "p95": 400.0},
                "error_rate": {"avg": 0.02}
            },
            "failures": [
                {"type": "timeout", "count": 5, "impact": "high"}
            ],
            "goals": [
                {"metric": "response_time", "target": 300.0, "current": 200.0}
            ]
        }
        
        report = report_generator.generate_report(performance_data)
        assert "summary" in report
        assert "metrics" in report
        assert "failures" in report
        assert "goals" in report
        assert "recommendations" in report
    
    def test_report_completeness(self, report_generator):
        """Test that report contains all required sections."""
        performance_data = {
            "metrics": {
                "response_time": {"avg": 200.0, "p95": 400.0, "p99": 600.0},
                "error_rate": {"avg": 0.02, "max": 0.05},
                "cpu_usage": {"avg": 60.0, "max": 85.0},
                "memory_usage": {"avg": 2048.0, "max": 4096.0},
                "throughput": {"avg": 500, "min": 300}
            },
            "failures": [
                {"type": "timeout", "count": 5, "impact": "high"},
                {"type": "error_500", "count": 3, "impact": "medium"}
            ],
            "goals": [
                {"metric": "response_time", "target": 300.0, "current": 200.0, "achievable": True},
                {"metric": "error_rate", "target": 0.01, "current": 0.02, "achievable": False}
            ]
        }
        
        report = report_generator.generate_report(performance_data)
        
        # Check summary section
        assert "overall_health" in report["summary"]
        assert "critical_issues" in report["summary"]
        assert "improvement_areas" in report["summary"]
        
        # Check metrics section
        for metric_name in performance_data["metrics"]:
            assert metric_name in report["metrics"]
            assert "current" in report["metrics"][metric_name]
            assert "trend" in report["metrics"][metric_name]
            assert "status" in report["metrics"][metric_name]
        
        # Check failures section
        assert "total_failures" in report["failures"]
        assert "failure_types" in report["failures"]
        assert "impact_analysis" in report["failures"]
        
        # Check goals section
        assert "progress" in report["goals"]
        assert "blockers" in report["goals"]
        assert "next_steps" in report["goals"]
        
        # Check recommendations
        assert len(report["recommendations"]) > 0
        for rec in report["recommendations"]:
            assert "priority" in rec
            assert "action" in rec
            assert "expected_impact" in rec
    
    def test_report_format_consistency(self, report_generator):
        """Test that report format is consistent across different data."""
        data_sets = [
            {"metrics": {"response_time": {"avg": 100.0}}, "failures": [], "goals": []},
            {"metrics": {"response_time": {"avg": 500.0}, "error_rate": {"avg": 0.05}}, 
             "failures": [{"type": "timeout", "count": 10}], 
             "goals": [{"metric": "response_time", "target": 300.0}]}
        ]
        
        reports = [report_generator.generate_report(data) for data in data_sets]
        
        # All reports should have same top-level keys
        common_keys = set(reports[0].keys())
        for report in reports[1:]:
            assert set(report.keys()) == common_keys
    
    def test_report_json_serializable(self, report_generator):
        """Test that report can be serialized to JSON."""
        performance_data = {
            "metrics": {"response_time": {"avg": 200.0}},
            "failures": [{"type": "timeout", "count": 5}],
            "goals": [{"metric": "response_time", "target": 300.0}]
        }
        
        report = report_generator.generate_report(performance_data)
        json_str = json.dumps(report, default=str)
        assert isinstance(json_str, str)
        
        # Verify it can be deserialized
        deserialized = json.loads(json_str)
        assert deserialized["metrics"]["response_time"]["avg"] == 200.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])