from typing import Dict, List, Any
import logging
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

    def run_evolution_cycle(self, mutation_attempts: List[Dict[str, Any]]) -> None:
        """Execute one evolution cycle with failure tracking, weight adjustment, and ecology pressure."""
        for attempt in mutation_attempts:
            try:
                # Simulate mutation attempt (replace with actual logic)
                success = self._perform_mutation(attempt)
                if not success:
                    self._handle_mutation_failure(attempt)
            except Exception as e:
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