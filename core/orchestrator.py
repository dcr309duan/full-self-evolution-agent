from pathlib import Path
import tempfile
import shutil
import sys
import os
import json
from typing import Dict, Any, List

# Assuming these modules exist in the 'core' package
from core.goal_selector import select_goal
from core.mutation_engine import mutate_file
from core.test_runner import run_tests
from core.reflection import analyze_result
from core.simulation_engine import simulate_change, SimulationResult

SMOKE_TEST_GOAL = "Add error handling to counter function"

MINIMAL_COUNTER_PY = """class Counter:
    def __init__(self):
        self.count = 0

    def increment(self):
        self.count += 1

    def decrement(self):
        self.count -= 1

    def get_count(self):
        return self.count
"""

MINIMAL_TEST_PY = """import unittest
from counter import Counter

class TestCounter(unittest.TestCase):
    def test_increment(self):
        c = Counter()
        c.increment()
        self.assertEqual(c.get_count(), 1)

    def test_decrement(self):
        c = Counter()
        c.decrement()
        self.assertEqual(c.get_count(), -1)

    def test_multiple_operations(self):
        c = Counter()
        c.increment()
        c.increment()
        c.decrement()
        self.assertEqual(c.get_count(), 1)

if __name__ == '__main__':
    unittest.main()
"""

# Track simulation accuracy over time
simulation_history: List[Dict[str, Any]] = []

def update_simulation_accuracy(sim_result: SimulationResult, actual_test_result: Dict[str, Any]) -> None:
    """Update simulation accuracy tracking based on actual test results."""
    predicted_success = sim_result.predicted_success
    actual_success = actual_test_result.get("success", False)
    
    accuracy_entry = {
        "predicted_success": predicted_success,
        "actual_success": actual_success,
        "confidence": sim_result.confidence,
        "correct": predicted_success == actual_success
    }
    simulation_history.append(accuracy_entry)

def get_simulation_accuracy() -> Dict[str, Any]:
    """Calculate current simulation accuracy metrics."""
    if not simulation_history:
        return {
            "overall_accuracy": 0.0,
            "total_predictions": 0,
            "correct_predictions": 0,
            "average_confidence": 0.0
        }
    
    total = len(simulation_history)
    correct = sum(1 for entry in simulation_history if entry["correct"])
    avg_confidence = sum(entry["confidence"] for entry in simulation_history) / total
    
    return {
        "overall_accuracy": correct / total if total > 0 else 0.0,
        "total_predictions": total,
        "correct_predictions": correct,
        "average_confidence": avg_confidence
    }

def run_smoke_test() -> Dict[str, Any]:
    """
    Execute the evolution smoke test in an isolated temporary directory.
    Integrates simulation engine to predict outcomes before mutation.

    Returns:
        A structured dictionary containing:
        - 'success': bool indicating overall success
        - 'logs': list of step-level log entries
        - 'result': the final analysis result from the reflection module
        - 'simulation_confidence': confidence score from simulation
    """
    logs: List[Dict[str, Any]] = []
    temp_dir = None
    simulation_confidence = 0.0

    try:
        # Step 1: Create isolated environment
        temp_dir = tempfile.mkdtemp(prefix="smoke_test_")
        logs.append({
            "step": 1,
            "action": "create_isolated_environment",
            "status": "success",
            "details": f"Created temporary directory: {temp_dir}"
        })

        # Write minimal counter.py and test file
        counter_path = Path(temp_dir) / "counter.py"
        test_path = Path(temp_dir) / "test_counter.py"
        counter_path.write_text(MINIMAL_COUNTER_PY)
        test_path.write_text(MINIMAL_TEST_PY)
        logs.append({
            "step": 1.1,
            "action": "write_source_files",
            "status": "success",
            "details": f"Written counter.py and test_counter.py to {temp_dir}"
        })

        # Step 2: Invoke goal selector
        goal = SMOKE_TEST_GOAL
        selected_goal = select_goal(goal)
        logs.append({
            "step": 2,
            "action": "invoke_goal_selector",
            "status": "success",
            "details": f"Selected goal: {selected_goal}"
        })

        # Step 3: Run simulation before mutation
        original_code = counter_path.read_text()
        sim_result = simulate_change(original_code, selected_goal)
        simulation_confidence = sim_result.confidence
        logs.append({
            "step": 2.5,
            "action": "run_simulation",
            "status": "success",
            "details": f"Simulation predicted success: {sim_result.predicted_success}, confidence: {sim_result.confidence}"
        })

        # Check simulation prediction
        if not sim_result.predicted_success:
            logs.append({
                "step": 2.6,
                "action": "simulation_warning",
                "status": "warning",
                "details": f"Simulation predicts failure with confidence {sim_result.confidence}. Skipping mutation."
            })
            # Return early with simulation failure result
            result = {
                "success": False,
                "logs": logs,
                "result": {
                    "simulation_confidence": simulation_confidence,
                    "simulation_prediction": "failure",
                    "simulation_accuracy": get_simulation_accuracy()
                },
                "simulation_confidence": simulation_confidence
            }
            return result

        # Step 4: Invoke mutation engine
        mutated_code = mutate_file(str(counter_path), selected_goal)
        logs.append({
            "step": 3,
            "action": "invoke_mutation_engine",
            "status": "success",
            "details": f"Mutation applied to {counter_path}"
        })

        # Write mutated code back to file
        counter_path.write_text(mutated_code)
        logs.append({
            "step": 3.1,
            "action": "write_mutated_code",
            "status": "success",
            "details": "Mutated code written back to counter.py"
        })

        # Step 5: Run test suite
        original_cwd = os.getcwd()
        os.chdir(temp_dir)
        try:
            test_result = run_tests(str(test_path))
            logs.append({
                "step": 4,
                "action": "run_test_suite",
                "status": "success",
                "details": f"Test result: {test_result}"
            })
            
            # Update simulation accuracy tracking
            update_simulation_accuracy(sim_result, test_result)
            
        finally:
            os.chdir(original_cwd)

        # Step 6: Invoke reflection module with simulation data
        analysis = analyze_result(test_result, mutated_code, selected_goal)
        
        # Add simulation confidence to reflection output
        analysis["simulation_confidence"] = simulation_confidence
        analysis["simulation_accuracy"] = get_simulation_accuracy()
        
        logs.append({
            "step": 5,
            "action": "invoke_reflection",
            "status": "success",
            "details": f"Analysis result: {analysis}"
        })

        # Step 7: Return structured result with simulation data
        result = {
            "success": True,
            "logs": logs,
            "result": analysis,
            "simulation_confidence": simulation_confidence
        }
        return result

    except Exception as e:
        logs.append({
            "step": -1,
            "action": "error",
            "status": "failed",
            "details": str(e)
        })
        return {
            "success": False,
            "logs": logs,
            "result": {
                "simulation_confidence": simulation_confidence,
                "simulation_accuracy": get_simulation_accuracy()
            },
            "simulation_confidence": simulation_confidence
        }

    finally:
        # Cleanup temporary directory
        if temp_dir and Path(temp_dir).exists():
            shutil.rmtree(temp_dir)
            logs.append({
                "step": "cleanup",
                "action": "remove_temp_directory",
                "status": "success",
                "details": f"Removed temporary directory: {temp_dir}"
            })