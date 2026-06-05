from datetime import datetime
import json
import os

# Priority levels
CRITICAL = "CRITICAL"
HIGH = "HIGH"
MEDIUM = "MEDIUM"
LOW = "LOW"

# Component criticality mapping
COMPONENT_CRITICALITY = {
    "mutation_engine": CRITICAL,
    "test_framework": CRITICAL,
    "reflection_parser": HIGH,
    "strategy_selector": MEDIUM,
}

# Suggested fixes for common failure types
FAILURE_FIX_MAP = {
    "timeout": "Increase timeout threshold or optimize component performance.",
    "connection_error": "Check network connectivity and service availability.",
    "parse_error": "Validate input format and update parser logic.",
    "memory_exhaustion": "Optimize memory usage or increase allocated resources.",
    "unexpected_exception": "Review component logic and add exception handling.",
    "invalid_state": "Reset component state or reinitialize dependencies.",
    "dependency_missing": "Install or update required dependencies.",
    "configuration_error": "Verify configuration file and correct invalid settings.",
}

def generate_bug_report(component_name, failure_type, timestamp=None, suggested_fix=None):
    """
    Generate a bug report dictionary for a given component failure.
    
    Args:
        component_name (str): Name of the failing component.
        failure_type (str): Type of failure (e.g., 'timeout', 'parse_error').
        timestamp (str, optional): ISO format timestamp. Defaults to current time.
        suggested_fix (str, optional): Custom fix suggestion. Defaults to mapped fix.
    
    Returns:
        dict: Bug report with component, failure, timestamp, fix, and priority.
    """
    if timestamp is None:
        timestamp = datetime.utcnow().isoformat()
    
    priority = COMPONENT_CRITICALITY.get(component_name, LOW)
    
    if suggested_fix is None:
        suggested_fix = FAILURE_FIX_MAP.get(failure_type, "Investigate and resolve manually.")
    
    return {
        "component": component_name,
        "failure_type": failure_type,
        "timestamp": timestamp,
        "suggested_fix": suggested_fix,
        "priority": priority,
    }

def write_bug_report(report, filename="pipeline_bug_reports.json"):
    """
    Append a bug report to the persistent JSON file.
    
    Args:
        report (dict): Bug report to write.
        filename (str): Path to the JSON file.
    """
    reports = []
    if os.path.exists(filename):
        try:
            with open(filename, "r") as f:
                reports = json.load(f)
        except (json.JSONDecodeError, IOError):
            reports = []
    
    reports.append(report)
    
    with open(filename, "w") as f:
        json.dump(reports, f, indent=2)

def report_failure(component_name, failure_type, timestamp=None, suggested_fix=None):
    """
    Convenience function to generate and persist a bug report in one call.
    
    Args:
        component_name (str): Name of the failing component.
        failure_type (str): Type of failure.
        timestamp (str, optional): ISO format timestamp.
        suggested_fix (str, optional): Custom fix suggestion.
    
    Returns:
        dict: The generated bug report.
    """
    report = generate_bug_report(component_name, failure_type, timestamp, suggested_fix)
    write_bug_report(report)
    return report

def get_all_reports(filename="pipeline_bug_reports.json"):
    """
    Retrieve all stored bug reports from the JSON file.
    
    Args:
        filename (str): Path to the JSON file.
    
    Returns:
        list: List of bug report dictionaries.
    """
    if not os.path.exists(filename):
        return []
    try:
        with open(filename, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return []

def clear_reports(filename="pipeline_bug_reports.json"):
    """
    Clear all stored bug reports by resetting the JSON file.
    
    Args:
        filename (str): Path to the JSON file.
    """
    with open(filename, "w") as f:
        json.dump([], f)