import json
import os
import random

STATE_FILE = "state.json"
INITIAL_STATE = {"version": 1, "goals_achieved": 0, "complexity": 0.5}
HARDCODED_GOALS = [
    "increase complexity by 0.1",
    "add a new key 'iterations' with value 0",
    "increment goals_achieved by 1",
    "add a key 'last_goal' with a string description",
    "set complexity to 1.0 if below 0.8"
]
ESSENTIAL_MODULES = [
    "reflect",
    "generate_goal",
    "mutate",
    "test",
    "accept",
    "sandbox_validate",
    "self_healing_recovery"
]

def reflect(state):
    """Analyze the state dictionary and return a summary."""
    summary = {}
    summary["keys"] = list(state.keys())
    summary["version"] = state.get("version", None)
    summary["goals_achieved"] = state.get("goals_achieved", 0)
    summary["complexity"] = state.get("complexity", None)
    return summary

def generate_goal():
    """Pick one improvement from the hardcoded list."""
    return random.choice(HARDCODED_GOALS)

def mutate(state, goal):
    """Apply the change described by the goal to the state dictionary."""
    new_state = state.copy()
    if goal == "increase complexity by 0.1":
        new_state["complexity"] = new_state.get("complexity", 0) + 0.1
    elif goal == "add a new key 'iterations' with value 0":
        if "iterations" not in new_state:
            new_state["iterations"] = 0
    elif goal == "increment goals_achieved by 1":
        new_state["goals_achieved"] = new_state.get("goals_achieved", 0) + 1
    elif goal == "add a key 'last_goal' with a string description":
        new_state["last_goal"] = goal
    elif goal == "set complexity to 1.0 if below 0.8":
        if new_state.get("complexity", 0) < 0.8:
            new_state["complexity"] = 1.0
    return new_state

def test(state):
    """Verify the state is valid JSON and contains expected keys."""
    try:
        json.dumps(state)
    except (TypeError, ValueError):
        return False
    expected_keys = {"version", "goals_achieved", "complexity"}
    return expected_keys.issubset(state.keys())

def accept(state):
    """Update the state file with the given state dictionary."""
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)

def load_or_initialize_state():
    """Load state from file or create initial state."""
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    else:
        accept(INITIAL_STATE)
        return INITIAL_STATE.copy()

def sandbox_validate(state):
    """Validate state in a sandboxed manner before acceptance."""
    try:
        # Deep copy to avoid modifying original
        test_state = json.loads(json.dumps(state))
        # Run test on copy
        if not test(test_state):
            return False, "Test validation failed"
        # Verify state is serializable
        json.dumps(test_state)
        return True, "Sandbox validation passed"
    except Exception as e:
        return False, f"Sandbox validation error: {str(e)}"

def self_healing_recovery(state):
    """Recover state to a valid baseline if corruption is detected."""
    try:
        # Check if state is valid JSON
        json.dumps(state)
    except (TypeError, ValueError):
        print("State corruption detected. Recovering to initial state.")
        return INITIAL_STATE.copy()
    
    # Check for required keys
    required_keys = {"version", "goals_achieved", "complexity"}
    if not required_keys.issubset(state.keys()):
        print("Missing required keys. Recovering to initial state.")
        return INITIAL_STATE.copy()
    
    # Check for invalid values
    if not isinstance(state.get("version"), int) or state["version"] < 1:
        print("Invalid version. Recovering to initial state.")
        return INITIAL_STATE.copy()
    
    if not isinstance(state.get("goals_achieved"), int) or state["goals_achieved"] < 0:
        print("Invalid goals_achieved. Recovering to initial state.")
        return INITIAL_STATE.copy()
    
    if not isinstance(state.get("complexity"), (int, float)) or state["complexity"] < 0:
        print("Invalid complexity. Recovering to initial state.")
        return INITIAL_STATE.copy()
    
    # State is valid, return as is
    return state

def initialize_recovery_module():
    """Initialize the recovery module during bootstrap."""
    print("Initializing self-healing recovery module...")
    # Verify essential modules are available
    for module in ESSENTIAL_MODULES:
        if module not in globals():
            print(f"Warning: Essential module '{module}' not found during recovery initialization")
    
    # Test recovery function
    test_state = {"version": 1, "goals_achieved": 0, "complexity": 0.5}
    recovered = self_healing_recovery(test_state)
    if recovered == test_state:
        print("Recovery module initialized successfully.")
        return True
    else:
        print("Recovery module initialization failed.")
        return False

def test_recovery_integration():
    """Test recovery functionality in minimal core integration test."""
    print("\n--- Recovery Integration Test ---")
    
    # Test 1: Valid state should pass through
    valid_state = {"version": 1, "goals_achieved": 0, "complexity": 0.5}
    result = self_healing_recovery(valid_state)
    assert result == valid_state, "Test 1 failed: Valid state should remain unchanged"
    print("Test 1 passed: Valid state remains unchanged")
    
    # Test 2: Corrupted state should recover to initial
    corrupted_state = {"version": "invalid", "goals_achieved": -1, "complexity": "bad"}
    result = self_healing_recovery(corrupted_state)
    assert result == INITIAL_STATE, "Test 2 failed: Corrupted state should recover to initial"
    print("Test 2 passed: Corrupted state recovers to initial")
    
    # Test 3: Missing keys should recover
    missing_keys_state = {"version": 1}
    result = self_healing_recovery(missing_keys_state)
    assert result == INITIAL_STATE, "Test 3 failed: Missing keys should trigger recovery"
    print("Test 3 passed: Missing keys trigger recovery")
    
    # Test 4: Non-serializable state should recover
    non_serializable_state = {"version": 1, "goals_achieved": 0, "complexity": 0.5, "bad": set()}
    result = self_healing_recovery(non_serializable_state)
    assert result == INITIAL_STATE, "Test 4 failed: Non-serializable state should recover"
    print("Test 4 passed: Non-serializable state recovers")
    
    print("All recovery integration tests passed!\n")
    return True

def migrate_to_main():
    """Generate migration report and equivalent code for evolution_orchestrator.py's main loop."""
    # Read the working logic from this module
    working_logic = {
        "reflect": reflect.__code__.co_code,
        "generate_goal": generate_goal.__code__.co_code,
        "mutate": mutate.__code__.co_code,
        "test": test.__code__.co_code,
        "accept": accept.__code__.co_code,
        "sandbox_validate": sandbox_validate.__code__.co_code,
        "self_healing_recovery": self_healing_recovery.__code__.co_code
    }
    
    # Generate equivalent code for evolution_orchestrator.py's main loop
    main_loop_code = """
def evolution_main_loop():
    \"\"\"Main evolution loop adapted from minimal_core_bootstrap.py\"\"\"
    import json
    import os
    import random
    
    STATE_FILE = "state.json"
    INITIAL_STATE = {"version": 1, "goals_achieved": 0, "complexity": 0.5}
    HARDCODED_GOALS = [
        "increase complexity by 0.1",
        "add a new key 'iterations' with value 0",
        "increment goals_achieved by 1",
        "add a key 'last_goal' with a string description",
        "set complexity to 1.0 if below 0.8"
    ]
    ESSENTIAL_MODULES = [
        "reflect",
        "generate_goal",
        "mutate",
        "test",
        "accept",
        "sandbox_validate",
        "self_healing_recovery"
    ]
    
    def reflect(state):
        summary = {}
        summary["keys"] = list(state.keys())
        summary["version"] = state.get("version", None)
        summary["goals_achieved"] = state.get("goals_achieved", 0)
        summary["complexity"] = state.get("complexity", None)
        return summary
    
    def generate_goal():
        return random.choice(HARDCODED_GOALS)
    
    def mutate(state, goal):
        new_state = state.copy()
        if goal == "increase complexity by 0.1":
            new_state["complexity"] = new_state.get("complexity", 0) + 0.1
        elif goal == "add a new key 'iterations' with value 0":
            if "iterations" not in new_state:
                new_state["iterations"] = 0
        elif goal == "increment goals_achieved by 1":
            new_state["goals_achieved"] = new_state.get("goals_achieved", 0) + 1
        elif goal == "add a key 'last_goal' with a string description":
            new_state["last_goal"] = goal
        elif goal == "set complexity to 1.0 if below 0.8":
            if new_state.get("complexity", 0) < 0.8:
                new_state["complexity"] = 1.0
        return new_state
    
    def test(state):
        try:
            json.dumps(state)
        except (TypeError, ValueError):
            return False
        expected_keys = {"version", "goals_achieved", "complexity"}
        return expected_keys.issubset(state.keys())
    
    def accept(state):
        with open(STATE_FILE, "w") as f:
            json.dump(state, f, indent=2)
    
    def sandbox_validate(state):
        try:
            test_state = json.loads(json.dumps(state))
            if not test(test_state):
                return False, "Test validation failed"
            json.dumps(test_state)
            return True, "Sandbox validation passed"
        except Exception as e:
            return False, f"Sandbox validation error: {str(e)}"
    
    def self_healing_recovery(state):
        try:
            json.dumps(state)
        except (TypeError, ValueError):
            print("State corruption detected. Recovering to initial state.")
            return INITIAL_STATE.copy()
        
        required_keys = {"version", "goals_achieved", "complexity"}
        if not required_keys.issubset(state.keys()):
            print("Missing required keys. Recovering to initial state.")
            return INITIAL_STATE.copy()
        
        if not isinstance(state.get("version"), int) or state["version"] < 1:
            print("Invalid version. Recovering to initial state.")
            return INITIAL_STATE.copy()
        
        if not isinstance(state.get("goals_achieved"), int) or state["goals_achieved"] < 0:
            print("Invalid goals_achieved. Recovering to initial state.")
            return INITIAL_STATE.copy()
        
        if not isinstance(state.get("complexity"), (int, float)) or state["complexity"] < 0:
            print("Invalid complexity. Recovering to initial state.")
            return INITIAL_STATE.copy()
        
        return state
    
    def load_or_initialize_state():
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, "r") as f:
                return json.load(f)
        else:
            accept(INITIAL_STATE)
            return INITIAL_STATE.copy()
    
    def initialize_recovery_module():
        print("Initializing self-healing recovery module...")
        for module in ESSENTIAL_MODULES:
            if module not in globals():
                print(f"Warning: Essential module '{module}' not found during recovery initialization")
        
        test_state = {"version": 1, "goals_achieved": 0, "complexity": 0.5}
        recovered = self_healing_recovery(test_state)
        if recovered == test_state:
            print("Recovery module initialized successfully.")
            return True
        else:
            print("Recovery module initialization failed.")
            return False
    
    state = load_or_initialize_state()
    print("Initial state:", state)
    print()
    
    # Initialize recovery module
    initialize_recovery_module()
    
    for cycle in range(1, 4):
        print(f"--- Cycle {cycle} ---")
        summary = reflect(state)
        print("Reflection:", summary)
        
        goal = generate_goal()
        print("Goal:", goal)
        
        mutated_state = mutate(state, goal)
        print("Mutated state:", mutated_state)
        
        # Apply recovery before validation
        recovered_state = self_healing_recovery(mutated_state)
        if recovered_state != mutated_state:
            print("Recovery applied to mutated state")
            mutated_state = recovered_state
        
        is_valid, message = sandbox_validate(mutated_state)
        if is_valid:
            print("Sandbox validation:", message)
            accept(mutated_state)
            state = mutated_state
            print("State accepted and saved.")
        else:
            print("Sandbox validation failed:", message)
            print("State unchanged.")
        
        print()
    
    print("Final state:", state)
    return state
"""
    
    # Create migration report
    migration_report = {
        "source": "minimal_core_bootstrap.py",
        "target": "evolution_orchestrator.py",
        "learnings": [
            "Sandbox validation ensures state integrity before acceptance",
            "State mutation follows deterministic rules based on goals",
            "Reflection provides structured analysis of current state",
            "Test function validates JSON serializability and required keys",
            "Random goal selection introduces variability in evolution",
            "State persistence through JSON file enables continuity",
            "Initial state provides baseline for evolution experiments",
            "Cycle-based iteration allows controlled progression",
            "Error handling in sandbox prevents corrupted state acceptance",
            "Deep copy pattern ensures original state preservation during mutation",
            "Self-healing recovery provides automatic state corruption detection and recovery",
            "Recovery module initialization ensures core capabilities are available"
        ],
        "working_logic_bytecode": working_logic,
        "equivalent_main_loop": main_loop_code,
        "recommendations": [
            "Integrate sandbox_validate before all state acceptance operations",
            "Maintain same goal structure for consistency",
            "Use deep copy pattern for state mutation safety",
            "Implement reflection for monitoring state evolution",
            "Consider extending goal set for more complex behaviors",
            "Always initialize recovery module during bootstrap",
            "Apply self-healing recovery before sandbox validation"
        ]
    }
    
    # Save migration report
    with open("migration_report.json", "w") as f:
        json.dump(migration_report, f, indent=2, default=str)
    
    print("Migration report generated: migration_report.json")
    print("\nLearnings from minimal core experiment:")
    for learning in migration_report["learnings"]:
        print(f"  - {learning}")
    
    return migration_report

def main():
    """Run 3 cycles of the evolution loop and print results."""
    state = load_or_initialize_state()
    print("Initial state:", state)
    print()
    
    # Initialize recovery module during bootstrap
    initialize_recovery_module()

    for cycle in range(1, 4):
        print(f"--- Cycle {cycle} ---")
        # Reflect
        summary = reflect(state)
        print("Reflection:", summary)

        # Generate goal
        goal = generate_goal()
        print("Goal:", goal)

        # Mutate
        mutated_state = mutate(state, goal)
        print("Mutated state:", mutated_state)

        # Apply self-healing recovery before validation
        recovered_state = self_healing_recovery(mutated_state)
        if recovered_state != mutated_state:
            print("Recovery applied to mutated state")
            mutated_state = recovered_state

        # Sandbox validation
        is_valid, message = sandbox_validate(mutated_state)
        if is_valid:
            print("Sandbox validation:", message)
            # Accept
            accept(mutated_state)
            state = mutated_state
            print("State accepted and saved.")
        else:
            print("Sandbox validation failed:", message)
            print("State unchanged.")

        print()

    print("Final state:", state)
    
    # Run recovery integration test
    test_recovery_integration()
    
    # After successful sandbox validation, run migration
    print("\n--- Migration Phase ---")
    migrate_to_main()

if __name__ == "__main__":
    main()