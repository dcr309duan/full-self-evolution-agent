"""
evolution_engine.py - Main evolution engine with integrated meta-evaluation loop.
"""

import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum

# Import meta-evaluation components
from meta_evaluation_loop import MetaEvaluationLoop, EvolutionObjective, StagnationType

# Import mutation operators
from mutation_operators import (
    MutationOperator,
    AddCapabilityOperator,
    RefactorArchitectureOperator,
    DeleteDeadCodeOperator
)

# Import selection strategies
from selection_strategies import (
    SelectionStrategy,
    FitnessProportionalSelection,
    TournamentSelection,
    ElitistSelection
)

logger = logging.getLogger(__name__)


class EvolutionState(Enum):
    """Possible states of the evolution engine."""
    NORMAL = "normal"
    STAGNATION_DETECTED = "stagnation_detected"
    RECOVERY = "recovery"


@dataclass
class EvolutionConfig:
    """Configuration for the evolution engine."""
    population_size: int = 100
    mutation_rate: float = 0.1
    crossover_rate: float = 0.7
    max_generations: int = 1000
    stagnation_threshold: int = 10
    objective_switch_cooldown: int = 5


@dataclass
class EvolutionCycleResult:
    """Result of a single evolution cycle."""
    generation: int
    best_fitness: float
    average_fitness: float
    objective: EvolutionObjective
    stagnation_detected: bool
    operators_used: List[str]
    knowledge_added: Dict[str, Any]


class EvolutionEngine:
    """
    Main evolution engine with integrated meta-evaluation loop.
    Manages the evolutionary process and adapts strategies based on meta-evaluation feedback.
    """

    def __init__(self, config: Optional[EvolutionConfig] = None):
        """
        Initialize the evolution engine.

        Args:
            config: Configuration for the evolution engine. If None, uses defaults.
        """
        self.config = config or EvolutionConfig()
        self.meta_evaluator = MetaEvaluationLoop()
        self.population: List[Any] = []
        self.current_generation = 0
        self.state = EvolutionState.NORMAL
        self.current_objective = EvolutionObjective.IMPROVE_FITNESS
        self.objective_switch_counter = 0
        self.accumulated_knowledge: Dict[str, Any] = {}

        # Initialize mutation operators
        self.mutation_operators: Dict[str, MutationOperator] = {
            'add_capability': AddCapabilityOperator(),
            'refactor_architecture': RefactorArchitectureOperator(),
            'delete_dead_code': DeleteDeadCodeOperator()
        }

        # Initialize selection strategies
        self.selection_strategies: Dict[str, SelectionStrategy] = {
            'fitness_proportional': FitnessProportionalSelection(),
            'tournament': TournamentSelection(),
            'elitist': ElitistSelection()
        }

        # Track which operators are currently enabled
        self.enabled_operators: List[str] = ['add_capability', 'refactor_architecture', 'delete_dead_code']

        # History of evolution cycles
        self.cycle_history: List[EvolutionCycleResult] = []

    def initialize_population(self) -> None:
        """Initialize the population for evolution."""
        # Population initialization logic would go here
        # This is a placeholder for actual implementation
        self.population = []
        logger.info("Population initialized with size %d", self.config.population_size)

    def evaluate_fitness(self, individual: Any) -> float:
        """
        Evaluate the fitness of an individual.

        Args:
            individual: The individual to evaluate.

        Returns:
            Fitness score for the individual.
        """
        # Fitness evaluation logic would go here
        # This is a placeholder for actual implementation
        return 0.0

    def select_parents(self) -> List[Any]:
        """
        Select parents for reproduction based on current objective.

        Returns:
            List of selected parent individuals.
        """
        # Selection strategy is chosen based on current objective
        if self.current_objective == EvolutionObjective.IMPROVE_FITNESS:
            strategy = self.selection_strategies['fitness_proportional']
        elif self.current_objective == EvolutionObjective.INCREASE_DIVERSITY:
            strategy = self.selection_strategies['tournament']
        else:
            strategy = self.selection_strategies['elitist']

        return strategy.select(self.population, self.config.population_size // 2)

    def apply_mutation(self, individual: Any) -> Any:
        """
        Apply mutation operators to an individual.

        Args:
            individual: The individual to mutate.

        Returns:
            Mutated individual.
        """
        mutated = individual
        for operator_name in self.enabled_operators:
            if operator_name in self.mutation_operators:
                operator = self.mutation_operators[operator_name]
                mutated = operator.mutate(mutated, self.config.mutation_rate)
        return mutated

    def crossover(self, parent1: Any, parent2: Any) -> tuple:
        """
        Perform crossover between two parents.

        Args:
            parent1: First parent.
            parent2: Second parent.

        Returns:
            Tuple of two offspring individuals.
        """
        # Crossover logic would go here
        # This is a placeholder for actual implementation
        return parent1, parent2

    def update_operators_based_on_objective(self) -> None:
        """
        Update enabled mutation operators based on current objective.
        If stagnation is detected, disable 'add_capability' and enable
        'refactor_architecture' and 'delete_dead_code'.
        """
        if self.state == EvolutionState.STAGNATION_DETECTED:
            # Disable add_capability, enable refactoring and cleanup operators
            self.enabled_operators = ['refactor_architecture', 'delete_dead_code']
            logger.info("Stagnation detected: disabled 'add_capability', enabled 'refactor_architecture' and 'delete_dead_code'")
        else:
            # Normal operation - enable all operators
            self.enabled_operators = ['add_capability', 'refactor_architecture', 'delete_dead_code']

    def log_objective_switch(self, old_objective: EvolutionObjective, new_objective: EvolutionObjective) -> None:
        """
        Log an objective switch to accumulated knowledge.

        Args:
            old_objective: Previous evolution objective.
            new_objective: New evolution objective.
        """
        switch_entry = {
            'generation': self.current_generation,
            'old_objective': old_objective.value,
            'new_objective': new_objective.value,
            'state': self.state.value
        }

        if 'objective_switches' not in self.accumulated_knowledge:
            self.accumulated_knowledge['objective_switches'] = []

        self.accumulated_knowledge['objective_switches'].append(switch_entry)
        logger.info("Objective switch logged: %s -> %s at generation %d",
                    old_objective.value, new_objective.value, self.current_generation)

    def run_evolution_cycle(self) -> EvolutionCycleResult:
        """
        Run a single evolution cycle with integrated meta-evaluation.

        Returns:
            Result of the evolution cycle.
        """
        self.current_generation += 1

        # Evaluate fitness for all individuals
        fitness_scores = [self.evaluate_fitness(ind) for ind in self.population]

        # Calculate statistics
        best_fitness = max(fitness_scores) if fitness_scores else 0.0
        average_fitness = sum(fitness_scores) / len(fitness_scores) if fitness_scores else 0.0

        # Select parents and create new population
        parents = self.select_parents()
        new_population = []

        for i in range(0, len(parents) - 1, 2):
            parent1, parent2 = parents[i], parents[i + 1]
            offspring1, offspring2 = self.crossover(parent1, parent2)
            offspring1 = self.apply_mutation(offspring1)
            offspring2 = self.apply_mutation(offspring2)
            new_population.extend([offspring1, offspring2])

        self.population = new_population

        # --- Meta-evaluation integration ---
        # Analyze the current cycle using meta-evaluation loop
        analysis_result = self.meta_evaluator.analyze_cycle(
            generation=self.current_generation,
            best_fitness=best_fitness,
            average_fitness=average_fitness,
            population_diversity=self._calculate_diversity(),
            current_objective=self.current_objective
        )

        # Check for stagnation and update state
        if analysis_result.stagnation_detected:
            self.state = EvolutionState.STAGNATION_DETECTED
            logger.warning("Stagnation detected at generation %d: %s",
                          self.current_generation, analysis_result.stagnation_type.value)
        else:
            self.state = EvolutionState.NORMAL

        # Update operators based on current state
        self.update_operators_based_on_objective()

        # Handle objective switch with cooldown
        if analysis_result.suggested_objective != self.current_objective:
            if self.objective_switch_counter >= self.config.objective_switch_cooldown:
                old_objective = self.current_objective
                self.current_objective = analysis_result.suggested_objective
                self.log_objective_switch(old_objective, self.current_objective)
                self.objective_switch_counter = 0
            else:
                self.objective_switch_counter += 1
        else:
            self.objective_switch_counter = 0

        # Update accumulated knowledge
        if analysis_result.knowledge_updates:
            self.accumulated_knowledge.update(analysis_result.knowledge_updates)

        # Create cycle result
        cycle_result = EvolutionCycleResult(
            generation=self.current_generation,
            best_fitness=best_fitness,
            average_fitness=average_fitness,
            objective=self.current_objective,
            stagnation_detected=(self.state == EvolutionState.STAGNATION_DETECTED),
            operators_used=list(self.enabled_operators),
            knowledge_added=analysis_result.knowledge_updates
        )

        self.cycle_history.append(cycle_result)
        return cycle_result

    def _calculate_diversity(self) -> float:
        """
        Calculate the diversity of the current population.

        Returns:
            Diversity score between 0 and 1.
        """
        # Diversity calculation logic would go here
        # This is a placeholder for actual implementation
        return 0.5

    def run(self, generations: Optional[int] = None) -> List[EvolutionCycleResult]:
        """
        Run the evolution engine for a specified number of generations.

        Args:
            generations: Number of generations to run. If None, uses config value.

        Returns:
            List of cycle results for all generations.
        """
        num_generations = generations or self.config.max_generations
        self.initialize_population()

        results = []
        for _ in range(num_generations):
            cycle_result = self.run_evolution_cycle()
            results.append(cycle_result)

            # Early stopping if stagnation persists for too long
            if self.state == EvolutionState.STAGNATION_DETECTED:
                stagnation_count = sum(
                    1 for r in self.cycle_history[-self.config.stagnation_threshold:]
                    if r.stagnation_detected
                )
                if stagnation_count >= self.config.stagnation_threshold:
                    logger.info("Stagnation persisted for %d generations. Stopping evolution.",
                              self.config.stagnation_threshold)
                    break

        return results

    def get_accumulated_knowledge(self) -> Dict[str, Any]:
        """
        Get the accumulated knowledge from all evolution cycles.

        Returns:
            Dictionary containing accumulated knowledge.
        """
        return self.accumulated_knowledge

    def reset(self) -> None:
        """Reset the evolution engine to its initial state."""
        self.population = []
        self.current_generation = 0
        self.state = EvolutionState.NORMAL
        self.current_objective = EvolutionObjective.IMPROVE_FITNESS
        self.objective_switch_counter = 0
        self.accumulated_knowledge = {}
        self.cycle_history = []
        self.enabled_operators = ['add_capability', 'refactor_architecture', 'delete_dead_code']
        logger.info("Evolution engine reset to initial state")