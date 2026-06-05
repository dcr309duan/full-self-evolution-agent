from typing import Any, Dict, List, Optional
import functools
import json
import jsonschema
from jsonschema import validate, ValidationError
from datetime import datetime

# Schema definitions
TEST_REQUEST_SCHEMA_V1 = {
    "type": "object",
    "properties": {
        "test_id": {"type": "string"},
        "test_name": {"type": "string"},
        "test_type": {"type": "string", "enum": ["unit", "integration", "e2e"]},
        "parameters": {"type": "object"},
        "timestamp": {"type": "string", "format": "date-time"},
        "version": {"type": "integer", "minimum": 1}
    },
    "required": ["test_id", "test_name", "test_type", "version"]
}

TEST_RESULT_SCHEMA_V1 = {
    "type": "object",
    "properties": {
        "test_id": {"type": "string"},
        "status": {"type": "string", "enum": ["passed", "failed", "skipped", "error"]},
        "execution_time": {"type": "number", "minimum": 0},
        "error_message": {"type": "string"},
        "stack_trace": {"type": "string"},
        "timestamp": {"type": "string", "format": "date-time"},
        "version": {"type": "integer", "minimum": 1}
    },
    "required": ["test_id", "status", "execution_time", "version"]
}

# Schema registry
SCHEMA_REGISTRY = {
    "test_request": {1: TEST_REQUEST_SCHEMA_V1},
    "test_result": {1: TEST_RESULT_SCHEMA_V1}
}

# Supported versions for compatibility
SUPPORTED_VERSIONS = {
    "test_request": [1],
    "test_result": [1]
}

class SchemaValidationError(Exception):
    """Custom exception for schema validation failures."""
    pass

class VersionCompatibilityError(Exception):
    """Custom exception for version compatibility issues."""
    pass

def validate_schema(schema_type: str, version: int = 1):
    """
    Decorator to validate input/output data against a specified schema.
    
    Args:
        schema_type: Type of schema to validate against ('test_request' or 'test_result')
        version: Schema version to use (default: 1)
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Get the schema
            schema = SCHEMA_REGISTRY.get(schema_type, {}).get(version)
            if not schema:
                raise SchemaValidationError(
                    f"Schema '{schema_type}' version {version} not found"
                )
            
            # Validate input data if present
            if args:
                data = args[0] if isinstance(args[0], dict) else None
                if data:
                    try:
                        validate(instance=data, schema=schema)
                    except ValidationError as e:
                        raise SchemaValidationError(
                            f"Input validation failed for {schema_type}: {e.message}"
                        )
            
            # Execute the function
            result = func(*args, **kwargs)
            
            # Validate output data if schema_type is 'test_result' and result is a dict
            if schema_type == "test_result" and isinstance(result, dict):
                try:
                    validate(instance=result, schema=schema)
                except ValidationError as e:
                    raise SchemaValidationError(
                        f"Output validation failed for {schema_type}: {e.message}"
                    )
            
            return result
        return wrapper
    return decorator

def check_version_compatibility(
    mutation_candidates: List[Dict[str, Any]],
    schema_type: str = "test_request",
    min_version: int = 1
) -> List[Dict[str, Any]]:
    """
    Check version compatibility of mutation candidates from the mutation engine.
    
    Args:
        mutation_candidates: List of mutation candidate dictionaries
        schema_type: Type of schema to check compatibility for
        min_version: Minimum supported version
        
    Returns:
        Filtered list of compatible mutation candidates
        
    Raises:
        VersionCompatibilityError: If version incompatibility is detected
    """
    compatible_candidates = []
    supported_versions = SUPPORTED_VERSIONS.get(schema_type, [])
    
    for candidate in mutation_candidates:
        candidate_version = candidate.get("version", 1)
        
        # Check if version is supported
        if candidate_version not in supported_versions:
            raise VersionCompatibilityError(
                f"Mutation candidate version {candidate_version} is not supported. "
                f"Supported versions: {supported_versions}"
            )
        
        # Check minimum version requirement
        if candidate_version < min_version:
            raise VersionCompatibilityError(
                f"Mutation candidate version {candidate_version} is below minimum "
                f"required version {min_version}"
            )
        
        # Validate the candidate against the schema
        schema = SCHEMA_REGISTRY.get(schema_type, {}).get(candidate_version)
        if schema:
            try:
                validate(instance=candidate, schema=schema)
                compatible_candidates.append(candidate)
            except ValidationError as e:
                # Log the validation error but continue processing
                print(f"Warning: Mutation candidate failed schema validation: {e.message}")
                continue
        else:
            # If no schema found for this version, still include the candidate
            compatible_candidates.append(candidate)
    
    return compatible_candidates

class TestFramework:
    """Main test framework class with schema validation."""
    
    def __init__(self):
        self.test_results = []
        self.mutation_candidates = []
    
    @validate_schema('test_request', version=1)
    def run_tests(self, test_request: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Run tests based on the provided test request.
        
        Args:
            test_request: Dictionary containing test configuration
            
        Returns:
            List of test results
        """
        print(f"Running tests for: {test_request.get('test_name', 'Unknown')}")
        
        # Simulate test execution
        test_results = []
        for i in range(3):  # Simulate 3 tests
            result = {
                "test_id": f"{test_request['test_id']}_{i}",
                "status": "passed" if i % 2 == 0 else "failed",
                "execution_time": 0.5 + i * 0.1,
                "error_message": "" if i % 2 == 0 else "Test assertion failed",
                "stack_trace": "" if i % 2 == 0 else "File 'test.py', line 42",
                "timestamp": datetime.now().isoformat(),
                "version": 1
            }
            test_results.append(result)
        
        return test_results
    
    @validate_schema('test_result', version=1)
    def report_result(self, test_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Report a single test result.
        
        Args:
            test_result: Dictionary containing test result data
            
        Returns:
            The validated test result
        """
        self.test_results.append(test_result)
        print(f"Reported result for test: {test_result.get('test_id', 'Unknown')}")
        return test_result
    
    def receive_mutation_candidates(self, candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Receive and validate mutation candidates from the mutation engine.
        
        Args:
            candidates: List of mutation candidate dictionaries
            
        Returns:
            List of validated and compatible mutation candidates
        """
        try:
            compatible_candidates = check_version_compatibility(
                candidates,
                schema_type="test_request",
                min_version=1
            )
            self.mutation_candidates.extend(compatible_candidates)
            print(f"Received {len(compatible_candidates)} compatible mutation candidates")
            return compatible_candidates
        except VersionCompatibilityError as e:
            print(f"Version compatibility error: {e}")
            return []
        except Exception as e:
            print(f"Error processing mutation candidates: {e}")
            return []

# Example usage
if __name__ == "__main__":
    framework = TestFramework()
    
    # Example test request
    test_request = {
        "test_id": "test_001",
        "test_name": "User Authentication",
        "test_type": "integration",
        "parameters": {"username": "test_user", "password": "test_pass"},
        "timestamp": datetime.now().isoformat(),
        "version": 1
    }
    
    # Run tests
    results = framework.run_tests(test_request)
    
    # Report results
    for result in results:
        framework.report_result(result)
    
    # Example mutation candidates
    mutation_candidates = [
        {
            "test_id": "mut_001",
            "test_name": "Mutation Test 1",
            "test_type": "unit",
            "parameters": {"input": "test_data"},
            "timestamp": datetime.now().isoformat(),
            "version": 1
        },
        {
            "test_id": "mut_002",
            "test_name": "Mutation Test 2",
            "test_type": "unit",
            "parameters": {"input": "test_data_2"},
            "timestamp": datetime.now().isoformat(),
            "version": 1
        }
    ]
    
    # Receive mutation candidates
    framework.receive_mutation_candidates(mutation_candidates)