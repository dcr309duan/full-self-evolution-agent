import asyncio
import logging
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Dict, List, Optional

# Import existing modules (adjust import paths as needed)
from failure_analysis import FailureAnalysisModule
from goal_generator import GoalGenerator

logger = logging.getLogger(__name__)

class ProactiveRedesignOrchestrator:
    """
    Background orchestrator that monitors failure patterns and triggers redesign goals
    when recurring failures exceed a configurable threshold.
    """

    def __init__(
        self,
        failure_analysis: FailureAnalysisModule,
        goal_generator: GoalGenerator,
        check_interval_seconds: int = 30,
        failure_threshold: int = 3,
        time_window_minutes: int = 10,
        cooldown_minutes: int = 60
    ):
        """
        Initialize the orchestrator.

        Args:
            failure_analysis: Module for querying failure data
            goal_generator: Module for creating redesign goals
            check_interval_seconds: How often to poll for new failures
            failure_threshold: Number of same-type failures to trigger redesign
            time_window_minutes: Time window to count failures within
            cooldown_minutes: Minimum time between redesign triggers for same type
        """
        self.failure_analysis = failure_analysis
        self.goal_generator = goal_generator
        self.check_interval = check_interval_seconds
        self.failure_threshold = failure_threshold
        self.time_window = timedelta(minutes=time_window_minutes)
        self.cooldown = timedelta(minutes=cooldown_minutes)

        # Track recent failures per type
        self._failure_history: Dict[str, List[datetime]] = defaultdict(list)
        # Track last redesign trigger time per type
        self._last_redesign_time: Dict[str, Optional[datetime]] = defaultdict(lambda: None)
        # Running flag
        self._running = False

    async def start(self):
        """Start the background monitoring loop."""
        self._running = True
        logger.info("Proactive redesign orchestrator started.")
        while self._running:
            try:
                await self._check_and_trigger()
            except Exception as e:
                logger.error(f"Error in redesign check: {e}", exc_info=True)
            await asyncio.sleep(self.check_interval)

    async def stop(self):
        """Gracefully stop the orchestrator."""
        self._running = False
        logger.info("Proactive redesign orchestrator stopped.")

    async def _check_and_trigger(self):
        """Query failure analysis and trigger redesign if threshold exceeded."""
        # Get recent failures from analysis module
        recent_failures = await self.failure_analysis.get_recent_failures(
            window_minutes=self.time_window.total_seconds() / 60
        )

        # Group failures by type
        failures_by_type: Dict[str, List[datetime]] = defaultdict(list)
        for failure in recent_failures:
            failure_type = failure.get("type", "unknown")
            timestamp = failure.get("timestamp", datetime.utcnow())
            failures_by_type[failure_type].append(timestamp)

        # Check each failure type against threshold
        for failure_type, timestamps in failures_by_type.items():
            # Filter timestamps within the time window
            cutoff = datetime.utcnow() - self.time_window
            recent_timestamps = [ts for ts in timestamps if ts >= cutoff]

            if len(recent_timestamps) >= self.failure_threshold:
                # Check cooldown
                last_trigger = self._last_redesign_time.get(failure_type)
                if last_trigger and (datetime.utcnow() - last_trigger) < self.cooldown:
                    logger.debug(f"Skipping redesign for {failure_type} (cooldown active)")
                    continue

                # Trigger redesign
                logger.info(
                    f"Threshold exceeded for failure type '{failure_type}': "
                    f"{len(recent_timestamps)} failures in {self.time_window}"
                )
                await self._trigger_redesign(failure_type, recent_timestamps)
                self._last_redesign_time[failure_type] = datetime.utcnow()

    async def _trigger_redesign(self, failure_type: str, timestamps: List[datetime]):
        """Call goal generator to create a redesign goal for the given failure type."""
        try:
            # Prepare context for goal generation
            context = {
                "failure_type": failure_type,
                "failure_count": len(timestamps),
                "time_window_minutes": self.time_window.total_seconds() / 60,
                "timestamps": [ts.isoformat() for ts in timestamps],
                "trigger_source": "proactive_redesign_orchestrator"
            }

            # Create redesign goal
            goal = await self.goal_generator.create_redesign_goal(context)
            logger.info(f"Redesign goal created for {failure_type}: {goal}")

            # Optionally, update failure analysis with redesign trigger info
            await self.failure_analysis.record_redesign_trigger(failure_type, goal)

        except Exception as e:
            logger.error(f"Failed to trigger redesign for {failure_type}: {e}", exc_info=True)

    def get_status(self) -> dict:
        """Return current status information."""
        return {
            "running": self._running,
            "check_interval_seconds": self.check_interval,
            "failure_threshold": self.failure_threshold,
            "time_window_minutes": self.time_window.total_seconds() / 60,
            "cooldown_minutes": self.cooldown.total_seconds() / 60,
            "active_failure_types": list(self._failure_history.keys()),
            "last_redesign_times": {
                k: v.isoformat() if v else None
                for k, v in self._last_redesign_time.items()
            }
        }


# Example usage (if run directly)
if __name__ == "__main__":
    import asyncio

    async def main():
        # Mock modules for demonstration
        class MockFailureAnalysis:
            async def get_recent_failures(self, window_minutes):
                # Simulate returning failures
                return [
                    {"type": "timeout_error", "timestamp": datetime.utcnow() - timedelta(minutes=1)},
                    {"type": "timeout_error", "timestamp": datetime.utcnow() - timedelta(minutes=2)},
                    {"type": "timeout_error", "timestamp": datetime.utcnow() - timedelta(minutes=3)},
                    {"type": "connection_error", "timestamp": datetime.utcnow() - timedelta(minutes=5)},
                ]
            async def record_redesign_trigger(self, failure_type, goal):
                logger.info(f"Recorded redesign trigger for {failure_type}")

        class MockGoalGenerator:
            async def create_redesign_goal(self, context):
                return {"goal": f"Redesign for {context['failure_type']}", "priority": "high"}

        orchestrator = ProactiveRedesignOrchestrator(
            failure_analysis=MockFailureAnalysis(),
            goal_generator=MockGoalGenerator(),
            check_interval_seconds=10,
            failure_threshold=3,
            time_window_minutes=10,
            cooldown_minutes=60
        )

        # Run for a few cycles then stop
        task = asyncio.create_task(orchestrator.start())
        await asyncio.sleep(30)
        await orchestrator.stop()
        await task

    asyncio.run(main())