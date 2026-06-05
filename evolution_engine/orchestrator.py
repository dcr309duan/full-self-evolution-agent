"""Orchestrator module for managing the evolution engine's main loop."""

import os
import sys
import subprocess
import tempfile
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


def check_primitive_validation(sandbox_mode: bool = False) -> None:
    """
    Check if the primitive test file exists and passes.
    If not, log the error and set the global flag.
    
    Args:
        sandbox_mode: If True, use temporary directory for file operations
    """
    global PRIMITIVE_VALIDATION_FAILED

    if sandbox_mode:
        # Create a temporary directory for sandbox operations
        temp_dir = tempfile.mkdtemp(prefix="evolution_sandbox_")
        sandbox_test_path = Path(temp_dir) / PRIMITIVE_TEST_PATH.name
        
        # Copy the test file to sandbox if it exists
        if PRIMITIVE_TEST_PATH.exists():
            import shutil
            shutil.copy2(PRIMITIVE_TEST_PATH, sandbox_test_path)
            test_path = sandbox_test_path
        else:
            print(
                f"ERROR: Primitive test file not found: {PRIMITIVE_TEST_PATH}",
                file=sys.stderr
            )
            PRIMITIVE_VALIDATION_FAILED = True
            return
    else:
        test_path = PRIMITIVE_TEST_PATH

    if not test_path.exists():
        print(
            f"ERROR: Primitive test file not found: {test_path}",
            file=sys.stderr
        )
        PRIMITIVE_VALIDATION_FAILED = True
        return

    try:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", str(test_path), "-x", "--tb=short"],
            capture_output=True,
            text=True,
            timeout=60
        )
        if result.returncode != 0:
            print(
                f"ERROR: Primitive test failed: {test_path}\n"
                f"STDOUT: {result.stdout}\n"
                f"STDERR: {result.stderr}",
                file=sys.stderr
            )
            PRIMITIVE_VALIDATION_FAILED = True
        else:
            PRIMITIVE_VALIDATION_FAILED = False
    except subprocess.TimeoutExpired:
        print(
            f"ERROR: Primitive test timed out: {test_path}",
            file=sys.stderr
        )
        PRIMITIVE_VALIDATION_FAILED = True
    except Exception as e:
        print(
            f"ERROR: Unexpected error running primitive test: {e}",
            file=sys.stderr
        )
        PRIMITIVE_VALIDATION_FAILED = True
    finally:
        # Clean up sandbox directory if used
        if sandbox_mode and 'temp_dir' in locals():
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)


def schedule_goal(goal: Dict[str, Any], sandbox_mode: bool = False) -> bool:
    """
    Schedule a goal for execution after checking feasibility.
    
    Args:
        goal: Dictionary containing goal information
        sandbox_mode: If True, use temporary directory for file operations
        
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
    
    if sandbox_mode:
        # Create sandbox directory for this goal's operations
        temp_dir = tempfile.mkdtemp(prefix=f"goal_sandbox_{goal.get('id', 'unknown')}_")
        logger.info(f"Using sandbox directory for goal {goal.get('id', 'unknown')}: {temp_dir}")
        # Store sandbox path in goal for later cleanup
        goal['_sandbox_path'] = temp_dir
    
    # Actual scheduling logic would go here
    return True


def process_mutation_result(mutation_id: str, success: bool, sandbox_mode: bool = False) -> None:
    """
    Process the result of a mutation and re-evaluate blocked goals.
    
    Args:
        mutation_id: Identifier of the mutation that was executed
        success: Whether the mutation was successful
        sandbox_mode: If True, use temporary directory for file operations
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
            schedule_goal(goal, sandbox_mode)


def run_evolution_loop(sandbox_mode: bool = False) -> None:
    """
    Main evolution loop that checks primitive validation before proceeding.
    
    Args:
        sandbox_mode: If True, use temporary directory for all file operations
                      to avoid modifying production code
    """
    global PRIMITIVE_VALIDATION_FAILED
    global feasibility_estimator

    # Initial validation check
    check_primitive_validation(sandbox_mode)

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
            check_primitive_validation(sandbox_mode)
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
        if schedule_goal(example_goal, sandbox_mode):
            # If scheduled, execute and process result
            # This is where actual execution would happen
            process_mutation_result('mutation_001', True, sandbox_mode)
            process_mutation_result('mutation_002', True, sandbox_mode)
        
        break  # Remove this break when implementing actual loop logic


if __name__ == "__main__":
    # Default to sandbox mode for safety
    run_evolution_loop(sandbox_mode=True)