"""test_runner.py — Pressure test runner with adaptive disabling and evolutionary tracking."""

import os
import json
import time
import logging
from pathlib import Path
from typing import Callable, List, Tuple, Optional

logger = logging.getLogger(__name__)

PRESSURE_TRACKER_FILE = Path(".pressure_tracker.json")
PRESSURE_TAG = "pressure"
MAX_CONSECUTIVE_FAILURES = 3
COOLDOWN_CYCLES = 5


def _load_pressure_tracker() -> dict:
    """Load pressure test state from disk."""
    if PRESSURE_TRACKER_FILE.exists():
        try:
            with open(PRESSURE_TRACKER_FILE, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            logger.warning("Corrupted pressure tracker, resetting.")
    return {}


def _save_pressure_tracker(tracker: dict) -> None:
    """Persist pressure test state to disk."""
    try:
        with open(PRESSURE_TRACKER_FILE, "w") as f:
            json.dump(tracker, f, indent=2)
    except OSError as e:
        logger.error(f"Failed to save pressure tracker: {e}")


def _is_pressure_test_disabled(test_name: str, tracker: dict) -> bool:
    """Check if a pressure test is currently disabled due to repeated failures."""
    entry = tracker.get(test_name, {})
    consecutive_failures = entry.get("consecutive_failures", 0)
    cooldown_remaining = entry.get("cooldown_remaining", 0)

    if cooldown_remaining > 0:
        return True
    if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
        return True
    return False


def _record_result(test_name: str, passed: bool, tracker: dict) -> None:
    """Update tracker with test result and manage cooldown logic."""
    entry = tracker.setdefault(test_name, {"consecutive_failures": 0, "cooldown_remaining": 0, "total_runs": 0, "total_passes": 0})

    entry["total_runs"] += 1
    if passed:
        entry["total_passes"] += 1
        entry["consecutive_failures"] = 0
        entry["cooldown_remaining"] = 0
    else:
        entry["consecutive_failures"] += 1
        if entry["consecutive_failures"] >= MAX_CONSECUTIVE_FAILURES:
            entry["cooldown_remaining"] = COOLDOWN_CYCLES
            logger.info(f"Pressure test '{test_name}' disabled for {COOLDOWN_CYCLES} cycles due to {MAX_CONSECUTIVE_FAILURES} consecutive failures.")

    if entry["cooldown_remaining"] > 0:
        entry["cooldown_remaining"] -= 1


def get_pressure_tests(all_tests: List[Tuple[str, Callable]]) -> List[Tuple[str, Callable]]:
    """Filter tests tagged with 'pressure'."""
    return [(name, func) for name, func in all_tests if PRESSURE_TAG in name.lower()]


def run_pressure_test_cycle(
    normal_tests: List[Tuple[str, Callable]],
    pressure_tests: List[Tuple[str, Callable]],
    tracker: Optional[dict] = None,
) -> Tuple[int, int, dict]:
    """
    Run normal tests, then run enabled pressure tests.

    Returns:
        (normal_passed, normal_total, updated_tracker)
    """
    if tracker is None:
        tracker = _load_pressure_tracker()

    # Run normal tests
    normal_passed = 0
    normal_total = len(normal_tests)
    for name, func in normal_tests:
        try:
            func()
            normal_passed += 1
        except Exception:
            logger.warning(f"Normal test '{name}' failed.")

    # Run pressure tests
    pressure_passed = 0
    pressure_total = 0
    for name, func in pressure_tests:
        if _is_pressure_test_disabled(name, tracker):
            logger.debug(f"Skipping disabled pressure test '{name}'")
            continue
        pressure_total += 1
        try:
            func()
            _record_result(name, True, tracker)
            pressure_passed += 1
        except Exception:
            _record_result(name, False, tracker)
            logger.warning(f"Pressure test '{name}' failed.")

    _save_pressure_tracker(tracker)

    logger.info(
        f"Pressure test cycle: normal {normal_passed}/{normal_total} passed, "
        f"pressure {pressure_passed}/{pressure_total} passed"
    )

    return normal_passed, normal_total, tracker


def reset_pressure_tracker() -> None:
    """Delete the pressure tracker file to reset all state."""
    if PRESSURE_TRACKER_FILE.exists():
        PRESSURE_TRACKER_FILE.unlink()
        logger.info("Pressure tracker reset.")


def get_pressure_test_summary() -> dict:
    """Return a human-readable summary of pressure test health."""
    tracker = _load_pressure_tracker()
    summary = {}
    for test_name, entry in tracker.items():
        total = entry.get("total_runs", 0)
        passes = entry.get("total_passes", 0)
        pass_rate = (passes / total * 100) if total > 0 else 0.0
        summary[test_name] = {
            "total_runs": total,
            "total_passes": passes,
            "pass_rate": round(pass_rate, 1),
            "consecutive_failures": entry.get("consecutive_failures", 0),
            "disabled": _is_pressure_test_disabled(test_name, tracker),
        }
    return summary