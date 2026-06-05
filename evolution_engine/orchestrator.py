"""Orchestrator module for managing the evolution engine's main loop."""

import os
import sys
import subprocess
from pathlib import Path

# Global flag indicating whether primitive validation has failed
PRIMITIVE_VALIDATION_FAILED = False

PRIMITIVE_TEST_PATH = Path("tests/test_new_file_creation_metamorphic.py")


def check_primitive_validation() -> None:
    """
    Check if the primitive test file exists and passes.
    If not, log the error and set the global flag.
    """
    global PRIMITIVE_VALIDATION_FAILED

    if not PRIMITIVE_TEST_PATH.exists():
        print(
            f"ERROR: Primitive test file not found: {PRIMITIVE_TEST_PATH}",
            file=sys.stderr
        )
        PRIMITIVE_VALIDATION_FAILED = True
        return

    try:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", str(PRIMITIVE_TEST_PATH), "-x", "--tb=short"],
            capture_output=True,
            text=True,
            timeout=60
        )
        if result.returncode != 0:
            print(
                f"ERROR: Primitive test failed: {PRIMITIVE_TEST_PATH}\n"
                f"STDOUT: {result.stdout}\n"
                f"STDERR: {result.stderr}",
                file=sys.stderr
            )
            PRIMITIVE_VALIDATION_FAILED = True
        else:
            PRIMITIVE_VALIDATION_FAILED = False
    except subprocess.TimeoutExpired:
        print(
            f"ERROR: Primitive test timed out: {PRIMITIVE_TEST_PATH}",
            file=sys.stderr
        )
        PRIMITIVE_VALIDATION_FAILED = True
    except Exception as e:
        print(
            f"ERROR: Unexpected error running primitive test: {e}",
            file=sys.stderr
        )
        PRIMITIVE_VALIDATION_FAILED = True


def run_evolution_loop() -> None:
    """
    Main evolution loop that checks primitive validation before proceeding.
    """
    global PRIMITIVE_VALIDATION_FAILED

    # Initial validation check
    check_primitive_validation()

    while True:
        if PRIMITIVE_VALIDATION_FAILED:
            print(
                "ABORT: Higher-level integration goals cannot proceed because "
                "primitive validation has failed. Please ensure "
                f"'{PRIMITIVE_TEST_PATH}' exists and passes all tests.",
                file=sys.stderr
            )
            # Optionally, wait and retry periodically
            import time
            time.sleep(10)
            check_primitive_validation()
            continue

        # Main evolution logic goes here
        # (placeholder for actual evolution processing)
        print("Primitive validation passed. Running evolution loop...")
        break  # Remove this break when implementing actual loop logic


if __name__ == "__main__":
    run_evolution_loop()