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

# Specific suggested fixes for components and failure types
COMPONENT_SPECIFIC_FIXES = {
    "mutation_engine": {
        "empty_results": "Mutation engine returned empty results: check mutation_generator.py line 42",
        "timeout": "Mutation engine timeout: optimize mutation generation or increase timeout in mutation_engine.py",
        "parse_error": "Mutation engine parse error: validate input format in mutation_parser.py",
    },
    "test_framework": {
        "empty_results": "Test framework returned empty results: check test_runner.py line 55",
        "timeout": "Test framework timeout: increase timeout threshold in test_config.py",
        "connection_error": "Test framework connection error: check network settings in test_network.py",
    },
    "reflection_parser": {
        "parse_error": "Reflection parser parse error: update parser logic in reflection_parser.py line 30",
        "timeout": "Reflection parser timeout: optimize parsing in reflection_parser.py",
    },
    "strategy_selector": {
        "invalid_state": "Strategy selector invalid state: reset state in strategy_selector.py line 20",
        "configuration_error": "Strategy selector configuration error: verify config in strategy_config.py",
    },
}

# Component versions mapping
COMPONENT_VERSIONS = {
    "mutation_engine": "2.1.0",
    "test_framework": "1.8.3",
    "reflection_parser": "3.0.1",
    "strategy_selector": "1.2.0",
}

def generate_bug_report(component_name, failure_type, timestamp=None, suggested_fix=None, pipeline_run_id=None):
    """
    Generate a bug report dictionary for a given component failure.
    
    Args:
        component_name (str): Name of the failing component.
        failure_type (str): Type of failure (e.g., 'timeout', 'parse_error').
        timestamp (str, optional): ISO format timestamp. Defaults to current time.
        suggested_fix (str, optional): Custom fix suggestion. Defaults to mapped fix.
        pipeline_run_id (str, optional): Identifier for the pipeline run.
    
    Returns:
        dict: Bug report with component, failure, timestamp, fix, priority, and run ID.
    """
    if timestamp is None:
        timestamp = datetime.utcnow().isoformat()
    
    priority = COMPONENT_CRITICALITY.get(component_name, LOW)
    
    if suggested_fix is None:
        # Check for component-specific fix first
        component_fixes = COMPONENT_SPECIFIC_FIXES.get(component_name, {})
        suggested_fix = component_fixes.get(failure_type)
        if suggested_fix is None:
            # Fall back to general failure fix map
            suggested_fix = FAILURE_FIX_MAP.get(failure_type, "Investigate and resolve manually.")
    
    report = {
        "component": component_name,
        "failure_type": failure_type,
        "timestamp": timestamp,
        "suggested_fix": suggested_fix,
        "priority": priority,
        "component_version": COMPONENT_VERSIONS.get(component_name, "unknown"),
    }
    
    if pipeline_run_id is not None:
        report["pipeline_run_id"] = pipeline_run_id
    
    return report

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

def write_markdown_report(report, filename="pipeline_bug_reports.md"):
    """
    Append a bug report to a human-readable markdown file.
    
    Args:
        report (dict): Bug report to write.
        filename (str): Path to the markdown file.
    """
    # Read existing content if file exists
    existing_content = ""
    if os.path.exists(filename):
        try:
            with open(filename, "r") as f:
                existing_content = f.read()
        except IOError:
            existing_content = ""
    
    # Create markdown entry for the new report
    markdown_entry = f"""
## Bug Report - {report['component']}

- **Component:** {report['component']}
- **Component Version:** {report.get('component_version', 'unknown')}
- **Failure Type:** {report['failure_type']}
- **Timestamp:** {report['timestamp']}
- **Priority:** {report['priority']}
- **Suggested Fix:** {report['suggested_fix']}
- **Pipeline Run ID:** {report.get('pipeline_run_id', 'N/A')}

---
"""
    
    # Write the new entry at the beginning of the file
    with open(filename, "w") as f:
        f.write(markdown_entry + existing_content)

def report_failure(component_name, failure_type, timestamp=None, suggested_fix=None, pipeline_run_id=None):
    """
    Convenience function to generate and persist a bug report in both JSON and markdown formats.
    
    Args:
        component_name (str): Name of the failing component.
        failure_type (str): Type of failure.
        timestamp (str, optional): ISO format timestamp.
        suggested_fix (str, optional): Custom fix suggestion.
        pipeline_run_id (str, optional): Identifier for the pipeline run.
    
    Returns:
        dict: The generated bug report.
    """
    report = generate_bug_report(component_name, failure_type, timestamp, suggested_fix, pipeline_run_id)
    write_bug_report(report)
    write_markdown_report(report)
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
    
    # Also clear the markdown file
    markdown_filename = filename.replace(".json", ".md")
    if os.path.exists(markdown_filename):
        with open(markdown_filename, "w") as f:
            f.write("")

def generate_pipeline_report(pipeline_run_id, filename="pipeline_bug_reports.json"):
    """
    Generate a summary of all broken links found in a single pipeline run.
    
    Args:
        pipeline_run_id (str): The pipeline run ID to filter reports.
        filename (str): Path to the JSON file containing reports.
    
    Returns:
        dict: Summary report with total failures, component breakdown, and details.
    """
    all_reports = get_all_reports(filename)
    run_reports = [r for r in all_reports if r.get("pipeline_run_id") == pipeline_run_id]
    
    if not run_reports:
        return {
            "pipeline_run_id": pipeline_run_id,
            "total_failures": 0,
            "components": {},
            "details": [],
            "generated_at": datetime.utcnow().isoformat()
        }
    
    component_breakdown = {}
    for report in run_reports:
        component = report["component"]
        if component not in component_breakdown:
            component_breakdown[component] = {"total": 0, "failures": []}
        component_breakdown[component]["total"] += 1
        component_breakdown[component]["failures"].append({
            "failure_type": report["failure_type"],
            "timestamp": report["timestamp"],
            "priority": report["priority"]
        })
    
    return {
        "pipeline_run_id": pipeline_run_id,
        "total_failures": len(run_reports),
        "components": component_breakdown,
        "details": run_reports,
        "generated_at": datetime.utcnow().isoformat()
    }

def get_critical_path_failures(pipeline_run_id=None, filename="pipeline_bug_reports.json"):
    """
    Return only P0 (CRITICAL priority) failures that are blocking the pipeline.
    
    Args:
        pipeline_run_id (str, optional): If provided, filter by pipeline run ID.
        filename (str): Path to the JSON file containing reports.
    
    Returns:
        list: List of CRITICAL priority bug reports.
    """
    all_reports = get_all_reports(filename)
    
    if pipeline_run_id:
        filtered_reports = [r for r in all_reports if r.get("pipeline_run_id") == pipeline_run_id]
    else:
        filtered_reports = all_reports
    
    critical_failures = [r for r in filtered_reports if r.get("priority") == CRITICAL]
    return critical_failures