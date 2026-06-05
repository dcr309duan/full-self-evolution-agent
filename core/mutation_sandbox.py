import sys
import json
import os
import tempfile
import shutil
import subprocess
import difflib
import traceback

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