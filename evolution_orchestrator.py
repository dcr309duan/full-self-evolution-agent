"""evolution_orchestrator.py

Main orchestrator for the self-evolving system. Initializes all subsystems and runs a
continuous evolution loop that scores, selects, mutates, tests, and evaluates each subsystem.
Includes a goal_selection mechanism that maintains a priority queue of evolution goals.
"""

import time
import logging
import os
import heapq
import json
from typing import Dict, Any, Optional, List, Tuple

# Subsystem imports (placeholders for actual implementations)
from api_server import APIServer
from task_scheduler import TaskScheduler
from web_scraper import WebScraper
from mutation_engine import MutationEngine
from testing_framework import TestingFramework
from failure_analysis import FailureAnalysis
from meta_evaluation import MetaEvaluation

logger = logging.getLogger(__name__)

# Configuration for failure threshold and strategy switch
FAILURE_THRESHOLD = 3  # Number of consecutive failures before triggering strategy switch
EVOLUTION_INTERVAL = 60.0  # Default interval between evolution cycles in seconds
STATE_FILE = "orchestrator_state.json"  # File to persist orchestrator state
LOG_FILE = "evolution_log.json"  # File to log evolution cycles


class EvolutionOrchestrator:
    """Main orchestrator that initializes all subsystems and runs the continuous evolution loop."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}

        # Initialize all subsystems
        self.api_server = APIServer(self.config.get("api_server", {}))
        self.task_scheduler = TaskScheduler(self.config.get("task_scheduler", {}))
        self.web_scraper = WebScraper(self.config.get("web_scraper", {}))
        self.mutation_engine = MutationEngine(self.config.get("mutation_engine", {}))
        self.testing_framework = TestingFramework(self.config.get("testing_framework", {}))
        self.failure_analysis = FailureAnalysis(self.config.get("failure_analysis", {}))
        self.meta_evaluation = MetaEvaluation(self.config.get("meta_evaluation", {}))

        # Subsystem health / performance scores (0.0 = worst, 1.0 = best)
        self.subsystem_scores: Dict[str, float] = {
            "api_server": 1.0,
            "task_scheduler": 1.0,
            "web_scraper": 1.0,
            "mutation_engine": 1.0,
            "testing_framework": 1.0,
            "failure_analysis": 1.0,
            "meta_evaluation": 1.0,
        }

        # Count consecutive failures per subsystem
        self.consecutive_failures: Dict[str, int] = {name: 0 for name in self.subsystem_scores}

        # History log
        self.evolution_history: list = []

        # Control flag
        self.running = False

        # Mapping of subsystem names to their source file paths
        self.subsystem_source_paths: Dict[str, str] = {
            "api_server": "api_server.py",
            "task_scheduler": "task_scheduler.py",
            "web_scraper": "web_scraper.py",
            "mutation_engine": "mutation_engine.py",
            "testing_framework": "testing_framework.py",
            "failure_analysis": "failure_analysis.py",
            "meta_evaluation": "meta_evaluation.py",
        }

        # Mapping of subsystem names to their instances for restart
        self.subsystem_instances: Dict[str, object] = {
            "api_server": self.api_server,
            "task_scheduler": self.task_scheduler,
            "web_scraper": self.web_scraper,
            "mutation_engine": self.mutation_engine,
            "testing_framework": self.testing_framework,
            "failure_analysis": self.failure_analysis,
            "meta_evaluation": self.meta_evaluation,
        }

        # Goal selection mechanism: priority queue of evolution goals
        # Each goal is a tuple: (priority, timestamp, goal_description, subsystem_mapping)
        # Lower priority value = higher priority (standard heapq behavior)
        self.goal_queue: List[Tuple[int, float, str, str]] = []
        self._initialize_goal_queue()

        # Load persisted state if available
        self._load_state()

        logger.info("EvolutionOrchestrator initialized with subsystems: %s", list(self.subsystem_scores.keys()))

    def _initialize_goal_queue(self):
        """Initialize the goal queue with default goals and their priorities."""
        # Default goals with priorities (lower number = higher priority)
        default_goals = [
            (1, time.time(), "fix scheduler bug", "task_scheduler"),
            (2, time.time(), "improve API throughput", "api_server"),
            (3, time.time(), "add new scraper source", "web_scraper"),
            (4, time.time(), "optimize mutation engine", "mutation_engine"),
            (5, time.time(), "enhance testing framework", "testing_framework"),
            (6, time.time(), "improve failure analysis", "failure_analysis"),
            (7, time.time(), "refine meta evaluation", "meta_evaluation"),
        ]
        
        for goal in default_goals:
            heapq.heappush(self.goal_queue, goal)
        
        logger.info("Goal queue initialized with %d goals", len(default_goals))

    def add_goal(self, priority: int, goal_description: str, subsystem: str):
        """Add a new goal to the priority queue.

        Args:
            priority: Priority value (lower = higher priority)
            goal_description: Description of the goal
            subsystem: Target subsystem for this goal
        """
        if subsystem not in self.subsystem_scores:
            logger.error("Invalid subsystem '%s' for goal '%s'", subsystem, goal_description)
            return
        
        timestamp = time.time()
        heapq.heappush(self.goal_queue, (priority, timestamp, goal_description, subsystem))
        logger.info("Added goal '%s' with priority %d for subsystem '%s'", 
                    goal_description, priority, subsystem)

    def get_highest_priority_goal(self) -> Optional[Tuple[int, float, str, str]]:
        """Get the highest priority goal from the queue without removing it.

        Returns:
            The highest priority goal tuple, or None if queue is empty
        """
        if not self.goal_queue:
            return None
        return self.goal_queue[0]

    def pop_highest_priority_goal(self) -> Optional[Tuple[int, float, str, str]]:
        """Pop and return the highest priority goal from the queue.

        Returns:
            The highest priority goal tuple, or None if queue is empty
        """
        if not self.goal_queue:
            return None
        return heapq.heappop(self.goal_queue)

    def map_goal_to_subsystem(self, goal: Tuple[int, float, str, str]) -> str:
        """Map a goal to its target subsystem.

        Args:
            goal: A goal tuple (priority, timestamp, description, subsystem)

        Returns:
            The name of the target subsystem
        """
        return goal[3]

    def score_subsystems(self) -> Dict[str, float]:
        """Score each subsystem's current performance/health.

        Returns:
            Dict mapping subsystem name to a score between 0.0 and 1.0.
        """
        scores = {}
        # Collect health metrics from each subsystem
        scores["api_server"] = self.api_server.get_health_score()
        scores["task_scheduler"] = self.task_scheduler.get_health_score()
        scores["web_scraper"] = self.web_scraper.get_health_score()
        scores["mutation_engine"] = self.mutation_engine.get_health_score()
        scores["testing_framework"] = self.testing_framework.get_health_score()
        scores["failure_analysis"] = self.failure_analysis.get_health_score()
        scores["meta_evaluation"] = self.meta_evaluation.get_health_score()

        # Clamp to [0, 1]
        for name in scores:
            scores[name] = max(0.0, min(1.0, scores[name]))

        self.subsystem_scores = scores
        logger.debug("Subsystem scores updated: %s", scores)
        return scores

    def select_subsystem_to_evolve(self) -> str:
        """Select which subsystem to evolve next based on goal queue and subsystem health.

        Returns:
            Name of the subsystem to evolve.
        """
        # First, check if there are goals in the queue
        highest_goal = self.get_highest_priority_goal()
        
        if highest_goal:
            # Get the target subsystem from the highest priority goal
            target_subsystem = self.map_goal_to_subsystem(highest_goal)
            
            # Check if this subsystem has a very low score or high failures
            score = self.subsystem_scores.get(target_subsystem, 1.0)
            failures = self.consecutive_failures.get(target_subsystem, 0)
            
            # If the subsystem is in a critical state, still use it but log a warning
            if score < 0.3 or failures >= FAILURE_THRESHOLD:
                logger.warning("Selected subsystem '%s' from goal queue despite poor health (score=%.2f, failures=%d)",
                              target_subsystem, score, failures)
            
            logger.info("Selected subsystem '%s' based on highest priority goal: '%s'", 
                       target_subsystem, highest_goal[2])
            return target_subsystem
        
        # Fallback to original selection method if no goals in queue
        logger.info("No goals in queue, falling back to score-based selection")
        priority = {}
        for name in self.subsystem_scores:
            failure_factor = min(self.consecutive_failures.get(name, 0), 10) / 10.0
            priority[name] = (1.0 - self.subsystem_scores[name]) + failure_factor

        selected = max(priority, key=priority.get)
        logger.info("Selected subsystem '%s' for evolution (priority=%.2f)", selected, priority[selected])
        return selected

    def read_subsystem_source_code(self, subsystem_name: str) -> Optional[str]:
        """Read the source code of a subsystem from disk.

        Args:
            subsystem_name: Name of the subsystem.

        Returns:
            Source code as a string, or None if reading fails.
        """
        file_path = self.subsystem_source_paths.get(subsystem_name)
        if not file_path or not os.path.exists(file_path):
            logger.error("Source file for subsystem '%s' not found at '%s'", subsystem_name, file_path)
            return None
        
        try:
            with open(file_path, 'r') as f:
                source_code = f.read()
            logger.debug("Read source code for subsystem '%s' from '%s'", subsystem_name, file_path)
            return source_code
        except Exception as e:
            logger.exception("Failed to read source code for subsystem '%s': %s", subsystem_name, e)
            return None

    def write_subsystem_source_code(self, subsystem_name: str, source_code: str) -> bool:
        """Write mutated source code back to disk.

        Args:
            subsystem_name: Name of the subsystem.
            source_code: The mutated source code to write.

        Returns:
            True if writing was successful, False otherwise.
        """
        file_path = self.subsystem_source_paths.get(subsystem_name)
        if not file_path:
            logger.error("No file path configured for subsystem '%s'", subsystem_name)
            return False
        
        try:
            with open(file_path, 'w') as f:
                f.write(source_code)
            logger.info("Successfully wrote mutated code for subsystem '%s' to '%s'", subsystem_name, file_path)
            return True
        except Exception as e:
            logger.exception("Failed to write source code for subsystem '%s': %s", subsystem_name, e)
            return False

    def restart_subsystem(self, subsystem_name: str) -> bool:
        """Restart a subsystem after successful mutation.

        Args:
            subsystem_name: Name of the subsystem to restart.

        Returns:
            True if restart was successful, False otherwise.
        """
        instance = self.subsystem_instances.get(subsystem_name)
        if not instance:
            logger.error("No instance found for subsystem '%s'", subsystem_name)
            return False
        
        try:
            if hasattr(instance, 'restart'):
                instance.restart()
                logger.info("Subsystem '%s' restarted successfully", subsystem_name)
                return True
            else:
                logger.warning("Subsystem '%s' does not have a restart method", subsystem_name)
                return False
        except Exception as e:
            logger.exception("Failed to restart subsystem '%s': %s", subsystem_name, e)
            return False

    def trigger_strategy_switch(self, subsystem_name: str):
        """Trigger a strategy switch for a subsystem that has failed too many times.

        Args:
            subsystem_name: Name of the subsystem to switch strategy for.
        """
        logger.warning("Triggering strategy switch for subsystem '%s' due to %d consecutive failures",
                       subsystem_name, self.consecutive_failures[subsystem_name])
        # Reset failure counter after triggering strategy switch
        self.consecutive_failures[subsystem_name] = 0
        
        # Placeholder for actual strategy switch logic
        # This could involve changing configuration, loading alternative implementations, etc.
        try:
            instance = self.subsystem_instances.get(subsystem_name)
            if instance and hasattr(instance, 'switch_strategy'):
                instance.switch_strategy()
                logger.info("Strategy switch completed for subsystem '%s'", subsystem_name)
            else:
                logger.warning("Subsystem '%s' does not support strategy switching", subsystem_name)
        except Exception as e:
            logger.exception("Error during strategy switch for subsystem '%s': %s", subsystem_name, e)

    def evolve_subsystem(self, subsystem_name: str) -> bool:
        """Trigger the mutation engine to evolve the specified subsystem.

        Args:
            subsystem_name: Name of the subsystem to evolve.

        Returns:
            True if mutation was applied successfully, False otherwise.
        """
        subsystem_map = {
            "api_server": self.api_server,
            "task_scheduler": self.task_scheduler,
            "web_scraper": self.web_scraper,
            "mutation_engine": self.mutation_engine,
            "testing_framework": self.testing_framework,
            "failure_analysis": self.failure_analysis,
            "meta_evaluation": self.meta_evaluation,
        }

        target = subsystem_map.get(subsystem_name)
        if target is None:
            logger.error("Unknown subsystem: %s", subsystem_name)
            return False

        logger.info("Evolving subsystem '%s'...", subsystem_name)
        try:
            success = self.mutation_engine.evolve(target)
            if success:
                logger.info("Subsystem '%s' evolved successfully.", subsystem_name)
            else:
                logger.warning("Subsystem '%s' evolution returned failure.", subsystem_name)
            return success
        except Exception as e:
            logger.exception("Exception during evolution of '%s': %s", subsystem_name, e)
            return False

    def run_tests(self, subsystem_name: str) -> bool:
        """Run tests for the given subsystem.

        Args:
            subsystem_name: Name of the subsystem to test.

        Returns:
            True if all tests pass, False otherwise.
        """
        logger.info("Running tests for subsystem '%s'...", subsystem_name)
        try:
            passed = self.testing_framework.run_tests(subsystem_name)
            logger.info("Tests for '%s' %s.", subsystem_name, "passed" if passed else "failed")
            return passed
        except Exception as e:
            logger.exception("Exception during testing of '%s': %s", subsystem_name, e)
            return False

    def evaluate_success(self, subsystem_name: str, tests_passed: bool) -> bool:
        """Evaluate whether the evolution was successful.

        Args:
            subsystem_name: Name of the subsystem that was evolved.
            tests_passed: Whether the tests passed.

        Returns:
            True if evolution is considered successful, False otherwise.
        """
        # Basic evaluation: tests must pass
        # Could be extended with performance benchmarks, regression checks, etc.
        if tests_passed:
            logger.info("Evolution of '%s' evaluated as SUCCESS.", subsystem_name)
            return True
        else:
            logger.warning("Evolution of '%s' evaluated as FAILURE.", subsystem_name)
            return False

    def update_scores_and_log(self, subsystem_name: str, success: bool):
        """Update subsystem scores and log the evolution result.

        Args:
            subsystem_name: The subsystem that was evolved.
            success: Whether the evolution was successful.
        """
        # Update consecutive failures
        if success:
            self.consecutive_failures[subsystem_name] = 0
            # Boost score slightly on success
            self.subsystem_scores[subsystem_name] = min(
                1.0, self.subsystem_scores[subsystem_name] + 0.1
            )
        else:
            self.consecutive_failures[subsystem_name] += 1
            # Reduce score on failure
            self.subsystem_scores[subsystem_name] = max(
                0.0, self.subsystem_scores[subsystem_name] - 0.2
            )

        # Log to history
        entry = {
            "timestamp": time.time(),
            "subsystem": subsystem_name,
            "success": success,
            "score": self.subsystem_scores[subsystem_name],
            "consecutive_failures": self.consecutive_failures[subsystem_name],
        }
        self.evolution_history.append(entry)
        logger.info("Evolution history updated: %s", entry)

    def _log_evolution_cycle(self, subsystem_name: str, strategy: str, success: bool, old_scores: Dict[str, float], new_scores: Dict[str, float]):
        """Log an evolution cycle to the JSON log file.

        Args:
            subsystem_name: The subsystem that was evolved.
            strategy: The strategy used for evolution.
            success: Whether the evolution was successful.
            old_scores: The subsystem scores before evolution.
            new_scores: The subsystem scores after evolution.
        """
        log_entry = {
            "timestamp": time.time(),
            "subsystem": subsystem_name,
            "strategy": strategy,
            "success": success,
            "old_scores": old_scores,
            "new_scores": new_scores,
            "consecutive_failures": self.consecutive_failures.get(subsystem_name, 0)
        }
        
        try:
            with open(LOG_FILE, 'a') as f:
                f.write(json.dumps(log_entry) + '\n')
            logger.debug("Evolution cycle logged to %s", LOG_FILE)
        except Exception as e:
            logger.error("Failed to log evolution cycle to %s: %s", LOG_FILE, e)

    def _save_state(self):
        """Save the current orchestrator state to a JSON file for resumption."""
        state = {
            "subsystem_scores": self.subsystem_scores,
            "consecutive_failures": self.consecutive_failures,
            "goal_queue": list(self.goal_queue),
            "evolution_history": self.evolution_history[-100:],  # Keep last 100 entries
            "timestamp": time.time()
        }
        
        try:
            with open(STATE_FILE, 'w') as f:
                json.dump(state, f, indent=2)
            logger.debug("Orchestrator state saved to %s", STATE_FILE)
        except Exception as e:
            logger.error("Failed to save orchestrator state to %s: %s", STATE_FILE, e)

    def _load_state(self):
        """Load the orchestrator state from a JSON file if it exists."""
        if not os.path.exists(STATE_FILE):
            logger.info("No saved state found at %s, starting fresh", STATE_FILE)
            return
        
        try:
            with open(STATE_FILE, 'r') as f:
                state = json.load(f)
            
            # Restore subsystem scores
            if "subsystem_scores" in state:
                self.subsystem_scores.update(state["subsystem_scores"])
                logger.info("Restored subsystem scores from saved state")
            
            # Restore consecutive failures
            if "consecutive_failures" in state:
                self.consecutive_failures.update(state["consecutive_failures"])
                logger.info("Restored consecutive failures from saved state")
            
            # Restore goal queue
            if "goal_queue" in state:
                self.goal_queue = [tuple(g) for g in state["goal_queue"]]
                heapq.heapify(self.goal_queue)
                logger.info("Restored goal queue with %d goals from saved state", len(self.goal_queue))
            
            # Restore evolution history
            if "evolution_history" in state:
                self.evolution_history = state["evolution_history"]
                logger.info("Restored %d evolution history entries from saved state", len(self.evolution_history))
            
            logger.info("Orchestrator state loaded successfully from %s", STATE_FILE)
        except Exception as e:
            logger.error("Failed to load orchestrator state from %s: %s", STATE_FILE, e)

    def evolution_cycle(self):
        """Execute one complete evolution cycle."""
        logger.info("Starting evolution cycle...")

        # Save old scores for logging
        old_scores = self.subsystem_scores.copy()

        # 1) Score each subsystem
        self.score_subsystems()

        # 2) Identify the subsystem to evolve using goal selection mechanism
        selected = self.select_subsystem_to_evolve()

        # Determine the strategy used
        strategy = "goal_based" if self.get_highest_priority_goal() else "score_based"

        # If a goal was used, pop it from the queue
        highest_goal = self.get_highest_priority_goal()
        if highest_goal and self.map_goal_to_subsystem(highest_goal) == selected:
            self.pop_highest_priority_goal()
            logger.info("Popped goal '%s' from queue after selecting subsystem '%s'", 
                       highest_goal[2], selected)

        # 3) Read that subsystem's source code from disk
        source_code = self.read_subsystem_source_code(selected)
        if source_code is None:
            logger.error("Failed to read source code for '%s'. Skipping evolution.", selected)
            self.update_scores_and_log(selected, False)
            self._log_evolution_cycle(selected, strategy, False, old_scores, self.subsystem_scores)
            self._save_state()
            return

        # 4) Call mutation_engine.evolve_subsystem() with that code
        logger.info("Calling mutation engine to evolve subsystem '%s'", selected)
        try:
            mutated_code = self.mutation_engine.evolve_subsystem(source_code)
        except Exception as e:
            logger.exception("Mutation engine failed to evolve subsystem '%s': %s", selected, e)
            self.update_scores_and_log(selected, False)
            self._log_evolution_cycle(selected, strategy, False, old_scores, self.subsystem_scores)
            self._save_state()
            return

        if mutated_code is None:
            logger.error("Mutation engine returned None for subsystem '%s'. Evolution failed.", selected)
            self.update_scores_and_log(selected, False)
            self._log_evolution_cycle(selected, strategy, False, old_scores, self.subsystem_scores)
            self._save_state()
            return

        # 5) If successful, write the mutated code back to disk and restart the subsystem
        write_success = self.write_subsystem_source_code(selected, mutated_code)
        if not write_success:
            logger.error("Failed to write mutated code for subsystem '%s'. Evolution failed.", selected)
            self.update_scores_and_log(selected, False)
            self._log_evolution_cycle(selected, strategy, False, old_scores, self.subsystem_scores)
            self._save_state()
            return

        restart_success = self.restart_subsystem(selected)
        if not restart_success:
            logger.warning("Failed to restart subsystem '%s' after mutation. Continuing anyway.", selected)

        # Run tests to validate the mutation
        tests_passed = self.run_tests(selected)
        success = self.evaluate_success(selected, tests_passed)

        # 6) If failed, log failure and increment failure counter for that subsystem
        if not success:
            logger.warning("Evolution of subsystem '%s' failed. Incrementing failure counter.", selected)
            self.update_scores_and_log(selected, False)
            
            # 7) If failure counter reaches threshold, integrate with failure analysis module
            if self.consecutive_failures[selected] >= FAILURE_THRESHOLD:
                logger.warning("Failure threshold reached for subsystem '%s'. Calling failure analysis module.", selected)
                try:
                    # Call the failure analysis module to analyze the subsystem failure
                    analysis_result = self.failure_analysis.analyze_subsystem_failure(selected)
                    logger.info("Failure analysis result for '%s': %s", selected, analysis_result)
                    
                    # Apply the recommended strategy from failure analysis
                    if analysis_result and "recommended_strategy" in analysis_result:
                        recommended_strategy = analysis_result["recommended_strategy"]
                        logger.info("Applying recommended strategy '%s' for subsystem '%s'", recommended_strategy, selected)
                        
                        # Apply the strategy based on the recommendation
                        if recommended_strategy == "switch_strategy":
                            self.trigger_strategy_switch(selected)
                        elif recommended_strategy == "rollback":
                            # Rollback to previous version if available
                            logger.info("Rolling back subsystem '%s' to previous version", selected)
                            # Placeholder for rollback logic
                        elif recommended_strategy == "adjust_parameters":
                            # Adjust subsystem parameters
                            logger.info("Adjusting parameters for subsystem '%s'", selected)
                            # Placeholder for parameter adjustment
                        elif recommended_strategy == "reinitialize":
                            # Reinitialize the subsystem
                            logger.info("Reinitializing subsystem '%s'", selected)
                            # Placeholder for reinitialization logic
                        else:
                            logger.warning("Unknown recommended strategy '%s' for subsystem '%s'", recommended_strategy, selected)
                    else:
                        logger.warning("No recommended strategy provided by failure analysis for subsystem '%s'", selected)
                        # Fallback to default strategy switch
                        self.trigger_strategy_switch(selected)
                except Exception as e:
                    logger.exception("Error during failure analysis integration for subsystem '%s': %s", selected, e)
                    # Fallback to default strategy switch
                    self.trigger_strategy_switch(selected)
        else:
            self.update_scores_and_log(selected, True)

        # Log the evolution cycle
        self._log_evolution_cycle(selected, strategy, success, old_scores, self.subsystem_scores)
        
        # Save state after each cycle
        self._save_state()

        logger.info("Evolution cycle completed for '%s' (success=%s).", selected, success)

    def run_continuous_loop(self, interval_seconds: float = EVOLUTION_INTERVAL):
        """Run the continuous evolution loop.

        Args:
            interval_seconds: Time in seconds between evolution cycles.
        """
        self.running = True
        logger.info("Starting continuous evolution loop with interval %.2f seconds.", interval_seconds)

        try:
            while self.running:
                self.evolution_cycle()
                # 8) Sleep for configurable interval then repeat
                time.sleep(interval_seconds)
        except KeyboardInterrupt:
            logger.info("Evolution loop interrupted by user.")
        except Exception as e:
            logger.exception("Unexpected error in evolution loop: %s", e)
        finally:
            self.running = False
            # Save state on exit
            self._save_state()
            logger.info("Evolution loop stopped.")

    def stop(self):
        """Signal the continuous loop to stop."""
        self.running = False
        logger.info("Stop signal sent to evolution loop.")


# Example usage (if run as script)
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    orchestrator = EvolutionOrchestrator()
    
    # Example of adding custom goals
    orchestrator.add_goal(1, "urgent: fix API server crash", "api_server")
    orchestrator.add_goal(5, "improve web scraper efficiency", "web_scraper")
    
    # Run a single cycle for demonstration
    orchestrator.evolution_cycle()
    # Uncomment to run continuously:
    # orchestrator.run_continuous_loop(interval_seconds=10)