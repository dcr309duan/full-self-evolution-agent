"""
meta_evaluation_loop.py

Implements a meta-evaluation loop that tracks performance metrics per cycle,
detects stagnation, and dynamically adjusts the objective function to maintain
improvement momentum.
"""

import math
import time
from collections import deque
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple


class EvolutionObjective(Enum):
    IMPROVE_FITNESS = "improve_fitness"
    INCREASE_DIVERSITY = "increase_diversity"
    REFACTOR_ARCHITECTURE = "refactor_architecture"
    EXPLORE_NOVELTY = "explore_novelty"


class StagnationType(Enum):
    NO_STAGNATION = "no_stagnation"
    FITNESS_PLATEAU = "fitness_plateau"
    DIVERSITY_LOSS = "diversity_loss"
    REPEATED_FAILURES = "repeated_failures"


# Type alias for objective functions
ObjectiveFunction = Callable[..., float]

# Predefined objective functions
def maximize_capability_count(params: Dict[str, Any]) -> float:
    """Objective to maximize the number of capabilities."""
    return params.get("capability_count", 0)

def minimize_code_complexity(params: Dict[str, Any]) -> float:
    """Objective to minimize code complexity (lower is better)."""
    complexity = params.get("code_complexity", 0)
    return -complexity  # negative because we maximize objective

def maximize_test_coverage(params: Dict[str, Any]) -> float:
    """Objective to maximize test coverage percentage."""
    return params.get("test_coverage", 0)

class MetaEvaluationLoop:
    """
    Manages the meta-evaluation cycle, tracking metrics, detecting stagnation,
    and adjusting the objective function dynamically.
    """

    # Available objective functions with metadata
    OBJECTIVES = {
        "maximize_capability_count": {
            "func": maximize_capability_count,
            "params": {},
            "description": "Maximize the number of capabilities"
        },
        "minimize_code_complexity": {
            "func": minimize_code_complexity,
            "params": {},
            "description": "Minimize code complexity"
        },
        "maximize_test_coverage": {
            "func": maximize_test_coverage,
            "params": {},
            "description": "Maximize test coverage"
        }
    }

    def __init__(
        self,
        initial_objective: str = "maximize_capability_count",
        stagnation_threshold: float = 0.01,
        stagnation_window: int = 5,
        diversity_threshold: float = 0.2,
        cycle_history_size: int = 20
    ):
        """
        Initialize the meta-evaluation loop.

        Args:
            initial_objective: Name of the initial objective function.
            stagnation_threshold: Minimum improvement rate to consider non-stagnant.
            stagnation_window: Number of consecutive cycles below threshold to trigger stagnation.
            diversity_threshold: Minimum diversity score (0-1) to consider diverse.
            cycle_history_size: Number of recent cycles to keep for trend analysis.
        """
        if initial_objective not in self.OBJECTIVES:
            raise ValueError(f"Unknown objective: {initial_objective}. Available: {list(self.OBJECTIVES.keys())}")

        self.current_objective_name = initial_objective
        self.stagnation_threshold = stagnation_threshold
        self.stagnation_window = stagnation_window
        self.diversity_threshold = diversity_threshold
        self.cycle_history_size = cycle_history_size

        # Cycle tracking
        self.cycle_number = 0
        self.cycle_history: deque = deque(maxlen=cycle_history_size)
        self.metrics_history: deque = deque(maxlen=cycle_history_size)

        # Stagnation detection
        self.consecutive_low_improvement = 0
        self.stagnation_detected = False

        # Diversity tracking
        self.change_type_counts: Dict[str, int] = {
            "add": 0,
            "refactor": 0,
            "delete": 0,
            "optimize": 0
        }

        # Improvement rate tracking
        self.previous_capability_score: Optional[float] = None

    def record_cycle(
        self,
        changes: List[Dict[str, Any]],
        capability_scores: Dict[str, float],
        code_complexity: float,
        test_coverage: float
    ) -> Dict[str, Any]:
        """
        Record metrics for a single cycle.

        Args:
            changes: List of change dictionaries, each with a 'type' key ('add', 'refactor', 'delete', 'optimize').
            capability_scores: Dictionary mapping capability names to their scores.
            code_complexity: Current code complexity metric.
            test_coverage: Current test coverage percentage.

        Returns:
            Dictionary with cycle metrics.
        """
        self.cycle_number += 1
        total_capabilities = len(capability_scores)
        avg_capability_score = sum(capability_scores.values()) / total_capabilities if total_capabilities > 0 else 0.0

        # Count change types
        change_type_counts = {"add": 0, "refactor": 0, "delete": 0, "optimize": 0}
        for change in changes:
            change_type = change.get("type", "add")
            if change_type in change_type_counts:
                change_type_counts[change_type] += 1
            else:
                change_type_counts[change_type] = 1

        # Update cumulative counts
        for ctype, count in change_type_counts.items():
            self.change_type_counts[ctype] += count

        # Calculate diversity score (entropy-based)
        total_changes = sum(change_type_counts.values())
        if total_changes > 0:
            proportions = [count / total_changes for count in change_type_counts.values() if count > 0]
            diversity_score = -sum(p * math.log2(p) for p in proportions) / math.log2(4)
        else:
            diversity_score = 0.0

        # Calculate improvement rate
        if self.previous_capability_score is not None:
            improvement_rate = (avg_capability_score - self.previous_capability_score) / abs(self.previous_capability_score) if self.previous_capability_score != 0 else 0.0
        else:
            improvement_rate = 0.0

        self.previous_capability_score = avg_capability_score

        # Store cycle metrics
        cycle_metrics = {
            "cycle": self.cycle_number,
            "timestamp": time.time(),
            "total_changes": total_changes,
            "change_type_counts": change_type_counts,
            "diversity_score": diversity_score,
            "avg_capability_score": avg_capability_score,
            "total_capabilities": total_capabilities,
            "code_complexity": code_complexity,
            "test_coverage": test_coverage,
            "improvement_rate": improvement_rate
        }

        self.cycle_history.append(cycle_metrics)
        self.metrics_history.append(cycle_metrics)

        # Detect stagnation
        self._detect_stagnation(improvement_rate, diversity_score)

        # Adjust objective if needed
        if self.stagnation_detected:
            self._adjust_objective()

        return cycle_metrics

    def _detect_stagnation(self, improvement_rate: float, diversity_score: float) -> None:
        """
        Detect stagnation based on improvement rate and diversity.

        Stagnation is detected if:
        - Improvement rate is below threshold for N consecutive cycles, OR
        - Diversity score is below threshold for the current cycle.
        """
        # Check improvement rate stagnation
        if improvement_rate < self.stagnation_threshold:
            self.consecutive_low_improvement += 1
        else:
            self.consecutive_low_improvement = 0

        improvement_stagnation = self.consecutive_low_improvement >= self.stagnation_window

        # Check diversity stagnation
        diversity_stagnation = diversity_score < self.diversity_threshold

        self.stagnation_detected = improvement_stagnation or diversity_stagnation

    def _adjust_objective(self) -> None:
        """
        Dynamically adjust the objective function based on detected stagnation.

        Strategy:
        - If currently maximizing capability count, switch to minimizing code complexity.
        - If currently minimizing code complexity, switch to maximizing test coverage.
        - If currently maximizing test coverage, switch back to maximizing capability count.
        """
        if self.current_objective_name == "maximize_capability_count":
            new_objective = "minimize_code_complexity"
        elif self.current_objective_name == "minimize_code_complexity":
            new_objective = "maximize_test_coverage"
        else:  # maximize_test_coverage
            new_objective = "maximize_capability_count"

        print(f"Stagnation detected at cycle {self.cycle_number}. Switching objective from "
              f"'{self.current_objective_name}' to '{new_objective}'.")

        self.current_objective_name = new_objective
        self.stagnation_detected = False  # Reset stagnation flag after adjustment
        self.consecutive_low_improvement = 0  # Reset counter

    def get_current_objective(self) -> Dict[str, Any]:
        """
        Return the active objective function and its parameters.

        Returns:
            Dictionary with keys 'name', 'func', 'params', 'description'.
        """
        objective_info = self.OBJECTIVES[self.current_objective_name].copy()
        objective_info["name"] = self.current_objective_name
        return objective_info

    def evaluate_current_state(self, params: Dict[str, Any]) -> float:
        """
        Evaluate the current state using the active objective function.

        Args:
            params: Parameters needed by the objective function.

        Returns:
            Objective value (higher is better).
        """
        objective_info = self.get_current_objective()
        func = objective_info["func"]
        return func(params)

    def get_summary(self) -> Dict[str, Any]:
        """
        Return a summary of the meta-evaluation loop state.

        Returns:
            Dictionary with key metrics and state information.
        """
        return {
            "cycle_number": self.cycle_number,
            "current_objective": self.current_objective_name,
            "stagnation_detected": self.stagnation_detected,
            "consecutive_low_improvement": self.consecutive_low_improvement,
            "change_type_counts": self.change_type_counts,
            "total_changes": sum(self.change_type_counts.values()),
            "recent_improvement_rates": [m["improvement_rate"] for m in self.metrics_history],
            "recent_diversity_scores": [m["diversity_score"] for m in self.metrics_history]
        }

    def export_aggregated_statistics(self, n_cycles: int = 10) -> Dict[str, Any]:
        """
        Export aggregated performance statistics over the last N cycles.
        This method is designed to be called by the meta-mutation engine to get
        the data needed for analysis.

        Args:
            n_cycles: Number of recent cycles to consider for aggregation.
                     Defaults to 10. If fewer cycles are available, uses all available.

        Returns:
            Dictionary containing aggregated statistics including:
            - average_mutation_success_rate: Average improvement rate over the period
            - evolution_score_trend: List of evolution scores (avg capability scores) over the period
            - diversity_trend: List of diversity scores over the period
            - total_cycles_analyzed: Number of cycles actually analyzed
            - current_objective: The active objective name
            - stagnation_status: Whether stagnation is currently detected
        """
        # Get the last n_cycles from metrics_history
        recent_metrics = list(self.metrics_history)
        if len(recent_metrics) > n_cycles:
            recent_metrics = recent_metrics[-n_cycles:]

        if not recent_metrics:
            return {
                "average_mutation_success_rate": 0.0,
                "evolution_score_trend": [],
                "diversity_trend": [],
                "total_cycles_analyzed": 0,
                "current_objective": self.current_objective_name,
                "stagnation_status": self.stagnation_detected
            }

        # Calculate average mutation success rate (average improvement rate)
        improvement_rates = [m["improvement_rate"] for m in recent_metrics]
        average_mutation_success_rate = sum(improvement_rates) / len(improvement_rates)

        # Get evolution score trend (avg capability scores)
        evolution_score_trend = [m["avg_capability_score"] for m in recent_metrics]

        # Get diversity trend
        diversity_trend = [m["diversity_score"] for m in recent_metrics]

        return {
            "average_mutation_success_rate": average_mutation_success_rate,
            "evolution_score_trend": evolution_score_trend,
            "diversity_trend": diversity_trend,
            "total_cycles_analyzed": len(recent_metrics),
            "current_objective": self.current_objective_name,
            "stagnation_status": self.stagnation_detected
        }

# Example usage (if run as script)
if __name__ == "__main__":
    # Create meta-evaluation loop
    meta_loop = MetaEvaluationLoop(
        initial_objective="maximize_capability_count",
        stagnation_threshold=0.02,
        stagnation_window=3,
        diversity_threshold=0.3
    )

    # Simulate cycles
    for cycle in range(10):
        # Simulate changes (random types)
        import random
        changes = []
        for _ in range(random.randint(1, 5)):
            change_type = random.choice(["add", "refactor", "delete", "optimize"])
            changes.append({"type": change_type})

        # Simulate capability scores
        capability_scores = {
            f"cap_{i}": random.uniform(0.5, 1.0) for i in range(random.randint(3, 8))
        }

        # Simulate metrics
        code_complexity = random.uniform(1, 10)
        test_coverage = random.uniform(50, 100)

        # Record cycle
        metrics = meta_loop.record_cycle(changes, capability_scores, code_complexity, test_coverage)
        print(f"Cycle {metrics['cycle']}: improvement_rate={metrics['improvement_rate']:.4f}, "
              f"diversity={metrics['diversity_score']:.4f}, objective={meta_loop.current_objective_name}")

    # Get current objective
    current_obj = meta_loop.get_current_objective()
    print(f"\nCurrent objective: {current_obj['name']} - {current_obj['description']}")

    # Get summary
    summary = meta_loop.get_summary()
    print(f"Summary: {summary}")

    # Test the new export method
    print("\nExporting aggregated statistics for last 5 cycles:")
    stats = meta_loop.export_aggregated_statistics(n_cycles=5)
    print(f"Aggregated Statistics: {stats}")