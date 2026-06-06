"""
Ecology Integration Module

Connects the ecology engine to the evolution loop, providing cycle management,
metrics tracking, and automatic triggering to prevent stagnation.
"""

from ecology_engine import (
    evolve_test_suite,
    get_ecology_state,
    get_test_difficulty,
    reset_ecology_state
)
from typing import Dict, List, Optional, Tuple
import time
import logging

logger = logging.getLogger(__name__)


def run_ecology_cycle() -> Dict[str, any]:
    """
    Run a complete ecology cycle:
    1. Evolve the test suite
    2. Run the new tests
    3. Return results
    
    Returns:
        Dict containing cycle results with keys:
        - new_tests_added: int
        - pass_rate: float
        - difficulty_curve: List[float]
        - cycle_duration: float
    """
    start_time = time.time()
    
    try:
        # Evolve the test suite
        evolution_result = evolve_test_suite()
        
        new_tests = evolution_result.get('new_tests', [])
        test_results = evolution_result.get('test_results', {})
        
        # Calculate metrics
        total_tests = len(new_tests)
        passed_tests = sum(1 for result in test_results.values() if result.get('passed', False))
        pass_rate = passed_tests / total_tests if total_tests > 0 else 0.0
        
        # Get difficulty curve
        difficulty_curve = get_test_difficulty()
        
        cycle_duration = time.time() - start_time
        
        result = {
            'new_tests_added': total_tests,
            'pass_rate': pass_rate,
            'difficulty_curve': difficulty_curve,
            'cycle_duration': cycle_duration,
            'success': True
        }
        
        logger.info(
            f"Ecology cycle completed: {total_tests} tests added, "
            f"pass rate: {pass_rate:.2%}, duration: {cycle_duration:.2f}s"
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Ecology cycle failed: {str(e)}")
        return {
            'new_tests_added': 0,
            'pass_rate': 0.0,
            'difficulty_curve': [],
            'cycle_duration': time.time() - start_time,
            'success': False,
            'error': str(e)
        }


def track_ecology_metrics(cycle_results: List[Dict[str, any]]) -> Dict[str, any]:
    """
    Track and aggregate ecology metrics over multiple cycles.
    
    Args:
        cycle_results: List of cycle result dictionaries from run_ecology_cycle()
        
    Returns:
        Dict containing aggregated metrics:
        - total_new_tests: int
        - average_pass_rate: float
        - difficulty_trend: List[float]
        - stagnation_score: float
        - cycles_completed: int
    """
    if not cycle_results:
        return {
            'total_new_tests': 0,
            'average_pass_rate': 0.0,
            'difficulty_trend': [],
            'stagnation_score': 0.0,
            'cycles_completed': 0
        }
    
    total_new_tests = sum(r.get('new_tests_added', 0) for r in cycle_results)
    pass_rates = [r.get('pass_rate', 0.0) for r in cycle_results if r.get('success', False)]
    average_pass_rate = sum(pass_rates) / len(pass_rates) if pass_rates else 0.0
    
    # Extract difficulty curves and flatten to trend
    difficulty_trend = []
    for r in cycle_results:
        curve = r.get('difficulty_curve', [])
        if curve:
            difficulty_trend.extend(curve)
    
    # Calculate stagnation score (0 = no stagnation, 1 = fully stagnant)
    stagnation_score = _calculate_stagnation_score(cycle_results)
    
    metrics = {
        'total_new_tests': total_new_tests,
        'average_pass_rate': average_pass_rate,
        'difficulty_trend': difficulty_trend,
        'stagnation_score': stagnation_score,
        'cycles_completed': len(cycle_results)
    }
    
    logger.info(
        f"Ecology metrics: {total_new_tests} total tests, "
        f"avg pass rate: {average_pass_rate:.2%}, "
        f"stagnation: {stagnation_score:.2%}"
    )
    
    return metrics


def _calculate_stagnation_score(cycle_results: List[Dict[str, any]]) -> float:
    """
    Calculate stagnation score based on recent cycle results.
    
    A higher score indicates more stagnation (fewer new tests, lower pass rates).
    
    Args:
        cycle_results: List of cycle result dictionaries
        
    Returns:
        Float between 0.0 and 1.0 indicating stagnation level
    """
    if len(cycle_results) < 3:
        return 0.0
    
    # Look at last 3 cycles
    recent_results = cycle_results[-3:]
    
    # Check if new tests are being added
    new_tests_counts = [r.get('new_tests_added', 0) for r in recent_results]
    if sum(new_tests_counts) == 0:
        return 1.0  # Fully stagnant
    
    # Check pass rate trends
    pass_rates = [r.get('pass_rate', 0.0) for r in recent_results if r.get('success', False)]
    if not pass_rates:
        return 0.8  # High stagnation if no successful cycles
    
    avg_pass_rate = sum(pass_rates) / len(pass_rates)
    
    # Combine factors
    test_factor = 1.0 - (sum(new_tests_counts) / (len(new_tests_counts) * 10))
    pass_factor = 1.0 - avg_pass_rate
    
    stagnation_score = (test_factor * 0.6) + (pass_factor * 0.4)
    
    return min(1.0, max(0.0, stagnation_score))


def auto_trigger_ecology(cycle_count: int, metrics: Dict[str, any]) -> bool:
    """
    Determine if ecology should be auto-triggered to prevent stagnation.
    
    Triggers every 5 cycles or when stagnation is detected.
    
    Args:
        cycle_count: Current cycle number in the evolution loop
        metrics: Current ecology metrics from track_ecology_metrics()
        
    Returns:
        True if ecology should be triggered, False otherwise
    """
    # Trigger every 5 cycles
    if cycle_count > 0 and cycle_count % 5 == 0:
        logger.info(f"Auto-triggering ecology at cycle {cycle_count}")
        return True
    
    # Trigger if stagnation is high
    stagnation_score = metrics.get('stagnation_score', 0.0)
    if stagnation_score > 0.7:
        logger.warning(
            f"High stagnation detected ({stagnation_score:.2%}), "
            f"triggering ecology cycle"
        )
        return True
    
    # Trigger if no new tests in last 3 cycles
    if metrics.get('total_new_tests', 0) == 0 and metrics.get('cycles_completed', 0) >= 3:
        logger.warning("No new tests added in recent cycles, triggering ecology")
        return True
    
    return False


def reset_ecology_integration() -> None:
    """
    Reset the ecology integration state.
    Useful for testing or restarting the ecology system.
    """
    try:
        reset_ecology_state()
        logger.info("Ecology integration state reset successfully")
    except Exception as e:
        logger.error(f"Failed to reset ecology integration state: {str(e)}")
        raise


def get_ecology_status() -> Dict[str, any]:
    """
    Get the current status of the ecology system.
    
    Returns:
        Dict containing current ecology state information
    """
    try:
        state = get_ecology_state()
        return {
            'active': state.get('active', False),
            'cycle_count': state.get('cycle_count', 0),
            'test_count': state.get('test_count', 0),
            'difficulty_level': state.get('difficulty_level', 0.0),
            'last_cycle_time': state.get('last_cycle_time', None)
        }
    except Exception as e:
        logger.error(f"Failed to get ecology status: {str(e)}")
        return {
            'active': False,
            'cycle_count': 0,
            'test_count': 0,
            'difficulty_level': 0.0,
            'last_cycle_time': None,
            'error': str(e)
        }