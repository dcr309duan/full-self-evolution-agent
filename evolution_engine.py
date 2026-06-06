"""
evolution_engine.py - Main evolution engine with integrated meta-evaluation loop.
"""

import logging
import os
import ast
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

    def ecological_pressure(self) -> None:
        """
        Scan the current test suite files in tests/ directory, identify untested edge cases
        (empty inputs, boundary values, concurrent access, resource exhaustion), generate new
        test functions that test these edge cases, and write them to a new file
        tests/generated_ecology_tests.py with proper imports.
        """
        tests_dir = "tests"
        if not os.path.isdir(tests_dir):
            logger.warning("Tests directory '%s' does not exist. Skipping ecological pressure.", tests_dir)
            return

        # Scan all Python test files in the tests directory
        test_files = [f for f in os.listdir(tests_dir) if f.endswith('.py') and f != '__init__.py']
        if not test_files:
            logger.info("No test files found in '%s'. Skipping ecological pressure.", tests_dir)
            return

        # Analyze each test file for existing test functions and edge case coverage
        existing_tests = {}
        for test_file in test_files:
            filepath = os.path.join(tests_dir, test_file)
            try:
                with open(filepath, 'r') as f:
                    tree = ast.parse(f.read(), filename=filepath)
                test_functions = []
                for node in ast.walk(tree):
                    if isinstance(node, ast.FunctionDef) and node.name.startswith('test_'):
                        test_functions.append(node.name)
                existing_tests[test_file] = test_functions
            except (SyntaxError, IOError) as e:
                logger.warning("Could not parse test file '%s': %s", test_file, e)

        # Identify untested edge cases based on analysis of existing tests
        edge_cases_to_test = []
        edge_case_patterns = {
            'empty_input': ['test_empty', 'test_no_input', 'test_zero'],
            'boundary_value': ['test_boundary', 'test_edge', 'test_min', 'test_max'],
            'concurrent_access': ['test_concurrent', 'test_thread', 'test_parallel', 'test_race'],
            'resource_exhaustion': ['test_memory', 'test_timeout', 'test_exhaustion', 'test_overflow']
        }

        for test_file, test_funcs in existing_tests.items():
            for edge_type, patterns in edge_case_patterns.items():
                has_edge_test = any(
                    any(pattern in func_name for pattern in patterns)
                    for func_name in test_funcs
                )
                if not has_edge_test:
                    edge_cases_to_test.append((test_file, edge_type))

        if not edge_cases_to_test:
            logger.info("All edge cases appear to be covered. No new tests generated.")
            return

        # Generate new test functions for each missing edge case
        generated_tests = []
        for test_file, edge_type in edge_cases_to_test:
            test_module = test_file.replace('.py', '')
            test_func_name = f"test_{test_module}_{edge_type}"

            if edge_type == 'empty_input':
                test_body = f"""
    def {test_func_name}(self):
        \"\"\"Test {test_module} with empty input.\"\"\"
        # TODO: Implement actual test logic for {test_module}
        # This test verifies behavior when empty input is provided
        try:
            # Example: result = {test_module}.process_empty_input()
            pass
        except Exception as e:
            self.fail(f"Empty input handling failed: {{e}}")
"""
            elif edge_type == 'boundary_value':
                test_body = f"""
    def {test_func_name}(self):
        \"\"\"Test {test_module} with boundary values.\"\"\"
        # TODO: Implement actual test logic for {test_module}
        # This test verifies behavior at boundary conditions (min/max values)
        boundary_values = [0, 1, -1, 2**31 - 1, -2**31, float('inf'), float('-inf')]
        for value in boundary_values:
            try:
                # Example: result = {test_module}.process_boundary(value)
                pass
            except Exception as e:
                self.fail(f"Boundary value {{value}} failed: {{e}}")
"""
            elif edge_type == 'concurrent_access':
                test_body = f"""
    def {test_func_name}(self):
        \"\"\"Test {test_module} with concurrent access.\"\"\"
        # TODO: Implement actual test logic for {test_module}
        # This test verifies thread safety and concurrent access handling
        import threading
        errors = []
        def worker():
            try:
                # Example: result = {test_module}.concurrent_operation()
                pass
            except Exception as e:
                errors.append(e)
        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        if errors:
            self.fail(f"Concurrent access failed with errors: {{errors}}")
"""
            elif edge_type == 'resource_exhaustion':
                test_body = f"""
    def {test_func_name}(self):
        \"\"\"Test {test_module} with resource exhaustion.\"\"\"
        # TODO: Implement actual test logic for {test_module}
        # This test verifies behavior under resource exhaustion (memory, timeout)
        import signal
        class TimeoutError(Exception):
            pass
        def handler(signum, frame):
            raise TimeoutError("Operation timed out")
        signal.signal(signal.SIGALRM, handler)
        signal.alarm(5)  # 5 second timeout
        try:
            # Example: result = {test_module}.exhaustive_operation()
            pass
        except TimeoutError:
            pass  # Expected timeout
        except Exception as e:
            self.fail(f"Resource exhaustion handling failed: {{e}}")
        finally:
            signal.alarm(0)
"""
            else:
                continue

            generated_tests.append(test_body)

        if not generated_tests:
            logger.info("No new edge case tests to generate.")
            return

        # Write generated tests to tests/generated_ecology_tests.py
        output_file = os.path.join(tests_dir, "generated_ecology_tests.py")
        try:
            with open(output_file, 'w') as f:
                f.write('"""\n')
                f.write('Auto-generated ecology tests for edge case coverage.\n')
                f.write('Generated by EvolutionEngine.ecological_pressure()\n')
                f.write('"""\n\n')
                f.write('import unittest\n')
                f.write('import sys\n')
                f.write('import os\n\n')
                f.write('sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))\n\n\n')
                f.write('class GeneratedEcologyTests(unittest.TestCase):\n')
                f.write('    """Test suite for edge cases identified by ecological pressure."""\n\n')
                for test_body in generated_tests:
                    f.write(test_body)
                    f.write('\n')
                f.write('\nif __name__ == "__main__":\n')
                f.write('    unittest.main()\n')

            logger.info("Generated ecology tests written to '%s' with %d test functions.",
                       output_file, len(generated_tests))
        except IOError as e:
            logger.error("Failed to write generated tests to '%s': %s", output_file, e)