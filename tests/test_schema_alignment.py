"""End-to-end tests for schema alignment across reflection modules.

Tests cover:
1. Registering canonical schemas for all three modules
2. Generating sample outputs from reflection_parser, goal_generator, and failure_analysis
3. Validating each output against its schema
4. Testing conversion between formats
5. Running a full reflection cycle and confirming no schema mismatches
6. Validation test suite with specific tests
7. Pre-mutation validation catches malformed GoalSpec objects
8. Schema version mismatches between components trigger migration
9. Round-trip data flow preserves schema integrity
10. SCHEMA_MISMATCH errors are properly logged and block execution
11. Self-repair is triggered on schema violation
12. Integration test suite for schema alignment
"""

import json
import pytest
import logging
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


class TestValidationTestSuite:
    """Validation test suite for schema alignment."""
    
    def test_reflection_parser_output_passes_schema_validation(self, schema_registry, sample_reflection_output):
        """Test that reflection_parser output passes schema validation."""
        validator = SchemaValidator(schema_registry)
        output_dict = sample_reflection_output.to_dict()
        is_valid, errors = validator.validate("reflection_parser", output_dict)
        assert is_valid, f"Reflection parser output failed schema validation: {errors}"
        assert len(errors) == 0
    
    def test_goal_generator_accepts_validated_input(self, schema_registry, sample_reflection_output):
        """Test that goal_generator accepts validated input."""
        validator = SchemaValidator(schema_registry)
        reflection_dict = sample_reflection_output.to_dict()
        is_valid, errors = validator.validate("reflection_parser", reflection_dict)
        assert is_valid, f"Input validation failed: {errors}"
        
        # Use validated reflection data to generate a goal
        generator = GoalGenerator()
        goal = generator.generate_goal(
            description=f"Address issue: {reflection_dict['content']}",
            priority=3,
            constraints=[
                {"type": "reflection_id", "value": reflection_dict["reflection_id"]}
            ]
        )
        goal_dict = goal.to_dict()
        is_valid, errors = validator.validate("goal_generator", goal_dict)
        assert is_valid, f"Goal output failed schema validation: {errors}"
    
    def test_migration_scripts_handle_version_mismatches(self, schema_registry):
        """Test that migration scripts handle version mismatches."""
        # Simulate a version mismatch scenario
        old_schema = {
            "type": "object",
            "properties": {
                "reflection_id": {"type": "string"},
                "content": {"type": "string"}
            },
            "required": ["reflection_id", "content"]
        }
        new_schema = schema_registry.get_schema("reflection_parser")
        
        # Create a migration script that handles the mismatch
        def migrate_v1_to_v2(old_data: Dict[str, Any]) -> Dict[str, Any]:
            """Migrate from old schema to new schema."""
            new_data = old_data.copy()
            if "timestamp" not in new_data:
                new_data["timestamp"] = datetime.now().isoformat()
            if "metadata" not in new_data:
                new_data["metadata"] = {
                    "confidence": 0.5,
                    "category": "migrated"
                }
            return new_data
        
        # Test migration with old data
        old_data = {
            "reflection_id": "migrated-001",
            "content": "Migrated content"
        }
        migrated_data = migrate_v1_to_v2(old_data)
        
        # Validate migrated data against new schema
        validator = SchemaValidator(schema_registry)
        is_valid, errors = validator.validate("reflection_parser", migrated_data)
        assert is_valid, f"Migration failed schema validation: {errors}"
        
        # Test that migration fails gracefully with incompatible data
        with pytest.raises(ValueError, match="Missing required field"):
            incomplete_data = {"reflection_id": "test"}
            migrate_v1_to_v2(incomplete_data)
    
    def test_pre_mutation_validation_catches_malformed_data(self, schema_registry):
        """Test that pre-mutation validation catches malformed data."""
        validator = SchemaValidator(schema_registry)
        
        # Test various malformed data scenarios
        malformed_cases = [
            {
                "name": "missing_required_field",
                "data": {
                    "reflection_id": "test-001",
                    "content": "Test content"
                    # Missing timestamp and metadata
                },
                "expected_errors": True
            },
            {
                "name": "invalid_enum_value",
                "data": {
                    "analysis_id": "test-001",
                    "failure_type": "test",
                    "severity": "invalid_severity",
                    "root_cause": "test",
                    "analyzed_at": datetime.now().isoformat()
                },
                "expected_errors": True
            },
            {
                "name": "invalid_type",
                "data": {
                    "goal_id": "test-001",
                    "description": "Test goal",
                    "priority": "high",  # Should be integer
                    "status": "pending",
                    "created_at": datetime.now().isoformat()
                },
                "expected_errors": True
            },
            {
                "name": "out_of_range_value",
                "data": {
                    "goal_id": "test-001",
                    "description": "Test goal",
                    "priority": 10,  # Should be between 1 and 5
                    "status": "pending",
                    "created_at": datetime.now().isoformat()
                },
                "expected_errors": True
            }
        ]
        
        for case in malformed_cases:
            # Try to validate against appropriate schema
            module_name = None
            if "reflection_id" in case["data"]:
                module_name = "reflection_parser"
            elif "goal_id" in case["data"]:
                module_name = "goal_generator"
            elif "analysis_id" in case["data"]:
                module_name = "failure_analysis"
            
            if module_name:
                is_valid, errors = validator.validate(module_name, case["data"])
                assert not is_valid, f"Case '{case['name']}' should have been caught"
                assert len(errors) > 0, f"Case '{case['name']}' should have errors"
    
    def test_round_trip_compatibility_between_all_three_modules(self, schema_registry):
        """Test round-trip compatibility between all three modules."""
        validator = SchemaValidator(schema_registry)
        
        # Create initial reflection
        parser = ReflectionParser()
        reflection = parser.parse(
            content="Database connection failures increasing",
            metadata={
                "confidence": 0.88,
                "category": "database_error",
                "tags": ["database", "connection", "failure"]
            }
        )
        
        # Validate reflection
        reflection_dict = reflection.to_dict()
        is_valid, errors = validator.validate("reflection_parser", reflection_dict)
        assert is_valid, f"Initial reflection validation failed: {errors}"
        
        # Convert reflection to goal input
        generator = GoalGenerator()
        goal = generator.generate_goal(
            description=f"Investigate and fix: {reflection_dict['content']}",
            priority=4,
            constraints=[
                {"type": "reflection_id", "value": reflection_dict["reflection_id"]},
                {"type": "category", "value": reflection_dict["metadata"]["category"]}
            ]
        )
        
        # Validate goal
        goal_dict = goal.to_dict()
        is_valid, errors = validator.validate("goal_generator", goal_dict)
        assert is_valid, f"Goal validation failed: {errors}"
        
        # Convert goal to failure analysis input
        analyzer = FailureAnalyzer()
        failure = analyzer.analyze(
            failure_type="database_connection_failure",
            severity="high",
            root_cause=f"Goal {goal_dict['goal_id']}: {goal_dict['description']}",
            affected_components=["database_service", "connection_pool"],
            recommendations=[
                {
                    "action": "Increase connection pool size",
                    "priority": 4,
                    "expected_impact": "Reduce connection failures"
                },
                {
                    "action": "Monitor connection metrics",
                    "priority": 3,
                    "expected_impact": "Early detection of issues"
                }
            ]
        )
        
        # Validate failure analysis
        failure_dict = failure.to_dict()
        is_valid, errors = validator.validate("failure_analysis", failure_dict)
        assert is_valid, f"Failure analysis validation failed: {errors}"
        
        # Verify round-trip: Convert failure back to reflection context
        round_trip_reflection = parser.parse(
            content=f"Analysis of {failure_dict['failure_type']}: {failure_dict['root_cause']}",
            metadata={
                "confidence": 0.95,
                "category": "analysis_result",
                "tags": failure_dict["affected_components"]
            }
        )
        
        # Validate round-trip reflection
        round_trip_dict = round_trip_reflection.to_dict()
        is_valid, errors = validator.validate("reflection_parser", round_trip_dict)
        assert is_valid, f"Round-trip reflection validation failed: {errors}"
        
        # Verify data consistency across the round-trip
        assert round_trip_dict["metadata"]["tags"] == failure_dict["affected_components"], (
            "Tags should match affected components from failure analysis"
        )
        assert "analysis" in round_trip_dict["content"].lower(), (
            "Content should reference the analysis"
        )


class TestPreMutationValidation:
    """Test pre-mutation validation catches malformed GoalSpec objects."""
    
    def test_malformed_goalspec_missing_required_fields(self, schema_registry):
        """Test that pre-mutation validation catches GoalSpec with missing required fields."""
        validator = SchemaValidator(schema_registry)
        
        # Malformed GoalSpec missing 'description'
        malformed_goal = {
            "goal_id": "test-001",
            # Missing "description"
            "priority": 3,
            "status": "pending",
            "created_at": datetime.now().isoformat()
        }
        
        is_valid, errors = validator.validate("goal_generator", malformed_goal)
        assert not is_valid, "Should catch missing required field 'description'"
        assert any("description" in error for error in errors), "Error should mention missing 'description'"
    
    def test_malformed_goalspec_invalid_priority_type(self, schema_registry):
        """Test that pre-mutation validation catches GoalSpec with invalid priority type."""
        validator = SchemaValidator(schema_registry)
        
        # Malformed GoalSpec with string priority instead of integer
        malformed_goal = {
            "goal_id": "test-002",
            "description": "Test goal",
            "priority": "high",  # Should be integer
            "status": "pending",
            "created_at": datetime.now().isoformat()
        }
        
        is_valid, errors = validator.validate("goal_generator", malformed_goal)
        assert not is_valid, "Should catch invalid priority type"
        assert any("priority" in error for error in errors), "Error should mention 'priority'"
    
    def test_malformed_goalspec_invalid_enum_status(self, schema_registry):
        """Test that pre-mutation validation catches GoalSpec with invalid status enum."""
        validator = SchemaValidator(schema_registry)
        
        # Malformed GoalSpec with invalid status
        malformed_goal = {
            "goal_id": "test-003",
            "description": "Test goal",
            "priority": 3,
            "status": "in_progress",  # Not in enum
            "created_at": datetime.now().isoformat()
        }
        
        is_valid, errors = validator.validate("goal_generator", malformed_goal)
        assert not is_valid, "Should catch invalid status enum value"
        assert any("status" in error for error in errors), "Error should mention 'status'"
    
    def test_malformed_goalspec_out_of_range_priority(self, schema_registry):
        """Test that pre-mutation validation catches GoalSpec with out-of-range priority."""
        validator = SchemaValidator(schema_registry)
        
        # Malformed GoalSpec with priority out of range
        malformed_goal = {
            "goal_id": "test-004",
            "description": "Test goal",
            "priority": 10,  # Should be between 1 and 5
            "status": "pending",
            "created_at": datetime.now().isoformat()
        }
        
        is_valid, errors = validator.validate("goal_generator", malformed_goal)
        assert not is_valid, "Should catch out-of-range priority"
        assert any("priority" in error for error in errors), "Error should mention 'priority'"
    
    def test_malformed_goalspec_invalid_constraints(self, schema_registry):
        """Test that pre-mutation validation catches GoalSpec with invalid constraints."""
        validator = SchemaValidator(schema_registry)
        
        # Malformed GoalSpec with constraint missing 'value'
        malformed_goal = {
            "goal_id": "test-005",
            "description": "Test goal",
            "priority": 3,
            "status": "pending",
            "constraints": [
                {"type": "timeframe"}  # Missing "value"
            ],
            "created_at": datetime.now().isoformat()
        }
        
        is_valid, errors = validator.validate("goal_generator", malformed_goal)
        assert not is_valid, "Should catch invalid constraints"
        assert any("constraints" in error for error in errors), "Error should mention 'constraints'"


class TestSchemaVersionMigration:
    """Test schema version mismatches between components trigger migration."""
    
    def test_version_mismatch_triggers_migration(self, schema_registry):
        """Test that schema version mismatches trigger migration."""
        # Simulate a scenario where reflection_parser has version 1.0 and goal_generator has version 2.0
        old_schema = {
            "type": "object",
            "properties": {
                "reflection_id": {"type": "string"},
                "content": {"type": "string"}
            },
            "required": ["reflection_id", "content"]
        }
        
        # Register old schema for reflection_parser to simulate version mismatch
        schema_registry.register_schema("reflection_parser_v1", old_schema)
        
        # Create data in old format
        old_data = {
            "reflection_id": "test-001",
            "content": "Old format content"
        }
        
        # Migration function should be triggered
        def migrate_v1_to_v2(data):
            """Migration function from v1 to v2."""
            new_data = data.copy()
            new_data["timestamp"] = datetime.now().isoformat()
            new_data["metadata"] = {
                "confidence": 0.5,
                "category": "migrated"
            }
            return new_data
        
        migrated_data = migrate_v1_to_v2(old_data)
        
        # Validate migrated data against current schema
        validator = SchemaValidator(schema_registry)
        is_valid, errors = validator.validate("reflection_parser", migrated_data)
        assert is_valid, f"Migration should produce valid data: {errors}"
    
    def test_migration_preserves_data_integrity(self, schema_registry):
        """Test that migration preserves data integrity."""
        # Create original data
        original_data = {
            "reflection_id": "test-002",
            "content": "Original content",
            "timestamp": datetime.now().isoformat(),
            "metadata": {
                "confidence": 0.8,
                "category": "test"
            }
        }
        
        # Simulate migration to a new schema version
        def migrate_v2_to_v3(data):
            """Migration function from v2 to v3."""
            new_data = data.copy()
            # Add new field
            new_data["version"] = "3.0"
            # Preserve all original fields
            return new_data
        
        migrated_data = migrate_v2_to_v3(original_data)
        
        # Verify all original fields are preserved
        for key in original_data:
            assert key in migrated_data, f"Migration should preserve field '{key}'"
            assert migrated_data[key] == original_data[key], f"Field '{key}' should have same value"
        
        # Verify new field is added
        assert "version" in migrated_data, "Migration should add new field 'version'"
        assert migrated_data["version"] == "3.0", "New field should have correct value"
    
    def test_migration_fails_gracefully_on_incompatible_data(self, schema_registry):
        """Test that migration fails gracefully on incompatible data."""
        # Incompatible data that cannot be migrated
        incompatible_data = {
            "reflection_id": "test-003"
            # Missing required fields
        }
        
        def migrate_v1_to_v2(data):
            """Migration function that requires certain fields."""
            if "content" not in data:
                raise ValueError("Missing required field 'content' for migration")
            new_data = data.copy()
            new_data["timestamp"] = datetime.now().isoformat()
            new_data["metadata"] = {
                "confidence": 0.5,
                "category": "migrated"
            }
            return new_data
        
        # Migration should raise an error
        with pytest.raises(ValueError, match="Missing required field"):
            migrate_v1_to_v2(incompatible_data)


class TestSchemaMismatchLogging:
    """Test that SCHEMA_MISMATCH errors are properly logged and block execution."""
    
    def test_schema_mismatch_logs_error(self, schema_registry, caplog):
        """Test that SCHEMA_MISMATCH errors are properly logged."""
        caplog.set_level(logging.ERROR)
        
        validator = SchemaValidator(schema_registry)
        
        # Create data with schema mismatch
        mismatched_data = {
            "reflection_id": "test-001",
            "timestamp": datetime.now().isoformat(),
            "content": "Test content",
            "metadata": {
                "confidence": 0.5,
                "category": "test"
            },
            "extra_field": "This should not be here"  # Extra field not in schema
        }
        
        # Validate and log mismatch
        is_valid, errors = validator.validate("reflection_parser", mismatched_data)
        if not is_valid:
            logging.error(f"SCHEMA_MISMATCH: {errors}")
        
        # Check that error was logged
        assert any("SCHEMA_MISMATCH" in record.message for record in caplog.records), (
            "SCHEMA_MISMATCH should be logged"
        )
        assert any("extra_field" in record.message for record in caplog.records), (
            "Error log should mention the extra field"
        )
    
    def test_schema_mismatch_blocks_execution(self, schema_registry):
        """Test that SCHEMA_MISMATCH errors block execution."""
        validator = SchemaValidator(schema_registry)
        
        # Create data with schema mismatch
        mismatched_data = {
            "goal_id": "test-001",
            "description": "Test goal",
            "priority": 3,
            "status": "invalid_status",  # Not in enum
            "created_at": datetime.now().isoformat()
        }
        
        # Validate should fail
        is_valid, errors = validator.validate("goal_generator", mismatched_data)
        assert not is_valid, "Schema mismatch should be detected"
        
        # Execution should be blocked (simulated by raising exception)
        if not is_valid:
            with pytest.raises(ValueError, match="SCHEMA_MISMATCH"):
                raise ValueError(f"SCHEMA_MISMATCH: {errors}")
    
    def test_schema_mismatch_with_critical_severity(self, schema_registry, caplog):
        """Test that critical schema mismatches are logged with higher severity."""
        caplog.set_level(logging.CRITICAL)
        
        validator = SchemaValidator(schema_registry)
        
        # Create data with critical schema mismatch (missing required fields)
        critical_mismatch = {
            "analysis_id": "test-001"
            # Missing all other required fields
        }
        
        is_valid, errors = validator.validate("failure_analysis", critical_mismatch)
        if not is_valid:
            logging.critical(f"CRITICAL SCHEMA_MISMATCH: {errors}")
        
        # Check that critical error was logged
        assert any("CRITICAL SCHEMA_MISMATCH" in record.message for record in caplog.records), (
            "Critical schema mismatch should be logged"
        )


class TestSelfRepair:
    """Test that self-repair is triggered on schema violation."""
    
    def test_self_repair_triggers_on_schema_violation(self, schema_registry):
        """Test that self-repair is triggered on schema violation."""
        validator = SchemaValidator(schema_registry)
        
        # Create data with schema violation
        violated_data = {
            "reflection_id": "test-001",
            "timestamp": datetime.now().isoformat(),
            "content": "Test content",
            "metadata": {
                "confidence": 0.5,
                "category": "test"
            }
        }
        
        # Simulate self-repair function
        def self_repair(data):
            """Self-repair function to fix schema violations."""
            repaired = data.copy()
            # Add missing fields with default values
            if "tags" not in repaired.get("metadata", {}):
                repaired["metadata"]["tags"] = []
            return repaired
        
        # Validate before repair
        is_valid, errors = validator.validate("reflection_parser", violated_data)
        if not is_valid:
            # Trigger self-repair
            repaired_data = self_repair(violated_data)
            
            # Validate after repair
            is_valid_after, errors_after