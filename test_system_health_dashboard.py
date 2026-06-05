import pytest
import threading
import time
import os
import tempfile
import json
from unittest.mock import patch, MagicMock
from system_health_dashboard import (
    ConflictDetector,
    UnderutilizedScanner,
    Dashboard,
    WebServer,
    PerformanceDataInjector,
    FileWriteSimulator
)

# Fixtures for temporary directories and files
@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir

@pytest.fixture
def conflict_detector():
    return ConflictDetector()

@pytest.fixture
def underutilized_scanner():
    return UnderutilizedScanner()

@pytest.fixture
def dashboard():
    return Dashboard()

@pytest.fixture
def web_server():
    return WebServer(port=8080)

# Test 1: Simulate two modules with conflicting file writes and verify conflict detector catches it
def test_conflicting_file_writes_detected(conflict_detector, temp_dir):
    # Create two modules that write to the same file
    file_path = os.path.join(temp_dir, "shared_config.txt")
    
    # Simulate module A writing
    conflict_detector.register_write("ModuleA", file_path)
    # Simulate module B writing
    conflict_detector.register_write("ModuleB", file_path)
    
    # Check for conflicts
    conflicts = conflict_detector.detect_conflicts()
    
    assert len(conflicts) == 1
    assert conflicts[0]["file"] == file_path
    assert "ModuleA" in conflicts[0]["modules"]
    assert "ModuleB" in conflicts[0]["modules"]

# Test 2: Create an orphan capability and verify underutilized scanner flags it
def test_orphan_capability_detected(underutilized_scanner):
    # Register a capability that is never used
    underutilized_scanner.register_capability("OrphanFeature", usage_count=0)
    # Register a well-used capability
    underutilized_scanner.register_capability("PopularFeature", usage_count=100)
    
    # Scan for underutilized capabilities (threshold: usage < 5)
    orphans = underutilized_scanner.scan(threshold=5)
    
    assert len(orphans) == 1
    assert orphans[0]["name"] == "OrphanFeature"
    assert orphans[0]["usage_count"] == 0

# Test 3: Inject fake performance data and verify dashboard renders correct charts
def test_dashboard_renders_performance_charts(dashboard):
    # Inject fake performance data
    fake_data = {
        "cpu_usage": [45.2, 50.1, 48.7],
        "memory_usage": [1024, 1088, 1056],
        "disk_io": [150, 200, 180]
    }
    
    dashboard.inject_performance_data(fake_data)
    
    # Render charts (assuming dashboard generates chart data in JSON format)
    chart_data = dashboard.render_charts()
    
    # Verify CPU chart data matches injected data
    assert "cpu_usage" in chart_data
    assert chart_data["cpu_usage"] == fake_data["cpu_usage"]
    
    # Verify memory chart data
    assert "memory_usage" in chart_data
    assert chart_data["memory_usage"] == fake_data["memory_usage"]
    
    # Verify disk I/O chart data
    assert "disk_io" in chart_data
    assert chart_data["disk_io"] == fake_data["disk_io"]

# Test 4: Test that the web server starts and serves valid HTML
def test_web_server_serves_valid_html(web_server):
    # Start the web server in a separate thread
    server_thread = threading.Thread(target=web_server.start, daemon=True)
    server_thread.start()
    time.sleep(0.5)  # Allow server to initialize
    
    # Make a request to the server
    import requests
    try:
        response = requests.get("http://localhost:8080/")
        assert response.status_code == 200
        # Check that response contains valid HTML structure
        assert "<!DOCTYPE html>" in response.text
        assert "<html" in response.text
        assert "</html>" in response.text
        # Check for common dashboard elements
        assert "System Health Dashboard" in response.text or "Dashboard" in response.text
    finally:
        # Clean up: stop the server
        web_server.stop()

# Additional helper tests to ensure components work together
def test_integration_scenario(conflict_detector, underutilized_scanner, dashboard, temp_dir):
    """Full integration test combining multiple components."""
    # Simulate conflicting writes
    file_path = os.path.join(temp_dir, "conflict.txt")
    conflict_detector.register_write("ModuleX", file_path)
    conflict_detector.register_write("ModuleY", file_path)
    
    # Create orphan capability
    underutilized_scanner.register_capability("LegacyFeature", usage_count=1)
    underutilized_scanner.register_capability("ActiveFeature", usage_count=50)
    
    # Inject performance data
    perf_data = {
        "cpu_usage": [30.0, 35.5, 40.2],
        "memory_usage": [2048, 2100, 2150]
    }
    dashboard.inject_performance_data(perf_data)
    
    # Verify all detections
    conflicts = conflict_detector.detect_conflicts()
    assert len(conflicts) == 1
    
    orphans = underutilized_scanner.scan(threshold=5)
    assert len(orphans) == 1
    assert orphans[0]["name"] == "LegacyFeature"
    
    chart_data = dashboard.render_charts()
    assert chart_data["cpu_usage"] == perf_data["cpu_usage"]