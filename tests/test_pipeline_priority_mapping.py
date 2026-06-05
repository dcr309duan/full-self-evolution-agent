import unittest
from unittest.mock import Mock, patch
from src.pipeline_priority_mapping import PriorityMapper, PriorityLevel, BugReport

class TestPipelinePriorityMapping(unittest.TestCase):
    """Test suite for validating priority mapping logic in pipeline components."""

    def setUp(self):
        """Initialize the PriorityMapper instance for testing."""
        self.mapper = PriorityMapper()

    def test_mutation_engine_failure_gets_critical_priority(self):
        """Test that mutation engine failures are assigned CRITICAL priority."""
        # Arrange
        component = "mutation_engine"
        error_message = "Mutation engine encountered a fatal error"
        
        # Act
        bug_report = self.mapper.map_failure(component, error_message)
        
        # Assert
        self.assertEqual(bug_report.priority, PriorityLevel.CRITICAL)
        self.assertEqual(bug_report.component, component)
        self.assertEqual(bug_report.error_message, error_message)

    def test_reflection_parser_failure_gets_high_priority(self):
        """Test that reflection parser failures are assigned HIGH priority."""
        # Arrange
        component = "reflection_parser"
        error_message = "Reflection parser failed to parse input"
        
        # Act
        bug_report = self.mapper.map_failure(component, error_message)
        
        # Assert
        self.assertEqual(bug_report.priority, PriorityLevel.HIGH)
        self.assertEqual(bug_report.component, component)
        self.assertEqual(bug_report.error_message, error_message)

    def test_strategy_selector_failure_gets_medium_priority(self):
        """Test that strategy selector failures are assigned MEDIUM priority."""
        # Arrange
        component = "strategy_selector"
        error_message = "Strategy selector could not determine appropriate strategy"
        
        # Act
        bug_report = self.mapper.map_failure(component, error_message)
        
        # Assert
        self.assertEqual(bug_report.priority, PriorityLevel.MEDIUM)
        self.assertEqual(bug_report.component, component)
        self.assertEqual(bug_report.error_message, error_message)

    def test_unknown_component_failure_gets_low_priority(self):
        """Test that unknown components are assigned LOW priority."""
        # Arrange
        component = "unknown_component"
        error_message = "An error occurred in an unrecognized component"
        
        # Act
        bug_report = self.mapper.map_failure(component, error_message)
        
        # Assert
        self.assertEqual(bug_report.priority, PriorityLevel.LOW)
        self.assertEqual(bug_report.component, component)
        self.assertEqual(bug_report.error_message, error_message)

    def test_multiple_simultaneous_failures_generate_separate_bug_reports(self):
        """Test that multiple simultaneous failures produce individual bug reports with correct priorities."""
        # Arrange
        failures = [
            ("mutation_engine", "Mutation engine failure"),
            ("reflection_parser", "Reflection parser failure"),
            ("strategy_selector", "Strategy selector failure"),
            ("unknown_component", "Unknown component failure")
        ]
        
        # Act
        bug_reports = self.mapper.map_multiple_failures(failures)
        
        # Assert
        self.assertEqual(len(bug_reports), len(failures))
        
        # Verify each bug report has the correct priority
        expected_priorities = [
            PriorityLevel.CRITICAL,
            PriorityLevel.HIGH,
            PriorityLevel.MEDIUM,
            PriorityLevel.LOW
        ]
        
        for i, (component, error_message) in enumerate(failures):
            bug_report = bug_reports[i]
            self.assertEqual(bug_report.component, component)
            self.assertEqual(bug_report.error_message, error_message)
            self.assertEqual(bug_report.priority, expected_priorities[i])
        
        # Verify that bug reports are independent (modifying one doesn't affect others)
        bug_reports[0].priority = PriorityLevel.LOW
        self.assertEqual(bug_reports[1].priority, PriorityLevel.HIGH)

    def test_case_insensitive_component_mapping(self):
        """Test that component names are matched case-insensitively."""
        # Arrange
        test_cases = [
            ("Mutation_Engine", PriorityLevel.CRITICAL),
            ("MUTATION_ENGINE", PriorityLevel.CRITICAL),
            ("Reflection_Parser", PriorityLevel.HIGH),
            ("REFLECTION_PARSER", PriorityLevel.HIGH),
            ("Strategy_Selector", PriorityLevel.MEDIUM),
            ("STRATEGY_SELECTOR", PriorityLevel.MEDIUM)
        ]
        
        # Act & Assert
        for component, expected_priority in test_cases:
            with self.subTest(component=component):
                bug_report = self.mapper.map_failure(component, "Test error")
                self.assertEqual(bug_report.priority, expected_priority)

    def test_empty_error_message_handling(self):
        """Test that empty error messages are handled gracefully."""
        # Arrange
        component = "mutation_engine"
        empty_error = ""
        
        # Act
        bug_report = self.mapper.map_failure(component, empty_error)
        
        # Assert
        self.assertEqual(bug_report.priority, PriorityLevel.CRITICAL)
        self.assertEqual(bug_report.error_message, "")

    def test_none_component_handling(self):
        """Test that None component is treated as unknown and gets LOW priority."""
        # Arrange
        component = None
        error_message = "Component is None"
        
        # Act
        bug_report = self.mapper.map_failure(component, error_message)
        
        # Assert
        self.assertEqual(bug_report.priority, PriorityLevel.LOW)
        self.assertEqual(bug_report.component, "unknown")

    def test_bug_report_immutability(self):
        """Test that BugReport objects are immutable after creation."""
        # Arrange
        bug_report = self.mapper.map_failure("mutation_engine", "Test error")
        
        # Act & Assert
        with self.assertRaises(AttributeError):
            bug_report.priority = PriorityLevel.LOW
        
        with self.assertRaises(AttributeError):
            bug_report.component = "changed"
        
        with self.assertRaises(AttributeError):
            bug_report.error_message = "changed"

if __name__ == '__main__':
    unittest.main()