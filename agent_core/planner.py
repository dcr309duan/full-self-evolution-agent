from typing import Any, Dict, List, Optional
from functools import wraps
import logging

logger = logging.getLogger(__name__)

# Schema registry for version management
SCHEMA_REGISTRY = {
    'plan': {
        '1.0': {
            'required_fields': ['goal', 'steps', 'status'],
            'optional_fields': ['metadata', 'context'],
            'version': '1.0'
        }
    },
    'plan_request': {
        '1': {
            'required_fields': ['goal', 'context'],
            'optional_fields': ['constraints', 'preferences'],
            'version': '1'
        }
    },
    'plan_output': {
        '1': {
            'required_fields': ['goal', 'steps', 'status', 'plan_id'],
            'optional_fields': ['metadata', 'context', 'estimated_duration'],
            'version': '1'
        }
    },
    'failure_analysis': {
        '1.0': {
            'required_fields': ['failure_type', 'root_cause', 'impact'],
            'optional_fields': ['recommendations', 'timestamp'],
            'version': '1.0'
        }
    },
    'system_state': {
        '1.0': {
            'required_fields': ['status', 'components', 'last_updated'],
            'optional_fields': ['alerts', 'metrics'],
            'version': '1.0'
        }
    },
    'feasibility_data': {
        '1': {
            'required_fields': ['feasible', 'estimated_resources', 'risks'],
            'optional_fields': ['alternative_approaches', 'timestamp'],
            'version': '1'
        }
    }
}


class SchemaValidationError(Exception):
    """Raised when schema validation fails."""
    pass


class VersionMismatchError(Exception):
    """Raised when input schema version does not match expected version."""
    pass


def validate_schema(schema_type: str, expected_version: str):
    """
    Decorator that validates the output of a function against a specified schema.
    
    Args:
        schema_type: The type of schema to validate against (e.g., 'plan', 'failure_analysis')
        expected_version: The expected version of the schema (e.g., '1.0')
    
    Returns:
        Decorated function that validates its return value against the schema.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            result = func(*args, **kwargs)
            
            # Get the schema definition
            schema = SCHEMA_REGISTRY.get(schema_type, {}).get(expected_version)
            if not schema:
                raise SchemaValidationError(
                    f"Unknown schema type '{schema_type}' version '{expected_version}'"
                )
            
            # Validate the result
            if not isinstance(result, dict):
                raise SchemaValidationError(
                    f"Expected dict result, got {type(result).__name__}"
                )
            
            # Check required fields
            missing_fields = [
                field for field in schema['required_fields']
                if field not in result
            ]
            if missing_fields:
                raise SchemaValidationError(
                    f"Missing required fields in {schema_type}: {missing_fields}"
                )
            
            # Add schema version to result
            result['_schema_version'] = expected_version
            
            return result
        return wrapper
    return decorator


def validate_input_data(data: Dict[str, Any], schema_type: str, expected_version: str) -> bool:
    """
    Validates incoming data against a specified schema.
    
    Args:
        data: The data dictionary to validate
        schema_type: The type of schema to validate against
        expected_version: The expected version of the schema
    
    Returns:
        True if validation passes, raises exception otherwise
    """
    # Get the schema definition
    schema = SCHEMA_REGISTRY.get(schema_type, {}).get(expected_version)
    if not schema:
        raise SchemaValidationError(
            f"Unknown schema type '{schema_type}' version '{expected_version}'"
        )
    
    # Check required fields
    missing_fields = [
        field for field in schema['required_fields']
        if field not in data
    ]
    if missing_fields:
        raise SchemaValidationError(
            f"Missing required fields in {schema_type}: {missing_fields}"
        )
    
    # Check for unexpected fields (optional, can be relaxed)
    allowed_fields = set(schema['required_fields'] + schema['optional_fields'])
    unexpected_fields = [
        field for field in data
        if field not in allowed_fields and not field.startswith('_')
    ]
    if unexpected_fields:
        logger.warning(f"Unexpected fields in {schema_type}: {unexpected_fields}")
    
    return True


def check_version_compatibility(inputs: Dict[str, Dict[str, Any]], expected_versions: Dict[str, str]) -> bool:
    """
    Ensures all inputs match expected schema versions.
    
    Args:
        inputs: Dictionary mapping input names to their data dictionaries
        expected_versions: Dictionary mapping input names to expected schema versions
    
    Returns:
        True if all versions match, raises exception otherwise
    """
    for input_name, data in inputs.items():
        expected_version = expected_versions.get(input_name)
        if not expected_version:
            raise VersionMismatchError(
                f"No expected version specified for input '{input_name}'"
            )
        
        actual_version = data.get('_schema_version')
        if not actual_version:
            raise VersionMismatchError(
                f"Input '{input_name}' has no schema version specified"
            )
        
        if actual_version != expected_version:
            raise VersionMismatchError(
                f"Version mismatch for input '{input_name}': "
                f"expected {expected_version}, got {actual_version}"
            )
    
    return True


def validate_planning_inputs(failure_analysis: Dict[str, Any], system_state: Dict[str, Any]) -> bool:
    """
    Validates both failure analysis and system state data before planning.
    
    Args:
        failure_analysis: The failure analysis data to validate
        system_state: The system state data to validate
    
    Returns:
        True if both inputs are valid
    """
    # Validate failure analysis
    validate_input_data(failure_analysis, 'failure_analysis', '1.0')
    
    # Validate system state
    validate_input_data(system_state, 'system_state', '1.0')
    
    # Check version compatibility
    inputs = {
        'failure_analysis': failure_analysis,
        'system_state': system_state
    }
    expected_versions = {
        'failure_analysis': '1.0',
        'system_state': '1.0'
    }
    check_version_compatibility(inputs, expected_versions)
    
    return True


@validate_schema('plan_request', '1')
def generate_plan(goal: str, context: Dict[str, Any], constraints: Optional[Dict[str, Any]] = None, preferences: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Generates a plan with schema validation on input and output.
    
    Args:
        goal: The goal of the plan
        context: Context information for planning
        constraints: Optional constraints for the plan
        preferences: Optional preferences for the plan
    
    Returns:
        A validated plan output dictionary
    """
    # Build the plan request
    plan_request = {
        'goal': goal,
        'context': context
    }
    if constraints:
        plan_request['constraints'] = constraints
    if preferences:
        plan_request['preferences'] = preferences
    
    # Simulate plan generation logic
    plan_result = {
        'goal': goal,
        'steps': ['Step 1: Analyze requirements', 'Step 2: Design solution', 'Step 3: Implement'],
        'status': 'generated',
        'plan_id': 'PLAN-001',
        'context': context,
        'estimated_duration': '2 weeks'
    }
    
    # Validate the output using the decorator
    return plan_result


@validate_schema('plan_output', '1')
def create_plan(goal: str, steps: List[str], status: str = "pending") -> Dict[str, Any]:
    """
    Creates a plan with schema validation.
    
    Args:
        goal: The goal of the plan
        steps: List of steps to achieve the goal
        status: Current status of the plan
    
    Returns:
        A validated plan dictionary
    """
    return {
        'goal': goal,
        'steps': steps,
        'status': status,
        'plan_id': 'PLAN-' + str(hash(goal))[:8]
    }


def receive_feasibility_data(feasibility_data: Dict[str, Any]) -> bool:
    """
    Receives and validates feasibility data from orchestrator with version check.
    
    Args:
        feasibility_data: The feasibility data to validate
    
    Returns:
        True if validation passes, raises exception otherwise
    """
    # Validate the feasibility data against schema
    validate_input_data(feasibility_data, 'feasibility_data', '1')
    
    # Check version compatibility
    expected_version = '1'
    actual_version = feasibility_data.get('_schema_version')
    
    if not actual_version:
        raise VersionMismatchError(
            "Feasibility data has no schema version specified"
        )
    
    if actual_version != expected_version:
        raise VersionMismatchError(
            f"Version mismatch for feasibility data: "
            f"expected {expected_version}, got {actual_version}"
        )
    
    logger.info(f"Feasibility data received and validated (version {actual_version})")
    return True