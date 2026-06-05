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
        # Fitness delta history per module pair: (module1, module2) -> list of recent deltas
        self.fitness_deltas: Dict[Tuple[str, str], List[float]] = defaultdict(list)
        # Consecutive non-improvement counter per module pair
        self.stagnation_counter: Dict[Tuple[str, str], int] = defaultdict(int)
        # Threshold for consecutive non-improvement cycles
        self.stagnation_threshold: int = 5
        # Current cycle number
        self.current_cycle: int = 0
        # Maximum history length per module pair
        self.max_history_length: int = 10
        # Stagnation scores per module pair (0-1)
        self.stagnation_scores: Dict[Tuple[str, str], float] = defaultdict(float)
        # History of last 5 cycles' mutation outcomes: list of booleans (True if any improvement)
        self._cycle_improvement_history: List[bool] = []
        # Module interaction matrix: module -> dict of module -> interaction strength
        self._module_interaction_matrix: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))

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
        For Nash equilibrium detection, we track deltas per module pair.
        
        Args:
            module: The module that was mutated
            delta: The change in system fitness (positive = improvement)
        """
        # Get all module pairs involving this module
        module_pairs = self._get_module_pairs(module)
        
        for pair in module_pairs:
            self.fitness_deltas[pair].append(delta)
            
            # Keep only last 10 entries
            if len(self.fitness_deltas[pair]) > self.max_history_length:
                self.fitness_deltas[pair] = self.fitness_deltas[pair][-self.max_history_length:]
            
            # Update stagnation counter
            if delta <= 0:
                self.stagnation_counter[pair] += 1
            else:
                self.stagnation_counter[pair] = 0
            
            # Update stagnation score
            self._update_stagnation_score(pair)

    def _get_module_pairs(self, module: str) -> List[Tuple[str, str]]:
        """
        Get all module pairs involving the given module.
        
        Args:
            module: The module to find pairs for
            
        Returns:
            List of module pairs (sorted tuples)
        """
        pairs = []
        # Pairs with dependent modules
        for dep in self.dependency_graph.get(module, set()):
            pair = tuple(sorted([module, dep]))
            pairs.append(pair)
        # Pairs with dependency modules
        for dep in self.reverse_dependency.get(module, set()):
            pair = tuple(sorted([module, dep]))
            pairs.append(pair)
        return pairs

    def _update_stagnation_score(self, pair: Tuple[str, str]) -> None:
        """
        Update the stagnation score for a module pair (0-1).
        
        Args:
            pair: The module pair to update
        """
        deltas = self.fitness_deltas.get(pair, [])
        if not deltas:
            self.stagnation_scores[pair] = 0.0
            return
        
        # Calculate stagnation score based on:
        # 1. Proportion of non-improving deltas in history
        # 2. Consecutive non-improvement count
        # 3. Recent trend (last 5 deltas)
        
        recent_deltas = deltas[-5:] if len(deltas) >= 5 else deltas
        non_improving_count = sum(1 for d in recent_deltas if d <= 0)
        non_improving_ratio = non_improving_count / max(len(recent_deltas), 1)
        
        consecutive_count = self.stagnation_counter.get(pair, 0)
        consecutive_factor = min(consecutive_count / self.stagnation_threshold, 1.0)
        
        # Combine factors with weights
        score = (non_improving_ratio * 0.4) + (consecutive_factor * 0.6)
        self.stagnation_scores[pair] = min(max(score, 0.0), 1.0)

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

    def is_module_pair_stagnant(self, pair: Tuple[str, str]) -> bool:
        """
        Check if a specific module pair has reached stagnation (no improvement).
        
        Args:
            pair: The module pair to check
            
        Returns:
            True if module pair has no improvement for threshold cycles
        """
        return self.stagnation_counter.get(pair, 0) >= self.stagnation_threshold

    def get_stagnant_module_pairs(self) -> List[Tuple[str, str]]:
        """
        Get all module pairs that are currently stagnant.
        
        Returns:
            List of stagnant module pairs
        """
        return [
            pair for pair, count in self.stagnation_counter.items()
            if count >= self.stagnation_threshold
        ]

    def is_nash_equilibrium(self) -> bool:
        """
        Check if the system has reached a Nash equilibrium state.
        This occurs when no single module change has improved the system
        for the threshold number of consecutive cycles.
        
        Returns:
            True if system is in Nash equilibrium
        """
        if not self.fitness_deltas:
            return False
        
        # Check if all module pairs that have been evaluated are stagnant
        all_pairs = set(self.fitness_deltas.keys())
        stagnant_pairs = set(self.get_stagnant_module_pairs())
        
        # Only consider pairs that have been evaluated enough
        evaluated_pairs = {
            pair for pair, deltas in self.fitness_deltas.items()
            if len(deltas) >= self.stagnation_threshold
        }
        
        if not evaluated_pairs:
            return False
        
        return evaluated_pairs.issubset(stagnant_pairs)

    def get_system_analysis(self) -> Dict:
        """
        Get a comprehensive analysis of the current system state.
        
        Returns:
            Dictionary containing:
            - 'nash_equilibrium': bool
            - 'stagnant_module_pairs': list of module pairs
            - 'dependency_graph': dict of module dependencies
            - 'fitness_summary': dict of module pair fitness trends
            - 'stagnation_scores': dict of module pair stagnation scores
            - 'cycle_count': int
        """
        return {
            'nash_equilibrium': self.is_nash_equilibrium(),
            'stagnant_module_pairs': self.get_stagnant_module_pairs(),
            'dependency_graph': {
                module: list(deps) 
                for module, deps in self.dependency_graph.items()
            },
            'fitness_summary': {
                pair: {
                    'recent_deltas': deltas[-5:],
                    'average_delta': sum(deltas[-5:]) / max(len(deltas[-5:]), 1),
                    'stagnant': self.is_module_pair_stagnant(pair),
                    'stagnation_score': self.stagnation_scores.get(pair, 0.0)
                }
                for pair, deltas in self.fitness_deltas.items()
            },
            'stagnation_scores': dict(self.stagnation_scores),
            'cycle_count': self.current_cycle
        }

    def increment_cycle(self) -> None:
        """Advance to the next evaluation cycle."""
        self.current_cycle += 1

    def reset_module_pair(self, module1: str, module2: str) -> None:
        """
        Reset stagnation tracking for a specific module pair.
        Useful when modules are significantly restructured.
        
        Args:
            module1: First module in the pair
            module2: Second module in the pair
        """
        pair = tuple(sorted([module1, module2]))
        self.stagnation_counter[pair] = 0
        self.fitness_deltas[pair] = []
        self.stagnation_scores[pair] = 0.0

    def reset_all(self) -> None:
        """Reset all tracking data."""
        self.dependency_graph.clear()
        self.reverse_dependency.clear()
        self.output_to_inputs.clear()
        self.fitness_deltas.clear()
        self.stagnation_counter.clear()
        self.stagnation_scores.clear()
        self.current_cycle = 0
        self._cycle_improvement_history.clear()
        self._module_interaction_matrix.clear()

    def set_stagnation_threshold(self, threshold: int) -> None:
        """
        Set the number of consecutive non-improvement cycles required for stagnation.
        
        Args:
            threshold: Number of cycles (must be positive)
        """
        if threshold < 1:
            raise ValueError("Stagnation threshold must be at least 1")
        self.stagnation_threshold = threshold

    def get_stagnation_score(self, module1: str, module2: str) -> float:
        """
        Get the stagnation score for a module pair (0-1).
        
        Args:
            module1: First module in the pair
            module2: Second module in the pair
            
        Returns:
            Stagnation score between 0 and 1
        """
        pair = tuple(sorted([module1, module2]))
        return self.stagnation_scores.get(pair, 0.0)

    def get_all_stagnation_scores(self) -> Dict[Tuple[str, str], float]:
        """
        Get all stagnation scores for all module pairs.
        
        Returns:
            Dictionary mapping module pairs to their stagnation scores
        """
        return dict(self.stagnation_scores)

    def record_cycle_outcome(self, any_improvement: bool) -> None:
        """
        Record whether any module showed improvement in the current cycle.
        
        Args:
            any_improvement: True if at least one module improved fitness
        """
        self._cycle_improvement_history.append(any_improvement)
        # Keep only last 5 cycles
        if len(self._cycle_improvement_history) > 5:
            self._cycle_improvement_history = self._cycle_improvement_history[-5:]

    def is_at_equilibrium(self) -> bool:
        """
        Check if no single-module mutation has improved system fitness in the last 5 cycles.
        
        Returns:
            True if no improvement in last 5 cycles
        """
        if len(self._cycle_improvement_history) < 5:
            return False
        return not any(self._cycle_improvement_history[-5:])

    def detect_equilibrium(self) -> bool:
        """
        Returns True if the last 3 cycles show no single-module improvement
        (all mutations failed or no score increase).
        
        Returns:
            True if no improvement in last 3 cycles
        """
        if len(self._cycle_improvement_history) < 3:
            return False
        return not any(self._cycle_improvement_history[-3:])

    def get_equilibrium_state(self) -> Dict[str, Dict[str, float]]:
        """
        Return current module interaction matrix and equilibrium flag.
        The matrix maps each module to a dictionary of other modules and their interaction strengths.
        
        Returns:
            Dictionary containing:
            - 'interaction_matrix': module -> {other_module: interaction_strength}
            - 'equilibrium': bool indicating if system is at equilibrium
        """
        # Build interaction matrix from dependency graph and stagnation scores
        matrix: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))
        
        # Add interactions from dependency graph
        for source, targets in self.dependency_graph.items():
            for target in targets:
                pair = tuple(sorted([source, target]))
                # Use stagnation score as interaction strength (0 = no interaction, 1 = fully stagnant)
                strength = self.stagnation_scores.get(pair, 0.0)
                matrix[source][target] = strength
                matrix[target][source] = strength
        
        # Add interactions from reverse dependencies not already covered
        for target, sources in self.reverse_dependency.items():
            for source in sources:
                if source not in matrix or target not in matrix[source]:
                    pair = tuple(sorted([source, target]))
                    strength = self.stagnation_scores.get(pair, 0.0)
                    matrix[source][target] = strength
                    matrix[target][source] = strength
        
        return {
            'interaction_matrix': dict(matrix),
            'equilibrium': self.is_at_equilibrium()
        }

    def check_and_trigger_coordinated(self) -> Optional[Dict]:
        """
        Check if equilibrium has been reached in the last 3 cycles.
        If yes, call coordinated_mutation_planner to generate multi-module changes.
        
        Returns:
            The mutation plan from coordinated_mutation_planner, or None if not at equilibrium.
        """
        if not self.detect_equilibrium():
            return None
        
        # Import here to avoid circular imports
        from modules.coordinated_mutation_planner import CoordinatedMutationPlanner
        
        planner = CoordinatedMutationPlanner()
        equilibrium_state = self.get_equilibrium_state()
        mutation_plan = planner.generate_plan(
            dependency_graph=dict(self.dependency_graph),
            equilibrium_state=equilibrium_state
        )
        
        return mutation_plan