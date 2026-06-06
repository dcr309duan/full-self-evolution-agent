import unittest
import os
import json
import tempfile
import shutil
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta

# Adjust import path as needed
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.daily_reporter import DailyReporter


class TestDailyReporterIntegration(unittest.TestCase):
    """Integration tests for DailyReporter module."""

    def setUp(self):
        """Set up test environment with temporary directories."""
        self.test_dir = tempfile.mkdtemp()
        self.reports_dir = os.path.join(self.test_dir, 'reports', 'daily')
        os.makedirs(self.reports_dir, exist_ok=True)
        
        # Create mock evolution state
        self.mock_state = {
            'capabilities': [
                {'name': 'test_capability_1', 'success_rate': 0.85, 'last_used': '2024-01-15'},
                {'name': 'test_capability_2', 'success_rate': 0.92, 'last_used': '2024-01-14'},
                {'name': 'test_capability_3', 'success_rate': 0.45, 'last_used': '2024-01-10'}
            ],
            'failures': [
                {'capability': 'test_capability_3', 'error': 'TimeoutError', 'timestamp': '2024-01-15T10:30:00'},
                {'capability': 'test_capability_1', 'error': 'ValueError', 'timestamp': '2024-01-15T11:00:00'}
            ],
            'insights': [
                {'id': 'insight_001', 'content': 'Test insight about performance', 'confidence': 0.8},
                {'id': 'insight_002', 'content': 'Another test insight', 'confidence': 0.6}
            ],
            'metrics': {
                'total_goals_completed': 15,
                'total_capabilities': 10,
                'active_capabilities': 8,
                'average_success_rate': 0.74
            },
            'cycle_number': 42
        }

    def tearDown(self):
        """Clean up temporary directories."""
        shutil.rmtree(self.test_dir)

    def _create_reporter(self, state_override=None):
        """Helper to create DailyReporter with mock state."""
        state = state_override or self.mock_state
        reporter = DailyReporter(
            state=state,
            reports_dir=self.reports_dir
        )
        return reporter

    def test_report_creation_and_file_exists(self):
        """Test that generate_report creates a file in reports/daily/."""
        reporter = self._create_reporter()
        report_path = reporter.generate_report()
        
        # Verify file exists
        self.assertTrue(os.path.exists(report_path), "Report file was not created")
        self.assertTrue(report_path.startswith(self.reports_dir), 
                       f"Report path {report_path} is not in reports/daily/ directory")

    def test_report_contains_required_sections(self):
        """Test that generated report contains all required sections."""
        reporter = self._create_reporter()
        report_path = reporter.generate_report()
        
        with open(report_path, 'r') as f:
            content = f.read()
        
        required_sections = [
            'Daily Report',
            'Capabilities',
            'Failures',
            'Insights',
            'Metrics',
            'Summary',
            'Cycle Number'
        ]
        
        for section in required_sections:
            self.assertIn(section, content, 
                         f"Required section '{section}' not found in report")

    def test_report_content_accuracy(self):
        """Test that report content accurately reflects the state."""
        reporter = self._create_reporter()
        report_path = reporter.generate_report()
        
        with open(report_path, 'r') as f:
            content = f.read()
        
        # Check capabilities are listed
        for cap in self.mock_state['capabilities']:
            self.assertIn(cap['name'], content, 
                         f"Capability '{cap['name']}' not found in report")
        
        # Check failures are listed
        for failure in self.mock_state['failures']:
            self.assertIn(failure['error'], content,
                         f"Failure error '{failure['error']}' not found in report")
        
        # Check insights are listed
        for insight in self.mock_state['insights']:
            self.assertIn(insight['content'], content,
                         f"Insight '{insight['content']}' not found in report")
        
        # Check metrics are included
        for key, value in self.mock_state['metrics'].items():
            self.assertIn(str(value), content,
                         f"Metric value '{value}' not found in report")
        
        # Check cycle number is included
        self.assertIn(str(self.mock_state['cycle_number']), content,
                     f"Cycle number '{self.mock_state['cycle_number']}' not found in report")

    def test_duplicate_report_prevention(self):
        """Test that duplicate reports for the same day are prevented."""
        reporter = self._create_reporter()
        
        # Generate first report
        first_report = reporter.generate_report()
        self.assertTrue(os.path.exists(first_report))
        
        # Attempt to generate second report for same day
        second_report = reporter.generate_report()
        
        # Should return the same path (prevent duplicate)
        self.assertEqual(first_report, second_report,
                        "Duplicate report prevention failed: different paths returned")
        
        # Verify only one report file exists
        report_files = [f for f in os.listdir(self.reports_dir) if f.endswith('.md')]
        self.assertEqual(len(report_files), 1,
                        f"Expected 1 report file, found {len(report_files)}")

    def test_different_day_allows_new_report(self):
        """Test that a new report is created for a different day."""
        reporter = self._create_reporter()
        
        # Mock today's date for first report
        with patch('core.daily_reporter.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2024, 1, 15, 12, 0, 0)
            mock_datetime.strftime = datetime.strftime
            first_report = reporter.generate_report()
        
        # Mock a different date for second report
        with patch('core.daily_reporter.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2024, 1, 16, 12, 0, 0)
            mock_datetime.strftime = datetime.strftime
            second_report = reporter.generate_report()
        
        # Should be different files
        self.assertNotEqual(first_report, second_report,
                          "Reports for different days should have different paths")
        
        # Verify two report files exist
        report_files = [f for f in os.listdir(self.reports_dir) if f.endswith('.md')]
        self.assertEqual(len(report_files), 2,
                        f"Expected 2 report files, found {len(report_files)}")

    def test_report_with_empty_state(self):
        """Test report generation with minimal/empty state."""
        empty_state = {
            'capabilities': [],
            'failures': [],
            'insights': [],
            'metrics': {},
            'cycle_number': 0
        }
        reporter = self._create_reporter(state_override=empty_state)
        report_path = reporter.generate_report()
        
        self.assertTrue(os.path.exists(report_path), 
                       "Report should be created even with empty state")
        
        with open(report_path, 'r') as f:
            content = f.read()
        
        # Should still contain basic sections
        self.assertIn('Daily Report', content)
        self.assertIn('Capabilities', content)
        self.assertIn('Failures', content)
        self.assertIn('Insights', content)
        self.assertIn('Cycle Number', content)

    def test_report_format_is_markdown(self):
        """Test that generated report is valid markdown."""
        reporter = self._create_reporter()
        report_path = reporter.generate_report()
        
        self.assertTrue(report_path.endswith('.md'),
                       f"Report file should be markdown (.md), got: {report_path}")
        
        with open(report_path, 'r') as f:
            content = f.read()
        
        # Check for markdown headers
        self.assertRegex(content, r'^#\s+', "Report should have markdown headers")
        
        # Check for list items if capabilities exist
        if self.mock_state['capabilities']:
            self.assertRegex(content, r'^- ', "Report should have markdown list items")

    def test_report_contains_timestamp(self):
        """Test that report contains a timestamp/date."""
        reporter = self._create_reporter()
        report_path = reporter.generate_report()
        
        with open(report_path, 'r') as f:
            content = f.read()
        
        # Check for date pattern (YYYY-MM-DD)
        date_pattern = r'\d{4}-\d{2}-\d{2}'
        self.assertRegex(content, date_pattern, 
                        "Report should contain a date timestamp")

    def test_report_file_is_valid_json(self):
        """Test that the generated report file can be parsed as valid JSON."""
        reporter = self._create_reporter()
        report_path = reporter.generate_report()
        
        with open(report_path, 'r') as f:
            content = f.read()
        
        # Attempt to parse as JSON
        try:
            report_data = json.loads(content)
            self.assertIsInstance(report_data, dict, "Report should be a JSON object")
            self.assertIn('date', report_data, "Report JSON should contain 'date' field")
            self.assertIn('capabilities', report_data, "Report JSON should contain 'capabilities' field")
            self.assertIn('failures', report_data, "Report JSON should contain 'failures' field")
            self.assertIn('insights', report_data, "Report JSON should contain 'insights' field")
            self.assertIn('metrics', report_data, "Report JSON should contain 'metrics' field")
            self.assertIn('cycle_number', report_data, "Report JSON should contain 'cycle_number' field")
        except json.JSONDecodeError:
            self.fail("Report file is not valid JSON")

    def test_report_file_contains_all_state_data(self):
        """Test that the report JSON contains all data from the mock state."""
        reporter = self._create_reporter()
        report_path = reporter.generate_report()
        
        with open(report_path, 'r') as f:
            report_data = json.load(f)
        
        # Verify capabilities match
        self.assertEqual(len(report_data['capabilities']), len(self.mock_state['capabilities']))
        for cap in self.mock_state['capabilities']:
            found = any(c['name'] == cap['name'] for c in report_data['capabilities'])
            self.assertTrue(found, f"Capability '{cap['name']}' missing from report")
        
        # Verify failures match
        self.assertEqual(len(report_data['failures']), len(self.mock_state['failures']))
        for failure in self.mock_state['failures']:
            found = any(f['error'] == failure['error'] for f in report_data['failures'])
            self.assertTrue(found, f"Failure '{failure['error']}' missing from report")
        
        # Verify insights match
        self.assertEqual(len(report_data['insights']), len(self.mock_state['insights']))
        for insight in self.mock_state['insights']:
            found = any(i['content'] == insight['content'] for i in report_data['insights'])
            self.assertTrue(found, f"Insight '{insight['content']}' missing from report")
        
        # Verify metrics match
        for key, value in self.mock_state['metrics'].items():
            self.assertEqual(report_data['metrics'][key], value,
                           f"Metric '{key}' value mismatch")
        
        # Verify cycle number matches
        self.assertEqual(report_data['cycle_number'], self.mock_state['cycle_number'],
                        f"Cycle number mismatch")

    def test_report_file_has_correct_date_format(self):
        """Test that the report date is in YYYY-MM-DD format."""
        reporter = self._create_reporter()
        report_path = reporter.generate_report()
        
        with open(report_path, 'r') as f:
            report_data = json.load(f)
        
        date_str = report_data['date']
        # Verify date format
        try:
            datetime.strptime(date_str, '%Y-%m-%d')
        except ValueError:
            self.fail(f"Date '{date_str}' is not in YYYY-MM-DD format")

    def test_report_file_is_not_empty(self):
        """Test that the generated report file is not empty."""
        reporter = self._create_reporter()
        report_path = reporter.generate_report()
        
        file_size = os.path.getsize(report_path)
        self.assertGreater(file_size, 0, "Report file should not be empty")

    def test_report_file_has_correct_extension(self):
        """Test that the report file has the correct .json extension."""
        reporter = self._create_reporter()
        report_path = reporter.generate_report()
        
        self.assertTrue(report_path.endswith('.json'),
                       f"Report file should have .json extension, got: {report_path}")

    def test_report_file_is_readable(self):
        """Test that the report file can be read without errors."""
        reporter = self._create_reporter()
        report_path = reporter.generate_report()
        
        try:
            with open(report_path, 'r') as f:
                f.read()
        except IOError:
            self.fail(f"Report file '{report_path}' could not be read")

    def test_report_file_contains_summary_section(self):
        """Test that the report JSON contains a summary section."""
        reporter = self._create_reporter()
        report_path = reporter.generate_report()
        
        with open(report_path, 'r') as f:
            report_data = json.load(f)
        
        self.assertIn('summary', report_data, "Report JSON should contain 'summary' field")
        self.assertIsInstance(report_data['summary'], str, "Summary should be a string")
        self.assertGreater(len(report_data['summary']), 0, "Summary should not be empty")


if __name__ == '__main__':
    unittest.main()