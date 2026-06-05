from typing import List, Dict, Any, Optional
from collections import defaultdict
import math


class MetaCognitiveEvaluator:
    """
    Meta-cognitive evaluator that tracks fitness scores and capability changes
    across cycles, and identifies low-impact modules for pruning.
    """

    def __init__(self, initial_fitness: Optional[float] = None):
        """
        Initialize the evaluator.

        Args:
            initial_fitness: Optional initial fitness score from an external fitness function.
                            If None, defaults to 0.
        """
        self.fitness_log: List[float] = []
        self.capability_count_log: List[int] = []
        self.capability_usage: Dict[str, int] = defaultdict(int)
        self.capability_fitness_contribution: Dict[str, float] = defaultdict(float)
        self.cycle_counter: int = 0
        self.pruning_candidates: List[str] = []

        # Initialize fitness log with the provided initial fitness or 0
        if initial_fitness is not None:
            self.fitness_log.append(initial_fitness)
        else:
            self.fitness_log.append(0.0)

        # Initialize capability count log with 0
        self.capability_count_log.append(0)

    def record_cycle(self, fitness_score: float, capability_count: int,
                     capability_updates: Optional[Dict[str, float]] = None) -> None:
        """
        Record a new cycle's fitness score and capability count.

        Args:
            fitness_score: The fitness score for this cycle.
            capability_count: The number of capabilities present in this cycle.
            capability_updates: Optional dictionary mapping capability names to their
                               fitness contribution for this cycle.
        """
        self.cycle_counter += 1
        self.fitness_log.append(fitness_score)
        self.capability_count_log.append(capability_count)

        # Update capability usage and fitness contribution tracking
        if capability_updates:
            for cap_name, contribution in capability_updates.items():
                self.capability_usage[cap_name] += 1
                self.capability_fitness_contribution[cap_name] += contribution

        # Every 10 cycles, perform evaluation
        if self.cycle_counter % 10 == 0:
            self._evaluate_and_prune()

    def _evaluate_and_prune(self) -> None:
        """
        Evaluate the ratio of fitness improvement to new capabilities added
        over the last 10 cycles. If ratio < 0.1, flag low-impact modules for pruning.
        """
        # Need at least 11 entries (initial + 10 cycles) to compute
        if len(self.fitness_log) < 11 or len(self.capability_count_log) < 11:
            return

        # Get fitness and capability counts from 10 cycles ago and current
        fitness_10_cycles_ago = self.fitness_log[-11]
        current_fitness = self.fitness_log[-1]
        capabilities_10_cycles_ago = self.capability_count_log[-11]
        current_capabilities = self.capability_count_log[-1]

        fitness_improvement = current_fitness - fitness_10_cycles_ago
        new_capabilities_added = current_capabilities - capabilities_10_cycles_ago

        # Avoid division by zero
        if new_capabilities_added <= 0:
            return

        ratio = fitness_improvement / new_capabilities_added

        # If ratio is below threshold, identify low-impact capabilities for pruning
        if ratio < 0.1:
            self._identify_pruning_candidates()

    def _identify_pruning_candidates(self) -> None:
        """
        Identify capabilities with the lowest usage/fitness contribution ratio.
        These are candidates for pruning.
        """
        if not self.capability_usage:
            self.pruning_candidates = []
            return

        # Calculate average contribution per usage for each capability
        contribution_per_usage: Dict[str, float] = {}
        for cap_name in self.capability_usage:
            usage_count = self.capability_usage[cap_name]
            if usage_count > 0:
                contribution_per_usage[cap_name] = (
                    self.capability_fitness_contribution[cap_name] / usage_count
                )
            else:
                contribution_per_usage[cap_name] = 0.0

        # Sort capabilities by contribution per usage (ascending)
        sorted_caps = sorted(contribution_per_usage.items(), key=lambda x: x[1])

        # Select bottom 25% as pruning candidates (at least 1)
        num_candidates = max(1, len(sorted_caps) // 4)
        self.pruning_candidates = [cap for cap, _ in sorted_caps[:num_candidates]]

    def get_pruning_candidates(self) -> List[str]:
        """
        Get the current list of pruning candidates.

        Returns:
            List of capability names identified for potential pruning.
        """
        return self.pruning_candidates.copy()

    def get_fitness_log(self) -> List[float]:
        """
        Get the full fitness score log.

        Returns:
            List of fitness scores per cycle.
        """
        return self.fitness_log.copy()

    def get_capability_count_log(self) -> List[int]:
        """
        Get the full capability count log.

        Returns:
            List of capability counts per cycle.
        """
        return self.capability_count_log.copy()

    def get_current_cycle(self) -> int:
        """
        Get the current cycle number.

        Returns:
            Current cycle counter value.
        """
        return self.cycle_counter

    def reset(self, initial_fitness: Optional[float] = None) -> None:
        """
        Reset the evaluator to its initial state.

        Args:
            initial_fitness: Optional initial fitness score for the reset state.
        """
        self.fitness_log.clear()
        self.capability_count_log.clear()
        self.capability_usage.clear()
        self.capability_fitness_contribution.clear()
        self.cycle_counter = 0
        self.pruning_candidates.clear()

        if initial_fitness is not None:
            self.fitness_log.append(initial_fitness)
        else:
            self.fitness_log.append(0.0)

        self.capability_count_log.append(0)