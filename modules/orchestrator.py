from typing import Dict, List, Any
import logging
import subprocess
import os
from modules.failure_pattern_learner import FailurePatternLearner
from modules.mutation_engine import MutationEngine
from modules.ecology_engine import EcologyEngine
from modules.test_runner import TestRunner

logger = logging.getLogger(__name__)

class Orchestrator:
    """Integrates failure pattern learning and ecology engine into the evolution loop."""

    def __init__(self, mutation_engine: MutationEngine, failure_learner: FailurePatternLearner, 
                 ecology_engine: EcologyEngine, test_runner: TestRunner):
        self.mutation_engine = mutation_engine
        self.failure_learner = failure_learner
        self.ecology_engine = ecology_engine
        self.test_runner = test_runner
        self.cycle_count = 0
        self.adjustment_interval = 5
        self.ecology_interval = 10
        self.injected_tests = set()
        self.injection_log = []

    def _init_git_repo(self) -> None:
        """Initialize git repository if not already exists."""
        if not os.path.exists('.git'):
            subprocess.run(['git', 'init'], check=True, capture_output=True)
            logger.info("Initialized new git repository")
        
        # Ensure we have an initial commit if repo is empty
        result = subprocess.run(['git', 'rev-list', '--max-parents=0', 'HEAD'], 
                              capture_output=True, text=True)
        if result.returncode != 0:
            # Create initial commit
            subprocess.run(['git', 'add', '-A'], check=True, capture_output=True)
            subprocess.run(['git', 'commit', '-m', 'Initial commit'], 
                         check=True, capture_output=True)
            logger.info("Created initial commit")

    def _stage_all_changes(self) -> None:
        """Stage all changes in the working directory."""
        subprocess.run(['git', 'add', '-A'], check=True, capture_output=True)

    def _create_pre_mutation_commit(self, goal_id: str) -> None:
        """Create a pre-mutation commit."""
        self._stage_all_changes()
        commit_message = f'pre-mutation: {goal_id}'
        subprocess.run(['git', 'commit', '-m', commit_message], 
                      check=True, capture_output=True)
        logger.debug(f"Created pre-mutation commit: {commit_message}")

    def _create_success_commit(self, goal_id: str) -> None:
        """Create a success commit after mutation."""
        self._stage_all_changes()
        commit_message = f'mutation: {goal_id} - success'
        subprocess.run(['git', 'commit', '-m', commit_message], 
                      check=True, capture_output=True)
        logger.debug(f"Created success commit: {commit_message}")

    def git_rollback(self) -> None:
        """Revert to previous state and confirm clean working tree."""
        try:
            # Revert the last commit
            result = subprocess.run(['git', 'revert', 'HEAD', '--no-edit'], 
                                  check=True, capture_output=True, text=True)
            logger.info(f"Git revert completed: {result.stdout.strip()}")
            
            # Verify working tree is clean
            status_result = subprocess.run(['git', 'status', '--porcelain'], 
                                         capture_output=True, text=True)
            if status_result.stdout.strip():
                logger.warning(f"Working tree not clean after revert: {status_result.stdout}")
            else:
                logger.info("Working tree is clean after revert")
                
        except subprocess.CalledProcessError as e:
            logger.error(f"Git rollback failed: {e.stderr}")
            raise

    def run_evolution_cycle(self, mutation_attempts: List[Dict[str, Any]]) -> None:
        """Execute one evolution cycle with failure tracking, weight adjustment, and ecology pressure."""
        # Initialize git repo at start
        self._init_git_repo()
        
        for attempt in mutation_attempts:
            goal_id = attempt.get("goal_id", f"cycle_{self.cycle_count}")
            
            try:
                # Create pre-mutation commit
                self._create_pre_mutation_commit(goal_id)
                
                # Perform mutation
                success = self._perform_mutation(attempt)
                
                if success:
                    # Create success commit
                    self._create_success_commit(goal_id)
                else:
                    # Rollback on failure
                    self.git_rollback()
                    self._handle_mutation_failure(attempt)
                    
            except Exception as e:
                # Rollback on any exception
                self.git_rollback()
                self._handle_mutation_failure(attempt, error=str(e))

        self.cycle_count += 1
        if self.cycle_count % self.adjustment_interval == 0:
            self._adjust_operator_weights()
        
        if self.cycle_count % self.ecology_interval == 0:
            self._apply_ecology_pressure()

    def _handle_mutation_failure(self, attempt: Dict[str, Any], error: str = "Unknown error") -> None:
        """Record failure details and update learner."""
        failure_details = {
            "operator": attempt.get("operator", "unknown"),
            "input": attempt.get("input"),
            "error": error,
            "cycle": self.cycle_count
        }
        self.failure_learner.record_failure(failure_details)
        logger.debug(f"Recorded failure: {failure_details}")

    def _adjust_operator_weights(self) -> None:
        """Analyze failures and update mutation engine weights."""
        adjusted_weights = self.failure_learner.analyze_and_adjust()
        if adjusted_weights:
            self.mutation_engine.set_operator_weights(adjusted_weights)
            logger.info(f"Adjusted operator weights: {adjusted_weights}")

    def _perform_mutation(self, attempt: Dict[str, Any]) -> bool:
        """Placeholder for actual mutation logic. Returns True if successful."""
        # Replace with real mutation execution
        return True

    def _apply_ecology_pressure(self) -> None:
        """Generate and inject new tests from ecology engine, preventing duplicates."""
        new_tests = self.ecology_engine.generate_ecology_pressure()
        
        for test in new_tests:
            test_signature = self._get_test_signature(test)
            
            if test_signature not in self.injected_tests:
                self.injected_tests.add(test_signature)
                self.test_runner.add_test(test)
                
                injection_record = {
                    "test": test,
                    "source": test.get("source", "unknown"),
                    "cycle": self.cycle_count,
                    "signature": test_signature
                }
                self.injection_log.append(injection_record)
                logger.info(f"Injected new test from {test.get('source', 'unknown')}: {test_signature}")
                
                # Track impact on downstream capability fitness
                self._track_test_impact(test)
            else:
                logger.debug(f"Skipped duplicate test: {test_signature}")

    def _get_test_signature(self, test: Dict[str, Any]) -> str:
        """Generate a unique signature for a test based on its function definition."""
        test_func = test.get("function")
        if test_func and callable(test_func):
            return f"{test_func.__name__}_{test_func.__code__.co_code}"
        return str(test.get("name", test))

    def _track_test_impact(self, test: Dict[str, Any]) -> None:
        """Track the impact of injected tests on downstream capability fitness."""
        test_name = test.get("name", "unknown")
        test_source = test.get("source", "unknown")
        
        # Record test injection for fitness tracking
        impact_data = {
            "test_name": test_name,
            "source": test_source,
            "cycle": self.cycle_count,
            "timestamp": self.cycle_count * 10  # Simplified timestamp
        }
        
        # Store impact data for later analysis
        if not hasattr(self, 'test_impacts'):
            self.test_impacts = []
        self.test_impacts.append(impact_data)
        
        logger.debug(f"Tracked test impact: {impact_data}")

    def get_injection_statistics(self) -> Dict[str, Any]:
        """Return statistics about test injections."""
        source_counts = {}
        for record in self.injection_log:
            source = record.get("source", "unknown")
            source_counts[source] = source_counts.get(source, 0) + 1
        
        return {
            "total_injections": len(self.injection_log),
            "unique_tests": len(self.injected_tests),
            "source_distribution": source_counts,
            "last_injection_cycle": self.injection_log[-1]["cycle"] if self.injection_log else None
        }