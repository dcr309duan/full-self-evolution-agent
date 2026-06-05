from typing import Dict, List, Any, Optional
from collections import deque, Counter
import time

class SelfEvaluationLoop:
    """
    Self-evaluation loop that tracks per-capability scores and improvement rates,
    and reports them to the meta-evaluation loop.
    """

    def __init__(self, history_size: int = 10):
        """
        Initialize the self-evaluation loop.

        Args:
            history_size: Number of recent cycles to track for diversity metrics.
        """
        self.capability_scores: Dict[str, float] = {}
        self.improvement_rates: Dict[str, float] = {}
        self.change_history: deque = deque(maxlen=history_size)
        self.history_size = history_size
        self.cycle_count = 0

    def update_capability_score(self, capability: str, score: float) -> None:
        """
        Update the score for a specific capability.

        Args:
            capability: Name of the capability.
            score: Score value (0-100).
        """
        if not 0 <= score <= 100:
            raise ValueError(f"Score must be between 0 and 100, got {score}")
        old_score = self.capability_scores.get(capability, None)
        self.capability_scores[capability] = score

        # Update improvement rate
        if old_score is not None and old_score != 0:
            improvement = (score - old_score) / old_score
            self.improvement_rates[capability] = improvement
        else:
            self.improvement_rates[capability] = 0.0

    def get_capability_scores(self) -> Dict[str, float]:
        """
        Return a dictionary of capability names to their current scores.

        Returns:
            Dict mapping capability names to scores (0-100).
        """
        return dict(self.capability_scores)

    def get_improvement_rates(self) -> Dict[str, float]:
        """
        Return a dictionary of capability names to their improvement rates.

        Returns:
            Dict mapping capability names to improvement rates (as decimal fractions).
        """
        return dict(self.improvement_rates)

    def record_change(self, change_type: str, details: Optional[Dict[str, Any]] = None) -> None:
        """
        Record a change event for diversity tracking.

        Args:
            change_type: Type of change (e.g., 'parameter_update', 'architecture_change', 'data_augmentation').
            details: Optional additional details about the change.
        """
        self.change_history.append({
            'type': change_type,
            'timestamp': time.time(),
            'details': details or {}
        })
        self.cycle_count += 1

    def get_change_diversity(self) -> int:
        """
        Calculate the diversity of change types in the last N cycles.

        Returns:
            Count of unique change types in the recent history.
        """
        if not self.change_history:
            return 0
        change_types = [entry['type'] for entry in self.change_history]
        return len(set(change_types))

    def get_change_type_counts(self) -> Dict[str, int]:
        """
        Get the frequency of each change type in the recent history.

        Returns:
            Dict mapping change type names to their counts.
        """
        if not self.change_history:
            return {}
        change_types = [entry['type'] for entry in self.change_history]
        return dict(Counter(change_types))

    def report_to_meta_evaluation(self) -> Dict[str, Any]:
        """
        Compile and return a report for the meta-evaluation loop.

        Returns:
            Dict containing capability scores, improvement rates, and change diversity.
        """
        report = {
            'capability_scores': self.get_capability_scores(),
            'improvement_rates': self.get_improvement_rates(),
            'change_diversity': self.get_change_diversity(),
            'change_type_counts': self.get_change_type_counts(),
            'cycle_count': self.cycle_count,
            'timestamp': time.time()
        }
        return report

    def reset_history(self) -> None:
        """Reset the change history and cycle counter."""
        self.change_history.clear()
        self.cycle_count = 0

    def __repr__(self) -> str:
        return (f"SelfEvaluationLoop(capabilities={list(self.capability_scores.keys())}, "
                f"cycles={self.cycle_count}, diversity={self.get_change_diversity()})")