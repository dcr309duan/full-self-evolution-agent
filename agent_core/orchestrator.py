from typing import List, Dict, Any, Optional
from agent_core.feasibility_estimator import FeasibilityEstimator
from agent_core.dependency_graph import DependencyGraph
from agent_core.backlog import Backlog
from agent_core.goal_executor import GoalExecutor
from agent_core.schema_version_checker import SchemaVersionChecker
from agent_core.schema_registry import SchemaRegistry, SchemaMismatchError
import logging

logger = logging.getLogger(__name__)


class Orchestrator:
    """
    Orchestrates goal execution by integrating feasibility checks,
    dependency management, and backlog prioritization.
    """

    def __init__(
        self,
        feasibility_estimator: FeasibilityEstimator,
        dependency_graph: DependencyGraph,
        backlog: Backlog,
        goal_executor: GoalExecutor,
        schema_version_checker: Optional[SchemaVersionChecker] = None,
        schema_registry: Optional[SchemaRegistry] = None,
    ):
        self.feasibility_estimator = feasibility_estimator
        self.dependency_graph = dependency_graph
        self.backlog = backlog
        self.goal_executor = goal_executor
        self.schema_version_checker = schema_version_checker or SchemaVersionChecker()
        self.schema_registry = schema_registry or SchemaRegistry()

    def run_cycle(self) -> None:
        """
        Execute one full cycle: check feasibility, execute goals, update dependencies,
        and re-prioritize the backlog.
        """
        goals = self.backlog.get_pending_goals()
        if not goals:
            logger.info("No pending goals in backlog.")
            return

        for goal in goals:
            self._process_goal(goal)

        self._update_dependencies()
        self._reprioritize_backlog()

    def _process_goal(self, goal: Dict[str, Any]) -> None:
        """
        Check feasibility of a goal and execute if possible.
        If blocked, log the reason and skip.
        """
        goal_id = goal.get("id", "unknown")
        logger.info(f"Processing goal: {goal_id}")

        # Check schema version compatibility before feasibility check
        if not self._check_schema_compatibility(goal):
            return

        # Validate inter-module call before feasibility check
        if not self._validate_inter_module_call("orchestrator", "feasibility_estimator", goal):
            return

        if not self.feasibility_estimator.is_feasible(goal):
            reason = self.feasibility_estimator.get_blocking_reason(goal)
            logger.warning(f"Goal {goal_id} is blocked: {reason}")
            self.backlog.mark_blocked(goal_id, reason)
            return

        # Validate inter-module call before goal execution
        if not self._validate_inter_module_call("orchestrator", "goal_executor", goal):
            return

        try:
            self.goal_executor.execute(goal)
            logger.info(f"Goal {goal_id} completed successfully.")
            self.backlog.mark_completed(goal_id)
        except Exception as e:
            logger.error(f"Goal {goal_id} failed during execution: {e}")
            self.backlog.mark_failed(goal_id, str(e))

    def _validate_inter_module_call(self, source: str, target: str, goal: Dict[str, Any]) -> bool:
        """
        Validate inter-module call using schema registry.
        Returns True if call is valid, False if blocked.
        """
        goal_id = goal.get("id", "unknown")
        max_retries = 3
        retry_count = 0

        while retry_count < max_retries:
            try:
                self.schema_registry.validate_inter_module_call(source, target)
                return True
            except SchemaMismatchError as e:
                logger.warning(
                    f"Inter-module call blocked from {source} to {target} "
                    f"for goal {goal_id}: {e}"
                )
                # Attempt to re-register schemas if version mismatch detected
                if "version mismatch" in str(e).lower():
                    logger.info(
                        f"Attempting to re-register schemas for {source} and {target} "
                        f"(attempt {retry_count + 1}/{max_retries})"
                    )
                    try:
                        self.schema_registry.register_schema(source, self.schema_version_checker.get_current_version())
                        self.schema_registry.register_schema(target, self.schema_version_checker.get_current_version())
                        retry_count += 1
                        continue
                    except Exception as reg_error:
                        logger.error(
                            f"Failed to re-register schemas for {source} and {target}: {reg_error}"
                        )
                        self.backlog.mark_blocked(
                            goal_id,
                            f"Inter-module call blocked from {source} to {target}: {str(e)}"
                        )
                        return False
                else:
                    logger.error(
                        f"Non-retryable schema mismatch from {source} to {target} "
                        f"for goal {goal_id}: {e}"
                    )
                    self.backlog.mark_blocked(
                        goal_id,
                        f"Inter-module call blocked from {source} to {target}: {str(e)}"
                    )
                    return False

        logger.error(
            f"Max retries reached for inter-module call from {source} to {target} "
            f"for goal {goal_id}"
        )
        self.backlog.mark_blocked(
            goal_id,
            f"Inter-module call blocked from {source} to {target} after {max_retries} retries"
        )
        return False

    def _check_schema_compatibility(self, goal: Dict[str, Any]) -> bool:
        """
        Check schema version compatibility between modules before inter-module calls.
        Returns True if compatible, False if mismatch detected.
        """
        goal_id = goal.get("id", "unknown")
        
        # Get schema versions from relevant modules
        feasibility_version = self.feasibility_estimator.get_schema_version()
        executor_version = self.goal_executor.get_schema_version()
        dependency_version = self.dependency_graph.get_schema_version()
        backlog_version = self.backlog.get_schema_version()

        # Check compatibility between orchestrator and each module
        if not self.schema_version_checker.check_compatibility(
            self.schema_version_checker.get_current_version(),
            feasibility_version
        ):
            logger.critical(
                f"Schema version mismatch between orchestrator and feasibility estimator "
                f"for goal {goal_id}: orchestrator={self.schema_version_checker.get_current_version()}, "
                f"feasibility_estimator={feasibility_version}"
            )
            self._handle_schema_mismatch(goal, "feasibility_estimator")
            return False

        if not self.schema_version_checker.check_compatibility(
            self.schema_version_checker.get_current_version(),
            executor_version
        ):
            logger.critical(
                f"Schema version mismatch between orchestrator and goal executor "
                f"for goal {goal_id}: orchestrator={self.schema_version_checker.get_current_version()}, "
                f"goal_executor={executor_version}"
            )
            self._handle_schema_mismatch(goal, "goal_executor")
            return False

        if not self.schema_version_checker.check_compatibility(
            self.schema_version_checker.get_current_version(),
            dependency_version
        ):
            logger.critical(
                f"Schema version mismatch between orchestrator and dependency graph "
                f"for goal {goal_id}: orchestrator={self.schema_version_checker.get_current_version()}, "
                f"dependency_graph={dependency_version}"
            )
            self._handle_schema_mismatch(goal, "dependency_graph")
            return False

        if not self.schema_version_checker.check_compatibility(
            self.schema_version_checker.get_current_version(),
            backlog_version
        ):
            logger.critical(
                f"Schema version mismatch between orchestrator and backlog "
                f"for goal {goal_id}: orchestrator={self.schema_version_checker.get_current_version()}, "
                f"backlog={backlog_version}"
            )
            self._handle_schema_mismatch(goal, "backlog")
            return False

        return True

    def _handle_schema_mismatch(self, goal: Dict[str, Any], module_name: str) -> None:
        """
        Handle schema version mismatch by triggering migration and blocking the goal.
        """
        goal_id = goal.get("id", "unknown")
        logger.info(f"Triggering schema migration for goal {goal_id} due to mismatch in {module_name}")
        
        # Attempt to migrate the module to compatible schema version
        try:
            if module_name == "feasibility_estimator":
                self.feasibility_estimator.migrate_schema(self.schema_version_checker.get_current_version())
            elif module_name == "goal_executor":
                self.goal_executor.migrate_schema(self.schema_version_checker.get_current_version())
            elif module_name == "dependency_graph":
                self.dependency_graph.migrate_schema(self.schema_version_checker.get_current_version())
            elif module_name == "backlog":
                self.backlog.migrate_schema(self.schema_version_checker.get_current_version())
            
            # Re-check compatibility after migration
            if self._check_schema_compatibility(goal):
                logger.info(f"Schema migration successful for {module_name} on goal {goal_id}")
            else:
                logger.error(f"Schema migration failed for {module_name} on goal {goal_id}")
                self.backlog.mark_blocked(goal_id, f"Schema version mismatch in {module_name} after migration attempt")
        except Exception as e:
            logger.error(f"Schema migration failed for {module_name} on goal {goal_id}: {e}")
            self.backlog.mark_blocked(goal_id, f"Schema migration error in {module_name}: {str(e)}")

    def _update_dependencies(self) -> None:
        """
        After each cycle, update the dependency graph by marking prerequisites
        as satisfied for all completed goals.
        """
        completed_goals = self.backlog.get_completed_goals()
        for goal in completed_goals:
            goal_id = goal.get("id")
            if goal_id:
                # Check schema compatibility before dependency update
                if self._check_schema_compatibility(goal):
                    # Validate inter-module call before dependency update
                    if self._validate_inter_module_call("orchestrator", "dependency_graph", goal):
                        self.dependency_graph.mark_prerequisites_satisfied(goal_id)
                        logger.debug(f"Dependencies updated for goal: {goal_id}")

    def _reprioritize_backlog(self) -> None:
        """
        Re-prioritize the backlog based on updated dependency status and feasibility.
        """
        self.backlog.reprioritize()
        logger.info("Backlog re-prioritized.")