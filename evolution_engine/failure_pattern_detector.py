from collections import defaultdict
from typing import List, Dict, Tuple, Optional
from enum import Enum


class Priority(Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class DebuggingGoal:
    def __init__(self, priority: Priority, description: str):
        self.priority = priority
        self.description = description

    def __repr__(self):
        return f"DebuggingGoal(priority={self.priority}, description='{self.description}')"


class FailurePatternDetector:
    """
    Detects recurring failure patterns across cycles and generates debugging goals.
    """

    def __init__(self):
        # Key: (error_type, module_name)
        # Value: list of cycle numbers where the failure occurred
        self._failure_log: Dict[Tuple[str, str], List[int]] = defaultdict(list)

    def log_failure(self, error_type: str, module_name: str, cycle_number: int) -> None:
        """
        Log a failure occurrence for a given (error_type, module_name) pair at a specific cycle.

        Args:
            error_type: Type/category of the error.
            module_name: Name of the module where the error occurred.
            cycle_number: The cycle number during which the failure occurred.
        """
        key = (error_type, module_name)
        if cycle_number not in self._failure_log[key]:
            self._failure_log[key].append(cycle_number)

    def get_recurring_patterns(self) -> List[Tuple[str, str, List[int]]]:
        """
        Identify all (error_type, module_name) pairs that have appeared in 3 or more consecutive cycles.

        Returns:
            A list of tuples, each containing (error_type, module_name, list_of_cycle_numbers)
            for patterns that meet the recurrence threshold.
        """
        recurring = []
        for (error_type, module_name), cycles in self._failure_log.items():
            sorted_cycles = sorted(cycles)
            if self._has_consecutive_occurrences(sorted_cycles, min_consecutive=3):
                recurring.append((error_type, module_name, sorted_cycles))
        return recurring

    def generate_debugging_goal(self, pattern: Tuple[str, str, List[int]]) -> DebuggingGoal:
        """
        Generate a debugging goal for a given failure pattern.

        Args:
            pattern: A tuple (error_type, module_name, cycle_numbers) representing a recurring failure.

        Returns:
            A DebuggingGoal with HIGH priority and a description referencing the failure pattern.
        """
        error_type, module_name, cycles = pattern
        description = (
            f"Recurring failure detected: error type '{error_type}' in module '{module_name}' "
            f"occurred in cycles {cycles}. Investigate and fix the root cause."
        )
        return DebuggingGoal(priority=Priority.HIGH, description=description)

    def _has_consecutive_occurrences(self, sorted_cycles: List[int], min_consecutive: int = 3) -> bool:
        """
        Check if the sorted list of cycle numbers contains at least `min_consecutive` consecutive integers.

        Args:
            sorted_cycles: Sorted list of cycle numbers.
            min_consecutive: Minimum number of consecutive occurrences required.

        Returns:
            True if at least `min_consecutive` consecutive cycles are present, False otherwise.
        """
        if len(sorted_cycles) < min_consecutive:
            return False

        consecutive_count = 1
        for i in range(1, len(sorted_cycles)):
            if sorted_cycles[i] == sorted_cycles[i - 1] + 1:
                consecutive_count += 1
                if consecutive_count >= min_consecutive:
                    return True
            else:
                consecutive_count = 1
        return False