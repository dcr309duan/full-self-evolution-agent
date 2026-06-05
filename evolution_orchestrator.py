"""evolution_orchestrator.py

Main orchestrator for the self-evolving system. Initializes all subsystems and runs a
continuous evolution loop that scores, selects, mutates, tests, and evaluates each subsystem.
Includes a goal_selection mechanism that maintains a priority queue of evolution goals.
Integrates reflection parsing to close the feedback loop between mutation outcomes and strategy selection.
Integrates Nash equilibrium detection and coordinated mutation planning to escape local optima.
Includes a health check hook that updates the system health dashboard after each mutation cycle,
and a health check threshold that pauses evolution if the dashboard reports a critical integration conflict.
Includes a post-mutation hook that calls self_model_consistency_validator.after_mutation(modified_files)
after every successful mutation. If critical mismatches are found, the orchestrator should either
rollback the mutation or queue a repair goal.
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
from reflection_parser import ReflectionParser
from nash_detector import NashEquilibriumDetector  # New import for Nash detection
from coordinated_planner import CoordinatedMutationPlanner  # New import for coordinated planning
from system_health_dashboard import SystemHealthDashboard  # Import for health dashboard
from self_model_consistency_validator import SelfModelConsistencyValidator  # Import for consistency validation

logger = logging.getLogger(__name__)

# Configuration for failure threshold and strategy switch
FAILURE_THRESHOLD = 3  # Number of consecutive failures before triggering strategy switch
EVOLUTION_INTERVAL = 60.0  # Default interval between evolution cycles in seconds
STATE_FILE = "orchestrator_state.json"  # File to persist orchestrator state
LOG_FILE = "evolution_log.json"  # File to log evolution cycles
REFLECTION_LOG_FILE = "reflection_log.json"  # File to log reflection data
NASH_DETECTION_INTERVAL = 5  # Number of cycles between Nash equilibrium checks
HEALTH_CHECK_THRESHOLD = 3  # Number of critical integration conflicts before pausing evolution


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
        self.reflection_parser = ReflectionParser(self.config.get("reflection_parser", {}))
        self.nash_detector = NashEquilibriumDetector(self.config.get("nash_detector", {}))  # New subsystem
        self.coordinated_planner = CoordinatedMutationPlanner(self.config.get("coordinated_planner", {}))  # New subsystem
        self.system_health_dashboard = SystemHealthDashboard(self.config.get("system_health_dashboard", {}))  # New subsystem
        self.consistency_validator = SelfModelConsistencyValidator(self.config.get("consistency_validator", {}))  # New subsystem

        # Subsystem health / performance scores (0.0 = worst, 1.0 = best)
        self.subsystem_scores: Dict[str, float] = {
            "api_server": 1.0,
            "task_scheduler": 1.0,
            "web_scraper": 1.0,
            "mutation_engine": 1.0,
            "testing_framework": 1.0,
            "failure_analysis": 1.0,
            "meta_evaluation": 1.0,
            "reflection_parser": 1.0,
            "nash_detector": 1.0,  # Added nash_detector score
            "coordinated_planner": 1.0,  # Added coordinated_planner score
            "system_health_dashboard": 1.0,  # Added system_health_dashboard score
            "consistency_validator": 1.0,  # Added consistency_validator score
        }

        # Count consecutive failures per subsystem
        self.consecutive_failures: Dict[str, int] = {name: 0 for name in self.subsystem_scores}

        # History log
        self.evolution_history: list = []

        # Control flag
        self.running = False

        # Nash equilibrium state tracking
        self.nash_detected = False
        self.cycles_since_nash_check = 0
        self.coordinated_mutation_active = False
        self.coordinated_mutation_plan = None

        # Health check state tracking
        self.health_check_conflict_count = 0
        self.evolution_paused = False

        # Mapping of subsystem names to their source file paths
        self.subsystem_source_paths: Dict[str, str] = {
            "api_server": "api_server.py",
            "task_scheduler": "task_scheduler.py",
            "web_scraper": "web_scraper.py",
            "mutation_engine": "mutation_engine.py",
            "testing_framework": "testing_framework.py",
            "failure_analysis": "failure_analysis.py",
            "meta_evaluation": "meta_evaluation.py",
            "reflection_parser": "reflection_parser.py",
            "nash_detector": "nash_detector.py",  # Added nash_detector path
            "coordinated_planner": "coordinated_planner.py",  # Added coordinated_planner path
            "system_health_dashboard": "system_health_dashboard.py",  # Added system_health_dashboard path
            "consistency_validator": "consistency_validator.py",  # Added consistency_validator path
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
            "reflection_parser": self.reflection_parser,
            "nash_detector": self.nash_detector,  # Added nash_detector instance
            "coordinated_planner": self.coordinated_planner,  # Added coordinated_planner instance
            "system_health_dashboard": self.system_health_dashboard,  # Added system_health_dashboard instance
            "consistency_validator": self.consistency_validator,  # Added consistency_validator instance
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
            (8, time.time(), "improve reflection parsing", "reflection_parser"),
            (9, time.time(), "improve nash detection", "nash_detector"),  # Added nash_detector goal
            (10, time.time(), "improve coordinated planning", "coordinated_planner"),  # Added coordinated_planner goal
            (11, time.time(), "improve system health dashboard", "system_health_dashboard"),  # Added system_health_dashboard goal
            (12, time.time(), "improve consistency validation", "consistency_validator"),  # Added consistency_validator goal
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
        scores["reflection_parser"] = self.reflection_parser.get_health_score()
        scores["nash_detector"] = self.nash_detector.get_health_score()  # Added nash_detector score
        scores["coordinated_planner"] = self.coordinated_planner.get_health_score()  # Added coordinated_planner score
        scores["system_health_dashboard"] = self.system_health_dashboard.get_health_score()  # Added system_health_dashboard score
        scores["consistency_validator"] = self.consistency_validator.get_health_score()  # Added consistency_validator score

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
        # If coordinated mutation is active, use the plan
        if self.coordinated_mutation_active and self.coordinated_mutation_plan:
            next_subsystem = self.coordinated_mutation_plan.get("next_subsystem")
            if next_subsystem and next_subsystem in self.subsystem_scores:
                logger.info("Using coordinated mutation plan, selecting subsystem '%s'", next_subsystem)
                return next_subsystem
        
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
            "reflection_parser": self.reflection_parser,
            "nash_detector": self.nash_detector,
            "coordinated_planner": self.coordinated_planner,
            "system_health_dashboard": self.system_health_dashboard,
            "consistency_validator": self.consistency_validator,
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
            "consecutive_failures": self.consecutive_failures.get(subsystem_name, 0),
            "nash_detected": self.nash_detected,
            "coordinated_mutation_active": self.coordinated_mutation_active,
            "evolution_paused": self.evolution_paused,
            "health_check_conflict_count": self.health_check_conflict_count,
        }
        
        try:
            with open(LOG_FILE, 'a') as f:
                f.write(json.dumps(log_entry) + '\n')
            logger.debug("Evolution cycle logged to %s", LOG_FILE)
        except Exception as e:
            logger.error("Failed to log evolution cycle to %s: %s", LOG_FILE, e)

    def _log_reflection_data(self, subsystem_name: str, reflection_data: Dict[str, Any]):
        """Log reflection data to the reflection log file.

        Args:
            subsystem_name: The subsystem that was reflected upon.
            reflection_data: The parsed reflection data.
        """
        log_entry = {
            "timestamp": time.time(),
            "subsystem": subsystem_name,
            "reflection_data": reflection_data
        }
        
        try:
            with open(REFLECTION_LOG_FILE, 'a') as f:
                f.write(json.dumps(log_entry) + '\n')
            logger.debug("Reflection data logged to %s", REFLECTION_LOG_FILE)
        except Exception as e:
            logger.error("Failed to log reflection data to %s: %s", REFLECTION_LOG_FILE, e)

    def _save_state(self):
        """Save the current orchestrator state to a JSON file for resumption."""
        state = {
            "subsystem_scores": self.subsystem_scores,
            "consecutive_failures": self.consecutive_failures,
            "goal_queue": list(self.goal_queue),
            "evolution_history": self.evolution_history[-100:],  # Keep last 100 entries
            "nash_detected": self.nash_detected,
            "cycles_since_nash_check": self.cycles_since_nash_check,
            "coordinated_mutation_active": self.coordinated_mutation_active,
            "coordinated_mutation_plan": self.coordinated_mutation_plan,
            "health_check_conflict_count": self.health_check_conflict_count,
            "evolution_paused": self.evolution_paused,
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
            
            # Restore Nash equilibrium state
            if "nash_detected" in state:
                self.nash_detected = state["nash_detected"]
            if "cycles_since_nash_check" in state:
                self.cycles_since_nash_check = state["cycles_since_nash_check"]
            if "coordinated_mutation_active" in state:
                self.coordinated_mutation_active = state["coordinated_mutation_active"]
            if "coordinated_mutation_plan" in state:
                self.coordinated_mutation_plan = state["coordinated_mutation_plan"]
            
            # Restore health check state
            if "health_check_conflict_count" in state:
                self.health_check_conflict_count = state["health_check_conflict_count"]
            if "evolution_paused" in state:
                self.evolution_paused = state["evolution_paused"]
            
            logger.info("Orchestrator state loaded successfully from %s", STATE_FILE)
        except Exception as e:
            logger.error("Failed to load orchestrator state from %s: %s", STATE_FILE, e)

    def _parse_reflection_and_update_strategy(self, subsystem_name: str, mutation_success: bool):
        """Parse the reflection log and update mutation strategies based on insights.

        This method implements the reflection parsing step in the unified evolution loop.
        After each mutation cycle, it parses the reflection log, extracts structured insights,
        and feeds them into the mutation strategy selector.

        Args:
            subsystem_name: The subsystem that was mutated.
            mutation_success: Whether the mutation was successful.
        """
        logger.info("Parsing reflection data for subsystem '%s' after mutation (success=%s)", 
                   subsystem_name, mutation_success)
        
        try:
            # Read the reflection log to get recent reflection data
            reflection_data = None
            if os.path.exists(REFLECTION_LOG_FILE):
                with open(REFLECTION_LOG_FILE, 'r') as f:
                    lines = f.readlines()
                    if lines:
                        # Get the last reflection entry for this subsystem
                        for line in reversed(lines):
                            try:
                                entry = json.loads(line.strip())
                                if entry.get("subsystem") == subsystem_name:
                                    reflection_data = entry.get("reflection_data")
                                    break
                            except json.JSONDecodeError:
                                continue
            
            # If no reflection data exists, create a basic one from the mutation outcome
            if reflection_data is None:
                reflection_data = {
                    "subsystem": subsystem_name,
                    "mutation_success": mutation_success,
                    "gaps_identified": [],
                    "priorities": [],
                    "insights": []
                }
            
            # Parse the reflection data to extract structured insights
            parsed_insights = self.reflection_parser.parse_reflection(reflection_data)
            
            if parsed_insights:
                logger.info("Parsed %d insights from reflection data for subsystem '%s'", 
                          len(parsed_insights), subsystem_name)
                
                # Extract gaps and priorities from parsed insights
                gaps = parsed_insights.get("gaps_identified", [])
                priorities = parsed_insights.get("priorities", [])
                
                # Feed insights into mutation strategy selector
                if gaps or priorities:
                    logger.info("Feeding %d gaps and %d priorities into mutation strategy selector for '%s'",
                              len(gaps), len(priorities), subsystem_name)
                    
                    # Update mutation engine strategy based on parsed insights
                    strategy_update = {
                        "subsystem": subsystem_name,
                        "gaps": gaps,
                        "priorities": priorities,
                        "insights": parsed_insights.get("insights", [])
                    }
                    
                    # Call mutation engine to update its strategy
                    self.mutation_engine.update_strategy(strategy_update)
                    
                    # Add new goals based on identified gaps and priorities
                    for gap in gaps:
                        if isinstance(gap, dict) and "description" in gap and "priority" in gap:
                            self.add_goal(
                                priority=gap["priority"],
                                goal_description=gap["description"],
                                subsystem=subsystem_name
                            )
                    
                    for priority in priorities:
                        if isinstance(priority, dict) and "description" in priority and "priority_level" in priority:
                            self.add_goal(
                                priority=priority["priority_level"],
                                goal_description=priority["description"],
                                subsystem=subsystem_name
                            )
                    
                    logger.info("Mutation strategy updated for subsystem '%s' based on reflection insights", 
                              subsystem_name)
                else:
                    logger.debug("No gaps or priorities found in reflection insights for '%s'", subsystem_name)
            else:
                logger.debug("No insights parsed from reflection data for subsystem '%s'", subsystem_name)
                
        except Exception as e:
            logger.exception("Error during reflection parsing for subsystem '%s': %s", subsystem_name, e)

    def _check_nash_equilibrium(self):
        """Check if the system has reached a Nash equilibrium state.
        
        A Nash equilibrium in this context means that no single subsystem mutation
        can improve the overall system performance. This is detected by analyzing
        the recent mutation history and subsystem scores.
        """
        logger.info("Checking for Nash equilibrium state...")
        
        try:
            # Collect recent mutation history for analysis
            recent_history = self.evolution_history[-20:] if len(self.evolution_history) >= 20 else self.evolution_history
            
            # Call the Nash detector to analyze the system state
            nash_result = self.nash_detector.detect_equilibrium(
                subsystem_scores=self.subsystem_scores,
                consecutive_failures=self.consecutive_failures,
                recent_history=recent_history
            )
            
            if nash_result and nash_result.get("nash_detected", False):
                logger.warning("Nash equilibrium detected! System is stuck in local optimum.")
                self.nash_detected = True
                
                # Log the Nash detection details
                nash_details = {
                    "timestamp": time.time(),
                    "detection_method": nash_result.get("method", "unknown"),
                    "confidence": nash_result.get("confidence", 0.0),
                    "stuck_subsystems": nash_result.get("stuck_subsystems", []),
                    "recommendation": nash_result.get("recommendation", "invoke_coordinated_planning")
                }
                logger.info("Nash detection details: %s", nash_details)
                
                # Invoke coordinated mutation planner
                self._invoke_coordinated_planner(nash_result)
            else:
                self.nash_detected = False
                logger.debug("No Nash equilibrium detected. Continuing normal operation.")
                
        except Exception as e:
            logger.exception("Error during Nash equilibrium detection: %s", e)
            self.nash_detected = False

    def _invoke_coordinated_planner(self, nash_result: Dict[str, Any]):
        """Invoke the coordinated mutation planner to escape Nash equilibrium.

        Args:
            nash_result: The result from the Nash equilibrium detector containing
                        information about which subsystems are stuck.
        """
        logger.info("Invoking coordinated mutation planner to escape Nash equilibrium...")
        
        try:
            # Get the stuck subsystems from the Nash result
            stuck_subsystems = nash_result.get("stuck_subsystems", list(self.subsystem_scores.keys()))
            
            # Call the coordinated planner to generate a mutation plan
            plan = self.coordinated_planner.generate_plan(
                stuck_subsystems=stuck_subsystems,
                subsystem_scores=self.subsystem_scores,
                consecutive_failures=self.consecutive_failures,
                evolution_history=self.evolution_history
            )
            
            if plan:
                self.coordinated_mutation_plan = plan
                self.coordinated_mutation_active = True
                logger.info("Coordinated mutation plan generated: %s", plan)
                
                # Add high-priority goals for the coordinated mutations
                for mutation_step in plan.get("mutation_steps", []):
                    subsystem = mutation_step.get("subsystem")
                    priority = mutation_step.get("priority", 1)  # High priority for coordinated mutations
                    description = mutation_step.get("description", f"Coordinated mutation for {subsystem}")
                    
                    if subsystem and subsystem in self.subsystem_scores:
                        self.add_goal(
                            priority=priority,
                            goal_description=description,
                            subsystem=subsystem
                        )
                
                logger.info("Added %d coordinated mutation goals to the queue", 
                          len(plan.get("mutation_steps", [])))
            else:
                logger.warning("Coordinated planner returned no plan. Falling back to normal operation.")
                self.coordinated_mutation_active = False
                self.coordinated_mutation_plan = None
                
        except Exception as e:
            logger.exception("Error during coordinated planning: %s", e)
            self.coordinated_mutation_active = False
            self.coordinated_mutation_plan = None

    def _update_coordinated_mutation_status(self, subsystem_name: str, success: bool):
        """Update the status of the coordinated mutation plan after a mutation cycle.

        Args:
            subsystem_name: The subsystem that was mutated.
            success: Whether the mutation was successful.
        """
        if not self.coordinated_mutation_active or not self.coordinated_mutation_plan:
            return
        
        # Update the plan with the result of this mutation
        mutation