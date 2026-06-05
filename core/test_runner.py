import subprocess
import sys
import os
import json
import re
from typing import List, Dict, Any, Optional
import glob

def run_tests(test_paths: List[str], timeout: int = 30) -> Dict[str, Any]:
    """
    Run tests specified by test_paths with a given timeout.
    
    Args:
        test_paths: List of paths to test files or directories
        timeout: Maximum execution time in seconds (default: 30)
    
    Returns:
        Dictionary containing test results, including stdout, stderr, return code,
        and any errors encountered.
    """
    if not test_paths:
        return {
            "success": False,
            "error": "No test paths provided",
            "stdout": "",
            "stderr": "No test paths provided",
            "return_code": -1
        }
    
    # Validate paths exist
    valid_paths = []
    for path in test_paths:
        if os.path.exists(path):
            valid_paths.append(path)
        else:
            print(f"Warning: Test path '{path}' does not exist, skipping.", file=sys.stderr)
    
    if not valid_paths:
        return {
            "success": False,
            "error": "No valid test paths found",
            "stdout": "",
            "stderr": "No valid test paths found",
            "return_code": -1
        }
    
    try:
        # Build command to run tests using pytest
        cmd = [sys.executable, "-m", "pytest"] + valid_paths + ["-v", "--tb=short"]
        
        # Run the test process
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=os.getcwd()
        )
        
        return {
            "success": result.returncode == 0,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "return_code": result.returncode,
            "error": None if result.returncode == 0 else result.stderr[:500]  # Truncate long errors
        }
    
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error": f"Test execution timed out after {timeout} seconds",
            "stdout": "",
            "stderr": f"Timeout: Tests did not complete within {timeout} seconds",
            "return_code": -1
        }
    except FileNotFoundError as e:
        return {
            "success": False,
            "error": f"Python or pytest not found: {str(e)}",
            "stdout": "",
            "stderr": f"FileNotFoundError: {str(e)}",
            "return_code": -1
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Unexpected error running tests: {str(e)}",
            "stdout": "",
            "stderr": f"Exception: {str(e)}",
            "return_code": -1
        }


def parse_results(raw_output: str) -> Dict[str, Any]:
    """
    Parse raw test output into structured results.
    
    Args:
        raw_output: Raw string output from test execution
    
    Returns:
        Dictionary with parsed test results including:
        - total: total number of tests
        - passed: number of passed tests
        - failed: number of failed tests
        - errors: list of error messages
        - test_details: list of individual test results
    """
    if not raw_output:
        return {
            "total": 0,
            "passed": 0,
            "failed": 0,
            "errors": [],
            "test_details": []
        }
    
    lines = raw_output.split('\n')
    test_details = []
    errors = []
    passed_count = 0
    failed_count = 0
    
    # Pattern to match test results: PASSED/FAILED test_name
    test_pattern = re.compile(r'^(PASSED|FAILED)\s+(.+)$')
    # Pattern to match test summary line
    summary_pattern = re.compile(r'^=+\s+(\d+)\s+(passed|failed|error|warning)s?\s+in\s+[\d.]+\w+')
    
    for line in lines:
        line = line.strip()
        
        # Match individual test results
        match = test_pattern.match(line)
        if match:
            status = match.group(1).lower()
            test_name = match.group(2).strip()
            test_details.append({
                "name": test_name,
                "status": status,
                "output": line
            })
            if status == "passed":
                passed_count += 1
            elif status == "failed":
                failed_count += 1
        
        # Capture error messages
        if "ERROR" in line or "Error" in line:
            errors.append(line)
    
    # Try to extract total from summary if available
    total = passed_count + failed_count
    for line in lines:
        match = summary_pattern.match(line.strip())
        if match:
            total = int(match.group(1))
            break
    
    return {
        "total": total,
        "passed": passed_count,
        "failed": failed_count,
        "errors": errors[:20],  # Limit to first 20 errors
        "test_details": test_details
    }


def get_coverage(modules: List[str]) -> Dict[str, Any]:
    """
    Get code coverage information for specified modules.
    
    Args:
        modules: List of module names to get coverage for
    
    Returns:
        Dictionary with coverage data including:
        - covered_lines: total lines covered
        - total_lines: total executable lines
        - coverage_percent: percentage of coverage
        - module_coverage: per-module coverage details
    """
    if not modules:
        return {
            "covered_lines": 0,
            "total_lines": 0,
            "coverage_percent": 0.0,
            "module_coverage": {}
        }
    
    try:
        # Try to use coverage.py if available
        import coverage
        
        # Create a coverage object and load existing data
        cov = coverage.Coverage()
        cov.load()
        
        # Get coverage data for specified modules
        module_coverage = {}
        total_covered = 0
        total_lines = 0
        
        for module_name in modules:
            try:
                # Get coverage for module
                data = cov.analysis2(module_name)
                if data:
                    # data structure: (filename, lines_executed, lines_missed, lines_covered)
                    _, executed, missing, _ = data
                    covered = len(executed) - len(missing)
                    total = len(executed)
                    total_covered += covered
                    total_lines += total
                    
                    module_coverage[module_name] = {
                        "covered_lines": covered,
                        "total_lines": total,
                        "coverage_percent": (covered / total * 100) if total > 0 else 0.0
                    }
            except Exception as e:
                module_coverage[module_name] = {
                    "covered_lines": 0,
                    "total_lines": 0,
                    "coverage_percent": 0.0,
                    "error": str(e)
                }
        
        coverage_percent = (total_covered / total_lines * 100) if total_lines > 0 else 0.0
        
        return {
            "covered_lines": total_covered,
            "total_lines": total_lines,
            "coverage_percent": round(coverage_percent, 2),
            "module_coverage": module_coverage
        }
    
    except ImportError:
        # coverage.py not installed, return placeholder data
        return {
            "covered_lines": 0,
            "total_lines": 0,
            "coverage_percent": 0.0,
            "module_coverage": {module: {"error": "coverage.py not installed"} for module in modules},
            "warning": "coverage.py is not installed. Install with: pip install coverage"
        }
    except Exception as e:
        return {
            "covered_lines": 0,
            "total_lines": 0,
            "coverage_percent": 0.0,
            "module_coverage": {},
            "error": f"Failed to get coverage: {str(e)}"
        }


def discover_test_files(root_dir: str = ".") -> List[str]:
    """
    Discover all test files in the project using glob pattern *test*.py.
    
    Args:
        root_dir: Root directory to search from (default: current directory)
    
    Returns:
        List of test file paths found
    """
    test_files = []
    pattern = os.path.join(root_dir, "**", "*test*.py")
    test_files = glob.glob(pattern, recursive=True)
    return test_files


def inject_test_function(file_path: str, test_function_code: str) -> bool:
    """
    Inject a new test function into a given file by appending it to the end.
    
    Args:
        file_path: Path to the test file to modify
        test_function_code: The complete test function code to inject
    
    Returns:
        True if successful, False otherwise
    """
    try:
        # Read the existing file content
        with open(file_path, 'r') as f:
            content = f.read()
        
        # Ensure the file ends with a newline before appending
        if not content.endswith('\n'):
            content += '\n'
        
        # Append the new test function
        content += '\n' + test_function_code + '\n'
        
        # Write the modified content back to the file
        with open(file_path, 'w') as f:
            f.write(content)
        
        return True
    except Exception as e:
        print(f"Error injecting test function into {file_path}: {str(e)}", file=sys.stderr)
        return False


def _validate_paths(paths: List[str]) -> List[str]:
    """Internal helper to validate and filter test paths."""
    valid = []
    for path in paths:
        if os.path.exists(path):
            valid.append(path)
        else:
            print(f"Warning: Path '{path}' does not exist.", file=sys.stderr)
    return valid