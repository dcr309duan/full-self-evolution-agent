"""
system_health_dashboard.py

Main dashboard module that collects and correlates health data from all modules.
Provides a standardized health report interface, collects failure rates, performance
metrics, dependency status, computes cross-module conflict scores, identifies
underutilized components, and exposes a real-time JSON endpoint for external monitoring.
"""

import json
import time
import threading
from collections import defaultdict
from typing import Any, Callable, Dict, List, Optional, Tuple

# ----------------------------------------------------------------------
# Standardized Health Report Interface
# ----------------------------------------------------------------------

class HealthReport:
    """
    Standardized health report that each module should implement.
    Modules must return an instance of this class from their health check method.
    """
    def __init__(
        self,
        module_name: str,
        failure_rate: float,
        execution_time: float,
        success_rate: float,
        dependencies: Dict[str, bool],
        last_active_cycle: int,
        modified_files: List[str] = None,
        capabilities: List[str] = None,
    ):
        self.module_name = module_name
        self.failure_rate = failure_rate          # 0.0 to 1.0
        self.execution_time = execution_time      # in seconds
        self.success_rate = success_rate          # 0.0 to 1.0
        self.dependencies = dependencies          # {dependency_name: is_healthy}
        self.last_active_cycle = last_active_cycle
        self.modified_files = modified_files or []
        self.capabilities = capabilities or []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "module_name": self.module_name,
            "failure_rate": self.failure_rate,
            "execution_time": self.execution_time,
            "success_rate": self.success_rate,
            "dependencies": self.dependencies,
            "last_active_cycle": self.last_active_cycle,
            "modified_files": self.modified_files,
            "capabilities": self.capabilities,
        }


# ----------------------------------------------------------------------
# Dashboard Core
# ----------------------------------------------------------------------

class SystemHealthDashboard:
    """
    Main dashboard that collects and correlates health data from all modules.
    """

    def __init__(self, current_cycle: int = 0, underutilized_threshold: int = 20):
        self._registry: Dict[str, Callable[[], HealthReport]] = {}
        self._reports: Dict[str, HealthReport] = {}
        self._lock = threading.Lock()
        self._current_cycle = current_cycle
        self._underutilized_threshold = underutilized_threshold
        self._file_modification_map: Dict[str, List[str]] = defaultdict(list)

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register_module(self, module_name: str, health_check_func: Callable[[], HealthReport]) -> None:
        """
        Register a module's health check function. The function should return a HealthReport instance.
        """
        with self._lock:
            self._registry[module_name] = health_check_func

    def unregister_module(self, module_name: str) -> None:
        """Remove a module from the registry."""
        with self._lock:
            self._registry.pop(module_name, None)
            self._reports.pop(module_name, None)

    # ------------------------------------------------------------------
    # Data Collection
    # ------------------------------------------------------------------

    def collect_all_reports(self) -> None:
        """
        Call all registered health check functions and store the reports.
        """
        reports = {}
        with self._lock:
            registry_snapshot = list(self._registry.items())
        for module_name, health_check_func in registry_snapshot:
            try:
                report = health_check_func()
                reports[module_name] = report
            except Exception as e:
                # If a module fails to report, create a failure report
                reports[module_name] = HealthReport(
                    module_name=module_name,
                    failure_rate=1.0,
                    execution_time=0.0,
                    success_rate=0.0,
                    dependencies={},
                    last_active_cycle=self._current_cycle,
                )
        with self._lock:
            self._reports = reports
            # Update file modification map
            self._file_modification_map.clear()
            for module_name, report in reports.items():
                for f in report.modified_files:
                    self._file_modification_map[f].append(module_name)

    def set_current_cycle(self, cycle: int) -> None:
        """Update the current cycle number."""
        self._current_cycle = cycle

    # ------------------------------------------------------------------
    # Aggregated Metrics
    # ------------------------------------------------------------------

    def get_average_failure_rate(self) -> float:
        """Compute average failure rate across all modules."""
        with self._lock:
            if not self._reports:
                return 0.0
            rates = [r.failure_rate for r in self._reports.values()]
            return sum(rates) / len(rates)

    def get_average_execution_time(self) -> float:
        """Compute average execution time across all modules."""
        with self._lock:
            if not self._reports:
                return 0.0
            times = [r.execution_time for r in self._reports.values()]
            return sum(times) / len(times)

    def get_average_success_rate(self) -> float:
        """Compute average success rate across all modules."""
        with self._lock:
            if not self._reports:
                return 0.0
            rates = [r.success_rate for r in self._reports.values()]
            return sum(rates) / len(rates)

    def get_dependency_status(self) -> Dict[str, bool]:
        """Aggregate dependency status across all modules. A dependency is healthy if all modules report it as healthy."""
        with self._lock:
            dep_status: Dict[str, List[bool]] = defaultdict(list)
            for report in self._reports.values():
                for dep, healthy in report.dependencies.items():
                    dep_status[dep].append(healthy)
            return {dep: all(statuses) for dep, statuses in dep_status.items()}

    # ------------------------------------------------------------------
    # Cross-Module Conflict Scores
    # ------------------------------------------------------------------

    def compute_conflict_scores(self) -> Dict[str, float]:
        """
        Compute conflict scores for each pair of modules based on shared file modifications.
        Returns a dictionary with keys like "moduleA<->moduleB" and values 0.0 to 1.0.
        """
        conflict_scores: Dict[Tuple[str, str], int] = defaultdict(int)
        total_files = len(self._file_modification_map)
        if total_files == 0:
            return {}
        for modules in self._file_modification_map.values():
            if len(modules) > 1:
                for i in range(len(modules)):
                    for j in range(i + 1, len(modules)):
                        pair = tuple(sorted([modules[i], modules[j]]))
                        conflict_scores[pair] += 1
        # Normalize by total files
        return {f"{a}<->{b}": count / total_files for (a, b), count in conflict_scores.items()}

    # ------------------------------------------------------------------
    # Underutilized Components
    # ------------------------------------------------------------------

    def get_underutilized_components(self) -> List[Dict[str, Any]]:
        """
        Identify capabilities not used in the last N cycles (default 20).
        Returns a list of dicts with module_name and capability.
        """
        underutilized = []
        with self._lock:
            for module_name, report in self._reports.items():
                cycles_since_active = self._current_cycle - report.last_active_cycle
                if cycles_since_active >= self._underutilized_threshold:
                    for cap in report.capabilities:
                        underutilized.append({
                            "module_name": module_name,
                            "capability": cap,
                            "cycles_since_active": cycles_since_active,
                        })
        return underutilized

    # ------------------------------------------------------------------
    # Real-Time JSON Endpoint
    # ------------------------------------------------------------------

    def get_json_snapshot(self) -> str:
        """
        Generate a JSON string representing the current health state.
        Suitable for external monitoring.
        """
        with self._lock:
            reports_dict = {name: report.to_dict() for name, report in self._reports.items()}
        snapshot = {
            "timestamp": time.time(),
            "current_cycle": self._current_cycle,
            "average_failure_rate": self.get_average_failure_rate(),
            "average_execution_time": self.get_average_execution_time(),
            "average_success_rate": self.get_average_success_rate(),
            "dependency_status": self.get_dependency_status(),
            "conflict_scores": self.compute_conflict_scores(),
            "underutilized_components": self.get_underutilized_components(),
            "module_reports": reports_dict,
        }
        return json.dumps(snapshot, indent=2)

    # ------------------------------------------------------------------
    # Convenience Methods
    # ------------------------------------------------------------------

    def get_all_reports(self) -> Dict[str, HealthReport]:
        """Return a copy of all current reports."""
        with self._lock:
            return dict(self._reports)

    def get_report(self, module_name: str) -> Optional[HealthReport]:
        """Return the report for a specific module."""
        with self._lock:
            return self._reports.get(module_name)


# ----------------------------------------------------------------------
# Singleton instance for easy import
# ----------------------------------------------------------------------

_dashboard_instance: Optional[SystemHealthDashboard] = None
_dashboard_lock = threading.Lock()

def get_dashboard() -> SystemHealthDashboard:
    """Return the singleton dashboard instance."""
    global _dashboard_instance
    if _dashboard_instance is None:
        with _dashboard_lock:
            if _dashboard_instance is None:
                _dashboard_instance = SystemHealthDashboard()
    return _dashboard_instance


# ----------------------------------------------------------------------
# Example usage (if run as main)
# ----------------------------------------------------------------------

if __name__ == "__main__":
    # Example module health check functions
    def module_a_health():
        return HealthReport(
            module_name="ModuleA",
            failure_rate=0.05,
            execution_time=0.2,
            success_rate=0.95,
            dependencies={"database": True, "cache": True},
            last_active_cycle=10,
            modified_files=["/tmp/file1.txt", "/tmp/file2.txt"],
            capabilities=["read", "write"],
        )

    def module_b_health():
        return HealthReport(
            module_name="ModuleB",
            failure_rate=0.1,
            execution_time=0.5,
            success_rate=0.9,
            dependencies={"database": True, "queue": False},
            last_active_cycle=5,
            modified_files=["/tmp/file1.txt", "/tmp/file3.txt"],
            capabilities=["process", "write"],
        )

    dashboard = get_dashboard()
    dashboard.set_current_cycle(25)
    dashboard.register_module("ModuleA", module_a_health)
    dashboard.register_module("ModuleB", module_b_health)
    dashboard.collect_all_reports()

    print("JSON Snapshot:")
    print(dashboard.get_json_snapshot())