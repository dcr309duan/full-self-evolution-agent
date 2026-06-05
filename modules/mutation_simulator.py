"""
Mutation Simulator - Coordinated Mutation Simulation

This module extends basic mutation simulation to support coordinated (bundled) mutations.
It allows accepting mutation bundles (list of (module, mutation) pairs), simulating all
mutations simultaneously in a sandbox, evaluating the combined fitness impact, and
reporting which individual mutations would have been rejected but succeed in combination.
"""

import copy
import random
from typing import List, Tuple, Any, Dict, Optional
from mutation_planner import MutationPlanner  # Assuming a base mutation planner exists

class MutationSimulator:
    """
    Simulates coordinated mutations by applying bundles of mutations simultaneously
    in a sandbox environment and evaluating their combined fitness impact.
    """

    def __init__(self, base_system: Any, fitness_function: callable):
        """
        Initialize the simulator with a base system and a fitness evaluation function.

        Args:
            base_system: The original system (e.g., a program, model, or configuration)
            fitness_function: A callable that takes a system and returns a fitness score
        """
        self.base_system = base_system
        self.fitness_function = fitness_function
        self.base_fitness = self.fitness_function(base_system)

    def simulate_bundle(self, mutation_bundle: List[Tuple[Any, callable]]) -> Dict[str, Any]:
        """
        Simulate a bundle of mutations applied simultaneously.

        Args:
            mutation_bundle: List of (module, mutation_function) pairs.
                             mutation_function takes a module and returns a mutated module.

        Returns:
            Dictionary with keys:
                - 'success': bool indicating if the bundle improved fitness
                - 'combined_fitness': fitness score after applying all mutations
                - 'fitness_delta': change in fitness from base
                - 'individual_results': list of dicts for each mutation applied individually
                - 'synergistic_mutations': list of mutations that would fail individually but succeed together
        """
        # Create a sandbox copy of the base system
        sandbox = copy.deepcopy(self.base_system)

        # Apply all mutations simultaneously
        for module, mutation_func in mutation_bundle:
            # Locate the module in the sandbox (assuming module is a key/path)
            target = self._get_module(sandbox, module)
            mutated = mutation_func(target)
            self._set_module(sandbox, module, mutated)

        # Evaluate combined fitness
        combined_fitness = self.fitness_function(sandbox)
        fitness_delta = combined_fitness - self.base_fitness
        success = fitness_delta > 0

        # Evaluate each mutation individually
        individual_results = []
        for module, mutation_func in mutation_bundle:
            individual_sandbox = copy.deepcopy(self.base_system)
            target = self._get_module(individual_sandbox, module)
            mutated = mutation_func(target)
            self._set_module(individual_sandbox, module, mutated)
            ind_fitness = self.fitness_function(individual_sandbox)
            ind_delta = ind_fitness - self.base_fitness
            individual_results.append({
                'module': module,
                'mutation': mutation_func,
                'fitness_delta': ind_delta,
                'success': ind_delta > 0
            })

        # Identify synergistic mutations (fail individually but succeed together)
        synergistic_mutations = []
        for i, ind_res in enumerate(individual_results):
            if not ind_res['success'] and success:
                synergistic_mutations.append(mutation_bundle[i])

        return {
            'success': success,
            'combined_fitness': combined_fitness,
            'fitness_delta': fitness_delta,
            'individual_results': individual_results,
            'synergistic_mutations': synergistic_mutations
        }

    def simulate_bundles(self, bundles: List[List[Tuple[Any, callable]]]) -> List[Dict[str, Any]]:
        """
        Simulate multiple mutation bundles.

        Args:
            bundles: List of mutation bundles

        Returns:
            List of result dictionaries
        """
        return [self.simulate_bundle(bundle) for bundle in bundles]

    def _get_module(self, system: Any, module_path: Any) -> Any:
        """
        Retrieve a module from the system by its path/key.
        Override this method for custom system structures.

        Args:
            system: The system object (e.g., dict, object)
            module_path: Identifier for the module (e.g., string key, attribute name)

        Returns:
            The module object
        """
        if isinstance(system, dict):
            return system.get(module_path)
        elif hasattr(system, module_path):
            return getattr(system, module_path)
        else:
            raise ValueError(f"Module path '{module_path}' not found in system")

    def _set_module(self, system: Any, module_path: Any, value: Any) -> None:
        """
        Set a module in the system by its path/key.
        Override this method for custom system structures.

        Args:
            system: The system object (e.g., dict, object)
            module_path: Identifier for the module (e.g., string key, attribute name)
            value: The new module value
        """
        if isinstance(system, dict):
            system[module_path] = value
        elif hasattr(system, module_path):
            setattr(system, module_path, value)
        else:
            raise ValueError(f"Module path '{module_path}' not found in system")


# Example usage (if run as script)
if __name__ == "__main__":
    # Dummy example: system as a dict with numeric modules
    base_system = {'a': 1, 'b': 2, 'c': 3}

    def fitness(system):
        # Simple fitness: sum of values
        return sum(system.values())

    def add_one(module):
        return module + 1

    def double(module):
        return module * 2

    simulator = MutationSimulator(base_system, fitness)

    # Bundle: mutate module 'a' by adding 1, and module 'b' by doubling
    bundle = [('a', add_one), ('b', double)]
    result = simulator.simulate_bundle(bundle)

    print("Base fitness:", simulator.base_fitness)
    print("Combined fitness:", result['combined_fitness'])
    print("Success:", result['success'])
    print("Synergistic mutations:", result['synergistic_mutations'])