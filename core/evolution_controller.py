import os
import logging
from datetime import datetime
from typing import Optional, Dict, Any
from core import mutation_sandbox

# Configure sandbox rejection logger
REJECTION_LOG_DIR = "logs"
REJECTION_LOG_FILE = os.path.join(REJECTION_LOG_DIR, "sandbox_rejections.log")

os.makedirs(REJECTION_LOG_DIR, exist_ok=True)

rejection_logger = logging.getLogger("sandbox_rejections")
rejection_logger.setLevel(logging.WARNING)
rejection_handler = logging.FileHandler(REJECTION_LOG_FILE)
rejection_handler.setFormatter(logging.Formatter("%(asctime)s - %(message)s"))
rejection_logger.addHandler(rejection_handler)

# Track sandbox pass/fail counts per module for adaptive validation
_module_stats: Dict[str, Dict[str, int]] = {}  # module_name -> {"pass": int, "fail": int, "count": int}
_module_skip_counter: Dict[str, int] = {}  # module_name -> skip counter for every 3rd mutation

PASS_THRESHOLD = 0.9  # 90% pass rate required to reduce validation frequency
MIN_SAMPLES = 10  # minimum samples before adaptive reduction kicks in
VALIDATION_INTERVAL = 3  # validate every 3rd mutation when pass rate > 90%


def _get_module_name(target_file: str) -> str:
    """Extract a module name from the target file path."""
    # Normalize path separators and remove extension
    normalized = target_file.replace("\\", "/").replace(".py", "")
    # Use the last meaningful part as module name
    parts = normalized.split("/")
    return parts[-1] if parts else normalized


def _should_validate(module_name: str) -> bool:
    """Determine if validation should run based on historical pass rate."""
    stats = _module_stats.get(module_name, {"pass": 0, "fail": 0, "count": 0})
    
    # Always validate if we don't have enough samples
    if stats["count"] < MIN_SAMPLES:
        return True
    
    # Calculate pass rate
    pass_rate = stats["pass"] / stats["count"] if stats["count"] > 0 else 0.0
    
    # If pass rate is above threshold, use adaptive validation
    if pass_rate > PASS_THRESHOLD:
        skip_counter = _module_skip_counter.get(module_name, 0)
        _module_skip_counter[module_name] = (skip_counter + 1) % VALIDATION_INTERVAL
        # Only validate every VALIDATION_INTERVAL-th mutation
        return skip_counter == 0
    
    # Always validate if pass rate is below threshold
    return True


def _update_stats(module_name: str, passed: bool) -> None:
    """Update pass/fail statistics for a module."""
    if module_name not in _module_stats:
        _module_stats[module_name] = {"pass": 0, "fail": 0, "count": 0}
    
    _module_stats[module_name]["count"] += 1
    if passed:
        _module_stats[module_name]["pass"] += 1
    else:
        _module_stats[module_name]["fail"] += 1


def _log_rejection(target_file: str, error: str) -> None:
    """Log a sandbox rejection with timestamp, target file, and error."""
    rejection_logger.warning(f"TARGET_FILE: {target_file} | ERROR: {error}")


def validate_mutation(target_file: str, proposed_code: str, context: Optional[Dict[str, Any]] = None) -> bool:
    """
    Validate a proposed mutation using the sandbox.
    
    Args:
        target_file: Path to the file being mutated
        proposed_code: The proposed new code content
        context: Optional dictionary with additional context (e.g., original_code, mutation_type)
    
    Returns:
        True if validation passes (or skipped), False if rejected
    """
    module_name = _get_module_name(target_file)
    
    # Check if we should skip validation for performance
    if not _should_validate(module_name):
        logging.debug(f"Skipping sandbox validation for {target_file} (adaptive optimization)")
        return True
    
    # Perform sandbox validation
    try:
        result = mutation_sandbox.validate(target_file, proposed_code, context)
        
        if result.get("valid", False):
            _update_stats(module_name, passed=True)
            return True
        else:
            error_msg = result.get("error", "Unknown validation error")
            _update_stats(module_name, passed=False)
            _log_rejection(target_file, error_msg)
            return False
            
    except Exception as e:
        error_msg = f"Sandbox validation exception: {str(e)}"
        logging.error(f"Sandbox validation failed for {target_file}: {error_msg}")
        _update_stats(module_name, passed=False)
        _log_rejection(target_file, error_msg)
        return False


def reset_stats() -> None:
    """Reset all module statistics and skip counters (useful for testing)."""
    global _module_stats, _module_skip_counter
    _module_stats.clear()
    _module_skip_counter.clear()
    logging.info("Sandbox validation statistics reset")


def get_module_stats(module_name: Optional[str] = None) -> Dict[str, Any]:
    """
    Get sandbox validation statistics for one or all modules.
    
    Args:
        module_name: Optional specific module name. If None, returns all stats.
    
    Returns:
        Dictionary with pass/fail counts and pass rate
    """
    if module_name:
        stats = _module_stats.get(module_name, {"pass": 0, "fail": 0, "count": 0})
        pass_rate = stats["pass"] / stats["count"] if stats["count"] > 0 else 0.0
        return {
            "module": module_name,
            "pass": stats["pass"],
            "fail": stats["fail"],
            "total": stats["count"],
            "pass_rate": round(pass_rate, 4)
        }
    else:
        result = {}
        for mod, stats in _module_stats.items():
            pass_rate = stats["pass"] / stats["count"] if stats["count"] > 0 else 0.0
            result[mod] = {
                "pass": stats["pass"],
                "fail": stats["fail"],
                "total": stats["count"],
                "pass_rate": round(pass_rate, 4)
            }
        return result