"""Adaptive Parameter Controller

This module adjusts mutation rate and goal acceptance threshold based on trend data
from the meta-cognitive evaluator. It detects brittleness and stabilizes the system
by favoring core-stabilizing mutations.
"""

import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from collections import deque

logger = logging.getLogger(__name__)

# Default parameter values
DEFAULT_MUTATION_RATE = 0.1
DEFAULT_GOAL_ACCEPTANCE_THRESHOLD = 0.7

# Adjustment factors
BRITTLENESS_MUTATION_REDUCTION = 0.7  # Reduce by 30%
BRITTLENESS_THRESHOLD_INCREASE = 1.2  # Increase by 20%

# Stability detection
STABILITY_CYCLES_REQUIRED = 10
RELAXATION_STEP = 0.02  # Gradual relaxation per cycle


@dataclass
class ParameterState:
    """Current state of adaptive parameters."""
    mutation_rate: float = DEFAULT_MUTATION_RATE
    goal_acceptance_threshold: float = DEFAULT_GOAL_ACCEPTANCE_THRESHOLD
    is_brittle: bool = False
    stability_counter: int = 0
    relaxation_active: bool = False
    base_mutation_rate: float = DEFAULT_MUTATION_RATE
    base_goal_acceptance_threshold: float = DEFAULT_GOAL_ACCEPTANCE_THRESHOLD


@dataclass
class ParameterChangeLog:
    """Log entry for a parameter change."""
    cycle: int
    parameter: str
    old_value: float
    new_value: float
    reason: str


class AdaptiveParameterController:
    """Controls adaptive mutation rate and goal acceptance threshold."""

    def __init__(self, evaluator=None):
        self.evaluator = evaluator
        self.state = ParameterState()
        self.change_log: list[ParameterChangeLog] = []
        self.trend_history: deque = deque(maxlen=20)
        self.cycle_count = 0

    def update(self, trend_data: Optional[Dict[str, Any]] = None) -> None:
        """Main update method to adjust parameters based on trend data.

        Args:
            trend_data: Dictionary with trend information from meta_cognitive_evaluator.
                        Expected keys: 'brittleness', 'stability', 'trend_direction'
        """
        self.cycle_count += 1

        if trend_data is None and self.evaluator is not None:
            try:
                trend_data = self.evaluator.get_trend_data()
            except AttributeError:
                logger.warning("Evaluator has no get_trend_data method")
                return
        elif trend_data is None:
            logger.warning("No trend data provided and no evaluator set")
            return

        self._process_trend_data(trend_data)
        self._adjust_parameters()

    def _process_trend_data(self, trend_data: Dict[str, Any]) -> None:
        """Process incoming trend data and update internal state."""
        brittleness = trend_data.get('brittleness', 0.0)
        stability = trend_data.get('stability', 1.0)
        trend_direction = trend_data.get('trend_direction', 'stable')

        self.trend_history.append({
            'brittleness': brittleness,
            'stability': stability,
            'trend_direction': trend_direction
        })

        # Detect brittleness: high brittleness or negative trend
        self.state.is_brittle = (
            brittleness > 0.6 or
            trend_direction == 'deteriorating'
        )

        # Update stability counter
        if self.state.is_brittle:
            self.state.stability_counter = 0
            self.state.relaxation_active = False
        else:
            self.state.stability_counter += 1

    def _adjust_parameters(self) -> None:
        """Adjust parameters based on current state."""
        if self.state.is_brittle:
            self._apply_brittleness_response()
        elif self.state.stability_counter >= STABILITY_CYCLES_REQUIRED:
            self._apply_relaxation()
        else:
            # Maintain current parameters
            pass

    def _apply_brittleness_response(self) -> None:
        """Reduce mutation rate and increase threshold to favor core-stabilizing mutations."""
        # Calculate target values
        target_mutation = (
            self.state.base_mutation_rate * BRITTLENESS_MUTATION_REDUCTION
        )
        target_threshold = (
            self.state.base_goal_acceptance_threshold * BRITTLENESS_THRESHOLD_INCREASE
        )

        # Apply changes if different from current
        if abs(self.state.mutation_rate - target_mutation) > 0.001:
            old_rate = self.state.mutation_rate
            self.state.mutation_rate = target_mutation
            self._log_change('mutation_rate', old_rate, target_mutation,
                             "Brittleness detected: reducing mutation rate by 30%")

        if abs(self.state.goal_acceptance_threshold - target_threshold) > 0.001:
            old_threshold = self.state.goal_acceptance_threshold
            self.state.goal_acceptance_threshold = target_threshold
            self._log_change('goal_acceptance_threshold', old_threshold, target_threshold,
                             "Brittleness detected: increasing goal acceptance threshold by 20%")

        self.state.relaxation_active = False

    def _apply_relaxation(self) -> None:
        """Gradually relax parameters back to baseline when stability persists."""
        self.state.relaxation_active = True

        # Relax mutation rate toward baseline
        if self.state.mutation_rate < self.state.base_mutation_rate:
            new_rate = min(
                self.state.mutation_rate + RELAXATION_STEP,
                self.state.base_mutation_rate
            )
            old_rate = self.state.mutation_rate
            self.state.mutation_rate = new_rate
            self._log_change('mutation_rate', old_rate, new_rate,
                             f"Stability persists: relaxing mutation rate toward baseline")

        # Relax threshold toward baseline
        if self.state.goal_acceptance_threshold > self.state.base_goal_acceptance_threshold:
            new_threshold = max(
                self.state.goal_acceptance_threshold - RELAXATION_STEP,
                self.state.base_goal_acceptance_threshold
            )
            old_threshold = self.state.goal_acceptance_threshold
            self.state.goal_acceptance_threshold = new_threshold
            self._log_change('goal_acceptance_threshold', old_threshold, new_threshold,
                             f"Stability persists: relaxing goal acceptance threshold toward baseline")

        # Reset stability counter if fully relaxed
        if (abs(self.state.mutation_rate - self.state.base_mutation_rate) < 0.001 and
                abs(self.state.goal_acceptance_threshold - self.state.base_goal_acceptance_threshold) < 0.001):
            self.state.stability_counter = 0
            self.state.relaxation_active = False

    def _log_change(self, parameter: str, old_value: float, new_value: float, reason: str) -> None:
        """Log a parameter change with reasoning."""
        log_entry = ParameterChangeLog(
            cycle=self.cycle_count,
            parameter=parameter,
            old_value=round(old_value, 4),
            new_value=round(new_value, 4),
            reason=reason
        )
        self.change_log.append(log_entry)
        logger.info(
            f"Cycle {self.cycle_count}: {parameter} changed from {old_value:.4f} to {new_value:.4f} - {reason}"
        )

    def get_parameter_state(self) -> Dict[str, Any]:
        """Expose current parameter state for other modules to query.

        Returns:
            Dictionary with current parameter values and state information.
        """
        return {
            'mutation_rate': self.state.mutation_rate,
            'goal_acceptance_threshold': self.state.goal_acceptance_threshold,
            'is_brittle': self.state.is_brittle,
            'stability_counter': self.state.stability_counter,
            'relaxation_active': self.state.relaxation_active,
            'base_mutation_rate': self.state.base_mutation_rate,
            'base_goal_acceptance_threshold': self.state.base_goal_acceptance_threshold,
        }

    def get_change_log(self, last_n: Optional[int] = None) -> list[Dict[str, Any]]:
        """Retrieve parameter change logs.

        Args:
            last_n: If provided, return only the last N log entries.

        Returns:
            List of log entries as dictionaries.
        """
        logs = self.change_log
        if last_n is not None:
            logs = logs[-last_n:]
        return [
            {
                'cycle': entry.cycle,
                'parameter': entry.parameter,
                'old_value': entry.old_value,
                'new_value': entry.new_value,
                'reason': entry.reason
            }
            for entry in logs
        ]

    def reset_to_baseline(self) -> None:
        """Reset parameters to baseline values."""
        old_rate = self.state.mutation_rate
        old_threshold = self.state.goal_acceptance_threshold

        self.state.mutation_rate = self.state.base_mutation_rate
        self.state.goal_acceptance_threshold = self.state.base_goal_acceptance_threshold
        self.state.stability_counter = 0
        self.state.relaxation_active = False
        self.state.is_brittle = False

        if abs(old_rate - self.state.base_mutation_rate) > 0.001:
            self._log_change('mutation_rate', old_rate, self.state.base_mutation_rate,
                             "Manual reset to baseline")
        if abs(old_threshold - self.state.base_goal_acceptance_threshold) > 0.001:
            self._log_change('goal_acceptance_threshold', old_threshold,
                             self.state.base_goal_acceptance_threshold,
                             "Manual reset to baseline")

    def set_baseline(self, mutation_rate: float, goal_acceptance_threshold: float) -> None:
        """Set new baseline parameter values.

        Args:
            mutation_rate: New baseline mutation rate.
            goal_acceptance_threshold: New baseline goal acceptance threshold.
        """
        self.state.base_mutation_rate = mutation_rate
        self.state.base_goal_acceptance_threshold = goal_acceptance_threshold
        logger.info(f"Baseline parameters updated: mutation_rate={mutation_rate}, "
                    f"goal_acceptance_threshold={goal_acceptance_threshold}")