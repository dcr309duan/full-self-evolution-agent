"""Structured logger for the test harness with hierarchical logging and summary reporting."""

import json
import logging
import logging.handlers
import os
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any


class TestHarnessLogger:
    """Structured logger for test harness events with hierarchical tracking and summary reports."""

    def __init__(self, log_dir: str = "logs", log_file: str = "test_harness.log",
                 max_bytes: int = 10 * 1024 * 1024, backup_count: int = 5):
        """
        Initialize the test harness logger.

        Args:
            log_dir: Directory for log files
            log_file: Name of the log file
            max_bytes: Maximum size of a log file before rotation
            backup_count: Number of backup log files to keep
        """
        self.log_dir = log_dir
        os.makedirs(log_dir, exist_ok=True)

        # Create logger
        self.logger = logging.getLogger("TestHarness")
        self.logger.setLevel(logging.DEBUG)
        self.logger.handlers.clear()

        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(self._create_formatter())
        self.logger.addHandler(console_handler)

        # Rotating file handler
        file_path = os.path.join(log_dir, log_file)
        file_handler = logging.handlers.RotatingFileHandler(
            file_path, maxBytes=max_bytes, backupCount=backup_count
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(self._create_formatter())
        self.logger.addHandler(file_handler)

        # Hierarchical state tracking
        self.current_cycle: Optional[str] = None
        self.current_step: Optional[str] = None
        self.current_sub_step: Optional[str] = None
        self.cycle_start_time: Optional[float] = None

        # Summary data
        self.total_steps = 0
        self.failed_steps = 0
        self.repair_goals_generated = 0
        self.failure_patterns: Counter = Counter()
        self.step_durations: Dict[str, float] = {}

    def _create_formatter(self) -> logging.Formatter:
        """Create a structured log formatter with ISO timestamps."""
        return logging.Formatter(
            fmt='%(asctime)s | %(levelname)-8s | %(message)s',
            datefmt='%Y-%m-%dT%H:%M:%S.%fZ'
        )

    def _get_iso_timestamp(self) -> str:
        """Get current UTC time as ISO 8601 string."""
        return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'

    def _format_hierarchical_message(self, message: str) -> str:
        """Format message with hierarchical context."""
        parts = []
        if self.current_cycle:
            parts.append(f"[Cycle: {self.current_cycle}]")
        if self.current_step:
            parts.append(f"[Step: {self.current_step}]")
        if self.current_sub_step:
            parts.append(f"[SubStep: {self.current_sub_step}]")
        prefix = " ".join(parts)
        return f"{prefix} {message}" if prefix else message

    def start_cycle(self, cycle_id: str) -> None:
        """Start a new test cycle."""
        self.current_cycle = cycle_id
        self.current_step = None
        self.current_sub_step = None
        self.cycle_start_time = time.time()
        self.total_steps = 0
        self.failed_steps = 0
        self.repair_goals_generated = 0
        self.failure_patterns.clear()
        self.step_durations.clear()
        self.logger.info(self._format_hierarchical_message(f"Starting cycle: {cycle_id}"))

    def end_cycle(self) -> Dict[str, Any]:
        """End the current test cycle and return summary report."""
        if not self.current_cycle:
            raise RuntimeError("No active cycle to end")

        cycle_duration = time.time() - self.cycle_start_time if self.cycle_start_time else 0.0
        summary = self.generate_summary_report(cycle_duration)
        self.logger.info(self._format_hierarchical_message(
            f"Cycle ended. Duration: {cycle_duration:.2f}s. "
            f"Steps: {self.total_steps}, Failed: {self.failed_steps}"
        ))
        self.current_cycle = None
        self.current_step = None
        self.current_sub_step = None
        self.cycle_start_time = None
        return summary

    def start_step(self, step_name: str) -> None:
        """Start a new step within the current cycle."""
        if not self.current_cycle:
            raise RuntimeError("No active cycle to add step to")
        self.current_step = step_name
        self.current_sub_step = None
        self.total_steps += 1
        self.step_durations[step_name] = time.time()
        self.logger.info(self._format_hierarchical_message(f"Starting step: {step_name}"))

    def end_step(self, step_name: str, success: bool = True,
                 failure_pattern: Optional[str] = None) -> None:
        """End a step, recording success/failure and pattern."""
        if step_name in self.step_durations:
            duration = time.time() - self.step_durations.pop(step_name, time.time())
        else:
            duration = 0.0

        if not success:
            self.failed_steps += 1
            pattern = failure_pattern or "unknown"
            self.failure_patterns[pattern] += 1
            self.logger.warning(self._format_hierarchical_message(
                f"Step failed: {step_name} (pattern: {pattern}, duration: {duration:.2f}s)"
            ))
        else:
            self.logger.info(self._format_hierarchical_message(
                f"Step succeeded: {step_name} (duration: {duration:.2f}s)"
            ))
        self.current_step = None

    def start_sub_step(self, sub_step_name: str) -> None:
        """Start a sub-step within the current step."""
        if not self.current_step:
            raise RuntimeError("No active step to add sub-step to")
        self.current_sub_step = sub_step_name
        self.logger.debug(self._format_hierarchical_message(f"Starting sub-step: {sub_step_name}"))

    def end_sub_step(self, sub_step_name: str, success: bool = True) -> None:
        """End a sub-step."""
        status = "succeeded" if success else "failed"
        self.logger.debug(self._format_hierarchical_message(
            f"Sub-step {status}: {sub_step_name}"
        ))
        self.current_sub_step = None

    def log_failure(self, failure_type: str, details: str,
                    repair_goal: Optional[str] = None) -> None:
        """Log a failure event, optionally with a repair goal."""
        self.failure_patterns[failure_type] += 1
        if repair_goal:
            self.repair_goals_generated += 1
            self.logger.error(self._format_hierarchical_message(
                f"Failure: {failure_type} | Details: {details} | RepairGoal: {repair_goal}"
            ))
        else:
            self.logger.error(self._format_hierarchical_message(
                f"Failure: {failure_type} | Details: {details}"
            ))

    def log_event(self, message: str, level: str = "info") -> None:
        """Log a generic event at the specified severity level."""
        level = level.upper()
        log_method = getattr(self.logger, level.lower(), self.logger.info)
        log_method(self._format_hierarchical_message(message))

    def generate_summary_report(self, cycle_duration: float) -> Dict[str, Any]:
        """Generate a summary report for the current cycle."""
        report = {
            "timestamp": self._get_iso_timestamp(),
            "cycle_id": self.current_cycle,
            "total_steps": self.total_steps,
            "failed_steps": self.failed_steps,
            "repair_goals_generated": self.repair_goals_generated,
            "cycle_duration": round(cycle_duration, 3),
            "failure_pattern_distribution": dict(self.failure_patterns)
        }
        report_path = os.path.join(self.log_dir, f"summary_{self.current_cycle}.json")
        with open(report_path, "w") as f:
            json.dump(report, f, indent=2)
        self.logger.info(f"Summary report saved to {report_path}")
        return report

    def close(self) -> None:
        """Clean up logger handlers."""
        for handler in self.logger.handlers[:]:
            handler.close()
            self.logger.removeHandler(handler)