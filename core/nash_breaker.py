"""Nash Breaker - Forced multi-module mutation when Nash equilibrium is detected."""

from typing import Any, Dict, List, Optional
from core.nash_detector import NashEquilibriumDetector


def force_multi_module_change(
    detector: NashEquilibriumDetector,
    orchestrator: Any,
    min_modules: int = 2,
    max_modules: int = 5,
) -> Optional[Dict[str, Any]]:
    """Detect Nash equilibrium and force a multi-module mutation to break it.

    Args:
        detector: An initialized NashEquilibriumDetector instance.
        orchestrator: The evolution orchestrator with a pending_mutations queue.
        min_modules: Minimum number of modules to include in the mutation.
        max_modules: Maximum number of modules to include in the mutation.

    Returns:
        The mutation plan dict if submitted, None if no equilibrium detected.
    """
    equilibrium_state = detector.detect_equilibrium()
    if not equilibrium_state or not equilibrium_state.get("in_equilibrium"):
        return None

    modules_in_equilibrium = equilibrium_state.get("modules", [])
    if len(modules_in_equilibrium) < min_modules:
        return None

    # Select a subset of modules to mutate (at least min_modules, at most max_modules)
    selected_modules = modules_in_equilibrium[:max_modules]
    if len(selected_modules) < min_modules:
        selected_modules = modules_in_equilibrium[:min_modules]

    # Build a coordinated mutation plan affecting all selected modules
    mutation_plan = {
        "type": "coordinated_multi_module",
        "modules": selected_modules,
        "reason": f"Forced break of Nash equilibrium involving {len(selected_modules)} modules",
        "mutations": [],
    }

    for module_name in selected_modules:
        mutation_plan["mutations"].append(
            {
                "module": module_name,
                "action": "modify",
                "parameters": {
                    "strategy_shift": True,
                    "target": "core_strategy",
                },
            }
        )

    # Submit to orchestrator's pending mutations queue
    if hasattr(orchestrator, "pending_mutations") and isinstance(
        orchestrator.pending_mutations, list
    ):
        orchestrator.pending_mutations.append(mutation_plan)
        return mutation_plan

    return None