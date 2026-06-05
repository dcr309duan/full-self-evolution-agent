"""Orchestrator module for managing the evolution engine's main loop."""

import os
import sys
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional
import logging

# Global flag indicating whether primitive validation has failed
PRIMITIVE_VALIDATION_FAILED = False

PRIMITIVE_TEST_PATH = Path("tests/test_new_file_creation_metamorphic.py")

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class DependencyAwareFeasibilityEstimator:
    """Estimates feasibility of goals based on dependency awareness."""
    
    def __init__(self):
        self.blocked_goals: List[Dict[str, Any]] = []
        self.completed_dependencies: set = set()
    
    def is_goal_blocked(self, goal: Dict[str, Any]) -> bool:
        """
        Check if a goal is blocked by unmet dependencies.
        
        Args:
            goal: Dictionary containing goal information including dependencies
            
        Returns:
            True if goal is blocked, False otherwise
        """
        dependencies = goal.get('dependencies', [])
        
        # Check if all dependencies are completed
        for dep in dependencies:
            if dep not in self.completed_dependencies:
                logger.info(f"Goal {goal.get('id', 'unknown')} is blocked by dependency: {dep}")
                return True
        
        return False
    
    def add_blocked_goal(self, goal: Dict[str, Any]) -> None:
        """Add a goal to the blocked goals list."""
        self.blocked_goals.append(goal)
        logger.info(f"Added goal {goal.get('id', 'unknown')} to blocked goals list")
    
    def mark_dependency_completed(self, dependency_id: str) -> None:
        """Mark a dependency as completed."""
        self.completed_dependencies.add(dependency_id)
        logger.info(f"Dependency {dependency_id} marked as completed")
    
    def re_evaluate_blocked_goals(self) -> List[Dict[str, Any]]:
        """
        Re-evaluate previously blocked goals when dependencies are completed.
        
        Returns:
            List of goals that are now unblocked
        """
        unblocked_goals = []
        remaining_blocked = []
        
        for goal in self.blocked_goals:
            if not self.is_goal_blocked(goal):
                unblocked_goals.append(goal)
                logger.info(f"Goal {goal.get('id', 'unknown')} is now unblocked")
            else:
                remaining_blocked.append(goal)
        
        self.blocked_goals = remaining_blocked
        return unblocked_goals


# Global instance of the feasibility estimator
feasibility_estimator = DependencyAwareFeasibilityEstimator()


def check_primitive_validation() -> None:
    """
    Check if the primitive test file exists and passes.
    If not, log the error and set the global flag.
    """
    global PRIMITIVE_VALIDATION_FAILED

    if not PRIMITIVE_TEST_PATH.exists():
        print(
            f"ERROR: Primitive test file not found: {PRIMITIVE_TEST_PATH}",
            file=sys.stderr
        )
        PRIMITIVE_VALIDATION_FAILED = True
        return

    try:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", str(PRIMITIVE_TEST_PATH), "-x", "--tb=short"],
            capture_output=True,
            text=True,
            timeout=60
        )
        if result.returncode != 0:
            print(
                f"ERROR: Primitive test failed: {PRIMITIVE_TEST_PATH}\n"
                f"STDOUT: {result.stdout}\n"
                f"STDERR: {result.stderr}",
                file=sys.stderr
            )
            PRIMITIVE_VALIDATION_FAILED = True
        else:
            PRIMITIVE_VALIDATION_FAILED = False
    except subprocess.TimeoutExpired:
        print(
            f"ERROR: Primitive test timed out: {PRIMITIVE_TEST_PATH}",
            file=sys.stderr
        )
        PRIMITIVE_VALIDATION_FAILED = True
    except Exception as e:
        print(
            f"ERROR: Unexpected error running primitive test: {e}",
            file=sys.stderr
        )
        PRIMITIVE_VALIDATION_FAILED = True


def schedule_goal(goal: Dict[str, Any]) -> bool:
    """
    Schedule a goal for execution after checking feasibility.
    
    Args:
        goal: Dictionary containing goal information
        
    Returns:
        True if goal was scheduled, False if blocked
    """
    global feasibility_estimator
    
    # Check if goal is blocked by dependencies
    if feasibility_estimator.is_goal_blocked(goal):
        logger.warning(f"Goal {goal.get('id', 'unknown')} is blocked by dependencies, not scheduling")
        feasibility_estimator.add_blocked_goal(goal)
        return False
    
    # Schedule the goal for execution
    logger.info(f"Goal {goal.get('id', 'unknown')} is feasible, scheduling for execution")
    # Actual scheduling logic would go here
    return True


def process_mutation_result(mutation_id: str, success: bool) -> None:
    """
    Process the result of a mutation and re-evaluate blocked goals.
    
    Args:
        mutation_id: Identifier of the mutation that was executed
        success: Whether the mutation was successful
    """
    global feasibility_estimator
    
    if success:
        # Mark the mutation as completed dependency
        feasibility_estimator.mark_dependency_completed(mutation_id)
        
        # Re-evaluate blocked goals
        unblocked_goals = feasibility_estimator.re_evaluate_blocked_goals()
        
        # Schedule newly unblocked goals
        for goal in unblocked_goals:
            logger.info(f"Re-scheduling previously blocked goal {goal.get('id', 'unknown')}")
            schedule_goal(goal)


def run_evolution_loop() -> None:
    """
    Main evolution loop that checks primitive validation before proceeding.
    """
    global PRIMITIVE_VALIDATION_FAILED
    global feasibility_estimator

    # Initial validation check
    check_primitive_validation()

    while True:
        if PRIMITIVE_VALIDATION_FAILED:
            print(
                "ABORT: Higher-level integration goals cannot proceed because "
                "primitive validation has failed. Please ensure "
                f"'{PRIMITIVE_TEST_PATH}' exists and passes all tests.",
                file=sys.stderr
            )
            # Optionally, wait and retry periodically
            import time
            time.sleep(10)
            check_primitive_validation()
            continue

        # Main evolution logic goes here
        # (placeholder for actual evolution processing)
        print("Primitive validation passed. Running evolution loop...")
        
        # Example usage of the new functionality
        # This would be replaced with actual goal management logic
        example_goal = {
            'id': 'goal_001',
            'dependencies': ['mutation_001', 'mutation_002'],
            'description': 'Example goal with dependencies'
        }
        
        # Try to schedule a goal
        if schedule_goal(example_goal):
            # If scheduled, execute and process result
            # This is where actual execution would happen
            process_mutation_result('mutation_001', True)
            process_mutation_result('mutation_002', True)
        
        break  # Remove this break when implementing actual loop logic


if __name__ == "__main__":
    run_evolution_loop()