"""Self-diagnosis module for analyzing failure logs and recommending test coverage improvements."""

import os
import json
from collections import Counter
from typing import List, Dict, Optional, Tuple
from datetime import datetime

# Path to failure logs (adjust as needed)
FAILURE_LOG_DIR = os.path.join(os.path.dirname(__file__), "..", "logs", "failures")
DEFAULT_LOG_COUNT = 20


def _load_failure_logs(last_n: int = DEFAULT_LOG_COUNT) -> List[Dict]:
    """Load the last N failure logs from the failure log directory."""
    if not os.path.isdir(FAILURE_LOG_DIR):
        return []

    log_files = sorted(
        [f for f in os.listdir(FAILURE_LOG_DIR) if f.endswith(".json")],
        key=lambda f: os.path.getmtime(os.path.join(FAILURE_LOG_DIR, f)),
        reverse=True,
    )[:last_n]

    logs = []
    for fname in log_files:
        fpath = os.path.join(FAILURE_LOG_DIR, fname)
        try:
            with open(fpath, "r") as f:
                data = json.load(f)
                logs.append(data)
        except (json.JSONDecodeError, IOError):
            continue
    return logs


def _extract_error_type(log: Dict) -> Optional[str]:
    """Extract the primary error type from a single failure log entry."""
    # Try common keys where error type might be stored
    for key in ["error_type", "error", "exception", "type", "failure_type"]:
        val = log.get(key)
        if val and isinstance(val, str):
            return val.strip().lower()
    # Fallback: look for 'message' or 'traceback' and infer
    msg = log.get("message", "") or log.get("traceback", "") or ""
    if "assertionerror" in msg.lower():
        return "assertionerror"
    if "syntaxerror" in msg.lower():
        return "syntaxerror"
    if "typeerror" in msg.lower():
        return "typeerror"
    if "valueerror" in msg.lower():
        return "valueerror"
    if "keyerror" in msg.lower():
        return "keyerror"
    if "importerror" in msg.lower():
        return "importerror"
    if "runtimeerror" in msg.lower():
        return "runtimeerror"
    return None


def get_most_common_error_type(last_n: int = DEFAULT_LOG_COUNT) -> Optional[Tuple[str, int]]:
    """Return the most common error type and its count from the last N failure logs."""
    logs = _load_failure_logs(last_n)
    if not logs:
        return None

    error_types = []
    for log in logs:
        etype = _extract_error_type(log)
        if etype:
            error_types.append(etype)

    if not error_types:
        return None

    counter = Counter(error_types)
    most_common = counter.most_common(1)[0]  # (error_type, count)
    return most_common


def analyze_test_coverage_gaps(last_n: int = DEFAULT_LOG_COUNT) -> Dict:
    """
    Scan the last N failure logs, extract the most common error type,
    and return a recommendation for a new test case that would catch that error earlier.

    Returns a dict with keys:
        - most_common_error_type: str
        - occurrence_count: int
        - total_logs_analyzed: int
        - recommendation: str (suggested test case description)
        - timestamp: str (ISO format)
    """
    logs = _load_failure_logs(last_n)
    total_logs = len(logs)

    if total_logs == 0:
        return {
            "most_common_error_type": None,
            "occurrence_count": 0,
            "total_logs_analyzed": 0,
            "recommendation": "No failure logs found. Consider running the system to generate logs.",
            "timestamp": datetime.utcnow().isoformat(),
        }

    most_common = get_most_common_error_type(last_n)
    if most_common is None:
        return {
            "most_common_error_type": None,
            "occurrence_count": 0,
            "total_logs_analyzed": total_logs,
            "recommendation": "No recognizable error types found in the logs. Consider improving log format.",
            "timestamp": datetime.utcnow().isoformat(),
        }

    error_type, count = most_common

    # Generate a recommendation based on the error type
    recommendation = _generate_test_recommendation(error_type, count, total_logs)

    return {
        "most_common_error_type": error_type,
        "occurrence_count": count,
        "total_logs_analyzed": total_logs,
        "recommendation": recommendation,
        "timestamp": datetime.utcnow().isoformat(),
    }


def _generate_test_recommendation(error_type: str, count: int, total: int) -> str:
    """Generate a human-readable test case recommendation based on the error type."""
    ratio = count / max(total, 1)

    base = f"Most common error: '{error_type}' (occurred {count} out of {total} times). "

    if error_type == "assertionerror":
        return base + "Recommend adding a unit test that validates critical assertions early in the workflow, " \
                       "especially for edge cases and boundary conditions."
    elif error_type == "syntaxerror":
        return base + "Recommend adding a static analysis or linting test that runs before execution " \
                       "to catch syntax errors early."
    elif error_type == "typeerror":
        return base + "Recommend adding a type-checking test (e.g., with mypy or isinstance checks) " \
                       "for the most frequently failing function arguments."
    elif error_type == "valueerror":
        return base + "Recommend adding a test that validates input ranges and formats " \
                       "before they are passed to the core logic."
    elif error_type == "keyerror":
        return base + "Recommend adding a test that ensures all expected dictionary keys are present " \
                       "before access, especially in data transformation functions."
    elif error_type == "importerror":
        return base + "Recommend adding a test that verifies all module imports succeed " \
                       "in the target environment, possibly with a dry-run import test."
    elif error_type == "runtimeerror":
        return base + "Recommend adding a test that simulates the failing runtime scenario " \
                       "with mocked dependencies to catch runtime errors earlier."
    else:
        return base + f"Recommend adding a targeted test case that exercises the conditions leading to '{error_type}' " \
                       f"failures, based on the most recent failure logs."


# Optional: if run as a script, print the analysis
if __name__ == "__main__":
    result = analyze_test_coverage_gaps()
    print(json.dumps(result, indent=2))