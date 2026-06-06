import json
import os
from typing import Optional, Dict, List, Any
from datetime import datetime

REGISTRY_FILE = os.path.join(os.path.dirname(__file__), "test_registry.json")

def _load_registry() -> List[Dict[str, Any]]:
    """Load the test registry from disk."""
    if not os.path.exists(REGISTRY_FILE):
        return []
    try:
        with open(REGISTRY_FILE, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return []

def _save_registry(registry: List[Dict[str, Any]]) -> None:
    """Save the test registry to disk."""
    with open(REGISTRY_FILE, "w") as f:
        json.dump(registry, f, indent=2)

def register_test(
    capability_id: str,
    test_file_path: str,
    test_function_name: str,
    last_result: str = "unknown",
    failure_reason: str = ""
) -> None:
    """Register a new test entry or update an existing one."""
    registry = _load_registry()
    now = datetime.utcnow().isoformat()

    # Check if entry already exists
    for entry in registry:
        if (entry["capability_id"] == capability_id and
            entry["test_file_path"] == test_file_path and
            entry["test_function_name"] == test_function_name):
            entry["last_run_timestamp"] = now
            entry["last_result"] = last_result
            entry["failure_reason"] = failure_reason
            _save_registry(registry)
            return

    # Create new entry
    entry = {
        "capability_id": capability_id,
        "test_file_path": test_file_path,
        "test_function_name": test_function_name,
        "last_run_timestamp": now,
        "last_result": last_result,
        "failure_reason": failure_reason
    }
    registry.append(entry)
    _save_registry(registry)

def get_test_result(
    capability_id: str,
    test_file_path: str,
    test_function_name: str
) -> Optional[Dict[str, Any]]:
    """Retrieve the latest test result for a given test."""
    registry = _load_registry()
    for entry in registry:
        if (entry["capability_id"] == capability_id and
            entry["test_file_path"] == test_file_path and
            entry["test_function_name"] == test_function_name):
            return entry
    return None

def has_test_been_run(
    capability_id: str,
    test_file_path: str,
    test_function_name: str
) -> bool:
    """Check if a specific test has been registered before."""
    return get_test_result(capability_id, test_file_path, test_function_name) is not None

def get_tests_for_capability(capability_id: str) -> List[Dict[str, Any]]:
    """Get all test entries for a given capability."""
    registry = _load_registry()
    return [entry for entry in registry if entry["capability_id"] == capability_id]

def clear_registry() -> None:
    """Clear all entries from the registry."""
    _save_registry([])

def update_test_result(
    capability_id: str,
    test_file_path: str,
    test_function_name: str,
    last_result: str,
    failure_reason: str = ""
) -> bool:
    """Update the result of an existing test entry. Returns True if updated, False if not found."""
    registry = _load_registry()
    now = datetime.utcnow().isoformat()
    for entry in registry:
        if (entry["capability_id"] == capability_id and
            entry["test_file_path"] == test_file_path and
            entry["test_function_name"] == test_function_name):
            entry["last_run_timestamp"] = now
            entry["last_result"] = last_result
            entry["failure_reason"] = failure_reason
            _save_registry(registry)
            return True
    return False