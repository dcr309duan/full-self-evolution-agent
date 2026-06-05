"""Shared JSON schema registry module for inter-module validation.

Provides:
- SchemaRegistry: stores canonical schemas for each module interface
- Validation functions using jsonschema
- Version tracking for each schema
- @validate_schema decorator for inter-module calls
- SchemaMismatchError exception
- register_schema() for adding/updating schemas with version bumps
"""

import json
import jsonschema
from jsonschema import validate, ValidationError
from functools import wraps
from typing import Any, Callable, Dict, Optional, Tuple
import threading


class SchemaMismatchError(Exception):
    """Exception raised when data does not match the expected schema."""
    def __init__(self, message: str, schema_name: str, version: str, errors: list):
        self.schema_name = schema_name
        self.version = version
        self.errors = errors
        super().__init__(f"Schema mismatch for '{schema_name}' v{version}: {message}")


class SchemaRegistry:
    """Thread-safe registry for storing and managing JSON schemas with versioning."""

    def __init__(self):
        self._lock = threading.RLock()
        self._schemas: Dict[str, Dict[str, Dict]] = {}  # schema_name -> {version: schema}

    def register_schema(self, name: str, schema: dict, version: Optional[str] = None) -> str:
        """Register or update a schema. If version is None, auto-increment or start at '1.0.0'.

        Args:
            name: Name of the schema (e.g., 'module_a.output')
            schema: JSON schema dictionary
            version: Optional version string. If None, auto-bumps.

        Returns:
            The version string assigned.
        """
        with self._lock:
            if name not in self._schemas:
                self._schemas[name] = {}
                if version is None:
                    version = "1.0.0"
                self._schemas[name][version] = schema
                return version

            # Schema exists
            if version is None:
                # Auto-bump: get latest version and increment minor
                existing_versions = sorted(self._schemas[name].keys(), key=lambda v: tuple(map(int, v.split('.'))))
                latest = existing_versions[-1]
                major, minor, patch = map(int, latest.split('.'))
                version = f"{major}.{minor + 1}.0"
            elif version in self._schemas[name]:
                # Explicit version already exists, overwrite (update)
                pass

            self._schemas[name][version] = schema
            return version

    def get_schema(self, name: str, version: Optional[str] = None) -> Tuple[dict, str]:
        """Retrieve a schema by name and optional version.

        Args:
            name: Schema name
            version: Version string. If None, returns the latest version.

        Returns:
            Tuple of (schema_dict, version_string)

        Raises:
            KeyError: If schema name not found or version not found.
        """
        with self._lock:
            if name not in self._schemas:
                raise KeyError(f"Schema '{name}' not found in registry.")

            versions = self._schemas[name]
            if version is None:
                # Return latest version (sorted by version tuple)
                sorted_versions = sorted(versions.keys(), key=lambda v: tuple(map(int, v.split('.'))))
                latest = sorted_versions[-1]
                return versions[latest], latest
            else:
                if version not in versions:
                    raise KeyError(f"Schema '{name}' version '{version}' not found.")
                return versions[version], version

    def list_schemas(self) -> Dict[str, list]:
        """Return a dict mapping schema names to list of available versions."""
        with self._lock:
            return {name: list(versions.keys()) for name, versions in self._schemas.items()}

    def validate(self, data: Any, schema_name: str, version: Optional[str] = None) -> None:
        """Validate data against a registered schema.

        Args:
            data: Data to validate
            schema_name: Name of the schema
            version: Version string (None for latest)

        Raises:
            SchemaMismatchError: If validation fails
            KeyError: If schema not found
        """
        schema, resolved_version = self.get_schema(schema_name, version)
        try:
            validate(instance=data, schema=schema)
        except ValidationError as e:
            # Collect all errors for better reporting
            errors = list(jsonschema.exceptions.iter_errors(data, schema))
            raise SchemaMismatchError(
                message=str(e),
                schema_name=schema_name,
                version=resolved_version,
                errors=[err.message for err in errors]
            ) from e

    def validate_json(self, json_str: str, schema_name: str, version: Optional[str] = None) -> None:
        """Validate a JSON string against a registered schema.

        Args:
            json_str: JSON string to validate
            schema_name: Name of the schema
            version: Version string (None for latest)

        Raises:
            SchemaMismatchError: If validation fails
            json.JSONDecodeError: If JSON is invalid
            KeyError: If schema not found
        """
        data = json.loads(json_str)
        self.validate(data, schema_name, version)


# Global singleton registry
_registry = SchemaRegistry()


def get_registry() -> SchemaRegistry:
    """Return the global SchemaRegistry instance."""
    return _registry


def validate_schema(schema_name: str, version: Optional[str] = None) -> Callable:
    """Decorator that validates the return value of a function against a schema.

    The decorated function should return data that matches the specified schema.
    If validation fails, SchemaMismatchError is raised.

    Args:
        schema_name: Name of the schema to validate against
        version: Version string (None for latest)

    Returns:
        Decorated function
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            result = func(*args, **kwargs)
            _registry.validate(result, schema_name, version)
            return result
        return wrapper
    return decorator


def validate_input_schema(schema_name: str, version: Optional[str] = None) -> Callable:
    """Decorator that validates the first positional argument (or 'data' keyword) against a schema.

    Useful for validating input to module functions.

    Args:
        schema_name: Name of the schema to validate against
        version: Version string (None for latest)

    Returns:
        Decorated function
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Determine the data to validate: first positional arg or 'data' keyword
            if args:
                data = args[0]
            elif 'data' in kwargs:
                data = kwargs['data']
            else:
                raise TypeError("No data argument found to validate. Provide positional arg or 'data' keyword.")
            _registry.validate(data, schema_name, version)
            return func(*args, **kwargs)
        return wrapper
    return decorator