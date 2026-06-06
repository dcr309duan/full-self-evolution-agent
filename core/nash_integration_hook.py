"""Lightweight integration hook for Nash equilibrium detection and coordinated multi-module forcing.

This module provides a hook that the evolution orchestrator can call after each mutation
cycle to check if the system has reached a Nash equilibrium state, and if so, trigger
coordinated multi-module changes to escape local optima.
"""

import json
import logging
import os
from typing import Optional, Dict, Any

# Set up logging
logger = logging.getLogger(__name__)

# State file for tracking mutation attempts
_STATE_FILE = "nash_integration_state.json"
# Number of consecutive failed single-module attempts to consider equilibrium
_EQUILIBRIUM_THRESHOLD = 5

# Flag to track if nash_detector is available
_nash_detector_available = None


def _check_nash_detector() -> bool:
    """Check if the nash_detector module exists and is importable.
    
    Returns:
        True if the module can be imported, False otherwise.
    """
    global _nash_detector_available
    if _nash_detector_available is not None:
        return _nash_detector_available
    
    try:
        import importlib
        importlib.import_module('core.nash_detector')
        _nash_detector_available = True
        logger.debug("nash_detector module is available")
    except ImportError:
        _nash_detector_available = False
        logger.warning("nash_detector module not found - skipping Nash-related logic")
    except Exception as e:
        _nash_detector_available = False
        logger.warning(f"Error importing nash_detector module: {e} - skipping Nash-related logic")
    
    return _nash_detector_available


def _load_state() -> Dict[str, Any]:
    """Load the integration state from disk."""
    if os.path.exists(_STATE_FILE):
        try:
            with open(_STATE_FILE, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {
        "consecutive_failures": 0,
        "total_attempts": 0,
        "last_equilibrium_trigger": None,
        "in_equilibrium": False,
    }


def _save_state(state: Dict[str, Any]) -> None:
    """Save the integration state to disk."""
    try:
        with open(_STATE_FILE, "w") as f:
            json.dump(state, f)
    except IOError:
        pass


def _is_at_equilibrium(state: Dict[str, Any]) -> bool:
    """Check if the system appears to be at a Nash equilibrium.

    A Nash equilibrium in this context means no single-module improvement
    has been found in the last N consecutive attempts.
    """
    return state["consecutive_failures"] >= _EQUILIBRIUM_THRESHOLD


def _trigger_coordinated_change() -> None:
    """Trigger a coordinated multi-module change via the forcer.

    This function attempts to import and call the multi_module_forcer's
    coordinated change function. If the import fails, it logs the issue
    silently.
    """
    try:
        from core.multi_module_forcer import force_coordinated_change
        force_coordinated_change()
    except ImportError:
        # Forcer module not available; silently skip
        pass
    except Exception:
        # Any other error during forcing; silently skip
        pass


def record_attempt(success: bool) -> None:
    """Record the result of a mutation attempt and check for equilibrium.

    Args:
        success: True if the mutation was successful, False otherwise.
    """
    # Check if nash_detector is available before proceeding
    if not _check_nash_detector():
        logger.debug("Skipping Nash equilibrium check - nash_detector not available")
        return
    
    state = _load_state()
    state["total_attempts"] += 1

    if success:
        state["consecutive_failures"] = 0
        state["in_equilibrium"] = False
    else:
        state["consecutive_failures"] += 1
        if _is_at_equilibrium(state):
            state["in_equilibrium"] = True
            state["last_equilibrium_trigger"] = state["total_attempts"]
            _trigger_coordinated_change()
            # Reset after triggering to avoid repeated triggers
            state["consecutive_failures"] = 0

    _save_state(state)


def check_and_trigger() -> bool:
    """Check if system is at equilibrium and trigger coordinated change if so.

    Returns:
        True if a coordinated change was triggered, False otherwise.
    """
    # Check if nash_detector is available before proceeding
    if not _check_nash_detector():
        logger.debug("Skipping Nash equilibrium check - nash_detector not available")
        return False
    
    state = _load_state()
    if _is_at_equilibrium(state) and not state["in_equilibrium"]:
        state["in_equilibrium"] = True
        state["last_equilibrium_trigger"] = state["total_attempts"]
        _trigger_coordinated_change()
        state["consecutive_failures"] = 0
        _save_state(state)
        return True
    return False


def reset_state() -> None:
    """Reset the integration state to initial values."""
    state = {
        "consecutive_failures": 0,
        "total_attempts": 0,
        "last_equilibrium_trigger": None,
        "in_equilibrium": False,
    }
    _save_state(state)


def get_state_summary() -> Dict[str, Any]:
    """Get a summary of the current integration state.

    Returns:
        Dictionary with state information.
    """
    return _load_state()