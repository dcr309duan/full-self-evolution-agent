import json
import os
import time
from collections import defaultdict
from typing import Dict, List, Optional, Tuple, Any

STATE_FILE = "nash_state.json"

class NashStateManager:
    """Manages the state of module interactions, performance metrics, and mutation history."""

    def __init__(self, state_file: str = STATE_FILE):
        self.state_file = state_file
        self.state = self._load_or_initialize()

    def _load_or_initialize(self) -> Dict[str, Any]:
        """Load existing state file or create a default one."""
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, "r") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        return self._default_state()

    def _default_state(self) -> Dict[str, Any]:
        """Return a default state structure."""
        return {
            "interaction_matrix": {},
            "performance_metrics": {},
            "mutation_history": {},
            "last_updated": time.time()
        }

    def save(self) -> None:
        """Persist current state to JSON file."""
        self.state["last_updated"] = time.time()
        with open(self.state_file, "w") as f:
            json.dump(self.state, f, indent=2)

    def register_module(self, module_name: str) -> None:
        """Register a new module if not already present."""
        if module_name not in self.state["interaction_matrix"]:
            self.state["interaction_matrix"][module_name] = {}
        if module_name not in self.state["performance_metrics"]:
            self.state["performance_metrics"][module_name] = {
                "success_rate": 0.0,
                "avg_execution_time": 0.0,
                "total_calls": 0,
                "last_success": None,
                "last_failure": None
            }
        if module_name not in self.state["mutation_history"]:
            self.state["mutation_history"][module_name] = []

    def record_interaction(self, source: str, target: str, interaction_type: str = "call") -> None:
        """Record that source module interacted with target module."""
        self.register_module(source)
        self.register_module(target)
        if target not in self.state["interaction_matrix"][source]:
            self.state["interaction_matrix"][source][target] = {"count": 0, "types": []}
        self.state["interaction_matrix"][source][target]["count"] += 1
        self.state["interaction_matrix"][source][target]["types"].append(interaction_type)

    def update_performance(self, module_name: str, success: bool, execution_time: float) -> None:
        """Update performance metrics for a module after an operation."""
        self.register_module(module_name)
        metrics = self.state["performance_metrics"][module_name]
        total = metrics["total_calls"]
        if success:
            metrics["last_success"] = time.time()
            metrics["success_rate"] = (metrics["success_rate"] * total + 1.0) / (total + 1)
        else:
            metrics["last_failure"] = time.time()
            metrics["success_rate"] = (metrics["success_rate"] * total) / (total + 1)
        metrics["total_calls"] = total + 1
        metrics["avg_execution_time"] = (metrics["avg_execution_time"] * total + execution_time) / (total + 1)

    def record_mutation(self, module_name: str, mutation_type: str, details: Optional[Dict] = None) -> None:
        """Record a mutation event for a module."""
        self.register_module(module_name)
        entry = {
            "timestamp": time.time(),
            "mutation_type": mutation_type,
            "details": details or {}
        }
        self.state["mutation_history"][module_name].append(entry)

    def get_interaction_matrix(self) -> Dict[str, Dict[str, Dict]]:
        """Return the full interaction matrix."""
        return self.state["interaction_matrix"]

    def get_performance_metrics(self, module_name: Optional[str] = None) -> Dict:
        """Return performance metrics for all modules or a specific one."""
        if module_name:
            return self.state["performance_metrics"].get(module_name, {})
        return self.state["performance_metrics"]

    def get_mutation_history(self, module_name: Optional[str] = None) -> Dict:
        """Return mutation history for all modules or a specific one."""
        if module_name:
            return self.state["mutation_history"].get(module_name, [])
        return self.state["mutation_history"]

    def get_module_summary(self, module_name: str) -> Dict:
        """Return a combined summary for a module."""
        self.register_module(module_name)
        return {
            "interactions": self.state["interaction_matrix"].get(module_name, {}),
            "performance": self.state["performance_metrics"].get(module_name, {}),
            "mutations": self.state["mutation_history"].get(module_name, [])
        }

    def reset_module(self, module_name: str) -> None:
        """Reset all data for a specific module."""
        if module_name in self.state["interaction_matrix"]:
            self.state["interaction_matrix"][module_name] = {}
        if module_name in self.state["performance_metrics"]:
            self.state["performance_metrics"][module_name] = {
                "success_rate": 0.0,
                "avg_execution_time": 0.0,
                "total_calls": 0,
                "last_success": None,
                "last_failure": None
            }
        if module_name in self.state["mutation_history"]:
            self.state["mutation_history"][module_name] = []

    def clear_all(self) -> None:
        """Reset entire state to default."""
        self.state = self._default_state()
        self.save()

# Convenience functions for quick access without instantiating the class

def update_state_after_mutation(module_name: str, mutation_type: str, success: bool,
                                execution_time: float, details: Optional[Dict] = None,
                                interactions: Optional[List[Tuple[str, str]]] = None) -> None:
    """Convenience function to update state after a mutation cycle."""
    manager = NashStateManager()
    manager.record_mutation(module_name, mutation_type, details)
    manager.update_performance(module_name, success, execution_time)
    if interactions:
        for source, target in interactions:
            manager.record_interaction(source, target)
    manager.save()

def get_state_for_detector() -> Dict[str, Any]:
    """Return a simplified state dict suitable for nash_detector consumption."""
    manager = NashStateManager()
    return {
        "interaction_matrix": manager.get_interaction_matrix(),
        "performance_metrics": manager.get_performance_metrics(),
        "mutation_history": manager.get_mutation_history(),
        "last_updated": manager.state.get("last_updated", 0)
    }