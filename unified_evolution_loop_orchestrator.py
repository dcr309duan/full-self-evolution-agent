"""unified_evolution_loop_orchestrator.py

Integrates the proactive_redesign_orchestrator into the main evolution loop.
Before executing retry logic for a failed goal, checks if failure analysis
suggests a redesign is needed. If so, executes the redesign goal first,
then retries the original goal with the modified component.
Also integrates integration_test_suite execution after successful mutations.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

from proactive_redesign_orchestrator import ProactiveRedesignOrchestrator
from goal_manager import GoalManager
from failure_analyzer import FailureAnalyzer
from component_registry import ComponentRegistry
from execution_engine import ExecutionEngine
from integration_test_suite import IntegrationTestSuite

logger = logging.getLogger(__name__)


class UnifiedEvolutionLoopOrchestrator:
    """Orchestrates the evolution loop with integrated proactive redesign and integration testing."""

    def __init__(
        self,
        goal_manager: GoalManager,
        failure_analyzer: FailureAnalyzer,
        component_registry: ComponentRegistry,
        execution_engine: ExecutionEngine,
        redesign_orchestrator: ProactiveRedesignOrchestrator,
        integration_test_suite: IntegrationTestSuite,
        max_retries: int = 3,
    ):
        self.goal_manager = goal_manager
        self.failure_analyzer = failure_analyzer
        self.component_registry = component_registry
        self.execution_engine = execution_engine
        self.redesign_orchestrator = redesign_orchestrator
        self.integration_test_suite = integration_test_suite
        self.max_retries = max_retries
        self._loop_active = False
        self.validation_failure_count = 0
        self.degraded_cycles = 0

    def run_evolution_loop(self) -> None:
        """Main evolution loop that integrates redesign and integration testing when needed."""
        self._loop_active = True
        while self._loop_active:
            goal = self.goal_manager.get_next_goal()
            if goal is None:
                logger.info("No more goals to process. Evolution loop complete.")
                break

            self._process_goal_with_redesign(goal)

    def _process_goal_with_redesign(self, goal: Dict[str, Any]) -> None:
        """Process a single goal, potentially triggering redesign on failure."""
        goal_id = goal.get("id", "unknown")
        logger.info(f"Processing goal: {goal_id}")

        for attempt in range(1, self.max_retries + 1):
            logger.info(f"Attempt {attempt}/{self.max_retries} for goal {goal_id}")

            result = self.execution_engine.execute_goal(goal)

            if result.get("success", False):
                logger.info(f"Goal {goal_id} succeeded on attempt {attempt}")
                
                # After successful mutation and test run, execute integration tests
                if self._is_mutation_goal(goal):
                    integration_success = self._run_integration_tests(goal_id)
                    if not integration_success:
                        logger.warning(f"Integration tests failed after successful mutation for goal {goal_id}")
                        self.degraded_cycles += 1
                        logger.info(f"Degraded cycles count incremented to {self.degraded_cycles}")
                        self.goal_manager.mark_goal_completed(goal_id, status="degraded")
                        return
                
                self.goal_manager.mark_goal_completed(goal_id)
                return

            # Goal failed - analyze failure
            failure_analysis = self.failure_analyzer.analyze_failure(goal, result)
            logger.warning(f"Goal {goal_id} failed: {failure_analysis.get('reason', 'unknown')}")

            # Check if mutation was rejected by validator
            if self._is_validation_failure(result):
                self._log_validation_failure(goal_id, result)

            # Check if redesign is needed based on failure analysis
            if self._should_redesign(failure_analysis):
                logger.info(f"Redesign triggered for goal {goal_id}")
                redesign_success = self._execute_redesign(goal, failure_analysis)
                if not redesign_success:
                    logger.error(f"Redesign failed for goal {goal_id}. Aborting retries.")
                    self.goal_manager.mark_goal_failed(goal_id, "redesign_failed")
                    return
            else:
                logger.info(f"No redesign needed for goal {goal_id}. Retrying with current components.")

        # All retries exhausted
        logger.error(f"Goal {goal_id} failed after {self.max_retries} attempts")
        self.goal_manager.mark_goal_failed(goal_id, "max_retries_exceeded")

    def _is_mutation_goal(self, goal: Dict[str, Any]) -> bool:
        """Check if the goal involves a mutation operation."""
        goal_type = goal.get("type", "")
        return goal_type == "mutation" or "mutation" in goal.get("operation", "")

    def _run_integration_tests(self, goal_id: str) -> bool:
        """Run integration tests on the dummy module and return success status."""
        try:
            logger.info(f"Running integration tests after successful mutation for goal {goal_id}")
            test_results = self.integration_test_suite.run_tests()
            
            if test_results.get("success", False):
                logger.info(f"Integration tests passed for goal {goal_id}")
                return True
            else:
                # Log failure with full trace to reflection system
                failure_details = test_results.get("failures", [])
                for failure in failure_details:
                    logger.error(f"Integration test failure for goal {goal_id}: {failure.get('test_name', 'unknown')}")
                    logger.error(f"Failure trace: {failure.get('traceback', 'No traceback available')}")
                    # Log to reflection system
                    self._log_to_reflection_system(goal_id, failure)
                return False
                
        except Exception as e:
            logger.exception(f"Error running integration tests for goal {goal_id}: {e}")
            self._log_to_reflection_system(goal_id, {"error": str(e), "traceback": logging.traceback.format_exc()})
            return False

    def _log_to_reflection_system(self, goal_id: str, failure_info: Dict[str, Any]) -> None:
        """Log integration test failure to the reflection system."""
        try:
            reflection_entry = {
                "type": "integration_test_failure",
                "goal_id": goal_id,
                "failure_info": failure_info,
                "cycle_status": "degraded"
            }
            # Assuming there's a reflection system logger or storage
            logger.info(f"Reflection system entry: {reflection_entry}")
            # In a real implementation, this would write to a reflection database or log
        except Exception as e:
            logger.error(f"Failed to log to reflection system: {e}")

    def _is_validation_failure(self, result: Dict[str, Any]) -> bool:
        """Check if the failure was due to validation rejection."""
        failure_type = result.get("failure_type", "")
        return failure_type == "validation_rejection" or result.get("validation_failed", False)

    def _log_validation_failure(self, goal_id: str, result: Dict[str, Any]) -> None:
        """Log validation failure details and increment counter."""
        reason = result.get("validation_reason", "unknown")
        logger.warning(f"Validation failure for goal {goal_id}: {reason}")
        self.validation_failure_count += 1
        logger.info(f"Validation failure count incremented to {self.validation_failure_count}")

    def _should_redesign(self, failure_analysis: Dict[str, Any]) -> bool:
        """Determine if redesign is needed based on failure analysis."""
        # Check for explicit redesign suggestion
        if failure_analysis.get("suggest_redesign", False):
            return True

        # Check for specific failure patterns that indicate design issues
        failure_patterns = failure_analysis.get("patterns", [])
        redesign_indicators = [
            "performance_degradation",
            "structural_instability",
            "incompatible_interfaces",
            "resource_exhaustion",
            "design_constraint_violation",
        ]
        return any(pattern in redesign_indicators for pattern in failure_patterns)

    def _execute_redesign(
        self, goal: Dict[str, Any], failure_analysis: Dict[str, Any]
    ) -> bool:
        """Execute redesign for the failed goal."""
        try:
            # Identify the component that needs redesign
            component_id = self._identify_component_for_redesign(goal, failure_analysis)
            if component_id is None:
                logger.error("Could not identify component for redesign")
                return False

            # Create a redesign goal
            redesign_goal = self._create_redesign_goal(component_id, failure_analysis)

            # Execute the redesign
            redesign_result = self.redesign_orchestrator.execute_redesign(
                component_id, redesign_goal
            )

            if redesign_result.get("success", False):
                logger.info(f"Redesign successful for component {component_id}")
                # Update the component registry with the redesigned component
                self.component_registry.update_component(
                    component_id, redesign_result.get("modified_component", {})
                )
                return True
            else:
                logger.error(f"Redesign failed for component {component_id}")
                return False

        except Exception as e:
            logger.exception(f"Error during redesign execution: {e}")
            return False

    def _identify_component_for_redesign(
        self, goal: Dict[str, Any], failure_analysis: Dict[str, Any]
    ) -> Optional[str]:
        """Identify which component needs redesign based on failure analysis."""
        # Check if failure analysis explicitly identifies a component
        component_id = failure_analysis.get("component_id")
        if component_id:
            return component_id

        # Try to infer from the goal's target component
        target_component = goal.get("target_component")
        if target_component:
            return target_component

        # Fall back to the component that failed
        failed_component = failure_analysis.get("failed_component")
        if failed_component:
            return failed_component

        return None

    def _create_redesign_goal(
        self, component_id: str, failure_analysis: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create a redesign goal based on failure analysis."""
        return {
            "type": "redesign",
            "target_component": component_id,
            "failure_reason": failure_analysis.get("reason", "unknown"),
            "failure_patterns": failure_analysis.get("patterns", []),
            "requirements": failure_analysis.get("redesign_requirements", {}),
            "constraints": failure_analysis.get("redesign_constraints", {}),
            "priority": "high",
        }

    def stop_evolution_loop(self) -> None:
        """Gracefully stop the evolution loop."""
        self._loop_active = False
        logger.info("Evolution loop stop requested")

    def get_status(self) -> Dict[str, Any]:
        """Get current status of the evolution loop."""
        return {
            "active": self._loop_active,
            "goals_pending": self.goal_manager.get_pending_goal_count(),
            "goals_completed": self.goal_manager.get_completed_goal_count(),
            "goals_failed": self.goal_manager.get_failed_goal_count(),
            "components": self.component_registry.get_component_count(),
            "validation_failure_count": self.validation_failure_count,
            "degraded_cycles": self.degraded_cycles,
        }