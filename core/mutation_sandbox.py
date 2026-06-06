import sys
import json
import os
import tempfile
import shutil
import subprocess
import difflib
import traceback
import ast

# Determine the original repository root (the directory containing this script's parent 'core' folder)
# This is used to copy the repo into a temporary sandbox.
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(_SCRIPT_DIR, ".."))

def _copy_repo_to_temp():
    """Create a temporary copy of the entire repository and return the temp directory path."""
    temp_dir = tempfile.mkdtemp(prefix="mutation_sandbox_")
    # Copy all contents from REPO_ROOT to temp_dir, excluding __pycache__ and .git for speed
    for item in os.listdir(REPO_ROOT):
        src = os.path.join(REPO_ROOT, item)
        dst = os.path.join(temp_dir, item)
        if item in (".git", "__pycache__", ".pytest_cache"):
            continue
        if os.path.isdir(src):
            shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__", ".git", ".pytest_cache"))
        else:
            shutil.copy2(src, dst)
    return temp_dir

def _apply_mutation(temp_repo_path, file_rel_path, old_code, new_code):
    """
    Apply the mutation to the file at temp_repo_path/file_rel_path.
    Returns True if the patch was applied successfully, False otherwise.
    """
    full_path = os.path.join(temp_repo_path, file_rel_path)
    if not os.path.exists(full_path):
        return False
    try:
        with open(full_path, "r", encoding="utf-8") as f:
            content = f.read()
        if old_code not in content:
            return False
        # Replace only the first occurrence to simulate a single mutation
        new_content = content.replace(old_code, new_code, 1)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(new_content)
        return True
    except Exception:
        return False

def _compute_diff(temp_repo_path, file_rel_path, original_repo_path):
    """Compute the unified diff between original and mutated file."""
    original_file = os.path.join(original_repo_path, file_rel_path)
    mutated_file = os.path.join(temp_repo_path, file_rel_path)
    if not os.path.exists(original_file) or not os.path.exists(mutated_file):
        return ""
    with open(original_file, "r", encoding="utf-8") as f:
        original_lines = f.readlines()
    with open(mutated_file, "r", encoding="utf-8") as f:
        mutated_lines = f.readlines()
    diff = difflib.unified_diff(
        original_lines, mutated_lines,
        fromfile=f"a/{file_rel_path}",
        tofile=f"b/{file_rel_path}"
    )
    return "".join(diff)

def validate_mutation(proposed_code, target_file_path):
    """
    Validate a proposed code mutation before applying it.
    
    Args:
        proposed_code (str): The new code to be written to the target file
        target_file_path (str): Relative path from repo root to the target file
        
    Returns:
        dict: Structured result with keys:
            - success (bool): True if validation passes
            - error_type (str or None): Type of error if validation fails
            - error_message (str or None): Error message if validation fails
    """
    # Create a temporary directory for validation
    temp_dir = tempfile.mkdtemp(prefix="mutation_validation_")
    
    try:
        # Step 1: Write proposed code to a temp file in the isolated directory
        temp_file_path = os.path.join(temp_dir, os.path.basename(target_file_path))
        with open(temp_file_path, "w", encoding="utf-8") as f:
            f.write(proposed_code)
        
        # Step 2: Attempt to compile the code using ast.parse()
        try:
            ast.parse(proposed_code, filename=target_file_path)
        except SyntaxError as e:
            return {
                "success": False,
                "error_type": "SyntaxError",
                "error_message": f"Syntax error in proposed code: {str(e)}"
            }
        
        # Step 3: Attempt to import the module in a subprocess
        # Create a temporary module name based on the target file
        module_name = os.path.splitext(os.path.basename(target_file_path))[0]
        
        # Copy the repo to temp for proper import context
        temp_repo = _copy_repo_to_temp()
        
        try:
            # Write the proposed code to the target location in the temp repo
            target_full_path = os.path.join(temp_repo, target_file_path)
            os.makedirs(os.path.dirname(target_full_path), exist_ok=True)
            with open(target_full_path, "w", encoding="utf-8") as f:
                f.write(proposed_code)
            
            # Attempt to import the module in a subprocess
            import_command = f"import {module_name}"
            result = subprocess.run(
                [sys.executable, "-c", import_command],
                capture_output=True,
                text=True,
                cwd=temp_repo,
                timeout=30
            )
            
            if result.returncode != 0:
                error_output = result.stderr.strip()
                if "ImportError" in error_output:
                    return {
                        "success": False,
                        "error_type": "ImportError",
                        "error_message": error_output
                    }
                elif "NameError" in error_output:
                    return {
                        "success": False,
                        "error_type": "NameError",
                        "error_message": error_output
                    }
                else:
                    return {
                        "success": False,
                        "error_type": "ImportError",
                        "error_message": error_output
                    }
            
            # If we get here, validation passed
            return {
                "success": True,
                "error_type": None,
                "error_message": None
            }
            
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error_type": "TimeoutError",
                "error_message": "Module import timed out (30 seconds)"
            }
        except Exception as e:
            return {
                "success": False,
                "error_type": "RuntimeError",
                "error_message": f"Unexpected error during import: {str(e)}"
            }
        finally:
            # Clean up the temp repo copy
            shutil.rmtree(temp_repo, ignore_errors=True)
            
    except Exception as e:
        return {
            "success": False,
            "error_type": "RuntimeError",
            "error_message": f"Unexpected error during validation: {str(e)}"
        }
    finally:
        # Clean up temp files
        shutil.rmtree(temp_dir, ignore_errors=True)

def run_mutation(params):
    """
    params: dict with keys:
        - file: relative path from repo root (e.g., "core/utils.py")
        - old_code: string to replace
        - new_code: string to replace with
        - test_paths: optional list of test paths to run (default runs all tests)
    Returns: dict with keys:
        - success: bool (True if mutation applied and tests pass)
        - diff: string (unified diff)
        - test_results: dict from run_test
        - error: optional error message
    """
    file_rel = params.get("file")
    old_code = params.get("old_code")
    new_code = params.get("new_code")
    test_paths = params.get("test_paths", None)

    if not file_rel or old_code is None or new_code is None:
        return {"success": False, "error": "Missing required parameters: file, old_code, new_code"}

    # Create a temporary copy of the repo
    temp_repo = _copy_repo_to_temp()
    try:
        # Apply mutation
        applied = _apply_mutation(temp_repo, file_rel, old_code, new_code)
        if not applied:
            return {"success": False, "error": "Mutation could not be applied (old_code not found or file missing)", "diff": ""}

        # Compute diff
        diff = _compute_diff(temp_repo, file_rel, REPO_ROOT)

        # Run tests
        test_result = run_test({"test_paths": test_paths, "repo_path": temp_repo})

        # Determine success: tests passed (no failures/errors)
        success = test_result.get("passed", False)

        return {
            "success": success,
            "diff": diff,
            "test_results": test_result
        }
    except Exception as e:
        return {"success": False, "error": str(e), "diff": ""}
    finally:
        # Clean up temp directory
        shutil.rmtree(temp_repo, ignore_errors=True)

def run_test(params):
    """
    params: dict with keys:
        - test_paths: optional list of test file/directory paths (relative to repo root)
        - repo_path: optional path to the sandboxed repo (if not provided, uses original)
    Returns: dict with keys:
        - passed: bool (True if all tests pass)
        - output: string (stdout/stderr combined)
        - returncode: int
        - error: optional error message
    """
    test_paths = params.get("test_paths", None)
    repo_path = params.get("repo_path", REPO_ROOT)

    # If no test paths given, run all tests (discover in the repo)
    if test_paths is None:
        test_paths = [repo_path]
    else:
        # Convert relative paths to absolute within the repo
        test_paths = [os.path.join(repo_path, tp) if not os.path.isabs(tp) else tp for tp in test_paths]

    # Run pytest
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pytest"] + test_paths + ["--tb=short", "-q"],
            capture_output=True,
            text=True,
            cwd=repo_path,
            timeout=300  # 5 minutes timeout
        )
        passed = result.returncode == 0
        return {
            "passed": passed,
            "output": result.stdout + result.stderr,
            "returncode": result.returncode
        }
    except subprocess.TimeoutExpired:
        return {
            "passed": False,
            "output": "Test execution timed out (300 seconds)",
            "returncode": -1
        }
    except FileNotFoundError:
        return {
            "passed": False,
            "output": "pytest not found. Ensure it is installed.",
            "returncode": -2
        }
    except Exception as e:
        return {
            "passed": False,
            "output": f"Unexpected error: {str(e)}",
            "returncode": -3
        }

def handle_request(request):
    """Process a single JSON-RPC request and return a response dict."""
    req_id = request.get("id")
    method = request.get("method")
    params = request.get("params", {})

    if method == "run_mutation":
        result = run_mutation(params)
        return {"jsonrpc": "2.0", "id": req_id, "result": result}
    elif method == "run_test":
        result = run_test(params)
        return {"jsonrpc": "2.0", "id": req_id, "result": result}
    elif method == "validate_mutation":
        proposed_code = params.get("proposed_code")
        target_file_path = params.get("target_file_path")
        if not proposed_code or not target_file_path:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {
                    "code": -32602,
                    "message": "Missing required parameters: proposed_code, target_file_path"
                }
            }
        result = validate_mutation(proposed_code, target_file_path)
        return {"jsonrpc": "2.0", "id": req_id, "result": result}
    else:
        return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": f"Method '{method}' not found"}}

def main():
    """Read JSON-RPC requests from stdin line by line, write responses to stdout."""
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
            response = handle_request(request)
        except json.JSONDecodeError as e:
            response = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": f"Parse error: {str(e)}"}}
        except Exception as e:
            response = {"jsonrpc": "2.0", "id": None, "error": {"code": -32603, "message": f"Internal error: {str(e)}"}}
        # Write response as a single JSON line
        sys.stdout.write(json.dumps(response) + "\n")
        sys.stdout.flush()

if __name__ == "__main__":
    main()