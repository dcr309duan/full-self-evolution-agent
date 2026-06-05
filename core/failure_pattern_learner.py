from collections import deque
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
import traceback


@dataclass
class FailureRecord:
    """Represents a single failure record with its context."""
    module_name: str
    error_type: str
    error_message: str
    timestamp: datetime = field(default_factory=datetime.now)
    traceback: Optional[str] = None
    context: Dict[str, Any] = field(default_factory=dict)


class FailurePatternLearner:
    """
    Tracks and analyzes failure patterns across modules.
    Provides access to recent failure records for mutation engine analysis.
    """

    def __init__(self, max_history: int = 1000):
        self._failures: deque[FailureRecord] = deque(maxlen=max_history)
        self._module_failure_counts: Dict[str, int] = {}

    def record_failure(
        self,
        module_name: str,
        error: Exception,
        context: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Record a failure occurrence with its context.

        Args:
            module_name: Name of the module where failure occurred
            error: The exception that was raised
            context: Optional dictionary with additional context information
        """
        record = FailureRecord(
            module_name=module_name,
            error_type=type(error).__name__,
            error_message=str(error),
            traceback=traceback.format_exc() if error.__traceback__ else None,
            context=context or {}
        )
        self._failures.append(record)
        self._module_failure_counts[module_name] = (
            self._module_failure_counts.get(module_name, 0) + 1
        )

    def get_recent_failures(self, count: int = 10) -> List[FailureRecord]:
        """
        Return the last `count` failure records with their associated module names and error contexts.

        This method is designed to be accessible from mutation_engine for failure pattern analysis.

        Args:
            count: Number of recent failures to retrieve (default: 10)

        Returns:
            List of FailureRecord objects sorted by most recent first
        """
        if count <= 0:
            return []

        recent = list(self._failures)[-count:]
        # Return in reverse chronological order (most recent first)
        return list(reversed(recent))

    def get_module_failure_count(self, module_name: str) -> int:
        """Get the total failure count for a specific module."""
        return self._module_failure_counts.get(module_name, 0)

    def get_all_module_failure_counts(self) -> Dict[str, int]:
        """Get failure counts for all modules."""
        return dict(self._module_failure_counts)

    def clear_history(self) -> None:
        """Clear all recorded failures and reset module counts."""
        self._failures.clear()
        self._module_failure_counts.clear()

    @property
    def total_failures(self) -> int:
        """Return the total number of recorded failures."""
        return len(self._failures)