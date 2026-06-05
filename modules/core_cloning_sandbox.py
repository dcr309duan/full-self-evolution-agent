"""Core cloning sandbox module for safe experimentation with the evolution orchestrator."""

import copy
import json
import os
import subprocess
import sys
import tempfile
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

# ---------------------------------------------------------------------------
# 1. serialize_state
# ---------------------------------------------------------------------------

def serialize_state(
    evolution_orchestrator: Any,
    mutation_engine: Any,
    goal_generator: Any,
) -> Dict[str, Any]:
    """Deep-copy the three core objects and return a serializable dictionary.

    The dictionary contains:
        - 'orchestrator': state, config, and loaded modules (if available)
        - 'mutation_engine': state, config, and loaded modules
        - 'goal_generator': state, config, and loaded modules
        - 'timestamp': ISO format timestamp
        - 'session_id': unique identifier for this sandbox session
    """
    # Deep copy to avoid mutating originals
    orch_copy = copy.deepcopy(evolution_orchestrator)
    mut_copy = copy.deepcopy(mutation_engine)
    goal_copy = copy.deepcopy(goal_generator)

    def _to_dict(obj: Any) -> Dict[str, Any]:
        """Convert an object to a dict, preferring __dict__ or a to_dict method."""
        if hasattr(obj, "to_dict") and callable(obj.to_dict):
            return obj.to_dict()
        if hasattr(obj, "__dict__"):
            return obj.__dict__
        # Fallback: try to convert via json if possible
        try:
            json.dumps(obj)
            return {"value": obj}
        except (TypeError, ValueError):
            return {"raw": str(obj)}

    serialized = {
        "session_id": str(uuid.uuid4()),
        "timestamp": datetime.utcnow().isoformat(),
        "orchestrator": {
            "state": _to_dict(orch_copy),
            "config": _to_dict(getattr(orch_copy, "config", {})),
            "loaded_modules": _to_dict(getattr(orch_copy, "loaded_modules", [])),
        },
        "mutation_engine": {
            "state": _to_dict(mut_copy),
            "config": _to_dict(getattr(mut_copy, "config", {})),
            "loaded_modules": _to_dict(getattr(mut_copy, "loaded_modules", [])),
        },
        "goal_generator": {
            "state": _to_dict(goal_copy),
            "config": _to_dict(getattr(goal_copy, "config", {})),
            "loaded_modules": _to_dict(getattr(goal_copy, "loaded_modules", [])),
        },
    }
    return serialized


# ---------------------------------------------------------------------------
# 2. spawn_sandbox_subprocess
# ---------------------------------------------------------------------------

def spawn_sandbox_subprocess(
    serialized_state: Dict[str, Any],
    sandbox_runner_path: Optional[str] = None,
) -> subprocess.Popen:
    """Write serialized state to a temporary directory and spawn a sandbox runner.

    Args:
        serialized_state: Dictionary produced by serialize_state().
        sandbox_runner_path: Path to the sandbox runner script. If None, defaults
            to 'sandbox_runner.py' in the same directory as this module.

    Returns:
        subprocess.Popen handle to the spawned process.
    """
    # Create a temporary directory for sandbox artifacts
    sandbox_dir = tempfile.mkdtemp(prefix="core_cloning_sandbox_")
    state_path = os.path.join(sandbox_dir, "sandbox_state.json")

    # Write serialized state
    with open(state_path, "w") as f:
        json.dump(serialized_state, f, indent=2, default=str)

    # Determine runner path
    if sandbox_runner_path is None:
        sandbox_runner_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "sandbox_runner.py"
        )

    # Spawn the child process
    env = os.environ.copy()
    env["SANDBOX_STATE_PATH"] = state_path
    env["SANDBOX_DIR"] = sandbox_dir

    proc = subprocess.Popen(
        [sys.executable, sandbox_runner_path],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return proc


# ---------------------------------------------------------------------------
# 3. apply_mutation_to_orchestrator
# ---------------------------------------------------------------------------

def apply_mutation_to_orchestrator(
    orchestrator: Any,
    goal_selection_threshold: Optional[float] = None,
    mutation_acceptance_criteria: Optional[Dict[str, Any]] = None,
) -> Any:
    """Modify the orchestrator's decision logic in-place.

    Args:
        orchestrator: The evolution orchestrator object.
        goal_selection_threshold: New threshold for goal selection (if not None).
        mutation_acceptance_criteria: New criteria dict for mutation acceptance
            (if not None). Expected keys may include 'min_improvement', 'max_cost',
            etc.

    Returns:
        The modified orchestrator (same object, for chaining).
    """
    if goal_selection_threshold is not None:
        # Try common attribute names
        if hasattr(orchestrator, "goal_selection_threshold"):
            orchestrator.goal_selection_threshold = goal_selection_threshold
        elif hasattr(orchestrator, "config") and isinstance(orchestrator.config, dict):
            orchestrator.config["goal_selection_threshold"] = goal_selection_threshold
        elif hasattr(orchestrator, "config") and hasattr(orchestrator.config, "goal_selection_threshold"):
            orchestrator.config.goal_selection_threshold = goal_selection_threshold

    if mutation_acceptance_criteria is not None:
        if hasattr(orchestrator, "mutation_acceptance_criteria"):
            orchestrator.mutation_acceptance_criteria = mutation_acceptance_criteria
        elif hasattr(orchestrator, "config") and isinstance(orchestrator.config, dict):
            orchestrator.config["mutation_acceptance_criteria"] = mutation_acceptance_criteria
        elif hasattr(orchestrator, "config") and hasattr(orchestrator.config, "mutation_acceptance_criteria"):
            orchestrator.config.mutation_acceptance_criteria = mutation_acceptance_criteria

    return orchestrator


# ---------------------------------------------------------------------------
# 4. run_test_suite_in_sandbox
# ---------------------------------------------------------------------------

def run_test_suite_in_sandbox(
    tests_dir: str = "tests",
    timeout: Optional[int] = None,
    cwd: Optional[str] = None,
) -> Dict[str, Any]:
    """Execute all tests in the specified directory via subprocess.

    Args:
        tests_dir: Path to the tests directory (default 'tests').
        timeout: Timeout in seconds for the entire test run (optional).
        cwd: Working directory for the test process (default current dir).

    Returns:
        Dict with keys:
            - 'exit_code': int
            - 'stdout': str
            - 'stderr': str
            - 'timed_out': bool
    """
    if cwd is None:
        cwd = os.getcwd()

    # Discover test files (common patterns)
    test_patterns = ["test_*.py", "*_test.py"]
    test_files = []
    tests_path = Path(tests_dir)
    if tests_path.is_dir():
        for pattern in test_patterns:
            test_files.extend(sorted(tests_path.glob(pattern)))

    if not test_files:
        return {
            "exit_code": 0,
            "stdout": "",
            "stderr": "No test files found in '{}'.".format(tests_dir),
            "timed_out": False,
        }

    # Build command: run all discovered test files with pytest or unittest
    # Prefer pytest if available, else fallback to python -m unittest
    try:
        subprocess.run(
            [sys.executable, "-m", "pytest", "--version"],
            capture_output=True,
            check=True,
        )
        cmd = [sys.executable, "-m", "pytest"] + [str(f) for f in test_files]
    except (subprocess.CalledProcessError, FileNotFoundError):
        cmd = [sys.executable, "-m", "unittest"] + [str(f) for f in test_files]

    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        timed_out = False
    except subprocess.TimeoutExpired as e:
        result = e
        timed_out = True

    return {
        "exit_code": getattr(result, "returncode", -1),
        "stdout": getattr(result, "stdout", ""),
        "stderr": getattr(result, "stderr", ""),
        "timed_out": timed_out,
    }


# ---------------------------------------------------------------------------
# 5. promote_or_discard
# ---------------------------------------------------------------------------

def promote_or_discard(
    sandbox_dir: str,
    action: str = "discard",
    target_orchestrator: Optional[Any] = None,
    sandbox_state: Optional[Dict[str, Any]] = None,
) -> bool:
    """Either merge sandbox changes back or discard the sandbox.

    Args:
        sandbox_dir: Path to the sandbox temporary directory.
        action: 'promote' to merge changes, 'discard' to delete sandbox.
        target_orchestrator: If promoting, the orchestrator to update.
        sandbox_state: If promoting, the serialized state from the sandbox.

    Returns:
        True if successful, False otherwise.
    """
    if action == "promote":
        if target_orchestrator is None or sandbox_state is None:
            raise ValueError("target_orchestrator and sandbox_state required for promotion.")
        # Merge: update target orchestrator with sandbox state
        try:
            # Simple merge: update top-level attributes
            for key, value in sandbox_state.get("orchestrator", {}).items():
                if hasattr(target_orchestrator, key):
                    setattr(target_orchestrator, key, value)
                elif hasattr(target_orchestrator, "config") and isinstance(target_orchestrator.config, dict):
                    target_orchestrator.config[key] = value
            # Clean up sandbox dir after promotion
            _cleanup_sandbox(sandbox_dir)
            return True
        except Exception:
            return False

    elif action == "discard":
        try:
            _cleanup_sandbox(sandbox_dir)
            return True
        except Exception:
            return False
    else:
        raise ValueError("action must be 'promote' or 'discard'.")


def _cleanup_sandbox(sandbox_dir: str) -> None:
    """Remove the sandbox directory and all its contents."""
    import shutil
    if os.path.isdir(sandbox_dir):
        shutil.rmtree(sandbox_dir)


# ---------------------------------------------------------------------------
# 6. log_outcome
# ---------------------------------------------------------------------------

def log_outcome(
    outcome: str,
    mutation_details: Dict[str, Any],
    test_results: Dict[str, Any],
    errors: Optional[str] = None,
    log_file: str = "sandbox_outcomes.log",
) -> None:
    """Record the outcome of a sandbox experiment to a structured log file.

    Args:
        outcome: 'pass' or 'fail'.
        mutation_details: Dict describing the mutation applied.
        test_results: Dict from run_test_suite_in_sandbox().
        errors: Optional error string.
        log_file: Path to the log file (default 'sandbox_outcomes.log').
    """
    log_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "outcome": outcome,
        "mutation_details": mutation_details,
        "test_results": {
            "exit_code": test_results.get("exit_code"),
            "stdout": test_results.get("stdout", ""),
            "stderr": test_results.get("stderr", ""),
            "timed_out": test_results.get("timed_out", False),
        },
        "errors": errors or "",
    }

    # Append to log file as JSON lines
    with open(log_file, "a") as f:
        f.write(json.dumps(log_entry, default=str) + "\n")