"""Schema alignment layer for inter-module data validation.

Provides strict JSON schema validation, normalization, and versioned
migration for all data flowing between agent components.
"""

import logging
from typing import Any, Callable, Dict, List, Optional, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class SchemaViolation:
    field_name: str
    expected_type: str
    actual_type: str
    message: str


class SchemaRegistry:
    """Registry of versioned schemas for inter-module communication."""

    def __init__(self):
        self._schemas: Dict[str, Dict[str, Any]] = {}
        self._migrations: Dict[Tuple[str, int, int], Callable] = {}
        self._register_defaults()

    def _register_defaults(self):
        self._schemas["reflection_output"] = {
            "version": 2,
            "required_fields": {
                "current_assessment": str,
                "key_gaps": list,
                "next_priority": str,
                "timestamp": float,
                "cycle": int,
            },
            "optional_fields": {
                "meta_insights": list,
                "paradigm_shifts": list,
                "blind_spots": list,
                "metrics": dict,
            },
        }
        self._schemas["goal_spec"] = {
            "version": 2,
            "required_fields": {
                "description": str,
                "priority": int,
                "source": str,
                "timestamp": float,
            },
            "optional_fields": {
                "constraints": list,
                "prerequisites": list,
                "novelty_score": float,
                "source_domain": str,
            },
        }
        self._schemas["system_model_state"] = {
            "version": 1,
            "required_fields": {
                "components": dict,
                "interactions": list,
                "last_updated": float,
            },
            "optional_fields": {
                "schema_registry_version": int,
                "metadata": dict,
            },
        }
        self._schemas["mutation_request"] = {
            "version": 1,
            "required_fields": {
                "target_module": str,
                "strategy": str,
                "mutation_type": str,
            },
            "optional_fields": {
                "parameters": dict,
                "timeout_ms": float,
                "rollback_enabled": bool,
            },
        }

    def get_schema(self, name: str) -> Optional[Dict[str, Any]]:
        return self._schemas.get(name)

    def register_schema(self, name: str, schema: Dict[str, Any]):
        self._schemas[name] = schema

    def list_schemas(self) -> List[str]:
        return list(self._schemas.keys())


class SchemaValidator:
    """Validates data against registered schemas."""

    def __init__(self, registry: Optional[SchemaRegistry] = None):
        self.registry = registry or SchemaRegistry()

    def validate(self, data: Dict[str, Any], schema_name: str) -> Tuple[bool, List[SchemaViolation]]:
        schema = self.registry.get_schema(schema_name)
        if not schema:
            return False, [SchemaViolation("_schema", "registered", "unknown", f"Unknown schema: {schema_name}")]

        violations = []
        required = schema.get("required_fields", {})

        for field_name, expected_type in required.items():
            if field_name not in data:
                violations.append(SchemaViolation(
                    field_name, expected_type.__name__, "missing",
                    f"Required field '{field_name}' is missing"
                ))
            elif not isinstance(data[field_name], expected_type):
                violations.append(SchemaViolation(
                    field_name, expected_type.__name__, type(data[field_name]).__name__,
                    f"Field '{field_name}' has wrong type"
                ))

        return len(violations) == 0, violations

    def validate_and_normalize(self, data: Dict[str, Any], schema_name: str) -> Dict[str, Any]:
        schema = self.registry.get_schema(schema_name)
        if not schema:
            raise ValueError(f"Unknown schema: {schema_name}")

        is_valid, violations = self.validate(data, schema_name)
        if not is_valid:
            error_msgs = [v.message for v in violations]
            raise ValueError(f"Schema validation failed for '{schema_name}': {error_msgs}")

        normalized = {}
        required = schema.get("required_fields", {})
        optional = schema.get("optional_fields", {})

        for field_name in required:
            normalized[field_name] = data[field_name]

        for field_name, field_type in optional.items():
            if field_name in data:
                normalized[field_name] = data[field_name]

        return normalized

    def compare_schemas(self, output: Dict[str, Any], expected_schema: str) -> Dict[str, Any]:
        schema = self.registry.get_schema(expected_schema)
        if not schema:
            return {"match": False, "error": f"Unknown schema: {expected_schema}"}

        required_fields = set(schema.get("required_fields", {}).keys())
        optional_fields = set(schema.get("optional_fields", {}).keys())
        all_schema_fields = required_fields | optional_fields
        data_fields = set(output.keys())

        return {
            "match": required_fields.issubset(data_fields),
            "missing_required": list(required_fields - data_fields),
            "extra_fields": list(data_fields - all_schema_fields),
            "schema_only_fields": list(all_schema_fields - data_fields),
        }
