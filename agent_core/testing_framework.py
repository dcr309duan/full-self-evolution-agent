from typing import Any, Callable, Dict, Optional
from functools import wraps
import json
import logging

logger = logging.getLogger(__name__)

# Schema definitions
SCHEMAS = {
    'test_result': {
        '1.0': {
            'type': 'object',
            'properties': {
                'test_id': {'type': 'string'},
                'status': {'type': 'string', 'enum': ['pass', 'fail', 'error']},
                'output': {'type': 'string'},
                'duration_ms': {'type': 'number'},
                'timestamp': {'type': 'string', 'format': 'date-time'},
                'schema_version': {'type': 'string'}
            },
            'required': ['test_id', 'status', 'output', 'schema_version']
        }
    },
    'mutation_data': {
        '1.0': {
            'type': 'object',
            'properties': {
                'mutation_id': {'type': 'string'},
                'target': {'type': 'string'},
                'change': {'type': 'string'},
                'schema_version': {'type': 'string'}
            },
            'required': ['mutation_id', 'target', 'change', 'schema_version']
        }
    }
}

class SchemaValidationError(Exception):
    """Raised when schema validation fails."""
    pass

class SchemaVersionMismatchError(Exception):
    """Raised when schema versions don't match."""
    pass

def _validate_against_schema(data: Dict[str, Any], schema_name: str, version: str) -> bool:
    """
    Validate data against a defined schema.
    
    Args:
        data: The data to validate
        schema_name: Name of the schema to validate against
        version: Schema version string
    
    Returns:
        True if valid, raises exception otherwise
    """
    if schema_name not in SCHEMAS:
        raise SchemaValidationError(f"Unknown schema: {schema_name}")
    
    if version not in SCHEMAS[schema_name]:
        raise SchemaValidationError(f"Unknown version {version} for schema {schema_name}")
    
    schema = SCHEMAS[schema_name][version]
    
    # Check required fields
    for field in schema.get('required', []):
        if field not in data:
            raise SchemaValidationError(f"Missing required field '{field}' in {schema_name} schema")
    
    # Check field types
    for field, value in data.items():
        if field in schema.get('properties', {}):
            field_schema = schema['properties'][field]
            expected_type = field_schema.get('type')
            
            if expected_type == 'string' and not isinstance(value, str):
                raise SchemaValidationError(f"Field '{field}' should be string, got {type(value).__name__}")
            elif expected_type == 'number' and not isinstance(value, (int, float)):
                raise SchemaValidationError(f"Field '{field}' should be number, got {type(value).__name__}")
            elif expected_type == 'object' and not isinstance(value, dict):
                raise SchemaValidationError(f"Field '{field}' should be object, got {type(value).__name__}")
            
            # Check enum values
            if 'enum' in field_schema and value not in field_schema['enum']:
                raise SchemaValidationError(f"Field '{field}' value '{value}' not in allowed values: {field_schema['enum']}")
    
    return True

def validate_schema(schema_name: str, version: str) -> Callable:
    """
    Decorator that validates the output of a function against a schema.
    
    Args:
        schema_name: Name of the schema to validate against
        version: Schema version string
    
    Returns:
        Decorated function
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            result = func(*args, **kwargs)
            
            # Add schema version to result if it's a dict
            if isinstance(result, dict):
                result['schema_version'] = version
            
            # Validate the result
            _validate_against_schema(result, schema_name, version)
            
            return result
        return wrapper
    return decorator

def validate_mutation_data(data: Dict[str, Any], expected_version: str = '1.0') -> bool:
    """
    Validate incoming mutation data before executing tests.
    
    Args:
        data: The mutation data to validate
        expected_version: Expected schema version
    
    Returns:
        True if valid, raises exception otherwise
    """
    # Check schema version
    actual_version = data.get('schema_version')
    if actual_version != expected_version:
        raise SchemaVersionMismatchError(
            f"Schema version mismatch: expected {expected_version}, got {actual_version}"
        )
    
    # Validate against mutation_data schema
    _validate_against_schema(data, 'mutation_data', expected_version)
    
    logger.info(f"Mutation data validated successfully (version {expected_version})")
    return True

def validate_test_request(request_data: Dict[str, Any], expected_version: str = '1.0') -> bool:
    """
    Validate a test request, including version check.
    Rejects requests with mismatched schema versions.
    
    Args:
        request_data: The test request data
        expected_version: Expected schema version
    
    Returns:
        True if valid, raises exception otherwise
    """
    # Check schema version in request
    request_version = request_data.get('schema_version')
    if request_version is None:
        raise SchemaVersionMismatchError("No schema version specified in request")
    
    if request_version != expected_version:
        raise SchemaVersionMismatchError(
            f"Schema version mismatch in test request: expected {expected_version}, got {request_version}. "
            f"Request rejected."
        )
    
    # Validate mutation data if present
    mutation_data = request_data.get('mutation_data')
    if mutation_data:
        validate_mutation_data(mutation_data, expected_version)
    
    logger.info(f"Test request validated successfully (version {expected_version})")
    return True

def register_custom_schema(schema_name: str, version: str, schema_definition: Dict[str, Any]) -> None:
    """
    Register a custom schema for validation.
    
    Args:
        schema_name: Name of the schema
        version: Schema version string
        schema_definition: Schema definition dictionary
    """
    if schema_name not in SCHEMAS:
        SCHEMAS[schema_name] = {}
    
    SCHEMAS[schema_name][version] = schema_definition
    logger.info(f"Registered custom schema '{schema_name}' version {version}")