"""Capability Benchmarker Module

Maintains a list of capabilities with enable/disable state and runs benchmark
tests to measure the impact of each capability on system performance.
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class CapabilityState(Enum):
    """State of a capability in the benchmarker."""
    PENDING = "pending"
    RECENT = "recent"
    STABLE = "stable"
    DISABLED = "disabled"


@dataclass
class Capability:
    """Represents a capability with its enable/disable state."""
    name: str
    enabled: bool = True
    state: CapabilityState = CapabilityState.STABLE
    description: str = ""


@dataclass
class BenchmarkResult:
    """Stores benchmark results for a capability."""
    capability_name: str
    enabled_success_rate: float = 0.0
    disabled_success_rate: float = 0.0
    delta_score: float = 0.0
    num_cycles: int = 10
    completed: bool = False


class CapabilityBenchmarker:
    """Main benchmarking module for evaluating capability impact."""

    def __init__(self, num_test_cycles: int = 10):
        self._capabilities: Dict[str, Capability] = {}
        self._results: Dict[str, BenchmarkResult] = {}
        self._num_test_cycles = num_test_cycles
        self._test_function: Optional[Callable] = None
        self._historical_data: Dict[str, Dict] = {}

    def register_capability(self, name: str, enabled: bool = True,
                            state: CapabilityState = CapabilityState.STABLE,
                            description: str = "") -> None:
        """Register a new capability for benchmarking."""
        if name in self._capabilities:
            logger.warning(f"Capability '{name}' already registered. Updating.")
        self._capabilities[name] = Capability(
            name=name, enabled=enabled, state=state, description=description
        )
        logger.info(f"Registered capability: {name} (enabled={enabled}, state={state.value})")

    def remove_capability(self, name: str) -> None:
        """Remove a capability from the benchmarker."""
        self._capabilities.pop(name, None)
        self._results.pop(name, None)
        logger.info(f"Removed capability: {name}")

    def enable_capability(self, name: str) -> None:
        """Enable a specific capability."""
        if name in self._capabilities:
            self._capabilities[name].enabled = True
            logger.info(f"Enabled capability: {name}")

    def disable_capability(self, name: str) -> None:
        """Disable a specific capability."""
        if name in self._capabilities:
            self._capabilities[name].enabled = False
            logger.info(f"Disabled capability: {name}")

    def set_capability_state(self, name: str, state: CapabilityState) -> None:
        """Set the state of a capability."""
        if name in self._capabilities:
            self._capabilities[name].state = state

    def get_capability(self, name: str) -> Optional[Capability]:
        """Get a capability by name."""
        return self._capabilities.get(name)

    def get_all_capabilities(self) -> Dict[str, Capability]:
        """Get all registered capabilities."""
        return dict(self._capabilities)

    def get_pending_capabilities(self) -> List[str]:
        """Get list of capabilities in PENDING state."""
        return [name for name, cap in self._capabilities.items()
                if cap.state == CapabilityState.PENDING]

    def get_recent_capabilities(self) -> List[str]:
        """Get list of capabilities in RECENT state."""
        return [name for name, cap in self._capabilities.items()
                if cap.state == CapabilityState.RECENT]

    def set_test_function(self, test_func: Callable) -> None:
        """Set the test function to use for benchmarking.

        The test function should accept a capability name and a boolean
        indicating whether the capability is enabled, and return a success
        rate (float between 0.0 and 1.0).
        """
        self._test_function = test_func

    async def _run_single_test(self, capability_name: str, enabled: bool) -> float:
        """Run a single test cycle and return success rate."""
        if self._test_function is None:
            raise RuntimeError("Test function not set. Call set_test_function() first.")

        try:
            if asyncio.iscoroutinefunction(self._test_function):
                success_rate = await self._test_function(capability_name, enabled)
            else:
                success_rate = self._test_function(capability_name, enabled)
            return float(success_rate)
        except Exception as e:
            logger.error(f"Test failed for {capability_name} (enabled={enabled}): {e}")
            return 0.0

    async def benchmark_capability(self, capability_name: str) -> BenchmarkResult:
        """Run benchmark for a single capability.

        Runs num_test_cycles with the capability enabled and num_test_cycles
        with it disabled, then computes delta score.
        """
        if capability_name not in self._capabilities:
            raise ValueError(f"Capability '{capability_name}' not registered")

        result = BenchmarkResult(capability_name=capability_name,
                                 num_cycles=self._num_test_cycles)

        # Run tests with capability enabled
        enabled_successes = []
        for i in range(self._num_test_cycles):
            success_rate = await self._run_single_test(capability_name, enabled=True)
            enabled_successes.append(success_rate)
            logger.debug(f"Enabled test {i+1}/{self._num_test_cycles} for "
                        f"'{capability_name}': {success_rate:.3f}")

        # Run tests with capability disabled
        disabled_successes = []
        for i in range(self._num_test_cycles):
            success_rate = await self._run_single_test(capability_name, enabled=False)
            disabled_successes.append(success_rate)
            logger.debug(f"Disabled test {i+1}/{self._num_test_cycles} for "
                        f"'{capability_name}': {success_rate:.3f}")

        # Calculate average success rates
        result.enabled_success_rate = sum(enabled_successes) / len(enabled_successes)
        result.disabled_success_rate = sum(disabled_successes) / len(disabled_successes)

        # Delta score: positive means capability improves performance
        result.delta_score = result.enabled_success_rate - result.disabled_success_rate
        result.completed = True

        self._results[capability_name] = result
        logger.info(f"Benchmark completed for '{capability_name}': "
                    f"delta={result.delta_score:.4f}")

        return result

    async def benchmark_all_pending(self) -> Dict[str, BenchmarkResult]:
        """Run benchmarks for all pending capabilities."""
        pending = self.get_pending_capabilities()
        results = {}
        for cap_name in pending:
            results[cap_name] = await self.benchmark_capability(cap_name)
        return results

    async def benchmark_all_recent(self) -> Dict[str, BenchmarkResult]:
        """Run benchmarks for all recent capabilities."""
        recent = self.get_recent_capabilities()
        results = {}
        for cap_name in recent:
            results[cap_name] = await self.benchmark_capability(cap_name)
        return results

    async def benchmark_all(self) -> Dict[str, BenchmarkResult]:
        """Run benchmarks for all registered capabilities."""
        results = {}
        for cap_name in self._capabilities:
            results[cap_name] = await self.benchmark_capability(cap_name)
        return results

    def get_delta_scores(self) -> Dict[str, float]:
        """Return delta scores for all completed benchmarks."""
        return {
            name: result.delta_score
            for name, result in self._results.items()
            if result.completed
        }

    def get_ranked_capabilities(self) -> List[Tuple[str, float]]:
        """Return capabilities ranked by delta score (best first)."""
        deltas = self.get_delta_scores()
        return sorted(deltas.items(), key=lambda x: x[1], reverse=True)

    def get_result(self, capability_name: str) -> Optional[BenchmarkResult]:
        """Get benchmark result for a specific capability."""
        return self._results.get(capability_name)

    def clear_results(self) -> None:
        """Clear all benchmark results."""
        self._results.clear()
        logger.info("Cleared all benchmark results")

    def get_summary(self) -> Dict[str, Dict]:
        """Get a summary of all capabilities and their benchmark results."""
        summary = {}
        for name, cap in self._capabilities.items():
            result = self._results.get(name)
            summary[name] = {
                "enabled": cap.enabled,
                "state": cap.state.value,
                "description": cap.description,
                "benchmark_completed": result.completed if result else False,
                "delta_score": result.delta_score if result else None,
                "enabled_success_rate": result.enabled_success_rate if result else None,
                "disabled_success_rate": result.disabled_success_rate if result else None,
            }
        return summary

    def estimate_goal_impact(self, goal: str) -> Tuple[float, float, int, int]:
        """Estimate the impact of a goal based on historical data or defaults.

        Args:
            goal: The goal description to estimate impact for.

        Returns:
            A tuple containing:
                - estimated_test_pass_rate (float): 0.0-1.0
                - simplicity_score (float): 0.0-1.0
                - lines_added (int): Estimated lines of code to add
                - new_deps (int): Estimated number of new dependencies
        """
        # Check if we have historical data for this goal
        if goal in self._historical_data:
            data = self._historical_data[goal]
            return (
                data.get("test_pass_rate", 0.5),
                data.get("simplicity_score", 0.5),
                data.get("lines_added", 10),
                data.get("new_deps", 0)
            )

        # Check for similar goals based on keywords
        goal_lower = goal.lower()
        for hist_goal, data in self._historical_data.items():
            if any(keyword in goal_lower for keyword in hist_goal.lower().split()):
                return (
                    data.get("test_pass_rate", 0.5),
                    data.get("simplicity_score", 0.5),
                    data.get("lines_added", 10),
                    data.get("new_deps", 0)
                )

        # Return defaults based on goal characteristics
        if "test" in goal_lower or "testing" in goal_lower:
            return (0.7, 0.6, 15, 1)
        elif "refactor" in goal_lower or "clean" in goal_lower:
            return (0.8, 0.8, 5, 0)
        elif "feature" in goal_lower or "add" in goal_lower:
            return (0.5, 0.4, 30, 2)
        elif "fix" in goal_lower or "bug" in goal_lower:
            return (0.6, 0.7, 10, 0)
        elif "optimize" in goal_lower or "performance" in goal_lower:
            return (0.4, 0.3, 20, 1)
        elif "document" in goal_lower or "doc" in goal_lower:
            return (0.9, 0.9, 50, 0)
        elif "config" in goal_lower or "configuration" in goal_lower:
            return (0.7, 0.5, 10, 1)
        elif "security" in goal_lower or "secure" in goal_lower:
            return (0.8, 0.6, 25, 2)
        elif "dependency" in goal_lower or "deps" in goal_lower:
            return (0.6, 0.4, 5, 3)
        elif "api" in goal_lower or "endpoint" in goal_lower:
            return (0.5, 0.5, 20, 1)
        elif "database" in goal_lower or "db" in goal_lower:
            return (0.6, 0.5, 15, 1)
        elif "ui" in goal_lower or "interface" in goal_lower:
            return (0.4, 0.3, 40, 2)
        elif "log" in goal_lower or "logging" in goal_lower:
            return (0.8, 0.7, 10, 0)
        elif "error" in goal_lower or "exception" in goal_lower:
            return (0.7, 0.6, 8, 0)
        elif "validation" in goal_lower or "validate" in goal_lower:
            return (0.8, 0.7, 12, 0)
        elif "migration" in goal_lower or "migrate" in goal_lower:
            return (0.5, 0.4, 50, 3)
        elif "upgrade" in goal_lower or "update" in goal_lower:
            return (0.6, 0.5, 20, 1)
        elif "integration" in goal_lower or "integrate" in goal_lower:
            return (0.4, 0.3, 35, 2)
        elif "monitor" in goal_lower or "monitoring" in goal_lower:
            return (0.7, 0.6, 15, 1)
        elif "backup" in goal_lower or "recovery" in goal_lower:
            return (0.8, 0.7, 20, 1)
        elif "deploy" in goal_lower or "deployment" in goal_lower:
            return (0.6, 0.5, 10, 1)
        elif "test" in goal_lower:
            return (0.7, 0.6, 15, 1)
        else:
            # Default conservative estimates
            return (0.5, 0.5, 10, 0)

    def update_historical_data(self, goal: str, test_pass_rate: float,
                               simplicity_score: float, lines_added: int,
                               new_deps: int) -> None:
        """Update historical data for a goal after it has been implemented.

        Args:
            goal: The goal description.
            test_pass_rate: Actual test pass rate achieved (0.0-1.0).
            simplicity_score: Actual simplicity score (0.0-1.0).
            lines_added: Actual lines of code added.
            new_deps: Actual number of new dependencies.
        """
        self._historical_data[goal] = {
            "test_pass_rate": test_pass_rate,
            "simplicity_score": simplicity_score,
            "lines_added": lines_added,
            "new_deps": new_deps
        }
        logger.info(f"Updated historical data for goal: {goal}")

    def get_historical_data(self, goal: str) -> Optional[Dict]:
        """Get historical data for a specific goal.

        Args:
            goal: The goal description to look up.

        Returns:
            Dictionary with historical data if available, None otherwise.
        """
        return self._historical_data.get(goal)

    def get_all_historical_data(self) -> Dict[str, Dict]:
        """Get all historical data.

        Returns:
            Dictionary mapping goal descriptions to their historical data.
        """
        return dict(self._historical_data)

    def clear_historical_data(self) -> None:
        """Clear all historical data."""
        self._historical_data.clear()
        logger.info("Cleared all historical data")