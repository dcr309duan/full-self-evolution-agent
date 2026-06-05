import logging
from collections import defaultdict
from typing import Dict, List, Tuple, Set
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class FragilityHotspotMiner:
    """
    Tracks module pairs that are becoming hotspots over time,
    detects trends, and prioritizes refactoring goals.
    """

    def __init__(self, recurrence_threshold: int = 3, time_window_days: int = 30):
        self._pair_failures: Dict[Tuple[str, str], Dict[str, List[datetime]]] = defaultdict(lambda: defaultdict(list))
        self._recurrence_threshold = recurrence_threshold
        self._time_window_days = time_window_days

    def record_pair_failure(self, module_a: str, module_b: str, failure_type: str) -> None:
        """Record a failure for a module pair with a specific failure type."""
        pair_key = tuple(sorted([module_a, module_b]))
        self._pair_failures[pair_key][failure_type].append(datetime.now())
        logger.debug(f"Recorded {failure_type} failure for pair: {pair_key}")

    def get_pair_failure_count(self, module_a: str, module_b: str, failure_type: str = None) -> int:
        """Get failure count for a module pair, optionally filtered by failure type."""
        pair_key = tuple(sorted([module_a, module_b]))
        if pair_key not in self._pair_failures:
            return 0
        if failure_type:
            return len(self._pair_failures[pair_key].get(failure_type, []))
        return sum(len(times) for times in self._pair_failures[pair_key].values())

    def get_hotspot_pairs(self, min_failures: int = 3) -> List[Tuple[str, str, int]]:
        """Identify module pairs that are becoming hotspots based on failure count."""
        hotspots = []
        for pair_key, failure_types in self._pair_failures.items():
            total_failures = sum(len(times) for times in failure_types.values())
            if total_failures >= min_failures:
                hotspots.append((pair_key[0], pair_key[1], total_failures))
        return sorted(hotspots, key=lambda x: x[2], reverse=True)

    def detect_trends(self) -> List[Dict]:
        """
        Detect trends where the same pair appears in multiple failure types.
        Returns a list of trend descriptions.
        """
        trends = []
        for pair_key, failure_types in self._pair_failures.items():
            # Check if same pair appears in 3 different failure types
            if len(failure_types) >= 3:
                trend = {
                    "pair": pair_key,
                    "failure_types": list(failure_types.keys()),
                    "total_failures": sum(len(times) for times in failure_types.values()),
                    "description": f"Module pair {pair_key} appears in {len(failure_types)} different failure types"
                }
                trends.append(trend)
        return trends

    def get_recurrence_rate(self, module_a: str, module_b: str) -> float:
        """
        Calculate recurrence rate for a module pair based on failures in time window.
        Returns rate as failures per day.
        """
        pair_key = tuple(sorted([module_a, module_b]))
        if pair_key not in self._pair_failures:
            return 0.0
        
        all_times = []
        for times in self._pair_failures[pair_key].values():
            all_times.extend(times)
        
        if not all_times:
            return 0.0
        
        # Calculate time span in days
        time_span = (max(all_times) - min(all_times)).days
        if time_span == 0:
            return len(all_times)
        
        return len(all_times) / time_span

    def prioritize_refactoring_goals(self) -> List[Dict]:
        """
        Prioritize refactoring goals based on pair recurrence rate and trend detection.
        Returns a sorted list of refactoring recommendations.
        """
        goals = []
        
        # Get all pairs with failures
        for pair_key, failure_types in self._pair_failures.items():
            recurrence_rate = self.get_recurrence_rate(pair_key[0], pair_key[1])
            total_failures = sum(len(times) for times in failure_types.values())
            trend_count = len(failure_types)
            
            # Calculate priority score
            priority_score = (total_failures * 0.4) + (recurrence_rate * 0.3) + (trend_count * 0.3)
            
            goal = {
                "pair": pair_key,
                "total_failures": total_failures,
                "recurrence_rate": recurrence_rate,
                "trend_count": trend_count,
                "priority_score": priority_score,
                "failure_types": list(failure_types.keys()),
                "recommendation": self._generate_recommendation(pair_key, total_failures, recurrence_rate, trend_count)
            }
            goals.append(goal)
        
        # Sort by priority score descending
        return sorted(goals, key=lambda x: x["priority_score"], reverse=True)

    def _generate_recommendation(self, pair_key: Tuple[str, str], total_failures: int, 
                                  recurrence_rate: float, trend_count: int) -> str:
        """Generate a human-readable refactoring recommendation."""
        recommendations = []
        
        if total_failures >= 5:
            recommendations.append(f"High failure count ({total_failures})")
        if recurrence_rate > 1.0:
            recommendations.append(f"High recurrence rate ({recurrence_rate:.2f} failures/day)")
        if trend_count >= 3:
            recommendations.append(f"Multi-type failure trend ({trend_count} failure types)")
        
        if not recommendations:
            return "Monitor for future failures"
        
        return f"Prioritize refactoring: {', '.join(recommendations)}"

    def get_summary(self) -> Dict:
        """Get a summary of hotspot mining data."""
        return {
            "hotspot_pairs": self.get_hotspot_pairs(),
            "trends": self.detect_trends(),
            "refactoring_goals": self.prioritize_refactoring_goals(),
            "total_pairs_tracked": len(self._pair_failures)
        }


class DependencyFailureTracker:
    """
    Tracks and analyzes dependency validation failures to identify systemic issues.
    Distinguishes between circular dependency rejections and non-existent module rejections.
    Integrated with FragilityHotspotMiner for trend detection and refactoring prioritization.
    """

    def __init__(self):
        self._circular_rejections: Dict[str, int] = defaultdict(int)
        self._non_existent_rejections: Dict[str, int] = defaultdict(int)
        self._total_checks: int = 0
        self._hotspot_miner = FragilityHotspotMiner()

    def record_circular_rejection(self, module_name: str) -> None:
        """Record a circular dependency rejection for a module."""
        self._circular_rejections[module_name] += 1
        self._total_checks += 1
        # Record in hotspot miner with generic pair tracking
        self._hotspot_miner.record_pair_failure(module_name, "__circular__", "circular_dependency")
        logger.debug(f"Recorded circular rejection for module: {module_name}")

    def record_non_existent_rejection(self, module_name: str) -> None:
        """Record a non-existent module rejection for a module."""
        self._non_existent_rejections[module_name] += 1
        self._total_checks += 1
        # Record in hotspot miner with generic pair tracking
        self._hotspot_miner.record_pair_failure(module_name, "__non_existent__", "non_existent_module")
        logger.debug(f"Recorded non-existent rejection for module: {module_name}")

    def record_pair_failure(self, module_a: str, module_b: str, failure_type: str) -> None:
        """Record a failure for a specific module pair with a failure type."""
        self._total_checks += 1
        self._hotspot_miner.record_pair_failure(module_a, module_b, failure_type)
        logger.debug(f"Recorded {failure_type} failure for pair: ({module_a}, {module_b})")

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

        # Add hotspot miner insights
        hotspot_pairs = self._hotspot_miner.get_hotspot_pairs()
        for pair in hotspot_pairs[:5]:  # Top 5 hotspots
            issues.append(f"Hotspot pair ({pair[0]}, {pair[1]}) with {pair[2]} failures - consider refactoring")

        trends = self._hotspot_miner.detect_trends()
        for trend in trends:
            issues.append(f"Trend detected: {trend['description']}")

        return issues

    def get_hotspot_miner(self) -> FragilityHotspotMiner:
        """Get the fragility hotspot miner instance."""
        return self._hotspot_miner

    def reset(self) -> None:
        """Reset all tracking data."""
        self._circular_rejections.clear()
        self._non_existent_rejections.clear()
        self._total_checks = 0
        self._hotspot_miner = FragilityHotspotMiner()
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
            "systemic_issues": self.identify_systemic_issues(),
            "hotspot_miner": self._hotspot_miner.get_summary()
        }

# Global instance for use across the self-diagnosis module
dependency_failure_tracker = DependencyFailureTracker()