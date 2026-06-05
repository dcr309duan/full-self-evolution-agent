"""Evolution Engine - Integrates plasticity-stability scheduler into the evolution cycle."""

from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field
import random
from core.system_state import SystemState
from core.plasticity_stability_scheduler import PlasticityStabilityScheduler
from core.goal import Goal
from core.mutation import Mutation
from core.ecology_engine import EcologyEngine


@dataclass
class EvolutionEngine:
    """Manages the evolution cycle with plasticity-stability scheduling and ecology integration."""
    
    system_state: SystemState
    scheduler: PlasticityStabilityScheduler
    ecology_engine: EcologyEngine
    mutation_outcomes: List[Dict[str, Any]] = field(default_factory=list)
    consecutive_test_passes: int = 0
    
    def __post_init__(self):
        """Initialize mutation outcomes tracking if not already present."""
        if not hasattr(self.system_state, 'mutation_outcomes'):
            self.system_state.mutation_outcomes = []
    
    def select_goal(self, goals: List[Goal]) -> Optional[Goal]:
        """Select a goal based on feasibility threshold from system state.
        
        Filters out goals whose feasibility score is below the current
        goal_acceptance_threshold.
        
        Args:
            goals: List of available goals
            
        Returns:
            Selected goal or None if no suitable goal exists
        """
        threshold = self.system_state.goal_acceptance_threshold
        
        # Filter goals by feasibility threshold
        eligible_goals = [
            goal for goal in goals 
            if goal.feasibility_score >= threshold
        ]
        
        if not eligible_goals:
            return None
        
        # Select from eligible goals (can be extended with more sophisticated selection)
        return random.choice(eligible_goals)
    
    def apply_mutation(self, goal: Goal) -> bool:
        """Apply a mutation to a goal and record the outcome.
        
        Uses the current mutation_rate from system_state to determine
        mutation probability.
        
        Args:
            goal: The goal to mutate
            
        Returns:
            True if mutation was successful, False otherwise
        """
        mutation_rate = self.system_state.mutation_rate
        
        # Determine if mutation occurs based on current rate
        if random.random() > mutation_rate:
            return False
        
        # Create and apply mutation
        mutation = Mutation(goal)
        success = mutation.apply()
        
        # Record outcome
        outcome = {
            'goal_id': goal.id,
            'success': success,
            'mutation_rate': mutation_rate,
            'timestamp': self._get_timestamp()
        }
        self.mutation_outcomes.append(outcome)
        self.system_state.mutation_outcomes.append(outcome)
        
        return success
    
    def _get_timestamp(self) -> float:
        """Get current timestamp for recording outcomes."""
        import time
        return time.time()
    
    def _log_meta_parameter_state(self) -> None:
        """Log the current meta-parameter state for continuous monitoring."""
        import logging
        logger = logging.getLogger(__name__)
        logger.info(
            f"Meta-parameter state - mutation_rate: {self.system_state.mutation_rate:.4f}, "
            f"goal_acceptance_threshold: {self.system_state.goal_acceptance_threshold:.4f}"
        )
    
    def _log_fitness_landscape_report(self, goals: List[Goal], ecology_changes_made: bool) -> None:
        """Log a fitness landscape report at the end of each cycle.
        
        Reports: number of tests, pass rate, difficulty distribution, and whether
        the ecology engine made any changes.
        
        Args:
            goals: Current list of goals
            ecology_changes_made: Whether ecology engine made changes this cycle
        """
        import logging
        logger = logging.getLogger(__name__)
        
        # Count tests and passes
        total_tests = len(goals)
        passed_tests = sum(1 for goal in goals if hasattr(goal, 'passed') and goal.passed)
        pass_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0.0
        
        # Calculate difficulty distribution
        difficulty_distribution = {}
        for goal in goals:
            difficulty = getattr(goal, 'difficulty', 'unknown')
            difficulty_distribution[difficulty] = difficulty_distribution.get(difficulty, 0) + 1
        
        # Log the report
        logger.info(
            f"Fitness Landscape Report - "
            f"Total Tests: {total_tests}, "
            f"Pass Rate: {pass_rate:.1f}%, "
            f"Difficulty Distribution: {difficulty_distribution}, "
            f"Ecology Changes: {ecology_changes_made}"
        )
    
    def _check_and_apply_ecology_pressure(self, goals: List[Goal]) -> bool:
        """Check if ecology engine should introduce new pressure.
        
        Evaluates fitness landscape and triggers new pressure if agent
        has passed all tests for 3+ consecutive cycles.
        
        Args:
            goals: Current list of goals
            
        Returns:
            True if ecology engine made changes, False otherwise
        """
        # Evaluate fitness landscape
        landscape = self.ecology_engine.evaluate_fitness_landscape(goals)
        
        # Check if all tests passed
        all_tests_passed = landscape.get('all_tests_passed', False)
        
        if all_tests_passed:
            self.consecutive_test_passes += 1
        else:
            self.consecutive_test_passes = 0
        
        # Trigger new pressure if 3+ consecutive passes
        if self.consecutive_test_passes >= 3:
            self.ecology_engine.introduce_new_pressure(goals)
            self.consecutive_test_passes = 0  # Reset counter after introducing pressure
            return True
        
        return False
    
    def evolve(self, goals: List[Goal]) -> List[Goal]:
        """Execute one evolution cycle.
        
        Steps:
        1. Select a goal using current threshold
        2. Attempt mutation using current mutation rate
        3. Record outcome
        4. Evaluate and adjust scheduler parameters
        5. Check ecology engine and introduce pressure if needed
        6. Log current meta-parameter state for continuous monitoring
        7. Log fitness landscape report
        
        Args:
            goals: Current list of goals to evolve
            
        Returns:
            Updated list of goals after evolution
        """
        # Select goal
        selected_goal = self.select_goal(goals)
        if selected_goal is None:
            # Log meta-parameter state even when no goal is selected
            self._log_meta_parameter_state()
            # Log fitness landscape report even when no goal is selected
            self._log_fitness_landscape_report(goals, False)
            return goals
        
        # Apply mutation
        mutation_success = self.apply_mutation(selected_goal)
        
        # Evaluate and adjust scheduler
        self.scheduler.evaluate_and_adjust()
        
        # Update system state with current scheduler parameters
        self.system_state.mutation_rate = self.scheduler.current_mutation_rate
        self.system_state.goal_acceptance_threshold = self.scheduler.current_acceptance_threshold
        
        # Check ecology engine and introduce pressure if needed
        ecology_changes_made = self._check_and_apply_ecology_pressure(goals)
        
        # Log meta-parameter state at the end of each evolution cycle
        self._log_meta_parameter_state()
        
        # Log fitness landscape report at the end of each cycle
        self._log_fitness_landscape_report(goals, ecology_changes_made)
        
        return goals
    
    def run_evolution_cycle(self, goals: List[Goal], num_iterations: int = 1) -> List[Goal]:
        """Run multiple evolution cycles.
        
        Args:
            goals: Initial list of goals
            num_iterations: Number of evolution cycles to run
            
        Returns:
            Final list of goals after all cycles
        """
        current_goals = goals.copy()
        
        for _ in range(num_iterations):
            current_goals = self.evolve(current_goals)
        
        return current_goals
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get evolution statistics for monitoring.
        
        Returns:
            Dictionary with evolution statistics
        """
        total_attempts = len(self.mutation_outcomes)
        successful = sum(1 for o in self.mutation_outcomes if o['success'])
        
        return {
            'total_mutation_attempts': total_attempts,
            'successful_mutations': successful,
            'success_rate': successful / total_attempts if total_attempts > 0 else 0.0,
            'current_mutation_rate': self.system_state.mutation_rate,
            'current_acceptance_threshold': self.system_state.goal_acceptance_threshold,
            'scheduler_state': self.scheduler.get_state(),
            'consecutive_test_passes': self.consecutive_test_passes,
            'ecology_engine_state': self.ecology_engine.get_state() if hasattr(self.ecology_engine, 'get_state') else {}
        }