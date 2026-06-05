from collections import defaultdict
from typing import Dict, List, Tuple, Set, Optional

class NashDetector:
    """
    Analyzes inter-module data flows and detects Nash equilibrium conditions
    where no single-module mutation improves overall system fitness.
    """

    def __init__(self):
        # Dependency graph: module -> set of modules that depend on its outputs
        self.dependency_graph: Dict[str, Set[str]] = defaultdict(set)
        # Reverse dependency: module -> set of modules it depends on
        self.reverse_dependency: Dict[str, Set[str]] = defaultdict(set)
        # Module outputs -> list of input modules that consume them
        self.output_to_inputs: Dict[str, Set[str]] = defaultdict(set)
        # Fitness delta history per module: module -> list of recent deltas
        self.fitness_deltas: Dict[str, List[float]] = defaultdict(list)
        # Consecutive non-improvement counter per module
        self.stagnation_counter: Dict[str, int] = defaultdict(int)
        # Threshold for consecutive non-improvement cycles
        self.stagnation_threshold: int = 3
        # Current cycle number
        self.current_cycle: int = 0

    def register_data_flow(self, source_module: str, target_module: str) -> None:
        """
        Register a data flow from source_module's output to target_module's input.
        
        Args:
            source_module: The module producing output
            target_module: The module consuming the output as input
        """
        self.dependency_graph[source_module].add(target_module)
        self.reverse_dependency[target_module].add(source_module)
        self.output_to_inputs[source_module].add(target_module)

    def register_module_output(self, module: str, output_name: str) -> None:
        """
        Register that a module produces a specific output.
        This is a placeholder for more detailed output tracking.
        
        Args:
            module: The module name
            output_name: The name of the output produced
        """
        # In a full implementation, this would track specific output names
        pass

    def register_module_input(self, module: str, input_name: str, source_module: str) -> None:
        """
        Register that a module consumes input from another module.
        
        Args:
            module: The consuming module
            input_name: The name of the input
            source_module: The module providing this input
        """
        self.register_data_flow(source_module, module)

    def record_fitness_delta(self, module: str, delta: float) -> None:
        """
        Record the fitness delta resulting from a mutation of the given module.
        
        Args:
            module: The module that was mutated
            delta: The change in system fitness (positive = improvement)
        """
        self.fitness_deltas[module].append(delta)
        
        # Update stagnation counter
        if delta <= 0:
            self.stagnation_counter[module] += 1
        else:
            self.stagnation_counter[module] = 0

    def get_dependent_modules(self, module: str) -> Set[str]:
        """
        Get all modules that directly depend on this module's outputs.
        
        Args:
            module: The module to query
            
        Returns:
            Set of module names that depend on this module
        """
        return self.dependency_graph.get(module, set()).copy()

    def get_dependencies(self, module: str) -> Set[str]:
        """
        Get all modules that this module directly depends on.
        
        Args:
            module: The module to query
            
        Returns:
            Set of module names that this module depends on
        """
        return self.reverse_dependency.get(module, set()).copy()

    def get_all_downstream_modules(self, module: str) -> Set[str]:
        """
        Get all modules that are downstream (directly or indirectly) from this module.
        
        Args:
            module: The starting module
            
        Returns:
            Set of all downstream module names
        """
        visited = set()
        to_visit = {module}
        
        while to_visit:
            current = to_visit.pop()
            if current in visited:
                continue
            visited.add(current)
            downstream = self.dependency_graph.get(current, set())
            to_visit.update(downstream - visited)
        
        visited.discard(module)
        return visited

    def is_module_stagnant(self, module: str) -> bool:
        """
        Check if a specific module has reached stagnation (no improvement).
        
        Args:
            module: The module to check
            
        Returns:
            True if module has no improvement for threshold cycles
        """
        return self.stagnation_counter.get(module, 0) >= self.stagnation_threshold

    def get_stagnant_modules(self) -> List[str]:
        """
        Get all modules that are currently stagnant.
        
        Returns:
            List of stagnant module names
        """
        return [
            module for module, count in self.stagnation_counter.items()
            if count >= self.stagnation_threshold
        ]

    def is_nash_equilibrium(self) -> bool:
        """
        Check if the system has reached a Nash equilibrium state.
        This occurs when ALL modules have no single-module mutation
        that improves fitness for the threshold number of consecutive cycles.
        
        Returns:
            True if system is in Nash equilibrium
        """
        if not self.fitness_deltas:
            return False
        
        # Check if all modules that have been mutated are stagnant
        all_modules = set(self.fitness_deltas.keys())
        stagnant_modules = set(self.get_stagnant_modules())
        
        # Only consider modules that have been evaluated
        evaluated_modules = {
            module for module, deltas in self.fitness_deltas.items()
            if len(deltas) >= self.stagnation_threshold
        }
        
        if not evaluated_modules:
            return False
        
        return evaluated_modules.issubset(stagnant_modules)

    def get_system_analysis(self) -> Dict:
        """
        Get a comprehensive analysis of the current system state.
        
        Returns:
            Dictionary containing:
            - 'nash_equilibrium': bool
            - 'stagnant_modules': list of module names
            - 'dependency_graph': dict of module dependencies
            - 'fitness_summary': dict of module fitness trends
            - 'cycle_count': int
        """
        return {
            'nash_equilibrium': self.is_nash_equilibrium(),
            'stagnant_modules': self.get_stagnant_modules(),
            'dependency_graph': {
                module: list(deps) 
                for module, deps in self.dependency_graph.items()
            },
            'fitness_summary': {
                module: {
                    'recent_deltas': deltas[-5:],
                    'average_delta': sum(deltas[-5:]) / max(len(deltas[-5:]), 1),
                    'stagnant': self.is_module_stagnant(module)
                }
                for module, deltas in self.fitness_deltas.items()
            },
            'cycle_count': self.current_cycle
        }

    def increment_cycle(self) -> None:
        """Advance to the next evaluation cycle."""
        self.current_cycle += 1

    def reset_module(self, module: str) -> None:
        """
        Reset stagnation tracking for a specific module.
        Useful when a module is significantly restructured.
        
        Args:
            module: The module to reset
        """
        self.stagnation_counter[module] = 0
        self.fitness_deltas[module] = []

    def reset_all(self) -> None:
        """Reset all tracking data."""
        self.dependency_graph.clear()
        self.reverse_dependency.clear()
        self.output_to_inputs.clear()
        self.fitness_deltas.clear()
        self.stagnation_counter.clear()
        self.current_cycle = 0

    def set_stagnation_threshold(self, threshold: int) -> None:
        """
        Set the number of consecutive non-improvement cycles required for stagnation.
        
        Args:
            threshold: Number of cycles (must be positive)
        """
        if threshold < 1:
            raise ValueError("Stagnation threshold must be at least 1")
        self.stagnation_threshold = threshold