from logging import Logger, FileHandler, Formatter, getLogger
import json
import os
from datetime import datetime
from typing import Optional, Dict, Any

class SandboxOutcomeHandler(FileHandler):
    """Custom log handler that writes structured JSON logs for sandbox outcomes."""
    
    def __init__(self, filename: str = 'logs/sandbox_outcomes.log', mode: str = 'a', encoding: str = 'utf-8'):
        # Ensure the logs directory exists
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        super().__init__(filename, mode=mode, encoding=encoding)
        self.setFormatter(Formatter('%(message)s'))  # We'll format as JSON ourselves
    
    def emit(self, record):
        """Emit a log record as a JSON line."""
        try:
            # Extract the structured data from the log record
            msg = self.format(record)
            if isinstance(msg, str):
                # If the message is a JSON string, parse and re-serialize to ensure valid JSON
                try:
                    data = json.loads(msg)
                except json.JSONDecodeError:
                    data = {"message": msg}
            else:
                data = msg
            
            # Ensure required fields are present
            if not isinstance(data, dict):
                data = {"message": str(data)}
            
            # Add timestamp if not present
            if 'timestamp' not in data:
                data['timestamp'] = datetime.utcnow().isoformat()
            
            # Write as a single JSON line
            self.stream.write(json.dumps(data, default=str) + '\n')
            self.flush()
        except Exception:
            self.handleError(record)

class FailurePatternHandler(FileHandler):
    """Custom log handler that writes structured JSON logs for failure patterns."""
    
    def __init__(self, filename: str = 'logs/failure_patterns.log', mode: str = 'a', encoding: str = 'utf-8'):
        # Ensure the logs directory exists
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        super().__init__(filename, mode=mode, encoding=encoding)
        self.setFormatter(Formatter('%(message)s'))  # We'll format as JSON ourselves
    
    def emit(self, record):
        """Emit a log record as a JSON line."""
        try:
            # Extract the structured data from the log record
            msg = self.format(record)
            if isinstance(msg, str):
                # If the message is a JSON string, parse and re-serialize to ensure valid JSON
                try:
                    data = json.loads(msg)
                except json.JSONDecodeError:
                    data = {"message": msg}
            else:
                data = msg
            
            # Ensure required fields are present
            if not isinstance(data, dict):
                data = {"message": str(data)}
            
            # Add timestamp if not present
            if 'timestamp' not in data:
                data['timestamp'] = datetime.utcnow().isoformat()
            
            # Write as a single JSON line
            self.stream.write(json.dumps(data, default=str) + '\n')
            self.flush()
        except Exception:
            self.handleError(record)

def get_sandbox_logger(name: str = 'sandbox_outcomes') -> Logger:
    """Get or create a logger configured for sandbox outcome logging."""
    logger = getLogger(name)
    
    # Only add handler if not already configured
    if not logger.handlers:
        handler = SandboxOutcomeHandler()
        logger.addHandler(handler)
        logger.setLevel('INFO')  # Adjust level as needed
        # Prevent propagation to root logger to avoid duplicate logs
        logger.propagate = False
    
    return logger

def get_failure_pattern_logger(name: str = 'failure_patterns') -> Logger:
    """Get or create a logger configured for failure pattern logging."""
    logger = getLogger(name)
    
    # Only add handler if not already configured
    if not logger.handlers:
        handler = FailurePatternHandler()
        logger.addHandler(handler)
        logger.setLevel('INFO')  # Adjust level as needed
        # Prevent propagation to root logger to avoid duplicate logs
        logger.propagate = False
    
    return logger

def log_sandbox_outcome(
    cycle: int,
    mutation_description: str,
    target_module: str,
    test_results: Dict[str, Any],
    outcome: str,
    error_details: Optional[str] = None,
    execution_time_seconds: Optional[float] = None
) -> None:
    """
    Log a structured sandbox outcome entry.
    
    Args:
        cycle: The cycle number
        mutation_description: Description of the mutation applied
        target_module: The module being tested
        test_results: Dict with 'pass_count', 'fail_count', 'total' keys
        outcome: One of 'promoted', 'discarded', 'error'
        error_details: Optional error details string
        execution_time_seconds: Optional execution time in seconds
    """
    logger = get_sandbox_logger()
    
    log_entry = {
        'timestamp': datetime.utcnow().isoformat(),
        'cycle': cycle,
        'mutation_description': mutation_description,
        'target_module': target_module,
        'test_results': {
            'pass_count': test_results.get('pass_count', 0),
            'fail_count': test_results.get('fail_count', 0),
            'total': test_results.get('total', 0)
        },
        'outcome': outcome,
        'error_details': error_details,
        'execution_time_seconds': execution_time_seconds
    }
    
    logger.info(json.dumps(log_entry, default=str))

def log_failure_pattern(
    cycle: int,
    error_type: str,
    operator_used: str,
    module_under_test: str,
    failure_count: int,
    success_count: int,
    adjusted_weight: float
) -> None:
    """
    Log a structured failure pattern entry.
    
    Args:
        cycle: The cycle number
        error_type: The type of error encountered
        operator_used: The operator that was used
        module_under_test: The module being tested
        failure_count: Number of failures
        success_count: Number of successes
        adjusted_weight: The adjusted weight value
    """
    logger = get_failure_pattern_logger()
    
    log_entry = {
        'timestamp': datetime.utcnow().isoformat(),
        'cycle': cycle,
        'error_type': error_type,
        'operator_used': operator_used,
        'module_under_test': module_under_test,
        'failure_count': failure_count,
        'success_count': success_count,
        'adjusted_weight': adjusted_weight
    }
    
    logger.info(json.dumps(log_entry, default=str))