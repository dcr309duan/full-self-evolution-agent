import os
import sys
import tempfile
import subprocess
import threading
import importlib.util
from pathlib import Path
from typing import Tuple, Optional


class SandboxRunner:
    """A subprocess-based sandbox runner for validating proposed code changes.

    This runner writes code to a temporary file, spawns a subprocess to compile/import it,
    and captures output with a configurable timeout. It handles edge cases like missing
    dependencies by checking import paths before execution.
    """

    def __init__(self, timeout: int = 5, python_executable: Optional[str] = None):
        """Initialize the sandbox runner.

        Args:
            timeout: Maximum execution time in seconds (default: 5).
            python_executable: Path to Python executable (default: sys.executable).
        """
        self.timeout = timeout
        self.python_executable = python_executable or sys.executable

    def _check_imports(self, code: str) -> Tuple[bool, str]:
        """Check if all imports in the code are resolvable.

        Args:
            code: The Python source code to check.

        Returns:
            Tuple of (success, error_message). If success is True, all imports are valid.
        """
        try:
            # Parse the code to extract import statements
            tree = compile(code, '<sandbox>', 'exec', flags=0)
            # We use a simple approach: try to import each module mentioned
            import re
            import_lines = re.findall(r'^(?:import |from\s+)(\S+)', code, re.MULTILINE)
            for line in import_lines:
                # Handle 'from X import Y' and 'import X.Y.Z'
                module_name = line.split()[0] if 'import' in line else line
                # Get the top-level package name
                top_level = module_name.split('.')[0]
                try:
                    importlib.import_module(top_level)
                except ImportError as e:
                    return False, f"Missing dependency: {top_level} - {str(e)}"
            return True, ""
        except SyntaxError as e:
            return False, f"Syntax error during import check: {str(e)}"
        except Exception as e:
            return False, f"Unexpected error during import check: {str(e)}"

    def _create_temp_file(self, code: str) -> str:
        """Write the proposed code to a temporary file with .py extension.

        Args:
            code: The Python source code to write.

        Returns:
            Path to the temporary file.
        """
        with tempfile.NamedTemporaryFile(
            mode='w',
            suffix='.py',
            delete=False,
            dir=tempfile.gettempdir()
        ) as f:
            f.write(code)
            return f.name

    def _run_subprocess(self, file_path: str) -> Tuple[int, str, str]:
        """Run the temporary file in a subprocess with a timeout.

        Args:
            file_path: Path to the Python file to execute.

        Returns:
            Tuple of (exit_code, stdout_output, stderr_output).
        """
        stdout = []
        stderr = []
        process = None

        def target():
            nonlocal process
            try:
                process = subprocess.Popen(
                    [self.python_executable, '-c', f'import {Path(file_path).stem}'],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    cwd=os.path.dirname(file_path)
                )
                out, err = process.communicate()
                stdout.append(out)
                stderr.append(err)
            except Exception as e:
                stderr.append(str(e))

        thread = threading.Thread(target=target)
        thread.daemon = True
        thread.start()
        thread.join(timeout=self.timeout)

        if thread.is_alive():
            # Timeout occurred
            if process:
                process.kill()
                process.wait()
            return -1, "", f"Execution timed out after {self.timeout} seconds"

        if process is None:
            return -2, "", "Failed to start subprocess"

        return process.returncode, stdout[0] if stdout else "", stderr[0] if stderr else ""

    def run(self, code: str) -> Tuple[bool, str, int]:
        """Run the proposed code in the sandbox.

        Args:
            code: The Python source code to validate.

        Returns:
            Tuple of (success, error_message, exit_code). success is True if the code
            compiled and executed without errors.
        """
        # Step 1: Check imports first
        imports_ok, import_error = self._check_imports(code)
        if not imports_ok:
            return False, import_error, -3

        # Step 2: Write code to temp file
        file_path = None
        try:
            file_path = self._create_temp_file(code)

            # Step 3: Run in subprocess
            exit_code, stdout, stderr = self._run_subprocess(file_path)

            # Step 4: Process results
            if exit_code != 0:
                error_msg = stderr if stderr else f"Exit code: {exit_code}"
                return False, error_msg, exit_code

            return True, "", exit_code

        except Exception as e:
            return False, f"Sandbox execution error: {str(e)}", -4

        finally:
            # Clean up temp file
            if file_path and os.path.exists(file_path):
                try:
                    os.unlink(file_path)
                except OSError:
                    pass

    def run_with_stdout(self, code: str) -> Tuple[bool, str, str, int]:
        """Run the proposed code and also return stdout.

        Args:
            code: The Python source code to validate.

        Returns:
            Tuple of (success, error_message, stdout_output, exit_code).
        """
        file_path = None
        try:
            # Check imports
            imports_ok, import_error = self._check_imports(code)
            if not imports_ok:
                return False, import_error, "", -3

            file_path = self._create_temp_file(code)
            exit_code, stdout, stderr = self._run_subprocess(file_path)

            if exit_code != 0:
                error_msg = stderr if stderr else f"Exit code: {exit_code}"
                return False, error_msg, stdout, exit_code

            return True, "", stdout, exit_code

        except Exception as e:
            return False, f"Sandbox execution error: {str(e)}", "", -4

        finally:
            if file_path and os.path.exists(file_path):
                try:
                    os.unlink(file_path)
                except OSError:
                    pass


# Convenience function for quick sandbox execution
def run_in_sandbox(code: str, timeout: int = 5) -> Tuple[bool, str, int]:
    """Quickly run code in the sandbox with default settings.

    Args:
        code: The Python source code to validate.
        timeout: Maximum execution time in seconds.

    Returns:
        Tuple of (success, error_message, exit_code).
    """
    runner = SandboxRunner(timeout=timeout)
    return runner.run(code)