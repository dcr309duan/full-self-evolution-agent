"""Evolution Orchestrator - Integrates static predictor into mutation pipeline."""

import logging
from typing import Any, Dict, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class OrchestratorConfig:
    """Configuration for the evolution orchestrator."""
    predictor_threshold: float = 0.7
    max_mutations: int = 100
    parallel_workers: int = 4
    additional_params: Dict[str, Any] = field(default_factory=dict)


class EvolutionOrchestrator:
    """Orchestrates mutation pipeline with predictive filtering."""

    def __init__(self, config: Optional[OrchestratorConfig] = None):
        self.config = config or OrchestratorConfig()
        self.predicted_failures = 0
        self.total_mutations_attempted = 0
        self.skipped_mutations = 0
        self.failure_insights: list = []
        self._predictor = None

    def set_predictor(self, predictor: Any) -> None:
        """Set the static predictor instance."""
        self._predictor = predictor

    def should_execute_mutation(self, mutation: Any) -> bool:
        """Check if mutation should be executed based on predictor analysis.

        Returns:
            True if mutation should proceed, False if it should be skipped.
        """
        if self._predictor is None:
            return True

        try:
            result = self._predictor.analyze(mutation)
            if result.get("abort", False):
                reasoning = result.get("reasoning", "No reasoning provided")
                logger.info(
                    "Mutation skipped by predictor (threshold=%s): %s",
                    self.config.predictor_threshold,
                    reasoning
                )
                self.predicted_failures += 1
                self.skipped_mutations += 1
                self.failure_insights.append({
                    "mutation": str(mutation),
                    "reasoning": reasoning,
                    "threshold": self.config.predictor_threshold
                })
                return False
        except Exception as e:
            logger.warning("Predictor analysis failed, proceeding with mutation: %s", e)

        return True

    def execute_mutation_pipeline(self, mutation: Any, executor_func: callable) -> Any:
        """Execute a mutation through the pipeline with predictive filtering.

        Args:
            mutation: The mutation to potentially execute.
            executor_func: Function that actually runs the mutation.

        Returns:
            Result of executor_func if mutation is executed, None if skipped.
        """
        self.total_mutations_attempted += 1

        if not self.should_execute_mutation(mutation):
            return None

        try:
            result = executor_func(mutation)
            return result
        except Exception as e:
            logger.error("Mutation execution failed: %s", e)
            raise

    def get_stats(self) -> Dict[str, Any]:
        """Get orchestrator statistics."""
        return {
            "predicted_failures": self.predicted_failures,
            "total_mutations_attempted": self.total_mutations_attempted,
            "skipped_mutations": self.skipped_mutations,
            "threshold": self.config.predictor_threshold,
            "failure_insights_count": len(self.failure_insights)
        }

    def reset_counters(self) -> None:
        """Reset all counters and insights."""
        self.predicted_failures = 0
        self.total_mutations_attempted = 0
        self.skipped_mutations = 0
        self.failure_insights = []