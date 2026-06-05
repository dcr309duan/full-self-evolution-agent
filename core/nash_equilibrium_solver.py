"""Self-contained Nash Equilibrium Solver module.

Tracks module interaction success rates over a sliding window,
detects Nash equilibria, and generates coordinated multi-module mutation plans.
"""

import random
from collections import deque
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
SLIDING_WINDOW_SIZE = 20
NASH_CONSECUTIVE_THRESHOLD = 5
MUTATION_PLAN_SIZE_MIN = 2
MUTATION_PLAN_SIZE_MAX = 3
FALLBACK_PERTURBATION_COUNT = 3

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------
InteractionRecord = Dict[str, Any]  # e.g. {"module": str, "success": bool, "timestamp": int}

# ---------------------------------------------------------------------------
# Module-level state
# ---------------------------------------------------------------------------
_interaction_history: deque = deque(maxlen=SLIDING_WINDOW_SIZE)
_module_success_rates: Dict[str, float] = {}
_nash_detected: bool = False
_consecutive_no_improvement: int = 0
_last_best_rate: float = 0.0

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def record_interaction(module_name: str, success: bool, timestamp: Optional[int] = None) -> None:
    """Record a module interaction outcome into the sliding window."""
    record: InteractionRecord = {
        "module": module_name,
        "success": success,
        "timestamp": timestamp if timestamp is not None else len(_interaction_history)
    }
    _interaction_history.append(record)
    _recompute_rates()


def get_module_success_rates() -> Dict[str, float]:
    """Return a copy of current per-module success rates."""
    return dict(_module_success_rates)


def is_nash_equilibrium() -> bool:
    """Return True if the system is currently in a Nash equilibrium state."""
    return _nash_detected


def detect_nash_equilibrium() -> bool:
    """Run detection logic and update internal Nash flag.

    Returns:
        True if Nash equilibrium is detected, False otherwise.
    """
    global _nash_detected, _consecutive_no_improvement, _last_best_rate

    if not _module_success_rates:
        _nash_detected = False
        return False

    current_best = max(_module_success_rates.values())

    if current_best <= _last_best_rate:
        _consecutive_no_improvement += 1
    else:
        _consecutive_no_improvement = 0
        _last_best_rate = current_best

    if _consecutive_no_improvement >= NASH_CONSECUTIVE_THRESHOLD:
        _nash_detected = True
    else:
        _nash_detected = False

    return _nash_detected


def generate_mutation_plan() -> List[Dict[str, Any]]:
    """Generate a coordinated multi-module mutation plan.

    Returns:
        A list of mutation actions, each a dict with keys:
            - "modules": list of module names to mutate
            - "type": "analytical" or "fallback"
            - "description": human-readable explanation
    """
    plans: List[Dict[str, Any]] = []

    if not _module_success_rates:
        # No data – fallback
        return _fallback_plan()

    # Attempt analytical plan: pick 2-3 modules with lowest success rates
    sorted_modules = sorted(_module_success_rates.items(), key=lambda x: x[1])
    low_performers = [m for m, r in sorted_modules if r < 0.5]

    if len(low_performers) >= MUTATION_PLAN_SIZE_MIN:
        # Analytical plan: mutate the worst-performing interdependent modules
        plan_size = min(len(low_performers), MUTATION_PLAN_SIZE_MAX)
        selected = low_performers[:plan_size]
        plans.append({
            "modules": selected,
            "type": "analytical",
            "description": f"Coordinated mutation of low-success modules: {', '.join(selected)}"
        })
    else:
        # Fallback to random perturbation
        plans = _fallback_plan()

    return plans


def reset() -> None:
    """Reset all internal state (useful for testing or fresh start)."""
    global _interaction_history, _module_success_rates
    global _nash_detected, _consecutive_no_improvement, _last_best_rate

    _interaction_history.clear()
    _module_success_rates.clear()
    _nash_detected = False
    _consecutive_no_improvement = 0
    _last_best_rate = 0.0


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _recompute_rates() -> None:
    """Recompute per-module success rates from the sliding window."""
    global _module_success_rates

    counts: Dict[str, Tuple[int, int]] = {}  # module -> (successes, total)

    for record in _interaction_history:
        mod = record["module"]
        success = record["success"]
        if mod not in counts:
            counts[mod] = [0, 0]
        counts[mod][0] += 1 if success else 0
        counts[mod][1] += 1

    rates: Dict[str, float] = {}
    for mod, (succ, total) in counts.items():
        rates[mod] = succ / total if total > 0 else 0.0

    _module_success_rates = rates


def _fallback_plan() -> List[Dict[str, Any]]:
    """Generate a fallback random multi-module perturbation plan."""
    modules = list(_module_success_rates.keys())
    if not modules:
        # No known modules – return empty plan
        return []

    plans: List[Dict[str, Any]] = []
    for _ in range(FALLBACK_PERTURBATION_COUNT):
        k = random.randint(MUTATION_PLAN_SIZE_MIN, MUTATION_PLAN_SIZE_MAX)
        selected = random.sample(modules, min(k, len(modules)))
        plans.append({
            "modules": selected,
            "type": "fallback",
            "description": f"Random perturbation of modules: {', '.join(selected)}"
        })
    return plans