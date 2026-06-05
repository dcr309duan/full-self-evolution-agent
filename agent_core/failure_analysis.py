from typing import Any, Dict, List, Optional
from datetime import datetime
import logging
from functools import wraps

from agent_core.schema_validator import validate_schema, SchemaVersionError

logger = logging.getLogger(__name__)

# Expected schema versions for incoming data
EXPECTED_TEST_RESULTS_VERSION = "1.0"
EXPECTED_MUTATION_DATA_VERSION = "1.0"

class FailureAnalysisError(Exception):
    """Base exception for failure analysis errors."""
    pass

class SchemaMismatchError(FailureAnalysisError):
    """Raised when incoming data schema version does not match expected version."""
    pass

def validate_incoming_data(schema_name: str, expected_version: str):
    """
    Decorator to validate incoming data schema version before processing.
    Raises SchemaMismatchError if version does not match.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Extract data from arguments (assumes first arg is data dict)
            data = args[0] if args else kwargs.get('data', {})
            if not isinstance(data, dict):
                raise SchemaMismatchError("Incoming data must be a dictionary")
            
            actual_version = data.get('schema_version', 'unknown')
            if actual_version != expected_version:
                raise SchemaMismatchError(
                    f"Schema version mismatch for '{schema_name}': "
                    f"expected {expected_version}, got {actual_version}"
                )
            
            logger.debug(f"Schema version check passed for '{schema_name}': {actual_version}")
            return func(*args, **kwargs)
        return wrapper
    return decorator

@validate_schema('failure_input', version=1)
def classify_failure(test_results: Dict[str, Any], mutation_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Classify failures based on test results and optional mutation data.
    
    Args:
        test_results: Dictionary containing test execution results
        mutation_data: Optional dictionary containing mutation testing data
    
    Returns:
        Dictionary with failure classification results
    """
    # Validate incoming data schemas
    if not _validate_test_results(test_results):
        raise SchemaMismatchError("Invalid test results schema")
    
    if mutation_data and not _validate_mutation_data(mutation_data):
        raise SchemaMismatchError("Invalid mutation data schema")
    
    # Perform failure classification logic
    classification = {
        'classification_version': '1.0',
        'timestamp': datetime.utcnow().isoformat(),
        'failure_type': _determine_failure_type(test_results),
        'severity': _calculate_severity(test_results),
        'root_cause_indicators': _identify_root_causes(test_results, mutation_data),
        'confidence_score': _calculate_confidence(test_results, mutation_data)
    }
    
    return classification

@validate_schema('failure_output', version=1)
def _validate_test_results(test_results: Dict[str, Any]) -> bool:
    """
    Validate the structure and required fields of test results data.
    
    Args:
        test_results: Dictionary to validate
    
    Returns:
        True if valid, False otherwise
    """
    required_fields = ['test_id', 'status', 'execution_time', 'schema_version']
    
    if not isinstance(test_results, dict):
        logger.error("Test results must be a dictionary")
        return False
    
    for field in required_fields:
        if field not in test_results:
            logger.error(f"Missing required field '{field}' in test results")
            return False
    
    # Check schema version
    if test_results.get('schema_version') != EXPECTED_TEST_RESULTS_VERSION:
        logger.error(
            f"Test results schema version mismatch: "
            f"expected {EXPECTED_TEST_RESULTS_VERSION}, "
            f"got {test_results.get('schema_version', 'unknown')}"
        )
        return False
    
    # Validate status field
    valid_statuses = ['passed', 'failed', 'error', 'skipped']
    if test_results.get('status') not in valid_statuses:
        logger.error(f"Invalid test status: {test_results.get('status')}")
        return False
    
    return True

def _validate_mutation_data(mutation_data: Dict[str, Any]) -> bool:
    """
    Validate the structure and required fields of mutation data.
    
    Args:
        mutation_data: Dictionary to validate
    
    Returns:
        True if valid, False otherwise
    """
    required_fields = ['mutation_id', 'mutant_type', 'killed', 'schema_version']
    
    if not isinstance(mutation_data, dict):
        logger.error("Mutation data must be a dictionary")
        return False
    
    for field in required_fields:
        if field not in mutation_data:
            logger.error(f"Missing required field '{field}' in mutation data")
            return False
    
    # Check schema version
    if mutation_data.get('schema_version') != EXPECTED_MUTATION_DATA_VERSION:
        logger.error(
            f"Mutation data schema version mismatch: "
            f"expected {EXPECTED_MUTATION_DATA_VERSION}, "
            f"got {mutation_data.get('schema_version', 'unknown')}"
        )
        return False
    
    # Validate killed field
    if not isinstance(mutation_data.get('killed'), bool):
        logger.error("Mutation 'killed' field must be boolean")
        return False
    
    return True

def _determine_failure_type(test_results: Dict[str, Any]) -> str:
    """
    Determine the type of failure based on test results.
    
    Args:
        test_results: Dictionary containing test results
    
    Returns:
        String indicating failure type
    """
    failure_patterns = test_results.get('failure_patterns', [])
    
    if 'assertion_error' in failure_patterns:
        return 'assertion_failure'
    elif 'timeout' in failure_patterns:
        return 'timeout_failure'
    elif 'exception' in failure_patterns:
        return 'runtime_exception'
    else:
        return 'unknown_failure'

def _calculate_severity(test_results: Dict[str, Any]) -> str:
    """
    Calculate severity level based on test results.
    
    Args:
        test_results: Dictionary containing test results
    
    Returns:
        String indicating severity level
    """
    failure_count = test_results.get('failure_count', 0)
    critical_failures = test_results.get('critical_failures', 0)
    
    if critical_failures > 0:
        return 'critical'
    elif failure_count > 5:
        return 'high'
    elif failure_count > 2:
        return 'medium'
    else:
        return 'low'

def _identify_root_causes(
    test_results: Dict[str, Any],
    mutation_data: Optional[Dict[str, Any]]
) -> List[str]:
    """
    Identify potential root causes from test results and mutation data.
    
    Args:
        test_results: Dictionary containing test results
        mutation_data: Optional dictionary containing mutation data
    
    Returns:
        List of root cause indicators
    """
    root_causes = []
    
    # Analyze test results for patterns
    error_messages = test_results.get('error_messages', [])
    for msg in error_messages:
        if 'null pointer' in msg.lower():
            root_causes.append('null_pointer_dereference')
        elif 'index out of bounds' in msg.lower():
            root_causes.append('index_out_of_bounds')
        elif 'type error' in msg.lower():
            root_causes.append('type_mismatch')
    
    # Analyze mutation data if available
    if mutation_data:
        if mutation_data.get('killed', False):
            root_causes.append(f"mutation_detected:{mutation_data.get('mutant_type', 'unknown')}")
    
    return root_causes if root_causes else ['no_clear_indicator']

def _calculate_confidence(
    test_results: Dict[str, Any],
    mutation_data: Optional[Dict[str, Any]]
) -> float:
    """
    Calculate confidence score for failure classification.
    
    Args:
        test_results: Dictionary containing test results
        mutation_data: Optional dictionary containing mutation data
    
    Returns:
        Float between 0.0 and 1.0 indicating confidence
    """
    confidence = 0.5  # Base confidence
    
    # Adjust based on test result completeness
    if test_results.get('error_messages'):
        confidence += 0.2
    
    if test_results.get('stack_trace'):
        confidence += 0.1
    
    # Adjust based on mutation data
    if mutation_data:
        confidence += 0.2
    
    # Ensure confidence is within bounds
    return min(max(confidence, 0.0), 1.0)

@validate_incoming_data('test_results', EXPECTED_TEST_RESULTS_VERSION)
def process_test_results(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process incoming test results with schema validation.
    
    Args:
        data: Dictionary containing test results data
    
    Returns:
        Processed test results
    """
    logger.info(f"Processing test results for test: {data.get('test_id', 'unknown')}")
    return {
        'processed': True,
        'timestamp': datetime.utcnow().isoformat(),
        'test_id': data.get('test_id'),
        'status': data.get('status')
    }

@validate_incoming_data('mutation_data', EXPECTED_MUTATION_DATA_VERSION)
def process_mutation_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process incoming mutation data with schema validation.
    
    Args:
        data: Dictionary containing mutation data
    
    Returns:
        Processed mutation data
    """
    logger.info(f"Processing mutation data for mutation: {data.get('mutation_id', 'unknown')}")
    return {
        'processed': True,
        'timestamp': datetime.utcnow().isoformat(),
        'mutation_id': data.get('mutation_id'),
        'killed': data.get('killed')
    }

def analyze_failure_with_version_check(
    test_results: Dict[str, Any],
    mutation_data: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Perform complete failure analysis with version checking.
    
    Args:
        test_results: Dictionary containing test results
        mutation_data: Optional dictionary containing mutation data
    
    Returns:
        Dictionary with complete failure analysis results
    
    Raises:
        SchemaMismatchError: If data schema versions don't match expected versions
    """
    # Version check for test results
    test_version = test_results.get('schema_version', 'unknown')
    if test_version != EXPECTED_TEST_RESULTS_VERSION:
        raise SchemaMismatchError(
            f"Test results schema version mismatch: "
            f"expected {EXPECTED_TEST_RESULTS_VERSION}, got {test_version}"
        )
    
    # Version check for mutation data if present
    if mutation_data:
        mutation_version = mutation_data.get('schema_version', 'unknown')
        if mutation_version != EXPECTED_MUTATION_DATA_VERSION:
            raise SchemaMismatchError(
                f"Mutation data schema version mismatch: "
                f"expected {EXPECTED_MUTATION_DATA_VERSION}, got {mutation_version}"
            )
    
    # Proceed with analysis
    classification = classify_failure(test_results, mutation_data)
    
    return {
        'analysis_version': '1.0',
        'timestamp': datetime.utcnow().isoformat(),
        'classification': classification,
        'test_results_processed': process_test_results(test_results),
        'mutation_data_processed': process_mutation_data(mutation_data) if mutation_data else None
    }