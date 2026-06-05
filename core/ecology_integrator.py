"""Ecology system coordinator module.

Provides the top-level orchestration for the ecology-driven test generation
and selection pipeline.  Coordinates benchmark generation, environmental
pressure creation, validation, and fitness landscape evolution.
"""

import logging
import subprocess
import sys
from collections import deque
from typing import Dict, List, Optional, Tuple

from core.ecology_engine import generate_benchmark, mutate_test_suite
from core.environmental_pressure import create_environmental_pressure

logger = logging.getLogger(__name__)

# Rolling window of last 10 generated test file paths (to prevent duplication)
_generated_test_window: deque = deque(maxlen=10)


def run_ecology_cycle(
    test_suite_path: str,
    output_dir: str,
    pressure_params: Optional[Dict] = None,
) -> Tuple[List[str], List[str]]:
    """Execute one full ecology cycle: benchmark generation + environmental pressure.

    Args:
        test_suite_path: Path to the current test suite file.
        output_dir: Directory where generated test files will be written.
        pressure_params: Optional dict of parameters for environmental pressure creation.

    Returns:
        A tuple (benchmark_files, pressure_files) listing the paths of newly
        generated benchmark and pressure test files.
    """
    logger.info("Starting ecology cycle: benchmark generation")
    benchmark_files = generate_benchmark(test_suite_path, output_dir)

    logger.info("Starting ecology cycle: environmental pressure creation")
    pressure_files = create_environmental_pressure(
        test_suite_path, output_dir, **(pressure_params or {})
    )

    # Track generated files in rolling window
    for f in benchmark_files + pressure_files:
        _generated_test_window.append(f)

    logger.info(
        "Ecology cycle complete: %d benchmarks, %d pressure files",
        len(benchmark_files),
        len(pressure_files),
    )
    return benchmark_files, pressure_files


def validate_new_tests(test_files: List[str]) -> Dict[str, bool]:
    """Run each test file in isolation and report pass/fail.

    Args:
        test_files: List of paths to test files to validate.

    Returns:
        A dict mapping each test file path to a boolean: True if the test
        passed (exit code 0), False otherwise.
    """
    results: Dict[str, bool] = {}
    for test_file in test_files:
        logger.info("Validating test file: %s", test_file)
        try:
            completed = subprocess.run(
                [sys.executable, "-m", "pytest", test_file, "--quiet", "--tb=short"],
                capture_output=True,
                text=True,
                timeout=120,
            )
            passed = completed.returncode == 0
            if not passed:
                logger.warning(
                    "Test %s failed:\n%s", test_file, completed.stderr[:500]
                )
            results[test_file] = passed
        except subprocess.TimeoutExpired:
            logger.warning("Test %s timed out after 120s", test_file)
            results[test_file] = False
        except Exception as exc:
            logger.error("Error validating %s: %s", test_file, exc)
            results[test_file] = False
    return results


def evolve_fitness_landscape(
    test_files: List[str],
    validation_results: Dict[str, bool],
    active_test_suite_path: str,
    max_new_tests: int = 5,
) -> int:
    """Select the most challenging valid tests and add them to the active suite.

    "Challenging" is defined heuristically: tests that passed but had longer
    execution times or more assertions are preferred.  This function also
    filters out any test file that already exists in the rolling window to
    prevent duplication.

    Args:
        test_files: List of candidate test file paths.
        validation_results: Dict mapping test file -> passed (bool).
        active_test_suite_path: Path to the active test suite file to mutate.
        max_new_tests: Maximum number of new tests to add (default 5).

    Returns:
        The number of tests actually added to the active suite.
    """
    # Gather passing tests not already in the rolling window
    candidates = [
        f
        for f in test_files
        if validation_results.get(f, False) and f not in _generated_test_window
    ]

    if not candidates:
        logger.info("No new valid tests to add to fitness landscape.")
        return 0

    # Heuristic: prefer tests with longer names as a proxy for complexity
    # (in a real system you'd measure execution time or assertion count)
    candidates.sort(key=lambda x: len(x), reverse=True)

    selected = candidates[:max_new_tests]
    logger.info("Evolving fitness landscape: adding %d tests", len(selected))

    # Add selected tests to the active suite via mutation
    mutate_test_suite(active_test_suite_path, selected)

    # Update rolling window to include selected tests
    for f in selected:
        _generated_test_window.append(f)

    return len(selected)


def get_generated_test_window() -> List[str]:
    """Return a copy of the current rolling window of generated tests."""
    return list(_generated_test_window)


def clear_generated_test_window() -> None:
    """Clear the rolling window (useful for testing)."""
    _generated_test_window.clear()