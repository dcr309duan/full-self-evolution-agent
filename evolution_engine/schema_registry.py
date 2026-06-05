from typing import Dict, Any, List, Optional
from enum import Enum
import json
import os


class SchemaVersion(str, Enum):
    V1 = "1.0.0"


class FieldType(str, Enum):
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    ARRAY = "array"
    OBJECT = "object"
    NULL = "null"


class FieldRequirement(str, Enum):
    REQUIRED = "required"
    OPTIONAL = "optional"


class SchemaRegistry:
    """
    Schema registry that defines canonical JSON schemas for all inter-module data contracts.
    Each schema includes field names, types, required/optional status, and version number.
    """

    _schemas: Dict[str, Dict[str, Any]] = {}

    @classmethod
    def _build_field_schema(cls, name: str, field_type: FieldType, requirement: FieldRequirement, description: str = "") -> Dict[str, Any]:
        """Build a single field schema entry."""
        field_schema = {
            "name": name,
            "type": field_type.value,
            "required": requirement == FieldRequirement.REQUIRED,
            "description": description
        }
        return field_schema

    @classmethod
    def _build_object_schema(cls, fields: List[Dict[str, Any]], version: str = SchemaVersion.V1.value) -> Dict[str, Any]:
        """Build a complete object schema with versioning."""
        return {
            "version": version,
            "type": "object",
            "properties": {field["name"]: {
                "type": field["type"],
                "required": field["required"],
                "description": field.get("description", "")
            } for field in fields},
            "required": [field["name"] for field in fields if field["required"]]
        }

    @classmethod
    def _register_schema(cls, schema_name: str, schema: Dict[str, Any]) -> None:
        """Register a schema in the registry."""
        cls._schemas[schema_name] = schema

    @classmethod
    def initialize(cls) -> None:
        """Initialize all canonical schemas for inter-module data contracts."""

        # ============================================================================
        # Goal Generator Output Schema
        # ============================================================================
        goal_generator_output_fields = [
            cls._build_field_schema("goal_id", FieldType.STRING, FieldRequirement.REQUIRED, "Unique identifier for the goal"),
            cls._build_field_schema("goal_description", FieldType.STRING, FieldRequirement.REQUIRED, "Natural language description of the goal"),
            cls._build_field_schema("goal_type", FieldType.STRING, FieldRequirement.REQUIRED, "Type of goal (e.g., 'optimization', 'exploration', 'constraint')"),
            cls._build_field_schema("priority", FieldType.INTEGER, FieldRequirement.REQUIRED, "Priority level (1 = highest)"),
            cls._build_field_schema("constraints", FieldType.ARRAY, FieldRequirement.OPTIONAL, "List of constraint strings"),
            cls._build_field_schema("success_criteria", FieldType.ARRAY, FieldRequirement.REQUIRED, "Criteria for goal completion"),
            cls._build_field_schema("metadata", FieldType.OBJECT, FieldRequirement.OPTIONAL, "Additional metadata key-value pairs"),
            cls._build_field_schema("timestamp", FieldType.STRING, FieldRequirement.REQUIRED, "ISO 8601 timestamp of goal creation"),
        ]
        goal_generator_output_schema = cls._build_object_schema(goal_generator_output_fields)
        cls._register_schema("goal_generator_output", goal_generator_output_schema)

        # ============================================================================
        # Mutation Engine Input Schema
        # ============================================================================
        mutation_engine_input_fields = [
            cls._build_field_schema("goal_id", FieldType.STRING, FieldRequirement.REQUIRED, "Goal identifier to mutate towards"),
            cls._build_field_schema("current_code", FieldType.STRING, FieldRequirement.REQUIRED, "Current codebase state as string"),
            cls._build_field_schema("file_path", FieldType.STRING, FieldRequirement.REQUIRED, "Path to the file being mutated"),
            cls._build_field_schema("mutation_strategy", FieldType.STRING, FieldRequirement.OPTIONAL, "Specific mutation strategy to use"),
            cls._build_field_schema("context", FieldType.OBJECT, FieldRequirement.OPTIONAL, "Additional context for mutation"),
            cls._build_field_schema("max_mutations", FieldType.INTEGER, FieldRequirement.OPTIONAL, "Maximum number of mutations to generate"),
        ]
        mutation_engine_input_schema = cls._build_object_schema(mutation_engine_input_fields)
        cls._register_schema("mutation_engine_input", mutation_engine_input_schema)

        # ============================================================================
        # Mutation Engine Output Schema
        # ============================================================================
        mutation_engine_output_fields = [
            cls._build_field_schema("mutation_id", FieldType.STRING, FieldRequirement.REQUIRED, "Unique identifier for the mutation"),
            cls._build_field_schema("goal_id", FieldType.STRING, FieldRequirement.REQUIRED, "Associated goal identifier"),
            cls._build_field_schema("original_code", FieldType.STRING, FieldRequirement.REQUIRED, "Original code before mutation"),
            cls._build_field_schema("mutated_code", FieldType.STRING, FieldRequirement.REQUIRED, "Code after mutation"),
            cls._build_field_schema("file_path", FieldType.STRING, FieldRequirement.REQUIRED, "Path to the mutated file"),
            cls._build_field_schema("mutation_type", FieldType.STRING, FieldRequirement.REQUIRED, "Type of mutation applied"),
            cls._build_field_schema("diff", FieldType.STRING, FieldRequirement.OPTIONAL, "Unified diff of the mutation"),
            cls._build_field_schema("confidence_score", FieldType.FLOAT, FieldRequirement.OPTIONAL, "Confidence score of mutation success"),
            cls._build_field_schema("timestamp", FieldType.STRING, FieldRequirement.REQUIRED, "ISO 8601 timestamp of mutation"),
        ]
        mutation_engine_output_schema = cls._build_object_schema(mutation_engine_output_fields)
        cls._register_schema("mutation_engine_output", mutation_engine_output_schema)

        # ============================================================================
        # Test Runner Input Schema
        # ============================================================================
        test_runner_input_fields = [
            cls._build_field_schema("mutation_id", FieldType.STRING, FieldRequirement.REQUIRED, "Mutation identifier to test"),
            cls._build_field_schema("mutated_code", FieldType.STRING, FieldRequirement.REQUIRED, "Mutated code to test"),
            cls._build_field_schema("file_path", FieldType.STRING, FieldRequirement.REQUIRED, "Path to the file being tested"),
            cls._build_field_schema("test_command", FieldType.STRING, FieldRequirement.REQUIRED, "Command to run tests"),
            cls._build_field_schema("timeout_seconds", FieldType.INTEGER, FieldRequirement.OPTIONAL, "Timeout for test execution"),
            cls._build_field_schema("environment_variables", FieldType.OBJECT, FieldRequirement.OPTIONAL, "Environment variables for test run"),
        ]
        test_runner_input_schema = cls._build_object_schema(test_runner_input_fields)
        cls._register_schema("test_runner_input", test_runner_input_schema)

        # ============================================================================
        # Test Runner Output Schema
        # ============================================================================
        test_runner_output_fields = [
            cls._build_field_schema("mutation_id", FieldType.STRING, FieldRequirement.REQUIRED, "Associated mutation identifier"),
            cls._build_field_schema("test_passed", FieldType.BOOLEAN, FieldRequirement.REQUIRED, "Whether all tests passed"),
            cls._build_field_schema("test_output", FieldType.STRING, FieldRequirement.REQUIRED, "Full test output as string"),
            cls._build_field_schema("exit_code", FieldType.INTEGER, FieldRequirement.REQUIRED, "Test process exit code"),
            cls._build_field_schema("duration_seconds", FieldType.FLOAT, FieldRequirement.REQUIRED, "Test execution duration"),
            cls._build_field_schema("failed_tests", FieldType.ARRAY, FieldRequirement.OPTIONAL, "List of failed test names"),
            cls._build_field_schema("error_message", FieldType.STRING, FieldRequirement.OPTIONAL, "Error message if test execution failed"),
            cls._build_field_schema("timestamp", FieldType.STRING, FieldRequirement.REQUIRED, "ISO 8601 timestamp of test run"),
        ]
        test_runner_output_schema = cls._build_object_schema(test_runner_output_fields)
        cls._register_schema("test_runner_output", test_runner_output_schema)

        # ============================================================================
        # Reflection Parser Input Schema
        # ============================================================================
        reflection_parser_input_fields = [
            cls._build_field_schema("mutation_id", FieldType.STRING, FieldRequirement.REQUIRED, "Mutation identifier to reflect upon"),
            cls._build_field_schema("goal_id", FieldType.STRING, FieldRequirement.REQUIRED, "Associated goal identifier"),
            cls._build_field_schema("original_code", FieldType.STRING, FieldRequirement.REQUIRED, "Original code before mutation"),
            cls._build_field_schema("mutated_code", FieldType.STRING, FieldRequirement.REQUIRED, "Mutated code after mutation"),
            cls._build_field_schema("test_results", FieldType.OBJECT, FieldRequirement.REQUIRED, "Test runner output object"),
            cls._build_field_schema("diff", FieldType.STRING, FieldRequirement.OPTIONAL, "Unified diff of the mutation"),
            cls._build_field_schema("context", FieldType.OBJECT, FieldRequirement.OPTIONAL, "Additional context for reflection"),
        ]
        reflection_parser_input_schema = cls._build_object_schema(reflection_parser_input_fields)
        cls._register_schema("reflection_parser_input", reflection_parser_input_schema)

        # ============================================================================
        # Reflection Parser Output Schema
        # ============================================================================
        reflection_parser_output_fields = [
            cls._build_field_schema("mutation_id", FieldType.STRING, FieldRequirement.REQUIRED, "Associated mutation identifier"),
            cls._build_field_schema("goal_id", FieldType.STRING, FieldRequirement.REQUIRED, "Associated goal identifier"),
            cls._build_field_schema("reflection_summary", FieldType.STRING, FieldRequirement.REQUIRED, "Summary of the reflection analysis"),
            cls._build_field_schema("success_rating", FieldType.FLOAT, FieldRequirement.REQUIRED, "Rating of mutation success (0.0 to 1.0)"),
            cls._build_field_schema("lessons_learned", FieldType.ARRAY, FieldRequirement.REQUIRED, "List of lessons learned from mutation"),
            cls._build_field_schema("suggestions", FieldType.ARRAY, FieldRequirement.OPTIONAL, "Suggestions for future mutations"),
            cls._build_field_schema("code_quality_score", FieldType.FLOAT, FieldRequirement.OPTIONAL, "Code quality assessment score"),
            cls._build_field_schema("timestamp", FieldType.STRING, FieldRequirement.REQUIRED, "ISO 8601 timestamp of reflection"),
        ]
        reflection_parser_output_schema = cls._build_object_schema(reflection_parser_output_fields)
        cls._register_schema("reflection_parser_output", reflection_parser_output_schema)

    @classmethod
    def get_schema(cls, schema_name: str) -> Optional[Dict[str, Any]]:
        """Retrieve a schema by name."""
        return cls._schemas.get(schema_name)

    @classmethod
    def list_schemas(cls) -> List[str]:
        """List all registered schema names."""
        return list(cls._schemas.keys())

    @classmethod
    def validate(cls, schema_name: str, data: Dict[str, Any]) -> bool:
        """
        Basic validation of data against a registered schema.
        Checks required fields exist and have correct types.
        """
        schema = cls.get_schema(schema_name)
        if not schema:
            raise ValueError(f"Schema '{schema_name}' not found in registry")

        required_fields = schema.get("required", [])
        properties = schema.get("properties", {})

        # Check required fields exist
        for field in required_fields:
            if field not in data:
                return False

        # Check field types (basic type checking)
        for field_name, field_value in data.items():
            if field_name in properties:
                expected_type = properties[field_name]["type"]
                if expected_type == "string" and not isinstance(field_value, str):
                    return False
                elif expected_type == "integer" and not isinstance(field_value, int):
                    return False
                elif expected_type == "float" and not isinstance(field_value, (int, float)):
                    return False
                elif expected_type == "boolean" and not isinstance(field_value, bool):
                    return False
                elif expected_type == "array" and not isinstance(field_value, list):
                    return False
                elif expected_type == "object" and not isinstance(field_value, dict):
                    return False

        return True

    @classmethod
    def to_json(cls, schema_name: str) -> str:
        """Export a schema as JSON string."""
        schema = cls.get_schema(schema_name)
        if not schema:
            raise ValueError(f"Schema '{schema_name}' not found in registry")
        return json.dumps(schema, indent=2)

    @classmethod
    def export_all(cls) -> Dict[str, str]:
        """Export all schemas as JSON strings keyed by schema name."""
        return {name: json.dumps(schema, indent=2) for name, schema in cls._schemas.items()}


# Initialize schemas on module import
SchemaRegistry.initialize()