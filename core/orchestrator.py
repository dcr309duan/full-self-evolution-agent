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

def run_smoke_test() -> Dict[str, Any]:
    """
    Execute the evolution smoke test in an isolated temporary directory.

    Returns:
        A structured dictionary containing:
        - 'success': bool indicating overall success
        - 'logs': list of step-level log entries
        - 'result': the final analysis result from the reflection module
    """
    logs: List[Dict[str, Any]] = []
    temp_dir = None

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

        # Step 3: Invoke mutation engine
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

        # Step 4: Run test suite
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
        finally:
            os.chdir(original_cwd)

        # Step 5: Invoke reflection module
        analysis = analyze_result(test_result, mutated_code, selected_goal)
        logs.append({
            "step": 5,
            "action": "invoke_reflection",
            "status": "success",
            "details": f"Analysis result: {analysis}"
        })

        # Step 6: Return structured result
        result = {
            "success": True,
            "logs": logs,
            "result": analysis
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
            "result": None
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