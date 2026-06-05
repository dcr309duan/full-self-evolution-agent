"""Metrics collector for the simulation engine.

Tracks simulation accuracy, performance, and error rates per module.
Provides data export for the reflection system to analyze.
"""

import time
import threading
from collections import defaultdict
from typing import Dict, List, Optional, Tuple, Any


class SimulationMetrics:
    """Collects and manages metrics for the simulation engine."""

    def __init__(self):
        self._lock = threading.Lock()
        # Accuracy tracking
        self._total_simulations = 0
        self._correct_predictions = 0
        self._incorrect_predictions = 0
        self._module_accuracy: Dict[str, Dict[str, int]] = defaultdict(
            lambda: {"correct": 0, "incorrect": 0, "total": 0}
        )
        # Performance tracking
        self._simulation_times: List[float] = []
        self._resource_usage: Dict[str, List[float]] = defaultdict(list)
        self._start_time: Optional[float] = None
        # False positive/negative rates per module
        self._module_fp_fn: Dict[str, Dict[str, int]] = defaultdict(
            lambda: {"fp": 0, "fn": 0, "tp": 0, "tn": 0}
        )
        # Metadata
        self._labels: Dict[str, Any] = {}

    def start_session(self) -> None:
        """Start a new metrics collection session."""
        with self._lock:
            self._start_time = time.time()

    def record_simulation_result(
        self,
        module_name: str,
        predicted_outcome: Any,
        actual_outcome: Any,
        simulation_time: float,
        resource_usage: Optional[Dict[str, float]] = None,
    ) -> None:
        """Record a single simulation result.

        Args:
            module_name: Name of the module being simulated.
            predicted_outcome: The outcome predicted by the simulation.
            actual_outcome: The actual outcome observed.
            simulation_time: Time taken for the simulation in seconds.
            resource_usage: Optional dict of resource usage metrics (e.g., memory, CPU).
        """
        with self._lock:
            self._total_simulations += 1
            self._simulation_times.append(simulation_time)

            if predicted_outcome == actual_outcome:
                self._correct_predictions += 1
                self._module_accuracy[module_name]["correct"] += 1
            else:
                self._incorrect_predictions += 1
                self._module_accuracy[module_name]["incorrect"] += 1

            self._module_accuracy[module_name]["total"] += 1

            if resource_usage:
                for key, value in resource_usage.items():
                    self._resource_usage[key].append(value)

    def record_false_positive_negative(
        self,
        module_name: str,
        is_false_positive: bool = False,
        is_false_negative: bool = False,
        is_true_positive: bool = False,
        is_true_negative: bool = False,
    ) -> None:
        """Record a false positive or false negative for a module.

        Args:
            module_name: Name of the module.
            is_false_positive: Whether this is a false positive.
            is_false_negative: Whether this is a false negative.
            is_true_positive: Whether this is a true positive.
            is_true_negative: Whether this is a true negative.
        """
        with self._lock:
            if is_false_positive:
                self._module_fp_fn[module_name]["fp"] += 1
            if is_false_negative:
                self._module_fp_fn[module_name]["fn"] += 1
            if is_true_positive:
                self._module_fp_fn[module_name]["tp"] += 1
            if is_true_negative:
                self._module_fp_fn[module_name]["tn"] += 1

    def set_label(self, key: str, value: Any) -> None:
        """Set a metadata label for the metrics session.

        Args:
            key: Label key.
            value: Label value.
        """
        with self._lock:
            self._labels[key] = value

    def get_accuracy(self) -> float:
        """Get overall simulation accuracy.

        Returns:
            Accuracy as a float between 0 and 1.
        """
        with self._lock:
            if self._total_simulations == 0:
                return 0.0
            return self._correct_predictions / self._total_simulations

    def get_module_accuracy(self, module_name: str) -> float:
        """Get accuracy for a specific module.

        Args:
            module_name: Name of the module.

        Returns:
            Accuracy as a float between 0 and 1.
        """
        with self._lock:
            data = self._module_accuracy.get(module_name)
            if not data or data["total"] == 0:
                return 0.0
            return data["correct"] / data["total"]

    def get_module_false_positive_rate(self, module_name: str) -> float:
        """Get false positive rate for a module.

        Args:
            module_name: Name of the module.

        Returns:
            False positive rate as a float between 0 and 1.
        """
        with self._lock:
            data = self._module_fp_fn.get(module_name)
            if not data:
                return 0.0
            total_negatives = data["fp"] + data["tn"]
            if total_negatives == 0:
                return 0.0
            return data["fp"] / total_negatives

    def get_module_false_negative_rate(self, module_name: str) -> float:
        """Get false negative rate for a module.

        Args:
            module_name: Name of the module.

        Returns:
            False negative rate as a float between 0 and 1.
        """
        with self._lock:
            data = self._module_fp_fn.get(module_name)
            if not data:
                return 0.0
            total_positives = data["fn"] + data["tp"]
            if total_positives == 0:
                return 0.0
            return data["fn"] / total_positives

    def get_average_simulation_time(self) -> float:
        """Get average simulation time.

        Returns:
            Average time in seconds.
        """
        with self._lock:
            if not self._simulation_times:
                return 0.0
            return sum(self._simulation_times) / len(self._simulation_times)

    def get_total_simulation_time(self) -> float:
        """Get total simulation time.

        Returns:
            Total time in seconds.
        """
        with self._lock:
            return sum(self._simulation_times)

    def get_session_duration(self) -> float:
        """Get duration of the current metrics session.

        Returns:
            Duration in seconds, or 0 if no session started.
        """
        with self._lock:
            if self._start_time is None:
                return 0.0
            return time.time() - self._start_time

    def get_resource_usage_stats(self) -> Dict[str, Dict[str, float]]:
        """Get resource usage statistics.

        Returns:
            Dict mapping resource names to dicts with 'mean', 'max', 'min', 'count'.
        """
        with self._lock:
            stats = {}
            for key, values in self._resource_usage.items():
                if values:
                    stats[key] = {
                        "mean": sum(values) / len(values),
                        "max": max(values),
                        "min": min(values),
                        "count": len(values),
                    }
            return stats

    def export_metrics(self) -> Dict[str, Any]:
        """Export all collected metrics for the reflection system.

        Returns:
            Dict containing all metrics data.
        """
        with self._lock:
            module_accuracies = {}
            for mod, data in self._module_accuracy.items():
                if data["total"] > 0:
                    module_accuracies[mod] = {
                        "accuracy": data["correct"] / data["total"],
                        "correct": data["correct"],
                        "incorrect": data["incorrect"],
                        "total": data["total"],
                    }

            module_fp_fn_rates = {}
            for mod, data in self._module_fp_fn.items():
                total_neg = data["fp"] + data["tn"]
                total_pos = data["fn"] + data["tp"]
                module_fp_fn_rates[mod] = {
                    "false_positive_rate": data["fp"] / total_neg if total_neg > 0 else 0.0,
                    "false_negative_rate": data["fn"] / total_pos if total_pos > 0 else 0.0,
                    "fp": data["fp"],
                    "fn": data["fn"],
                    "tp": data["tp"],
                    "tn": data["tn"],
                }

            return {
                "overall": {
                    "total_simulations": self._total_simulations,
                    "correct_predictions": self._correct_predictions,
                    "incorrect_predictions": self._incorrect_predictions,
                    "accuracy": self.get_accuracy(),
                    "average_simulation_time": self.get_average_simulation_time(),
                    "total_simulation_time": self.get_total_simulation_time(),
                    "session_duration": self.get_session_duration(),
                },
                "module_accuracy": module_accuracies,
                "module_false_positive_negative_rates": module_fp_fn_rates,
                "resource_usage": self.get_resource_usage_stats(),
                "labels": dict(self._labels),
            }

    def reset(self) -> None:
        """Reset all metrics to initial state."""
        with self._lock:
            self._total_simulations = 0
            self._correct_predictions = 0
            self._incorrect_predictions = 0
            self._module_accuracy.clear()
            self._simulation_times.clear()
            self._resource_usage.clear()
            self._module_fp_fn.clear()
            self._labels.clear()
            self._start_time = None