"""Shared JSON schema registry module for inter-module validation.

Provides:
- SchemaRegistry: stores canonical schemas for each module interface
- Validation functions using jsonschema
- Version tracking for each schema
- @validate_schema decorator for inter-module calls
- SchemaMismatchError exception
- register_schema() for adding/updating schemas with version bumps
- Explicit interface definitions for core modules
- validate_inter_module_call() for cross-module validation
- version_compatibility_check() for version compatibility
- get_required_version() for minimum version requirements
"""

import json
import jsonschema
from jsonschema import validate, ValidationError
from functools import wraps
from typing import Any, Callable, Dict, Optional, Tuple, List
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
        self._module_interfaces: Dict[str, Dict[str, Any]] = {}  # module_name -> interface definition
        self._required_versions: Dict[str, str] = {}  # module_name -> minimum accepted version

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

    def register_interface(self, module_name: str, interface: Dict[str, Any]) -> None:
        """Register an explicit interface definition for a module.

        Args:
            module_name: Name of the module (e.g., 'mutation_engine')
            interface: Dictionary defining required fields and types
        """
        with self._lock:
            self._module_interfaces[module_name] = interface

    def get_interface(self, module_name: str) -> Dict[str, Any]:
        """Get the interface definition for a module.

        Args:
            module_name: Name of the module

        Returns:
            Interface definition dictionary

        Raises:
            KeyError: If module not found
        """
        with self._lock:
            if module_name not in self._module_interfaces:
                raise KeyError(f"Interface for module '{module_name}' not found.")
            return self._module_interfaces[module_name]

    def set_required_version(self, module_name: str, version: str) -> None:
        """Set the minimum accepted version for a module.

        Args:
            module_name: Name of the module
            version: Minimum version string (e.g., '1.2.0')
        """
        with self._lock:
            self._required_versions[module_name] = version

    def get_required_version(self, module_name: str) -> str:
        """Get the minimum accepted version for a module.

        Args:
            module_name: Name of the module

        Returns:
            Minimum version string

        Raises:
            KeyError: If module not found
        """
        with self._lock:
            if module_name not in self._required_versions:
                raise KeyError(f"Required version for module '{module_name}' not set.")
            return self._required_versions[module_name]

    def version_compatibility_check(self, caller_version: str, callee_version: str) -> bool:
        """Check if caller version is compatible with callee version.

        Compatibility is determined by comparing major versions:
        - Same major version is compatible
        - Different major versions are incompatible

        Args:
            caller_version: Version of the calling module
            callee_version: Version of the called module

        Returns:
            True if compatible, False otherwise

        Raises:
            SchemaMismatchError: If versions are incompatible
        """
        caller_parts = list(map(int, caller_version.split('.')))
        callee_parts = list(map(int, callee_version.split('.')))

        # Check major version compatibility
        if caller_parts[0] != callee_parts[0]:
            raise SchemaMismatchError(
                message=f"Major version mismatch: caller v{caller_version} vs callee v{callee_version}",
                schema_name="version_compatibility",
                version=caller_version,
                errors=[f"Incompatible major versions: {caller_parts[0]} != {callee_parts[0]}"]
            )

        # Check minimum version requirement
        if caller_parts[1] < callee_parts[1] or (caller_parts[1] == callee_parts[1] and caller_parts[2] < callee_parts[2]):
            raise SchemaMismatchError(
                message=f"Caller version {caller_version} is lower than required {callee_version}",
                schema_name="version_compatibility",
                version=caller_version,
                errors=[f"Version {caller_version} < {callee_version}"]
            )

        return True

    def validate_inter_module_call(self, caller_module: str, callee_module: str, data: Any, schema_name: str) -> None:
        """Validate an inter-module call with schema and version compatibility checks.

        Args:
            caller_module: Name of the calling module
            callee_module: Name of the called module
            data: Data to validate
            schema_name: Name of the schema to validate against

        Raises:
            SchemaMismatchError: If validation fails or versions are incompatible
            KeyError: If modules or schemas not found
        """
        with self._lock:
            # Get versions for both modules
            caller_version = self.get_required_version(caller_module)
            callee_version = self.get_required_version(callee_module)

            # Check version compatibility
            self.version_compatibility_check(caller_version, callee_version)

            # Validate data against schema
            self.validate(data, schema_name)


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


# Initialize core module interfaces with required fields and types
def _initialize_core_interfaces():
    """Initialize explicit interface definitions for core modules."""
    registry = get_registry()

    # Mutation Engine interface
    mutation_engine_interface = {
        "name": "mutation_engine",
        "description": "Handles code mutations for testing",
        "required_fields": {
            "source_code": {"type": "string", "description": "Source code to mutate"},
            "mutation_type": {"type": "string", "description": "Type of mutation to apply"},
            "target_line": {"type": "integer", "description": "Line number for mutation"}
        },
        "optional_fields": {
            "context": {"type": "object", "description": "Additional context for mutation"}
        },
        "output_fields": {
            "mutated_code": {"type": "string", "description": "Mutated source code"},
            "mutation_id": {"type": "string", "description": "Unique identifier for mutation"}
        }
    }
    registry.register_interface("mutation_engine", mutation_engine_interface)
    registry.set_required_version("mutation_engine", "1.0.0")

    # Testing Framework interface
    testing_framework_interface = {
        "name": "testing_framework",
        "description": "Executes tests and reports results",
        "required_fields": {
            "test_suite": {"type": "array", "description": "List of test cases"},
            "test_runner": {"type": "string", "description": "Test runner to use"}
        },
        "optional_fields": {
            "timeout": {"type": "integer", "description": "Test timeout in seconds"},
            "parallel": {"type": "boolean", "description": "Run tests in parallel"}
        },
        "output_fields": {
            "test_results": {"type": "array", "description": "Individual test results"},
            "summary": {"type": "object", "description": "Test execution summary"}
        }
    }
    registry.register_interface("testing_framework", testing_framework_interface)
    registry.set_required_version("testing_framework", "1.0.0")

    # Failure Analysis interface
    failure_analysis_interface = {
        "name": "failure_analysis",
        "description": "Analyzes test failures and identifies root causes",
        "required_fields": {
            "failure_data": {"type": "object", "description": "Failure information"},
            "analysis_type": {"type": "string", "description": "Type of analysis to perform"}
        },
        "optional_fields": {
            "historical_data": {"type": "array", "description": "Historical failure data"},
            "threshold": {"type": "number", "description": "Analysis threshold"}
        },
        "output_fields": {
            "root_causes": {"type": "array", "description": "Identified root causes"},
            "confidence_score": {"type": "number", "description": "Confidence in analysis"}
        }
    }
    registry.register_interface("failure_analysis", failure_analysis_interface)
    registry.set_required_version("failure_analysis", "1.0.0")

    # Planning interface
    planning_interface = {
        "name": "planning",
        "description": "Creates execution plans for testing strategies",
        "required_fields": {
            "objective": {"type": "string", "description": "Planning objective"},
            "constraints": {"type": "array", "description": "Planning constraints"}
        },
        "optional_fields": {
            "resources": {"type": "object", "description": "Available resources"},
            "preferences": {"type": "object", "description": "Planning preferences"}
        },
        "output_fields": {
            "plan": {"type": "object", "description": "Generated execution plan"},
            "estimated_duration": {"type": "integer", "description": "Estimated execution time"}
        }
    }
    registry.register_interface("planning", planning_interface)
    registry.set_required_version("planning", "1.0.0")


# Initialize core interfaces on module import
_initialize_core_interfaces()