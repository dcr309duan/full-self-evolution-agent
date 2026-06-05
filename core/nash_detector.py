from collections import defaultdict
from typing import Dict, List, Tuple, Optional

class NashEquilibriumDetector:
    """
    Detects Nash equilibrium conditions in module interaction scores.
    Tracks module fitness scores over a sliding window, detects when no single
    module's fitness improves by >1% over 3 consecutive cycles, and provides
    a 'force_coordinated_change' method that generates multi-module mutation plans
    designed to escape local optima.
    """

    def __init__(self, module_names: List[str]):
        """
        Initialize the detector with module names.
        
        Args:
            module_names: List of module names to track
        """
        if not module_names:
            raise ValueError("module_names list cannot be empty")
        
        self.module_names = list(module_names)
        
        # Module interaction tracking: (module1, module2) -> list of (success, timestamp)
        self.module_interactions: Dict[Tuple[str, str], List[Tuple[bool, str]]] = defaultdict(list)
        
        # Module fitness history: module_name -> list of fitness scores
        self.module_fitness_history: Dict[str, List[float]] = {}
        
        # Maximum history length per module (sliding window)
        self.max_history_length: int = 10
        
        # Stagnation threshold for detecting equilibrium (N consecutive cycles)
        self.stagnation_threshold: int = 3
        
        # Consecutive non-improvement counter per module
        self.stagnation_counter: Dict[str, int] = {}
        
        # History of cycle outcomes: list of booleans (True if any improvement)
        self._cycle_improvement_history: List[bool] = []
        
        # Current fitness scores for each module
        self.current_scores: Dict[str, float] = {}
        
        # Improvement threshold (1% = 0.01)
        self.improvement_threshold: float = 0.01
        
        # Number of cycles without improvement
        self.cycles_without_improvement: int = 0
        
        # Initialize current scores to 0
        for module_name in self.module_names:
            self.current_scores[module_name] = 0.0
            self.module_fitness_history[module_name] = [0.0]

    def track_module_interactions(self, module1: str, module2: str, success: bool) -> None:
        """
        Records which modules were mutated together and success rates.
        
        Args:
            module1: First module name
            module2: Second module name
            success: Whether the interaction was successful
        """
        if module1 not in self.module_names or module2 not in self.module_names:
            return
        
        # Normalize order for consistent key
        key = tuple(sorted([module1, module2]))
        
        # Use cycle count as timestamp for simplicity
        timestamp = str(len(self._cycle_improvement_history))
        self.module_interactions[key].append((success, timestamp))
        
        # Keep only last 100 interactions per pair
        if len(self.module_interactions[key]) > 100:
            self.module_interactions[key] = self.module_interactions[key][-100:]

    def detect_nash(self) -> bool:
        """
        Checks if all single-module mutations fail to improve fitness by >1% over 3 consecutive cycles.
        
        Returns:
            True if no single module's fitness has improved in last 3 cycles
        """
        cycles = self.stagnation_threshold
        
        # Check if we have enough history
        if len(self._cycle_improvement_history) < cycles:
            return False
        
        # Check the last N cycles
        recent_cycles = self._cycle_improvement_history[-cycles:]
        
        # If any cycle had improvement, not in equilibrium
        if any(recent_cycles):
            return False
        
        # Also check stagnation counters for all modules
        for module_name in self.module_names:
            if self.stagnation_counter.get(module_name, 0) < cycles:
                return False
        
        return True

    def force_coordinated_change(self) -> Optional[Dict]:
        """
        Selects 2-3 modules and applies simultaneous mutations to escape local optima.
        
        Returns:
            Dictionary with coordinated change plan, or None if no plan possible
        """
        # Find stagnant modules
        stagnant_modules = []
        for module_name in self.module_names:
            if self.stagnation_counter.get(module_name, 0) >= self.stagnation_threshold:
                stagnant_modules.append(module_name)
        
        # If not enough stagnant modules, use modules with lowest scores
        if len(stagnant_modules) < 2:
            # Sort modules by current score (ascending)
            sorted_modules = sorted(
                self.module_names,
                key=lambda m: self.current_scores.get(m, 0.0)
            )
            stagnant_modules = sorted_modules[:3]
        
        # Ensure we have at least 2 modules
        if len(stagnant_modules) < 2:
            return None
        
        # Select 2-3 modules
        num_modules = min(len(stagnant_modules), 3)
        selected_modules = stagnant_modules[:num_modules]
        
        # Generate coordinated mutation plan with complementary modifications
        plan = {
            'timestamp': str(len(self._cycle_improvement_history)),
            'modules': selected_modules,
            'description': f"Coordinated multi-module mutation plan targeting {len(selected_modules)} modules to escape local optima",
            'changes': []
        }
        
        # Define complementary changes that work well together
        complementary_changes = [
            ('interface_redesign', 'protocol_upgrade'),
            ('dependency_inversion', 'shared_state_synchronization'),
            ('data_format_migration', 'caching_strategy_overhaul'),
            ('concurrency_model_change', 'error_handling_restructure'),
            ('logging_infrastructure_change', 'security_policy_update')
        ]
        
        # Assign complementary changes to pairs of modules
        for i in range(0, len(selected_modules), 2):
            if i + 1 < len(selected_modules):
                change_pair = complementary_changes[i % len(complementary_changes)]
                plan['changes'].append({
                    'module': selected_modules[i],
                    'action': change_pair[0],
                    'description': f"Apply {change_pair[0]} to {selected_modules[i]} (complementary to {change_pair[1]} on {selected_modules[i+1]})"
                })
                plan['changes'].append({
                    'module': selected_modules[i + 1],
                    'action': change_pair[1],
                    'description': f"Apply {change_pair[1]} to {selected_modules[i+1]} (complementary to {change_pair[0]} on {selected_modules[i]})"
                })
            else:
                # Handle odd number of modules
                change = 'interface_redesign'
                plan['changes'].append({
                    'module': selected_modules[i],
                    'action': change,
                    'description': f"Apply {change} to {selected_modules[i]}"
                })
        
        # Record the interaction for each pair
        for i in range(len(selected_modules)):
            for j in range(i + 1, len(selected_modules)):
                self.track_module_interactions(
                    selected_modules[i],
                    selected_modules[j],
                    True  # Assume success for planning
                )
        
        return plan

    def run_detection_cycle(self) -> Optional[Dict]:
        """
        Runs a detection cycle and returns a plan if equilibrium is detected.
        
        Returns:
            Dictionary with coordinated change plan if at equilibrium, or None if not at equilibrium
        """
        if not self.detect_nash():
            return None
        
        return self.force_coordinated_change()

    def record_mutation_outcome(self, module_name: str, score_delta: float) -> None:
        """
        Record the outcome of a mutation affecting a module.
        
        Args:
            module_name: Name of the module
            score_delta: The change in score (positive = improvement)
        """
        if module_name not in self.module_fitness_history:
            self.module_fitness_history[module_name] = []
        
        # Update current score
        current = self.current_scores.get(module_name, 0.0)
        self.current_scores[module_name] = current + score_delta
        
        # Track fitness history
        self.module_fitness_history[module_name].append(self.current_scores[module_name])
        
        # Keep only last N entries (sliding window)
        if len(self.module_fitness_history[module_name]) > self.max_history_length:
            self.module_fitness_history[module_name] = self.module_fitness_history[module_name][-self.max_history_length:]
        
        # Update stagnation counter
        if module_name not in self.stagnation_counter:
            self.stagnation_counter[module_name] = 0
        
        # Check if improvement is >1% compared to previous score
        previous_score = self.module_fitness_history[module_name][-2] if len(self.module_fitness_history[module_name]) >= 2 else 0.0
        if previous_score > 0:
            improvement_pct = abs(score_delta) / previous_score
        else:
            improvement_pct = abs(score_delta) if score_delta > 0 else 0
        
        if improvement_pct > self.improvement_threshold:
            self.stagnation_counter[module_name] = 0
        else:
            self.stagnation_counter[module_name] += 1

    def increment_cycle(self) -> None:
        """Advance to the next evaluation cycle."""
        self.cycles_without_improvement += 1
        
        # Check if any module improved by >1% in this cycle
        any_improvement = False
        for module_name in self.module_names:
            current_score = self.current_scores.get(module_name, 0.0)
            previous_score = self.module_fitness_history[module_name][-2] if len(self.module_fitness_history[module_name]) >= 2 else 0.0
            
            if previous_score > 0:
                improvement_pct = abs(current_score - previous_score) / previous_score
                if improvement_pct > self.improvement_threshold:
                    any_improvement = True
                    break
        
        if any_improvement:
            self.cycles_without_improvement = 0
        
        self._cycle_improvement_history.append(any_improvement)
        if len(self._cycle_improvement_history) > 5:
            self._cycle_improvement_history = self._cycle_improvement_history[-5:]

    def get_interaction_success_rate(self, module1: str, module2: str) -> float:
        """
        Get the success rate for interactions between two modules.
        
        Args:
            module1: First module name
            module2: Second module name
            
        Returns:
            Success rate as a float between 0 and 1
        """
        key = tuple(sorted([module1, module2]))
        interactions = self.module_interactions.get(key, [])
        
        if not interactions:
            return 0.0
        
        successes = sum(1 for success, _ in interactions if success)
        return successes / len(interactions)

    def get_all_interaction_stats(self) -> Dict[str, Dict]:
        """
        Get statistics for all module interactions.
        
        Returns:
            Dictionary mapping interaction keys to their statistics
        """
        stats = {}
        for key, interactions in self.module_interactions.items():
            total = len(interactions)
            successes = sum(1 for success, _ in interactions if success)
            stats[f"{key[0]}_{key[1]}"] = {
                'total_interactions': total,
                'successful_interactions': successes,
                'success_rate': successes / total if total > 0 else 0.0,
                'last_interaction': interactions[-1][1] if interactions else None
            }
        return stats

    def get_equilibrium_state(self) -> Dict:
        """
        Get the current equilibrium state information.
        
        Returns:
            Dictionary containing equilibrium state information
        """
        return {
            'equilibrium': self.detect_nash(),
            'stagnant_modules': [
                m for m in self.module_names 
                if self.stagnation_counter.get(m, 0) >= self.stagnation_threshold
            ],
            'cycles_without_improvement': self.cycles_without_improvement,
            'module_scores': dict(self.current_scores),
            'interaction_stats': self.get_all_interaction_stats()
        }

    def reset(self) -> None:
        """Reset all tracking data."""
        self.module_interactions.clear()
        self.module_fitness_history.clear()
        self.stagnation_counter.clear()
        self._cycle_improvement_history.clear()
        self.cycles_without_improvement = 0
        
        # Reset current scores
        for module_name in self.module_names:
            self.current_scores[module_name] = 0.0
            self.module_fitness_history[module_name] = [0.0]

    def set_improvement_threshold(self, threshold: float) -> None:
        """
        Set the improvement threshold for detecting equilibrium.
        
        Args:
            threshold: Float representing the minimum improvement value (default 0.01 for 1%)
        """
        if threshold < 0:
            raise ValueError("Improvement threshold must be non-negative")
        self.improvement_threshold = threshold

    def set_stagnation_threshold(self, threshold: int) -> None:
        """
        Set the number of consecutive non-improvement cycles required for stagnation.
        
        Args:
            threshold: Number of cycles (must be positive)
        """
        if threshold < 1:
            raise ValueError("Stagnation threshold must be at least 1")
        self.stagnation_threshold = threshold

    # Integration hooks for orchestrator registration
    def register_with_orchestrator(self, orchestrator) -> None:
        """
        Register this detector with an orchestrator.
        
        Args:
            orchestrator: The orchestrator instance to register with
        """
        orchestrator.register_detector(self)

    def get_orchestrator_hooks(self) -> Dict:
        """
        Get hooks for orchestrator integration.
        
        Returns:
            Dictionary of hook methods for orchestrator
        """
        return {
            'detect_nash': self.detect_nash,
            'force_coordinated_change': self.force_coordinated_change,
            'run_detection_cycle': self.run_detection_cycle,
            'get_equilibrium_state': self.get_equilibrium_state,
            'record_mutation_outcome': self.record_mutation_outcome,
            'track_module_interactions': self.track_module_interactions,
            'increment_cycle': self.increment_cycle,
            'reset': self.reset
        }