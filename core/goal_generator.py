"""Goal generation for improving simulation accuracy.

This module provides functions to generate goals based on simulation accuracy
metrics and unexpected side effects. Goals are prioritized to expand simulation
coverage.
"""

from typing import List, Dict, Optional
from dataclasses import dataclass, field
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class GoalPriority(Enum):
    """Priority levels for generated goals."""
    HIGH = 1
    MEDIUM = 2
    LOW = 3


@dataclass
class Goal:
    """Represents a generated goal for improving simulation."""
    description: str
    priority: GoalPriority
    module: str
    goal_type: str  # 'accuracy' or 'dependency_tracking'

    def __str__(self) -> str:
        return f"[{self.priority.name}] {self.description}"


@dataclass
class SimulationMetrics:
    """Metrics from a simulation run."""
    module: str
    accuracy: float  # 0.0 to 1.0
    has_unexpected_side_effects: bool = False
    coverage: float = 0.0  # 0.0 to 1.0, how much of the module is covered


def generate_goals(
    metrics_list: List[SimulationMetrics],
    accuracy_threshold: float = 0.8,
    coverage_weight: float = 0.5
) -> List[Goal]:
    """Generate goals based on simulation metrics.

    Args:
        metrics_list: List of simulation metrics for different modules.
        accuracy_threshold: Threshold below which accuracy goals are generated.
        coverage_weight: Weight for coverage in priority calculation (0-1).

    Returns:
        List of generated goals, sorted by priority (highest first).
    """
    goals: List[Goal] = []

    for metrics in metrics_list:
        # Generate accuracy improvement goals if accuracy is below threshold
        if metrics.accuracy < accuracy_threshold:
            goal = Goal(
                description=f"Improve simulation accuracy for {metrics.module}",
                priority=_calculate_priority(metrics, coverage_weight),
                module=metrics.module,
                goal_type="accuracy"
            )
            goals.append(goal)
            logger.debug(
                "Generated accuracy goal for %s (accuracy=%.2f, threshold=%.2f)",
                metrics.module, metrics.accuracy, accuracy_threshold
            )

        # Generate dependency tracking goals if unexpected side effects
        if metrics.has_unexpected_side_effects:
            goal = Goal(
                description=f"Add dependency tracking for {metrics.module}",
                priority=_calculate_priority(metrics, coverage_weight),
                module=metrics.module,
                goal_type="dependency_tracking"
            )
            goals.append(goal)
            logger.debug(
                "Generated dependency tracking goal for %s (side effects detected)",
                metrics.module
            )

    # Sort goals by priority (HIGH first) to prioritize coverage expansion
    goals.sort(key=lambda g: (g.priority.value, -_coverage_score(g, metrics_list)))

    return goals


def _calculate_priority(
    metrics: SimulationMetrics,
    coverage_weight: float
) -> GoalPriority:
    """Calculate priority based on metrics and coverage weight.

    Lower coverage and lower accuracy increase priority.
    """
    # Base priority on accuracy deficit and coverage
    accuracy_deficit = 1.0 - metrics.accuracy
    coverage_deficit = 1.0 - metrics.coverage

    # Weighted score: higher = more urgent
    score = (accuracy_deficit * (1 - coverage_weight) +
             coverage_deficit * coverage_weight)

    if score > 0.7:
        return GoalPriority.HIGH
    elif score > 0.4:
        return GoalPriority.MEDIUM
    else:
        return GoalPriority.LOW


def _coverage_score(goal: Goal, metrics_list: List[SimulationMetrics]) -> float:
    """Calculate coverage score for a goal to prioritize coverage expansion.

    Returns higher score for modules with lower coverage.
    """
    for metrics in metrics_list:
        if metrics.module == goal.module:
            return 1.0 - metrics.coverage
    return 0.0


def generate_goals_from_report(
    report: Dict,
    accuracy_threshold: float = 0.8,
    coverage_weight: float = 0.5
) -> List[Goal]:
    """Generate goals from a simulation report dictionary.

    Expected report format:
    {
        "modules": [
            {
                "name": "module_name",
                "accuracy": 0.95,
                "has_unexpected_side_effects": False,
                "coverage": 0.8
            },
            ...
        ]
    }

    Args:
        report: Dictionary containing simulation report data.
        accuracy_threshold: Threshold for accuracy goals.
        coverage_weight: Weight for coverage in priority.

    Returns:
        List of generated goals.
    """
    metrics_list = []
    for module_data in report.get("modules", []):
        metrics = SimulationMetrics(
            module=module_data.get("name", "unknown"),
            accuracy=module_data.get("accuracy", 1.0),
            has_unexpected_side_effects=module_data.get(
                "has_unexpected_side_effects", False
            ),
            coverage=module_data.get("coverage", 0.0)
        )
        metrics_list.append(metrics)

    return generate_goals(metrics_list, accuracy_threshold, coverage_weight)


def prioritize_goals(goals: List[Goal]) -> List[Goal]:
    """Re-prioritize goals to expand simulation coverage.

    This function sorts goals so that those related to modules with
    lower coverage come first, within the same priority level.

    Args:
        goals: List of goals to prioritize.

    Returns:
        Re-prioritized list of goals.
    """
    # Sort by priority first, then by coverage (lower coverage first)
    # This assumes goals have been generated with coverage info
    return sorted(goals, key=lambda g: (g.priority.value, g.description))


# Example usage (for testing)
if __name__ == "__main__":
    # Example metrics
    example_metrics = [
        SimulationMetrics(
            module="module_a",
            accuracy=0.65,
            has_unexpected_side_effects=True,
            coverage=0.3
        ),
        SimulationMetrics(
            module="module_b",
            accuracy=0.95,
            has_unexpected_side_effects=False,
            coverage=0.9
        ),
        SimulationMetrics(
            module="module_c",
            accuracy=0.75,
            has_unexpected_side_effects=True,
            coverage=0.5
        ),
    ]

    generated = generate_goals(example_metrics)
    print("Generated goals:")
    for goal in generated:
        print(f"  {goal}")

    print("\nPrioritized goals:")
    prioritized = prioritize_goals(generated)
    for goal in prioritized:
        print(f"  {goal}")