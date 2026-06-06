"""Lightweight integration hook for Nash equilibrium detection and coordinated multi-module forcing.

This module provides a hook that the evolution orchestrator can call after each mutation
cycle to check if the system has reached a Nash equilibrium state, and if so, trigger
coordinated multi-module changes to escape local optima.
"""

import json
import logging
import os
from typing import Dict, Any, List

# Set up logging
logger = logging.getLogger(__name__)

# State file for tracking mutation attempts
_STATE_FILE = "nash_integration_state.json"
# Number of consecutive failed single-module attempts to consider equilibrium
_EQUILIBRIUM_THRESHOLD = 5

# Flag to track if nash_detector_and_forcer is available
_nash_detector_and_forcer_available = None


def _check_nash_detector_and_forcer() -> bool:
    """Check if the nash_detector_and_forcer module exists and is importable.
    
    Returns:
        True if the module can be imported, False otherwise.
    """
    global _nash_detector_and_forcer_available
    if _nash_detector_and_forcer_available is not None:
        return _nash_detector_and_forcer_available
    
    try:
        import importlib
        importlib.import_module('core.nash_detector_and_forcer')
        _nash_detector_and_forcer_available = True
        logger.debug("nash_detector_and_forcer module is available")
    except ImportError:
        _nash_detector_and_forcer_available = False
        logger.warning("nash_detector_and_forcer module not found - skipping Nash-related logic")
    except Exception as e:
        _nash_detector_and_forcer_available = False
        logger.warning(f"Error importing nash_detector_and_forcer module: {e} - skipping Nash-related logic")
    
    return _nash_detector_and_forcer_available


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


def check_and_force_nash(state_dict: Dict[str, Any]) -> List[str]:
    """Check if system is at Nash equilibrium and force coordinated changes if so.

    This function imports from nash_detector_and_forcer and uses its detection
    and forcing capabilities. It isolates the import chain so the orchestrator
    can safely call this hook.

    Args:
        state_dict: Dictionary containing the current system state, including
            mutation results and module interaction metrics.

    Returns:
        List of changes made (e.g., module names that were forced to change),
        or empty list if no equilibrium was detected or no changes were needed.
    """
    # Check if nash_detector_and_forcer is available before proceeding
    if not _check_nash_detector_and_forcer():
        logger.debug("Skipping Nash equilibrium check - nash_detector_and_forcer not available")
        return []

    try:
        from core.nash_detector_and_forcer import detect_and_force_nash
        
        # Call the detection and forcing function with the state dictionary
        changes = detect_and_force_nash(state_dict)
        
        if changes:
            logger.info(f"Nash equilibrium detected and forced changes: {changes}")
            return changes
        else:
            logger.debug("No Nash equilibrium detected or no changes needed")
            return []
            
    except ImportError:
        logger.warning("Failed to import detect_and_force_nash from nash_detector_and_forcer")
        return []
    except Exception as e:
        logger.error(f"Error in check_and_force_nash: {e}")
        return []


def record_attempt(success: bool) -> None:
    """Record the result of a mutation attempt and check for equilibrium.

    Args:
        success: True if the mutation was successful, False otherwise.
    """
    # Check if nash_detector_and_forcer is available before proceeding
    if not _check_nash_detector_and_forcer():
        logger.debug("Skipping Nash equilibrium check - nash_detector_and_forcer not available")
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
            # Use the new check_and_force_nash function with an empty state dict
            # to trigger the coordinated change
            check_and_force_nash({})
            # Reset after triggering to avoid repeated triggers
            state["consecutive_failures"] = 0

    _save_state(state)


def check_and_trigger() -> bool:
    """Check if system is at equilibrium and trigger coordinated change if so.

    Returns:
        True if a coordinated change was triggered, False otherwise.
    """
    # Check if nash_detector_and_forcer is available before proceeding
    if not _check_nash_detector_and_forcer():
        logger.debug("Skipping Nash equilibrium check - nash_detector_and_forcer not available")
        return False
    
    state = _load_state()
    if _is_at_equilibrium(state) and not state["in_equilibrium"]:
        state["in_equilibrium"] = True
        state["last_equilibrium_trigger"] = state["total_attempts"]
        # Use the new check_and_force_nash function with an empty state dict
        changes = check_and_force_nash({})
        if changes:
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