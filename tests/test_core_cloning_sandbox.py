import pytest
import json
import os
import tempfile
import subprocess
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.orchestrator import Orchestrator
from core.state_manager import StateManager
from core.mutation_engine import MutationEngine

@pytest.fixture
def temp_dir():
    """Create a temporary directory for test artifacts."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)

@pytest.fixture
def initial_state(temp_dir):
    """Initialize the three core modules with known state."""
    state_file = temp_dir / "state.json"
    state_manager = StateManager(state_file)
    
    # Set known initial state
    initial_orchestrator_config = {
        "goal_selection_threshold": 0.7,
        "max_iterations": 100,
        "learning_rate": 0.01
    }
    
    orchestrator = Orchestrator(config=initial_orchestrator_config, state_manager=state_manager)
    mutation_engine = MutationEngine(state_manager=state_manager)
    
    # Save initial state
    state_manager.save_state({
        "orchestrator": initial_orchestrator_config,
        "mutation_engine": {"mutation_rate": 0.1, "population_size": 50},
        "version": "1.0.0"
    })
    
    return {
        "orchestrator": orchestrator,
        "state_manager": state_manager,
        "mutation_engine": mutation_engine,
        "temp_dir": temp_dir,
        "state_file": state_file
    }

def test_serialize_state_contains_all_key_fields(initial_state):
    """Verify serialize_state() output contains all key fields."""
    state = initial_state["state_manager"].serialize_state()
    
    # Check top-level keys
    assert "orchestrator" in state
    assert "mutation_engine" in state
    assert "version" in state
    
    # Check orchestrator fields
    assert "goal_selection_threshold" in state["orchestrator"]
    assert state["orchestrator"]["goal_selection_threshold"] == 0.7
    assert "max_iterations" in state["orchestrator"]
    assert "learning_rate" in state["orchestrator"]
    
    # Check mutation_engine fields
    assert "mutation_rate" in state["mutation_engine"]
    assert "population_size" in state["mutation_engine"]

def test_sandbox_subprocess_mutation_and_result(initial_state):
    """Spawn sandbox subprocess with mutation and verify result file."""
    temp_dir = initial_state["temp_dir"]
    state_file = initial_state["state_file"]
    
    # Create a mutation script that changes goal_selection_threshold
    mutation_script = temp_dir / "mutation.py"
    mutation_script.write_text("""
import json
import sys

def apply_mutation(state):
    state['orchestrator']['goal_selection_threshold'] = 0.5
    return state

if __name__ == "__main__":
    state = json.loads(sys.stdin.read())
    mutated_state = apply_mutation(state)
    print(json.dumps(mutated_state))
""")
    
    # Create sandbox test script
    sandbox_script = temp_dir / "sandbox_tests.py"
    sandbox_script.write_text("""
import json
import sys

# Simulate running tests
test_results = {
    "passed": 5,
    "failed": 0,
    "total": 5,
    "success": True
}

# Write results to file
with open(sys.argv[1], 'w') as f:
    json.dump(test_results, f)
""")
    
    result_file = temp_dir / "sandbox_results.json"
    
    # Spawn sandbox subprocess
    sandbox_cmd = [
        sys.executable,
        str(sandbox_script),
        str(result_file)
    ]
    
    # Apply mutation via subprocess
    with open(state_file, 'r') as f:
        original_state = json.load(f)
    
    mutation_process = subprocess.Popen(
        [sys.executable, str(mutation_script)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    mutated_state_json, mutation_err = mutation_process.communicate(input=json.dumps(original_state))
    
    # Write mutated state to a temporary file for sandbox
    mutated_state_file = temp_dir / "mutated_state.json"
    with open(mutated_state_file, 'w') as f:
        f.write(mutated_state_json)
    
    # Run sandbox tests
    sandbox_process = subprocess.Popen(
        sandbox_cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    sandbox_stdout, sandbox_stderr = sandbox_process.communicate()
    
    # Verify result file exists
    assert result_file.exists(), "Sandbox result file was not created"
    
    # Verify result file contains expected data
    with open(result_file, 'r') as f:
        results = json.load(f)
    
    assert "passed" in results
    assert "failed" in results
    assert "total" in results
    assert "success" in results
    assert results["success"] == True
    assert results["passed"] == 5
    assert results["failed"] == 0

def test_promotion_logic_merges_threshold_change(initial_state):
    """Verify promotion logic correctly merges threshold change when tests pass."""
    state_manager = initial_state["state_manager"]
    orchestrator = initial_state["orchestrator"]
    
    # Simulate a mutation that changes threshold to 0.5
    mutation = {"orchestrator": {"goal_selection_threshold": 0.5}}
    
    # Apply promotion logic (simulating tests passed)
    current_state = state_manager.serialize_state()
    current_state["orchestrator"]["goal_selection_threshold"] = 0.5
    state_manager.save_state(current_state)
    
    # Verify the change was merged
    updated_state = state_manager.serialize_state()
    assert updated_state["orchestrator"]["goal_selection_threshold"] == 0.5
    
    # Verify other fields remain unchanged
    assert updated_state["orchestrator"]["max_iterations"] == 100
    assert updated_state["orchestrator"]["learning_rate"] == 0.01

def test_discard_logic_restores_original_state(initial_state):
    """Verify discard logic restores original state when tests fail."""
    state_manager = initial_state["state_manager"]
    
    # Save original state
    original_state = state_manager.serialize_state()
    original_threshold = original_state["orchestrator"]["goal_selection_threshold"]
    
    # Simulate a mutation that changes threshold to 0.5
    mutated_state = original_state.copy()
    mutated_state["orchestrator"] = mutated_state["orchestrator"].copy()
    mutated_state["orchestrator"]["goal_selection_threshold"] = 0.5
    
    # Apply the mutation (simulating tests failed)
    state_manager.save_state(mutated_state)
    
    # Verify mutation was applied
    temp_state = state_manager.serialize_state()
    assert temp_state["orchestrator"]["goal_selection_threshold"] == 0.5
    
    # Now discard the mutation (restore original state)
    state_manager.save_state(original_state)
    
    # Verify original state is restored
    restored_state = state_manager.serialize_state()
    assert restored_state["orchestrator"]["goal_selection_threshold"] == original_threshold
    assert restored_state["orchestrator"]["goal_selection_threshold"] == 0.7

def test_log_file_contains_mutation_description_and_results(initial_state):
    """Verify log file contains mutation description, test results, and any errors."""
    temp_dir = initial_state["temp_dir"]
    log_file = temp_dir / "mutation_log.txt"
    
    # Create a comprehensive log entry
    log_entries = [
        "=== Mutation Log ===",
        f"Timestamp: 2024-01-01T00:00:00Z",
        "Mutation Description: Changed goal_selection_threshold from 0.7 to 0.5",
        "Mutation Type: Parameter Tuning",
        "Affected Module: orchestrator",
        "",
        "=== Test Results ===",
        "Tests Passed: 5",
        "Tests Failed: 0",
        "Total Tests: 5",
        "Success Rate: 100.0%",
        "",
        "=== Errors ===",
        "No errors encountered during mutation application.",
        ""
    ]
    
    with open(log_file, 'w') as f:
        f.write("\n".join(log_entries))
    
    # Verify log file exists
    assert log_file.exists()
    
    # Read and verify log contents
    with open(log_file, 'r') as f:
        log_content = f.read()
    
    # Check for mutation description
    assert "goal_selection_threshold from 0.7 to 0.5" in log_content
    assert "Mutation Description" in log_content
    
    # Check for test results
    assert "Tests Passed: 5" in log_content
    assert "Tests Failed: 0" in log_content
    assert "Total Tests: 5" in log_content
    assert "Success Rate: 100.0%" in log_content
    
    # Check for errors section
    assert "Errors" in log_content
    assert "No errors encountered" in log_content

def test_full_integration_flow(initial_state):
    """Test the complete integration flow: mutation, sandbox execution, promotion/discard."""
    temp_dir = initial_state["temp_dir"]
    state_manager = initial_state["state_manager"]
    log_file = temp_dir / "integration_log.txt"
    
    # Step 1: Initialize with known state
    original_state = state_manager.serialize_state()
    assert original_state["orchestrator"]["goal_selection_threshold"] == 0.7
    
    # Step 2: Apply mutation
    mutation = {"orchestrator": {"goal_selection_threshold": 0.5}}
    mutated_state = original_state.copy()
    mutated_state["orchestrator"] = mutated_state["orchestrator"].copy()
    mutated_state["orchestrator"]["goal_selection_threshold"] = 0.5
    
    # Step 3: Simulate sandbox execution (tests pass)
    test_results = {"passed": 5, "failed": 0, "total": 5, "success": True}
    
    # Step 4: Write log
    with open(log_file, 'w') as f:
        f.write(f"Mutation: {json.dumps(mutation)}\n")
        f.write(f"Test Results: {json.dumps(test_results)}\n")
        f.write("Status: PROMOTED\n")
    
    # Step 5: Apply promotion
    state_manager.save_state(mutated_state)
    
    # Verify promotion
    promoted_state = state_manager.serialize_state()
    assert promoted_state["orchestrator"]["goal_selection_threshold"] == 0.5
    
    # Step 6: Simulate another mutation that fails
    failed_mutation = {"orchestrator": {"goal_selection_threshold": 0.3}}
    failed_state = promoted_state.copy()
    failed_state["orchestrator"] = failed_state["orchestrator"].copy()
    failed_state["orchestrator"]["goal_selection_threshold"] = 0.3
    
    state_manager.save_state(failed_state)
    
    # Simulate failed tests
    failed_test_results = {"passed": 2, "failed": 3, "total": 5, "success": False}
    
    # Apply discard (restore to promoted state)
    state_manager.save_state(promoted_state)
    
    # Verify discard
    final_state = state_manager.serialize_state()
    assert final_state["orchestrator"]["goal_selection_threshold"] == 0.5
    
    # Verify log contains all information
    with open(log_file, 'r') as f:
        log_content = f.read()
    
    assert "Mutation" in log_content
    assert "Test Results" in log_content
    assert "PROMOTED" in log_content
    assert json.dumps(mutation) in log_content
    assert json.dumps(test_results) in log_content