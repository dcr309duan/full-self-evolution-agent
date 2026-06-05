"""unified_evolution_loop_orchestrator.py

Integrates the proactive_redesign_orchestrator into the main evolution loop.
Before executing retry logic for a failed goal, checks if failure analysis
suggests a redesign is needed. If so, executes the redesign goal first,
then retries the original goal with the modified component.
Also integrates integration_test_suite execution after successful mutations.
Integrates meta_mutation_engine to check for meta-mutations after each evolution cycle.
Integrates rollback_manager to verify and rollback after each mutation application.
Integrates curiosity_module to inject exploration tasks with configurable probability.
Integrates DependencyScheduler to manage mutation dependencies and bottleneck resolution.
Integrates self-consistency test suite to verify module consistency after mutations.
"""

import logging
import random
from typing import Any, Dict, List, Optional, Tuple

from proactive_redesign_orchestrator import ProactiveRedesignOrchestrator
from goal_manager import GoalManager
from failure_analyzer import FailureAnalyzer
from component_registry import ComponentRegistry
from execution_engine import ExecutionEngine
from integration_test_suite import IntegrationTestSuite
from meta_mutation_engine import MetaMutationEngine
from rollback_manager import RollbackManager
from curiosity_module import CuriosityModule
from dependency_scheduler import DependencyScheduler
from self_consistency_test_suite import SelfConsistencyTestSuite

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
        meta_mutation_engine: MetaMutationEngine,
        rollback_manager: RollbackManager,
        curiosity_module: CuriosityModule,
        dependency_scheduler: DependencyScheduler,
        self_consistency_test_suite: SelfConsistencyTestSuite,
        max_retries: int = 3,
        curiosity_enabled: bool = True,
        curiosity_probability: float = 0.3,
    ):
        self.goal_manager = goal_manager
        self.failure_analyzer = failure_analyzer
        self.component_registry = component_registry
        self.execution_engine = execution_engine
        self.redesign_orchestrator = redesign_orchestrator
        self.integration_test_suite = integration_test_suite
        self.meta_mutation_engine = meta_mutation_engine
        self.rollback_manager = rollback_manager
        self.curiosity_module = curiosity_module
        self.dependency_scheduler = dependency_scheduler
        self.self_consistency_test_suite = self_consistency_test_suite
        self.max_retries = max_retries
        self.curiosity_enabled = curiosity_enabled
        self.curiosity_probability = curiosity_probability
        self._loop_active = False
        self.validation_failure_count = 0
        self.degraded_cycles = 0
        self.cycle_number = 0
        self.recent_failures = 0
        self.consecutive_successes = 0
        self.state_store = {}  # Stores module states: 'needs_verification', 'verified_consistent', etc.

    def run_evolution_loop(self) -> None:
        """Main evolution loop that integrates redesign and integration testing when needed."""
        self._loop_active = True
        while self._loop_active:
            goal = self.goal_manager.get_next_goal()
            if goal is None:
                logger.info("No more goals to process. Evolution loop complete.")
                break

            self._process_goal_with_redesign(goal)
            self.cycle_number += 1
            
            # After each evolution cycle, check for meta-mutation
            aggregated_stats = self._get_aggregated_stats()
            self._check_and_apply_meta_mutation(aggregated_stats)

    def _get_aggregated_stats(self) -> Dict[str, Any]:
        """Aggregate stats from reflection parser and meta-evaluation loop."""
        stats = {
            "cycle_number": self.cycle_number,
            "validation_failure_count": self.validation_failure_count,
            "degraded_cycles": self.degraded_cycles,
            "recent_failures": self.recent_failures,
            "consecutive_successes": self.consecutive_successes,
            "goals_pending": self.goal_manager.get_pending_goal_count(),
            "goals_completed": self.goal_manager.get_completed_goal_count(),
            "goals_failed": self.goal_manager.get_failed_goal_count(),
            "component_count": self.component_registry.get_component_count(),
        }
        return stats

    def _check_and_apply_meta_mutation(self, aggregated_stats: Dict[str, Any]) -> None:
        """Check if meta-mutation is needed and apply it when system is stable."""
        # Check if system is in a stable state (no recent failures)
        if self._is_system_stable():
            logger.info(f"System is stable. Checking meta-mutation for cycle {self.cycle_number}")
            try:
                meta_result = self.meta_mutation_engine.evaluate_and_mutate(
                    cycle_number=self.cycle_number,
                    aggregated_stats=aggregated_stats
                )
                
                if meta_result.get("mutation_applied", False):
                    logger.info(f"Meta-mutation applied successfully at cycle {self.cycle_number}")
                    logger.info(f"Meta-mutation details: {meta_result.get('details', {})}")
                    
                    # Update system state based on meta-mutation
                    if "modified_parameters" in meta_result:
                        self._apply_meta_mutation_parameters(meta_result["modified_parameters"])
                else:
                    logger.debug(f"No meta-mutation needed at cycle {self.cycle_number}")
                    
            except Exception as e:
                logger.error(f"Error during meta-mutation evaluation at cycle {self.cycle_number}: {e}")
        else:
            logger.debug(f"System not stable (recent_failures={self.recent_failures}), skipping meta-mutation check")

    def _is_system_stable(self) -> bool:
        """Check if the system is in a stable state for meta-mutation."""
        # System is stable if there are no recent failures and no degraded cycles
        return self.recent_failures == 0 and self.degraded_cycles == 0

    def _apply_meta_mutation_parameters(self, parameters: Dict[str, Any]) -> None:
        """Apply modified parameters from meta-mutation to the system."""
        try:
            if "max_retries" in parameters:
                new_max_retries = parameters["max_retries"]
                if isinstance(new_max_retries, int) and new_max_retries > 0:
                    logger.info(f"Updating max_retries from {self.max_retries} to {new_max_retries}")
                    self.max_retries = new_max_retries
                    
            if "validation_threshold" in parameters:
                # Apply validation threshold changes if applicable
                logger.info(f"Validation threshold updated: {parameters['validation_threshold']}")
                
            if "mutation_rate" in parameters:
                # Apply mutation rate changes if applicable
                logger.info(f"Mutation rate updated: {parameters['mutation_rate']}")
                
            logger.info(f"Meta-mutation parameters applied successfully")
            
        except Exception as e:
            logger.error(f"Error applying meta-mutation parameters: {e}")

    def _process_goal_with_redesign(self, goal: Dict[str, Any]) -> None:
        """Process a single goal, potentially triggering redesign on failure."""
        goal_id = goal.get("id", "unknown")
        logger.info(f"Processing goal: {goal_id}")

        # Step 1: Identify bottleneck before mutation cycle
        bottleneck = self.dependency_scheduler.get_bottleneck()
        if bottleneck:
            logger.info(f"Bottleneck identified: {bottleneck}")
            # Step 2: Prioritize mutations that unblock the bottleneck
            self._prioritize_bottleneck_mutations(bottleneck)

        for attempt in range(1, self.max_retries + 1):
            logger.info(f"Attempt {attempt}/{self.max_retries} for goal {goal_id}")

            # Check goal feasibility before mutation execution
            feasibility_check = self._check_goal_feasibility(goal)
            if not feasibility_check.get("feasible", True):
                logger.warning(f"Goal {goal_id} is not feasible: {feasibility_check.get('reason', 'unknown')}")
                self.goal_manager.mark_goal_failed(goal_id, "not_feasible")
                return

            # Inject exploration tasks after feasibility check and before mutation execution
            if self.curiosity_enabled and random.random() < self.curiosity_probability:
                self._inject_exploration_tasks(goal_id)

            # Step 3: Verify prerequisites before mutating any module
            module_id = goal.get("target_component", "")
            if module_id:
                prerequisites_met = self.dependency_scheduler.verify_prerequisites(module_id)
                if not prerequisites_met:
                    logger.warning(f"Prerequisites not met for module {module_id}. Skipping mutation for goal {goal_id}")
                    self.goal_manager.mark_goal_failed(goal_id, "prerequisites_not_met")
                    return

            result = self.execution_engine.execute_goal(goal)

            if result.get("success", False):
                logger.info(f"Goal {goal_id} succeeded on attempt {attempt}")
                self.consecutive_successes += 1
                self.recent_failures = 0
                
                # After successful mutation and test run, execute integration tests
                if self._is_mutation_goal(goal):
                    # Step 4: Update state to 'needs_verification' after successful mutation
                    if module_id:
                        self.state_store[module_id] = "needs_verification"
                        logger.info(f"Module {module_id} state updated to 'needs_verification'")

                    integration_success = self._run_integration_tests(goal_id)
                    if not integration_success:
                        logger.warning(f"Integration tests failed after successful mutation for goal {goal_id}")
                        self.degraded_cycles += 1
                        logger.info(f"Degraded cycles count incremented to {self.degraded_cycles}")
                        self.goal_manager.mark_goal_completed(goal_id, status="degraded")
                        return
                    
                    # Step 5: Run self-consistency checks before marking as verified_consistent
                    self_consistency_success = self._run_self_consistency_checks(goal_id, module_id)
                    if not self_consistency_success:
                        logger.warning(f"Self-consistency checks failed for goal {goal_id}")
                        if module_id:
                            self.state_store[module_id] = "failed"
                            logger.info(f"Module {module_id} state updated to 'failed'")
                        # Trigger rollback
                        rollback_result = self.rollback_manager.verify_and_rollback()
                        if rollback_result.get("rollback_performed", False):
                            logger.warning(f"Rollback performed after self-consistency failure for goal {goal_id}")
                            self._pause_for_rollback_processing(goal_id, rollback_result)
                        self.goal_manager.mark_goal_completed(goal_id, status="self_consistency_failed")
                        return
                    
                    # Step 6: Update state to 'verified_consistent' after self-consistency checks pass
                    if module_id:
                        self.state_store[module_id] = "verified_consistent"
                        logger.info(f"Module {module_id} state updated to 'verified_consistent'")

                    # After mutation application and before proceeding to next cycle,
                    # verify and rollback if needed
                    rollback_result = self.rollback_manager.verify_and_rollback()
                    if rollback_result.get("rollback_performed", False):
                        logger.warning(f"Rollback performed after mutation for goal {goal_id}")
                        # Pause the loop to allow goal generator to process failure insight
                        self._pause_for_rollback_processing(goal_id, rollback_result)
                        self.goal_manager.mark_goal_completed(goal_id, status="rolled_back")
                        return
                
                self.goal_manager.mark_goal_completed(goal_id)
                return

            # Goal failed - analyze failure
            self.recent_failures += 1
            self.consecutive_successes = 0
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

    def _run_self_consistency_checks(self, goal_id: str, module_id: str) -> bool:
        """Run self-consistency tests on the module and return success status."""
        try:
            logger.info(f"Running self-consistency checks for module {module_id} after goal {goal_id}")
            consistency_results = self.self_consistency_test_suite.run_tests(module_id)
            
            if consistency_results.get("success", False):
                logger.info(f"Self-consistency checks passed for module {module_id}")
                return True
            else:
                failure_details = consistency_results.get("failures", [])
                for failure in failure_details:
                    logger.error(f"Self-consistency check failure for module {module_id}: {failure.get('test_name', 'unknown')}")
                    logger.error(f"Failure trace: {failure.get('traceback', 'No traceback available')}")
                    self._log_to_reflection_system(goal_id, failure)
                return False
                
        except Exception as e:
            logger.exception(f"Error running self-consistency checks for module {module_id}: {e}")
            self._log_to_reflection_system(goal_id, {"error": str(e), "traceback": logging.traceback.format_exc()})
            return False

    def _prioritize_bottleneck_mutations(self, bottleneck: str) -> None:
        """Prioritize mutations that unblock the identified bottleneck."""
        try:
            # Get pending goals from goal manager
            pending_goals = self.goal_manager.get_pending_goals()
            
            # Filter goals that target the bottleneck module or its dependencies
            bottleneck_goals = []
            for goal in pending_goals:
                target = goal.get("target_component", "")
                if target == bottleneck or self.dependency_scheduler.is_dependency_of(bottleneck, target):
                    bottleneck_goals.append(goal)
            
            # Reorder goals to prioritize bottleneck-related mutations
            if bottleneck_goals:
                logger.info(f"Prioritizing {len(bottleneck_goals)} goals related to bottleneck {bottleneck}")
                # Move bottleneck goals to the front of the queue
                self.goal_manager.reorder_goals(bottleneck_goals, priority="high")
                
        except Exception as e:
            logger.error(f"Error prioritizing bottleneck mutations: {e}")

    def _check_goal_feasibility(self, goal: Dict[str, Any]) -> Dict[str, Any]:
        """Check if a goal is feasible before execution."""
        try:
            # Basic feasibility checks
            goal_type = goal.get("type", "")
            target_component = goal.get("target_component")
            
            if not goal_type:
                return {"feasible": False, "reason": "Goal has no type"}
            
            if not target_component:
                return {"feasible": False, "reason": "Goal has no target component"}
            
            # Check if target component exists in registry
            if not self.component_registry.has_component(target_component):
                return {"feasible": False, "reason": f"Target component {target_component} not found"}
            
            # Check if goal type is supported
            supported_types = ["mutation", "redesign", "exploration", "optimization"]
            if goal_type not in supported_types:
                return {"feasible": False, "reason": f"Unsupported goal type: {goal_type}"}
            
            return {"feasible": True}
            
        except Exception as e:
            logger.error(f"Error checking goal feasibility: {e}")
            return {"feasible": False, "reason": str(e)}

    def _inject_exploration_tasks(self, goal_id: str) -> None:
        """Inject exploration tasks from curiosity module with lower priority."""
        try:
            logger.info(f"Injecting exploration tasks for goal {goal_id}")
            
            # Get exploration tasks from curiosity module
            exploration_tasks = self.curiosity_module.inject_exploration_tasks()
            
            if not exploration_tasks:
                logger.debug(f"No exploration tasks generated for goal {goal_id}")
                return
            
            # Assign lower priority to exploration tasks
            for task in exploration_tasks:
                task["priority"] = "low"
                task["parent_goal_id"] = goal_id
                task["type"] = "exploration"
                
                # Add to goal manager with low priority
                self.goal_manager.add_goal(task, priority="low")
                logger.info(f"Added exploration task: {task.get('id', 'unknown')} with low priority")
                
        except Exception as e:
            logger.error(f"Error injecting exploration tasks for goal {goal_id}: {e}")

    def _pause_for_rollback_processing(self, goal_id: str, rollback_result: Dict[str, Any]) -> None:
        """Pause the evolution loop to allow goal generator to process rollback failure insight."""
        logger.info(f"Pausing evolution loop for rollback processing of goal {goal_id}")
        
        # Log the rollback failure insight for the goal generator
        failure_insight = {
            "goal_id": goal_id,
            "rollback_reason": rollback_result.get("reason", "unknown"),
            "rollback_details": rollback_result.get("details", {}),
            "cycle_number": self.cycle_number,
            "timestamp": logging.time.time() if hasattr(logging.time, 'time') else None
        }
        
        # Notify the goal generator about the failure insight
        try:
            self.goal_manager.process_rollback_insight(failure_insight)
            logger.info(f"Rollback failure insight processed for goal {goal_id}")
        except Exception as e:
            logger.error(f"Failed to process rollback insight for goal {goal_id}: {e}")
        
        # The loop will naturally continue to the next iteration after this method returns
        # The goal generator should have processed the insight and adjusted future goals accordingly

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

    def _validate_reflection_output(self, reflection_output: Dict[str, Any]) -> Dict[str, Any]:
        """Validate reflection parser output and compute defaults for missing fields."""
        validated_output = dict(reflection_output)
        
        # Check and set default for meta_mutation_directives
        if "meta_mutation_directives" not in validated_output:
            logger.debug("Missing 'meta_mutation_directives' in reflection output. Setting default: []")
            validated_output["meta_mutation_directives"] = []
        else:
            logger.debug(f"'meta_mutation_directives' present in reflection output: {validated_output['meta_mutation_directives']}")
        
        # Check and set default for exploration_task_acceptance
        if "exploration_task_acceptance" not in validated_output:
            logger.debug("Missing 'exploration_task_acceptance' in reflection output. Setting default: {'accepted': False, 'task_spec': None}")
            validated_output["exploration_task_acceptance"] = {"accepted": False, "task_spec": None}
        else:
            logger.debug(f"'exploration_task_acceptance' present in reflection output: {validated_output['exploration_task_acceptance']}")
        
        return validated_output

    def _process_reflection_output(self, reflection_output: Dict[str, Any]) -> Dict[str, Any]:
        """Process reflection output with schema alignment before passing to goal generator."""
        # Validate and align the reflection output schema
        aligned_output = self._validate_reflection_output(reflection_output)
        
        # Log the schema alignment decisions
        logger.info(f"Schema alignment completed for reflection output. "
                    f"meta_mutation_directives: {aligned_output.get('meta_mutation_directives')}, "
                    f"exploration_task_acceptance: {aligned_output.get('exploration_task_acceptance')}")
        
        return aligned_output

    def stop_evolution_loop(self) -> None:
        """Gracefully stop the evolution loop."""
        self._loop_active = False
        logger.info("Evolution loop stop requested")

    def get_status(self) -> Dict[str, Any]:
        """Get current status of the evolution loop."""
        return {
            "active": self._loop_active,
            "cycle_number": self.cycle_number,
            "goals_pending": self.goal_manager.get_pending_goal_count(),
            "goals_completed": self.goal_manager.get_completed_goal_count(),
            "goals_failed": self.goal_manager.get_failed_goal_count(),
            "components": self.component_registry.get_component_count(),
            "validation_failure_count": self.validation_failure_count,
            "degraded_cycles": self.degraded_cycles,
            "recent_failures": self.recent_failures,
            "consecutive_successes": self.consecutive_successes,
            "max_retries": self.max_retries,
            "curiosity_enabled": self.curiosity_enabled,
            "curiosity_probability": self.curiosity_probability,
            "state_store": self.state_store,
        }