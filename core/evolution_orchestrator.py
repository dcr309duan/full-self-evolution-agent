"""evolution_orchestrator.py

Main orchestrator for the self-evolving system. Initializes all subsystems and runs a
continuous evolution loop that scores, selects, mutates, tests, and evaluates each subsystem.
Includes a goal_selection mechanism that maintains a priority queue of evolution goals.
Integrates reflection parsing to close the feedback loop between mutation outcomes and strategy selection.
Includes a 'fitness landscape mutation' phase that runs every 3 cycles to generate new tests targeting weak areas.
Includes meta_goal_generator integration that analyzes statistics every 10 cycles and injects disruptive goals.
Includes a 50-cycle trigger that reads orchestrator state to find clean integration points for targeted evolution.
Includes Nash equilibrium detection and coordinated mutation after each evolution cycle.
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
from reflection_parser import ReflectionParser  # New import for reflection parsing
from meta_goal_generator import MetaGoalGenerator  # Import for meta goal generation

# Import guard for Nash equilibrium integration modules
try:
    from nash_detector import NashDetector
    NASH_DETECTOR_AVAILABLE = True
except ImportError:
    NashDetector = None
    NASH_DETECTOR_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.warning("nash_detector module not available; Nash equilibrium detection disabled")

try:
    from multi_module_forcer import MultiModuleForcer
    MULTI_MODULE_FORCER_AVAILABLE = True
except ImportError:
    MultiModuleForcer = None
    MULTI_MODULE_FORCER_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.warning("multi_module_forcer module not available; coordinated forcing disabled")

try:
    from coordinated_mutation_runner import CoordinatedMutationRunner
    COORDINATED_MUTATION_RUNNER_AVAILABLE = True
except ImportError:
    CoordinatedMutationRunner = None
    COORDINATED_MUTATION_RUNNER_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.warning("coordinated_mutation_runner module not available; coordinated mutation runner disabled")

logger = logging.getLogger(__name__)

# Configuration for failure threshold and strategy switch
FAILURE_THRESHOLD = 3  # Number of consecutive failures before triggering strategy switch
EVOLUTION_INTERVAL = 60.0  # Default interval between evolution cycles in seconds
STATE_FILE = "orchestrator_state.json"  # File to persist orchestrator state
LOG_FILE = "evolution_log.json"  # File to log evolution cycles
REFLECTION_LOG_FILE = "reflection_log.json"  # File to log reflection data
FITNESS_LANDSCAPE_INTERVAL = 3  # Number of cycles between fitness landscape mutation phases
META_GOAL_INTERVAL = 10  # Number of cycles between meta goal generator analyses
FIFTY_CYCLE_TRIGGER_INTERVAL = 50  # Number of cycles between 50-cycle trigger analyses


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
        self.reflection_parser = ReflectionParser(self.config.get("reflection_parser", {}))  # New subsystem
        self.meta_goal_generator = MetaGoalGenerator(self.config.get("meta_goal_generator", {}))  # Meta goal generator

        # Initialize Nash equilibrium integration modules if available
        self.nash_detector = None
        self.multi_module_forcer = None
        self.coordinated_mutation_runner = None
        
        if NASH_DETECTOR_AVAILABLE:
            try:
                self.nash_detector = NashDetector(self.config.get("nash_detector", {}))
                logger.info("NashDetector initialized successfully")
            except Exception as e:
                logger.error("Failed to initialize NashDetector: %s", e)
                self.nash_detector = None
        
        if MULTI_MODULE_FORCER_AVAILABLE:
            try:
                self.multi_module_forcer = MultiModuleForcer(self.config.get("multi_module_forcer", {}))
                logger.info("MultiModuleForcer initialized successfully")
            except Exception as e:
                logger.error("Failed to initialize MultiModuleForcer: %s", e)
                self.multi_module_forcer = None
        
        if COORDINATED_MUTATION_RUNNER_AVAILABLE:
            try:
                self.coordinated_mutation_runner = CoordinatedMutationRunner(self.config.get("coordinated_mutation_runner", {}))
                logger.info("CoordinatedMutationRunner initialized successfully")
            except Exception as e:
                logger.error("Failed to initialize CoordinatedMutationRunner: %s", e)
                self.coordinated_mutation_runner = None

        # Subsystem health / performance scores (0.0 = worst, 1.0 = best)
        self.subsystem_scores: Dict[str, float] = {
            "api_server": 1.0,
            "task_scheduler": 1.0,
            "web_scraper": 1.0,
            "mutation_engine": 1.0,
            "testing_framework": 1.0,
            "failure_analysis": 1.0,
            "meta_evaluation": 1.0,
            "reflection_parser": 1.0,  # Added reflection_parser score
        }

        # Count consecutive failures per subsystem
        self.consecutive_failures: Dict[str, int] = {name: 0 for name in self.subsystem_scores}

        # History log
        self.evolution_history: list = []

        # Control flag
        self.running = False

        # Cycle counter for fitness landscape mutation and meta goal generation
        self.cycle_count = 0

        # Mapping of subsystem names to their source file paths
        self.subsystem_source_paths: Dict[str, str] = {
            "api_server": "api_server.py",
            "task_scheduler": "task_scheduler.py",
            "web_scraper": "web_scraper.py",
            "mutation_engine": "mutation_engine.py",
            "testing_framework": "testing_framework.py",
            "failure_analysis": "failure_analysis.py",
            "meta_evaluation": "meta_evaluation.py",
            "reflection_parser": "reflection_parser.py",  # Added reflection_parser path
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
            "reflection_parser": self.reflection_parser,  # Added reflection_parser instance
        }

        # Goal selection mechanism: priority queue of evolution goals
        # Each goal is a tuple: (priority, timestamp, goal_description, subsystem_mapping)
        # Lower priority value = higher priority (standard heapq behavior)
        self.goal_queue: List[Tuple[int, float, str, str]] = []
        self._initialize_goal_queue()

        # Multi-mutation mode flag: when True, overrides normal single-mutation selection
        self.multi_mutation_mode = False

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
            (8, time.time(), "improve reflection parsing", "reflection_parser"),  # Added reflection_parser goal
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
        scores["reflection_parser"] = self.reflection_parser.get_health_score()  # Added reflection_parser score

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
            "reflection_parser": self.reflection_parser,  # Added reflection_parser
        }

        target = subsystem_map.get(subsystem_name)
        if target is None:
            logger.error("Unknown subsystem: %s", subsystem_name)
            return False

        logger.info("Evolving subsystem '%s'...", subsystem_name)
        try:
            # Pass failure_pattern_learner reference to mutation_engine during evolution
            success = self.mutation_engine.evolve(target, failure_pattern_learner=self.failure_analysis)
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
            "cycle_count": self.cycle_count,
            "multi_mutation_mode": self.multi_mutation_mode,
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
            
            # Restore cycle count
            if "cycle_count" in state:
                self.cycle_count = state["cycle_count"]
                logger.info("Restored cycle count to %d from saved state", self.cycle_count)
            
            # Restore multi_mutation_mode
            if "multi_mutation_mode" in state:
                self.multi_mutation_mode = state["multi_mutation_mode"]
                logger.info("Restored multi_mutation_mode to %s from saved state", self.multi_mutation_mode)
            
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

    def _run_sandboxed_mutation(self, subsystem_name: str, source_code: str, strategy: str) -> Tuple[Optional[str], bool, Optional[str]]:
        """Run mutation in a sandboxed pipeline and test it.

        Args:
            subsystem_name: Name of the subsystem to mutate.
            source_code: The source code to mutate.
            strategy: The mutation strategy to use.

        Returns:
            Tuple of (mutated_code, sandbox_test_passed, failure_report_path)
            - mutated_code: The mutated source code, or None if mutation failed
            - sandbox_test_passed: Whether the sandbox tests passed
            - failure_report_path: Path to the failure report if tests failed, None otherwise
        """
        logger.info("Running sandboxed mutation for subsystem '%s' with strategy '%s'", subsystem_name, strategy)
        
        try:
            # Use the mutation engine to generate mutated code in sandbox
            mutated_code = self.mutation_engine.evolve_subsystem(source_code, strategy=strategy, sandbox=True)
            
            if mutated_code is None:
                logger.error("Sandboxed mutation returned None for subsystem '%s'", subsystem_name)
                return None, False, None
            
            # Run tests in sandbox environment
            sandbox_test_passed = self.testing_framework.run_tests(subsystem_name, sandbox=True)
            
            failure_report_path = None
            if not sandbox_test_passed:
                # Generate failure report
                failure_report_path = f"failure_reports/{subsystem_name}_{int(time.time())}.json"
                os.makedirs("failure_reports", exist_ok=True)
                
                failure_report = {
                    "timestamp": time.time(),
                    "subsystem": subsystem_name,
                    "strategy": strategy,
                    "mutated_code": mutated_code,
                    "error_details": self.testing_framework.get_last_error_details()
                }
                
                with open(failure_report_path, 'w') as f:
                    json.dump(failure_report, f, indent=2)
                
                logger.info("Failure report saved to %s", failure_report_path)
            
            return mutated_code, sandbox_test_passed, failure_report_path
            
        except Exception as e:
            logger.exception("Error during sandboxed mutation for subsystem '%s': %s", subsystem_name, e)
            return None, False, None

    def _run_fitness_landscape_mutation(self):
        """Run the fitness landscape mutation phase to generate new tests targeting weak areas.
        
        This method is called every FITNESS_LANDSCAPE_INTERVAL cycles. It analyzes failure patterns
        and subsystem scores to identify weak areas, then generates 1-3 new tests that target those
        areas or introduce novel constraints. These tests become part of the permanent test suite.
        """
        logger.info("Running fitness landscape mutation phase (cycle %d)", self.cycle_count)
        
        try:
            # Identify weak areas based on failure patterns and low scores
            weak_areas = []
            for subsystem_name, score in self.subsystem_scores.items():
                failures = self.consecutive_failures.get(subsystem_name, 0)
                if score < 0.5 or failures >= FAILURE_THRESHOLD:
                    weak_areas.append({
                        "subsystem": subsystem_name,
                        "score": score,
                        "failures": failures,
                        "failure_pattern": self.failure_analysis.get_failure_pattern(subsystem_name)
                    })
            
            # If no weak areas found, target the lowest scoring subsystem
            if not weak_areas:
                lowest_subsystem = min(self.subsystem_scores, key=self.subsystem_scores.get)
                weak_areas.append({
                    "subsystem": lowest_subsystem,
                    "score": self.subsystem_scores[lowest_subsystem],
                    "failures": self.consecutive_failures.get(lowest_subsystem, 0),
                    "failure_pattern": self.failure_analysis.get_failure_pattern(lowest_subsystem)
                })
            
            # Generate 1-3 new tests based on weak areas
            num_tests = min(len(weak_areas), 3)
            if num_tests < 1:
                num_tests = 1
            
            for i in range(num_tests):
                weak_area = weak_areas[i % len(weak_areas)]
                subsystem_name = weak_area["subsystem"]
                failure_pattern = weak_area.get("failure_pattern", {})
                
                # Determine test type based on failure pattern
                test_type = "standard"
                if failure_pattern:
                    # If there are performance failures, create performance limit tests
                    if "performance" in str(failure_pattern).lower():
                        test_type = "performance"
                    # If there are input format failures, create new input format tests
                    elif "input" in str(failure_pattern).lower() or "format" in str(failure_pattern).lower():
                        test_type = "input_format"
                    # If there are adversarial failures, create adversarial tests
                    elif "adversarial" in str(failure_pattern).lower() or "security" in str(failure_pattern).lower():
                        test_type = "adversarial"
                
                # Generate the test using the testing framework
                new_test = self.testing_framework.generate_test(
                    subsystem=subsystem_name,
                    test_type=test_type,
                    failure_pattern=failure_pattern
                )
                
                if new_test:
                    # Add the test to the permanent test suite
                    self.testing_framework.add_permanent_test(new_test)
                    logger.info("Added new %s test for subsystem '%s' to permanent test suite", 
                              test_type, subsystem_name)
                    
                    # Log the new test generation
                    log_entry = {
                        "timestamp": time.time(),
                        "phase": "fitness_landscape_mutation",
                        "subsystem": subsystem_name,
                        "test_type": test_type,
                        "test_details": new_test,
                        "weak_area_info": weak_area
                    }
                    
                    try:
                        with open("fitness_landscape_log.json", 'a') as f:
                            f.write(json.dumps(log_entry) + '\n')
                    except Exception as e:
                        logger.error("Failed to log fitness landscape mutation: %s", e)
                else:
                    logger.warning("Failed to generate new test for subsystem '%s'", subsystem_name)
            
            logger.info("Fitness landscape mutation phase completed with %d new tests generated", num_tests)
            
        except Exception as e:
            logger