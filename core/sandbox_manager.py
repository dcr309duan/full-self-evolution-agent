import os
import sys
import shutil
import tempfile
import subprocess
import json
import datetime
from pathlib import Path
from typing import Dict, Any, Optional, Tuple

class SandboxManager:
    """
    Manages sandboxed execution of agent state with mutations.
    
    Clones the entire agent state into a temporary directory, applies a mutation
    (diff/patch), runs the full integration test suite, and returns success/failure
    with detailed logs and structured failure reports.
    """
    
    # Directories and files to clone from the agent state
    SOURCE_DIRS = ['core', 'tests', 'config']
    SOURCE_FILES = ['goals.json', 'meta_parameters.json']
    
    # Path to the integration test suite
    INTEGRATION_TEST_PATH = 'tests/test_integration_evolution_loop.py'
    
    # Directory for storing failure reports
    FAILURES_DIR = 'logs/failures'
    
    def __init__(self, project_root: Optional[str] = None):
        """
        Initialize the SandboxManager.
        
        Args:
            project_root: Path to the project root directory. If None, uses current working directory.
        """
        self.project_root = Path(project_root or os.getcwd()).resolve()
        self.failures_dir = self.project_root / self.FAILURES_DIR
        
        # Ensure failures directory exists
        self.failures_dir.mkdir(parents=True, exist_ok=True)
    
    def _clone_agent_state(self, target_dir: Path) -> None:
        """
        Clone the entire agent state into the target directory.
        
        Args:
            target_dir: Path to the temporary directory where state will be cloned.
        """
        # Clone source directories
        for dir_name in self.SOURCE_DIRS:
            src_dir = self.project_root / dir_name
            dst_dir = target_dir / dir_name
            if src_dir.exists():
                shutil.copytree(src_dir, dst_dir, symlinks=False, ignore_dangling_symlinks=True)
        
        # Clone individual files
        for file_name in self.SOURCE_FILES:
            src_file = self.project_root / file_name
            dst_file = target_dir / file_name
            if src_file.exists():
                shutil.copy2(src_file, dst_file)
        
        # Clone history log if it exists
        history_log = self.project_root / 'history.log'
        if history_log.exists():
            shutil.copy2(history_log, target_dir / 'history.log')
    
    def _apply_mutation(self, target_dir: Path, mutation: str) -> bool:
        """
        Apply a mutation (diff/patch) to the cloned files.
        
        Args:
            target_dir: Path to the directory containing cloned files.
            mutation: A unified diff/patch string to apply.
            
        Returns:
            True if the patch was applied successfully, False otherwise.
        """
        # Write the mutation to a temporary patch file
        patch_file = target_dir / '_mutation.patch'
        try:
            patch_file.write_text(mutation)
        except Exception as e:
            print(f"Error writing patch file: {e}")
            return False
        
        # Apply the patch using the 'patch' command
        try:
            result = subprocess.run(
                ['patch', '-p1', '-i', str(patch_file)],
                cwd=str(target_dir),
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode != 0:
                print(f"Patch application failed:\n{result.stderr}")
                return False
            return True
        except subprocess.TimeoutExpired:
            print("Patch application timed out")
            return False
        except FileNotFoundError:
            print("'patch' command not found. Please install patch.")
            return False
        except Exception as e:
            print(f"Error applying patch: {e}")
            return False
        finally:
            # Clean up the patch file
            if patch_file.exists():
                patch_file.unlink()
    
    def _run_integration_tests(self, target_dir: Path) -> Tuple[bool, str, str]:
        """
        Run the full integration test suite in the sandbox.
        
        Args:
            target_dir: Path to the sandbox directory.
            
        Returns:
            Tuple of (success, stdout, stderr)
        """
        test_path = target_dir / self.INTEGRATION_TEST_PATH
        
        if not test_path.exists():
            return False, "", f"Integration test file not found: {test_path}"
        
        try:
            result = subprocess.run(
                [sys.executable, '-m', 'pytest', str(test_path), '-v', '--tb=long'],
                cwd=str(target_dir),
                capture_output=True,
                text=True,
                timeout=300  # 5 minutes timeout for tests
            )
            
            success = result.returncode == 0
            return success, result.stdout, result.stderr
            
        except subprocess.TimeoutExpired:
            return False, "", "Integration tests timed out after 5 minutes"
        except Exception as e:
            return False, "", f"Error running integration tests: {str(e)}"
    
    def _generate_failure_report(self, 
                                  mutation: str, 
                                  test_stdout: str, 
                                  test_stderr: str,
                                  affected_modules: list) -> Dict[str, Any]:
        """
        Generate a structured failure report.
        
        Args:
            mutation: The mutation that was applied.
            test_stdout: Standard output from the test run.
            test_stderr: Standard error from the test run.
            affected_modules: List of modules affected by the mutation.
            
        Returns:
            Dictionary containing the structured failure report.
        """
        # Extract error types from test output
        error_types = []
        for line in test_stderr.split('\n'):
            if 'Error' in line or 'Exception' in line or 'Failed' in line:
                error_types.append(line.strip())
        
        # If no specific errors found, capture the last few lines of stderr
        if not error_types:
            stderr_lines = test_stderr.strip().split('\n')
            if stderr_lines:
                error_types = stderr_lines[-5:]  # Last 5 lines
        
        report = {
            'timestamp': datetime.datetime.now().isoformat(),
            'mutation': mutation,
            'test_stdout': test_stdout,
            'test_stderr': test_stderr,
            'error_types': error_types,
            'affected_modules': affected_modules,
            'success': False
        }
        
        return report
    
    def _save_failure_report(self, report: Dict[str, Any]) -> str:
        """
        Save a failure report to the failures directory.
        
        Args:
            report: The failure report dictionary.
            
        Returns:
            Path to the saved report file.
        """
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        report_file = self.failures_dir / f'failure_{timestamp}.json'
        
        try:
            report_file.write_text(json.dumps(report, indent=2))
            return str(report_file)
        except Exception as e:
            print(f"Error saving failure report: {e}")
            return ""
    
    def _determine_affected_modules(self, mutation: str) -> list:
        """
        Determine which modules are affected by a mutation.
        
        Args:
            mutation: The mutation (diff/patch) string.
            
        Returns:
            List of affected module paths.
        """
        affected = []
        for line in mutation.split('\n'):
            if line.startswith('--- a/') or line.startswith('+++ b/'):
                # Extract file path from diff header
                file_path = line[6:].strip()  # Remove '--- a/' or '+++ b/'
                if file_path and file_path not in affected:
                    affected.append(file_path)
        return affected
    
    def run_sandboxed(self, mutation: str) -> Dict[str, Any]:
        """
        Run the full sandboxed workflow: clone, apply mutation, run tests.
        
        Args:
            mutation: A unified diff/patch string to apply to the cloned state.
            
        Returns:
            Dictionary with keys:
                - success (bool): Whether tests passed
                - test_stdout (str): Standard output from tests
                - test_stderr (str): Standard error from tests
                - failure_report_path (str): Path to saved failure report (if failed)
                - affected_modules (list): List of affected modules
        """
        # Create temporary directory
        with tempfile.TemporaryDirectory(prefix='sandbox_') as tmp_dir:
            sandbox_dir = Path(tmp_dir)
            
            # Step 1: Clone agent state
            try:
                self._clone_agent_state(sandbox_dir)
            except Exception as e:
                return {
                    'success': False,
                    'test_stdout': '',
                    'test_stderr': f"Failed to clone agent state: {str(e)}",
                    'failure_report_path': '',
                    'affected_modules': []
                }
            
            # Step 2: Apply mutation
            if not self._apply_mutation(sandbox_dir, mutation):
                return {
                    'success': False,
                    'test_stdout': '',
                    'test_stderr': 'Failed to apply mutation',
                    'failure_report_path': '',
                    'affected_modules': []
                }
            
            # Step 3: Run integration tests
            success, test_stdout, test_stderr = self._run_integration_tests(sandbox_dir)
            
            # Step 4: Determine affected modules
            affected_modules = self._determine_affected_modules(mutation)
            
            # Step 5: Handle failure
            failure_report_path = ''
            if not success:
                report = self._generate_failure_report(
                    mutation=mutation,
                    test_stdout=test_stdout,
                    test_stderr=test_stderr,
                    affected_modules=affected_modules
                )
                failure_report_path = self._save_failure_report(report)
            
            return {
                'success': success,
                'test_stdout': test_stdout,
                'test_stderr': test_stderr,
                'failure_report_path': failure_report_path,
                'affected_modules': affected_modules
            }