"""
core/game_theory_integration.py

Lightweight integration module that connects nash_detector and multi_module_forcer
with the evolution orchestrator. Provides a hook function for post-cycle processing,
logging equilibrium detection and forced multi-module changes to a JSON file.
"""

import json
import os
import logging
from datetime import datetime
from typing import Dict, Any, Optional

from . import nash_detector
from . import multi_module_forcer

logger = logging.getLogger(__name__)

# Default path for the integration log
INTEGRATION_LOG_PATH = os.path.join(os.path.dirname(__file__), "game_theory_integration_log.json")


def _load_integration_log(log_path: str = INTEGRATION_LOG_PATH) -> Dict[str, Any]:
    """Load the existing integration log from disk, or return an empty structure."""
    if os.path.exists(log_path):
        try:
            with open(log_path, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Failed to load integration log from {log_path}: {e}")
            return {"cycles": [], "summary": {"total_cycles": 0, "equilibria_detected": 0, "forced_changes": 0}}
    return {"cycles": [], "summary": {"total_cycles": 0, "equilibria_detected": 0, "forced_changes": 0}}


def _save_integration_log(log_data: Dict[str, Any], log_path: str = INTEGRATION_LOG_PATH) -> None:
    """Save the integration log to disk."""
    try:
        with open(log_path, "w") as f:
            json.dump(log_data, f, indent=2)
    except IOError as e:
        logger.error(f"Failed to save integration log to {log_path}: {e}")


def post_cycle_hook(
    cycle_number: int,
    state_snapshot: Optional[Dict[str, Any]] = None,
    log_path: str = INTEGRATION_LOG_PATH
) -> Dict[str, Any]:
    """
    Hook function to be called by the orchestrator after each evolution cycle.

    This function:
    1. Runs Nash equilibrium detection on the current state.
    2. If an equilibrium is detected, triggers multi_module_forcer to break it.
    3. Logs the results to a JSON file.

    Args:
        cycle_number: The current cycle number.
        state_snapshot: Optional dictionary representing the current system state.
                        If None, nash_detector will attempt to infer state.
        log_path: Path to the JSON log file.

    Returns:
        A dictionary with keys:
            - "cycle": int
            - "equilibrium_detected": bool
            - "forced_changes": list of dicts describing changes made
            - "timestamp": ISO format string
    """
    log_data = _load_integration_log(log_path)

    # Step 1: Detect Nash equilibrium
    try:
        equilibrium_result = nash_detector.detect_equilibrium(state_snapshot)
        equilibrium_detected = equilibrium_result.get("is_equilibrium", False)
        equilibrium_details = equilibrium_result.get("details", {})
    except Exception as e:
        logger.error(f"nash_detector.detect_equilibrium failed: {e}")
        equilibrium_detected = False
        equilibrium_details = {"error": str(e)}

    # Step 2: If equilibrium, trigger multi_module_forcer
    forced_changes = []
    if equilibrium_detected:
        try:
            force_result = multi_module_forcer.force_multi_module_changes(
                cycle_number=cycle_number,
                equilibrium_details=equilibrium_details
            )
            forced_changes = force_result.get("changes", [])
        except Exception as e:
            logger.error(f"multi_module_forcer.force_multi_module_changes failed: {e}")
            forced_changes = [{"error": str(e)}]

    # Step 3: Build cycle record
    cycle_record = {
        "cycle": cycle_number,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "equilibrium_detected": equilibrium_detected,
        "equilibrium_details": equilibrium_details,
        "forced_changes": forced_changes
    }

    # Step 4: Update log data
    log_data["cycles"].append(cycle_record)
    log_data["summary"]["total_cycles"] += 1
    if equilibrium_detected:
        log_data["summary"]["equilibria_detected"] += 1
    log_data["summary"]["forced_changes"] += len(forced_changes)

    # Step 5: Save log
    _save_integration_log(log_data, log_path)

    logger.info(
        f"Cycle {cycle_number}: equilibrium={equilibrium_detected}, "
        f"forced_changes={len(forced_changes)}"
    )

    return {
        "cycle": cycle_number,
        "equilibrium_detected": equilibrium_detected,
        "forced_changes": forced_changes,
        "timestamp": cycle_record["timestamp"]
    }


def get_integration_summary(log_path: str = INTEGRATION_LOG_PATH) -> Dict[str, Any]:
    """Return the current summary from the integration log."""
    log_data = _load_integration_log(log_path)
    return log_data.get("summary", {})


def reset_integration_log(log_path: str = INTEGRATION_LOG_PATH) -> None:
    """Reset the integration log to an empty state."""
    initial_data = {"cycles": [], "summary": {"total_cycles": 0, "equilibria_detected": 0, "forced_changes": 0}}
    _save_integration_log(initial_data, log_path)
    logger.info(f"Integration log reset at {log_path}")