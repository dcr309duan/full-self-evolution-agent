import json
import os
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime


class EcologyMetrics:
    """
    Collects and stores ecology metrics for test suite analysis.
    Tracks test file count, coverage, unique patterns, and failure rate.
    """

    def __init__(self, metrics_file: str = "ecology_metrics.json"):
        self.metrics_file = metrics_file
        self.metrics: Dict[str, any] = {
            "test_file_count": 0,
            "test_coverage_percentage": 0.0,
            "unique_test_patterns": 0,
            "test_failure_rate": 0.0,
            "last_updated": None,
            "history": []
        }
        self._load_existing()

    def _load_existing(self) -> None:
        """Load existing metrics from JSON file if it exists."""
        if os.path.exists(self.metrics_file):
            try:
                with open(self.metrics_file, "r") as f:
                    loaded = json.load(f)
                    self.metrics.update(loaded)
            except (json.JSONDecodeError, IOError):
                pass

    def save(self) -> None:
        """Save current metrics to JSON file."""
        self.metrics["last_updated"] = datetime.now().isoformat()
        with open(self.metrics_file, "w") as f:
            json.dump(self.metrics, f, indent=2)

    def update_test_file_count(self, count: int) -> None:
        """Update the number of test files."""
        self.metrics["test_file_count"] = count
        self._record_history("test_file_count", count)

    def update_coverage(self, coverage: float) -> None:
        """Update test coverage percentage (0-100)."""
        self.metrics["test_coverage_percentage"] = round(coverage, 2)
        self._record_history("test_coverage_percentage", round(coverage, 2))

    def update_unique_patterns(self, patterns: int) -> None:
        """Update the count of unique test patterns."""
        self.metrics["unique_test_patterns"] = patterns
        self._record_history("unique_test_patterns", patterns)

    def update_failure_rate(self, rate: float) -> None:
        """Update test failure rate (0.0 to 1.0)."""
        self.metrics["test_failure_rate"] = round(rate, 4)
        self._record_history("test_failure_rate", round(rate, 4))

    def _record_history(self, metric_name: str, value: any) -> None:
        """Record a metric change in history for trend analysis."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "metric": metric_name,
            "value": value
        }
        self.metrics["history"].append(entry)
        # Keep only last 100 entries to avoid unbounded growth
        if len(self.metrics["history"]) > 100:
            self.metrics["history"] = self.metrics["history"][-100:]

    def get_summary(self) -> Dict[str, any]:
        """Return a summary of current metrics."""
        return {
            "test_file_count": self.metrics["test_file_count"],
            "test_coverage_percentage": self.metrics["test_coverage_percentage"],
            "unique_test_patterns": self.metrics["unique_test_patterns"],
            "test_failure_rate": self.metrics["test_failure_rate"],
            "last_updated": self.metrics["last_updated"]
        }

    def reset(self) -> None:
        """Reset all metrics to default values (keeps history)."""
        self.metrics["test_file_count"] = 0
        self.metrics["test_coverage_percentage"] = 0.0
        self.metrics["unique_test_patterns"] = 0
        self.metrics["test_failure_rate"] = 0.0
        self.metrics["last_updated"] = None
        self.save()


def collect_metrics_from_directory(test_dir: str = "tests") -> EcologyMetrics:
    """
    Convenience function to scan a test directory and populate metrics.
    Returns an EcologyMetrics instance with collected data.
    """
    metrics = EcologyMetrics()
    test_path = Path(test_dir)

    if not test_path.exists():
        metrics.update_test_file_count(0)
        metrics.update_coverage(0.0)
        metrics.update_unique_patterns(0)
        metrics.update_failure_rate(0.0)
        metrics.save()
        return metrics

    # Count test files (files ending with _test.py or test_*.py)
    test_files = list(test_path.rglob("test_*.py")) + list(test_path.rglob("*_test.py"))
    metrics.update_test_file_count(len(test_files))

    # Estimate unique patterns by counting distinct test function names
    unique_patterns = set()
    for tf in test_files:
        try:
            with open(tf, "r") as f:
                content = f.read()
                # Simple heuristic: find lines starting with 'def test_'
                for line in content.split("\n"):
                    stripped = line.strip()
                    if stripped.startswith("def test_"):
                        unique_patterns.add(stripped)
        except (IOError, OSError):
            pass
    metrics.update_unique_patterns(len(unique_patterns))

    # Coverage and failure rate are placeholders; real values require external tools
    metrics.update_coverage(0.0)
    metrics.update_failure_rate(0.0)

    metrics.save()
    return metrics