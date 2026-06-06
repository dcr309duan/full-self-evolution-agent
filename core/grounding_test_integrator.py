import ast
import os
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path
from typing import List, Dict, Optional, Tuple

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
DEFAULT_LOG_DIR = "logs"
DEFAULT_TEST_REGISTRY_DIR = "test_registry"
DEFAULT_ROLLBACK_MODULE = "core.rollback_manager"
DEFAULT_ROLLBACK_FUNC = "rollback_capability"
DEFAULT_QUALITY_GATE_LOG = "mutation_quality_gate.log"

# ---------------------------------------------------------------------------
# Helper: parse capability description to extract affected module paths
# ---------------------------------------------------------------------------
def parse_affected_modules(capability_description: str) -> List[str]:
    """
    Parse a capability description string to extract file paths / module names
    that are affected.  Uses simple heuristics:
      - lines containing 'file:' or 'module:' followed by a path
      - lines that look like Python import paths (e.g. 'core.foo')
      - any quoted string that ends with '.py'
    Returns a list of unique module paths (relative to project root).
    """
    modules: List[str] = []
    lines = capability_description.splitlines()
    for line in lines:
        line = line.strip()
        # pattern: file: path/to/module.py
        if line.lower().startswith("file:"):
            parts = line.split(":", 1)
            if len(parts) == 2:
                candidate = parts[1].strip().strip('"').strip("'")
                if candidate:
                    modules.append(candidate)
        # pattern: module: some.module.path
        elif line.lower().startswith("module:"):
            parts = line.split(":", 1)
            if len(parts) == 2:
                candidate = parts[1].strip().strip('"').strip("'")
                if candidate:
                    modules.append(candidate.replace(".", "/") + ".py")
        # lines that look like Python import paths (e.g. core.foo)
        elif line.startswith("core.") or line.startswith("src."):
            modules.append(line.replace(".", "/") + ".py")
        # quoted strings ending with .py
        elif ".py" in line:
            # try to extract quoted strings
            import re
            matches = re.findall(r'["\']([^"\']+\.py)["\']', line)
            for m in matches:
                modules.append(m)
    # deduplicate and filter
    seen = set()
    unique = []
    for m in modules:
        norm = m.replace("\\", "/")
        if norm not in seen:
            seen.add(norm)
            unique.append(norm)
    return unique


# ---------------------------------------------------------------------------
# Helper: generate a minimal assert-based unit test for a given module file
# ---------------------------------------------------------------------------
def generate_minimal_test(module_path: str) -> str:
    """
    Given a path to a Python module file (relative to cwd), generate a minimal
    unittest-style test that imports the module and runs a simple assertion
    (e.g., that the module can be imported without error).
    Returns the full test source code as a string.
    """
    # Convert file path to a Python module name
    module_name = module_path.replace("/", ".").replace("\\", ".").rstrip(".py")
    # Sanitize for use as a test class name
    safe_name = module_name.replace(".", "_").replace("-", "_")
    test_code = f"""import unittest
import sys
import os

# Ensure the project root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class Test{safe_name}(unittest.TestCase):
    def test_import(self):
        try:
            __import__("{module_name}")
        except Exception as e:
            self.fail(f"Failed to import module {{module_name}}: {{e}}")

    def test_module_has_attributes(self):
        mod = __import__("{module_name}")
        # Basic check: module should have at least one public attribute
        public = [x for x in dir(mod) if not x.startswith("_")]
        self.assertTrue(len(public) > 0, f"Module {{module_name}} has no public attributes")

if __name__ == "__main__":
    unittest.main()
"""
    return test_code


# ---------------------------------------------------------------------------
# Helper: run a test via subprocess
# ---------------------------------------------------------------------------
def run_test_via_subprocess(test_source: str, module_path: str) -> Tuple[bool, str]:
    """
    Write test_source to a temporary file, run it with subprocess, capture output.
    Returns (success: bool, output: str).
    """
    # Create a temporary test file
    fd, tmp_path = tempfile.mkstemp(suffix="_test.py", prefix="grounding_test_", text=True)
    try:
        with os.fdopen(fd, "w") as f:
            f.write(test_source)
        # Run the test
        result = subprocess.run(
            [sys.executable, tmp_path],
            capture_output=True,
            text=True,
            timeout=30  # 30 seconds max per test
        )
        success = (result.returncode == 0)
        output = result.stdout + result.stderr
        return success, output
    except subprocess.TimeoutExpired:
        return False, "Test timed out after 30 seconds"
    except Exception as e:
        return False, f"Exception while running test: {e}"
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Helper: log failure to mutation quality gate log
# ---------------------------------------------------------------------------
def log_failure_to_quality_gate(module_path: str, error_output: str,
                                 log_dir: str = DEFAULT_LOG_DIR,
                                 log_file: str = DEFAULT_QUALITY_GATE_LOG) -> None:
    """Append a failure record to the quality gate log file."""
    log_path = Path(log_dir) / log_file
    log_path.parent.mkdir(parents=True, exist_ok=True)
    timestamp = __import__("datetime").datetime.now().isoformat()
    with open(log_path, "a") as f:
        f.write(f"[{timestamp}] GROUNDING_TEST_FAILURE\n")
        f.write(f"  Module: {module_path}\n")
        f.write(f"  Error:\n")
        for line in error_output.splitlines():
            f.write(f"    {line}\n")
        f.write("\n")


# ---------------------------------------------------------------------------
# Helper: register test in test registry
# ---------------------------------------------------------------------------
def register_test_in_registry(module_path: str, test_source: str,
                               registry_dir: str = DEFAULT_TEST_REGISTRY_DIR) -> None:
    """Save the generated test source to a registry directory for future reference."""
    registry_path = Path(registry_dir)
    registry_path.mkdir(parents=True, exist_ok=True)
    # Create a safe filename based on module path
    safe_name = module_path.replace("/", "_").replace("\\", "_").replace(".", "_")
    test_file = registry_path / f"test_{safe_name}.py"
    with open(test_file, "w") as f:
        f.write(test_source)


# ---------------------------------------------------------------------------
# Helper: call rollback function
# ---------------------------------------------------------------------------
def call_rollback(capability_id: str, module_path: str,
                  rollback_module: str = DEFAULT_ROLLBACK_MODULE,
                  rollback_func: str = DEFAULT_ROLLBACK_FUNC) -> bool:
    """
    Dynamically import the rollback module and call the rollback function.
    Returns True if rollback succeeded, False otherwise.
    """
    try:
        mod = __import__(rollback_module, fromlist=[rollback_func])
        func = getattr(mod, rollback_func)
        func(capability_id, module_path)
        return True
    except Exception as e:
        # If rollback itself fails, we log but do not crash
        print(f"WARNING: Rollback failed for capability {capability_id}, module {module_path}: {e}", file=sys.stderr)
        return False


# ---------------------------------------------------------------------------
# Main integration function
# ---------------------------------------------------------------------------
def integrate_grounding_test(capability_id: str,
                              capability_description: str,
                              log_dir: str = DEFAULT_LOG_DIR,
                              test_registry_dir: str = DEFAULT_TEST_REGISTRY_DIR,
                              rollback_module: str = DEFAULT_ROLLBACK_MODULE,
                              rollback_func: str = DEFAULT_ROLLBACK_FUNC,
                              quality_gate_log: str = DEFAULT_QUALITY_GATE_LOG) -> Dict[str, any]:
    """
    Main entry point: after a capability is accepted, this function:
      1. Parses the capability description to identify affected modules.
      2. For each affected module, generates a minimal assert-based unit test.
      3. Runs the test using subprocess.
      4. On failure, reverts the capability (calls rollback) and logs failure.
      5. On success, registers the test in the test registry.
    Returns a dict with keys:
      - 'success': bool (True if all tests passed)
      - 'results': list of dicts per module with module, passed, output
      - 'rollback_called': bool
    """
    affected_modules = parse_affected_modules(capability_description)
    if not affected_modules:
        # If no modules identified, treat as success (nothing to test)
        return {
            "success": True,
            "results": [],
            "rollback_called": False,
            "message": "No affected modules identified in capability description."
        }

    results = []
    all_passed = True
    rollback_called = False

    for module_path in affected_modules:
        # Step 2: Generate test
        test_source = generate_minimal_test(module_path)

        # Step 3: Run test
        passed, output = run_test_via_subprocess(test_source, module_path)

        if passed:
            # Step 5: Register test
            register_test_in_registry(module_path, test_source, test_registry_dir)
            results.append({
                "module": module_path,
                "passed": True,
                "output": output
            })
        else:
            all_passed = False
            # Step 4: Log failure
            log_failure_to_quality_gate(module_path, output, log_dir, quality_gate_log)
            # Step 4: Revert capability
            rollback_ok = call_rollback(capability_id, module_path, rollback_module, rollback_func)
            if rollback_ok:
                rollback_called = True
            results.append({
                "module": module_path,
                "passed": False,
                "output": output,
                "rollback_attempted": rollback_ok
            })

    return {
        "success": all_passed,
        "results": results,
        "rollback_called": rollback_called,
        "capability_id": capability_id,
        "modules_tested": len(affected_modules)
    }


# ---------------------------------------------------------------------------
# Convenience function for one-shot testing
# ---------------------------------------------------------------------------
def test_integration(capability_id: str, capability_description: str) -> Dict[str, any]:
    """Wrapper that uses default settings for quick testing."""
    return integrate_grounding_test(capability_id, capability_description)


# ---------------------------------------------------------------------------
# If run as script, demonstrate usage
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    # Example capability description
    example_desc = """
    Capability: Add logging to core module
    file: core/ecology_core.py
    module: core.nash_detector_and_forcer
    Also modifies: "core/mutation_quality_gate.py"
    """
    result = test_integration("demo_cap_001", example_desc)
    print("Integration result:", result)