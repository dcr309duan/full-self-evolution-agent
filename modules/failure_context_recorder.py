from typing import Dict, List, Optional
from dataclasses import dataclass, field, asdict
import json
import datetime
import os

@dataclass
class PredictedFailure:
    """Represents a predicted failure with context for pattern analysis."""
    mutation_description: str
    predicted_conflict_score: float
    affected_modules: List[str]
    reasoning: str
    timestamp: str = field(default_factory=lambda: datetime.datetime.utcnow().isoformat())

    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        return asdict(self)

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_dict(cls, data: Dict) -> 'PredictedFailure':
        """Create instance from dictionary."""
        return cls(
            mutation_description=data['mutation_description'],
            predicted_conflict_score=data['predicted_conflict_score'],
            affected_modules=data['affected_modules'],
            reasoning=data['reasoning'],
            timestamp=data.get('timestamp', datetime.datetime.utcnow().isoformat())
        )


class FailureContextRecorder:
    """Records predicted failures in the same format as actual failures for pattern analysis."""

    def __init__(self, log_file: Optional[str] = None):
        self.log_file = log_file or "predicted_failures_log.json"
        self._failures: List[PredictedFailure] = []
        self._load_existing()

    def _load_existing(self) -> None:
        """Load existing predicted failures from log file if it exists."""
        if os.path.exists(self.log_file):
            try:
                with open(self.log_file, 'r') as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        self._failures = [PredictedFailure.from_dict(item) for item in data]
                    else:
                        self._failures = []
            except (json.JSONDecodeError, IOError):
                self._failures = []

    def record_failure(self, mutation_description: str, predicted_conflict_score: float,
                       affected_modules: List[str], reasoning: str) -> PredictedFailure:
        """Record a predicted failure with all context fields.

        Args:
            mutation_description: Description of the mutation that caused the failure
            predicted_conflict_score: Score indicating likelihood of conflict (0.0 to 1.0)
            affected_modules: List of module names affected by the failure
            reasoning: Explanation of why the failure is predicted

        Returns:
            The created PredictedFailure instance
        """
        failure = PredictedFailure(
            mutation_description=mutation_description,
            predicted_conflict_score=predicted_conflict_score,
            affected_modules=affected_modules,
            reasoning=reasoning
        )
        self._failures.append(failure)
        self._persist()
        return failure

    def _persist(self) -> None:
        """Write all recorded failures to the log file."""
        try:
            with open(self.log_file, 'w') as f:
                json.dump([f.to_dict() for f in self._failures], f, indent=2)
        except IOError as e:
            print(f"Warning: Could not persist predicted failures to {self.log_file}: {e}")

    def get_all_failures(self) -> List[PredictedFailure]:
        """Return all recorded predicted failures."""
        return self._failures.copy()

    def get_failures_by_module(self, module_name: str) -> List[PredictedFailure]:
        """Get all predicted failures affecting a specific module.

        Args:
            module_name: Name of the module to filter by

        Returns:
            List of PredictedFailure instances affecting the given module
        """
        return [f for f in self._failures if module_name in f.affected_modules]

    def get_failures_by_score_threshold(self, min_score: float) -> List[PredictedFailure]:
        """Get all predicted failures with a conflict score above a threshold.

        Args:
            min_score: Minimum predicted conflict score (0.0 to 1.0)

        Returns:
            List of PredictedFailure instances meeting the threshold
        """
        return [f for f in self._failures if f.predicted_conflict_score >= min_score]

    def clear(self) -> None:
        """Clear all recorded failures and reset the log file."""
        self._failures = []
        self._persist()

    def export_as_actual_failures_format(self) -> List[Dict]:
        """Export predicted failures in a format compatible with actual failure logs.

        Returns:
            List of dictionaries with standardized failure format fields
        """
        return [
            {
                'type': 'predicted_failure',
                'mutation_description': f.mutation_description,
                'conflict_score': f.predicted_conflict_score,
                'affected_modules': f.affected_modules,
                'reasoning': f.reasoning,
                'timestamp': f.timestamp,
                'source': 'prediction_model'
            }
            for f in self._failures
        ]

    def __len__(self) -> int:
        return len(self._failures)

    def __repr__(self) -> str:
        return f"FailureContextRecorder(failures={len(self._failures)}, log_file='{self.log_file}')"