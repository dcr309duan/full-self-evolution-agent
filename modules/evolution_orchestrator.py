"""Evolution Orchestrator - Integrates static predictor into mutation pipeline."""

import logging
from typing import Any, Callable, Dict, Optional, List
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
    """Orchestrates mutation pipeline with predictive filtering and git workflow."""

    def __init__(self, config: Optional[OrchestratorConfig] = None):
        self.config = config or OrchestratorConfig()
        self.predicted_failures = 0
        self.total_mutations_attempted = 0
        self.skipped_mutations = 0
        self.failure_insights: list = []
        self._predictor = None
        self._cycle_count = 0
        self._git_orchestrator = None
        self._nash_detector = None
        self._coordinated_planner = None
        self._coordinated_mode = False
        self._coordinated_cycles_remaining = 0
        self._equilibrium_detected = False
        self._coordinated_mutation_outcomes: List[Dict[str, Any]] = []

    def set_predictor(self, predictor: Any) -> None:
        """Set the static predictor instance."""
        self._predictor = predictor

    def set_git_orchestrator(self, git_orchestrator: Any) -> None:
        """Set the git orchestrator instance."""
        self._git_orchestrator = git_orchestrator

    def set_nash_detector(self, detector: Any) -> None:
        """Set the Nash equilibrium detector instance."""
        self._nash_detector = detector

    def set_coordinated_planner(self, planner: Any) -> None:
        """Set the coordinated mutation planner instance."""
        self._coordinated_planner = planner

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

    def _check_nash_equilibrium(self) -> bool:
        """Check if Nash equilibrium is detected."""
        if self._nash_detector is None:
            return False
        
        try:
            equilibrium_detected = self._nash_detector.detect_equilibrium()
            if equilibrium_detected:
                logger.info("Nash equilibrium detected by detector")
                self._equilibrium_detected = True
                return True
        except Exception as e:
            logger.warning("Nash equilibrium detection failed: %s", e)
        
        return False

    def _generate_mutation_bundles(self) -> List[Any]:
        """Generate mutation bundles for coordinated mutation mode."""
        if self._coordinated_planner is None:
            return []
        
        try:
            bundles = self._coordinated_planner.plan_coordinated_mutations()
            logger.info("Generated %d mutation bundles for coordinated mode", len(bundles))
            return bundles
        except Exception as e:
            logger.error("Failed to generate mutation bundles: %s", e)
            return []

    def _apply_mutation_bundle(self, bundle: Any) -> bool:
        """Apply a mutation bundle atomically using git workflow.
        
        Args:
            bundle: The mutation bundle to apply
            
        Returns:
            True if bundle was applied successfully, False otherwise
        """
        if self._git_orchestrator is None:
            logger.warning("Git orchestrator not available, cannot apply bundle atomically")
            return False

        try:
            # Create a branch for the bundle
            self._git_orchestrator.git_create_branch(f"bundle-{self._cycle_count}")
            
            # Apply all mutations in the bundle
            for mutation in bundle.get("mutations", []):
                if not self.should_execute_mutation(mutation):
                    logger.warning("Mutation in bundle skipped by predictor")
                    self._git_orchestrator.git_rollback()
                    return False
                
                try:
                    mutation.execute()
                except Exception as e:
                    logger.error("Mutation in bundle failed: %s", e)
                    self._git_orchestrator.git_rollback()
                    return False
            
            # Commit the entire bundle
            self._git_orchestrator.git_commit_mutation()
            logger.info("Mutation bundle applied successfully")
            return True
            
        except Exception as e:
            logger.error("Failed to apply mutation bundle: %s", e)
            try:
                self._git_orchestrator.git_rollback()
            except Exception as rollback_error:
                logger.error("Rollback after bundle failure failed: %s", rollback_error)
            return False

    def execute_mutation_pipeline(self, mutation: Any, executor_func: Callable) -> Any:
        """Execute a mutation through the pipeline with predictive filtering and git workflow.

        Args:
            mutation: The mutation to potentially execute.
            executor_func: Function that actually runs the mutation.

        Returns:
            Result of executor_func if mutation is executed, None if skipped.
        """
        self.total_mutations_attempted += 1
        self._cycle_count += 1

        # Safety check: abort if git working tree is dirty at start of cycle
        if self._git_orchestrator is not None:
            try:
                if self._git_orchestrator.is_working_tree_dirty():
                    logger.warning("Git working tree is dirty at start of mutation cycle. Aborting.")
                    return None
            except Exception as e:
                logger.warning("Failed to check git working tree status: %s", e)

        # Check for Nash equilibrium after standard mutation cycle
        if not self._coordinated_mode and self._check_nash_equilibrium():
            logger.info("Switching to coordinated mutation mode")
            self._coordinated_mode = True
            self._coordinated_cycles_remaining = 2  # Run coordinated mode for 1-2 cycles
        
        # Handle coordinated mutation mode
        if self._coordinated_mode:
            if self._coordinated_cycles_remaining > 0:
                self._coordinated_cycles_remaining -= 1
                
                # Generate and apply mutation bundles
                bundles = self._generate_mutation_bundles()
                if bundles:
                    for bundle in bundles:
                        success = self._apply_mutation_bundle(bundle)
                        self._coordinated_mutation_outcomes.append({
                            "cycle": self._cycle_count,
                            "bundle": str(bundle),
                            "success": success
                        })
                        if success:
                            logger.info("Coordinated mutation bundle applied successfully")
                        else:
                            logger.warning("Coordinated mutation bundle failed")
                
                # Check if coordinated mode should end
                if self._coordinated_cycles_remaining == 0:
                    logger.info("Returning to normal single-module optimization mode")
                    self._coordinated_mode = False
                    self._equilibrium_detected = False
                
                return None  # Coordinated mutations are handled differently
            else:
                self._coordinated_mode = False
                self._equilibrium_detected = False
                logger.info("Returning to normal single-module optimization mode")

        if not self.should_execute_mutation(mutation):
            return None

        # Pre-mutation git operations
        if self._git_orchestrator is not None:
            try:
                self._git_orchestrator.git_stash()
            except Exception as e:
                logger.warning("Git stash failed, attempting pre-mutation commit: %s", e)
                try:
                    self._git_orchestrator.git_commit_pre_mutation()
                except Exception as e2:
                    logger.error("Pre-mutation git operations failed: %s", e2)
                    return None

        try:
            result = executor_func(mutation)
            
            # Post-mutation validation and git operations
            if self._git_orchestrator is not None:
                try:
                    self._git_orchestrator.git_commit_mutation()
                except Exception as e:
                    logger.warning("Post-mutation git commit failed, rolling back: %s", e)
                    try:
                        self._git_orchestrator.git_rollback()
                    except Exception as e2:
                        logger.error("Git rollback failed: %s", e2)
                    return None
            
            return result
            
        except Exception as e:
            logger.error("Mutation execution failed: %s", e)
            # Rollback on failure
            if self._git_orchestrator is not None:
                try:
                    self._git_orchestrator.git_rollback()
                except Exception as e2:
                    logger.error("Git rollback after mutation failure failed: %s", e2)
            raise

    def get_stats(self) -> Dict[str, Any]:
        """Get orchestrator statistics."""
        stats = {
            "predicted_failures": self.predicted_failures,
            "total_mutations_attempted": self.total_mutations_attempted,
            "skipped_mutations": self.skipped_mutations,
            "threshold": self.config.predictor_threshold,
            "failure_insights_count": len(self.failure_insights),
            "coordinated_mode": self._coordinated_mode,
            "equilibrium_detected": self._equilibrium_detected,
            "coordinated_cycles_remaining": self._coordinated_cycles_remaining,
            "coordinated_mutation_outcomes_count": len(self._coordinated_mutation_outcomes)
        }
        return stats

    def reset_counters(self) -> None:
        """Reset all counters and insights."""
        self.predicted_failures = 0
        self.total_mutations_attempted = 0
        self.skipped_mutations = 0
        self.failure_insights = []
        self._coordinated_mutation_outcomes = []
        self._coordinated_mode = False
        self._coordinated_cycles_remaining = 0
        self._equilibrium_detected = False

    def get_decision_logic_state(self) -> Dict[str, Any]:
        """Return a serializable dict of the orchestrator's current decision parameters.

        Returns:
            Dictionary containing current decision parameters.
        """
        return {
            "goal_selection_threshold": self.config.predictor_threshold,
            "mutation_acceptance_criteria": "predictor_analysis",
            "cycle_count": self._cycle_count,
            "max_mutations": self.config.max_mutations,
            "parallel_workers": self.config.parallel_workers,
            "additional_params": dict(self.config.additional_params),
            "coordinated_mode": self._coordinated_mode,
            "equilibrium_detected": self._equilibrium_detected,
            "coordinated_cycles_remaining": self._coordinated_cycles_remaining
        }

    def apply_decision_mutation(self, mutation_spec: Dict[str, Any]) -> None:
        """Apply a targeted mutation to one decision parameter.

        Args:
            mutation_spec: Dictionary specifying the mutation. Supported keys:
                - "parameter": Name of the parameter to mutate.
                - "operation": Operation to perform ("add", "subtract", "set", "swap").
                - "value": Value for the operation (if applicable).

        Raises:
            ValueError: If the parameter or operation is invalid.
        """
        parameter = mutation_spec.get("parameter")
        operation = mutation_spec.get("operation")
        value = mutation_spec.get("value")

        if parameter == "goal_selection_threshold":
            if operation == "add":
                self.config.predictor_threshold += value
            elif operation == "subtract":
                self.config.predictor_threshold -= value
            elif operation == "set":
                self.config.predictor_threshold = value
            else:
                raise ValueError(f"Unsupported operation '{operation}' for parameter '{parameter}'")
        elif parameter == "mutation_acceptance_criteria":
            if operation == "swap":
                # Toggle between predictor_analysis and always_accept
                if self.config.additional_params.get("acceptance_criteria") == "always_accept":
                    self.config.additional_params["acceptance_criteria"] = "predictor_analysis"
                else:
                    self.config.additional_params["acceptance_criteria"] = "always_accept"
            else:
                raise ValueError(f"Unsupported operation '{operation}' for parameter '{parameter}'")
        elif parameter == "cycle_count":
            if operation == "set":
                self._cycle_count = value
            else:
                raise ValueError(f"Unsupported operation '{operation}' for parameter '{parameter}'")
        elif parameter == "max_mutations":
            if operation == "set":
                self.config.max_mutations = value
            else:
                raise ValueError(f"Unsupported operation '{operation}' for parameter '{parameter}'")
        elif parameter == "parallel_workers":
            if operation == "set":
                self.config.parallel_workers = value
            else:
                raise ValueError(f"Unsupported operation '{operation}' for parameter '{parameter}'")
        else:
            raise ValueError(f"Unknown parameter '{parameter}'")