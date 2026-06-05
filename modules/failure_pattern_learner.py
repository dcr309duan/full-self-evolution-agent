"""Failure Pattern Learner Module.

Maintains a rolling window of mutation failures, classifies error types,
computes per-operator success rates, and adjusts operator weights accordingly.
"""

import json
import re
from collections import defaultdict, deque
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Constants
ROLLING_WINDOW_SIZE = 50
HIGH_FAILURE_THRESHOLD = 0.7
MEDIUM_FAILURE_THRESHOLD = 0.4
HIGH_FAILURE_DISABLE = True
MEDIUM_FAILURE_REDUCTION = 0.5
OPERATOR_WEIGHTS_FILE = "operator_weights.json"

# Regex patterns for error classification
ERROR_PATTERNS: Dict[str, re.Pattern] = {
    "import_error": re.compile(r"ImportError|ModuleNotFoundError", re.IGNORECASE),
    "type_mismatch": re.compile(
        r"TypeError|ValueError|AttributeError|KeyError|IndexError", re.IGNORECASE
    ),
    "infinite_loop": re.compile(
        r"timeout|infinite loop|maximum recursion depth|RuntimeError", re.IGNORECASE
    ),
    "syntax_error": re.compile(r"SyntaxError|IndentationError|TabError", re.IGNORECASE),
    "name_error": re.compile(r"NameError|UnboundLocalError", re.IGNORECASE),
    "zero_division": re.compile(r"ZeroDivisionError|FloatingPointError", re.IGNORECASE),
    "memory_error": re.compile(r"MemoryError|OutOfMemory", re.IGNORECASE),
}


class FailurePatternLearner:
    """Learns failure patterns from mutation testing results."""

    def __init__(self, window_size: int = ROLLING_WINDOW_SIZE):
        self.window_size = window_size
        # Rolling window: list of (operator_name, error_type) tuples
        self.failure_window: deque = deque(maxlen=window_size)
        # Per-operator statistics: {operator: {"success": int, "failure": int}}
        self.operator_stats: Dict[str, Dict[str, int]] = defaultdict(
            lambda: {"success": 0, "failure": 0}
        )
        # Current operator weights (adjusted)
        self.operator_weights: Dict[str, float] = {}
        # Load existing weights if available
        self._load_weights()

    def _load_weights(self) -> None:
        """Load operator weights from JSON file if exists."""
        path = Path(OPERATOR_WEIGHTS_FILE)
        if path.exists():
            try:
                with open(path, "r") as f:
                    data = json.load(f)
                    self.operator_weights = data.get("weights", {})
                    # Restore stats if present
                    stats = data.get("stats", {})
                    for op, s in stats.items():
                        self.operator_stats[op] = s
            except (json.JSONDecodeError, KeyError):
                self.operator_weights = {}

    def _save_weights(self) -> None:
        """Persist operator weights and stats to JSON file."""
        data = {
            "weights": self.operator_weights,
            "stats": dict(self.operator_stats),
        }
        with open(OPERATOR_WEIGHTS_FILE, "w") as f:
            json.dump(data, f, indent=2)

    def classify_error(self, error_message: str) -> str:
        """Classify an error message into a category.

        Args:
            error_message: The error text to classify.

        Returns:
            A string representing the error category.
        """
        for category, pattern in ERROR_PATTERNS.items():
            if pattern.search(error_message):
                return category
        return "other"

    def record_result(
        self, operator: str, success: bool, error_message: Optional[str] = None
    ) -> None:
        """Record a mutation result (success or failure with optional error).

        Args:
            operator: The mutation operator name.
            success: Whether the mutation was successful (i.e., killed).
            error_message: The error message if the mutation failed.
        """
        # Update operator stats
        if success:
            self.operator_stats[operator]["success"] += 1
        else:
            self.operator_stats[operator]["failure"] += 1
            error_type = self.classify_error(error_message or "")
            self.failure_window.append((operator, error_type))

        # Trim window if needed (deque does this automatically)
        # Recompute weights after each recording
        self._adjust_weights()

    def get_success_rate(self, operator: str) -> float:
        """Compute the success rate for a given operator.

        Args:
            operator: The operator name.

        Returns:
            Success rate as a float between 0 and 1. Returns 1.0 if no data.
        """
        stats = self.operator_stats.get(operator, {"success": 0, "failure": 0})
        total = stats["success"] + stats["failure"]
        if total == 0:
            return 1.0
        return stats["success"] / total

    def get_failure_rate(self, operator: str) -> float:
        """Compute the failure rate for a given operator.

        Args:
            operator: The operator name.

        Returns:
            Failure rate as a float between 0 and 1. Returns 0.0 if no data.
        """
        return 1.0 - self.get_success_rate(operator)

    def _adjust_weights(self) -> None:
        """Adjust operator weights based on failure rates.

        Operators with >70% failure rate are disabled (weight = 0).
        Operators with >40% failure rate have their weight reduced by 50%.
        """
        for operator in list(self.operator_stats.keys()):
            failure_rate = self.get_failure_rate(operator)
            current_weight = self.operator_weights.get(operator, 1.0)

            if failure_rate > HIGH_FAILURE_THRESHOLD:
                if HIGH_FAILURE_DISABLE:
                    new_weight = 0.0
                else:
                    new_weight = current_weight * 0.1
            elif failure_rate > MEDIUM_FAILURE_THRESHOLD:
                new_weight = current_weight * MEDIUM_FAILURE_REDUCTION
            else:
                # Keep existing weight or default to 1.0
                new_weight = current_weight if current_weight > 0 else 1.0

            self.operator_weights[operator] = new_weight

        # Persist updated weights
        self._save_weights()

    def get_operator_weight(self, operator: str) -> float:
        """Get the current weight for an operator.

        Args:
            operator: The operator name.

        Returns:
            Weight as a float (0.0 means disabled).
        """
        return self.operator_weights.get(operator, 1.0)

    def get_all_weights(self) -> Dict[str, float]:
        """Get all current operator weights.

        Returns:
            Dictionary mapping operator names to weights.
        """
        return dict(self.operator_weights)

    def get_failure_patterns(self) -> Dict[str, List[Tuple[str, str]]]:
        """Get failure patterns grouped by error type.

        Returns:
            Dictionary mapping error types to list of (operator, error_type) tuples.
        """
        patterns: Dict[str, List[Tuple[str, str]]] = defaultdict(list)
        for operator, error_type in self.failure_window:
            patterns[error_type].append((operator, error_type))
        return dict(patterns)

    def get_most_common_errors(self, top_n: int = 5) -> List[Tuple[str, int]]:
        """Get the most common error types in the current window.

        Args:
            top_n: Number of top error types to return.

        Returns:
            List of (error_type, count) tuples sorted by count descending.
        """
        error_counts: Dict[str, int] = defaultdict(int)
        for _, error_type in self.failure_window:
            error_counts[error_type] += 1
        sorted_errors = sorted(error_counts.items(), key=lambda x: x[1], reverse=True)
        return sorted_errors[:top_n]

    def get_lessons_learned(self) -> str:
        """Get a formatted string of the last 10 mutation failures with error types and affected files.

        Returns:
            A formatted string summarizing the last 10 failures for short-term memory.
        """
        if not self.failure_window:
            return "No failures recorded yet."

        # Get the last 10 failures
        recent_failures = list(self.failure_window)[-10:]

        lines = ["Lessons Learned (Last 10 Failures):"]
        for i, (operator, error_type) in enumerate(recent_failures, 1):
            lines.append(f"  {i}. Operator: {operator}, Error Type: {error_type}")

        return "\n".join(lines)

    def reset(self) -> None:
        """Reset all learned data."""
        self.failure_window.clear()
        self.operator_stats.clear()
        self.operator_weights.clear()
        self._save_weights()