import json
import os
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

class NashEquilibriumDetector:
    """
    A completely self-contained Nash equilibrium detector that tracks module
    performance metrics in a local JSON file and detects when no single module
    has improved for 3+ cycles.
    """
    
    def __init__(self, metrics_file: str = "module_metrics_history.json"):
        self.metrics_file = metrics_file
        self.history = self._load_history()
        self.cycles_without_improvement = {}
        
    def _load_history(self) -> Dict[str, List[Dict[str, Any]]]:
        """Load historical metrics from JSON file."""
        if os.path.exists(self.metrics_file):
            try:
                with open(self.metrics_file, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return {}
        return {}
    
    def _save_history(self):
        """Save historical metrics to JSON file."""
        try:
            with open(self.metrics_file, 'w') as f:
                json.dump(self.history, f, indent=2)
        except IOError:
            pass  # Silently fail if we can't write
    
    def record_metrics(self, metrics_list: List[ModuleMetrics]):
        """Record current metrics for all modules."""
        timestamp = len(self.history.get('_timestamps', []))
        
        for metrics in metrics_list:
            name = metrics.name if metrics.name else f"Module_{id(metrics)}"
            if name not in self.history:
                self.history[name] = []
            
            self.history[name].append({
                'success_rate': metrics.success_rate,
                'error_count': metrics.error_count,
                'timestamp': timestamp
            })
        
        # Track timestamps
        if '_timestamps' not in self.history:
            self.history['_timestamps'] = []
        self.history['_timestamps'].append(timestamp)
        
        self._save_history()
    
    def _compute_improvement_potential(self, metrics: ModuleMetrics, system_avg_success: float, 
                                       system_avg_errors: float) -> float:
        """
        Compute a heuristic improvement potential for a single module.
        Returns a positive value if improving this module would likely help the system.
        Uses a weighted combination of success rate deficit and error rate excess.
        """
        success_deficit = max(0.0, system_avg_success - metrics.success_rate)
        error_rate = min(1.0, metrics.error_count / 100.0)
        system_error_rate = min(1.0, system_avg_errors / 100.0)
        error_excess = max(0.0, error_rate - system_error_rate)
        improvement = 0.7 * success_deficit + 0.3 * error_excess
        return improvement
    
    def _compute_system_averages(self, metrics_list: List[ModuleMetrics]) -> Tuple[float, float]:
        """Compute average success rate and average error count across all modules."""
        if not metrics_list:
            return 0.0, 0.0
        
        total_success = sum(m.success_rate for m in metrics_list)
        total_errors = sum(m.error_count for m in metrics_list)
        n = len(metrics_list)
        
        return total_success / n, total_errors / n
    
    def _has_improved_recently(self, module_name: str, cycles: int = 3) -> bool:
        """
        Check if a module has shown improvement in the last N cycles.
        Improvement is defined as increase in success_rate or decrease in error_count.
        """
        if module_name not in self.history:
            return True  # No history means we assume improvement is possible
        
        module_history = self.history[module_name]
        if len(module_history) < 2:
            return True  # Not enough data to determine
        
        # Check the last N cycles
        check_cycles = min(cycles, len(module_history) - 1)
        recent_history = module_history[-check_cycles-1:]
        
        for i in range(1, len(recent_history)):
            prev = recent_history[i-1]
            curr = recent_history[i]
            
            # Check for improvement in success_rate
            if curr['success_rate'] > prev['success_rate']:
                return True
            
            # Check for improvement in error_count
            if curr['error_count'] < prev['error_count']:
                return True
        
        return False
    
    def check_nash_equilibrium(self, metrics_list: List[ModuleMetrics], 
                              improvement_threshold: float = 0.05) -> EquilibriumResult:
        """
        Check if the system is in a Nash equilibrium state.
        
        A system is in Nash equilibrium if no single module can be improved (according to 
        heuristic) to significantly improve overall system performance, AND no module has
        shown improvement for 3+ cycles.
        
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
        
        # Record current metrics
        self.record_metrics(metrics_list)
        
        # Compute system averages
        avg_success, avg_errors = self._compute_system_averages(metrics_list)
        
        # Compute improvement potential for each module
        improvement_potential = {}
        stuck_modules = set()
        
        for metrics in metrics_list:
            name = metrics.name if metrics.name else f"Module_{id(metrics)}"
            potential = self._compute_improvement_potential(metrics, avg_success, avg_errors)
            improvement_potential[name] = potential
            
            # A module is 'stuck' if its improvement potential is below threshold
            # AND it hasn't improved in the last 3 cycles
            if potential < improvement_threshold:
                if not self._has_improved_recently(name, cycles=3):
                    stuck_modules.add(name)
        
        # System is in equilibrium if all modules are stuck (no significant improvement possible)
        is_equilibrium = len(stuck_modules) == len(metrics_list)
        
        return EquilibriumResult(
            is_equilibrium=is_equilibrium,
            stuck_modules=stuck_modules,
            improvement_potential=improvement_potential
        )
    
    def find_improvement_candidates(self, metrics_list: List[ModuleMetrics],
                                   improvement_threshold: float = 0.05) -> List[Tuple[str, float]]:
        """
        Find modules that could be improved to move the system toward equilibrium.
        
        Returns sorted list of (module_name, improvement_potential) tuples,
        from highest potential to lowest.
        """
        result = self.check_nash_equilibrium(metrics_list, improvement_threshold)
        
        candidates = [
            (name, potential) 
            for name, potential in result.improvement_potential.items()
            if potential >= improvement_threshold
        ]
        
        # Sort by improvement potential descending
        candidates.sort(key=lambda x: x[1], reverse=True)
        return candidates
    
    def is_system_stable(self, metrics_list: List[ModuleMetrics],
                        stability_threshold: float = 0.02) -> bool:
        """
        Quick check if the system is stable (close to Nash equilibrium).
        
        A system is stable if the maximum improvement potential across all modules
        is below the stability threshold.
        """
        result = self.check_nash_equilibrium(metrics_list, stability_threshold)
        return result.is_equilibrium
    
    def get_equilibrium_status(self) -> Tuple[bool, List[str]]:
        """
        Returns a boolean flag indicating if the system is at equilibrium
        and a list of modules that are at equilibrium.
        """
        # Load the latest metrics from history
        if not self.history or '_timestamps' not in self.history:
            return False, []
        
        # Get the latest metrics for each module
        latest_metrics = []
        for module_name, module_history in self.history.items():
            if module_name == '_timestamps':
                continue
            if module_history:
                latest = module_history[-1]
                latest_metrics.append(ModuleMetrics(
                    name=module_name,
                    success_rate=latest['success_rate'],
                    error_count=latest['error_count']
                ))
        
        if not latest_metrics:
            return False, []
        
        result = self.check_nash_equilibrium(latest_metrics)
        return result.is_equilibrium, list(result.stuck_modules)

# Example usage and test
if __name__ == "__main__":
    # Create detector instance
    detector = NashEquilibriumDetector()
    
    # Create sample module metrics
    modules = [
        ModuleMetrics(name="Module_A", success_rate=0.95, error_count=5),
        ModuleMetrics(name="Module_B", success_rate=0.85, error_count=15),
        ModuleMetrics(name="Module_C", success_rate=0.98, error_count=2),
        ModuleMetrics(name="Module_D", success_rate=0.70, error_count=30),
    ]
    
    # Check equilibrium
    result = detector.check_nash_equilibrium(modules)
    print(f"Is equilibrium: {result.is_equilibrium}")
    print(f"Stuck modules: {result.stuck_modules}")
    print(f"Improvement potentials: {result.improvement_potential}")
    
    # Find improvement candidates
    candidates = detector.find_improvement_candidates(modules)
    print(f"Improvement candidates: {candidates}")
    
    # Check stability
    print(f"Is stable: {detector.is_system_stable(modules)}")
    
    # Get equilibrium status
    is_eq, stuck = detector.get_equilibrium_status()
    print(f"Equilibrium status: is_equilibrium={is_eq}, stuck_modules={stuck}")