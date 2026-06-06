"""Nash Metrics Collector - Tracks per-module performance metrics over the last 5 cycles.

Provides data needed for equilibrium detection including success rate,
execution time, and error count for each module.
"""

from collections import deque
import time
from typing import Dict, List, Optional, Tuple


class ModuleMetrics:
    """Tracks metrics for a single module over the last N cycles."""
    
    def __init__(self, max_cycles: int = 5):
        self.max_cycles = max_cycles
        self.successes: deque = deque(maxlen=max_cycles)
        self.execution_times: deque = deque(maxlen=max_cycles)
        self.error_counts: deque = deque(maxlen=max_cycles)
        self.total_cycles = 0
        
    def record_cycle(self, success: bool, execution_time: float, error_count: int) -> None:
        """Record metrics for a single cycle."""
        self.successes.append(1 if success else 0)
        self.execution_times.append(execution_time)
        self.error_counts.append(error_count)
        self.total_cycles += 1
        
    @property
    def success_rate(self) -> float:
        """Calculate success rate over tracked cycles."""
        if not self.successes:
            return 0.0
        return sum(self.successes) / len(self.successes)
    
    @property
    def avg_execution_time(self) -> float:
        """Calculate average execution time over tracked cycles."""
        if not self.execution_times:
            return 0.0
        return sum(self.execution_times) / len(self.execution_times)
    
    @property
    def avg_error_count(self) -> float:
        """Calculate average error count over tracked cycles."""
        if not self.error_counts:
            return 0.0
        return sum(self.error_counts) / len(self.error_counts)
    
    @property
    def total_errors(self) -> int:
        """Get total error count over tracked cycles."""
        return sum(self.error_counts)
    
    def get_summary(self) -> Dict[str, float]:
        """Get a summary of all metrics."""
        return {
            'success_rate': self.success_rate,
            'avg_execution_time': self.avg_execution_time,
            'avg_error_count': self.avg_error_count,
            'total_errors': self.total_errors,
            'total_cycles': self.total_cycles
        }


class NashMetricsCollector:
    """Collects and manages metrics for all modules."""
    
    def __init__(self, max_cycles: int = 5):
        self.max_cycles = max_cycles
        self._modules: Dict[str, ModuleMetrics] = {}
        self._current_cycle = 0
        
    def _get_or_create_module(self, module_name: str) -> ModuleMetrics:
        """Get existing module metrics or create new ones."""
        if module_name not in self._modules:
            self._modules[module_name] = ModuleMetrics(self.max_cycles)
        return self._modules[module_name]
    
    def record_success(self, module_name: str, execution_time: float) -> None:
        """Record a successful execution for a module."""
        module = self._get_or_create_module(module_name)
        module.record_cycle(success=True, execution_time=execution_time, error_count=0)
        
    def record_failure(self, module_name: str, execution_time: float, error_count: int = 1) -> None:
        """Record a failed execution for a module."""
        module = self._get_or_create_module(module_name)
        module.record_cycle(success=False, execution_time=execution_time, error_count=error_count)
        
    def record_cycle(self, module_name: str, success: bool, execution_time: float, 
                    error_count: int = 0) -> None:
        """Record a complete cycle for a module."""
        module = self._get_or_create_module(module_name)
        module.record_cycle(success, execution_time, error_count)
        self._current_cycle += 1
        
    def get_module_metrics(self, module_name: str) -> Optional[Dict[str, float]]:
        """Get metrics summary for a specific module."""
        if module_name not in self._modules:
            return None
        return self._modules[module_name].get_summary()
    
    def get_all_metrics(self) -> Dict[str, Dict[str, float]]:
        """Get metrics for all tracked modules."""
        return {
            name: metrics.get_summary() 
            for name, metrics in self._modules.items()
        }
    
    def get_high_performing_modules(self, threshold: float = 0.8) -> List[str]:
        """Get modules with success rate above threshold."""
        return [
            name for name, metrics in self._modules.items()
            if metrics.success_rate >= threshold
        ]
    
    def get_low_performing_modules(self, threshold: float = 0.5) -> List[str]:
        """Get modules with success rate below threshold."""
        return [
            name for name, metrics in self._modules.items()
            if metrics.success_rate < threshold
        ]
    
    def get_equilibrium_data(self) -> Dict[str, Dict[str, float]]:
        """Get data formatted for equilibrium detection."""
        return {
            name: {
                'success_rate': metrics.success_rate,
                'avg_time': metrics.avg_execution_time,
                'avg_errors': metrics.avg_error_count,
                'stability': self._calculate_stability(metrics)
            }
            for name, metrics in self._modules.items()
        }
    
    def _calculate_stability(self, metrics: ModuleMetrics) -> float:
        """Calculate stability score (1.0 = perfectly stable, 0.0 = unstable)."""
        if len(metrics.successes) < 2:
            return 1.0
        
        # Check for consistent success/failure patterns
        successes_list = list(metrics.successes)
        changes = sum(
            1 for i in range(1, len(successes_list))
            if successes_list[i] != successes_list[i-1]
        )
        
        # Fewer changes = more stable
        stability = 1.0 - (changes / (len(successes_list) - 1))
        return max(0.0, min(1.0, stability))
    
    def reset_module(self, module_name: str) -> None:
        """Reset metrics for a specific module."""
        if module_name in self._modules:
            del self._modules[module_name]
    
    def reset_all(self) -> None:
        """Reset all metrics."""
        self._modules.clear()
        self._current_cycle = 0
    
    @property
    def current_cycle(self) -> int:
        """Get the current cycle number."""
        return self._current_cycle
    
    @property
    def tracked_modules(self) -> List[str]:
        """Get list of all tracked module names."""
        return list(self._modules.keys())
    
    @property
    def module_count(self) -> int:
        """Get number of tracked modules."""
        return len(self._modules)