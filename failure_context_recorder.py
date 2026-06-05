from datetime import datetime
import json
import traceback
import ast
import sys

class FailureContextRecorder:
    """
    Records detailed context for each failed mutation during testing cycles.
    Stores structured failure data in a JSONL file with timestamps and cycle numbers.
    """

    def __init__(self, output_file="failure_log.jsonl"):
        self.output_file = output_file
        self.cycle_number = 0

    def set_cycle_number(self, cycle_number: int):
        """Set the current mutation testing cycle number."""
        self.cycle_number = cycle_number

    def record_failure(
        self,
        mutation_ast: ast.AST,
        error_type: str,
        modules_involved: list,
        test_that_failed: str,
        error: Exception,
        additional_context: dict = None
    ):
        """
        Record a failure with full context.

        Args:
            mutation_ast: The AST of the mutation that caused the failure.
            error_type: Type of error (e.g., 'import_error', 'schema_mismatch', 'side_effect', 'syntax_error').
            modules_involved: List of module names involved in the failure.
            test_that_failed: Name or identifier of the test that failed.
            error: The exception object.
            additional_context: Optional dict with extra context.
        """
        timestamp = datetime.utcnow().isoformat() + "Z"
        tb_str = ''.join(traceback.format_exception(type(error), error, error.__traceback__))

        failure_entry = {
            "timestamp": timestamp,
            "cycle_number": self.cycle_number,
            "error_type": error_type,
            "error_message": str(error),
            "traceback": tb_str,
            "test_that_failed": test_that_failed,
            "modules_involved": modules_involved,
            "mutation_ast": ast.dump(mutation_ast, indent=2),
        }

        if additional_context:
            failure_entry["additional_context"] = additional_context

        self._write_entry(failure_entry)

    def record_sandbox_failure(
        self,
        mutation_ast: ast.AST,
        error_type: str,
        modules_involved: list,
        test_that_failed: str,
        error: Exception,
        test_output: str = None,
        diff: str = None,
        sandbox_path: str = None,
        additional_context: dict = None
    ):
        """
        Record a sandbox failure with additional context including test output, diff, and sandbox path.

        Args:
            mutation_ast: The AST of the mutation that caused the failure.
            error_type: Type of error (e.g., 'import_error', 'schema_mismatch', 'side_effect', 'syntax_error').
            modules_involved: List of module names involved in the failure.
            test_that_failed: Name or identifier of the test that failed.
            error: The exception object.
            test_output: The output from the sandbox test execution.
            diff: The diff between expected and actual results.
            sandbox_path: The path to the sandbox environment.
            additional_context: Optional dict with extra context.
        """
        timestamp = datetime.utcnow().isoformat() + "Z"
        tb_str = ''.join(traceback.format_exception(type(error), error, error.__traceback__))

        failure_entry = {
            "timestamp": timestamp,
            "cycle_number": self.cycle_number,
            "error_type": error_type,
            "error_message": str(error),
            "traceback": tb_str,
            "test_that_failed": test_that_failed,
            "modules_involved": modules_involved,
            "mutation_ast": ast.dump(mutation_ast, indent=2),
            "sandbox_failure": True,
            "test_output": test_output,
            "diff": diff,
            "sandbox_path": sandbox_path
        }

        if additional_context:
            failure_entry["additional_context"] = additional_context

        self._write_entry(failure_entry)

    def record_failure_from_exception(
        self,
        mutation_ast: ast.AST,
        modules_involved: list,
        test_that_failed: str,
        additional_context: dict = None
    ):
        """
        Convenience method to record a failure using the current exception context.
        Should be called inside an except block.
        """
        exc_type, exc_value, exc_tb = sys.exc_info()
        if exc_value is None:
            raise ValueError("No exception is currently being handled")

        # Determine error type based on exception
        error_type = self._classify_error(exc_type, exc_value)

        self.record_failure(
            mutation_ast=mutation_ast,
            error_type=error_type,
            modules_involved=modules_involved,
            test_that_failed=test_that_failed,
            error=exc_value,
            additional_context=additional_context
        )

    def _classify_error(self, exc_type, exc_value) -> str:
        """Classify an exception into a standard error type."""
        if exc_type is SyntaxError:
            return "syntax_error"
        elif exc_type is ImportError or exc_type is ModuleNotFoundError:
            return "import_error"
        elif "schema" in str(exc_type).lower() or "schema" in str(exc_value).lower():
            return "schema_mismatch"
        elif "side effect" in str(exc_value).lower():
            return "side_effect"
        else:
            return "runtime_error"

    def _write_entry(self, entry: dict):
        """Write a single JSON entry to the log file."""
        with open(self.output_file, "a") as f:
            f.write(json.dumps(entry) + "\n")

    def read_all_failures(self) -> list:
        """Read all recorded failures from the log file."""
        failures = []
        try:
            with open(self.output_file, "r") as f:
                for line in f:
                    if line.strip():
                        failures.append(json.loads(line))
        except FileNotFoundError:
            pass
        return failures

    def get_failures_by_cycle(self, cycle_number: int) -> list:
        """Get all failures for a specific cycle number."""
        return [f for f in self.read_all_failures() if f.get("cycle_number") == cycle_number]

    def get_failures_by_type(self, error_type: str) -> list:
        """Get all failures of a specific error type."""
        return [f for f in self.read_all_failures() if f.get("error_type") == error_type]

    def get_recent_sandbox_failures(self, limit: int = 10) -> list:
        """
        Get the most recent sandbox failures.

        Args:
            limit: Maximum number of recent sandbox failures to return.

        Returns:
            List of sandbox failure entries, sorted by timestamp descending.
        """
        all_failures = self.read_all_failures()
        sandbox_failures = [f for f in all_failures if f.get("sandbox_failure") == True]
        sandbox_failures.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        return sandbox_failures[:limit]

    def clear_log(self):
        """Clear the failure log file."""
        open(self.output_file, "w").close()