"""
failure_diagnosis_module.py

Module to read failure logs, parse error types, count occurrences, identify the most common error,
and generate targeted fix snippets.
"""

import re
import os
from collections import Counter
from typing import List, Tuple, Optional

# Default log file path (can be overridden)
DEFAULT_LOG_FILE = "failure_logs.txt"

# Mapping of error types to fix snippets
ERROR_FIX_MAP = {
    "ModuleNotFoundError": "import <missing_module>",
    "NameError": "<variable_name> = <initial_value>",
    "PermissionError": "os.chmod('<file_path>', 0o644)  # or appropriate permissions",
    "FileNotFoundError": "Ensure the file exists before accessing it.",
    "ValueError": "Check input values and validate before use.",
    "TypeError": "Ensure correct data types are used.",
    "IndexError": "Check list indices and ensure they are within range.",
    "KeyError": "Ensure dictionary keys exist before accessing.",
    "AttributeError": "Check object attributes and ensure they exist.",
    "ImportError": "Ensure the module is installed or the import path is correct.",
    "SyntaxError": "Check for syntax errors in the code.",
    "IndentationError": "Ensure consistent indentation (spaces vs tabs).",
    "ZeroDivisionError": "Add a check to avoid division by zero.",
    "OSError": "Check operating system level errors.",
    "RuntimeError": "Review runtime logic and error handling.",
}

# Default target file mapping (can be extended)
DEFAULT_TARGET_FILE = "main.py"


def read_last_n_logs(log_source: str = DEFAULT_LOG_FILE, n: int = 20) -> List[str]:
    """
    Read the last n lines from a log file or other source.

    Args:
        log_source: Path to the log file.
        n: Number of recent log entries to retrieve.

    Returns:
        List of log lines (strings).
    """
    logs = []
    try:
        with open(log_source, 'r') as f:
            # Read all lines and get the last n
            all_lines = f.readlines()
            logs = [line.strip() for line in all_lines[-n:]]
    except FileNotFoundError:
        print(f"Warning: Log file '{log_source}' not found. Returning empty list.")
    except Exception as e:
        print(f"Error reading log file: {e}")
    return logs


def parse_error_type(log_line: str) -> Optional[str]:
    """
    Extract the error type from a log line.

    Args:
        log_line: A single log line string.

    Returns:
        The error type (e.g., 'ModuleNotFoundError') or None if not found.
    """
    # Common patterns: "Error: <ErrorType>", "Traceback ... <ErrorType>:", etc.
    # Pattern to match common Python error types
    pattern = r'\b([A-Z][a-zA-Z]*Error)\b'
    match = re.search(pattern, log_line)
    if match:
        return match.group(1)
    return None


def count_error_types(logs: List[str]) -> Counter:
    """
    Count occurrences of each error type from a list of log lines.

    Args:
        logs: List of log lines.

    Returns:
        Counter object with error type counts.
    """
    error_counts = Counter()
    for log in logs:
        error_type = parse_error_type(log)
        if error_type:
            error_counts[error_type] += 1
    return error_counts


def get_most_common_error(error_counts: Counter) -> Optional[Tuple[str, int]]:
    """
    Identify the most common error type.

    Args:
        error_counts: Counter with error type counts.

    Returns:
        Tuple of (error_type, count) or None if no errors found.
    """
    if error_counts:
        return error_counts.most_common(1)[0]
    return None


def generate_fix_snippet(error_type: str, target_file: str = DEFAULT_TARGET_FILE) -> Tuple[str, str]:
    """
    Generate a targeted fix snippet for a given error type.

    Args:
        error_type: The error type string.
        target_file: The target file where the fix should be injected.

    Returns:
        Tuple of (fix_snippet, target_file).
    """
    # Get the generic fix template
    fix_template = ERROR_FIX_MAP.get(error_type, f"# Fix for {error_type}: Review and correct the issue.")

    # For some errors, we can provide more specific guidance
    if error_type == "ModuleNotFoundError":
        # Suggest a specific module name placeholder
        fix_snippet = "# Add missing import\nimport <module_name>  # Replace <module_name> with actual module"
    elif error_type == "NameError":
        fix_snippet = "# Initialize variable before use\n<variable_name> = None  # Replace with appropriate initial value"
    elif error_type == "PermissionError":
        fix_snippet = "# Fix permissions\nimport os\nos.chmod('<file_path>', 0o644)  # Adjust path and permissions as needed"
    elif error_type == "FileNotFoundError":
        fix_snippet = "# Ensure file exists before access\nimport os\nif os.path.exists('<file_path>'):\n    # proceed with file operations\nelse:\n    # handle missing file"
    else:
        fix_snippet = f"# Fix for {error_type}\n{fix_template}"

    return fix_snippet, target_file


def diagnose_and_fix(log_source: str = DEFAULT_LOG_FILE, n: int = 20, target_file: str = DEFAULT_TARGET_FILE) -> Optional[Tuple[str, str]]:
    """
    Main function to read logs, analyze errors, and generate a fix.

    Args:
        log_source: Path to the log file.
        n: Number of recent log entries to analyze.
        target_file: Target file for the fix injection.

    Returns:
        Tuple of (fix_snippet, target_file) or None if no errors found.
    """
    # Step 1: Read logs
    logs = read_last_n_logs(log_source, n)
    if not logs:
        print("No logs to analyze.")
        return None

    # Step 2 & 3: Parse and count error types
    error_counts = count_error_types(logs)
    if not error_counts:
        print("No recognizable error types found in logs.")
        return None

    # Step 4: Identify most common error
    most_common = get_most_common_error(error_counts)
    if most_common is None:
        print("No errors found.")
        return None

    error_type, count = most_common
    print(f"Most common error: {error_type} (occurred {count} times)")

    # Step 5 & 6: Generate fix snippet and return
    fix_snippet, target = generate_fix_snippet(error_type, target_file)
    print(f"Generated fix snippet for {error_type}")
    print(f"Target file: {target}")
    print(f"Fix snippet:\n{fix_snippet}")

    return fix_snippet, target


# Example usage (if run as script)
if __name__ == "__main__":
    # Example: analyze last 20 logs from default file
    result = diagnose_and_fix()
    if result:
        snippet, target = result
        print(f"\nTo apply fix, insert the following snippet into {target}:")
        print(snippet)