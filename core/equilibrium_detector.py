"""
core/equilibrium_detector.py

A self-contained equilibrium detector that monitors module interaction scores
over a sliding window. Uses only standard library (no external imports).
Tracks per-module improvement potential and declares Nash equilibrium when
no single-module change improves the system by >5% for 3 consecutive cycles.
Outputs a list of module pairs that are stuck.
"""

from collections import deque
from typing import List, Tuple, Dict, Optional

class EquilibriumDetector:
    """
    Detects Nash equilibrium in a system of interacting modules by monitoring
    improvement potential over a sliding window of cycles.
    """

    def __init__(self, window_size: int = 10, improvement_threshold: float = 5.0,
                 consecutive_cycles: int = 3):
        """
        Initialize the equilibrium detector.

        Args:
            window_size: Number of recent cycles to keep in the sliding window.
            improvement_threshold: Minimum improvement percentage to consider a change beneficial.
            consecutive_cycles: Number of consecutive cycles with no significant improvement
                                to declare equilibrium.
        """
        self.window_size = window_size
        self.improvement_threshold = improvement_threshold
        self.consecutive_cycles = consecutive_cycles

        # Sliding window of module interaction scores: list of dicts
        # Each dict maps module pair (tuple) to score
        self.score_history: deque = deque(maxlen=window_size)

        # Per-module improvement potential history: list of dicts
        # Each dict maps module name to best possible improvement percentage
        self.improvement_history: deque = deque(maxlen=consecutive_cycles)

        # Current cycle counter
        self.cycle_count = 0

        # Flag for equilibrium state
        self.in_equilibrium = False

        # Stuck module pairs (those with no improvement potential)
        self.stuck_pairs: List[Tuple[str, str]] = []

    def record_scores(self, scores: Dict[Tuple[str, str], float]) -> None:
        """
        Record module interaction scores for the current cycle.

        Args:
            scores: Dictionary mapping module pairs (tuple) to their interaction score.
        """
        self.score_history.append(scores)
        self.cycle_count += 1

    def _compute_improvement_potential(self) -> Dict[str, float]:
        """
        Compute the maximum possible improvement percentage for each module
        based on the current and previous scores.

        Returns:
            Dictionary mapping module name to its improvement potential percentage.
        """
        if len(self.score_history) < 2:
            return {}

        current_scores = self.score_history[-1]
        previous_scores = self.score_history[-2]

        # Collect all unique modules
        modules = set()
        for (mod1, mod2) in current_scores:
            modules.add(mod1)
            modules.add(mod2)

        improvement_potential = {}
        for module in modules:
            # Find all pairs involving this module
            module_pairs = [(m1, m2) for (m1, m2) in current_scores
                           if m1 == module or m2 == module]

            if not module_pairs:
                improvement_potential[module] = 0.0
                continue

            # Compute average improvement potential across all pairs
            total_improvement = 0.0
            for pair in module_pairs:
                current_val = current_scores.get(pair, 0.0)
                previous_val = previous_scores.get(pair, 0.0)

                if previous_val > 0:
                    improvement = ((current_val - previous_val) / previous_val) * 100.0
                else:
                    improvement = 0.0 if current_val == 0 else 100.0

                total_improvement += improvement

            avg_improvement = total_improvement / len(module_pairs)
            improvement_potential[module] = avg_improvement

        return improvement_potential

    def _find_stuck_pairs(self) -> List[Tuple[str, str]]:
        """
        Identify module pairs that have shown no significant improvement
        over the entire sliding window.

        Returns:
            List of module pairs that are stuck.
        """
        if len(self.score_history) < self.window_size:
            return []

        # Get the first and last scores in the window
        first_scores = self.score_history[0]
        last_scores = self.score_history[-1]

        stuck = []
        for pair in last_scores:
            if pair in first_scores:
                initial = first_scores[pair]
                final = last_scores[pair]
                if initial > 0:
                    change = ((final - initial) / initial) * 100.0
                else:
                    change = 0.0 if final == 0 else 100.0

                # Consider stuck if change is less than threshold
                if abs(change) < self.improvement_threshold:
                    stuck.append(pair)

        return stuck

    def check_equilibrium(self) -> bool:
        """
        Check if the system has reached Nash equilibrium.

        Returns:
            True if equilibrium is detected, False otherwise.
        """
        if self.cycle_count < 2:
            return False

        # Compute improvement potential for current cycle
        improvement = self._compute_improvement_potential()
        self.improvement_history.append(improvement)

        # Need at least consecutive_cycles of data
        if len(self.improvement_history) < self.consecutive_cycles:
            return False

        # Check if no module has improvement potential above threshold
        # for consecutive_cycles
        all_below_threshold = True
        for cycle_improvement in self.improvement_history:
            for module, potential in cycle_improvement.items():
                if potential > self.improvement_threshold:
                    all_below_threshold = False
                    break
            if not all_below_threshold:
                break

        if all_below_threshold:
            self.in_equilibrium = True
            self.stuck_pairs = self._find_stuck_pairs()
            return True

        self.in_equilibrium = False
        return False

    def get_stuck_pairs(self) -> List[Tuple[str, str]]:
        """
        Get the list of module pairs that are stuck.

        Returns:
            List of module pairs (tuples) that are stuck.
        """
        return self.stuck_pairs.copy()

    def get_module_improvement_potentials(self) -> Dict[str, float]:
        """
        Get the current improvement potential for each module.

        Returns:
            Dictionary mapping module name to its improvement potential percentage.
        """
        return self._compute_improvement_potential()

    def reset(self) -> None:
        """Reset the detector to its initial state."""
        self.score_history.clear()
        self.improvement_history.clear()
        self.cycle_count = 0
        self.in_equilibrium = False
        self.stuck_pairs = []

    def get_summary(self) -> Dict:
        """
        Get a summary of the current state.

        Returns:
            Dictionary containing cycle count, equilibrium status, stuck pairs,
            and improvement potentials.
        """
        return {
            'cycle_count': self.cycle_count,
            'in_equilibrium': self.in_equilibrium,
            'stuck_pairs': self.stuck_pairs,
            'improvement_potentials': self.get_module_improvement_potentials(),
            'window_size': self.window_size,
            'improvement_threshold': self.improvement_threshold,
            'consecutive_cycles': self.consecutive_cycles
        }