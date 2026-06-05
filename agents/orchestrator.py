from typing import Dict, Any, Optional
import logging
from datetime import datetime
from enum import Enum

from agents.feasibility_estimator import FeasibilityEstimator, FeasibilityResult
from agents.goal_manager import GoalManager
from agents.execution_logger import ExecutionLogger
from agents.clone_and_promote import clone_and_promote_integration_test
from agents.mutation_engine import static_validator

logger = logging.getLogger(__name__)

class ExecutionStatus(Enum):
    FEASIBILITY_CHECK_FAILED = "feasibility_check_failed"
    EXECUTED = "executed"
    BLOCKED = "blocked"

class Orchestrator:
    """
    Orchestrator that manages goal execution with pre-execution feasibility checks.
    Before executing any goal, it runs the feasibility estimator. If the score is
    below threshold or the goal is blocked, execution is skipped and the reason is logged.
    """

    def __init__(
        self,
        goal_manager: GoalManager,
        feasibility_estimator: FeasibilityEstimator,
        execution_logger: ExecutionLogger,
        feasibility_threshold: float = 0.5
    ):
        self.goal_manager = goal_manager
        self.feasibility_estimator = feasibility_estimator
        self.execution_logger = execution_logger
        self.feasibility_threshold = feasibility_threshold
        self._mutation_operations_halted = False
        self.static_validation_failures = 0
        
        # Run clone_and_promote integration test during initialization
        self._verify_clone_and_promote()
        
        # Run static validator on the mutation engine module itself
        self._verify_static_validator()

    def _verify_clone_and_promote(self) -> None:
        """
        Run the clone_and_promote integration test to verify the mechanism is working.
        If the test fails, log a critical error and halt mutation operations.
        """
        try:
            test_result = clone_and_promote_integration_test()
            if not test_result:
                logger.critical(
                    "Clone and promote integration test FAILED. "
                    "Mutation operations are halted to prevent data corruption."
                )
                self._mutation_operations_halted = True
            else:
                logger.info(
                    "Clone and promote integration test PASSED. "
                    "Mutation operations are enabled."
                )
        except Exception as e:
            logger.critical(
                f"Clone and promote integration test raised an exception: {e}. "
                "Mutation operations are halted to prevent data corruption."
            )
            self._mutation_operations_halted = True

    def _verify_static_validator(self) -> None:
        """
        Run static_validator on the mutation engine module itself to ensure
        the validator works on real code. Increments static_validation_failures
        counter if validation fails.
        """
        try:
            from agents import mutation_engine
            validation_result = static_validator(mutation_engine)
            if not validation_result:
                self.static_validation_failures += 1
                logger.error(
                    "Static validation of mutation engine module FAILED. "
                    "Incrementing static_validation_failures counter."
                )
            else:
                logger.info(
                    "Static validation of mutation engine module PASSED."
                )
        except Exception as e:
            self.static_validation_failures += 1
            logger.error(
                f"Static validation of mutation engine module raised an exception: {e}. "
                "Incrementing static_validation_failures counter."
            )

    def execute_goal(self, goal_id: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Execute a single goal after performing a feasibility check.
        
        Args:
            goal_id: Identifier for the goal to execute.
            context: Optional context dictionary for feasibility estimation.
            
        Returns:
            Dictionary containing execution log with feasibility_check field.
        """
        # Check if mutation operations are halted
        if self._mutation_operations_halted:
            execution_log = {
                "goal_id": goal_id,
                "timestamp": datetime.utcnow().isoformat(),
                "status": ExecutionStatus.BLOCKED.value,
                "message": "Mutation operations are halted due to failed clone_and_promote integration test"
            }
            logger.error(f"Goal {goal_id} blocked: Mutation operations halted")
            self.execution_logger.log(execution_log)
            return execution_log

        goal = self.goal_manager.get_goal(goal_id)
        if not goal:
            raise ValueError(f"Goal {goal_id} not found")

        # Perform feasibility check
        feasibility_result = self.feasibility_estimator.estimate(goal, context or {})
        
        execution_log = {
            "goal_id": goal_id,
            "timestamp": datetime.utcnow().isoformat(),
            "feasibility_check": {
                "score": feasibility_result.score,
                "blocked": feasibility_result.blocked,
                "reason": feasibility_result.reason,
                "threshold": self.feasibility_threshold
            }
        }

        # Check if execution should proceed
        if feasibility_result.blocked or feasibility_result.score < self.feasibility_threshold:
            execution_log["status"] = ExecutionStatus.FEASIBILITY_CHECK_FAILED.value
            execution_log["message"] = (
                f"Goal execution skipped: {feasibility_result.reason or 'Feasibility score below threshold'}"
            )
            logger.warning(
                f"Goal {goal_id} skipped. Score: {feasibility_result.score}, "
                f"Blocked: {feasibility_result.blocked}, Reason: {feasibility_result.reason}"
            )
            self.execution_logger.log(execution_log)
            return execution_log

        # Proceed with execution
        try:
            execution_result = self._execute(goal, context)
            execution_log["status"] = ExecutionStatus.EXECUTED.value
            execution_log["result"] = execution_result
            execution_log["message"] = "Goal executed successfully"
        except Exception as e:
            execution_log["status"] = ExecutionStatus.BLOCKED.value
            execution_log["message"] = f"Execution failed: {str(e)}"
            logger.error(f"Goal {goal_id} execution failed: {e}")

        self.execution_logger.log(execution_log)
        return execution_log

    def execute_all_goals(self, context: Optional[Dict[str, Any]] = None) -> list[Dict[str, Any]]:
        """
        Execute all pending goals with feasibility checks.
        
        Args:
            context: Optional context dictionary for feasibility estimation.
            
        Returns:
            List of execution logs for each goal.
        """
        goals = self.goal_manager.get_pending_goals()
        logs = []
        for goal in goals:
            log = self.execute_goal(goal.id, context)
            logs.append(log)
        return logs

    def _execute(self, goal: Any, context: Optional[Dict[str, Any]] = None) -> Any:
        """
        Internal method to actually execute a goal.
        Override this in subclasses for custom execution logic.
        
        Args:
            goal: The goal object to execute.
            context: Optional context dictionary.
            
        Returns:
            Result of the goal execution.
        """
        # Placeholder for actual execution logic
        logger.info(f"Executing goal {goal.id}")
        return {"executed": True, "goal_id": goal.id}

    def get_monitoring_dashboard(self) -> Dict[str, Any]:
        """
        Returns monitoring dashboard data including static_validation_failures counter.
        """
        return {
            "static_validation_failures": self.static_validation_failures,
            "mutation_operations_halted": self._mutation_operations_halted
        }