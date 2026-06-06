import os
import json
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime

# Internal imports
from core.error_log_collector import ErrorLogCollector
from core.failure_pattern_miner import FailurePatternMiner
from core.lessons_learned import LessonsLearnedDB

logger = logging.getLogger(__name__)

# Global instances (singleton-like for simplicity in the main loop)
_error_log_collector: Optional[ErrorLogCollector] = None
_failure_pattern_miner: Optional[FailurePatternMiner] = None
_lessons_db: Optional[LessonsLearnedDB] = None
_cycle_counter: int = 0

def initialize_evolution_loop(
    error_log_path: str = "data/error_logs.json",
    lessons_path: str = "data/lessons_learned.json",
    patterns_path: str = "data/failure_patterns.json"
) -> None:
    """Initialize the global components for the evolution loop."""
    global _error_log_collector, _failure_pattern_miner, _lessons_db, _cycle_counter

    _error_log_collector = ErrorLogCollector(log_file=error_log_path)
    _lessons_db = LessonsLearnedDB(db_path=lessons_path)
    _failure_pattern_miner = FailurePatternMiner(
        error_log_path=error_log_path,
        lessons_path=lessons_path,
        patterns_path=patterns_path
    )
    _cycle_counter = 0
    logger.info("Evolution loop initialized with failure_pattern_miner integration.")

def query_lessons_learned(module_name: str) -> List[Dict[str, Any]]:
    """
    Query the lessons_learned database for relevant fix suggestions
    related to the given module_name. Returns a list of suggestion dicts.
    """
    global _lessons_db
    if _lessons_db is None:
        logger.warning("LessonsLearnedDB not initialized. Returning empty suggestions.")
        return []

    try:
        suggestions = _lessons_db.query(module_name=module_name)
        logger.debug(f"Found {len(suggestions)} lesson suggestions for module '{module_name}'.")
        return suggestions
    except Exception as e:
        logger.error(f"Failed to query lessons_learned for '{module_name}': {e}")
        return []

def log_mutation_outcome(
    module_name: str,
    mutation_id: str,
    success: bool,
    error_message: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> None:
    """
    Log the outcome of a mutation attempt to the error_log_collector.
    This feeds the failure_pattern_miner with data for pattern discovery.
    """
    global _error_log_collector
    if _error_log_collector is None:
        logger.warning("ErrorLogCollector not initialized. Skipping outcome logging.")
        return

    log_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "module_name": module_name,
        "mutation_id": mutation_id,
        "success": success,
        "error_message": error_message,
        "metadata": metadata or {}
    }

    try:
        _error_log_collector.log_event(log_entry)
        logger.debug(f"Logged mutation outcome for {module_name} (id={mutation_id}, success={success}).")
    except Exception as e:
        logger.error(f"Failed to log mutation outcome: {e}")

def run_periodic_mining() -> None:
    """
    Every 10 cycles, invoke the failure_pattern_miner to update
    lessons_learned.json with newly discovered patterns.
    """
    global _cycle_counter, _failure_pattern_miner

    _cycle_counter += 1
    if _cycle_counter % 10 != 0:
        return

    if _failure_pattern_miner is None:
        logger.warning("FailurePatternMiner not initialized. Skipping periodic mining.")
        return

    try:
        logger.info(f"Cycle {_cycle_counter}: Running failure pattern mining...")
        _failure_pattern_miner.run()
        logger.info("Failure pattern mining completed successfully.")
    except Exception as e:
        logger.error(f"Failure pattern mining failed at cycle {_cycle_counter}: {e}")

def before_mutation_hook(module_name: str) -> List[Dict[str, Any]]:
    """
    Hook to be called before each mutation. Returns relevant lesson suggestions
    that can be injected into the mutation prompt.
    """
    suggestions = query_lessons_learned(module_name)
    if suggestions:
        logger.info(f"Found {len(suggestions)} relevant lessons for '{module_name}'. Injecting into prompt.")
    return suggestions

def after_mutation_hook(
    module_name: str,
    mutation_id: str,
    success: bool,
    error_message: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> None:
    """
    Hook to be called after each mutation attempt. Logs the outcome and
    triggers periodic mining if needed.
    """
    log_mutation_outcome(module_name, mutation_id, success, error_message, metadata)
    run_periodic_mining()

# Convenience function to reset the cycle counter (useful for testing or manual reset)
def reset_cycle_counter() -> None:
    global _cycle_counter
    _cycle_counter = 0
    logger.info("Evolution loop cycle counter reset to 0.")