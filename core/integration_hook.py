"""
core/integration_hook.py

Lightweight integration hook that checks for Nash equilibrium after each mutation cycle.
If equilibrium is detected, forces a change via multi_module_forcer and logs the event.
"""

import json
import os
import time
from typing import Any, Dict, Optional

# Import local modules
from core import nash_detector
from core import multi_module_forcer

# Constants
LOG_FILE = "forced_changes_log.json"
DEFAULT_LOG_PATH = os.path.join(os.path.dirname(__file__), "..", LOG_FILE)


def _load_log(log_path: str) -> list:
    """Load existing log entries from JSON file."""
    if os.path.exists(log_path):
        try:
            with open(log_path, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return []
    return []


def _save_log(log_path: str, entries: list) -> None:
    """Save log entries to JSON file."""
    try:
        with open(log_path, "w") as f:
            json.dump(entries, f, indent=2)
    except IOError as e:
        print(f"Warning: Could not write log file {log_path}: {e}")


def run_integration_hook(
    cycle_number: int,
    population: Any,
    log_path: Optional[str] = None,
    force_change: bool = True,
) -> Dict[str, Any]:
    """
    Run the integration hook after a mutation cycle.

    Args:
        cycle_number: Current evolution cycle number.
        population: Current population state (passed to nash_detector).
        log_path: Path to JSON log file. Defaults to '../forced_changes_log.json'.
        force_change: If True, actually force a change when Nash detected.

    Returns:
        Dictionary with hook results:
            - nash_detected: bool
            - change_forced: bool
            - change_details: dict or None
    """
    if log_path is None:
        log_path = DEFAULT_LOG_PATH

    result = {
        "nash_detected": False,
        "change_forced": False,
        "change_details": None,
    }

    # Step 1: Check for Nash equilibrium
    try:
        nash_result = nash_detector.is_at_nash(population)
        nash_detected = bool(nash_result.get("is_nash", False))
    except Exception as e:
        print(f"Warning: nash_detector.is_at_nash() failed: {e}")
        nash_detected = False

    result["nash_detected"] = nash_detected

    if not nash_detected:
        return result

    # Step 2: Force a change if Nash detected
    if force_change:
        try:
            change_details = multi_module_forcer.force_change(
                cycle_number=cycle_number,
                reason="Nash equilibrium detected"
            )
            result["change_forced"] = True
            result["change_details"] = change_details
        except Exception as e:
            print(f"Warning: multi_module_forcer.force_change() failed: {e}")
            result["change_details"] = {"error": str(e)}

    # Step 3: Log the forced change
    log_entry = {
        "timestamp": time.time(),
        "cycle_number": cycle_number,
        "nash_detected": nash_detected,
        "change_forced": result["change_forced"],
        "change_details": result["change_details"],
    }

    log_entries = _load_log(log_path)
    log_entries.append(log_entry)
    _save_log(log_path, log_entries)

    return result


def get_log_summary(log_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Get a summary of all forced changes from the log file.

    Args:
        log_path: Path to JSON log file.

    Returns:
        Dictionary with summary statistics.
    """
    if log_path is None:
        log_path = DEFAULT_LOG_PATH

    entries = _load_log(log_path)

    total_cycles = len(entries)
    nash_detections = sum(1 for e in entries if e.get("nash_detected"))
    forced_changes = sum(1 for e in entries if e.get("change_forced"))

    return {
        "total_cycles_logged": total_cycles,
        "nash_detections": nash_detections,
        "forced_changes": forced_changes,
        "last_entry": entries[-1] if entries else None,
    }