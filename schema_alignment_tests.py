import unittest
from unittest.mock import Mock, patch, MagicMock
import json
from datetime import datetime
from typing import Dict, List, Optional, Any

# Import the modules to test
from schema_alignment.reflection_parser import ReflectionParser
from schema_alignment.goal_generator import GoalGenerator
from schema_alignment.schema_validator import SchemaValidator
from schema_alignment.models import ReflectionSchema, GoalDirective, GoalSet

class TestReflectionParser(unittest.TestCase):
    """Unit tests for the ReflectionParser class that produces correct schema from reflection data."""

    def setUp(self):
        """Set up test fixtures."""
        self.parser = ReflectionParser()
        
        # Sample valid reflection data
        self.valid_reflection = {
            "id": "ref_001",
            "timestamp": "2024-01-15T10:30:00Z",
            "agent_id": "agent_alpha",
            "content": "I have completed the initial analysis of the dataset.",
            "confidence": 0.85,
            "metadata": {
                "source": "analysis_module",
                "version": "2.1.0"
            }
        }
        
        # Sample reflection with goals
        self.reflection_with_goals = {
            "id": "ref_002",
            "timestamp": "2024-01-15T11:00:00Z",
            "agent_id": "agent_beta",
            "content": "I need to explore the outliers in the dataset.",
            "confidence": 0.92,
            "goals": [
                {"type": "explore", "target": "outliers", "priority": "high"},
                {"type": "analyze", "target": "correlation_matrix", "priority": "medium"}
            ],
            "metadata": {
                "source": "exploration_module",
                "version": "2.1.0"
            }
        }

    def test_parse_valid_reflection(self):
        """Test that a valid reflection produces correct schema."""
        result = self.parser.parse(self.valid_reflection)
        
        self.assertIsInstance(result, ReflectionSchema)
        self.assertEqual(result.id, "ref_001")
        self.assertEqual(result.agent_id, "agent_alpha")
        self.assertEqual(result.content, "I have completed the initial analysis of the dataset.")
        self.assertEqual(result.confidence, 0.85)
        self.assertIsInstance(result.timestamp, datetime)
        self.assertEqual(result.metadata["source"], "analysis_module")

    def test_parse_reflection_with_goals(self):
        """Test that reflection with embedded goals is parsed correctly."""
        result = self.parser.parse(self.reflection_with_goals)
        
        self.assertEqual(len(result.goals), 2)
        self.assertEqual(result.goals[0].type, "explore")
        self.assertEqual(result.goals[0].target, "outliers")
        self.assertEqual(result.goals[1].priority, "medium")

    def test_parse_missing_optional_fields(self):
        """Test that missing optional fields are handled gracefully."""
        minimal_reflection = {
            "id": "ref_003",
            "timestamp": "2024-01-15T12:00:00Z",
            "agent_id": "agent_gamma",
            "content": "Minimal reflection."
        }
        
        result = self.parser.parse(minimal_reflection)
        
        self.assertEqual(result.confidence, 0.5)  # Default confidence
        self.assertEqual(result.metadata, {})  # Empty metadata
        self.assertEqual(result.goals, [])  # No goals

    def test_parse_invalid_timestamp(self):
        """Test that invalid timestamp raises appropriate error."""
        invalid_reflection = {
            "id": "ref_004",
            "timestamp": "not-a-timestamp",
            "agent_id": "agent_delta",
            "content": "Invalid timestamp test."
        }
        
        with self.assertRaises(ValueError):
            self.parser.parse(invalid_reflection)

    def test_parse_missing_required_fields(self):
        """Test that missing required fields raise appropriate error."""
        incomplete_reflection = {
            "id": "ref_005",
            "timestamp": "2024-01-15T13:00:00Z"
        }
        
        with self.assertRaises(KeyError):
            self.parser.parse(incomplete_reflection)

    def test_parse_empty_content(self):
        """Test that empty content is handled."""
        empty_content_reflection = {
            "id": "ref_006",
            "timestamp": "2024-01-15T14:00:00Z",
            "agent_id": "agent_epsilon",
            "content": ""
        }
        
        result = self.parser.parse(empty_content_reflection)
        self.assertEqual(result.content, "")


class TestGoalGenerator(unittest.TestCase):
    """Unit tests for the GoalGenerator class that correctly interprets directives."""

    def setUp(self):
        """Set up test fixtures."""
        self.generator = GoalGenerator()
        
        # Sample valid directives
        self.valid_directives = [
            GoalDirective(
                type="explore",
                target="anomalies",
                priority="high",
                constraints={"max_iterations": 100, "timeout": 300}
            ),
            GoalDirective(
                type="analyze",
                target="trends",
                priority="medium",
                constraints={"method": "regression"}
            )
        ]
        
        # Sample old format directives (backward compatibility)
        self.old_format_directives = [
            {
                "action": "explore",
                "subject": "anomalies",
                "importance": "high",
                "params": {"max_iterations": 100}
            }
        ]

    def test_generate_goals_from_directives(self):
        """Test that valid directives generate correct goals."""
        goals = self.generator.generate(self.valid_directives)
        
        self.assertIsInstance(goals, GoalSet)
        self.assertEqual(len(goals.goals), 2)
        self.assertEqual(goals.goals[0].type, "explore")
        self.assertEqual(goals.goals[0].target, "anomalies")
        self.assertEqual(goals.goals[0].priority, "high")

    def test_generate_goals_with_constraints(self):
        """Test that constraints are properly applied to generated goals."""
        goals = self.generator.generate(self.valid_directives)
        
        self.assertIn("max_iterations", goals.goals[0].constraints)
        self.assertEqual(goals.goals[0].constraints["max_iterations"], 100)
        self.assertIn("timeout", goals.goals[0].constraints)
        self.assertEqual(goals.goals[0].constraints["timeout"], 300)

    def test_generate_goals_empty_directives(self):
        """Test that empty directives produce empty goal set."""
        goals = self.generator.generate([])
        
        self.assertIsInstance(goals, GoalSet)
        self.assertEqual(len(goals.goals), 0)

    def test_generate_goals_rejected_exploration(self):
        """Test that rejected exploration directives are handled."""
        rejected_directive = GoalDirective(
            type="explore",
            target="sensitive_data",
            priority="high",
            constraints={},
            rejected=True,
            rejection_reason="Access denied: insufficient permissions"
        )
        
        goals = self.generator.generate([rejected_directive])
        
        self.assertEqual(len(goals.goals), 0)
        self.assertIn("rejected", goals.metadata)
        self.assertEqual(goals.metadata["rejected"][0]["reason"], 
                        "Access denied: insufficient permissions")

    def test_generate_goals_with_priority_override(self):
        """Test that priority overrides are applied correctly."""
        override_directives = [
            GoalDirective(
                type="explore",
                target="outliers",
                priority="low",
                constraints={},
                priority_override="critical"
            )
        ]
        
        goals = self.generator.generate(override_directives)
        
        self.assertEqual(goals.goals[0].priority, "critical")

    def test_generate_goals_with_dependencies(self):
        """Test that goal dependencies are correctly interpreted."""
        dependent_directives = [
            GoalDirective(
                type="analyze",
                target="results",
                priority="high",
                constraints={},
                depends_on=["explore_outliers"]
            )
        ]
        
        goals = self.generator.generate(dependent_directives)
        
        self.assertIn("depends_on", goals.goals[0].metadata)
        self.assertEqual(goals.goals[0].metadata["depends_on"], ["explore_outliers"])


class TestBackwardCompatibility(unittest.TestCase):
    """Unit tests for backward compatibility with old format."""

    def setUp(self):
        """Set up test fixtures with old format data."""
        self.parser = ReflectionParser()
        self.generator = GoalGenerator()
        
        # Old format reflection (pre-v2.0)
        self.old_format_reflection = {
            "reflection_id": "old_001",
            "created_at": "2023-06-15T08:00:00Z",
            "agent": "legacy_agent",
            "text": "Legacy reflection format.",
            "score": 0.75,
            "tags": ["analysis", "completed"]
        }
        
        # Old format goals
        self.old_format_goals = [
            {"action": "explore", "subject": "data_quality", "importance": "high"},
            {"action": "report", "subject": "findings", "importance": "medium"}
        ]

    def test_parse_old_format_reflection(self):
        """Test that old format reflection is correctly parsed."""
        result = self.parser.parse_legacy(self.old_format_reflection)
        
        self.assertIsInstance(result, ReflectionSchema)
        self.assertEqual(result.id, "old_001")
        self.assertEqual(result.agent_id, "legacy_agent")
        self.assertEqual(result.content, "Legacy reflection format.")
        self.assertEqual(result.confidence, 0.75)

    def test_convert_old_format_goals(self):
        """Test that old format goals are converted to new format."""
        goals = self.generator.convert_legacy(self.old_format_goals)
        
        self.assertEqual(len(goals), 2)
        self.assertEqual(goals[0].type, "explore")
        self.assertEqual(goals[0].target, "data_quality")
        self.assertEqual(goals[0].priority, "high")

    def test_old_format_with_missing_fields(self):
        """Test that old format with missing optional fields is handled."""
        minimal_old_format = {
            "reflection_id": "old_002",
            "created_at": "2023-06-15T09:00:00Z",
            "agent": "legacy_agent",
            "text": "Minimal legacy format."
        }
        
        result = self.parser.parse_legacy(minimal_old_format)
        
        self.assertEqual(result.confidence, 0.5)  # Default for missing score
        self.assertEqual(result.metadata.get("tags"), [])

    def test_old_format_goal_with_unknown_action(self):
        """Test that old format with unknown action is handled."""
        unknown_action_goals = [
            {"action": "unknown_action", "subject": "test", "importance": "low"}
        ]
        
        goals = self.generator.convert_legacy(unknown_action_goals)
        
        self.assertEqual(len(goals), 1)
        self.assertEqual(goals[0].type, "unknown_action")  # Pass through unknown actions


class TestEdgeCases(unittest.TestCase):
    """Unit tests for edge cases in schema alignment."""

    def setUp(self):
        """Set up test fixtures for edge cases."""
        self.parser = ReflectionParser()
        self.generator = GoalGenerator()
        self.validator = SchemaValidator()

    def test_empty_directives(self):
        """Test handling of completely empty directives."""
        goals = self.generator.generate([])
        
        self.assertIsInstance(goals, GoalSet)
        self.assertEqual(len(goals.goals), 0)
        self.assertEqual(goals.metadata, {})

    def test_rejected_exploration(self):
        """Test handling of rejected exploration directives."""
        rejected = GoalDirective(
            type="explore",
            target="restricted_area",
            priority="high",
            constraints={},
            rejected=True,
            rejection_reason="Security policy violation"
        )
        
        goals = self.generator.generate([rejected])
        
        self.assertEqual(len(goals.goals), 0)
        self.assertIn("rejected", goals.metadata)

    def test_malformed_json_input(self):
        """Test handling of malformed JSON input."""
        malformed_input = "{invalid json here}"
        
        with self.assertRaises(json.JSONDecodeError):
            self.parser.parse_json(malformed_input)

    def test_malformed_directive_structure(self):
        """Test handling of malformed directive structure."""
        malformed_directive = GoalDirective(
            type="",
            target="",
            priority="invalid",
            constraints=None
        )
        
        with self.assertRaises(ValueError):
            self.generator.validate_directive(malformed_directive)

    def test_extremely_long_content(self):
        """Test handling of extremely long content."""
        long_content = "A" * 100000  # 100k characters
        long_reflection = {
            "id": "ref_long",
            "timestamp": "2024-01-15T15:00:00Z",
            "agent_id": "agent_long",
            "content": long_content
        }
        
        result = self.parser.parse(long_reflection)
        self.assertEqual(len(result.content), 100000)

    def test_special_characters_in_content(self):
        """Test handling of special characters in content."""
        special_content = "Unicode: ñ, é, ü, 你好, 😊"
        special_reflection = {
            "id": "ref_special",
            "timestamp": "2024-01-15T16:00:00Z",
            "agent_id": "agent_special",
            "content": special_content
        }
        
        result = self.parser.parse(special_reflection)
        self.assertEqual(result.content, special_content)

    def test_none_values_in_directives(self):
        """Test handling of None values in directives."""
        none_directive = GoalDirective(
            type=None,
            target=None,
            priority=None,
            constraints=None
        )
        
        with self.assertRaises(ValueError):
            self.generator.validate_directive(none_directive)

    def test_duplicate_goal_targets(self):
        """Test handling of duplicate goal targets."""
        duplicate_directives = [
            GoalDirective(type="explore", target="outliers", priority="high", constraints={}),
            GoalDirective(type="explore", target="outliers", priority="medium", constraints={})
        ]
        
        goals = self.generator.generate(duplicate_directives)
        
        # Should keep the higher priority or merge
        self.assertEqual(len(goals.goals), 1)
        self.assertEqual(goals.goals[0].priority, "high")

    def test_circular_dependencies(self):
        """Test handling of circular dependencies in goals."""
        circular_directives = [
            GoalDirective(type="analyze", target="A", priority="high", constraints={}, depends_on=["B"]),
            GoalDirective(type="analyze", target="B", priority="high", constraints={}, depends_on=["A"])
        ]
        
        with self.assertRaises(ValueError):
            self.generator.generate(circular_directives)

    def test_invalid_priority_values(self):
        """Test handling of invalid priority values."""
        invalid_priority = GoalDirective(
            type="explore",
            target="test",
            priority="urgent",  # Not a valid priority
            constraints={}
        )
        
        with self.assertRaises(ValueError):
            self.generator.validate_directive(invalid_priority)

    def test_empty_reflection_list(self):
        """Test handling of empty reflection list."""
        reflections = []
        
        results = self.parser.parse_batch(reflections)
        
        self.assertEqual(len(results), 0)

    def test_mixed_format_reflections(self):
        """Test handling of mixed format reflections in batch."""
        mixed_reflections = [
            self.valid_reflection,
            self.old_format_reflection
        ]
        
        results = self.parser.parse_batch(mixed_reflections)
        
        self.assertEqual(len(results), 2)
        self.assertIsInstance(results[0], ReflectionSchema)
        self.assertIsInstance(results[1], ReflectionSchema)


if __name__ == '__main__':
    unittest.main()