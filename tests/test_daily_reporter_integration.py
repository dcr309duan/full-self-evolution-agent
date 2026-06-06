import os
import sys
import json
import tempfile
import shutil
from datetime import datetime
from pathlib import Path

# Ensure the project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.daily_reporter import DailyReporter


def test_daily_reporter_integration():
    """
    Integration test: Simulate a full evolution cycle, call DailyReporter.run(),
    and verify that a report file is generated in reports/daily/ with the expected content.
    """
    # Create a temporary directory to simulate the project root
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create the reports/daily/ directory inside the temp dir
        reports_daily = Path(tmpdir) / "reports" / "daily"
        reports_daily.mkdir(parents=True, exist_ok=True)

        # Simulate evolution state
        capabilities = [
            {"name": "web_scraper", "version": "1.2.0", "description": "Scrapes web pages"},
            {"name": "data_analyzer", "version": "2.0.1", "description": "Analyzes data sets"},
        ]
        cycle_number = 42
        successful_goals = [
            "Implemented web_scraper v1.2.0 with rate limiting",
            "Refactored data_analyzer to use pandas",
        ]
        failed_goals = [
            "Integrate with external API (blocked by auth)",
        ]

        # Instantiate DailyReporter with the temp dir as project root
        reporter = DailyReporter(
            capabilities=capabilities,
            cycle_number=cycle_number,
            successful_goals=successful_goals,
            failed_goals=failed_goals,
            project_root=str(tmpdir),
        )

        # Run the reporter
        reporter.run()

        # Verify that a report file was created in reports/daily/
        report_files = list(reports_daily.glob("*.md"))
        assert len(report_files) > 0, "No report file was created in reports/daily/"

        # Get the most recently created file (should be the one just generated)
        report_file = max(report_files, key=os.path.getctime)

        # Read the report content
        with open(report_file, "r", encoding="utf-8") as f:
            content = f.read()

        # Verify expected sections exist
        assert "# Daily Evolution Report" in content, "Missing main header"
        assert f"Cycle {cycle_number}" in content, "Missing cycle number"
        assert "## Completed Goals" in content, "Missing Completed Goals section"
        assert "## Failed Goals" in content, "Missing Failed Goals section"
        assert "## Insights & Analysis" in content, "Missing Insights section"
        assert "## Next Steps" in content, "Missing Next Steps section"

        # Verify successful goals are listed
        for goal in successful_goals:
            assert goal in content, f"Successful goal '{goal}' not found in report"

        # Verify failed goals are listed
        for goal in failed_goals:
            assert goal in content, f"Failed goal '{goal}' not found in report"

        # Verify capabilities are mentioned
        for cap in capabilities:
            assert cap["name"] in content, f"Capability '{cap['name']}' not found in report"

        # Verify the file name contains the date
        today_str = datetime.now().strftime("%Y-%m-%d")
        assert today_str in report_file.name, f"Report filename does not contain today's date ({today_str})"

        # Cleanup is automatic via TemporaryDirectory


def test_daily_reporter_integration_no_failed_goals():
    """
    Integration test: Simulate a cycle with no failed goals.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        reports_daily = Path(tmpdir) / "reports" / "daily"
        reports_daily.mkdir(parents=True, exist_ok=True)

        capabilities = [
            {"name": "test_runner", "version": "1.0.0", "description": "Runs tests"},
        ]
        cycle_number = 10
        successful_goals = ["All tests pass"]
        failed_goals = []

        reporter = DailyReporter(
            capabilities=capabilities,
            cycle_number=cycle_number,
            successful_goals=successful_goals,
            failed_goals=failed_goals,
            project_root=str(tmpdir),
        )
        reporter.run()

        report_files = list(reports_daily.glob("*.md"))
        assert len(report_files) > 0, "No report file created"

        report_file = max(report_files, key=os.path.getctime)
        with open(report_file, "r", encoding="utf-8") as f:
            content = f.read()

        assert "## Failed Goals" in content, "Failed Goals section missing"
        assert "No failed goals this cycle." in content or "None" in content, \
            "Should indicate no failed goals"


def test_daily_reporter_integration_empty_capabilities():
    """
    Integration test: Simulate a cycle with no capabilities.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        reports_daily = Path(tmpdir) / "reports" / "daily"
        reports_daily.mkdir(parents=True, exist_ok=True)

        reporter = DailyReporter(
            capabilities=[],
            cycle_number=1,
            successful_goals=["Initial setup"],
            failed_goals=[],
            project_root=str(tmpdir),
        )
        reporter.run()

        report_files = list(reports_daily.glob("*.md"))
        assert len(report_files) > 0, "No report file created"

        report_file = max(report_files, key=os.path.getctime)
        with open(report_file, "r", encoding="utf-8") as f:
            content = f.read()

        assert "## Completed Goals" in content
        assert "Initial setup" in content
        assert "No capabilities registered yet." in content or "capabilities" in content.lower()