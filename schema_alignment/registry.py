"""Schema registry for storing and managing canonical JSON schemas.

This module provides a central registry for JSON schemas used across the
schema_alignment package, including schemas for reflection_parser output,
goal_generator input, and failure_analysis output. Supports versioning and
dynamic registration of new schemas.
"""

import json
from typing import Any, Dict, Optional, Set
from datetime import datetime


class SchemaRegistry:
    """A registry for managing canonical JSON schemas with versioning support.

    Stores schemas by name and version, allowing dynamic registration and
    retrieval. Provides methods to get the latest version of a schema or
    a specific version.
    """

    def __init__(self) -> None:
        """Initialize an empty schema registry."""
        self._schemas: Dict[str, Dict[str, Dict[str, Any]]] = {}
        self._latest_versions: Dict[str, str] = {}
        self._schema_names: Set[str] = set()

    def register_schema(
        self,
        name: str,
        schema: Dict[str, Any],
        version: Optional[str] = None,
        overwrite: bool = False,
    ) -> str:
        """Register a new schema or a new version of an existing schema.

        Args:
            name: The name of the schema (e.g., 'reflection_parser_output').
            schema: The JSON schema dictionary.
            version: Optional version string. If not provided, a timestamp-based
                version is generated.
            overwrite: If True, overwrite an existing version. Defaults to False.

        Returns:
            The version string assigned to the registered schema.

        Raises:
            ValueError: If the schema name already exists and overwrite is False,
                or if a specific version already exists and overwrite is False.
        """
        if version is None:
            version = datetime.utcnow().strftime("%Y%m%d%H%M%S%f")

        if name not in self._schemas:
            self._schemas[name] = {}
            self._schema_names.add(name)

        if version in self._schemas[name] and not overwrite:
            raise ValueError(
                f"Version '{version}' already exists for schema '{name}'. "
                "Use overwrite=True to replace it."
            )

        self._schemas[name][version] = schema
        self._latest_versions[name] = version
        return version

    def get_schema(
        self, name: str, version: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Retrieve a schema by name and optionally by version.

        Args:
            name: The name of the schema.
            version: Optional version string. If None, returns the latest version.

        Returns:
            The schema dictionary if found, or None if the schema or version
            does not exist.
        """
        if name not in self._schemas:
            return None

        if version is None:
            version = self._latest_versions.get(name)
            if version is None:
                return None

        return self._schemas[name].get(version)

    def get_latest_version(self, name: str) -> Optional[str]:
        """Get the latest version string for a given schema name.

        Args:
            name: The name of the schema.

        Returns:
            The latest version string, or None if the schema does not exist.
        """
        return self._latest_versions.get(name)

    def list_schemas(self) -> Set[str]:
        """List all registered schema names.

        Returns:
            A set of schema names currently registered.
        """
        return self._schema_names.copy()

    def list_versions(self, name: str) -> Set[str]:
        """List all versions for a given schema name.

        Args:
            name: The name of the schema.

        Returns:
            A set of version strings for the schema, or an empty set if the
            schema does not exist.
        """
        if name not in self._schemas:
            return set()
        return set(self._schemas[name].keys())

    def remove_schema(self, name: str, version: Optional[str] = None) -> bool:
        """Remove a schema or a specific version of a schema.

        Args:
            name: The name of the schema.
            version: Optional version string. If None, removes all versions
                of the schema. If specified, removes only that version.

        Returns:
            True if removal was successful, False if the schema or version
            does not exist.
        """
        if name not in self._schemas:
            return False

        if version is None:
            del self._schemas[name]
            self._schema_names.discard(name)
            self._latest_versions.pop(name, None)
            return True

        if version not in self._schemas[name]:
            return False

        del self._schemas[name][version]

        # Update latest version if we removed the current latest
        if self._latest_versions.get(name) == version:
            versions = list(self._schemas[name].keys())
            if versions:
                self._latest_versions[name] = versions[-1]
            else:
                del self._schemas[name]
                self._schema_names.discard(name)
                self._latest_versions.pop(name, None)

        return True

    def to_json(self, indent: int = 2) -> str:
        """Serialize the registry to a JSON string.

        Args:
            indent: Number of spaces for JSON indentation.

        Returns:
            A JSON string representation of the registry.
        """
        data = {
            "schemas": self._schemas,
            "latest_versions": self._latest_versions,
            "schema_names": list(self._schema_names),
        }
        return json.dumps(data, indent=indent)

    @classmethod
    def from_json(cls, json_str: str) -> "SchemaRegistry":
        """Create a SchemaRegistry instance from a JSON string.

        Args:
            json_str: A JSON string produced by to_json().

        Returns:
            A new SchemaRegistry instance with the deserialized data.
        """
        data = json.loads(json_str)
        registry = cls()
        registry._schemas = data["schemas"]
        registry._latest_versions = data["latest_versions"]
        registry._schema_names = set(data["schema_names"])
        return registry


# Predefined canonical schemas for the schema_alignment package

REFLECTION_PARSER_OUTPUT_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "ReflectionParserOutput",
    "type": "object",
    "properties": {
        "reflection_text": {"type": "string"},
        "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        "issues": {
            "type": "array",
            "items": {"type": "string"},
        },
        "timestamp": {"type": "string", "format": "date-time"},
    },
    "required": ["reflection_text", "confidence", "timestamp"],
}

GOAL_GENERATOR_INPUT_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "GoalGeneratorInput",
    "type": "object",
    "properties": {
        "context": {"type": "string"},
        "constraints": {
            "type": "array",
            "items": {"type": "string"},
        },
        "preferences": {
            "type": "object",
            "properties": {
                "priority": {"type": "string", "enum": ["low", "medium", "high"]},
                "deadline": {"type": "string", "format": "date-time"},
            },
            "required": ["priority"],
        },
    },
    "required": ["context", "constraints"],
}

FAILURE_ANALYSIS_OUTPUT_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "FailureAnalysisOutput",
    "type": "object",
    "properties": {
        "failure_type": {"type": "string"},
        "root_cause": {"type": "string"},
        "impact": {"type": "string"},
        "recommendations": {
            "type": "array",
            "items": {"type": "string"},
        },
        "severity": {"type": "string", "enum": ["low", "medium", "high", "critical"]},
        "timestamp": {"type": "string", "format": "date-time"},
    },
    "required": ["failure_type", "root_cause", "severity", "timestamp"],
}


def create_default_registry() -> SchemaRegistry:
    """Create and return a SchemaRegistry pre-populated with canonical schemas.

    Returns:
        A SchemaRegistry instance with the default schemas registered.
    """
    registry = SchemaRegistry()
    registry.register_schema(
        "reflection_parser_output",
        REFLECTION_PARSER_OUTPUT_SCHEMA,
        version="1.0.0",
    )
    registry.register_schema(
        "goal_generator_input",
        GOAL_GENERATOR_INPUT_SCHEMA,
        version="1.0.0",
    )
    registry.register_schema(
        "failure_analysis_output",
        FAILURE_ANALYSIS_OUTPUT_SCHEMA,
        version="1.0.0",
    )
    return registry