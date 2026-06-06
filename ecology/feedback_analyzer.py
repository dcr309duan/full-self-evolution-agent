"""Feedback Analyzer for the ecology system.

Monitors test results across cycles, identifies problematic tests,
suggests modifications, and generates fitness landscape reports.
"""

import json
import os
from collections import defaultdict, Counter
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple


class FeedbackAnalyzer:
    """Analyzes test feedback across evolution cycles.

    Tracks pass/fail history per test, identifies dead/impossible tests,
    suggests modifications, and generates landscape reports.
    """

    def __init__(self, history_path: str = "ecology/feedback_history.json"):
        self.history_path = history_path
        self.history: Dict[str, List[Dict[str, Any]]] = {}
        self._load_history()

    def _load_history(self) -> None:
        """Load existing feedback history from disk."""
        if os.path.exists(self.history_path):
            try:
                with open(self.history_path, "r") as f:
                    self.history = json.load(f)
            except (json.JSONDecodeError, IOError):
                self.history = {}
        else:
            self.history = {}

    def _save_history(self) -> None:
        """Persist feedback history to disk."""
        os.makedirs(os.path.dirname(self.history_path), exist_ok=True)
        with open(self.history_path, "w") as f:
            json.dump(self.history, f, indent=2)

    def record_cycle(
        self,
        cycle_id: int,
        test_results: Dict[str, bool],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Record results for a single evolution cycle.

        Args:
            cycle_id: The cycle number.
            test_results: Mapping of test name -> passed (True/False).
            metadata: Optional extra info (e.g., agent version, timestamp).
        """
        timestamp = datetime.utcnow().isoformat()
        for test_name, passed in test_results.items():
            if test_name not in self.history:
                self.history[test_name] = []
            self.history[test_name].append(
                {
                    "cycle": cycle_id,
                    "passed": passed,
                    "timestamp": timestamp,
                    **(metadata or {}),
                }
            )
        self._save_history()

    def get_test_history(self, test_name: str) -> List[Dict[str, Any]]:
        """Return full history for a specific test."""
        return self.history.get(test_name, [])

    def get_all_test_names(self) -> List[str]:
        """Return list of all tracked test names."""
        return list(self.history.keys())

    def identify_dead_tests(
        self, min_cycles: int = 3
    ) -> List[Tuple[str, int]]:
        """Find tests that have always passed for at least min_cycles.

        Returns:
            List of (test_name, consecutive_passes) tuples.
        """
        dead = []
        for test_name, records in self.history.items():
            if len(records) < min_cycles:
                continue
            # Check from most recent backwards
            consecutive_passes = 0
            for record in reversed(records):
                if record["passed"]:
                    consecutive_passes += 1
                else:
                    break
            if consecutive_passes >= min_cycles:
                dead.append((test_name, consecutive_passes))
        return dead

    def identify_impossible_tests(
        self, min_cycles: int = 3
    ) -> List[Tuple[str, int]]:
        """Find tests that have always failed for at least min_cycles.

        Returns:
            List of (test_name, consecutive_fails) tuples.
        """
        impossible = []
        for test_name, records in self.history.items():
            if len(records) < min_cycles:
                continue
            consecutive_fails = 0
            for record in reversed(records):
                if not record["passed"]:
                    consecutive_fails += 1
                else:
                    break
            if consecutive_fails >= min_cycles:
                impossible.append((test_name, consecutive_fails))
        return impossible

    def suggest_test_modifications(self) -> Dict[str, List[str]]:
        """Suggest modifications based on failure patterns.

        Returns:
            Dict mapping test_name to list of suggestion strings.
        """
        suggestions = {}
        for test_name, records in self.history.items():
            if len(records) < 2:
                continue
            test_suggestions = []
            # Pattern: alternating pass/fail (flaky test)
            recent = records[-5:] if len(records) >= 5 else records
            passes = sum(1 for r in recent if r["passed"])
            fails = len(recent) - passes
            if passes > 0 and fails > 0:
                test_suggestions.append(
                    f"Test '{test_name}' is flaky ({passes}/{len(recent)} passes). "
                    "Consider stabilizing or splitting into sub-tests."
                )
            # Pattern: sudden change from pass to fail
            if len(records) >= 3:
                last_three = records[-3:]
                if all(r["passed"] for r in last_three[:2]) and not last_three[-1]["passed"]:
                    test_suggestions.append(
                        f"Test '{test_name}' recently started failing after consecutive passes. "
                        "Check for regressions."
                    )
                if all(not r["passed"] for r in last_three[:2]) and last_three[-1]["passed"]:
                    test_suggestions.append(
                        f"Test '{test_name}' recently started passing after consecutive failures. "
                        "Verify the fix is complete."
                    )
            # Pattern: always failing (impossible)
            if len(records) >= 5 and all(not r["passed"] for r in records[-5:]):
                test_suggestions.append(
                    f"Test '{test_name}' has failed for 5+ consecutive cycles. "
                    "Consider relaxing constraints or removing if no longer relevant."
                )
            # Pattern: always passing (dead)
            if len(records) >= 5 and all(r["passed"] for r in records[-5:]):
                test_suggestions.append(
                    f"Test '{test_name}' has passed for 5+ consecutive cycles. "
                    "Consider increasing difficulty or archiving."
                )
            if test_suggestions:
                suggestions[test_name] = test_suggestions
        return suggestions

    def compute_difficulty_distribution(self) -> Dict[str, float]:
        """Compute current pass rate for each test as difficulty proxy.

        Returns:
            Dict mapping test_name -> pass_rate (0.0 to 1.0).
        """
        distribution = {}
        for test_name, records in self.history.items():
            if not records:
                continue
            passes = sum(1 for r in records if r["passed"])
            distribution[test_name] = passes / len(records)
        return distribution

    def compute_coverage_metrics(self) -> Dict[str, Any]:
        """Compute coverage-like metrics from test history.

        Returns:
            Dict with keys: total_tests, active_tests, dead_tests,
            impossible_tests, flaky_tests.
        """
        total = len(self.history)
        if total == 0:
            return {
                "total_tests": 0,
                "active_tests": 0,
                "dead_tests": 0,
                "impossible_tests": 0,
                "flaky_tests": 0,
            }
        dead = len(self.identify_dead_tests(min_cycles=3))
        impossible = len(self.identify_impossible_tests(min_cycles=3))
        flaky = 0
        for records in self.history.values():
            if len(records) >= 3:
                recent = records[-3:]
                passes = sum(1 for r in recent if r["passed"])
                if 0 < passes < 3:
                    flaky += 1
        return {
            "total_tests": total,
            "active_tests": total - dead - impossible,
            "dead_tests": dead,
            "impossible_tests": impossible,
            "flaky_tests": flaky,
        }

    def compute_diversity_metrics(self) -> Dict[str, Any]:
        """Compute diversity metrics from test history.

        Measures how varied the pass/fail patterns are across tests.

        Returns:
            Dict with keys: unique_patterns, pattern_entropy,
            dominant_pattern, dominant_frequency.
        """
        if not self.history:
            return {
                "unique_patterns": 0,
                "pattern_entropy": 0.0,
                "dominant_pattern": None,
                "dominant_frequency": 0.0,
            }
        # Build binary string patterns for each test (most recent up to 10 cycles)
        patterns = []
        for records in self.history.values():
            recent = records[-10:] if len(records) >= 10 else records
            pattern = "".join("1" if r["passed"] else "0" for r in recent)
            patterns.append(pattern)
        pattern_counts = Counter(patterns)
        total = len(patterns)
        unique = len(pattern_counts)
        # Shannon entropy
        import math
        entropy = 0.0
        for count in pattern_counts.values():
            p = count / total
            entropy -= p * math.log2(p) if p > 0 else 0
        dominant = pattern_counts.most_common(1)
        dominant_pattern = dominant[0][0] if dominant else None
        dominant_freq = dominant[0][1] / total if dominant else 0.0
        return {
            "unique_patterns": unique,
            "pattern_entropy": round(entropy, 4),
            "dominant_pattern": dominant_pattern,
            "dominant_frequency": round(dominant_freq, 4),
        }

    def generate_fitness_landscape_report(self) -> Dict[str, Any]:
        """Generate a comprehensive fitness landscape report.

        Returns:
            Dict with keys: timestamp, difficulty_distribution,
            coverage_metrics, diversity_metrics, dead_tests,
            impossible_tests, suggestions.
        """
        report = {
            "timestamp": datetime.utcnow().isoformat(),
            "difficulty_distribution": self.compute_difficulty_distribution(),
            "coverage_metrics": self.compute_coverage_metrics(),
            "diversity_metrics": self.compute_diversity_metrics(),
            "dead_tests": [t[0] for t in self.identify_dead_tests(min_cycles=3)],
            "impossible_tests": [t[0] for t in self.identify_impossible_tests(min_cycles=3)],
            "suggestions": self.suggest_test_modifications(),
        }
        return report

    def save_report(self, report: Optional[Dict[str, Any]] = None, path: str = "ecology/fitness_report.json") -> str:
        """Save a fitness landscape report to disk.

        Args:
            report: Report dict (generated if None).
            path: File path to save to.

        Returns:
            The path the report was saved to.
        """
        if report is None:
            report = self.generate_fitness_landscape_report()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            json.dump(report, f, indent=2)
        return path

    def clear_history(self) -> None:
        """Clear all recorded feedback history."""
        self.history = {}
        self._save_history()