import json
import importlib
import sys
import os
from datetime import datetime

class FitnessEvaluator:
    def __init__(self, test_file_path, history_file='fitness_history.json'):
        self.test_file_path = test_file_path
        self.history_file = history_file
        self.test_cases = []
        self.load_test_cases()

    def load_test_cases(self):
        """Load test cases from the test file."""
        try:
            with open(self.test_file_path, 'r') as f:
                self.test_cases = json.load(f)
        except FileNotFoundError:
            print(f"Error: Test file '{self.test_file_path}' not found.")
            sys.exit(1)
        except json.JSONDecodeError:
            print(f"Error: Test file '{self.test_file_path}' is not valid JSON.")
            sys.exit(1)

    def import_agent_module(self, module_name):
        """Dynamically import the agent's solution module."""
        try:
            # Add the current directory to sys.path if not already there
            if '' not in sys.path:
                sys.path.insert(0, '')
            module = importlib.import_module(module_name)
            return module
        except ImportError as e:
            print(f"Error: Could not import module '{module_name}': {e}")
            return None

    def run_test_case(self, solution_func, test_input, expected_output):
        """Run a single test case and return whether it passed."""
        try:
            result = solution_func(test_input)
            return result == expected_output
        except Exception as e:
            print(f"Error during test execution: {e}")
            return False

    def evaluate(self, module_name, cycle_number):
        """Evaluate the agent's solution against all test cases and compute score."""
        module = self.import_agent_module(module_name)
        if module is None:
            return 0.0

        if not hasattr(module, 'solve'):
            print(f"Error: Module '{module_name}' does not have a 'solve' function.")
            return 0.0

        solution_func = module.solve
        passed_tests = 0
        total_tests = len(self.test_cases)

        for test_case in self.test_cases:
            test_input = test_case.get('input')
            expected_output = test_case.get('expected_output')
            if test_input is None or expected_output is None:
                print(f"Warning: Test case missing 'input' or 'expected_output' field.")
                continue
            if self.run_test_case(solution_func, test_input, expected_output):
                passed_tests += 1

        score = (passed_tests / total_tests) * 100 if total_tests > 0 else 0.0
        self.log_score(score, cycle_number)
        return score

    def log_score(self, score, cycle_number):
        """Log the score to the fitness history file with timestamp and cycle number."""
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'cycle': cycle_number,
            'score': score
        }

        # Load existing history if file exists
        history = []
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, 'r') as f:
                    history = json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                history = []

        # Append new entry
        history.append(log_entry)

        # Write back to file
        with open(self.history_file, 'w') as f:
            json.dump(history, f, indent=2)

    def get_history(self):
        """Retrieve the full fitness history from the history file."""
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                return []
        return []


# Example usage (commented out):
# if __name__ == "__main__":
#     evaluator = FitnessEvaluator('test_cases.json')
#     score = evaluator.evaluate('agent_solution', cycle_number=1)
#     print(f"Score: {score:.2f}")