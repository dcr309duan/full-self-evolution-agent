import os
import sys
import json
import ast
import traceback
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple
from pathlib import Path

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.reflection_engine import ReflectionEngine
from core.goal_selector import GoalSelector
from core.mutation_engine import MutationEngine
from core.test_runner import TestRunner
from core.promotion_manager import PromotionManager
from core.state_manager import StateManager
from core.schema_manager import SchemaManager
from core.dependency_manager import DependencyManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('integration_harness.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class SystemicIntegrationTestHarness:
    """
    Orchestrates the full evolution loop for adding a new capability that requires
    schema updates and dependency changes. Logs each failure point with full context
    and automatically generates structured repair goals.
    """

    def __init__(self, config_path: str = "config/integration_config.json"):
        self.config = self._load_config(config_path)
        self.reflection_engine = ReflectionEngine()
        self.goal_selector = GoalSelector()
        self.mutation_engine = MutationEngine()
        self.test_runner = TestRunner()
        self.promotion_manager = PromotionManager()
        self.state_manager = StateManager()
        self.schema_manager = SchemaManager()
        self.dependency_manager = DependencyManager()

        self.evolution_cycle = 0
        self.max_cycles = self.config.get("max_cycles", 10)
        self.current_goal = None
        self.failure_log: List[Dict[str, Any]] = []
        self.repair_goals: List[Dict[str, Any]] = []

        # Track module state snapshots
        self.module_snapshots: Dict[str, str] = {}

    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """Load configuration from JSON file."""
        try:
            with open(config_path, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            logger.warning(f"Config file {config_path} not found. Using defaults.")
            return {
                "max_cycles": 10,
                "target_module": "core.new_capability",
                "schema_file": "schema/capability_schema.json",
                "dependency_file": "requirements/capability_deps.txt",
                "test_module": "tests.test_new_capability",
                "promotion_threshold": 0.8
            }

    def _snapshot_module_state(self, module_path: str) -> str:
        """Capture AST snapshot of a module."""
        try:
            with open(module_path, 'r') as f:
                source = f.read()
            tree = ast.parse(source)
            self.module_snapshots[module_path] = ast.dump(tree, indent=2)
            return self.module_snapshots[module_path]
        except Exception as e:
            logger.error(f"Failed to snapshot module {module_path}: {e}")
            return f"ERROR: {str(e)}"

    def _log_failure(self, phase: str, error: Exception, context: Dict[str, Any]) -> Dict[str, Any]:
        """Log a failure with full context."""
        failure_record = {
            "cycle": self.evolution_cycle,
            "timestamp": datetime.now().isoformat(),
            "phase": phase,
            "error_type": type(error).__name__,
            "error_message": str(error),
            "traceback": traceback.format_exc(),
            "context": context,
            "module_snapshots": self.module_snapshots.copy(),
            "current_goal": self.current_goal
        }
        self.failure_log.append(failure_record)
        logger.error(f"Failure in phase '{phase}': {error}")
        return failure_record

    def _generate_repair_goal(self, failure: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a structured repair goal from a failure record."""
        repair_goal = {
            "id": f"repair_{self.evolution_cycle}_{len(self.repair_goals)}",
            "source_failure": failure["phase"],
            "error_type": failure["error_type"],
            "target_module": failure["context"].get("module", self.config["target_module"]),
            "repair_type": "schema_update" if "schema" in failure["phase"].lower() else
                          "dependency_update" if "dependency" in failure["phase"].lower() else
                          "code_mutation",
            "constraints": self._extract_constraints(failure),
            "priority": self._calculate_priority(failure),
            "generated_at": datetime.now().isoformat()
        }
        self.repair_goals.append(repair_goal)
        return repair_goal

    def _extract_constraints(self, failure: Dict[str, Any]) -> List[str]:
        """Extract constraints from failure context."""
        constraints = []
        context = failure.get("context", {})
        if "schema" in context:
            constraints.append(f"schema_compliance:{context['schema']}")
        if "dependency" in context:
            constraints.append(f"dependency_consistency:{context['dependency']}")
        if "test" in context:
            constraints.append(f"test_coverage:{context['test']}")
        return constraints

    def _calculate_priority(self, failure: Dict[str, Any]) -> int:
        """Calculate repair priority based on failure severity."""
        error_type = failure.get("error_type", "")
        if "SyntaxError" in error_type or "ImportError" in error_type:
            return 1  # Highest priority
        elif "AttributeError" in error_type or "TypeError" in error_type:
            return 2
        elif "ValueError" in error_type:
            return 3
        else:
            return 4

    def _reflect_on_state(self) -> Dict[str, Any]:
        """Perform reflection on current system state."""
        try:
            reflection = self.reflection_engine.reflect(
                module_state=self.state_manager.get_state(),
                schema_state=self.schema_manager.get_schema_state(),
                dependency_state=self.dependency_manager.get_dependency_state()
            )
            logger.info(f"Reflection completed: {reflection.get('summary', 'No summary')}")
            return reflection
        except Exception as e:
            context = {"phase": "reflection", "module": self.config["target_module"]}
            failure = self._log_failure("reflection", e, context)
            self._generate_repair_goal(failure)
            return {"error": str(e), "failure": failure}

    def _select_goal(self, reflection: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Select next evolution goal based on reflection."""
        try:
            goal = self.goal_selector.select_goal(
                reflection=reflection,
                current_goal=self.current_goal,
                failure_log=self.failure_log
            )
            if goal:
                self.current_goal = goal
                logger.info(f"Goal selected: {goal.get('description', 'No description')}")
            return goal
        except Exception as e:
            context = {"phase": "goal_selection", "reflection": reflection}
            failure = self._log_failure("goal_selection", e, context)
            self._generate_repair_goal(failure)
            return None

    def _apply_mutation(self, goal: Dict[str, Any]) -> bool:
        """Apply mutation to achieve the selected goal."""
        try:
            # Snapshot current state before mutation
            module_path = f"src/{goal.get('target_module', self.config['target_module']).replace('.', '/')}.py"
            self._snapshot_module_state(module_path)

            # Handle schema updates if needed
            if goal.get("requires_schema_update", False):
                self.schema_manager.update_schema(goal["schema_updates"])

            # Handle dependency updates if needed
            if goal.get("requires_dependency_update", False):
                self.dependency_manager.update_dependencies(goal["dependency_updates"])

            # Apply code mutation
            mutation_result = self.mutation_engine.mutate(
                goal=goal,
                module_state=self.state_manager.get_state()
            )

            if mutation_result.get("success", False):
                logger.info(f"Mutation applied successfully for goal: {goal.get('id', 'unknown')}")
                return True
            else:
                raise RuntimeError(f"Mutation failed: {mutation_result.get('error', 'Unknown error')}")

        except Exception as e:
            context = {
                "phase": "mutation",
                "goal": goal,
                "module": goal.get("target_module", self.config["target_module"])
            }
            failure = self._log_failure("mutation", e, context)
            self._generate_repair_goal(failure)
            return False

    def _run_tests(self) -> Tuple[bool, Dict[str, Any]]:
        """Run tests and return success status and results."""
        try:
            test_results = self.test_runner.run_tests(
                test_module=self.config["test_module"],
                coverage_threshold=self.config.get("coverage_threshold", 0.7)
            )
            success = test_results.get("success", False) and \
                     test_results.get("coverage", 0) >= self.config.get("promotion_threshold", 0.8)
            logger.info(f"Tests {'passed' if success else 'failed'}: {test_results}")
            return success, test_results
        except Exception as e:
            context = {
                "phase": "testing",
                "test_module": self.config["test_module"]
            }
            failure = self._log_failure("testing", e, context)
            self._generate_repair_goal(failure)
            return False, {"error": str(e), "failure": failure}

    def _promote_changes(self) -> bool:
        """Promote changes if tests pass."""
        try:
            promotion_result = self.promotion_manager.promote(
                module=self.config["target_module"],
                test_results=self.test_runner.last_results,
                promotion_threshold=self.config.get("promotion_threshold", 0.8)
            )
            if promotion_result.get("success", False):
                logger.info(f"Changes promoted successfully for {self.config['target_module']}")
                return True
            else:
                logger.warning(f"Promotion failed: {promotion_result.get('reason', 'Unknown')}")
                return False
        except Exception as e:
            context = {
                "phase": "promotion",
                "module": self.config["target_module"]
            }
            failure = self._log_failure("promotion", e, context)
            self._generate_repair_goal(failure)
            return False

    def _generate_summary_report(self) -> Dict[str, Any]:
        """Generate a summary report of the evolution cycle."""
        return {
            "total_cycles": self.evolution_cycle,
            "total_failures": len(self.failure_log),
            "total_repair_goals": len(self.repair_goals),
            "failures_by_phase": self._count_failures_by_phase(),
            "successful_promotions": sum(1 for f in self.failure_log if f["phase"] == "promotion" and "success" in str(f.get("context", {}))),
            "current_goal": self.current_goal,
            "module_snapshots": self.module_snapshots,
            "repair_goals": self.repair_goals,
            "timestamp": datetime.now().isoformat()
        }

    def _count_failures_by_phase(self) -> Dict[str, int]:
        """Count failures grouped by phase."""
        phase_counts = {}
        for failure in self.failure_log:
            phase = failure["phase"]
            phase_counts[phase] = phase_counts.get(phase, 0) + 1
        return phase_counts

    def run_evolution_cycle(self) -> Dict[str, Any]:
        """Execute one complete evolution cycle."""
        self.evolution_cycle += 1
        logger.info(f"Starting evolution cycle {self.evolution_cycle}")

        # Phase 1: Reflection
        reflection = self._reflect_on_state()
        if "error" in reflection:
            logger.error("Reflection failed, aborting cycle")
            return self._generate_summary_report()

        # Phase 2: Goal Selection
        goal = self._select_goal(reflection)
        if not goal:
            logger.warning("No goal selected, ending evolution")
            return self._generate_summary_report()

        # Phase 3: Mutation
        mutation_success = self._apply_mutation(goal)
        if not mutation_success:
            logger.error("Mutation failed, generating repair goals")
            return self._generate_summary_report()

        # Phase 4: Testing
        tests_passed, test_results = self._run_tests()
        if not tests_passed:
            logger.error("Tests failed, generating repair goals")
            # Generate repair goals from test failures
            if "failures" in test_results:
                for test_failure in test_results["failures"]:
                    context = {
                        "phase": "testing",
                        "test": test_failure.get("test_name", "unknown"),
                        "error": test_failure.get("error", "unknown")
                    }
                    failure_record = self._log_failure("testing", Exception(test_failure.get("error", "")), context)
                    self._generate_repair_goal(failure_record)
            return self._generate_summary_report()

        # Phase 5: Promotion
        promotion_success = self._promote_changes()
        if not promotion_success:
            logger.warning("Promotion failed, but changes may be partially applied")

        logger.info(f"Evolution cycle {self.evolution_cycle} completed")
        return self._generate_summary_report()

    def run_full_evolution(self) -> Dict[str, Any]:
        """Run the full evolution loop until max cycles or no more goals."""
        logger.info("Starting full evolution loop")
        final_report = None

        while self.evolution_cycle < self.max_cycles:
            cycle_report = self.run_evolution_cycle()
            final_report = cycle_report

            # Check if we should stop (no more repair goals or all goals resolved)
            if not self.repair_goals and self.evolution_cycle > 0:
                logger.info("No more repair goals, evolution complete")
                break

            # Check if we've been stuck in a loop
            if self._detect_stuck_cycle():
                logger.warning("Detected stuck cycle, stopping evolution")
                break

        logger.info("Full evolution loop completed")
        return final_report or self._generate_summary_report()

    def _detect_stuck_cycle(self) -> bool:
        """Detect if the evolution is stuck in a loop."""
        if len(self.failure_log) < 3:
            return False

        # Check if last 3 failures are in the same phase
        recent_phases = [f["phase"] for f in self.failure_log[-3:]]
        return len(set(recent_phases)) == 1

    def get_failure_log(self) -> List[Dict[str, Any]]:
        """Return the complete failure log."""
        return self.failure_log

    def get_repair_goals(self) -> List[Dict[str, Any]]:
        """Return all generated repair goals."""
        return self.repair_goals

    def get_module_snapshots(self) -> Dict[str, str]:
        """Return all module AST snapshots."""
        return self.module_snapshots

    def export_report(self, output_path: str = "evolution_report.json"):
        """Export the evolution report to a JSON file."""
        report = self._generate_summary_report()
        with open(output_path, 'w') as f:
            json.dump(report, f, indent=2)
        logger.info(f"Report exported to {output_path}")
        return report


def main():
    """Main entry point for running the integration test harness."""
    harness = SystemicIntegrationTestHarness()
    report = harness.run_full_evolution()

    # Export report
    harness.export_report()

    # Print summary
    print("\n=== Evolution Summary ===")
    print(f"Total Cycles: {report['total_cycles']}")
    print(f"Total Failures: {report['total_failures']}")
    print(f"Total Repair Goals: {report['total_repair_goals']}")
    print(f"Failures by Phase: {report['failures_by_phase']}")

    return 0 if report['total_failures'] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())