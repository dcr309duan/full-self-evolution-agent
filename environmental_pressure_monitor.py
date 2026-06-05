import time
import random
from typing import List, Dict, Any, Optional, Callable

class EnvironmentalPressureMonitor:
    """
    Monitors agent performance over time and detects staleness in the fitness landscape.
    When staleness is detected (e.g., 10 consecutive cycles with no new failures,
    or all tests passing with high confidence), triggers creation of new benchmarks
    or mutation of existing ones.
    """

    def __init__(
        self,
        staleness_threshold: int = 10,
        high_confidence_threshold: float = 0.95,
        benchmark_creator: Optional[Callable] = None,
        benchmark_mutator: Optional[Callable] = None,
    ):
        """
        Initialize the monitor.

        Args:
            staleness_threshold: Number of consecutive cycles without new failures to consider stale.
            high_confidence_threshold: Confidence level above which all tests passing is considered stale.
            benchmark_creator: Function to create new benchmarks. Signature: () -> List[Any]
            benchmark_mutator: Function to mutate existing benchmarks. Signature: (List[Any]) -> List[Any]
        """
        self.staleness_threshold = staleness_threshold
        self.high_confidence_threshold = high_confidence_threshold
        self.benchmark_creator = benchmark_creator or self._default_benchmark_creator
        self.benchmark_mutator = benchmark_mutator or self._default_benchmark_mutator

        # Performance history
        self.cycle_count = 0
        self.consecutive_no_new_failures = 0
        self.last_failure_cycle = 0
        self.performance_log: List[Dict[str, Any]] = []
        self.current_benchmarks: List[Any] = []
        self.staleness_detected = False

    def _default_benchmark_creator(self) -> List[Any]:
        """Default benchmark creator: generates random test cases."""
        new_benchmarks = []
        for _ in range(random.randint(1, 5)):
            new_benchmarks.append({
                "input": random.randint(0, 100),
                "expected": random.randint(0, 100),
                "created_at": time.time()
            })
        return new_benchmarks

    def _default_benchmark_mutator(self, benchmarks: List[Any]) -> List[Any]:
        """Default benchmark mutator: slightly modifies existing benchmarks."""
        mutated = []
        for b in benchmarks:
            mutation = b.copy()
            mutation["input"] = b["input"] + random.randint(-10, 10)
            mutation["expected"] = b["expected"] + random.randint(-10, 10)
            mutation["mutated_at"] = time.time()
            mutated.append(mutation)
        return mutated

    def record_cycle(
        self,
        test_results: Dict[str, Any],
        confidence: float,
        new_failures: int,
    ) -> Dict[str, Any]:
        """
        Record a monitoring cycle.

        Args:
            test_results: Dictionary of test results (e.g., {"passed": 10, "failed": 0}).
            confidence: Confidence level of the agent's performance (0.0 to 1.0).
            new_failures: Number of new failures discovered in this cycle.

        Returns:
            Status dictionary indicating whether staleness was detected and actions taken.
        """
        self.cycle_count += 1

        # Update consecutive no-new-failures counter
        if new_failures == 0:
            self.consecutive_no_new_failures += 1
        else:
            self.consecutive_no_new_failures = 0
            self.last_failure_cycle = self.cycle_count

        # Log performance
        entry = {
            "cycle": self.cycle_count,
            "timestamp": time.time(),
            "test_results": test_results,
            "confidence": confidence,
            "new_failures": new_failures,
            "consecutive_no_new_failures": self.consecutive_no_new_failures,
        }
        self.performance_log.append(entry)

        # Check for staleness
        staleness_reason = None
        if self.consecutive_no_new_failures >= self.staleness_threshold:
            staleness_reason = f"No new failures for {self.consecutive_no_new_failures} consecutive cycles."
        elif confidence >= self.high_confidence_threshold and test_results.get("failed", 0) == 0:
            staleness_reason = f"All tests passing with high confidence ({confidence:.2f})."

        if staleness_reason:
            self.staleness_detected = True
            action_taken = self._handle_staleness(staleness_reason)
            return {
                "staleness_detected": True,
                "reason": staleness_reason,
                "action_taken": action_taken,
                "cycle": self.cycle_count,
            }

        return {
            "staleness_detected": False,
            "cycle": self.cycle_count,
        }

    def _handle_staleness(self, reason: str) -> Dict[str, Any]:
        """
        Handle staleness by creating new benchmarks or mutating existing ones.

        Args:
            reason: Description of why staleness was detected.

        Returns:
            Dictionary describing the action taken.
        """
        action = {}
        if not self.current_benchmarks:
            # No benchmarks exist, create new ones
            new_benchmarks = self.benchmark_creator()
            self.current_benchmarks.extend(new_benchmarks)
            action = {
                "action": "created_new_benchmarks",
                "count": len(new_benchmarks),
                "reason": reason,
            }
        else:
            # Mutate existing benchmarks
            mutated_benchmarks = self.benchmark_mutator(self.current_benchmarks)
            self.current_benchmarks = mutated_benchmarks
            action = {
                "action": "mutated_existing_benchmarks",
                "count": len(mutated_benchmarks),
                "reason": reason,
            }

        # Reset staleness counters after action
        self.consecutive_no_new_failures = 0
        self.staleness_detected = False

        return action

    def get_performance_summary(self) -> Dict[str, Any]:
        """Get a summary of the monitored performance."""
        if not self.performance_log:
            return {"status": "no_data"}

        total_cycles = len(self.performance_log)
        total_failures = sum(
            entry["test_results"].get("failed", 0) for entry in self.performance_log
        )
        avg_confidence = sum(entry["confidence"] for entry in self.performance_log) / total_cycles

        return {
            "total_cycles": total_cycles,
            "total_failures": total_failures,
            "average_confidence": avg_confidence,
            "consecutive_no_new_failures": self.consecutive_no_new_failures,
            "staleness_detected": self.staleness_detected,
            "current_benchmarks_count": len(self.current_benchmarks),
        }

    def reset(self) -> None:
        """Reset the monitor to initial state."""
        self.cycle_count = 0
        self.consecutive_no_new_failures = 0
        self.last_failure_cycle = 0
        self.performance_log = []
        self.current_benchmarks = []
        self.staleness_detected = False