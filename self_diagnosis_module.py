import logging
from collections import defaultdict
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)

class DependencyFailureTracker:
    """
    Tracks and analyzes dependency validation failures to identify systemic issues.
    Distinguishes between circular dependency rejections and non-existent module rejections.
    """

    def __init__(self):
        self._circular_rejections: Dict[str, int] = defaultdict(int)
        self._non_existent_rejections: Dict[str, int] = defaultdict(int)
        self._total_checks: int = 0

    def record_circular_rejection(self, module_name: str) -> None:
        """Record a circular dependency rejection for a module."""
        self._circular_rejections[module_name] += 1
        self._total_checks += 1
        logger.debug(f"Recorded circular rejection for module: {module_name}")

    def record_non_existent_rejection(self, module_name: str) -> None:
        """Record a non-existent module rejection for a module."""
        self._non_existent_rejections[module_name] += 1
        self._total_checks += 1
        logger.debug(f"Recorded non-existent rejection for module: {module_name}")

    def get_circular_rejection_count(self, module_name: str = None) -> int:
        """Get the count of circular rejections for a specific module or total."""
        if module_name:
            return self._circular_rejections.get(module_name, 0)
        return sum(self._circular_rejections.values())

    def get_non_existent_rejection_count(self, module_name: str = None) -> int:
        """Get the count of non-existent rejections for a specific module or total."""
        if module_name:
            return self._non_existent_rejections.get(module_name, 0)
        return sum(self._non_existent_rejections.values())

    def get_total_checks(self) -> int:
        """Get the total number of dependency checks performed."""
        return self._total_checks

    def get_failure_ratio(self) -> Tuple[float, float]:
        """
        Calculate the ratio of circular rejections and non-existent rejections to total checks.
        Returns (circular_ratio, non_existent_ratio).
        """
        if self._total_checks == 0:
            return (0.0, 0.0)
        circular_ratio = self.get_circular_rejection_count() / self._total_checks
        non_existent_ratio = self.get_non_existent_rejection_count() / self._total_checks
        return (circular_ratio, non_existent_ratio)

    def identify_systemic_issues(self, threshold: float = 0.1) -> List[str]:
        """
        Identify potential systemic issues based on failure patterns.
        Returns a list of warning messages.
        """
        issues = []
        circular_total = self.get_circular_rejection_count()
        non_existent_total = self.get_non_existent_rejection_count()

        if self._total_checks == 0:
            return issues

        # Check for high overall failure rate
        total_failures = circular_total + non_existent_total
        if total_failures / self._total_checks > threshold:
            issues.append(f"High overall dependency failure rate: {total_failures}/{self._total_checks}")

        # Check for disproportionate circular rejections
        if circular_total > non_existent_total * 2 and circular_total > 5:
            issues.append(f"Disproportionate circular dependency rejections ({circular_total}) vs non-existent ({non_existent_total}). Possible systemic circular dependency issue.")

        # Check for frequently failing modules
        for module, count in self._circular_rejections.items():
            if count > 3:
                issues.append(f"Module '{module}' has {count} circular rejections - consider reviewing its dependency graph.")

        for module, count in self._non_existent_rejections.items():
            if count > 3:
                issues.append(f"Module '{module}' has {count} non-existent rejections - verify module existence and import paths.")

        return issues

    def reset(self) -> None:
        """Reset all tracking data."""
        self._circular_rejections.clear()
        self._non_existent_rejections.clear()
        self._total_checks = 0
        logger.info("Dependency failure tracker reset.")

    def get_summary(self) -> Dict:
        """Get a summary of all tracked data."""
        return {
            "total_checks": self._total_checks,
            "circular_rejections": dict(self._circular_rejections),
            "non_existent_rejections": dict(self._non_existent_rejections),
            "circular_total": self.get_circular_rejection_count(),
            "non_existent_total": self.get_non_existent_rejection_count(),
            "failure_ratio": self.get_failure_ratio(),
            "systemic_issues": self.identify_systemic_issues()
        }

# Global instance for use across the self-diagnosis module
dependency_failure_tracker = DependencyFailureTracker()