import subprocess
import sys
import json
import time
import os
from typing import List, Dict, Any, Optional

def run_test(test_paths: List[str], pytest_args: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    Runs pytest on the given test file paths in a subprocess.
    
    Args:
        test_paths: List of paths to test files or directories.
        pytest_args: Additional arguments to pass to pytest (e.g., ['-v', '-x']).
    
    Returns:
        A dictionary with structured JSON results including pass/fail counts,
        error messages, and timing.
    """
    if pytest_args is None:
        pytest_args = []
    
    start_time = time.time()
    
    # Build the pytest command
    cmd = [sys.executable, '-m', 'pytest'] + test_paths + pytest_args
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600  # 10 minutes timeout
        )
    except subprocess.TimeoutExpired:
        return {
            "status": "timeout",
            "test_paths": test_paths,
            "passed": 0,
            "failed": 0,
            "errors": ["Test execution timed out after 10 minutes"],
            "stdout": "",
            "stderr": "Timeout expired",
            "returncode": -1,
            "execution_time_seconds": time.time() - start_time
        }
    except Exception as e:
        return {
            "status": "error",
            "test_paths": test_paths,
            "passed": 0,
            "failed": 0,
            "errors": [str(e)],
            "stdout": "",
            "stderr": str(e),
            "returncode": -1,
            "execution_time_seconds": time.time() - start_time
        }
    
    end_time = time.time()
    execution_time = end_time - start_time
    
    # Parse pytest output to extract pass/fail counts
    passed = 0
    failed = 0
    errors = []
    
    stdout_lines = result.stdout.split('\n')
    stderr_lines = result.stderr.split('\n')
    
    # Look for the summary line in stdout (e.g., "= 1 passed in 0.12s =")
    summary_found = False
    for line in stdout_lines:
        if 'passed' in line and 'failed' in line and '=' in line:
            summary_found = True
            # Extract numbers from summary line
            parts = line.split()
            for i, part in enumerate(parts):
                if part == 'passed':
                    try:
                        passed = int(parts[i-1])
                    except (ValueError, IndexError):
                        pass
                elif part == 'failed':
                    try:
                        failed = int(parts[i-1])
                    except (ValueError, IndexError):
                        pass
                elif part == 'errors':
                    try:
                        errors_count = int(parts[i-1])
                        errors.append(f"{errors_count} errors reported")
                    except (ValueError, IndexError):
                        pass
    
    if not summary_found:
        # Try to parse from the last line
        for line in reversed(stdout_lines):
            if 'passed' in line or 'failed' in line:
                parts = line.split()
                for i, part in enumerate(parts):
                    if part == 'passed':
                        try:
                            passed = int(parts[i-1])
                        except (ValueError, IndexError):
                            pass
                    elif part == 'failed':
                        try:
                            failed = int(parts[i-1])
                        except (ValueError, IndexError):
                            pass
                break
    
    # Collect error messages from stderr and failed test lines
    for line in stderr_lines:
        if line.strip() and 'ERROR' in line.upper():
            errors.append(line.strip())
    
    for line in stdout_lines:
        if 'FAILED' in line or 'ERROR' in line:
            errors.append(line.strip())
    
    # Determine overall status
    if result.returncode == 0:
        status = "success"
    elif result.returncode == 1:
        status = "tests_failed"
    elif result.returncode == 2:
        status = "error"
    elif result.returncode == 5:
        status = "no_tests_collected"
    else:
        status = "unknown_error"
    
    return {
        "status": status,
        "test_paths": test_paths,
        "passed": passed,
        "failed": failed,
        "errors": errors if errors else None,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "returncode": result.returncode,
        "execution_time_seconds": round(execution_time, 3)
    }


def get_coverage(modules: List[str], test_paths: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    Runs coverage analysis on specified modules.
    
    Args:
        modules: List of module names or paths to measure coverage for.
        test_paths: Optional list of test paths to run during coverage.
    
    Returns:
        A dictionary with coverage results including line coverage percentages,
        missing lines, and timing.
    """
    start_time = time.time()
    
    # Build coverage command
    coverage_args = ['run', '--source=' + ','.join(modules)]
    if test_paths:
        coverage_args.extend(['-m', 'pytest'] + test_paths)
    else:
        # If no tests specified, run a basic coverage check
        coverage_args.extend(['-m', 'pytest', '--coverage'])
    
    cmd = [sys.executable, '-m', 'coverage'] + coverage_args
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600
        )
    except subprocess.TimeoutExpired:
        return {
            "status": "timeout",
            "modules": modules,
            "line_coverage_percent": None,
            "missing_lines": [],
            "errors": ["Coverage execution timed out after 10 minutes"],
            "execution_time_seconds": time.time() - start_time
        }
    except Exception as e:
        return {
            "status": "error",
            "modules": modules,
            "line_coverage_percent": None,
            "missing_lines": [],
            "errors": [str(e)],
            "execution_time_seconds": time.time() - start_time
        }
    
    # Now get the coverage report in JSON format
    report_cmd = [sys.executable, '-m', 'coverage', 'json', '--pretty-print']
    try:
        report_result = subprocess.run(
            report_cmd,
            capture_output=True,
            text=True,
            timeout=30
        )
    except Exception as e:
        return {
            "status": "error",
            "modules": modules,
            "line_coverage_percent": None,
            "missing_lines": [],
            "errors": [f"Failed to generate coverage report: {str(e)}"],
            "execution_time_seconds": time.time() - start_time
        }
    
    # Parse the coverage JSON file
    coverage_data = {}
    try:
        with open('coverage.json', 'r') as f:
            coverage_data = json.load(f)
        os.remove('coverage.json')  # Clean up
    except (FileNotFoundError, json.JSONDecodeError) as e:
        return {
            "status": "error",
            "modules": modules,
            "line_coverage_percent": None,
            "missing_lines": [],
            "errors": [f"Failed to parse coverage data: {str(e)}"],
            "execution_time_seconds": time.time() - start_time
        }
    
    # Extract coverage information for requested modules
    total_covered = 0
    total_lines = 0
    missing_lines = []
    
    files = coverage_data.get('files', {})
    for file_path, file_data in files.items():
        # Check if this file belongs to one of the requested modules
        for module in modules:
            if module in file_path or file_path.startswith(module):
                summary = file_data.get('summary', {})
                covered = summary.get('covered_lines', 0)
                total = summary.get('num_statements', 0)
                total_covered += covered
                total_lines += total
                
                # Collect missing lines
                missing = file_data.get('missing_lines', [])
                for line_num in missing:
                    missing_lines.append(f"{file_path}:{line_num}")
                break
    
    # Calculate overall coverage percentage
    if total_lines > 0:
        coverage_percent = round((total_covered / total_lines) * 100, 2)
    else:
        coverage_percent = 0.0
    
    end_time = time.time()
    
    return {
        "status": "success" if result.returncode == 0 else "tests_failed",
        "modules": modules,
        "line_coverage_percent": coverage_percent,
        "covered_lines": total_covered,
        "total_lines": total_lines,
        "missing_lines": missing_lines if missing_lines else None,
        "errors": None if result.returncode == 0 else [result.stderr],
        "execution_time_seconds": round(end_time - start_time, 3)
    }


def run_test_suite(test_paths: List[str], 
                   modules: Optional[List[str]] = None,
                   pytest_args: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    Convenience function to run tests and optionally get coverage.
    
    Args:
        test_paths: List of test file/directory paths.
        modules: Optional list of modules for coverage analysis.
        pytest_args: Additional pytest arguments.
    
    Returns:
        Combined results from test execution and optional coverage.
    """
    test_results = run_test(test_paths, pytest_args)
    
    if modules:
        coverage_results = get_coverage(modules, test_paths)
        test_results['coverage'] = coverage_results
    
    return test_results


if __name__ == '__main__':
    # Example usage when run directly
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python test_sandbox.py <test_path1> [test_path2 ...] [--coverage module1,module2]")
        sys.exit(1)
    
    test_paths = []
    modules = None
    i = 1
    while i < len(sys.argv):
        if sys.argv[i] == '--coverage' and i + 1 < len(sys.argv):
            modules = sys.argv[i + 1].split(',')
            i += 2
        else:
            test_paths.append(sys.argv[i])
            i += 1
    
    if not test_paths:
        print("No test paths provided.")
        sys.exit(1)
    
    result = run_test_suite(test_paths, modules)
    print(json.dumps(result, indent=2))