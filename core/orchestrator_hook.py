import json
import os
import time
from pathlib import Path

# File paths for state communication
EQUILIBRIUM_STATE_FILE = "equilibrium_state.json"
MUTATION_CYCLE_FILE = "mutation_cycle_state.json"
FORCE_TRIGGER_FILE = "force_trigger.json"

def load_json(filepath):
    """Load JSON from file, return empty dict if not found or invalid."""
    try:
        with open(filepath, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_json(filepath, data):
    """Save data as JSON to file."""
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2)

def get_current_cycle():
    """Read the current mutation cycle number from state file."""
    state = load_json(MUTATION_CYCLE_FILE)
    return state.get("cycle", 0)

def set_current_cycle(cycle):
    """Update the mutation cycle number in state file."""
    save_json(MUTATION_CYCLE_FILE, {"cycle": cycle, "timestamp": time.time()})

def check_equilibrium():
    """Call equilibrium_detector via file-based interface and return result."""
    # Trigger equilibrium detection by writing request
    request = {
        "action": "detect_equilibrium",
        "timestamp": time.time(),
        "cycle": get_current_cycle()
    }
    save_json(EQUILIBRIUM_STATE_FILE, request)
    
    # Wait briefly for detector to process (simulated async)
    time.sleep(0.1)
    
    # Read response
    response = load_json(EQUILIBRIUM_STATE_FILE)
    return response.get("equilibrium_detected", False), response.get("details", {})

def trigger_multi_module_force(equilibrium_details):
    """Trigger multi_module_forcer to generate and apply coordinated changes."""
    trigger_data = {
        "action": "force_multi_module_change",
        "equilibrium_details": equilibrium_details,
        "timestamp": time.time(),
        "cycle": get_current_cycle()
    }
    save_json(FORCE_TRIGGER_FILE, trigger_data)
    
    # Wait for forcer to process
    time.sleep(0.2)
    
    # Read result
    result = load_json(FORCE_TRIGGER_FILE)
    return result.get("status", "unknown"), result.get("applied_changes", [])

def run_post_mutation_hook():
    """
    Main hook function to be called after each mutation cycle.
    Checks for equilibrium and triggers multi-module force if detected.
    """
    cycle = get_current_cycle()
    print(f"[OrchestratorHook] Post-mutation hook running for cycle {cycle}")
    
    # Check equilibrium state
    equilibrium_detected, details = check_equilibrium()
    
    if equilibrium_detected:
        print(f"[OrchestratorHook] Equilibrium detected at cycle {cycle}!")
        print(f"[OrchestratorHook] Details: {details}")
        
        # Trigger coordinated multi-module change
        status, changes = trigger_multi_module_force(details)
        print(f"[OrchestratorHook] Multi-module force status: {status}")
        print(f"[OrchestratorHook] Applied changes: {changes}")
        
        # Update cycle counter after force
        set_current_cycle(cycle + 1)
    else:
        print(f"[OrchestratorHook] No equilibrium detected at cycle {cycle}")
        set_current_cycle(cycle + 1)

def initialize_hook():
    """Initialize the hook state files if they don't exist."""
    if not os.path.exists(MUTATION_CYCLE_FILE):
        set_current_cycle(0)
    if not os.path.exists(EQUILIBRIUM_STATE_FILE):
        save_json(EQUILIBRIUM_STATE_FILE, {"initialized": True, "timestamp": time.time()})
    if not os.path.exists(FORCE_TRIGGER_FILE):
        save_json(FORCE_TRIGGER_FILE, {"initialized": True, "timestamp": time.time()})
    print("[OrchestratorHook] Initialized state files")

if __name__ == "__main__":
    # Allow standalone testing
    initialize_hook()
    run_post_mutation_hook()