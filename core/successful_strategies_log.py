from datetime import datetime
import json
from typing import List, Dict, Optional

class SuccessfulStrategiesLog:
    """
    A structured log for successful mutation strategies, storing metadata per mutation outcome.
    Supports querying by cycle number and exporting to JSON.
    """

    def __init__(self):
        self._entries: List[Dict] = []

    def log_mutation(
        self,
        mutation_type: str,
        cycle_number: int,
        schema_alignment_score: float,
        test_coverage_impact: float,
        dependency_resolution_score: float,
        timestamp: Optional[datetime] = None
    ) -> None:
        """
        Log a successful mutation with structured metadata.

        Args:
            mutation_type: Type of mutation (e.g., 'schema_extension', 'test_addition')
            cycle_number: The cycle number during which the mutation occurred
            schema_alignment_score: Score between 0 and 1 indicating schema alignment
            test_coverage_impact: Score between 0 and 1 indicating test coverage impact
            dependency_resolution_score: Score between 0 and 1 indicating dependency resolution
            timestamp: Optional timestamp; defaults to current UTC time
        """
        # Validate scores are within [0, 1]
        for score, name in [
            (schema_alignment_score, "schema_alignment_score"),
            (test_coverage_impact, "test_coverage_impact"),
            (dependency_resolution_score, "dependency_resolution_score")
        ]:
            if not (0 <= score <= 1):
                raise ValueError(f"{name} must be between 0 and 1, got {score}")

        if timestamp is None:
            timestamp = datetime.utcnow()

        # Composite success score: weighted average (equal weights for simplicity)
        success_score = (
            schema_alignment_score * 0.4 +
            test_coverage_impact * 0.3 +
            dependency_resolution_score * 0.3
        )

        entry = {
            "mutation_type": mutation_type,
            "timestamp": timestamp.isoformat(),
            "cycle_number": cycle_number,
            "schema_alignment_score": schema_alignment_score,
            "test_coverage_impact": test_coverage_impact,
            "dependency_resolution_score": dependency_resolution_score,
            "success_score": round(success_score, 4)
        }

        self._entries.append(entry)

    def get_last_n_by_cycle(self, n: int) -> List[Dict]:
        """
        Retrieve the last N log entries sorted by cycle number descending.

        Args:
            n: Number of entries to retrieve

        Returns:
            List of up to N most recent entries by cycle number
        """
        sorted_entries = sorted(
            self._entries,
            key=lambda e: e["cycle_number"],
            reverse=True
        )
        return sorted_entries[:n]

    def get_all_entries(self) -> List[Dict]:
        """Return all logged entries in insertion order."""
        return self._entries.copy()

    def to_json(self, indent: int = 2) -> str:
        """Export all entries as a JSON string."""
        return json.dumps(self._entries, indent=indent)

    def clear(self) -> None:
        """Remove all entries from the log."""
        self._entries.clear()