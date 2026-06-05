import json
from collections import defaultdict, deque
from typing import List, Dict, Set, Tuple, Optional, Any

class NashEquilibriumDetector:
    """
    Detects Nash equilibrium conditions in module interaction scores.
    Tracks module performance over last N mutations, detects when no single-module
    change improves any module's performance by >5% over 3 consecutive attempts,
    and provides force_coordinated_mutation() that selects 2-3 modules and generates
    a combined mutation plan.
    """

    def __init__(self, module_names: List[str], history_length: int = 10, stagnation_threshold: int = 3):
        """
        Initialize the detector with module names.
        
        Args:
            module_names: List of module names to track
            history_length: Maximum history length per module (sliding window)
            stagnation_threshold: Number of consecutive non-improvement cycles for equilibrium
        """
        if not module_names:
            raise ValueError("module_names list cannot be empty")
        
        self.module_names = list(module_names)
        
        # Module fitness history: module_name -> deque of fitness scores
        self.module_fitness_history: Dict[str, deque] = {}
        
        # Maximum history length per module (sliding window)
        self.max_history_length = max(1, history_length)
        
        # Stagnation threshold for detecting equilibrium (N consecutive cycles)
        self.stagnation_threshold = max(1, stagnation_threshold)
        
        # Consecutive non-improvement counter per module
        self.stagnation_counter: Dict[str, int] = {}
        
        # History of cycle outcomes: deque of booleans (True if any improvement)
        self._cycle_improvement_history: deque = deque(maxlen=5)
        
        # Current fitness scores for each module
        self.current_scores: Dict[str, float] = {}
        
        # Improvement threshold (5% = 0.05)
        self.improvement_threshold = 0.05
        
        # Number of cycles without improvement
        self.cycles_without_improvement = 0
        
        # Module interaction tracking: (module1, module2) -> list of (success, timestamp)
        self.module_interactions: Dict[Tuple[str, str], List[Tuple[bool, str]]] = {}
        
        # Module interaction frequency tracking
        self.module_interaction_frequencies: Dict[str, int] = {}
        
        # Module interaction success rates: module_name -> list of success rates
        self.module_interaction_success_rates: Dict[str, List[float]] = {}
        
        # Module improvement rates over cycles
        self.module_improvement_rates: Dict[str, List[float]] = {}
        
        # Payoff matrix for module interactions: (module1, module2) -> payoff value
        self.payoff_matrix: Dict[Tuple[str, str], float] = {}
        
        # Initialize current scores to 0
        for module_name in self.module_names:
            self.current_scores[module_name] = 0.0
            self.module_fitness_history[module_name] = deque([0.0], maxlen=self.max_history_length)
            self.stagnation_counter[module_name] = 0
            self.module_interaction_frequencies[module_name] = 0
            self.module_interaction_success_rates[module_name] = []
            self.module_improvement_rates[module_name] = []

    def register_module_interaction_metrics(self, module_name: str, success_rate: float, dependency_count: int) -> None:
        """
        Register module interaction metrics including success rates and dependency counts.
        
        Args:
            module_name: Name of the module
            success_rate: Success rate of interactions (0.0 to 1.0)
            dependency_count: Number of dependencies for the module
        """
        if module_name not in self.module_names:
            return
        
        try:
            # Track success rate
            if module_name not in self.module_interaction_success_rates:
                self.module_interaction_success_rates[module_name] = []
            self.module_interaction_success_rates[module_name].append(success_rate)
            
            # Keep only last 100 entries
            if len(self.module_interaction_success_rates[module_name]) > 100:
                self.module_interaction_success_rates[module_name] = self.module_interaction_success_rates[module_name][-100:]
            
            # Track dependency count as interaction frequency
            self.module_interaction_frequencies[module_name] = self.module_interaction_frequencies.get(module_name, 0) + dependency_count
            
        except Exception:
            pass

    def detect_equilibrium(self, module_scores: Dict[str, float]) -> bool:
        """
        Detect if the system is at Nash equilibrium based on module scores.
        Returns True when no single metric improves by more than 1% over 5 consecutive cycles.
        
        Args:
            module_scores: Dictionary mapping module names to their current scores
            
        Returns:
            True if system is at Nash equilibrium, False otherwise
        """
        try:
            # Update current scores
            for module_name, score in module_scores.items():
                if module_name in self.current_scores:
                    self.current_scores[module_name] = score
            
            # Check if we have enough history (need 5 consecutive cycles)
            if len(self._cycle_improvement_history) < 5:
                return False
            
            # Check recent 5 cycles for any improvement > 1%
            recent_cycles = list(self._cycle_improvement_history)[-5:]
            
            if any(recent_cycles):
                return False
            
            # Check each module for stagnation (no improvement > 1%)
            for module_name in self.module_names:
                if self.stagnation_counter.get(module_name, 0) < 5:
                    return False
            
            return True
            
        except Exception:
            return False

    def identify_multi_module_change_candidates(self) -> List[List[str]]:
        """
        Identify multi-module change candidates by finding correlated metrics that are all at equilibrium.
        Returns sets of 2-3 modules where all metrics are at equilibrium and correlated.
        
        Returns:
            List of module sets that are candidates for coordinated change
        """
        try:
            # Find modules at equilibrium (stagnant for 5+ cycles)
            stagnant_modules = []
            for module_name in self.module_names:
                if self.stagnation_counter.get(module_name, 0) >= 5:
                    stagnant_modules.append(module_name)
            
            if len(stagnant_modules) < 2:
                return []
            
            # Find correlated modules based on interaction history
            correlated_sets = []
            visited = set()
            
            for module in stagnant_modules:
                if module in visited:
                    continue
                
                current_set = [module]
                visited.add(module)
                
                # Find correlated modules (those with interaction history)
                for other in stagnant_modules:
                    if other not in visited:
                        key = tuple(sorted([module, other]))
                        interactions = self.module_interactions.get(key, [])
                        if interactions:
                            current_set.append(other)
                            visited.add(other)
                
                if len(current_set) >= 2:
                    correlated_sets.append(current_set)
            
            # If no correlated sets found but we have stagnant modules, group them
            if not correlated_sets and len(stagnant_modules) >= 2:
                # Group into sets of 2-3
                for i in range(0, len(stagnant_modules), 2):
                    if i + 1 < len(stagnant_modules):
                        if i + 2 < len(stagnant_modules):
                            correlated_sets.append(stagnant_modules[i:i+3])
                        else:
                            correlated_sets.append(stagnant_modules[i:i+2])
            
            return correlated_sets
            
        except Exception:
            return []

    def track_module_improvement_rates(self, module_name: str, improvement_rate: float) -> None:
        """
        Track the improvement rate for a module over cycles.
        
        Args:
            module_name: Name of the module
            improvement_rate: The improvement rate (as a decimal, e.g., 0.05 for 5%)
        """
        if module_name not in self.module_improvement_rates:
            self.module_improvement_rates[module_name] = []
        
        self.module_improvement_rates[module_name].append(improvement_rate)
        
        # Keep only last 100 entries to prevent memory issues
        if len(self.module_improvement_rates[module_name]) > 100:
            self.module_improvement_rates[module_name] = self.module_improvement_rates[module_name][-100:]

    def get_module_improvement_rate_history(self, module_name: str) -> List[float]:
        """
        Get the improvement rate history for a module.
        
        Args:
            module_name: Name of the module
            
        Returns:
            List of improvement rates over cycles
        """
        return self.module_improvement_rates.get(module_name, [])

    def get_average_improvement_rate(self, module_name: str, recent_cycles: int = 5) -> float:
        """
        Get the average improvement rate for a module over recent cycles.
        
        Args:
            module_name: Name of the module
            recent_cycles: Number of recent cycles to consider
            
        Returns:
            Average improvement rate as a float
        """
        rates = self.module_improvement_rates.get(module_name, [])
        if not rates:
            return 0.0
        
        recent_rates = rates[-recent_cycles:] if len(rates) > recent_cycles else rates
        return sum(recent_rates) / len(recent_rates)

    def get_all_module_improvement_rates(self) -> Dict[str, List[float]]:
        """
        Get improvement rates for all modules.
        
        Returns:
            Dictionary mapping module names to their improvement rate histories
        """
        return dict(self.module_improvement_rates)

    def get_stable_modules(self) -> List[str]:
        """
        Get list of modules that are currently in a stable state (stagnant).
        
        Returns:
            List of module names that are stagnant
        """
        try:
            stable_modules = []
            for module_name in self.module_names:
                if self.stagnation_counter.get(module_name, 0) >= self.stagnation_threshold:
                    stable_modules.append(module_name)
            return stable_modules
        except Exception:
            return []

    def force_coordinated_mutation(self, target_modules: List[str]) -> List[Dict[str, Any]]:
        """
        Generate coordinated mutation plans for multiple modules to break Nash equilibrium.
        
        Args:
            target_modules: List of module names to include in the coordinated mutation
            
        Returns:
            List of dictionaries with 'module' and 'change' keys representing mutation plans
        """
        if not target_modules or len(target_modules) < 2:
            return []
        
        try:
            selected_modules = target_modules[:3]
            
            complementary_changes = [
                ('interface_redesign', 'protocol_upgrade'),
                ('dependency_inversion', 'shared_state_synchronization'),
                ('data_format_migration', 'caching_strategy_overhaul'),
                ('concurrency_model_change', 'error_handling_restructure'),
                ('logging_infrastructure_change', 'security_policy_update')
            ]
            
            plan = []
            
            for i in range(0, len(selected_modules), 2):
                if i + 1 < len(selected_modules):
                    change_pair = complementary_changes[i % len(complementary_changes)]
                    plan.append({
                        'module': selected_modules[i],
                        'change': change_pair[0]
                    })
                    plan.append({
                        'module': selected_modules[i + 1],
                        'change': change_pair[1]
                    })
                else:
                    plan.append({
                        'module': selected_modules[i],
                        'change': 'interface_redesign'
                    })
            
            return plan
            
        except Exception:
            return []

    def get_orchestrator_hooks(self) -> Dict[str, Any]:
        """
        Get hooks for orchestrator integration.
        
        Returns:
            Dictionary of hook methods for orchestrator
        """
        return {
            'detect_equilibrium': self.detect_equilibrium,
            'get_stable_modules': self.get_stable_modules,
            'force_coordinated_mutation': self.force_coordinated_mutation,
            'get_equilibrium_state': self.get_equilibrium_state,
            'record_mutation_outcome': self.record_mutation_outcome,
            'track_module_interactions': self.track_module_interactions,
            'increment_cycle': self.increment_cycle,
            'reset': self.reset,
            'get_module_interaction_frequency': self.get_module_interaction_frequency,
            'get_module_success_rate': self.get_module_success_rate,
            'detect_nash_equilibrium': self.detect_nash_equilibrium,
            'detect_and_trigger_coordinated_change': self.detect_and_trigger_coordinated_change,
            'track_module_improvement_rates': self.track_module_improvement_rates,
            'get_module_improvement_rate_history': self.get_module_improvement_rate_history,
            'get_average_improvement_rate': self.get_average_improvement_rate,
            'get_all_module_improvement_rates': self.get_all_module_improvement_rates,
            'register_module_interaction_metrics': self.register_module_interaction_metrics,
            'identify_multi_module_change_candidates': self.identify_multi_module_change_candidates
        }

    def track_module_interactions(self, module_name: str, success_rate: float, dependency_list: List[str]) -> None:
        """
        Records which modules were mutated together and success rates.
        
        Args:
            module_name: The module name
            success_rate: Success rate of interactions with dependencies
            dependency_list: List of dependency module names
        """
        if module_name not in self.module_names:
            return
        
        try:
            valid_deps = [dep for dep in dependency_list if dep in self.module_names]
            
            for dep in valid_deps:
                key = tuple(sorted([module_name, dep]))
                timestamp = str(len(self.module_interactions.get(key, [])))
                
                if key not in self.module_interactions:
                    self.module_interactions[key] = []
                self.module_interactions[key].append((success_rate > 0.5, timestamp))
                
                self.module_interaction_frequencies[module_name] = self.module_interaction_frequencies.get(module_name, 0) + 1
                self.module_interaction_frequencies[dep] = self.module_interaction_frequencies.get(dep, 0) + 1
                
                if module_name not in self.module_interaction_success_rates:
                    self.module_interaction_success_rates[module_name] = []
                self.module_interaction_success_rates[module_name].append(success_rate)
                
                if dep not in self.module_interaction_success_rates:
                    self.module_interaction_success_rates[dep] = []
                self.module_interaction_success_rates[dep].append(success_rate)
                
                if len(self.module_interactions[key]) > 100:
                    self.module_interactions[key] = self.module_interactions[key][-100:]
                
                if len(self.module_interaction_success_rates[module_name]) > 100:
                    self.module_interaction_success_rates[module_name] = self.module_interaction_success_rates[module_name][-100:]
                if len(self.module_interaction_success_rates[dep]) > 100:
                    self.module_interaction_success_rates[dep] = self.module_interaction_success_rates[dep][-100:]
                    
        except Exception:
            pass

    def detect_equilibrium_sets(self) -> List[List[str]]:
        """
        Checks if all single-module mutations fail to improve fitness by >5% over N consecutive cycles.
        
        Returns:
            List of module sets at Nash equilibrium (each set is a list of module names)
        """
        try:
            cycles = self.stagnation_threshold
            
            if len(self._cycle_improvement_history) < cycles:
                return []
            
            recent_cycles = list(self._cycle_improvement_history)[-cycles:]
            
            if any(recent_cycles):
                return []
            
            stagnant_modules = []
            for module_name in self.module_names:
                if self.stagnation_counter.get(module_name, 0) >= cycles:
                    stagnant_modules.append(module_name)
            
            if len(stagnant_modules) < 2:
                return []
            
            equilibrium_sets = []
            visited = set()
            
            for module in stagnant_modules:
                if module in visited:
                    continue
                
                current_set = [module]
                visited.add(module)
                
                for other in stagnant_modules:
                    if other not in visited:
                        key = tuple(sorted([module, other]))
                        interactions = self.module_interactions.get(key, [])
                        if interactions:
                            current_set.append(other)
                            visited.add(other)
                
                if len(current_set) >= 2:
                    equilibrium_sets.append(current_set)
            
            if not equilibrium_sets and len(stagnant_modules) >= 2:
                equilibrium_sets.append(stagnant_modules)
            
            return equilibrium_sets
            
        except Exception:
            return []

    def detect_nash_equilibrium(self) -> bool:
        """
        Checks if any single-module change improves system metrics.
        Returns True if no single-module change improves metrics (Nash equilibrium).
        
        Returns:
            bool: True if system is at Nash equilibrium, False otherwise
        """
        try:
            if len(self._cycle_improvement_history) < self.stagnation_threshold:
                return False
            
            recent_cycles = list(self._cycle_improvement_history)[-self.stagnation_threshold:]
            
            if any(recent_cycles):
                return False
            
            for module_name in self.module_names:
                if self.stagnation_counter.get(module_name, 0) < self.stagnation_threshold:
                    return False
            
            return True
            
        except Exception:
            return False

    def force_coordinated_change(self, module_set: List[str]) -> List[Dict[str, Any]]:
        """
        Generates multi-module mutation plans that would be invisible to single-module optimization.
        Creates complementary changes for 2-3 modules simultaneously when Nash equilibrium is detected.
        
        Args:
            module_set: List of module names to include in the coordinated change
            
        Returns:
            List of dictionaries with 'module' and 'change' keys
        """
        if not module_set or len(module_set) < 2:
            return []
        
        try:
            selected_modules = module_set[:3]
            
            complementary_changes = [
                ('interface_redesign', 'protocol_upgrade'),
                ('dependency_inversion', 'shared_state_synchronization'),
                ('data_format_migration', 'caching_strategy_overhaul'),
                ('concurrency_model_change', 'error_handling_restructure'),
                ('logging_infrastructure_change', 'security_policy_update')
            ]
            
            plan = []
            
            for i in range(0, len(selected_modules), 2):
                if i + 1 < len(selected_modules):
                    change_pair = complementary_changes[i % len(complementary_changes)]
                    plan.append({
                        'module': selected_modules[i],
                        'change': change_pair[0]
                    })
                    plan.append({
                        'module': selected_modules[i + 1],
                        'change': change_pair[1]
                    })
                else:
                    plan.append({
                        'module': selected_modules[i],
                        'change': 'interface_redesign'
                    })
            
            for i in range(len(selected_modules)):
                for j in range(i + 1, len(selected_modules)):
                    self.track_module_interactions(
                        selected_modules[i],
                        1.0,
                        [selected_modules[j]]
                    )
            
            return plan
            
        except Exception:
            return []

    def detect_and_trigger_coordinated_change(self, module_scores: Dict[str, float]) -> List[Dict[str, Any]]:
        """
        Detect Nash equilibrium and trigger coordinated change if equilibrium is found.
        
        This method combines equilibrium detection and coordinated change planning into
        a single call. It first checks if the system is at Nash equilibrium using the
        provided module scores. If equilibrium is detected, it generates a multi-module
        mutation plan to break the equilibrium.
        
        Args:
            module_scores: Dictionary mapping module names to their current scores
            
        Returns:
            List of dictionaries with 'module' and 'change' keys representing mutation plans.
            Returns empty list if no equilibrium is detected or if no valid plan can be generated.
        """
        try:
            # First, detect if we're at equilibrium
            if not self.detect_equilibrium(module_scores):
                return []
            
            # Get equilibrium sets to find which modules are stagnant
            equilibrium_sets = self.detect_equilibrium_sets()
            
            if not equilibrium_sets:
                # If no equilibrium sets found but equilibrium detected, try with all stagnant modules
                stagnant_modules = [
                    m for m in self.module_names 
                    if self.stagnation_counter.get(m, 0) >= self.stagnation_threshold
                ]
                if len(stagnant_modules) >= 2:
                    return self.force_coordinated_change(stagnant_modules)
                return []
            
            # Use the first equilibrium set for coordinated change
            return self.force_coordinated_change(equilibrium_sets[0])
            
        except Exception:
            return []

    def record_mutation_outcome(self, module_name: str, score_delta: float) -> None:
        """
        Record the outcome of a mutation affecting a module.
        
        Args:
            module_name: Name of the module
            score_delta: The change in score (positive = improvement)
        """
        if module_name not in self.module_fitness_history:
            self.module_fitness_history[module_name] = deque(maxlen=self.max_history_length)
        
        try:
            current = self.current_scores.get(module_name, 0.0)
            self.current_scores[module_name] = current + score_delta
            
            self.module_fitness_history[module_name].append(self.current_scores[module_name])
            
            if module_name not in self.stagnation_counter:
                self.stagnation_counter[module_name] = 0
            
            history_list = list(self.module_fitness_history[module_name])
            previous_score = history_list[-2] if len(history_list) >= 2 else 0.0
            if previous_score > 0:
                improvement_pct = abs(score_delta) / previous_score
            else:
                improvement_pct = abs(score_delta) if score_delta > 0 else 0
            
            # Track improvement rate
            self.track_module_improvement_rates(module_name, improvement_pct)
            
            if improvement_pct > self.improvement_threshold:
                self.stagnation_counter[module_name] = 0
            else:
                self.stagnation_counter[module_name] = self.stagnation_counter.get(module_name, 0) + 1
                
        except Exception:
            pass

    def increment_cycle(self) -> None:
        """Advance to the next evaluation cycle."""
        try:
            self.cycles_without_improvement += 1
            
            any_improvement = False
            for module_name in self.module_names:
                current_score = self.current_scores.get(module_name, 0.0)
                history_list = list(self.module_fitness_history[module_name])
                previous_score = history_list[-2] if len(history_list) >= 2 else 0.0
                
                if previous_score > 0:
                    improvement_pct = abs(current_score - previous_score) / previous_score
                    if improvement_pct > self.improvement_threshold:
                        any_improvement = True
                        break
            
            if any_improvement:
                self.cycles_without_improvement = 0
            
            self._cycle_improvement_history.append(any_improvement)
            
        except Exception:
            pass

    def get_interaction_success_rate(self, module1: str, module2: str) -> float:
        """
        Get the success rate for interactions between two modules.
        
        Args:
            module1: First module name
            module2: Second module name
            
        Returns:
            Success rate as a float between 0 and 1
        """
        try:
            key = tuple(sorted([module1, module2]))
            interactions = self.module_interactions.get(key, [])
            
            if not interactions:
                return 0.0
            
            successes = sum(1 for success, _ in interactions if success)
            return successes / len(interactions)
            
        except Exception:
            return 0.0

    def get_module_interaction_frequency(self, module_name: str) -> int:
        """
        Get the interaction frequency for a specific module.
        
        Args:
            module_name: Name of the module
            
        Returns:
            Number of interactions recorded for the module
        """
        return self.module_interaction_frequencies.get(module_name, 0)

    def get_module_success_rate(self, module_name: str) -> float:
        """
        Get the average success rate for a specific module.
        
        Args:
            module_name: Name of the module
            
        Returns:
            Average success rate as a float between 0 and 1
        """
        try:
            rates = self.module_interaction_success_rates.get(module_name, [])
            if not rates:
                return 0.0
            return sum(rates) / len(rates)
            
        except Exception:
            return 0.0

    def get_all_interaction_stats(self) -> Dict[str, Dict[str, Any]]:
        """
        Get statistics for all module interactions.
        
        Returns:
            Dictionary mapping interaction keys to their statistics
        """
        stats = {}
        try:
            for key, interactions in self.module_interactions.items():
                total = len(interactions)
                successes = sum(1 for success, _ in interactions if success)
                stats[f"{key[0]}_{key[1]}"] = {
                    'total_interactions': total,
                    'successful_interactions': successes,
                    'success_rate': successes / total if total > 0 else 0.0,
                    'last_interaction': interactions[-1][1] if interactions else None
                }
        except Exception:
            pass
        
        return stats

    def get_equilibrium_state(self) -> Dict[str, Any]:
        """
        Get the current equilibrium state information for all tracked modules.
        
        Returns:
            Dictionary containing equilibrium state information
        """
        try:
            return {
                'equilibrium': self.detect_equilibrium_sets(),
                'stagnant_modules': [
                    m for m in self.module_names 
                    if self.stagnation_counter.get(m, 0) >= self.stagnation_threshold
                ],
                'cycles_without_improvement': self.cycles_without_improvement,
                'module_scores': dict(self.current_scores),
                'interaction_stats': self.get_all_interaction_stats(),
                'module_improvement_rates': {k: v[-5:] if len(v) > 5 else v for k, v in self.module_improvement_rates.items()}
            }
        except Exception:
            return {
                'equilibrium': [],
                'stagnant_modules': [],
                'cycles_without_improvement': self.cycles_without_improvement,
                'module_scores': dict(self.current_scores),
                'interaction_stats': {},
                'module_improvement_rates': {}
            }

    def reset(self) -> None:
        """Reset all tracking data."""
        try:
            self.module_interactions.clear()
            self.module_fitness_history.clear()
            self.stagnation_counter.clear()
            self._cycle_improvement_history.clear()
            self.cycles_without_improvement = 0
            self.module_interaction_frequencies.clear()
            self.module_interaction_success_rates.clear()
            self.module_improvement_rates.clear()
            self.payoff_matrix.clear()
            
            for module_name in self.module_names:
                self.current_scores[module_name] = 0.0
                self.module_fitness_history[module_name] = deque([0.0], maxlen=self.max_history_length)
                self.stagnation_counter[module_name] = 0
                self.module_interaction_frequencies[module_name] = 0
                self.module_interaction_success_rates[module_name] = []
                self.module_improvement_rates[module_name] = []
                
        except Exception:
            pass

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

    def update_payoff_matrix(self, module1: str, module2: str, payoff: float) -> None:
        """
        Update the payoff matrix for a pair of modules.
        
        Args:
            module1: First module name
            module2: Second module name
            payoff: The payoff value for the interaction
        """
        key = tuple(sorted([module1, module2]))
        self.payoff_matrix[key] = payoff

    def get_payoff(self, module1: str, module2: str) -> float:
        """
        Get the payoff value for a pair of modules.
        
        Args:
            module1: First module name
            module2: Second module name
            
        Returns:
            The payoff value, or 0.0 if not found
        """
        key = tuple(sorted([module1, module2]))
        return self.payoff_matrix.get(key, 0.0)

    def find_coordinated_mutation_sets(self) -> List[List[str]]:
        """
        Find sets of 2-3 modules where combined changes produce >15% improvement
        even though individual changes produce <5%.
        
        Returns:
            List of module sets that would benefit from coordinated mutation
        """
        try:
            coordinated_sets = []
            
            # Check pairs
            for i in range(len(self.module_names)):
                for j in range(i + 1, len(self.module_names)):
                    module_i = self.module_names[i]
                    module_j = self.module_names[j]
                    
                    # Get individual improvement rates
                    rate_i = self.get_average_improvement_rate(module_i, 5)
                    rate_j = self.get_average_improvement_rate(module_j, 5)
                    
                    # Check if individual improvements are < 5%
                    if rate_i < 0.05 and rate_j < 0.05:
                        # Get combined payoff
                        payoff = self.get_payoff(module_i, module_j)
                        
                        # Check if combined improvement would be > 15%
                        if payoff > 0.15:
                            coordinated_sets.append([module_i, module_j])
            
            # Check triples
            for i in range(len(self.module_names)):
                for j in range(i + 1, len(self.module_names)):
                    for k in range(j + 1, len(self.module_names)):
                        module_i = self.module_names[i]
                        module_j = self.module_names[j]
                        module_k = self.module_names[k]
                        
                        # Get individual improvement rates
                        rate_i = self.get_average_improvement_rate(module_i, 5)
                        rate_j = self.get_average_improvement_rate(module_j, 5)
                        rate_k = self.get_average_improvement_rate(module_k, 5)
                        
                        # Check if individual improvements are < 5%
                        if rate_i < 0.05 and rate_j < 0.05 and rate_k < 0.05:
                            # Get combined payoffs
                            payoff_ij = self.get_payoff(module_i, module_j)
                            payoff_ik = self.get_payoff(module_i, module_k)
                            payoff_jk = self.get_payoff(module_j, module_k)
                            
                            # Check if combined improvement would be > 15%
                            combined_payoff = payoff_ij + payoff_ik + payoff_jk
                            if combined_payoff > 0.15:
                                coordinated_sets.append([module_i, module_j, module_k])
            
            return coordinated_sets
            
        except Exception:
            return []

    def detect_nash(self, state: Dict[str, float]) -> bool:
        """
        Detect if the current state is a Nash equilibrium.
        A state is a Nash equilibrium if no single module can improve its score
        by changing its strategy while all other modules keep their strategies fixed.
        
        Args:
            state: Dictionary mapping module names to their current scores/strategies
            
        Returns:
            True if the state is a Nash equilibrium, False otherwise
        """
        try:
            # Update current scores from state
            for module_name, score in state.items():
                if module_name in self.current_scores:
                    self.current_scores[module_name] = score
            
            # Check if we have enough history
            if len(self._cycle_improvement_history) < self.stagnation_threshold:
                return False
            
            # Check recent cycles for any improvement
            recent_cycles = list(self._cycle_improvement_history)[-self.stagnation_threshold:]
            
            if any(recent_cycles):
                return False
            
            # Check each module for stagnation
            for module_name in self.module_names:
                if self.stagnation_counter.get(module_name, 0) < self.stagnation_threshold:
                    return False
            
            return True
            
        except Exception:
            return False

    def get_payoff_matrix(self) -> Dict[str, Dict[str, float]]:
        """
        Get the current payoff matrix as a nested dictionary.
        
        Returns:
            Dictionary mapping module pairs to their payoff values
        """
        try:
            matrix = {}
            for (mod1, mod2), payoff in self.payoff_matrix.items():
                if mod1 not in matrix:
                    matrix[mod1] = {}
                if mod2 not in matrix:
                    matrix[mod2] = {}
                matrix[mod1][mod2] = payoff
                matrix[mod2][mod1] = payoff
            
            # Ensure all modules are in the matrix
            for module in self.module_names:
                if module not in matrix:
                    matrix[module] = {}
                for other in self.module_names:
                    if other != module and other not in matrix[module]:
                        matrix[module][other] = self.get_payoff(module, other)
            
            return matrix
            
        except Exception:
            return {}


def run_test_mode():
    """Simple test mode that can run standalone."""
    print("Running NashEquilibriumDetector in test mode...")
    
    # Create detector with test modules
    detector = NashEquilibriumDetector(
        module_names=["module_a", "module_b", "module_c"],
        history_length=5,
        stagnation_threshold=3
    )
    
    # Test 1: Initial state
    print("\nTest 1: Initial state")
    print(f"  Equilibrium: {detector.detect_equilibrium_sets()}")
    print(f"  Nash equilibrium: {detector.detect_nash_equilibrium()}")
    assert detector.detect_equilibrium_sets() == [], "Initial state should not be in equilibrium"
    assert not detector.detect_nash_equilibrium(), "Initial state should not be in Nash equilibrium"
    print("  PASSED")
    
    # Test 2: Record improvements
    print("\nTest 2: Record improvements (should not trigger equilibrium)")
    detector.record_mutation_outcome("module_a", 10.0)  # 10% improvement
    detector.record_mutation_outcome("module_b", 8.0)   # 8% improvement
    detector.record_mutation_outcome("module_c", 12.0)  # 12% improvement
    detector.increment_cycle()
    
    print(f"  Equilibrium: {detector.detect_equilibrium_sets()}")
    print(f"  Nash equilibrium: {detector.detect_nash_equilibrium()}")
    assert detector.detect_equilibrium_sets() == [], "Improvements should prevent equilibrium"
    assert not detector.detect_nash_equilibrium(), "Improvements should prevent Nash equilibrium"
    print("  PASSED")
    
    # Test 3: Record stagnation (small changes)
    print("\nTest 3: Record stagnation (small changes < 5%)")
    for cycle in range(3):
        detector.record_mutation_outcome("module_a", 0.01)  # 0.1% improvement
        detector.record_mutation_outcome("module_b", 0.02)  # 0.2% improvement
        detector.record_mutation_outcome("module_c", 0.015) # 0.15% improvement
        detector.increment_cycle()
    
    print(f"  Equilibrium: {detector.detect_equilibrium_sets()}")
    print(f"  Nash equilibrium: {detector.detect_nash_equilibrium()}")
    equilibrium_sets = detector.detect_equilibrium_sets()
    assert len(equilibrium_sets) > 0, "Stagnation should trigger equilibrium"
    assert detector.detect_nash_equilibrium(), "Stagnation should trigger Nash equilibrium"
