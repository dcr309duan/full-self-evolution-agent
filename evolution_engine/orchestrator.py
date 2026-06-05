"""Orchestrator module for managing the evolution engine's main loop."""

import os
import sys
import subprocess
import tempfile
from pathlib import Path
from typing import List, Dict, Any, Optional
import logging
import argparse

# Global flag indicating whether primitive validation has failed
PRIMITIVE_VALIDATION_FAILED = False

PRIMITIVE_TEST_PATH = Path("tests/test_new_file_creation_metamorphic.py")

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class SchemaAlignmentChecker:
    """Checks schema alignment and auto-generates migration patches."""
    
    def __init__(self):
        self.validation_log: List[Dict[str, Any]] = []
        self.migration_log: List[Dict[str, Any]] = []
    
    def validate_schema(self, data: Dict[str, Any], context: str) -> bool:
        """
        Validate schema alignment for given data.
        
        Args:
            data: Data to validate
            context: Context description for logging
            
        Returns:
            True if schema is valid, False if mismatches detected
        """
        # Simulated schema validation logic
        # In production, this would check actual schema definitions
        is_valid = True
        mismatches = []
        
        # Check required fields
        required_fields = ['id', 'type', 'content']
        for field in required_fields:
            if field not in data:
                mismatches.append(f"Missing required field: {field}")
                is_valid = False
        
        # Check field types
        if 'id' in data and not isinstance(data['id'], str):
            mismatches.append(f"Field 'id' should be string, got {type(data['id']).__name__}")
            is_valid = False
        
        if 'type' in data and data['type'] not in ['goal', 'mutation', 'test_result', 'reflection']:
            mismatches.append(f"Invalid type: {data.get('type', 'unknown')}")
            is_valid = False
        
        # Log validation result
        validation_entry = {
            'context': context,
            'is_valid': is_valid,
            'mismatches': mismatches,
            'data_summary': {k: str(v)[:50] for k, v in data.items()}
        }
        self.validation_log.append(validation_entry)
        
        if mismatches:
            logger.warning(f"Schema validation failed for {context}: {mismatches}")
        else:
            logger.info(f"Schema validation passed for {context}")
        
        return is_valid
    
    def generate_migration_patch(self, data: Dict[str, Any], mismatches: List[str]) -> Dict[str, Any]:
        """
        Auto-generate migration patch to fix schema mismatches.
        
        Args:
            data: Original data with mismatches
            mismatches: List of detected mismatches
            
        Returns:
            Migration patch dictionary
        """
        patch = {
            'original_data': data.copy(),
            'patches': [],
            'migration_type': 'schema_alignment'
        }
        
        for mismatch in mismatches:
            if "Missing required field" in mismatch:
                field = mismatch.split(": ")[1]
                # Generate default value based on field name
                if field == 'id':
                    patch['patches'].append({'field': field, 'action': 'add', 'value': 'auto_generated_id'})
                elif field == 'type':
                    patch['patches'].append({'field': field, 'action': 'add', 'value': 'unknown'})
                elif field == 'content':
                    patch['patches'].append({'field': field, 'action': 'add', 'value': {}})
            
            elif "should be string" in mismatch:
                field = mismatch.split("'")[1]
                patch['patches'].append({'field': field, 'action': 'convert', 'target_type': 'str'})
            
            elif "Invalid type" in mismatch:
                patch['patches'].append({'field': 'type', 'action': 'convert', 'value': 'goal'})
        
        # Log migration
        migration_entry = {
            'patch': patch,
            'applied': False,
            'timestamp': logging.Formatter.formatTime(logging.makeLogRecord({}), '%Y-%m-%d %H:%M:%S')
        }
        self.migration_log.append(migration_entry)
        
        logger.info(f"Generated migration patch with {len(patch['patches'])} fixes")
        return patch
    
    def apply_migration_patch(self, data: Dict[str, Any], patch: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply migration patch to data.
        
        Args:
            data: Original data to patch
            patch: Migration patch to apply
            
        Returns:
            Patched data
        """
        patched_data = data.copy()
        
        for fix in patch['patches']:
            if fix['action'] == 'add':
                patched_data[fix['field']] = fix['value']
            elif fix['action'] == 'convert':
                if fix.get('target_type') == 'str':
                    patched_data[fix['field']] = str(patched_data[fix['field']])
                elif fix.get('value'):
                    patched_data[fix['field']] = fix['value']
        
        # Update migration log
        for entry in self.migration_log:
            if entry['patch'] == patch and not entry['applied']:
                entry['applied'] = True
                entry['timestamp'] = logging.Formatter.formatTime(logging.makeLogRecord({}), '%Y-%m-%d %H:%M:%S')
                break
        
        logger.info(f"Applied migration patch with {len(patch['patches'])} fixes")
        return patched_data
    
    def get_validation_summary(self) -> Dict[str, Any]:
        """Get summary of all validations performed."""
        total_validations = len(self.validation_log)
        failed_validations = sum(1 for v in self.validation_log if not v['is_valid'])
        total_migrations = len(self.migration_log)
        applied_migrations = sum(1 for m in self.migration_log if m['applied'])
        
        return {
            'total_validations': total_validations,
            'failed_validations': failed_validations,
            'total_migrations': total_migrations,
            'applied_migrations': applied_migrations,
            'validation_log': self.validation_log[-10:],  # Last 10 entries
            'migration_log': self.migration_log[-10:]  # Last 10 entries
        }


class MetaMonitor:
    """Monitors goal execution and manages reprioritization based on failures."""
    
    def __init__(self):
        self.consecutive_failures: Dict[str, int] = {}
        self.failure_categories: Dict[str, List[str]] = {}
        self.reprioritization_triggered: bool = False
        
    def record_failure(self, category: str, goal_id: str) -> None:
        """
        Record a failure for a specific category.
        
        Args:
            category: The category of the failure
            goal_id: The ID of the failed goal
        """
        if category not in self.consecutive_failures:
            self.consecutive_failures[category] = 0
            self.failure_categories[category] = []
        
        self.consecutive_failures[category] += 1
        self.failure_categories[category].append(goal_id)
        logger.info(f"Recorded failure for category '{category}' (goal {goal_id}), consecutive failures: {self.consecutive_failures[category]}")
        
    def check_consecutive_failures(self, category: str, threshold: int = 3) -> bool:
        """
        Check if a category has reached the consecutive failure threshold.
        
        Args:
            category: The category to check
            threshold: Number of consecutive failures to trigger reprioritization
            
        Returns:
            True if threshold is reached, False otherwise
        """
        failures = self.consecutive_failures.get(category, 0)
        return failures >= threshold
    
    def trigger_reprioritization(self) -> None:
        """Trigger reprioritization of the goal queue."""
        self.reprioritization_triggered = True
        logger.info("Reprioritization triggered due to consecutive failures")
        
    def generate_root_cause_hypothesis(self, category: str) -> str:
        """
        Generate a root cause hypothesis for failures in a category.
        
        Args:
            category: The category to analyze
            
        Returns:
            A hypothesis string explaining the likely root cause
        """
        failed_goals = self.failure_categories.get(category, [])
        hypothesis = f"Root cause hypothesis for category '{category}': "
        
        if len(failed_goals) >= 3:
            hypothesis += f"Multiple failures detected in goals: {', '.join(failed_goals[-3:])}. "
            hypothesis += "Likely systemic issue in dependency chain or environment configuration."
        elif len(failed_goals) >= 1:
            hypothesis += f"Single failure detected in goal: {failed_goals[-1]}. "
            hypothesis += "Possible isolated issue requiring further investigation."
        else:
            hypothesis += "No failures recorded yet."
            
        logger.info(f"Generated hypothesis: {hypothesis}")
        return hypothesis
    
    def reset_category(self, category: str) -> None:
        """Reset the consecutive failure count for a category."""
        self.consecutive_failures[category] = 0
        logger.info(f"Reset consecutive failures for category '{category}'")


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


# Global instances
feasibility_estimator = DependencyAwareFeasibilityEstimator()
meta_monitor = MetaMonitor()
schema_checker = SchemaAlignmentChecker()


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


def run_schema_validation(context: str, sandbox_mode: bool = False) -> None:
    """
    Run schema validation step before each evolution cycle.
    
    Args:
        context: Context description for logging
        sandbox_mode: If True, use temporary directory for file operations
    """
    logger.info(f"Running schema validation for context: {context}")
    
    # Simulated validation of the current state
    validation_data = {
        'id': 'cycle_validation',
        'type': 'goal',
        'content': {'status': 'ready'}
    }
    
    is_valid = schema_checker.validate_schema(validation_data, context)
    
    if not is_valid:
        logger.warning(f"Schema validation failed for {context}, generating migration patch")
        patch = schema_checker.generate_migration_patch(validation_data, ['Missing required field: id'])
        patched_data = schema_checker.apply_migration_patch(validation_data, patch)
        logger.info(f"Applied migration patch, new data: {patched_data}")
    
    # Log validation summary
    summary = schema_checker.get_validation_summary()
    logger.info(f"Schema validation summary: {summary['total_validations']} validations, "
                f"{summary['failed_validations']} failures, "
                f"{summary['applied_migrations']} migrations applied")


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


def run_meta_monitor(goal: Dict[str, Any], success: bool, meta_monitor_enabled: bool = False) -> None:
    """
    Run meta monitor after goal completion.
    
    Args:
        goal: The completed goal
        success: Whether the goal was successful
        meta_monitor_enabled: Whether meta monitor is enabled
    """
    global meta_monitor
    
    if not meta_monitor_enabled:
        return
    
    goal_id = goal.get('id', 'unknown')
    category = goal.get('category', 'default')
    
    if success:
        logger.info(f"Goal {goal_id} completed successfully")
        # Reset consecutive failures for this category on success
        meta_monitor.reset_category(category)
    else:
        logger.info(f"Goal {goal_id} failed")
        meta_monitor.record_failure(category, goal_id)
        
        # Check for 3+ consecutive failures
        if meta_monitor.check_consecutive_failures(category, threshold=3):
            logger.warning(f"3+ consecutive failures detected in category '{category}', triggering reprioritization")
            meta_monitor.trigger_reprioritization()
            
            # Update goal queue (simulated)
            # In a real implementation, this would modify the actual goal queue
            logger.info("Goal queue updated based on reprioritization")


def run_triage(sandbox_mode: bool = False) -> None:
    """
    Execute the triage module scan and prune operation.
    
    Args:
        sandbox_mode: If True, use temporary directory for file operations
    """
    try:
        from module_triage import scan_and_prune
        report = scan_and_prune(sandbox_mode=sandbox_mode)
        logger.info(f"Triage report: {report}")
    except ImportError:
        logger.error("module_triage not available, skipping triage step")
    except Exception as e:
        logger.error(f"Triage step failed: {e}")


def validate_and_fix(data: Dict[str, Any], context: str) -> Dict[str, Any]:
    """
    Validate data and auto-fix if mismatches detected.
    
    Args:
        data: Data to validate
        context: Context description for logging
        
    Returns:
        Validated (and possibly fixed) data
    """
    global schema_checker
    
    # Validate schema
    is_valid = schema_checker.validate_schema(data, context)
    
    if not is_valid:
        # Generate and apply migration patch
        mismatches = []
        if 'id' not in data:
            mismatches.append("Missing required field: id")
        if 'type' not in data:
            mismatches.append("Missing required field: type")
        if 'content' not in data:
            mismatches.append("Missing required field: content")
        
        patch = schema_checker.generate_migration_patch(data, mismatches)
        data = schema_checker.apply_migration_patch(data, patch)
        logger.info(f"Auto-fixed data for {context}")
    
    return data


def run_evolution_loop(sandbox_mode: bool = False, triage_interval: int = 5, meta_monitor_enabled: bool = False) -> None:
    """
    Main evolution loop that checks primitive validation before proceeding.
    
    Args:
        sandbox_mode: If True, use temporary directory for all file operations
                      to avoid modifying production code
        triage_interval: Number of evolution cycles between triage runs
        meta_monitor_enabled: Whether meta monitor is enabled
    """
    global PRIMITIVE_VALIDATION_FAILED
    global feasibility_estimator
    global meta_monitor
    global schema_checker

    # Initial validation check
    check_primitive_validation(sandbox_mode)
    
    cycle_count = 0

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

        # Run schema validation before each evolution cycle
        run_schema_validation(f"pre_cycle_{cycle_count}", sandbox_mode)

        # Main evolution logic goes here
        # (placeholder for actual evolution processing)
        print("Primitive validation passed. Running evolution loop...")
        
        # Example usage of the new functionality
        # This would be replaced with actual goal management logic
        example_goal = {
            'id': 'goal_001',
            'dependencies': ['mutation_001', 'mutation_002'],
            'description': 'Example goal with dependencies',
            'category': 'test_category'
        }
        
        # Validate goal_generator output before passing to mutation_engine
        goal_generator_output = {
            'id': 'goal_002',
            'type': 'goal',
            'content': {'action': 'mutate'}
        }
        validated_goal = validate_and_fix(goal_generator_output, "goal_generator_output")
        
        # Try to schedule a goal
        if schedule_goal(example_goal, sandbox_mode):
            # If scheduled, execute and process result
            # This is where actual execution would happen
            
            # Validate mutation_engine output before passing to test_runner
            mutation_engine_output = {
                'id': 'mutation_003',
                'type': 'mutation',
                'content': {'changes': ['modified_file_a.py']}
            }
            validated_mutation = validate_and_fix(mutation_engine_output, "mutation_engine_output")
            
            process_mutation_result('mutation_001', True, sandbox_mode)
            process_mutation_result('mutation_002', True, sandbox_mode)
            
            # Validate test_runner output before passing to reflection_parser
            test_runner_output = {
                'id': 'test_004',
                'type': 'test_result',
                'content': {'passed': True, 'failures': []}
            }
            validated_test_result = validate_and_fix(test_runner_output, "test_runner_output")
            
            # Run meta monitor after goal completion
            run_meta_monitor(example_goal, True, meta_monitor_enabled)
            
            # Example of failure scenario
            failed_goal = {
                'id': 'goal_002',
                'dependencies': [],
                'description': 'Example failed goal',
                'category': 'test_category'
            }
            run_meta_monitor(failed_goal, False, meta_monitor_enabled)
            
            # Check if reprioritization was triggered
            if meta_monitor.reprioritization_triggered and meta_monitor_enabled:
                # Before retrying any goal in a blocked category, generate hypothesis
                hypothesis = meta_monitor.generate_root_cause_hypothesis('test_category')
                logger.info(f"Root cause hypothesis for blocked category: {hypothesis}")
                meta_monitor.reprioritization_triggered = False
        
        cycle_count += 1
        
        # Run triage every triage_interval cycles
        if cycle_count % triage_interval == 0:
            logger.info(f"Running triage at cycle {cycle_count}")
            run_triage(sandbox_mode)
        
        break  # Remove this break when implementing actual loop logic


def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments for the orchestrator."""
    parser = argparse.ArgumentParser(description="Evolution Engine Orchestrator")
    parser.add_argument(
        "--triage-interval",
        type=int,
        default=5,
        help="Number of evolution cycles between triage runs (default: 5)"
    )
    parser.add_argument(
        "--sandbox-mode",
        action="store_true",
        default=True,
        help="Run in sandbox mode (default: True)"
    )
    parser.add_argument(
        "--meta-monitor-enabled",
        action="store_true",
        default=False,
        help="Enable meta monitor for failure tracking and reprioritization (default: False)"
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_arguments()
    # Default to sandbox mode for safety
    run_evolution_loop(
        sandbox_mode=args.sandbox_mode,
        triage_interval=args.triage_interval,
        meta_monitor_enabled=args.meta_monitor_enabled
    )