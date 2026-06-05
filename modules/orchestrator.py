from typing import Dict, List, Any
import logging
from modules.failure_pattern_learner import FailurePatternLearner
from modules.mutation_engine import MutationEngine

logger = logging.getLogger(__name__)

class Orchestrator:
    """Integrates failure pattern learning into the evolution loop."""

    def __init__(self, mutation_engine: MutationEngine, failure_learner: FailurePatternLearner):
        self.mutation_engine = mutation_engine
        self.failure_learner = failure_learner
        self.cycle_count = 0
        self.adjustment_interval = 5

    def run_evolution_cycle(self, mutation_attempts: List[Dict[str, Any]]) -> None:
        """Execute one evolution cycle with failure tracking and weight adjustment."""
        for attempt in mutation_attempts:
            try:
                # Simulate mutation attempt (replace with actual logic)
                success = self._perform_mutation(attempt)
                if not success:
                    self._handle_mutation_failure(attempt)
            except Exception as e:
                self._handle_mutation_failure(attempt, error=str(e))

        self.cycle_count += 1
        if self.cycle_count % self.adjustment_interval == 0:
            self._adjust_operator_weights()

    def _handle_mutation_failure(self, attempt: Dict[str, Any], error: str = "Unknown error") -> None:
        """Record failure details and update learner."""
        failure_details = {
            "operator": attempt.get("operator", "unknown"),
            "input": attempt.get("input"),
            "error": error,
            "cycle": self.cycle_count
        }
        self.failure_learner.record_failure(failure_details)
        logger.debug(f"Recorded failure: {failure_details}")

    def _adjust_operator_weights(self) -> None:
        """Analyze failures and update mutation engine weights."""
        adjusted_weights = self.failure_learner.analyze_and_adjust()
        if adjusted_weights:
            self.mutation_engine.set_operator_weights(adjusted_weights)
            logger.info(f"Adjusted operator weights: {adjusted_weights}")

    def _perform_mutation(self, attempt: Dict[str, Any]) -> bool:
        """Placeholder for actual mutation logic. Returns True if successful."""
        # Replace with real mutation execution
        return True