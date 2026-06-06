"""Lightweight error logging module for mutation attempts.
Each entry includes structured data for failure pattern mining.
Integrates with the main evolution loop to automatically log mutation failures."""

import json
import os
import time
from datetime import datetime
from typing import Optional, Dict, Any
from pathlib import Path

# Default log file path
DEFAULT_LOG_PATH = "data/error_log.jsonl"

# In-memory buffer for recent errors (for fast access)
_recent_errors: list = []
_max_recent_errors = 100

# Current cycle number (set by evolution loop)
_current_cycle: int = 0


def set_current_cycle(cycle_number: int) -> None:
    """Set the current cycle number for logging context."""
    global _current_cycle
    _current_cycle = cycle_number


def get_current_cycle() -> int:
    """Get the current cycle number."""
    return _current_cycle


def parse_error_type(exception: Exception) -> str:
    """Parse the error type from an exception object.
    
    Args:
        exception: The exception to parse
        
    Returns:
        String representation of the error type
    """
    return type(exception).__name__


def log_mutation_error(
    target_module: str,
    error: Exception,
    cycle_number: Optional[int] = None,
    log_path: Optional[str] = None,
    additional_info: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Log a mutation error to the structured error log.
    
    Args:
        target_module: Name of the module being mutated
        error: The exception that occurred
        cycle_number: Cycle number (defaults to current cycle)
        log_path: Path to log file (defaults to DEFAULT_LOG_PATH)
        additional_info: Any additional context to include
        
    Returns:
        The error entry dictionary that was logged
    """
    if cycle_number is None:
        cycle_number = _current_cycle
    
    if log_path is None:
        log_path = DEFAULT_LOG_PATH
    
    # Ensure directory exists
    log_dir = os.path.dirname(log_path)
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)
    
    # Build structured error entry
    entry = {
        "cycle_number": cycle_number,
        "target_module": target_module,
        "error_type": parse_error_type(error),
        "error_message": str(error),
        "timestamp": datetime.utcnow().isoformat(),
        "unix_timestamp": time.time()
    }
    
    # Add any additional context
    if additional_info:
        entry["additional_info"] = additional_info
    
    # Append to JSONL file
    try:
        with open(log_path, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except (IOError, OSError) as e:
        # If we can't write to the log file, at least print a warning
        print(f"Warning: Could not write to error log {log_path}: {e}")
    
    # Update in-memory buffer
    _recent_errors.append(entry)
    if len(_recent_errors) > _max_recent_errors:
        _recent_errors.pop(0)
    
    return entry


def log_mutation_success(
    target_module: str,
    cycle_number: Optional[int] = None,
    log_path: Optional[str] = None,
    additional_info: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Log a successful mutation (useful for tracking success/failure ratios).
    
    Args:
        target_module: Name of the module that was successfully mutated
        cycle_number: Cycle number (defaults to current cycle)
        log_path: Path to log file (defaults to DEFAULT_LOG_PATH)
        additional_info: Any additional context to include
        
    Returns:
        The success entry dictionary that was logged
    """
    if cycle_number is None:
        cycle_number = _current_cycle
    
    if log_path is None:
        log_path = DEFAULT_LOG_PATH
    
    # Ensure directory exists
    log_dir = os.path.dirname(log_path)
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)
    
    # Build structured success entry
    entry = {
        "cycle_number": cycle_number,
        "target_module": target_module,
        "error_type": "SUCCESS",
        "error_message": "Mutation applied successfully",
        "timestamp": datetime.utcnow().isoformat(),
        "unix_timestamp": time.time()
    }
    
    # Add any additional context
    if additional_info:
        entry["additional_info"] = additional_info
    
    # Append to JSONL file
    try:
        with open(log_path, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except (IOError, OSError) as e:
        print(f"Warning: Could not write to success log {log_path}: {e}")
    
    # Update in-memory buffer
    _recent_errors.append(entry)
    if len(_recent_errors) > _max_recent_errors:
        _recent_errors.pop(0)
    
    return entry


def get_recent_errors(count: int = 10) -> list:
    """Get the most recent error entries from the in-memory buffer.
    
    Args:
        count: Number of recent errors to return
        
    Returns:
        List of recent error entry dictionaries
    """
    return _recent_errors[-count:] if _recent_errors else []


def get_error_count(
    log_path: Optional[str] = None,
    cycle_number: Optional[int] = None,
    error_type: Optional[str] = None
) -> int:
    """Count errors matching given criteria.
    
    Args:
        log_path: Path to log file (defaults to DEFAULT_LOG_PATH)
        cycle_number: Filter by cycle number
        error_type: Filter by error type
        
    Returns:
        Number of matching error entries
    """
    if log_path is None:
        log_path = DEFAULT_LOG_PATH
    
    if not os.path.exists(log_path):
        return 0
    
    count = 0
    try:
        with open(log_path, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    if cycle_number is not None and entry.get("cycle_number") != cycle_number:
                        continue
                    if error_type is not None and entry.get("error_type") != error_type:
                        continue
                    count += 1
                except json.JSONDecodeError:
                    continue
    except (IOError, OSError):
        return 0
    
    return count


def get_errors_by_module(
    module_name: str,
    log_path: Optional[str] = None,
    limit: int = 100
) -> list:
    """Get all errors for a specific module.
    
    Args:
        module_name: Name of the module to filter by
        log_path: Path to log file (defaults to DEFAULT_LOG_PATH)
        limit: Maximum number of entries to return
        
    Returns:
        List of error entry dictionaries for the specified module
    """
    if log_path is None:
        log_path = DEFAULT_LOG_PATH
    
    if not os.path.exists(log_path):
        return []
    
    errors = []
    try:
        with open(log_path, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    if entry.get("target_module") == module_name:
                        errors.append(entry)
                        if len(errors) >= limit:
                            break
                except json.JSONDecodeError:
                    continue
    except (IOError, OSError):
        return []
    
    return errors


def clear_log(log_path: Optional[str] = None) -> bool:
    """Clear the error log file.
    
    Args:
        log_path: Path to log file (defaults to DEFAULT_LOG_PATH)
        
    Returns:
        True if successful, False otherwise
    """
    if log_path is None:
        log_path = DEFAULT_LOG_PATH
    
    try:
        # Clear the file by opening in write mode
        with open(log_path, "w") as f:
            f.write("")
        # Also clear the in-memory buffer
        _recent_errors.clear()
        return True
    except (IOError, OSError):
        return False


def get_error_summary(log_path: Optional[str] = None) -> Dict[str, Any]:
    """Get a summary of all errors in the log.
    
    Args:
        log_path: Path to log file (defaults to DEFAULT_LOG_PATH)
        
    Returns:
        Dictionary with error summary statistics
    """
    if log_path is None:
        log_path = DEFAULT_LOG_PATH
    
    if not os.path.exists(log_path):
        return {
            "total_errors": 0,
            "total_successes": 0,
            "error_types": {},
            "modules": {},
            "cycles": set()
        }
    
    summary = {
        "total_errors": 0,
        "total_successes": 0,
        "error_types": {},
        "modules": {},
        "cycles": set()
    }
    
    try:
        with open(log_path, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    error_type = entry.get("error_type", "UNKNOWN")
                    module = entry.get("target_module", "UNKNOWN")
                    cycle = entry.get("cycle_number")
                    
                    if error_type == "SUCCESS":
                        summary["total_successes"] += 1
                    else:
                        summary["total_errors"] += 1
                        summary["error_types"][error_type] = summary["error_types"].get(error_type, 0) + 1
                    
                    summary["modules"][module] = summary["modules"].get(module, 0) + 1
                    
                    if cycle is not None:
                        summary["cycles"].add(cycle)
                except json.JSONDecodeError:
                    continue
    except (IOError, OSError):
        pass
    
    # Convert set to list for JSON serialization
    summary["cycles"] = list(summary["cycles"])
    summary["total_entries"] = summary["total_errors"] + summary["total_successes"]
    
    return summary


# Convenience function for integration with evolution loop
def wrap_mutation_with_logging(mutation_func):
    """Decorator to automatically log mutation results.
    
    Usage in evolution loop:
        @wrap_mutation_with_logging
        def apply_mutation(module, ...):
            ...
    """
    def wrapper(module_name, *args, **kwargs):
        try:
            result = mutation_func(module_name, *args, **kwargs)
            log_mutation_success(module_name)
            return result
        except Exception as e:
            log_mutation_error(module_name, e)
            raise  # Re-raise to maintain existing error handling
    return wrapper