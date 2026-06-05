"""End-to-end tests for schema alignment across reflection modules.

Tests cover:
1. Registering canonical schemas for all three modules
2. Generating sample outputs from reflection_parser, goal_generator, and failure_analysis
3. Validating each output against its schema
4. Testing conversion between formats
5. Running a full reflection cycle and confirming no schema mismatches
"""

import json
import pytest
from typing import Dict, Any, List
from datetime import datetime

# Import the modules under test
from reflection_parser import ReflectionParser, ReflectionOutput
from goal_generator import GoalGenerator, GoalOutput
from failure_analysis import FailureAnalyzer, FailureAnalysisOutput
from schema_registry import SchemaRegistry, SchemaValidator


@pytest.fixture
def schema_registry():
    """Create a schema registry with canonical schemas for all modules."""
    registry = SchemaRegistry()
    
    # Register reflection parser schema
    registry.register_schema(
        module="reflection_parser",
        schema={
            "type": "object",
            "properties": {
                "reflection_id": {"type": "string"},
                "timestamp": {"type": "string", "format": "datetime"},
                "content": {"type": "string"},
                "metadata": {
                    "type": "object",
                    "properties": {
                        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                        "category": {"type": "string"},
                        "tags": {"type": "array", "items": {"type": "string"}}
                    },
                    "required": ["confidence", "category"]
                }
            },
            "required": ["reflection_id", "timestamp", "content", "metadata"]
        }
    )
    
    # Register goal generator schema
    registry.register_schema(
        module="goal_generator",
        schema={
            "type": "object",
            "properties": {
                "goal_id": {"type": "string"},
                "description": {"type": "string"},
                "priority": {"type": "integer", "minimum": 1, "maximum": 5},
                "status": {"type": "string", "enum": ["pending", "active", "completed", "failed"]},
                "constraints": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "type": {"type": "string"},
                            "value": {"type": "string"}
                        },
                        "required": ["type", "value"]
                    }
                },
                "created_at": {"type": "string", "format": "datetime"}
            },
            "required": ["goal_id", "description", "priority", "status", "created_at"]
        }
    )
    
    # Register failure analysis schema
    registry.register_schema(
        module="failure_analysis",
        schema={
            "type": "object",
            "properties": {
                "analysis_id": {"type": "string"},
                "failure_type": {"type": "string"},
                "severity": {"type": "string", "enum": ["low", "medium", "high", "critical"]},
                "root_cause": {"type": "string"},
                "affected_components": {
                    "type": "array",
                    "items": {"type": "string"}
                },
                "recommendations": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "action": {"type": "string"},
                            "priority": {"type": "integer", "minimum": 1, "maximum": 5},
                            "expected_impact": {"type": "string"}
                        },
                        "required": ["action", "priority"]
                    }
                },
                "analyzed_at": {"type": "string", "format": "datetime"}
            },
            "required": ["analysis_id", "failure_type", "severity", "root_cause", "analyzed_at"]
        }
    )
    
    return registry


@pytest.fixture
def sample_reflection_output() -> ReflectionOutput:
    """Generate a sample reflection parser output."""
    parser = ReflectionParser()
    return parser.parse(
        content="System encountered unexpected behavior during task execution",
        metadata={
            "confidence": 0.85,
            "category": "execution_error",
            "tags": ["runtime", "unexpected_behavior"]
        }
    )


@pytest.fixture
def sample_goal_output() -> GoalOutput:
    """Generate a sample goal generator output."""
    generator = GoalGenerator()
    return generator.generate_goal(
        description="Improve error handling for database connections",
        priority=3,
        constraints=[
            {"type": "timeframe", "value": "2 weeks"},
            {"type": "resource", "value": "development_team"}
        ]
    )


@pytest.fixture
def sample_failure_output() -> FailureAnalysisOutput:
    """Generate a sample failure analysis output."""
    analyzer = FailureAnalyzer()
    return analyzer.analyze(
        failure_type="database_connection_timeout",
        severity="high",
        root_cause="Connection pool exhausted due to slow queries",
        affected_components=["database_service", "query_optimizer"],
        recommendations=[
            {
                "action": "Increase connection pool size",
                "priority": 4,
                "expected_impact": "Reduce connection wait times"
            },
            {
                "action": "Optimize slow queries",
                "priority": 3,
                "expected_impact": "Reduce connection hold time"
            }
        ]
    )


class TestSchemaRegistration:
    """Test schema registration for all modules."""
    
    def test_register_all_schemas(self, schema_registry):
        """Test that all three module schemas are registered."""
        assert schema_registry.has_schema("reflection_parser")
        assert schema_registry.has_schema("goal_generator")
        assert schema_registry.has_schema("failure_analysis")
    
    def test_schema_uniqueness(self, schema_registry):
        """Test that schemas are unique across modules."""
        schemas = [
            schema_registry.get_schema("reflection_parser"),
            schema_registry.get_schema("goal_generator"),
            schema_registry.get_schema("failure_analysis")
        ]
        # Each schema should have different required fields
        required_fields = [set(s["required"]) for s in schemas]
        assert all(len(fields) > 0 for fields in required_fields)
        # At least some fields should differ
        assert not all(f == required_fields[0] for f in required_fields[1:])


class TestOutputValidation:
    """Test validation of outputs against their schemas."""
    
    def test_validate_reflection_output(self, schema_registry, sample_reflection_output):
        """Test reflection parser output validates against its schema."""
        validator = SchemaValidator(schema_registry)
        output_dict = sample_reflection_output.to_dict()
        is_valid, errors = validator.validate("reflection_parser", output_dict)
        assert is_valid, f"Validation failed: {errors}"
        assert len(errors) == 0
    
    def test_validate_goal_output(self, schema_registry, sample_goal_output):
        """Test goal generator output validates against its schema."""
        validator = SchemaValidator(schema_registry)
        output_dict = sample_goal_output.to_dict()
        is_valid, errors = validator.validate("goal_generator", output_dict)
        assert is_valid, f"Validation failed: {errors}"
        assert len(errors) == 0
    
    def test_validate_failure_output(self, schema_registry, sample_failure_output):
        """Test failure analysis output validates against its schema."""
        validator = SchemaValidator(schema_registry)
        output_dict = sample_failure_output.to_dict()
        is_valid, errors = validator.validate("failure_analysis", output_dict)
        assert is_valid, f"Validation failed: {errors}"
        assert len(errors) == 0
    
    def test_invalid_output_detected(self, schema_registry):
        """Test that invalid outputs are correctly rejected."""
        validator = SchemaValidator(schema_registry)
        invalid_output = {
            "reflection_id": "test-123",
            # Missing required 'timestamp' field
            "content": "Test content",
            "metadata": {
                "confidence": 0.5,
                # Missing required 'category' field
            }
        }
        is_valid, errors = validator.validate("reflection_parser", invalid_output)
        assert not is_valid
        assert len(errors) > 0


class TestFormatConversion:
    """Test conversion between different output formats."""
    
    def test_reflection_to_json(self, sample_reflection_output):
        """Test reflection output converts to JSON correctly."""
        json_str = sample_reflection_output.to_json()
        parsed = json.loads(json_str)
        assert parsed["reflection_id"] == sample_reflection_output.reflection_id
        assert parsed["content"] == sample_reflection_output.content
        assert parsed["metadata"]["confidence"] == sample_reflection_output.metadata["confidence"]
    
    def test_goal_to_dict_roundtrip(self, sample_goal_output):
        """Test goal output dict conversion is reversible."""
        output_dict = sample_goal_output.to_dict()
        restored = GoalOutput.from_dict(output_dict)
        assert restored.goal_id == sample_goal_output.goal_id
        assert restored.description == sample_goal_output.description
        assert restored.priority == sample_goal_output.priority
        assert restored.status == sample_goal_output.status
    
    def test_failure_to_json_schema(self, schema_registry, sample_failure_output):
        """Test failure output JSON conforms to schema."""
        json_str = sample_failure_output.to_json()
        parsed = json.loads(json_str)
        validator = SchemaValidator(schema_registry)
        is_valid, errors = validator.validate("failure_analysis", parsed)
        assert is_valid, f"JSON output failed schema validation: {errors}"
    
    def test_cross_format_conversion(self, sample_reflection_output, sample_goal_output, sample_failure_output):
        """Test converting between different output formats."""
        # Convert all to dict
        reflection_dict = sample_reflection_output.to_dict()
        goal_dict = sample_goal_output.to_dict()
        failure_dict = sample_failure_output.to_dict()
        
        # Convert all to JSON
        reflection_json = sample_reflection_output.to_json()
        goal_json = sample_goal_output.to_json()
        failure_json = sample_failure_output.to_json()
        
        # Verify JSON can be parsed back to dict
        assert json.loads(reflection_json) == reflection_dict
        assert json.loads(goal_json) == goal_dict
        assert json.loads(failure_json) == failure_dict


class TestFullReflectionCycle:
    """Test a complete reflection cycle with schema alignment."""
    
    @pytest.fixture
    def reflection_cycle_outputs(self):
        """Simulate a full reflection cycle producing outputs from all modules."""
        cycle_outputs = []
        
        # Phase 1: Reflection parsing
        parser = ReflectionParser()
        reflection = parser.parse(
            content="System performance degraded after deploying new caching layer",
            metadata={
                "confidence": 0.92,
                "category": "performance_regression",
                "tags": ["caching", "performance", "deployment"]
            }
        )
        cycle_outputs.append(("reflection_parser", reflection))
        
        # Phase 2: Goal generation based on reflection
        generator = GoalGenerator()
        goal = generator.generate_goal(
            description="Optimize caching layer configuration",
            priority=4,
            constraints=[
                {"type": "performance_target", "value": "response_time_under_100ms"},
                {"type": "compatibility", "value": "backward_compatible"}
            ]
        )
        cycle_outputs.append(("goal_generator", goal))
        
        # Phase 3: Failure analysis
        analyzer = FailureAnalyzer()
        failure = analyzer.analyze(
            failure_type="cache_miss_avalanche",
            severity="high",
            root_cause="Aggressive cache eviction policy causing cascade failures",
            affected_components=["cache_service", "api_gateway", "database"],
            recommendations=[
                {
                    "action": "Implement gradual cache eviction",
                    "priority": 5,
                    "expected_impact": "Prevent cascade failures"
                },
                {
                    "action": "Add cache warming mechanism",
                    "priority": 4,
                    "expected_impact": "Reduce cold start impact"
                }
            ]
        )
        cycle_outputs.append(("failure_analysis", failure))
        
        return cycle_outputs
    
    def test_cycle_schema_alignment(self, schema_registry, reflection_cycle_outputs):
        """Test that all outputs in the cycle align with their schemas."""
        validator = SchemaValidator(schema_registry)
        
        for module_name, output in reflection_cycle_outputs:
            output_dict = output.to_dict()
            is_valid, errors = validator.validate(module_name, output_dict)
            assert is_valid, (
                f"Schema mismatch in {module_name}: {errors}\n"
                f"Output: {json.dumps(output_dict, indent=2)}"
            )
    
    def test_cycle_data_consistency(self, reflection_cycle_outputs):
        """Test data consistency across the reflection cycle."""
        # Extract outputs
        reflection = reflection_cycle_outputs[0][1]
        goal = reflection_cycle_outputs[1][1]
        failure = reflection_cycle_outputs[2][1]
        
        # Verify timestamps are in order
        assert reflection.timestamp <= goal.created_at
        assert goal.created_at <= failure.analyzed_at
        
        # Verify tags from reflection appear in affected components
        reflection_tags = reflection.metadata.get("tags", [])
        failure_components = failure.affected_components
        # At least one tag should relate to affected components
        related_tags = [tag for tag in reflection_tags if any(
            tag.lower() in comp.lower() for comp in failure_components
        )]
        assert len(related_tags) > 0, (
            f"No relationship between reflection tags {reflection_tags} "
            f"and failure components {failure_components}"
        )
    
    def test_cycle_no_schema_mismatches(self, schema_registry, reflection_cycle_outputs):
        """Test that the full cycle produces no schema mismatches."""
        validator = SchemaValidator(schema_registry)
        mismatches = []
        
        for module_name, output in reflection_cycle_outputs:
            output_dict = output.to_dict()
            is_valid, errors = validator.validate(module_name, output_dict)
            if not is_valid:
                mismatches.append({
                    "module": module_name,
                    "errors": errors,
                    "output": output_dict
                })
        
        assert len(mismatches) == 0, (
            f"Found {len(mismatches)} schema mismatches in reflection cycle:\n"
            + "\n".join(
                f"  - {m['module']}: {m['errors']}"
                for m in mismatches
            )
        )
    
    def test_cycle_format_consistency(self, reflection_cycle_outputs):
        """Test format consistency across the reflection cycle."""
        # Convert all outputs to JSON
        json_outputs = []
        for _, output in reflection_cycle_outputs:
            json_str = output.to_json()
            parsed = json.loads(json_str)
            json_outputs.append(parsed)
        
        # Verify all outputs have required fields
        for output in json_outputs:
            assert "id" in output or any(
                key.endswith("_id") for key in output.keys()
            ), "Output missing identifier field"
            assert "timestamp" in output or any(
                key.endswith("_at") for key in output.keys()
            ), "Output missing timestamp field"
        
        # Verify outputs can be serialized to a single JSON structure
        cycle_data = {
            "reflection": json_outputs[0],
            "goal": json_outputs[1],
            "failure_analysis": json_outputs[2]
        }
        serialized = json.dumps(cycle_data)
        deserialized = json.loads(serialized)
        assert deserialized == cycle_data, "JSON serialization roundtrip failed"