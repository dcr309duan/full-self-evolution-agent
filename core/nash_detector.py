import json
from collections import defaultdict
from typing import Dict, List, Tuple, Set, Optional

class NashEquilibriumDetector:
    """
    Detects Nash equilibrium conditions in module interaction scores.
    Tracks module interaction scores over a sliding window of 10 cycles,
    detects when no single-module mutation improves score by >5% over 3
    consecutive cycles, and provides a 'force_coordinated_change' method
    that generates multi-module mutation plans.
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
        
        # Module performance history: module_name -> list of scores (sliding window of 10)
        self.module_performance_history: Dict[str, List[float]] = {}
        
        # Maximum history length per module (sliding window)
        self.max_history_length: int = 10
        
        # Stagnation threshold for detecting equilibrium (N cycles)
        self.stagnation_threshold: int = 3
        
        # Consecutive non-improvement counter per module
        self.stagnation_counter: Dict[str, int] = {}
        
        # History of cycle outcomes: list of booleans (True if any improvement)
        self._cycle_improvement_history: List[bool] = []
        
        # Baseline score values for each module
        self.baseline_scores: Dict[str, float] = {}
        
        # Current score values for each module
        self.current_scores: Dict[str, float] = {}
        
        # Improvement threshold (5% = 0.05)
        self.improvement_threshold: float = 0.05
        
        # Number of cycles without improvement
        self.cycles_without_improvement: int = 0
        
        # Initialize baseline scores to 0
        for module_name in self.module_names:
            self.baseline_scores[module_name] = 0.0
            self.current_scores[module_name] = 0.0
            self.module_performance_history[module_name] = [0.0]

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

    def detect_nash_equilibrium(self, cycles: int = 3) -> bool:
        """
        Checks if no single-module mutation has improved score by >5% in last N cycles.
        
        Args:
            cycles: Number of cycles to check (default: 3)
            
        Returns:
            True if no single-module mutation has improved the system in last N cycles
        """
        if cycles < 1:
            raise ValueError("cycles must be at least 1")
        
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

    def check_and_force_coordinated_mutation(self) -> Optional[Dict]:
        """
        Checks if current module interactions are at Nash equilibrium by verifying
        no single-module mutation improves system fitness by >5%. If at equilibrium,
        generates a coordinated multi-module mutation plan targeting 2-3 interdependent
        modules and returns the plan for the orchestrator to execute atomically.
        
        Returns:
            Dictionary with coordinated mutation plan, or None if not at equilibrium
        """
        # Check if at Nash equilibrium
        if not self.detect_nash_equilibrium():
            return None
        
        # Find interdependent modules based on interaction history
        interdependent_pairs = []
        for key, interactions in self.module_interactions.items():
            if len(interactions) >= 3:  # At least 3 interactions to consider
                success_rate = sum(1 for s, _ in interactions if s) / len(interactions)
                if success_rate > 0.5:  # More than 50% success rate indicates interdependence
                    interdependent_pairs.append(key)
        
        # Find stagnant modules
        stagnant_modules = []
        for module_name in self.module_names:
            if self.stagnation_counter.get(module_name, 0) >= self.stagnation_threshold:
                stagnant_modules.append(module_name)
        
        # Select target modules: prefer interdependent stagnant modules
        selected_modules = []
        used_modules = set()
        
        # First, try to find interdependent pairs among stagnant modules
        for pair in interdependent_pairs:
            m1, m2 = pair
            if m1 in stagnant_modules and m2 in stagnant_modules:
                if m1 not in used_modules and m2 not in used_modules:
                    selected_modules.extend([m1, m2])
                    used_modules.add(m1)
                    used_modules.add(m2)
                    if len(selected_modules) >= 2:
                        break
        
        # If not enough modules selected, add more stagnant modules
        if len(selected_modules) < 2:
            for module in stagnant_modules:
                if module not in used_modules:
                    selected_modules.append(module)
                    used_modules.add(module)
                    if len(selected_modules) >= 3:
                        break
        
        # If still not enough, use modules with lowest scores
        if len(selected_modules) < 2:
            sorted_modules = sorted(
                self.module_names,
                key=lambda m: self.current_scores.get(m, 0.0)
            )
            for module in sorted_modules:
                if module not in used_modules:
                    selected_modules.append(module)
                    used_modules.add(module)
                    if len(selected_modules) >= 3:
                        break
        
        # Ensure we have at least 2 modules
        if len(selected_modules) < 2:
            return None
        
        # Limit to 2-3 modules
        num_modules = min(len(selected_modules), 3)
        selected_modules = selected_modules[:num_modules]
        
        # Generate coordinated mutation plan
        plan = {
            'timestamp': str(len(self._cycle_improvement_history)),
            'modules': selected_modules,
            'description': f"Coordinated multi-module mutation plan targeting {len(selected_modules)} modules",
            'changes': []
        }
        
        # Define possible changes
        changes = [
            'interface_redesign',
            'dependency_inversion',
            'shared_state_synchronization',
            'protocol_upgrade',
            'data_format_migration',
            'concurrency_model_change',
            'caching_strategy_overhaul',
            'error_handling_restructure',
            'logging_infrastructure_change',
            'security_policy_update'
        ]
        
        for i, module in enumerate(selected_modules):
            change = changes[i % len(changes)]
            plan['changes'].append({
                'module': module,
                'action': change,
                'description': f"Apply {change} to {module}"
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

    def force_coordinated_change(self) -> Optional[Dict]:
        """
        Generates a multi-module mutation plan targeting 2-3 modules simultaneously.
        
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
        
        # Generate coordinated mutation plan
        plan = {
            'timestamp': str(len(self._cycle_improvement_history)),
            'modules': selected_modules,
            'description': f"Coordinated multi-module mutation plan targeting {len(selected_modules)} modules",
            'changes': []
        }
        
        # Define possible changes
        changes = [
            'interface_redesign',
            'dependency_inversion',
            'shared_state_synchronization',
            'protocol_upgrade',
            'data_format_migration',
            'concurrency_model_change',
            'caching_strategy_overhaul',
            'error_handling_restructure',
            'logging_infrastructure_change',
            'security_policy_update'
        ]
        
        for i, module in enumerate(selected_modules):
            change = changes[i % len(changes)]
            plan['changes'].append({
                'module': module,
                'action': change,
                'description': f"Apply {change} to {module}"
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

    def record_mutation_outcome(self, module_name: str, score_delta: float) -> None:
        """
        Record the outcome of a mutation affecting a module.
        
        Args:
            module_name: Name of the module
            score_delta: The change in score (positive = improvement)
        """
        if module_name not in self.module_performance_history:
            self.module_performance_history[module_name] = []
        
        # Update current score
        current = self.current_scores.get(module_name, 0.0)
        self.current_scores[module_name] = current + score_delta
        
        # Track performance history
        self.module_performance_history[module_name].append(self.current_scores[module_name])
        
        # Keep only last N entries (sliding window of 10)
        if len(self.module_performance_history[module_name]) > self.max_history_length:
            self.module_performance_history[module_name] = self.module_performance_history[module_name][-self.max_history_length:]
        
        # Update stagnation counter
        if module_name not in self.stagnation_counter:
            self.stagnation_counter[module_name] = 0
        
        # Check if improvement is >5% compared to baseline
        baseline = self.baseline_scores.get(module_name, 0.0)
        if baseline > 0:
            improvement_pct = abs(score_delta) / baseline
        else:
            improvement_pct = abs(score_delta) if score_delta > 0 else 0
        
        if improvement_pct > self.improvement_threshold:
            self.stagnation_counter[module_name] = 0
        else:
            self.stagnation_counter[module_name] += 1

    def increment_cycle(self) -> None:
        """Advance to the next evaluation cycle."""
        self.cycles_without_improvement += 1
        
        # Check if any module improved by >5% in this cycle
        any_improvement = False
        for module_name in self.module_names:
            current_score = self.current_scores.get(module_name, 0.0)
            baseline_score = self.baseline_scores.get(module_name, 0.0)
            
            if baseline_score > 0:
                improvement_pct = abs(current_score - baseline_score) / baseline_score
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
            'equilibrium': self.detect_nash_equilibrium(),
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
        self.module_performance_history.clear()
        self.stagnation_counter.clear()
        self._cycle_improvement_history.clear()
        self.cycles_without_improvement = 0
        
        # Reset baseline scores
        for module_name in self.module_names:
            self.baseline_scores[module_name] = 0.0
            self.current_scores[module_name] = 0.0
            self.module_performance_history[module_name] = [0.0]

    def set_improvement_threshold(self, threshold: float) -> None:
        """
        Set the improvement threshold for detecting equilibrium.
        
        Args:
            threshold: Float representing the minimum improvement value (default 0.05 for 5%)
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

    def to_json(self) -> str:
        """
        Serialize the detector state to JSON.
        
        Returns:
            JSON string representation of the detector state
        """
        state = {
            'module_names': self.module_names,
            'module_performance_history': {
                k: v for k, v in self.module_performance_history.items()
            },
            'stagnation_counter': dict(self.stagnation_counter),
            'cycle_improvement_history': self._cycle_improvement_history,
            'baseline_scores': self.baseline_scores,
            'current_scores': self.current_scores,
            'improvement_threshold': self.improvement_threshold,
            'cycles_without_improvement': self.cycles_without_improvement,
            'stagnation_threshold': self.stagnation_threshold,
            'max_history_length': self.max_history_length,
            'module_interactions': {
                f"{k[0]}_{k[1]}": [(s, t) for s, t in v]
                for k, v in self.module_interactions.items()
            }
        }
        return json.dumps(state, indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> 'NashEquilibriumDetector':
        """
        Deserialize the detector state from JSON.
        
        Args:
            json_str: JSON string representation of the detector state
            
        Returns:
            NashEquilibriumDetector instance with restored state
        """
        state = json.loads(json_str)
        
        detector = cls(state['module_names'])
        detector.module_performance_history = state['module_performance_history']
        detector.stagnation_counter = state['stagnation_counter']
        detector._cycle_improvement_history = state['cycle_improvement_history']
        detector.baseline_scores = state['baseline_scores']
        detector.current_scores = state['current_scores']
        detector.improvement_threshold = state['improvement_threshold']
        detector.cycles_without_improvement = state['cycles_without_improvement']
        detector.stagnation_threshold = state['stagnation_threshold']
        detector.max_history_length = state['max_history_length']
        
        # Restore module interactions
        for key_str, interactions in state['module_interactions'].items():
            parts = key_str.split('_')
            if len(parts) >= 2:
                key = (parts[0], parts[1])
                detector.module_interactions[key] = [(s, t) for s, t in interactions]
        
        return detector