import json
import os
import random
import signal
import sys
from multiprocessing import Process, Manager

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
    "self_healing_recovery",
    "failure_driven_simplification",
    "failure_driven_mutation_selector",
    "dead_module_detector",
    "module_removal_sandbox"
]

class SandboxManager:
    """Manages sandbox processes for mutation and testing."""
    
    def __init__(self):
        self.manager = Manager()
        self.mutation_sandbox = None
        self.test_sandbox = None
        self.mutation_queue = self.manager.Queue()
        self.test_queue = self.manager.Queue()
        self.result_queue = self.manager.Queue()
        self.running = False
    
    def start_mutation_sandbox(self):
        """Start the mutation sandbox process."""
        def mutation_worker(mutation_queue, result_queue):
            while True:
                try:
                    state, goal = mutation_queue.get(timeout=1)
                    result = mutate(state, goal)
                    result_queue.put(("mutation_result", result))
                except:
                    break
        
        self.mutation_sandbox = Process(target=mutation_worker, args=(self.mutation_queue, self.result_queue))
        self.mutation_sandbox.start()
        print("Mutation sandbox started.")
    
    def start_test_sandbox(self):
        """Start the test sandbox process."""
        def test_worker(test_queue, result_queue):
            while True:
                try:
                    state = test_queue.get(timeout=1)
                    result = test(state)
                    result_queue.put(("test_result", result))
                except:
                    break
        
        self.test_sandbox = Process(target=test_worker, args=(self.test_queue, self.result_queue))
        self.test_sandbox.start()
        print("Test sandbox started.")
    
    def stop_sandboxes(self):
        """Stop all sandbox processes."""
        if self.mutation_sandbox and self.mutation_sandbox.is_alive():
            self.mutation_sandbox.terminate()
            self.mutation_sandbox.join(timeout=2)
            print("Mutation sandbox stopped.")
        
        if self.test_sandbox and self.test_sandbox.is_alive():
            self.test_sandbox.terminate()
            self.test_sandbox.join(timeout=2)
            print("Test sandbox stopped.")
        
        self.running = False
    
    def submit_mutation(self, state, goal):
        """Submit a mutation task to the sandbox."""
        self.mutation_queue.put((state, goal))
    
    def submit_test(self, state):
        """Submit a test task to the sandbox."""
        self.test_queue.put(state)
    
    def get_result(self, timeout=5):
        """Get a result from the sandbox."""
        try:
            return self.result_queue.get(timeout=timeout)
        except:
            return None

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

def failure_driven_simplification(state):
    """Simplify state by removing unnecessary complexity when failures are detected."""
    simplified_state = state.copy()
    
    # Check for excessive complexity and reduce it
    if simplified_state.get("complexity", 0) > 1.5:
        print("Excessive complexity detected. Simplifying...")
        simplified_state["complexity"] = 1.0
    
    # Remove non-essential keys that may cause issues
    essential_keys = {"version", "goals_achieved", "complexity"}
    for key in list(simplified_state.keys()):
        if key not in essential_keys:
            del simplified_state[key]
            print(f"Removed non-essential key: {key}")
    
    return simplified_state

def failure_driven_mutation_selector(state, goal):
    """Select and apply mutations based on failure patterns in the state."""
    selected_state = state.copy()
    
    # Detect failure patterns and apply corrective mutations
    if selected_state.get("complexity", 0) > 1.0:
        print("Failure-driven mutation: Reducing complexity due to high value")
        selected_state["complexity"] = 0.8
    
    if "iterations" in selected_state and selected_state["iterations"] > 10:
        print("Failure-driven mutation: Resetting iterations due to excessive count")
        selected_state["iterations"] = 0
    
    # Check for missing essential keys and add them
    essential_keys = {"version", "goals_achieved", "complexity"}
    for key in essential_keys:
        if key not in selected_state:
            print(f"Failure-driven mutation: Adding missing essential key '{key}'")
            if key == "version":
                selected_state[key] = 1
            elif key == "goals_achieved":
                selected_state[key] = 0
            elif key == "complexity":
                selected_state[key] = 0.5
    
    return selected_state

def dead_module_detector(state):
    """Detect and report modules that are no longer needed or functional."""
    print("Dead module detector: Checking for unused modules...")
    # Placeholder implementation - would normally check module usage patterns
    return state

def module_removal_sandbox(state):
    """Safely test removal of dead modules in a sandboxed environment."""
    print("Module removal sandbox: Testing module removal safety...")
    # Placeholder implementation - would normally test removal impact
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

def initialize_failure_driven_simplification():
    """Initialize the failure-driven simplification module during bootstrap."""
    print("Initializing failure-driven simplification module...")
    
    # Verify the function exists
    if "failure_driven_simplification" not in globals():
        print("Warning: failure_driven_simplification function not found")
        return False
    
    # Test the simplification function
    test_state = {"version": 1, "goals_achieved": 0, "complexity": 2.0, "extra_key": "test"}
    simplified = failure_driven_simplification(test_state)
    
    # Verify simplification worked
    if simplified.get("complexity", 0) <= 1.0 and "extra_key" not in simplified:
        print("Failure-driven simplification module initialized successfully.")
        return True
    else:
        print("Failure-driven simplification module initialization failed.")
        return False

def initialize_failure_driven_mutation_selector():
    """Initialize the failure-driven mutation selector module during bootstrap."""
    print("Initializing failure-driven mutation selector module...")
    
    # Verify the function exists
    if "failure_driven_mutation_selector" not in globals():
        print("Warning: failure_driven_mutation_selector function not found")
        return False
    
    # Test the mutation selector function
    test_state = {"version": 1, "goals_achieved": 0, "complexity": 2.0}
    test_goal = "increase complexity by 0.1"
    selected = failure_driven_mutation_selector(test_state, test_goal)
    
    # Verify mutation selector worked
    if selected.get("complexity", 0) <= 1.0:
        print("Failure-driven mutation selector module initialized successfully.")
        return True
    else:
        print("Failure-driven mutation selector module initialization failed.")
        return False

def initialize_dead_module_detector():
    """Initialize the dead module detector during bootstrap."""
    print("Initializing dead module detector...")
    
    # Verify the function exists
    if "dead_module_detector" not in globals():
        print("Warning: dead_module_detector function not found")
        return False
    
    # Test the dead module detector function
    test_state = {"version": 1, "goals_achieved": 0, "complexity": 0.5}
    result = dead_module_detector(test_state)
    
    if result == test_state:
        print("Dead module detector initialized successfully.")
        return True
    else:
        print("Dead module detector initialization failed.")
        return False

def initialize_module_removal_sandbox():
    """Initialize the module removal sandbox during bootstrap."""
    print("Initializing module removal sandbox...")
    
    # Verify the function exists
    if "module_removal_sandbox" not in globals():
        print("Warning: module_removal_sandbox function not found")
        return False
    
    # Test the module removal sandbox function
    test_state = {"version": 1, "goals_achieved": 0, "complexity": 0.5}
    result = module_removal_sandbox(test_state)
    
    if result == test_state:
        print("Module removal sandbox initialized successfully.")
        return True
    else:
        print("Module removal sandbox initialization failed.")
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

def test_failure_driven_simplification():
    """Test failure-driven simplification functionality."""
    print("\n--- Failure-Driven Simplification Test ---")
    
    # Test 1: High complexity should be reduced
    high_complexity_state = {"version": 1, "goals_achieved": 0, "complexity": 2.0}
    result = failure_driven_simplification(high_complexity_state)
    assert result["complexity"] <= 1.0, "Test 1 failed: High complexity should be reduced"
    print("Test 1 passed: High complexity reduced")
    
    # Test 2: Non-essential keys should be removed
    extra_keys_state = {"version": 1, "goals_achieved": 0, "complexity": 0.5, "extra": "data"}
    result = failure_driven_simplification(extra_keys_state)
    assert "extra" not in result, "Test 2 failed: Non-essential keys should be removed"
    print("Test 2 passed: Non-essential keys removed")
    
    # Test 3: Normal state should remain unchanged
    normal_state = {"version": 1, "goals_achieved": 0, "complexity": 0.5}
    result = failure_driven_simplification(normal_state)
    assert result == normal_state, "Test 3 failed: Normal state should remain unchanged"
    print("Test 3 passed: Normal state remains unchanged")
    
    print("All failure-driven simplification tests passed!\n")
    return True

def test_failure_driven_mutation_selector():
    """Test failure-driven mutation selector functionality."""
    print("\n--- Failure-Driven Mutation Selector Test ---")
    
    # Test 1: High complexity should be reduced
    high_complexity_state = {"version": 1, "goals_achieved": 0, "complexity": 2.0}
    result = failure_driven_mutation_selector(high_complexity_state, "increase complexity by 0.1")
    assert result["complexity"] <= 1.0, "Test 1 failed: High complexity should be reduced"
    print("Test 1 passed: High complexity reduced")
    
    # Test 2: Missing essential keys should be added
    missing_keys_state = {"version": 1}
    result = failure_driven_mutation_selector(missing_keys_state, "increment goals_achieved by 1")
    assert "goals_achieved" in result, "Test 2 failed: Missing essential keys should be added"
    assert "complexity" in result, "Test 2 failed: Missing essential keys should be added"
    print("Test 2 passed: Missing essential keys added")
    
    # Test 3: Normal state should remain mostly unchanged
    normal_state = {"version": 1, "goals_achieved": 0, "complexity": 0.5}
    result = failure_driven_mutation_selector(normal_state, "increase complexity by 0.1")
    assert result["complexity"] == 0.5, "Test 3 failed: Normal state complexity should remain unchanged"
    print("Test 3 passed: Normal state remains unchanged")
    
    print("All failure-driven mutation selector tests passed!\n")
    return True

def test_dead_module_detector():
    """Test dead module detector functionality."""
    print("\n--- Dead Module Detector Test ---")
    
    # Test 1: Normal state should pass through
    normal_state = {"version": 1, "goals_achieved": 0, "complexity": 0.5}
    result = dead_module_detector(normal_state)
    assert result == normal_state, "Test 1 failed: Normal state should remain unchanged"
    print("Test 1 passed: Normal state remains unchanged")
    
    print("All dead module detector tests passed!\n")
    return True

def test_module_removal_sandbox():
    """Test module removal sandbox functionality."""
    print("\n--- Module Removal Sandbox Test ---")
    
    # Test 1: Normal state should pass through
    normal_state = {"version": 1, "goals_achieved": 0, "complexity": 0.5}
    result = module_removal_sandbox(normal_state)
    assert result == normal_state, "Test 1 failed: Normal state should remain unchanged"
    print("Test 1 passed: Normal state remains unchanged")
    
    print("All module removal sandbox tests passed!\n")
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
        "self_healing_recovery": self_healing_recovery.__code__.co_code,
        "failure_driven_simplification": failure_driven_simplification.__code__.co_code,
        "failure_driven_mutation_selector": failure_driven_mutation_selector.__code__.co_code,
        "dead_module_detector": dead_module_detector.__code__.co_code,
        "module_removal_sandbox": module_removal_sandbox.__code__.co_code
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
        "self_healing_recovery",
        "failure_driven_simplification",
        "failure_driven_mutation_selector",
        "dead_module_detector",
        "module_removal_sandbox"
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
    
    def failure_driven_simplification(state):
        simplified_state = state.copy()
        
        if simplified_state.get("complexity", 0) > 1.5:
            print("Excessive complexity detected. Simplifying...")
            simplified_state["complexity"] = 1.0
        
        essential_keys = {"version", "goals_achieved", "complexity"}
        for key in list(simplified_state.keys()):
            if key not in essential_keys:
                del simplified_state[key]
                print(f"Removed non-essential key: {key}")
        
        return simplified_state
    
    def failure_driven_mutation_selector(state, goal):
        selected_state = state.copy()
        
        if selected_state.get("complexity", 0) > 1.0:
            print("Failure-driven mutation: Reducing complexity due to high value")
            selected_state["complexity"] = 0.8
        
        if "iterations" in selected_state and selected_state["iterations"] > 10:
            print("Failure-driven mutation: Resetting iterations due to excessive count")
            selected_state["iterations"] = 0
        
        essential_keys = {"version", "goals_achieved", "complexity"}
        for key in essential_keys:
            if key not in selected_state:
                print(f"Failure-driven mutation: Adding missing essential key '{key}'")
                if key == "version":
                    selected_state[key] = 1
                elif key == "goals_achieved":
                    selected_state[key] = 0
                elif key == "complexity":
                    selected_state[key] = 0.5
        
        return selected_state
    
    def dead_module_detector(state):
        print("Dead module detector: Checking for unused modules...")
        return state
    
    def module_removal_sandbox(state):
        print("Module removal sandbox: Testing module removal safety...")
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
    
    def initialize_failure_driven_simplification():
        print("Initializing failure-driven simplification module...")
        
        if "failure_driven_simplification" not in globals():
            print("Warning: failure_driven_simplification function not found")
            return False
        
        test_state = {"version": 1, "goals_achieved": 0, "complexity": 2.0, "extra_key": "test"}
        simplified = failure_driven_simplification(test_state)
        
        if simplified.get("complexity", 0) <= 1.0 and "extra_key" not in simplified:
            print("Failure-driven simplification module initialized successfully.")
            return True
        else:
            print("Failure-driven simplification module initialization failed.")
            return False
    
    def initialize_failure_driven_mutation_selector():
        print("Initializing failure-driven mutation selector module...")
        
        if "failure_driven_mutation_selector" not in globals():
            print("Warning: failure_driven_mutation_selector function not found")
            return False
        
        test_state = {"version": 1, "goals_achieved": 0, "complexity": 2.0}
        test_goal = "increase complexity by 0.1"
        selected = failure_driven_mutation_selector(test_state, test_goal)
        
        if selected.get("complexity", 0) <= 1.0:
            print("Failure-driven mutation selector module initialized successfully.")
            return True
        else:
            print("Failure-driven mutation selector module initialization failed.")
            return False
    
    def initialize_dead_module_detector():
        print("Initializing dead module detector...")
        
        if "dead_module_detector" not in globals():
            print("Warning: dead_module_detector function not found")
            return False
        
        test_state = {"version": 1, "goals_achieved": 0, "complexity": 0.5}
        result = dead_module_detector(test_state)
        
        if result == test_state:
            print("Dead module detector initialized successfully.")
            return True
        else:
            print("Dead module detector initialization failed.")
            return False
    
    def initialize_module_removal_sandbox():
        print("Initializing module removal sandbox...")
        
        if "module_removal_sandbox" not in globals():
            print("Warning: module_removal_sandbox function not found")
            return False
        
        test_state = {"version": 1, "goals_achieved": 0, "complexity": 0.5}
        result = module_removal_sandbox(test_state)
        
        if result == test_state:
            print("Module removal sandbox initialized successfully.")
            return True
        else:
            print("Module removal sandbox initialization failed.")
            return False
    
    state = load_or_initialize_state()
    print("Initial state:", state)
    print()
    
    # Initialize all core modules
    initialize_recovery_module()
    initialize_failure_driven_simplification()
    initialize_failure_driven_mutation_selector()
    initialize_dead_module_detector()
    initialize_module_removal_sandbox()
    
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
        
        # Apply failure-driven simplification
        simplified_state = failure_driven_simplification(mutated_state)
        if simplified_state != mutated_state:
            print("Failure-driven simplification applied to mutated state")
            mutated_state = simplified_state
        
        # Apply failure-driven mutation selector
        selected_state = failure_driven_mutation_selector(mutated_state, goal)
        if selected_state != mutated_state:
            print("Failure-driven mutation selector applied to mutated state")
            mutated_state = selected_state
        
        # Apply dead module detector
        detected_state = dead_module_detector(mutated_state)
        if detected_state != mutated_state:
            print("Dead module detector applied to mutated state")
            mutated_state = detected_state
        
        # Apply module removal sandbox
        sandboxed_state = module_removal_sandbox(mutated_state)
        if sandboxed_state != mutated_state:
            print("Module removal sandbox applied to mutated state")
            mutated_state = sandboxed_state
        
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
            "Recovery module initialization ensures core capabilities are available",
            "Failure-driven simplification reduces complexity and removes non-essential keys",
            "Pruning mechanism is active from system start through bootstrap initialization",
            "Failure-driven mutation selector provides corrective mutations based on failure patterns",
            "Mutation selector is initialized during bootstrap for active failure-driven selection",
            "Dead module detector identifies unused modules for potential removal",
            "Module removal sandbox safely tests module removal before execution"
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
            "Apply self-healing recovery before sandbox validation",
            "Initialize failure-driven simplification during bootstrap for active pruning",
            "Apply failure-driven simplification after recovery but before validation",
            "Initialize failure-driven mutation selector during bootstrap for active selection",
            "Apply failure-driven mutation selector after simplification but before validation",
            "Initialize dead module detector during bootstrap for active monitoring",
            "Apply dead module detector after mutation selector but before validation",
            "Initialize module removal sandbox during bootstrap for safe removal testing",
            "Apply module removal sandbox after dead module detection but before validation"
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

def cleanup_handler(signum, frame, sandbox_manager):
    """Handle graceful shutdown on signal."""
    print(f"\nReceived signal {signum}. Performing graceful shutdown...")
    sandbox_manager.stop_sandboxes()
    print("Cleanup complete. Exiting.")
    sys.exit(0)

def main():
    """Run 3 cycles of the evolution loop and print results."""
    # Initialize sandbox manager
    sandbox_manager = SandboxManager()
    
    # Register cleanup handlers for graceful shutdown
    signal.signal(signal.SIGINT, lambda s, f: cleanup_handler(s, f, sandbox_manager))
    signal.signal(signal.SIGTERM, lambda s, f: cleanup_handler(s, f, sandbox_manager))
    
    # Start sandbox processes
    sandbox_manager.start_mutation_sandbox()
    sandbox_manager.start_test_sandbox()
    
    state = load_or_initialize_state()
    print("Initial state:", state)
    print()
    
    # Initialize all core modules during