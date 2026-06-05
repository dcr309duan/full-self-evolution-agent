from typing import List, Tuple, Set, Dict, Any
from dataclasses import dataclass, field
import math

@dataclass
class ModuleMetrics:
    """Represents performance metrics for a single module."""
    success_rate: float  # 0.0 to 1.0
    error_count: int     # non-negative integer
    name: str = ""

@dataclass
class EquilibriumResult:
    """Result of Nash equilibrium check."""
    is_equilibrium: bool
    stuck_modules: Set[str]
    improvement_potential: Dict[str, float] = field(default_factory=dict)

def _compute_improvement_potential(metrics: ModuleMetrics, system_avg_success: float, 
                                   system_avg_errors: float) -> float:
    """
    Compute a heuristic improvement potential for a single module.
    Returns a positive value if improving this module would likely help the system.
    Uses a weighted combination of success rate deficit and error rate excess.
    """
    # Success rate deficit (how far below system average)
    success_deficit = max(0.0, system_avg_success - metrics.success_rate)
    
    # Error rate excess (how far above system average)
    # Normalize error count to a rate relative to a baseline (e.g., max 100 errors)
    error_rate = min(1.0, metrics.error_count / 100.0)
    system_error_rate = min(1.0, system_avg_errors / 100.0)
    error_excess = max(0.0, error_rate - system_error_rate)
    
    # Weighted combination: success deficit is more important (weight 0.7)
    improvement = 0.7 * success_deficit + 0.3 * error_excess
    return improvement

def _compute_system_averages(metrics_list: List[ModuleMetrics]) -> Tuple[float, float]:
    """Compute average success rate and average error count across all modules."""
    if not metrics_list:
        return 0.0, 0.0
    
    total_success = sum(m.success_rate for m in metrics_list)
    total_errors = sum(m.error_count for m in metrics_list)
    n = len(metrics_list)
    
    return total_success / n, total_errors / n

def check_nash_equilibrium(metrics_list: List[ModuleMetrics], 
                          improvement_threshold: float = 0.05) -> EquilibriumResult:
    """
    Check if the system is in a Nash equilibrium state.
    
    A system is in Nash equilibrium if no single module can be improved (according to 
    heuristic) to significantly improve overall system performance.
    
    Args:
        metrics_list: List of ModuleMetrics for each module in the system
        improvement_threshold: Minimum improvement potential to consider a module 'stuck'
                              (default 0.05 = 5%)
    
    Returns:
        EquilibriumResult with:
            - is_equilibrium: True if no module has significant improvement potential
            - stuck_modules: Set of module names that are 'stuck' (cannot be improved)
            - improvement_potential: Dict mapping module names to their improvement potential
    """
    if not metrics_list:
        return EquilibriumResult(
            is_equilibrium=True,
            stuck_modules=set(),
            improvement_potential={}
        )
    
    # Compute system averages
    avg_success, avg_errors = _compute_system_averages(metrics_list)
    
    # Compute improvement potential for each module
    improvement_potential = {}
    stuck_modules = set()
    
    for metrics in metrics_list:
        name = metrics.name if metrics.name else f"Module_{id(metrics)}"
        potential = _compute_improvement_potential(metrics, avg_success, avg_errors)
        improvement_potential[name] = potential
        
        # A module is 'stuck' if its improvement potential is below threshold
        # (meaning it's already performing well relative to the system)
        if potential < improvement_threshold:
            stuck_modules.add(name)
    
    # System is in equilibrium if all modules are stuck (no significant improvement possible)
    is_equilibrium = len(stuck_modules) == len(metrics_list)
    
    return EquilibriumResult(
        is_equilibrium=is_equilibrium,
        stuck_modules=stuck_modules,
        improvement_potential=improvement_potential
    )

def find_improvement_candidates(metrics_list: List[ModuleMetrics],
                               improvement_threshold: float = 0.05) -> List[Tuple[str, float]]:
    """
    Find modules that could be improved to move the system toward equilibrium.
    
    Returns sorted list of (module_name, improvement_potential) tuples,
    from highest potential to lowest.
    """
    result = check_nash_equilibrium(metrics_list, improvement_threshold)
    
    candidates = [
        (name, potential) 
        for name, potential in result.improvement_potential.items()
        if potential >= improvement_threshold
    ]
    
    # Sort by improvement potential descending
    candidates.sort(key=lambda x: x[1], reverse=True)
    return candidates

def is_system_stable(metrics_list: List[ModuleMetrics],
                    stability_threshold: float = 0.02) -> bool:
    """
    Quick check if the system is stable (close to Nash equilibrium).
    
    A system is stable if the maximum improvement potential across all modules
    is below the stability threshold.
    """
    result = check_nash_equilibrium(metrics_list, stability_threshold)
    return result.is_equilibrium

# Example usage and test
if __name__ == "__main__":
    # Create sample module metrics
    modules = [
        ModuleMetrics(name="Module_A", success_rate=0.95, error_count=5),
        ModuleMetrics(name="Module_B", success_rate=0.85, error_count=15),
        ModuleMetrics(name="Module_C", success_rate=0.98, error_count=2),
        ModuleMetrics(name="Module_D", success_rate=0.70, error_count=30),
    ]
    
    # Check equilibrium
    result = check_nash_equilibrium(modules)
    print(f"Is equilibrium: {result.is_equilibrium}")
    print(f"Stuck modules: {result.stuck_modules}")
    print(f"Improvement potentials: {result.improvement_potential}")
    
    # Find improvement candidates
    candidates = find_improvement_candidates(modules)
    print(f"Improvement candidates: {candidates}")
    
    # Check stability
    print(f"Is stable: {is_system_stable(modules)}")