"""Lightweight module interaction tracker for Nash equilibrium detection.

Maintains a matrix of module-to-module interaction scores (0.0 to 1.0)
that are updated based on success/failure of cross-module operations.
Supports querying current interaction state, reset, and decay of old scores.
"""

import time
import threading
from typing import Dict, Tuple, Optional, List, Any


class ModuleInteractionTracker:
    """Tracks and scores interactions between modules over time."""

    def __init__(self, decay_rate: float = 0.95, default_score: float = 0.5):
        """
        Initialize the tracker.

        Args:
            decay_rate: Multiplicative factor applied to old scores during decay (0-1).
            default_score: Initial score for new module pairs.
        """
        self._lock = threading.Lock()
        self._decay_rate = max(0.0, min(1.0, decay_rate))
        self._default_score = max(0.0, min(1.0, default_score))
        # Matrix: {(module_a, module_b): (score, last_update_timestamp)}
        self._interaction_matrix: Dict[Tuple[str, str], Tuple[float, float]] = {}
        # Track total interactions per module
        self._module_interaction_counts: Dict[str, int] = {}

    def _normalize_modules(self, module_a: str, module_b: str) -> Tuple[str, str]:
        """Normalize module pair to ensure consistent ordering."""
        if module_a < module_b:
            return (module_a, module_b)
        return (module_b, module_a)

    def _get_or_create_entry(self, module_a: str, module_b: str) -> Tuple[float, float]:
        """Get existing entry or create default entry for module pair."""
        key = self._normalize_modules(module_a, module_b)
        if key not in self._interaction_matrix:
            self._interaction_matrix[key] = (self._default_score, time.time())
        return self._interaction_matrix[key]

    def record_interaction(self, module_a: str, module_b: str, success: bool,
                           weight: float = 1.0) -> None:
        """
        Record an interaction between two modules and update their score.

        Args:
            module_a: Name of the first module.
            module_b: Name of the second module.
            success: Whether the interaction was successful.
            weight: Weight of this interaction (0.0 to 1.0).
        """
        weight = max(0.0, min(1.0, weight))
        with self._lock:
            key = self._normalize_modules(module_a, module_b)
            current_score, _ = self._get_or_create_entry(module_a, module_b)

            # Calculate adjustment based on success/failure
            adjustment = 0.1 * weight
            if success:
                new_score = min(1.0, current_score + adjustment)
            else:
                new_score = max(0.0, current_score - adjustment)

            self._interaction_matrix[key] = (new_score, time.time())

            # Update interaction counts
            self._module_interaction_counts[module_a] = \
                self._module_interaction_counts.get(module_a, 0) + 1
            self._module_interaction_counts[module_b] = \
                self._module_interaction_counts.get(module_b, 0) + 1

    def get_interaction_score(self, module_a: str, module_b: str) -> float:
        """
        Get the current interaction score between two modules.

        Args:
            module_a: Name of the first module.
            module_b: Name of the second module.

        Returns:
            Current interaction score (0.0 to 1.0).
        """
        with self._lock:
            score, _ = self._get_or_create_entry(module_a, module_b)
            return score

    def get_all_scores(self) -> Dict[Tuple[str, str], float]:
        """
        Get all current interaction scores.

        Returns:
            Dictionary mapping module pairs to their scores.
        """
        with self._lock:
            return {key: score for key, (score, _) in self._interaction_matrix.items()}

    def get_module_interaction_count(self, module_name: str) -> int:
        """
        Get the total number of interactions involving a module.

        Args:
            module_name: Name of the module.

        Returns:
            Total interaction count.
        """
        with self._lock:
            return self._module_interaction_counts.get(module_name, 0)

    def get_average_score_for_module(self, module_name: str) -> float:
        """
        Get the average interaction score for a module with all other modules.

        Args:
            module_name: Name of the module.

        Returns:
            Average interaction score (0.0 to 1.0), or default score if no interactions.
        """
        with self._lock:
            scores = []
            for (a, b), (score, _) in self._interaction_matrix.items():
                if a == module_name or b == module_name:
                    scores.append(score)
            if not scores:
                return self._default_score
            return sum(scores) / len(scores)

    def get_interaction_matrix(self) -> Dict[str, Dict[str, float]]:
        """
        Get the full interaction matrix as a nested dictionary.

        Returns:
            Nested dictionary: {module_a: {module_b: score, ...}, ...}
        """
        with self._lock:
            matrix: Dict[str, Dict[str, float]] = {}
            for (a, b), (score, _) in self._interaction_matrix.items():
                if a not in matrix:
                    matrix[a] = {}
                if b not in matrix:
                    matrix[b] = {}
                matrix[a][b] = score
                matrix[b][a] = score
            return matrix

    def decay_scores(self, decay_factor: Optional[float] = None) -> None:
        """
        Apply decay to all scores, reducing them toward the default score.

        Args:
            decay_factor: Optional custom decay factor (overrides instance default).
        """
        factor = self._decay_rate if decay_factor is None else max(0.0, min(1.0, decay_factor))
        with self._lock:
            for key in self._interaction_matrix:
                current_score, timestamp = self._interaction_matrix[key]
                # Decay toward default score
                new_score = self._default_score + (current_score - self._default_score) * factor
                self._interaction_matrix[key] = (new_score, timestamp)

    def decay_old_scores(self, max_age_seconds: float,
                         decay_factor: Optional[float] = None) -> None:
        """
        Apply decay only to scores that haven't been updated recently.

        Args:
            max_age_seconds: Maximum age in seconds before a score is considered old.
            decay_factor: Optional custom decay factor (overrides instance default).
        """
        factor = self._decay_rate if decay_factor is None else max(0.0, min(1.0, decay_factor))
        current_time = time.time()
        with self._lock:
            for key in list(self._interaction_matrix.keys()):
                current_score, timestamp = self._interaction_matrix[key]
                age = current_time - timestamp
                if age > max_age_seconds:
                    new_score = self._default_score + (current_score - self._default_score) * factor
                    self._interaction_matrix[key] = (new_score, timestamp)

    def reset(self, keep_counts: bool = False) -> None:
        """
        Reset all interaction scores to default.

        Args:
            keep_counts: If True, keep interaction counts; otherwise reset them too.
        """
        with self._lock:
            current_time = time.time()
            for key in self._interaction_matrix:
                self._interaction_matrix[key] = (self._default_score, current_time)
            if not keep_counts:
                self._module_interaction_counts.clear()

    def reset_module(self, module_name: str) -> None:
        """
        Reset all interactions involving a specific module.

        Args:
            module_name: Name of the module to reset.
        """
        with self._lock:
            current_time = time.time()
            keys_to_reset = []
            for (a, b) in self._interaction_matrix:
                if a == module_name or b == module_name:
                    keys_to_reset.append((a, b))
            for key in keys_to_reset:
                self._interaction_matrix[key] = (self._default_score, current_time)
            self._module_interaction_counts.pop(module_name, None)

    def get_summary(self) -> Dict[str, Any]:
        """
        Get a summary of the current interaction state.

        Returns:
            Dictionary with summary statistics.
        """
        with self._lock:
            scores = [score for score, _ in self._interaction_matrix.values()]
            if not scores:
                return {
                    "total_pairs": 0,
                    "average_score": self._default_score,
                    "min_score": self._default_score,
                    "max_score": self._default_score,
                    "total_interactions": sum(self._module_interaction_counts.values()),
                    "active_modules": len(self._module_interaction_counts),
                }
            return {
                "total_pairs": len(scores),
                "average_score": sum(scores) / len(scores),
                "min_score": min(scores),
                "max_score": max(scores),
                "total_interactions": sum(self._module_interaction_counts.values()),
                "active_modules": len(self._module_interaction_counts),
            }

    def get_equilibrium_metrics(self) -> Dict[str, float]:
        """
        Get metrics useful for Nash equilibrium evaluation.

        Returns:
            Dictionary with equilibrium-related metrics.
        """
        with self._lock:
            scores = [score for score, _ in self._interaction_matrix.values()]
            if not scores:
                return {
                    "mean_score": self._default_score,
                    "score_variance": 0.0,
                    "high_interaction_ratio": 0.0,
                    "low_interaction_ratio": 0.0,
                }

            mean = sum(scores) / len(scores)
            variance = sum((s - mean) ** 2 for s in scores) / len(scores)
            high_count = sum(1 for s in scores if s >= 0.7)
            low_count = sum(1 for s in scores if s <= 0.3)

            return {
                "mean_score": mean,
                "score_variance": variance,
                "high_interaction_ratio": high_count / len(scores),
                "low_interaction_ratio": low_count / len(scores),
            }