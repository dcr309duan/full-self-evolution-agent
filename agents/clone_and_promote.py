"""Clone-and-promote safety mechanism for mutations.

Before applying any mutation to the live codebase, creates an isolated copy,
applies the mutation there, runs integration tests, and only promotes on success.
"""

import ast
import os
import shutil
import tempfile
import importlib
import sys
import logging
from typing import Callable, Optional, Any, Dict

logger = logging.getLogger(__name__)

_failure_counters: Dict[str, int] = {}


def get_failure_stats() -> Dict[str, int]:
    return dict(_failure_counters)


def safe_mutate(
    module_path: str,
    mutation_function: Callable,
    mutation_strategy_name: str,
    test_runner: Optional[Callable] = None,
) -> Optional[Any]:
    """Apply mutation safely using clone-and-promote pattern.

    1. Deep-copy target module to temp directory
    2. Apply mutation to the copy
    3. Validate the mutated copy (AST parse + optional test suite)
    4. If valid, promote copy to live location
    5. If invalid, discard copy, log failure, increment counter
    """
    if not os.path.isfile(module_path):
        logger.error(f"Module not found: {module_path}")
        return None

    workdir = tempfile.mkdtemp(prefix="mutation_sandbox_")
    basename = os.path.basename(module_path)
    copy_path = os.path.join(workdir, basename)

    try:
        shutil.copy2(module_path, copy_path)

        result = mutation_function(copy_path)

        with open(copy_path, 'r') as f:
            source = f.read()
        try:
            ast.parse(source)
        except SyntaxError as e:
            logger.warning(f"Mutation produced invalid syntax: {e}")
            _increment_failure(mutation_strategy_name)
            return None

        if test_runner:
            test_result = test_runner(copy_path)
            if not test_result:
                logger.warning(f"Integration tests failed for mutation '{mutation_strategy_name}'")
                _increment_failure(mutation_strategy_name)
                return None

        shutil.copy2(copy_path, module_path)
        logger.info(f"Mutation '{mutation_strategy_name}' promoted successfully")
        return result

    except Exception as e:
        logger.error(f"Clone-and-promote failed: {e}")
        _increment_failure(mutation_strategy_name)
        return None
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def _increment_failure(strategy_name: str) -> None:
    _failure_counters[strategy_name] = _failure_counters.get(strategy_name, 0) + 1
    logger.info(f"Failure counter for '{strategy_name}': {_failure_counters[strategy_name]}")
