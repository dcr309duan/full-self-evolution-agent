"""Evolution Engine - Integrates plasticity-stability scheduler into the evolution cycle."""

from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field
import random
import logging
from core.system_state import SystemState
from core.plasticity_stability_scheduler import PlasticityStabilityScheduler
from core.goal import Goal
from core.mutation import Mutation
from core.ecology_engine import EcologyEngine
from core.nash_detector import NashDetector
from core.coordinated_mutator import CoordinatedMutator
from core.consolidation_engine import ConsolidationEngine
from core.nash_detector_and_forcer import NashDetectorAndForcer


@dataclass
class EvolutionEngine:
    """Manages the evolution cycle with plasticity-stability scheduling and ecology integration."""
    
    system_state: SystemState
    scheduler: PlasticityStabilityScheduler
    ecology_engine: EcologyEngine
    nash_detector: NashDetector
    coordinated_mutator: CoordinatedMutator
    consolidation_engine: ConsolidationEngine
    nash_detector_and_forcer: NashDetectorAndForcer
    mutation_outcomes: List[Dict[str, Any]] = field(default_factory=list)
    consecutive_test_passes: int = 0
    nash_equilibrium_detected: bool = False
    nash_escape_attempts: int = 0
    consolidation_enabled: bool = True
    consolidation_threshold: int = 20
    archive_enabled: bool = True
    
    def __post_init__(self):
        """Initialize mutation outcomes tracking if not already present."""
        if not hasattr(self.system_state, 'mutation_outcomes'):
            self.system_state.mutation_outcomes = []
        self.logger = logging.getLogger(__name__)
        self._cycle_count = 0
    
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
        self.logger.info(
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
        self.logger.info(
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
    
    def _detect_and_escape_nash_equilibrium(self, goals: List[Goal]) -> bool:
        """Detect Nash equilibrium and attempt coordinated escape if detected.
        
        Args:
            goals: Current list of goals
            
        Returns:
            True if coordinated mutation was applied, False otherwise
        """
        # Run Nash detection
        equilibrium_detected = self.nash_detector.detect_equilibrium(goals)
        
        if equilibrium_detected:
            self.nash_equilibrium_detected = True
            self.nash_escape_attempts += 1
            
            self.logger.info(
                f"Nash equilibrium detected! Attempting coordinated escape "
                f"(attempt #{self.nash_escape_attempts})"
            )
            
            # Generate coordinated multi-module mutations
            coordinated_mutations = self.coordinated_mutator.generate_mutations(goals)
            
            if not coordinated_mutations:
                self.logger.warning("No coordinated mutations generated for Nash escape")
                return False
            
            # Test coordinated mutations in sandbox
            best_mutation = None
            best_fitness = float('-inf')
            
            for mutation in coordinated_mutations:
                # Apply mutation in sandbox (temporary copy)
                sandbox_goals = [goal.clone() for goal in goals]
                mutation.apply(sandbox_goals)
                
                # Evaluate fitness in sandbox
                fitness = self._evaluate_coordinated_fitness(sandbox_goals)
                
                if fitness > best_fitness:
                    best_fitness = fitness
                    best_mutation = mutation
            
            # Apply best-performing coordinated change
            if best_mutation is not None:
                best_mutation.apply(goals)
                self.logger.info(
                    f"Applied best coordinated mutation with fitness: {best_fitness:.4f}"
                )
                return True
            else:
                self.logger.warning("No suitable coordinated mutation found for Nash escape")
                return False
        
        self.nash_equilibrium_detected = False
        return False
    
    def _evaluate_coordinated_fitness(self, goals: List[Goal]) -> float:
        """Evaluate fitness of coordinated mutation in sandbox.
        
        Args:
            goals: Goals after coordinated mutation
            
        Returns:
            Fitness score (higher is better)
        """
        # Simple fitness evaluation based on goal feasibility and diversity
        total_feasibility = sum(goal.feasibility_score for goal in goals)
        diversity = len(set(goal.id for goal in goals))
        
        # Normalize and combine metrics
        avg_feasibility = total_feasibility / len(goals) if goals else 0
        diversity_score = diversity / (len(goals) + 1)  # Avoid division by zero
        
        return avg_feasibility * 0.7 + diversity_score * 0.3
    
    def _run_consolidation(self, goals: List[Goal]) -> None:
        """Run consolidation engine to scan, score, archive, and refactor modules.
        
        Args:
            goals: Current list of goals to evaluate
        """
        if not self.consolidation_enabled:
            self.logger.info("Consolidation disabled, skipping")
            return
        
        self.logger.info(
            f"Running consolidation cycle (threshold={self.consolidation_threshold}, "
            f"archive_enabled={self.archive_enabled})"
        )
        
        # Scan all modules and score them
        module_scores = self.consolidation_engine.score_modules(goals)
        
        # Log scores for each module
        for module_id, score in module_scores.items():
            self.logger.info(
                f"Consolidation scoring - Module {module_id}: score={score:.2f}, "
                f"threshold={self.consolidation_threshold}"
            )
        
        # Archive modules below threshold if enabled
        if self.archive_enabled:
            archived_modules = self.consolidation_engine.archive_modules(
                module_scores, 
                self.consolidation_threshold
            )
            if archived_modules:
                self.logger.info(
                    f"Consolidation archiving - Archived {len(archived_modules)} modules: "
                    f"{[m.id for m in archived_modules]}"
                )
            else:
                self.logger.info("Consolidation archiving - No modules archived")
        
        # Refactor core pathways
        refactored_pathways = self.consolidation_engine.refactor_core_pathways(goals)
        if refactored_pathways:
            self.logger.info(
                f"Consolidation refactoring - Refactored {len(refactored_pathways)} pathways: "
                f"{[p.id for p in refactored_pathways]}"
            )
        else:
            self.logger.info("Consolidation refactoring - No pathways refactored")
        
        # Log consolidation summary
        self.logger.info(
            f"Consolidation complete - Modules scored: {len(module_scores)}, "
            f"Archived: {len(archived_modules) if self.archive_enabled else 0}, "
            f"Pathways refactored: {len(refactored_pathways)}"
        )
    
    def _check_and_apply_nash_detector_and_forcer(self, goals: List[Goal]) -> bool:
        """Check for Nash equilibrium using nash_detector_and_forcer and apply forced multi-module changes if detected.
        
        This integrates the NashDetectorAndForcer into the evolution loop:
        (1) After each mutation cycle, call detector to check for equilibrium
        (2) If equilibrium detected, trigger forcer instead of normal single-module mutation
        (3) Log equilibrium events and forced multi-module changes to system state
        
        Args:
            goals: Current list of goals to check
            
        Returns:
            True if forced multi-module changes were applied, False otherwise
        """
        # Step 1: Call detector to check for equilibrium
        equilibrium_detected = self.nash_detector_and_forcer.detect_equilibrium(goals)
        
        if equilibrium_detected:
            self.logger.info(
                f"NashDetectorAndForcer: Equilibrium detected in system state. "
                f"Triggering forced multi-module changes."
            )
            
            # Step 2: Trigger forcer to apply multi-module changes
            forced_changes_applied = self.nash_detector_and_forcer.force_multi_module_changes(goals)
            
            # Step 3: Log equilibrium events and forced changes to system state
            equilibrium_event = {
                'type': 'nash_equilibrium_detected',
                'detector': 'nash_detector_and_forcer',
                'forced_changes_applied': forced_changes_applied,
                'cycle': self._cycle_count,
                'timestamp': self._get_timestamp()
            }
            
            if not hasattr(self.system_state, 'nash_equilibrium_events'):
                self.system_state.nash_equilibrium_events = []
            self.system_state.nash_equilibrium_events.append(equilibrium_event)
            
            if forced_changes_applied:
                forced_change_log = {
                    'type': 'forced_multi_module_changes',
                    'detector': 'nash_detector_and_forcer',
                    'cycle': self._cycle_count,
                    'timestamp': self._get_timestamp(),
                    'goals_affected': [goal.id for goal in goals]
                }
                if not hasattr(self.system_state, 'forced_changes_log'):
                    self.system_state.forced_changes_log = []
                self.system_state.forced_changes_log.append(forced_change_log)
                
                self.logger.info(
                    f"NashDetectorAndForcer: Forced multi-module changes applied successfully. "
                    f"Affected goals: {[goal.id for goal in goals]}"
                )
            else:
                self.logger.warning(
                    f"NashDetectorAndForcer: Equilibrium detected but forced changes could not be applied."
                )
            
            return forced_changes_applied
        
        return False
    
    def evolve(self, goals: List[Goal]) -> List[Goal]:
        """Execute one evolution cycle.
        
        Steps:
        1. Select a goal using current threshold
        2. Attempt mutation using current mutation rate
        3. Record outcome
        4. Evaluate and adjust scheduler parameters
        5. Check ecology engine and introduce pressure if needed
        6. Run Nash detection and attempt coordinated escape if equilibrium detected
        7. Run NashDetectorAndForcer check after mutation cycle
        8. Run consolidation every 5 cycles if enabled
        9. Log current meta-parameter state for continuous monitoring
        10. Log fitness landscape report
        
        Args:
            goals: Current list of goals to evolve
            
        Returns:
            Updated list of goals after evolution
        """
        self._cycle_count += 1
        
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
        
        # Run Nash detection and attempt coordinated escape if equilibrium detected
        nash_escape_applied = self._detect_and_escape_nash_equilibrium(goals)
        
        # Step 7: Run NashDetectorAndForcer check after mutation cycle
        nash_detector_and_forcer_applied = self._check_and_apply_nash_detector_and_forcer(goals)
        
        # Run consolidation every 5 cycles
        if self._cycle_count % 5 == 0:
            self._run_consolidation(goals)
        
        # Log meta-parameter state at the end of each evolution cycle
        self._log_meta_parameter_state()
        
        # Log fitness landscape report at the end of each cycle
        self._log_fitness_landscape_report(goals, ecology_changes_made)
        
        # Log Nash equilibrium events
        if self.nash_equilibrium_detected:
            self.logger.info(
                f"Nash equilibrium state: detected=True, "
                f"escape_attempts={self.nash_escape_attempts}, "
                f"escape_applied={nash_escape_applied}"
            )
        
        # Log NashDetectorAndForcer events
        if nash_detector_and_forcer_applied:
            self.logger.info(
                f"NashDetectorAndForcer: Forced multi-module changes applied during cycle {self._cycle_count}"
            )
        
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
        
        # Collect NashDetectorAndForcer statistics
        nash_detector_and_forcer_stats = {}
        if hasattr(self.system_state, 'nash_equilibrium_events'):
            nash_detector_and_forcer_stats['equilibrium_events'] = len(self.system_state.nash_equilibrium_events)
        if hasattr(self.system_state, 'forced_changes_log'):
            nash_detector_and_forcer_stats['forced_changes_applied'] = len(self.system_state.forced_changes_log)
        
        return {
            'total_mutation_attempts': total_attempts,
            'successful_mutations': successful,
            'success_rate': successful / total_attempts if total_attempts > 0 else 0.0,
            'current_mutation_rate': self.system_state.mutation_rate,
            'current_acceptance_threshold': self.system_state.goal_acceptance_threshold,
            'scheduler_state': self.scheduler.get_state(),
            'consecutive_test_passes': self.consecutive_test_passes,
            'ecology_engine_state': self.ecology_engine.get_state() if hasattr(self.ecology_engine, 'get_state') else {},
            'nash_equilibrium_detected': self.nash_equilibrium_detected,
            'nash_escape_attempts': self.nash_escape_attempts,
            'nash_detector_and_forcer_stats': nash_detector_and_forcer_stats,
            'consolidation_enabled': self.consolidation_enabled,
            'consolidation_threshold': self.consolidation_threshold,
            'archive_enabled': self.archive_enabled,
            'cycle_count': self._cycle_count
        }