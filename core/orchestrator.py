from pathlib import Path
import tempfile
import shutil
import sys
import os
import json
from typing import Dict, Any, List
from collections import defaultdict
from datetime import datetime, timedelta

# Assuming these modules exist in the 'core' package
from core.goal_selector import select_goal
from core.mutation_engine import mutate_file
from core.test_runner import run_tests
from core.reflection import analyze_result
from core.simulation_engine import simulate_change, SimulationResult
from core.goal_triage import triage_pending_goals
from core.fitness_evaluator import FitnessEvaluator
from core.curiosity_engine import CuriosityEngine
from core.fs_abstraction import FileSystemAbstraction

SMOKE_TEST_GOAL = "Add error handling to counter function"

MINIMAL_COUNTER_PY = """class Counter:
    def __init__(self):
        self.count = 0

    def increment(self):
        self.count += 1

    def decrement(self):
        self.count -= 1

    def get_count(self):
        return self.count
"""

MINIMAL_TEST_PY = """import unittest
from counter import Counter

class TestCounter(unittest.TestCase):
    def test_increment(self):
        c = Counter()
        c.increment()
        self.assertEqual(c.get_count(), 1)

    def test_decrement(self):
        c = Counter()
        c.decrement()
        self.assertEqual(c.get_count(), -1)

    def test_multiple_operations(self):
        c = Counter()
        c.increment()
        c.increment()
        c.decrement()
        self.assertEqual(c.get_count(), 1)

if __name__ == '__main__':
    unittest.main()
"""

# Configuration for retry parameters
RETRY_CONFIG = {
    "max_retries": 3,
    "base_delay": 1.0,
    "max_delay": 10.0
}

# Track simulation accuracy over time
simulation_history: List[Dict[str, Any]] = []

# Knowledge base to store fitness scores and other data
knowledge_base: List[Dict[str, Any]] = []

# Curiosity engine instance
curiosity_engine = CuriosityEngine()

# Cycle counter for curiosity engine interval
cycle_counter = 0
CURIOSITY_INTERVAL = 5  # Configurable interval for curiosity engine activation

# File system abstraction instance
fs_abstraction = FileSystemAbstraction()

# Failure cluster analyzer configuration
FAILURE_CLUSTER_CONFIG = {
    "threshold": 3,  # Number of failures in same module to trigger fix
    "time_window_minutes": 10,  # Time window to consider failures
    "cluster_file": "core/failure_clusters.json"  # Persistent storage file
}

# Failure cluster data structure
failure_clusters: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

def load_failure_clusters() -> Dict[str, List[Dict[str, Any]]]:
    """Load failure clusters from persistent storage."""
    cluster_file = Path(FAILURE_CLUSTER_CONFIG["cluster_file"])
    if cluster_file.exists():
        try:
            with open(cluster_file, 'r') as f:
                return defaultdict(list, json.load(f))
        except (json.JSONDecodeError, IOError):
            return defaultdict(list)
    return defaultdict(list)

def save_failure_clusters(clusters: Dict[str, List[Dict[str, Any]]]) -> None:
    """Save failure clusters to persistent storage."""
    cluster_file = Path(FAILURE_CLUSTER_CONFIG["cluster_file"])
    cluster_file.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(cluster_file, 'w') as f:
            json.dump(dict(clusters), f, indent=2)
    except IOError as e:
        print(f"Warning: Could not save failure clusters: {e}")

def update_failure_cluster(module_name: str, failure_info: Dict[str, Any]) -> None:
    """Update failure cluster data with new failure information."""
    global failure_clusters
    
    # Load existing clusters
    failure_clusters = load_failure_clusters()
    
    # Add new failure entry with timestamp
    failure_entry = {
        "timestamp": datetime.now().isoformat(),
        "failure_info": failure_info,
        "cycle_number": cycle_counter
    }
    
    failure_clusters[module_name].append(failure_entry)
    
    # Clean up old entries outside the time window
    time_window = timedelta(minutes=FAILURE_CLUSTER_CONFIG["time_window_minutes"])
    cutoff_time = datetime.now() - time_window
    
    failure_clusters[module_name] = [
        entry for entry in failure_clusters[module_name]
        if datetime.fromisoformat(entry["timestamp"]) > cutoff_time
    ]
    
    # Save updated clusters
    save_failure_clusters(failure_clusters)

def check_cluster_threshold(module_name: str) -> bool:
    """Check if a module has exceeded the failure threshold."""
    global failure_clusters
    
    failure_clusters = load_failure_clusters()
    
    if module_name not in failure_clusters:
        return False
    
    # Count failures within the time window
    time_window = timedelta(minutes=FAILURE_CLUSTER_CONFIG["time_window_minutes"])
    cutoff_time = datetime.now() - time_window
    
    recent_failures = [
        entry for entry in failure_clusters[module_name]
        if datetime.fromisoformat(entry["timestamp"]) > cutoff_time
    ]
    
    return len(recent_failures) >= FAILURE_CLUSTER_CONFIG["threshold"]

def trigger_environment_fix(module_name: str) -> Dict[str, Any]:
    """Trigger environment-level fix for a module that exceeded failure threshold."""
    fix_result = {
        "module": module_name,
        "fixes_applied": [],
        "success": True
    }
    
    try:
        # Run health check on filesystem abstraction
        health_check_result = fs_abstraction.health_check()
        if not health_check_result.get("healthy", True):
            fs_abstraction.repair()
            fix_result["fixes_applied"].append("fs_abstraction_repair")
        
        # Repair permissions if needed
        permission_repair_result = fs_abstraction.repair_permissions()
        if permission_repair_result.get("repaired", False):
            fix_result["fixes_applied"].append("permission_repair")
        
        # Clean temp directories
        temp_cleanup_result = fs_abstraction.cleanup_temp_directories()
        if temp_cleanup_result.get("cleaned", False):
            fix_result["fixes_applied"].append("temp_directory_cleanup")
        
        # Clear the failure cluster for this module after fix
        global failure_clusters
        failure_clusters = load_failure_clusters()
        if module_name in failure_clusters:
            del failure_clusters[module_name]
            save_failure_clusters(failure_clusters)
        
        fix_result["success"] = True
        fix_result["message"] = f"Environment fixes applied for module: {module_name}"
        
    except Exception as e:
        fix_result["success"] = False
        fix_result["message"] = f"Failed to apply environment fixes: {str(e)}"
    
    return fix_result

def update_simulation_accuracy(sim_result: SimulationResult, actual_test_result: Dict[str, Any]) -> None:
    """Update simulation accuracy tracking based on actual test results."""
    predicted_success = sim_result.predicted_success
    actual_success = actual_test_result.get("success", False)
    
    accuracy_entry = {
        "predicted_success": predicted_success,
        "actual_success": actual_success,
        "confidence": sim_result.confidence,
        "correct": predicted_success == actual_success
    }
    simulation_history.append(accuracy_entry)

def get_simulation_accuracy() -> Dict[str, Any]:
    """Calculate current simulation accuracy metrics."""
    if not simulation_history:
        return {
            "overall_accuracy": 0.0,
            "total_predictions": 0,
            "correct_predictions": 0,
            "average_confidence": 0.0
        }
    
    total = len(simulation_history)
    correct = sum(1 for entry in simulation_history if entry["correct"])
    avg_confidence = sum(entry["confidence"] for entry in simulation_history) / total
    
    return {
        "overall_accuracy": correct / total if total > 0 else 0.0,
        "total_predictions": total,
        "correct_predictions": correct,
        "average_confidence": avg_confidence
    }

def is_critical_goal(goal: Dict[str, Any]) -> bool:
    """Check if a goal is critical (high priority or has dependencies from other goals)."""
    priority = goal.get("priority", "low")
    dependencies = goal.get("dependencies", [])
    return priority == "high" or len(dependencies) > 0

def validate_triage_result(triage_result: Dict[str, Any]) -> Dict[str, Any]:
    """Validate triage results to ensure no critical goals were archived without confirmation."""
    archived_goals = triage_result.get("archived_goals", [])
    reverted_goals = []
    warnings = []
    
    for goal in archived_goals:
        if is_critical_goal(goal):
            # Revert the archive for critical goals
            reverted_goals.append(goal)
            warnings.append(f"Critical goal '{goal.get('name', 'unknown')}' was archived without explicit confirmation. Reverting archive.")
    
    if reverted_goals:
        # Remove reverted goals from archived list
        triage_result["archived_goals"] = [g for g in archived_goals if g not in reverted_goals]
        # Add reverted goals back to pending goals
        pending_goals = triage_result.get("pending_goals", [])
        pending_goals.extend(reverted_goals)
        triage_result["pending_goals"] = pending_goals
        triage_result["warnings"] = triage_result.get("warnings", []) + warnings
    
    return triage_result

def verify_prerequisites(goal: Dict[str, Any], dependency_graph: Dict[str, Any]) -> List[Dict[str, str]]:
    """
    Verify that all hard prerequisites for a goal are met.
    
    Args:
        goal: The goal to verify prerequisites for
        dependency_graph: The dependency graph containing prerequisite information
        
    Returns:
        A list of unmet prerequisites with reasons. Empty list if all prerequisites are met.
    """
    unmet_prerequisites = []
    
    # Query the dependency graph for all hard prerequisites of the goal
    goal_name = goal.get("name", "")
    hard_prerequisites = dependency_graph.get(goal_name, {}).get("hard_prerequisites", [])
    
    # Check each prerequisite against the current system state
    for prerequisite in hard_prerequisites:
        prereq_name = prerequisite.get("name", "")
        prereq_type = prerequisite.get("type", "module")
        prereq_value = prerequisite.get("value", "")
        
        # Check based on prerequisite type
        if prereq_type == "module":
            # Check if the module exists in the system
            try:
                __import__(prereq_value)
            except ImportError:
                unmet_prerequisites.append({
                    "prerequisite": prereq_name,
                    "reason": f"Required module '{prereq_value}' is not installed or available"
                })
        elif prereq_type == "capability":
            # Check if the capability exists (placeholder - actual implementation depends on system)
            # For now, we'll check if it's defined in a capabilities registry
            capabilities = dependency_graph.get("capabilities", {})
            if prereq_value not in capabilities:
                unmet_prerequisites.append({
                    "prerequisite": prereq_name,
                    "reason": f"Required capability '{prereq_value}' is not available"
                })
        elif prereq_type == "file":
            # Check if the file exists using fs_abstraction
            if not fs_abstraction.file_exists(prereq_value):
                unmet_prerequisites.append({
                    "prerequisite": prereq_name,
                    "reason": f"Required file '{prereq_value}' does not exist"
                })
        elif prereq_type == "environment_variable":
            # Check if the environment variable is set
            if prereq_value not in os.environ:
                unmet_prerequisites.append({
                    "prerequisite": prereq_name,
                    "reason": f"Required environment variable '{prereq_value}' is not set"
                })
        else:
            # Unknown prerequisite type
            unmet_prerequisites.append({
                "prerequisite": prereq_name,
                "reason": f"Unknown prerequisite type '{prereq_type}' for '{prereq_value}'"
            })
    
    return unmet_prerequisites

def run_curiosity_cycle() -> None:
    """Execute curiosity engine cycle and handle results."""
    global cycle_counter, knowledge_base
    
    cycle_counter += 1
    
    if cycle_counter % CURIOSITY_INTERVAL == 0:
        # Log curiosity cycle initiation
        knowledge_base.append({
            "type": "curiosity_event",
            "event": "cycle_initiated",
            "cycle_number": cycle_counter,
            "interval": CURIOSITY_INTERVAL
        })
        
        # Generate and attempt task
        task_result = curiosity_engine.generate_and_attempt_task()
        
        # Log the curiosity event
        knowledge_base.append({
            "type": "curiosity_event",
            "event": "task_attempted",
            "cycle_number": cycle_counter,
            "task_result": task_result,
            "success": task_result.get("success", False)
        })
        
        # If task failed, inject the resulting goal into the goal queue with high priority
        if not task_result.get("success", False):
            failed_goal = task_result.get("goal", {})
            failed_goal["priority"] = "high"
            
            # Inject into goal queue (assuming there's a global goal queue or mechanism)
            # For this implementation, we'll add it to the knowledge base for processing
            knowledge_base.append({
                "type": "curiosity_event",
                "event": "goal_injected",
                "cycle_number": cycle_counter,
                "injected_goal": failed_goal,
                "priority": "high"
            })
            
            # Log the injection
            print(f"Curiosity engine: Injected failed goal '{failed_goal.get('name', 'unknown')}' with high priority")

def run_smoke_test() -> Dict[str, Any]:
    """
    Execute the evolution smoke test in an isolated temporary directory.
    Integrates simulation engine to predict outcomes before mutation.
    Integrates goal triage to avoid re-generating archived goals.
    Integrates prerequisite verification to check dependencies before execution.
    Integrates fitness evaluator to assess code quality before and after mutation.
    Integrates curiosity engine for autonomous exploration.
    Integrates failure cluster analyzer for detecting and fixing recurring failures.

    Returns:
        A structured dictionary containing:
        - 'success': bool indicating overall success
        - 'logs': list of step-level log entries
        - 'result': the final analysis result from the reflection module
        - 'simulation_confidence': confidence score from simulation
    """
    logs: List[Dict[str, Any]] = []
    temp_dir = None
    simulation_confidence = 0.0
    fitness_evaluator = FitnessEvaluator()

    try:
        # Run curiosity engine cycle
        run_curiosity_cycle()
        
        # Step 1: Create isolated environment using fs_abstraction
        temp_dir = fs_abstraction.create_temp_directory(prefix="smoke_test_")
        logs.append({
            "step": 1,
            "action": "create_isolated_environment",
            "status": "success",
            "details": f"Created temporary directory: {temp_dir}"
        })

        # Write minimal counter.py and test file using fs_abstraction
        counter_path = Path(temp_dir) / "counter.py"
        test_path = Path(temp_dir) / "test_counter.py"
        fs_abstraction.write_file(str(counter_path), MINIMAL_COUNTER_PY)
        fs_abstraction.write_file(str(test_path), MINIMAL_TEST_PY)
        logs.append({
            "step": 1.1,
            "action": "write_source_files",
            "status": "success",
            "details": f"Written counter.py and test_counter.py to {temp_dir}"
        })

        # Step 2: Invoke goal selector
        goal = SMOKE_TEST_GOAL
        selected_goal = select_goal(goal)
        logs.append({
            "step": 2,
            "action": "invoke_goal_selector",
            "status": "success",
            "details": f"Selected goal: {selected_goal}"
        })

        # Step 2.5: Verify prerequisites before execution
        # Build a dependency graph (in a real system, this would come from a database or configuration)
        dependency_graph = {
            selected_goal.get("name", goal): {
                "hard_prerequisites": [
                    {"name": "unittest module", "type": "module", "value": "unittest"},
                    {"name": "counter.py file", "type": "file", "value": str(counter_path)},
                    {"name": "test_counter.py file", "type": "file", "value": str(test_path)}
                ]
            },
            "capabilities": {
                "file_operations": True,
                "module_import": True
            }
        }
        
        unmet_prerequisites = verify_prerequisites(selected_goal, dependency_graph)
        
        if unmet_prerequisites:
            # Log unmet prerequisites
            for prereq in unmet_prerequisites:
                logs.append({
                    "step": 2.3,
                    "action": "prerequisite_check",
                    "status": "failed",
                    "details": f"Unmet prerequisite: {prereq['prerequisite']} - {prereq['reason']}"
                })
            
            # Defer the goal if prerequisites are not met
            logs.append({
                "step": 2.4,
                "action": "defer_goal",
                "status": "deferred",
                "details": f"Goal '{selected_goal.get('name', goal)}' deferred due to unmet prerequisites"
            })
            
            # Return early with deferred result
            result = {
                "success": False,
                "logs": logs,
                "result": {
                    "deferred": True,
                    "unmet_prerequisites": unmet_prerequisites,
                    "simulation_confidence": simulation_confidence,
                    "simulation_accuracy": get_simulation_accuracy()
                },
                "simulation_confidence": simulation_confidence
            }
            return result
        
        logs.append({
            "step": 2.3,
            "action": "prerequisite_check",
            "status": "success",
            "details": "All prerequisites are met"
        })

        # Step 3: Run simulation before mutation using fs_abstraction
        original_code = fs_abstraction.read_file(str(counter_path))
        sim_result = simulate_change(original_code, selected_goal)
        simulation_confidence = sim_result.confidence
        logs.append({
            "step": 2.5,
            "action": "run_simulation",
            "status": "success",
            "details": f"Simulation predicted success: {sim_result.predicted_success}, confidence: {sim_result.confidence}"
        })

        # Check simulation prediction
        if not sim_result.predicted_success:
            logs.append({
                "step": 2.6,
                "action": "simulation_warning",
                "status": "warning",
                "details": f"Simulation predicts failure with confidence {sim_result.confidence}. Skipping mutation."
            })
            # Return early with simulation failure result
            result = {
                "success": False,
                "logs": logs,
                "result": {
                    "simulation_confidence": simulation_confidence,
                    "simulation_prediction": "failure",
                    "simulation_accuracy": get_simulation_accuracy()
                },
                "simulation_confidence": simulation_confidence
            }
            return result

        # Step 3.5: Run fitness evaluator before mutation using fs_abstraction
        pre_mutation_fitness = fitness_evaluator.run_fitness_test(str(counter_path))
        logs.append({
            "step": 2.7,
            "action": "run_fitness_evaluation_pre_mutation",
            "status": "success",
            "details": f"Pre-mutation fitness score: {pre_mutation_fitness}"
        })

        # Store pre-mutation fitness score in knowledge base
        knowledge_base.append({
            "type": "fitness_score",
            "phase": "pre_mutation",
            "score": pre_mutation_fitness,
            "goal": selected_goal.get("name", goal)
        })

        # Step 4: Invoke mutation engine
        mutated_code = mutate_file(str(counter_path), selected_goal)
        logs.append({
            "step": 3,
            "action": "invoke_mutation_engine",
            "status": "success",
            "details": f"Mutation applied to {counter_path}"
        })

        # Write mutated code back to file using fs_abstraction
        fs_abstraction.write_file(str(counter_path), mutated_code)
        logs.append({
            "step": 3.1,
            "action": "write_mutated_code",
            "status": "success",
            "details": "Mutated code written back to counter.py"
        })

        # Step 4.5: Run fitness evaluator after mutation using fs_abstraction
        post_mutation_fitness = fitness_evaluator.run_fitness_test(str(counter_path))
        logs.append({
            "step": 3.5,
            "action": "run_fitness_evaluation_post_mutation",
            "status": "success",
            "details": f"Post-mutation fitness score: {post_mutation_fitness}"
        })

        # Store post-mutation fitness score in knowledge base
        knowledge_base.append({
            "type": "fitness_score",
            "phase": "post_mutation",
            "score": post_mutation_fitness,
            "goal": selected_goal.get("name", goal)
        })

        # Check if fitness score dropped significantly (>20%)
        if pre_mutation_fitness > 0:
            fitness_drop = (pre_mutation_fitness - post_mutation_fitness) / pre_mutation_fitness
            if fitness_drop > 0.2:
                logs.append({
                    "step": 3.6,
                    "action": "fitness_drop_detected",
                    "status": "warning",
                    "details": f"Fitness score dropped by {fitness_drop*100:.1f}% (>20%). Rolling back mutation."
                })
                
                # Rollback the mutation by restoring original code using fs_abstraction
                fs_abstraction.write_file(str(counter_path), original_code)
                logs.append({
                    "step": 3.7,
                    "action": "rollback_mutation",
                    "status": "success",
                    "details": "Mutation rolled back to original code due to significant fitness drop"
                })
                
                # Store rollback in knowledge base
                knowledge_base.append({
                    "type": "rollback",
                    "reason": "fitness_drop",
                    "pre_mutation_score": pre_mutation_fitness,
                    "post_mutation_score": post_mutation_fitness,
                    "drop_percentage": fitness_drop * 100,
                    "goal": selected_goal.get("name", goal)
                })
                
                # Return early with rollback result
                result = {
                    "success": False,
                    "logs": logs,
                    "result": {
                        "rolled_back": True,
                        "reason": "fitness_drop",
                        "pre_mutation_fitness": pre_mutation_fitness,
                        "post_mutation_fitness": post_mutation_fitness,
                        "fitness_drop_percentage": fitness_drop * 100,
                        "simulation_confidence": simulation_confidence,
                        "simulation_accuracy": get_simulation_accuracy()
                    },
                    "simulation_confidence": simulation_confidence
                }
                return result

        # Step 5: Run test suite
        original_cwd = os.getcwd()
        os.chdir(temp_dir)
        try:
            test_result = run_tests(str(test_path))
            logs.append({
                "step": 4,
                "action": "run_test_suite",
                "status": "success",
                "details": f"Test result: {test_result}"
            })
            
            # Update simulation accuracy tracking
            update_simulation_accuracy(sim_result, test_result)
            
            # Integrate failure cluster analyzer after mutation attempt
            module_name = "counter"  # In real scenario, extract from goal or file path
            failure_info = {
                "goal": selected_goal.get("name", goal),
                "test_result": test_result,
                "simulation_confidence": simulation_confidence,
                "mutation_applied": True
            }
            
            # Update failure cluster regardless of success/failure
            update_failure_cluster(module_name, failure_info)
            
            # Check if cluster threshold exceeded
            if check_cluster_threshold(module_name):
                logs.append({
                    "step": 4.1,
                    "action": "failure_cluster_detected",
                    "status": "warning",
                    "details": f"Failure cluster threshold exceeded for module: {module_name}"
                })
                
                # Trigger environment-level fix
                fix_result = trigger_environment_fix(module_name)
                logs.append({
                    "step": 4.2,
                    "action": "environment_fix",
                    "status": "success" if fix_result["success"] else "failed",
                    "details": fix_result["message"]
                })
                
                # Log applied fixes
                for fix in fix_result["fixes_applied"]:
                    logs.append({
                        "step": 4.3,
                        "action": f"applied_fix_{fix}",
                        "status": "success",
                        "details": f"Applied fix: {fix}"
                    })
            
        finally:
            os.chdir(original_cwd)

        # Step 6: Invoke reflection module with simulation data
        analysis = analyze_result(test_result, mutated_code, selected_goal)
        
        # Add simulation confidence to reflection output
        analysis["simulation_confidence"] = simulation_confidence
        analysis["simulation_accuracy"] = get_simulation_accuracy()
        analysis["pre_mutation_fitness"] = pre_mutation_fitness
        analysis["post_mutation_fitness"] = post_mutation_fitness
        
        logs.append({
            "step": 5,
            "action": "invoke_reflection",
            "status": "success",
            "details": f"Analysis result: {analysis}"
        })

        # Step 7: Goal triage - triage pending goals after reflection
        triage_result = triage_pending_goals()
        logs.append({
            "step": 6,
            "action": "goal_triage",
            "status": "success",
            "details": f"Triage result: {triage_result}"
        })

        # Step 7.5: Post-triage validation - check for critical goals archived without confirmation
        validated_triage = validate_triage_result(triage_result)
        if validated_triage.get("warnings"):
            for warning in validated_triage["warnings"]:
                logs.append({
                    "step": 6.5,
                    "action": "post_triage_validation",
                    "status": "warning",
                    "details": warning
                })
            # Update triage result with validated version
            triage_result = validated_triage

        # Step 8: Goal generation with archived goals excluded
        archived_goals = triage_result.get("archived_goals", [])
        # Pass archived goals to goal generator to avoid re-generating them
        # This is a placeholder for actual goal generation logic
        new_goal = select_goal(goal, exclude_goals=archived_goals)
        logs.append({
            "step": 7,
            "action": "goal_generation",
            "status": "success",
            "details": f"Generated new goal: {new_goal}, excluding {len(archived_goals)} archived goals"
        })

        # Step 9: Return structured result with simulation data
        result = {
            "success": True,
            "logs": logs,
            "result": analysis,
            "simulation_confidence": simulation_confidence
        }
        return result

    except Exception as e:
        logs.append({
            "step": -1,
            "action": "error",
            "status": "failed",
            "details": str(e)
        })
        return {
            "success": False,
            "logs": logs,
            "result": {
                "simulation_confidence": simulation_confidence,
                "simulation_accuracy": get_simulation_accuracy()
            },
            "simulation_confidence": simulation_confidence
        }

    finally:
        # Cleanup temporary directory using fs_abstraction
        if temp_dir and fs_abstraction.directory_exists(temp_dir):
            fs_abstraction.remove_directory(temp_dir)
            logs.append({
                "step": "cleanup",
                "action": "remove_temp_directory",
                "status": "success",
                "details": f"Removed temporary directory: {temp_dir}"
            })