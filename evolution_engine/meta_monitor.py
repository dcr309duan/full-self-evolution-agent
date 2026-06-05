"""Meta-monitor for detecting and responding to systemic failures across goal categories."""

from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple


class FailureCategoryTracker:
    """Tracks failures per category and detects consecutive failure patterns."""

    def __init__(self) -> None:
        self._failures: Dict[str, List[Tuple[datetime, str, str]]] = defaultdict(list)
        self._consecutive_counts: Dict[str, int] = defaultdict(int)

    def record_failure(self, category: str, goal_id: str, outcome: str) -> None:
        """Record a failure event for a given category."""
        self._failures[category].append((datetime.utcnow(), goal_id, outcome))
        self._consecutive_counts[category] += 1

    def record_success(self, category: str) -> None:
        """Reset consecutive failure count for a category on success."""
        self._consecutive_counts[category] = 0

    def detect_consecutive_failures(self, threshold: int = 3) -> List[str]:
        """Return categories with at least `threshold` consecutive failures."""
        return [
            cat for cat, count in self._consecutive_counts.items()
            if count >= threshold
        ]

    def trigger_reprioritization(self, categories: List[str]) -> Dict[str, Any]:
        """Mark all goals in affected categories as 'blocked' and set root cause flag.

        Returns a reprioritization command structure.
        """
        return {
            "action": "reprioritize",
            "affected_categories": categories,
            "goal_status": "blocked",
            "requires_root_cause": True,
            "timestamp": datetime.utcnow().isoformat(),
        }

    def generate_root_cause_hypothesis(self, category: str) -> Optional[Dict[str, Any]]:
        """Analyze the last 3 failed goals in a category and produce a hypothesis.

        Returns a structured hypothesis dict or None if insufficient data.
        """
        failures = self._failures.get(category, [])
        if len(failures) < 3:
            return None

        recent_failures = failures[-3:]
        goal_ids = [f[1] for f in recent_failures]
        outcomes = [f[2] for f in recent_failures]

        # Simple heuristic: check for common outcome patterns
        common_outcomes = set(outcomes)
        if len(common_outcomes) == 1:
            suspected_root_cause = f"Consistent failure mode: {common_outcomes.pop()}"
        else:
            suspected_root_cause = f"Multiple failure modes observed: {', '.join(outcomes)}"

        evidence = {
            "category": category,
            "recent_goal_ids": goal_ids,
            "recent_outcomes": outcomes,
            "consecutive_failure_count": self._consecutive_counts.get(category, 0),
        }

        # Recommend fix category based on outcome patterns
        if any("timeout" in o.lower() for o in outcomes):
            recommended_fix = "resource_allocation"
        elif any("dependency" in o.lower() for o in outcomes):
            recommended_fix = "dependency_resolution"
        elif any("invalid" in o.lower() for o in outcomes):
            recommended_fix = "validation_improvement"
        else:
            recommended_fix = "general_investigation"

        return {
            "suspected_root_cause": suspected_root_cause,
            "evidence": evidence,
            "recommended_fix_category": recommended_fix,
            "generated_at": datetime.utcnow().isoformat(),
        }