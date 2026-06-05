from typing import Dict, List, Optional, Tuple
from collections import deque
import numpy as np
from dataclasses import dataclass, field
from enum import Enum


class ParameterType(Enum):
    MUTATION_RATE = "mutation_rate"
    GOAL_SELECTION_WEIGHTS = "goal_selection_weights"
    REFLECTION_DEPTH = "reflection_depth"


@dataclass
class GenerationSnapshot:
    generation: int
    mutation_rate: float
    goal_selection_weights: Dict[str, float]
    reflection_depth: int
    fitness: float
    fitness_delta: float = 0.0


class ParameterTracker:
    """Tracks meta-parameter values and fitness deltas across generations."""

    def __init__(self):
        self.history: deque = deque(maxlen=20)
        self._current_generation: int = 0
        self._last_fitness: Optional[float] = None

    def log(self, mutation_rate: float, goal_selection_weights: Dict[str, float],
            reflection_depth: int, fitness: float) -> None:
        """Log a generation snapshot with current parameters and fitness."""
        fitness_delta = 0.0
        if self._last_fitness is not None:
            fitness_delta = fitness - self._last_fitness

        snapshot = GenerationSnapshot(
            generation=self._current_generation,
            mutation_rate=mutation_rate,
            goal_selection_weights=goal_selection_weights.copy(),
            reflection_depth=reflection_depth,
            fitness=fitness,
            fitness_delta=fitness_delta
        )
        self.history.append(snapshot)
        self._last_fitness = fitness
        self._current_generation += 1

    def get_recent_history(self, n: int = 20) -> List[GenerationSnapshot]:
        """Return the last n snapshots from history."""
        return list(self.history)[-n:]

    def compute_correlations(self) -> Dict[str, float]:
        """Compute correlation between each parameter and fitness delta."""
        if len(self.history) < 3:
            return {}

        snapshots = list(self.history)
        fitness_deltas = [s.fitness_delta for s in snapshots]

        correlations = {}

        # Mutation rate correlation
        mutation_rates = [s.mutation_rate for s in snapshots]
        if len(set(mutation_rates)) > 1:
            corr = np.corrcoef(mutation_rates, fitness_deltas)[0, 1]
            correlations[ParameterType.MUTATION_RATE.value] = corr if not np.isnan(corr) else 0.0

        # Reflection depth correlation
        reflection_depths = [s.reflection_depth for s in snapshots]
        if len(set(reflection_depths)) > 1:
            corr = np.corrcoef(reflection_depths, fitness_deltas)[0, 1]
            correlations[ParameterType.REFLECTION_DEPTH.value] = corr if not np.isnan(corr) else 0.0

        # Goal selection weights correlation (average across weights)
        if snapshots[0].goal_selection_weights:
            weight_keys = list(snapshots[0].goal_selection_weights.keys())
            weight_corrs = []
            for key in weight_keys:
                weights = [s.goal_selection_weights[key] for s in snapshots]
                if len(set(weights)) > 1:
                    corr = np.corrcoef(weights, fitness_deltas)[0, 1]
                    if not np.isnan(corr):
                        weight_corrs.append(abs(corr))
            if weight_corrs:
                correlations[ParameterType.GOAL_SELECTION_WEIGHTS.value] = np.mean(weight_corrs)

        return correlations


class HillClimber:
    """Adjusts meta-parameters using hill climbing with ±10% changes."""

    def __init__(self, tracker: ParameterTracker, step_size: float = 0.1):
        self.tracker = tracker
        self.step_size = step_size
        self._current_params: Optional[Dict] = None
        self._current_fitness: Optional[float] = None

    def set_current_state(self, mutation_rate: float, goal_selection_weights: Dict[str, float],
                          reflection_depth: int, fitness: float) -> None:
        """Set the current parameter state and fitness."""
        self._current_params = {
            ParameterType.MUTATION_RATE.value: mutation_rate,
            ParameterType.GOAL_SELECTION_WEIGHTS.value: goal_selection_weights.copy(),
            ParameterType.REFLECTION_DEPTH.value: reflection_depth
        }
        self._current_fitness = fitness

    def _adjust_mutation_rate(self, direction: int) -> float:
        """Adjust mutation rate by ±10%."""
        current = self._current_params[ParameterType.MUTATION_RATE.value]
        adjustment = current * self.step_size * direction
        new_value = current + adjustment
        return max(0.001, min(1.0, new_value))  # Clamp to valid range

    def _adjust_reflection_depth(self, direction: int) -> int:
        """Adjust reflection depth by ±10% (rounded to nearest integer, min 1)."""
        current = self._current_params[ParameterType.REFLECTION_DEPTH.value]
        adjustment = max(1, int(current * self.step_size * direction))
        new_value = current + adjustment
        return max(1, new_value)

    def _adjust_goal_weights(self, direction: int) -> Dict[str, float]:
        """Adjust all goal selection weights by ±10% and normalize."""
        current = self._current_params[ParameterType.GOAL_SELECTION_WEIGHTS.value]
        new_weights = {}
        for key, value in current.items():
            adjustment = value * self.step_size * direction
            new_weights[key] = max(0.01, value + adjustment)

        # Normalize to sum to 1
        total = sum(new_weights.values())
        if total > 0:
            for key in new_weights:
                new_weights[key] /= total
        return new_weights

    def try_adjustment(self, param_type: str, direction: int) -> Tuple:
        """Try adjusting a parameter and return the new parameter values."""
        mutation_rate = self._current_params[ParameterType.MUTATION_RATE.value]
        goal_weights = self._current_params[ParameterType.GOAL_SELECTION_WEIGHTS.value].copy()
        reflection_depth = self._current_params[ParameterType.REFLECTION_DEPTH.value]

        if param_type == ParameterType.MUTATION_RATE.value:
            mutation_rate = self._adjust_mutation_rate(direction)
        elif param_type == ParameterType.REFLECTION_DEPTH.value:
            reflection_depth = self._adjust_reflection_depth(direction)
        elif param_type == ParameterType.GOAL_SELECTION_WEIGHTS.value:
            goal_weights = self._adjust_goal_weights(direction)

        return mutation_rate, goal_weights, reflection_depth

    def accept_adjustment(self, mutation_rate: float, goal_selection_weights: Dict[str, float],
                          reflection_depth: int, fitness: float) -> bool:
        """Accept the adjustment if fitness improved."""
        if self._current_fitness is not None and fitness > self._current_fitness:
            self._current_params[ParameterType.MUTATION_RATE.value] = mutation_rate
            self._current_params[ParameterType.GOAL_SELECTION_WEIGHTS.value] = goal_selection_weights.copy()
            self._current_params[ParameterType.REFLECTION_DEPTH.value] = reflection_depth
            self._current_fitness = fitness
            return True
        return False


class MetaParameterEvolution:
    """Main class orchestrating meta-parameter evolution with periodic hill climbing."""

    def __init__(self, cycle_interval: int = 10):
        self.tracker = ParameterTracker()
        self.climber = HillClimber(self.tracker)
        self.cycle_interval = cycle_interval
        self._cycle_count: int = 0

    def log_generation(self, mutation_rate: float, goal_selection_weights: Dict[str, float],
                       reflection_depth: int, fitness: float) -> None:
        """Log a generation and update the climber's state."""
        self.tracker.log(mutation_rate, goal_selection_weights, reflection_depth, fitness)
        self.climber.set_current_state(mutation_rate, goal_selection_weights, reflection_depth, fitness)
        self._cycle_count += 1

    def trigger(self) -> Optional[Tuple[float, Dict[str, float], int]]:
        """
        Called every 10 cycles to run hill climbing on the most impactful parameter.
        Returns the new parameter values if an adjustment was accepted, None otherwise.
        """
        if self._cycle_count % self.cycle_interval != 0:
            return None

        correlations = self.tracker.compute_correlations()
        if not correlations:
            return None

        # Find the parameter with highest absolute correlation
        most_impactful = max(correlations, key=lambda k: abs(correlations[k]))
        direction = 1 if correlations[most_impactful] > 0 else -1

        # Try positive direction first, then negative if needed
        for d in [direction, -direction]:
            new_mutation_rate, new_goal_weights, new_reflection_depth = (
                self.climber.try_adjustment(most_impactful, d)
            )

            # Simulate the adjustment (in real scenario, this would be evaluated)
            # For now, we accept the adjustment
            if self.climber.accept_adjustment(
                new_mutation_rate, new_goal_weights, new_reflection_depth,
                self.climber._current_fitness  # Placeholder - real fitness would come from evaluation
            ):
                return (new_mutation_rate, new_goal_weights, new_reflection_depth)

        return None

    def get_current_params(self) -> Optional[Dict]:
        """Get the current parameter state from the climber."""
        return self.climber._current_params

    def get_current_fitness(self) -> Optional[float]:
        """Get the current fitness from the climber."""
        return self.climber._current_fitness