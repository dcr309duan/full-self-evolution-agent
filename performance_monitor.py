import json
import os
from collections import defaultdict, deque
from typing import Dict, List, Optional, Tuple, Any

class PerformanceMonitor:
    """
    Central performance monitoring module for tracking and analyzing
    evolution and module-level performance metrics.
    """

    def __init__(self, log_file: str = "evolution_log.json"):
        self.log_file = log_file
        self.window_sizes = [10, 50, 100]
        self._metrics_cache: Dict[str, Any] = {}
        self._load_log()

    def _load_log(self) -> None:
        """Load evolution log data from JSON file."""
        if os.path.exists(self.log_file):
            try:
                with open(self.log_file, 'r') as f:
                    self._log_data = json.load(f)
            except (json.JSONDecodeError, IOError):
                self._log_data = []
        else:
            self._log_data = []

    def _get_moving_average(self, values: List[float], window: int) -> Optional[float]:
        """Compute moving average for a given window size."""
        if len(values) < window:
            return None
        recent = values[-window:]
        return sum(recent) / window

    def get_success_rate(self, window: Optional[int] = None) -> Dict[str, Any]:
        """
        Calculate success rate over entire log or sliding window.
        
        Args:
            window: Optional window size (10, 50, or 100)
        
        Returns:
            Dict with success_rate and optional moving_averages
        """
        if not self._log_data:
            return {"success_rate": 0.0, "moving_averages": {}}

        total_cycles = len(self._log_data)
        successful = sum(1 for entry in self._log_data if entry.get("success", False))
        overall_rate = successful / total_cycles if total_cycles > 0 else 0.0

        result = {"success_rate": overall_rate}

        if window:
            if window in self.window_sizes:
                recent = self._log_data[-window:]
                recent_success = sum(1 for entry in recent if entry.get("success", False))
                result["window_rate"] = recent_success / len(recent) if recent else 0.0
        else:
            # Compute all moving averages
            success_values = [1.0 if entry.get("success", False) else 0.0 for entry in self._log_data]
            result["moving_averages"] = {
                str(w): self._get_moving_average(success_values, w)
                for w in self.window_sizes
            }

        return result

    def get_cycle_time(self, window: Optional[int] = None) -> Dict[str, Any]:
        """
        Calculate average cycle time over entire log or sliding window.
        
        Args:
            window: Optional window size (10, 50, or 100)
        
        Returns:
            Dict with avg_cycle_time and optional moving_averages
        """
        if not self._log_data:
            return {"avg_cycle_time": 0.0, "moving_averages": {}}

        cycle_times = [entry.get("cycle_time", 0) for entry in self._log_data if "cycle_time" in entry]
        if not cycle_times:
            return {"avg_cycle_time": 0.0, "moving_averages": {}}

        overall_avg = sum(cycle_times) / len(cycle_times)

        result = {"avg_cycle_time": overall_avg}

        if window:
            if window in self.window_sizes:
                recent = cycle_times[-window:]
                result["window_avg"] = sum(recent) / len(recent) if recent else 0.0
        else:
            result["moving_averages"] = {
                str(w): self._get_moving_average(cycle_times, w)
                for w in self.window_sizes
            }

        return result

    def get_mutation_type_distribution(self, window: Optional[int] = None) -> Dict[str, Any]:
        """
        Get distribution of mutation types over entire log or sliding window.
        
        Args:
            window: Optional window size (10, 50, or 100)
        
        Returns:
            Dict with mutation_counts and percentages
        """
        if not self._log_data:
            return {"mutation_counts": {}, "percentages": {}}

        data = self._log_data[-window:] if window and window in self.window_sizes else self._log_data
        total = len(data)

        mutation_counts = defaultdict(int)
        for entry in data:
            mutation_type = entry.get("mutation_type", "unknown")
            mutation_counts[mutation_type] += 1

        percentages = {
            mutation: (count / total * 100) if total > 0 else 0.0
            for mutation, count in mutation_counts.items()
        }

        return {
            "mutation_counts": dict(mutation_counts),
            "percentages": percentages
        }

    def get_module_performance(self, module_name: str, window: Optional[int] = None) -> Dict[str, Any]:
        """
        Track performance metrics for a specific module.
        
        Args:
            module_name: Name of the module to analyze
            window: Optional window size (10, 50, or 100)
        
        Returns:
            Dict with failure_frequency, rollback_rate, and moving averages
        """
        if not self._log_data:
            return {
                "failure_frequency": 0.0,
                "rollback_rate": 0.0,
                "moving_averages": {}
            }

        data = self._log_data[-window:] if window and window in self.window_sizes else self._log_data

        module_entries = [entry for entry in data if entry.get("module") == module_name]
        if not module_entries:
            return {
                "failure_frequency": 0.0,
                "rollback_rate": 0.0,
                "moving_averages": {}
            }

        total_module = len(module_entries)
        failures = sum(1 for entry in module_entries if not entry.get("success", True))
        rollbacks = sum(1 for entry in module_entries if entry.get("rolled_back", False))

        failure_freq = failures / total_module if total_module > 0 else 0.0
        rollback_rate = rollbacks / total_module if total_module > 0 else 0.0

        result = {
            "failure_frequency": failure_freq,
            "rollback_rate": rollback_rate,
            "total_entries": total_module
        }

        if not window:
            # Compute moving averages for module metrics
            module_success = [1.0 if entry.get("success", True) else 0.0 for entry in module_entries]
            module_rollbacks = [1.0 if entry.get("rolled_back", False) else 0.0 for entry in module_entries]

            result["moving_averages"] = {
                "failure": {str(w): self._get_moving_average(
                    [1 - s for s in module_success], w
                ) for w in self.window_sizes},
                "rollback": {str(w): self._get_moving_average(module_rollbacks, w) for w in self.window_sizes}
            }

        return result

    def get_all_modules_performance(self, window: Optional[int] = None) -> Dict[str, Dict]:
        """
        Get performance metrics for all modules.
        
        Args:
            window: Optional window size (10, 50, or 100)
        
        Returns:
            Dict mapping module names to their performance metrics
        """
        if not self._log_data:
            return {}

        modules = set(entry.get("module") for entry in self._log_data if "module" in entry)
        return {
            module: self.get_module_performance(module, window)
            for module in modules
        }

    def get_summary(self, window: Optional[int] = None) -> Dict[str, Any]:
        """
        Get a comprehensive summary of all performance metrics.
        
        Args:
            window: Optional window size (10, 50, or 100)
        
        Returns:
            Dict with all key metrics
        """
        return {
            "success_rate": self.get_success_rate(window),
            "cycle_time": self.get_cycle_time(window),
            "mutation_distribution": self.get_mutation_type_distribution(window),
            "module_performance": self.get_all_modules_performance(window)
        }

    def refresh(self) -> None:
        """Reload log data from file to get latest metrics."""
        self._load_log()
        self._metrics_cache = {}


# Convenience functions for external modules
def get_performance_summary(log_file: str = "evolution_log.json", window: Optional[int] = None) -> Dict[str, Any]:
    """Quick access to performance summary."""
    monitor = PerformanceMonitor(log_file)
    return monitor.get_summary(window)


def get_module_insights(module_name: str, log_file: str = "evolution_log.json", window: Optional[int] = None) -> Dict[str, Any]:
    """Quick access to specific module performance insights."""
    monitor = PerformanceMonitor(log_file)
    return monitor.get_module_performance(module_name, window)


def get_success_rate_trend(log_file: str = "evolution_log.json") -> Dict[str, Optional[float]]:
    """Get success rate moving averages for all window sizes."""
    monitor = PerformanceMonitor(log_file)
    return monitor.get_success_rate()["moving_averages"]


def get_cycle_time_trend(log_file: str = "evolution_log.json") -> Dict[str, Optional[float]]:
    """Get cycle time moving averages for all window sizes."""
    monitor = PerformanceMonitor(log_file)
    return monitor.get_cycle_time()["moving_averages"]