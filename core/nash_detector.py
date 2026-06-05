from collections import defaultdict
from typing import Dict, List, Tuple, Optional

class NashEquilibriumDetector:
    """
    Detects Nash equilibrium conditions in module interaction scores.
    Tracks module fitness scores over a sliding window, detects when no single
    module's fitness improves by >1% over N consecutive cycles, and provides
    a 'force_coordinated_change' method that generates multi-module mutation plans
    designed to escape local optima.
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
        
        # Module interaction tracking: (module1, module2) -> list of (success, timestamp)
        self.module_interactions: Dict[Tuple[str, str], List[Tuple[bool, str]]] = defaultdict(list)
        
        # Module fitness history: module_name -> list of fitness scores
        self.module_fitness_history: Dict[str, List[float]] = {}
        
        # Maximum history length per module (sliding window)
        self.max_history_length: int = history_length
        
        # Stagnation threshold for detecting equilibrium (N consecutive cycles)
        self.stagnation_threshold: int = stagnation_threshold
        
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
        
        # Track interactions with each dependency
        for dep in dependency_list:
            if dep not in self.module_names:
                continue
            
            # Normalize order for consistent key
            key = tuple(sorted([module_name, dep]))
            
            # Use cycle count as timestamp for simplicity
            timestamp = str(len(self._cycle_improvement_history))
            self.module_interactions[key].append((success_rate > 0.5, timestamp))
            
            # Keep only last 100 interactions per pair
            if len(self.module_interactions[key]) > 100:
                self.module_interactions[key] = self.module_interactions[key][-100:]

    def is_nash_equilibrium(self) -> bool:
        """
        Checks if no single module change improves the system by more than 1%.
        This is the core Nash equilibrium condition: no unilateral deviation yields improvement.
        
        Returns:
            True if the system is at a Nash equilibrium
        """
        # Check if we have enough history
        if len(self._cycle_improvement_history) < self.stagnation_threshold:
            return False
        
        # Check the last N cycles
        recent_cycles = self._cycle_improvement_history[-self.stagnation_threshold:]
        
        # If any cycle had improvement, not in equilibrium
        if any(recent_cycles):
            return False
        
        # Also check stagnation counters for all modules
        for module_name in self.module_names:
            if self.stagnation_counter.get(module_name, 0) < self.stagnation_threshold:
                return False
        
        return True

    def detect_nash_equilibrium(self) -> List[Dict]:
        """
        Analyzes module interaction matrices and identifies when no single-module change improves the system.
        Scans all module pairs to detect Nash equilibria conditions.
        For each pair, checks if both modules are stagnant and if their interaction
        success rate is below a threshold, indicating a potential local optimum.
        
        Returns:
            List of dictionaries, each describing a detected equilibrium condition
            for a module pair
        """
        equilibria = []
        
        for i in range(len(self.module_names)):
            for j in range(i + 1, len(self.module_names)):
                module1 = self.module_names[i]
                module2 = self.module_names[j]
                
                # Check if both modules are stagnant
                stagnant1 = self.stagnation_counter.get(module1, 0) >= self.stagnation_threshold
                stagnant2 = self.stagnation_counter.get(module2, 0) >= self.stagnation_threshold
                
                if stagnant1 and stagnant2:
                    # Get interaction success rate
                    success_rate = self.get_interaction_success_rate(module1, module2)
                    
                    # Check if interaction is stuck (low success rate)
                    if success_rate < 0.5 or len(self.module_interactions.get(tuple(sorted([module1, module2])), [])) == 0:
                        equilibria.append({
                            'module1': module1,
                            'module2': module2,
                            'success_rate': success_rate,
                            'stagnant1': stagnant1,
                            'stagnant2': stagnant2,
                            'score1': self.current_scores.get(module1, 0.0),
                            'score2': self.current_scores.get(module2, 0.0),
                            'description': f"Nash equilibrium detected between {module1} and {module2}"
                        })
        
        return equilibria

    def detect_equilibrium(self) -> List[List[str]]:
        """
        Checks if all single-module mutations fail to improve fitness by >1% over N consecutive cycles.
        Tracks module performance over the last N cycles and identifies when no single-module mutation
        improves the system.
        
        Returns:
            List of module sets at Nash equilibrium (each set is a list of module names)
        """
        cycles = self.stagnation_threshold
        
        # Check if we have enough history
        if len(self._cycle_improvement_history) < cycles:
            return []
        
        # Check the last N cycles
        recent_cycles = self._cycle_improvement_history[-cycles:]
        
        # If any cycle had improvement, not in equilibrium
        if any(recent_cycles):
            return []
        
        # Find all modules that are stagnant
        stagnant_modules = []
        for module_name in self.module_names:
            if self.stagnation_counter.get(module_name, 0) >= cycles:
                stagnant_modules.append(module_name)
        
        if len(stagnant_modules) < 2:
            return []
        
        # Group stagnant modules into equilibrium sets based on interaction patterns
        equilibrium_sets = []
        visited = set()
        
        for module in stagnant_modules:
            if module in visited:
                continue
            
            # Find all modules that interact with this module and are also stagnant
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
        
        # If no interaction-based sets found, return all stagnant modules as one set
        if not equilibrium_sets and len(stagnant_modules) >= 2:
            equilibrium_sets.append(stagnant_modules)
        
        return equilibrium_sets

    def force_coordinated_change(self, module_set: List[str]) -> List[Dict]:
        """
        Generates multi-module mutation plans that would be invisible to single-module optimization.
        Creates complementary changes for 2-3 modules simultaneously when Nash equilibrium is detected.
        Selects stagnant modules or those with lowest scores and creates complementary changes.
        
        Args:
            module_set: List of module names to include in the coordinated change
            
        Returns:
            List of dictionaries with 'module' and 'change' keys
        """
        if not module_set or len(module_set) < 2:
            return []
        
        # Ensure we have at least 2 modules
        selected_modules = module_set[:3]  # Max 3 modules
        
        # Generate coordinated mutation plan with complementary modifications
        plan = []
        
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
                plan.append({
                    'module': selected_modules[i],
                    'change': change_pair[0]
                })
                plan.append({
                    'module': selected_modules[i + 1],
                    'change': change_pair[1]
                })
            else:
                # Handle odd number of modules
                plan.append({
                    'module': selected_modules[i],
                    'change': 'interface_redesign'
                })
        
        # Record the interaction for each pair
        for i in range(len(selected_modules)):
            for j in range(i + 1, len(selected_modules)):
                self.track_module_interactions(
                    selected_modules[i],
                    1.0,  # Assume success for planning
                    [selected_modules[j]]
                )
        
        return plan

    def apply_coordinated_change(self, plan: List[Dict]) -> bool:
        """
        Executes a coordinated change plan atomically.
        Applies all changes in the plan to the module interaction matrix and updates
        scores accordingly. If any change fails, rolls back all changes.
        
        Args:
            plan: List of dictionaries with 'module' and 'change' keys from force_coordinated_change()
            
        Returns:
            True if all changes were applied successfully, False if rollback occurred
        """
        if not plan:
            return False
        
        # Save state for rollback
        saved_scores = dict(self.current_scores)
        saved_stagnation = dict(self.stagnation_counter)
        saved_history = {}
        for module_name in self.module_names:
            saved_history[module_name] = list(self.module_fitness_history.get(module_name, []))
        
        try:
            # Apply each change
            for change in plan:
                module = change['module']
                
                if module not in self.module_names:
                    raise ValueError(f"Unknown module: {module}")
                
                # Simulate applying the change (in real system, this would call mutation logic)
                # For now, we just record the interaction and update scores
                score_delta = 0.05  # Simulated improvement
                self.record_mutation_outcome(module, score_delta)
                
                # Track the interaction for all pairs in the plan
                for other_change in plan:
                    if other_change['module'] != module:
                        self.track_module_interactions(module, 1.0, [other_change['module']])
            
            # If we get here, all changes succeeded
            return True
            
        except Exception as e:
            # Rollback all changes
            self.current_scores = saved_scores
            self.stagnation_counter = saved_stagnation
            self.module_fitness_history = saved_history
            
            # Record failed interactions
            for change in plan:
                for other_change in plan:
                    if other_change['module'] != change['module']:
                        self.track_module_interactions(change['module'], 0.0, [other_change['module']])
            
            return False

    def run_detection_cycle(self) -> Optional[List[Dict]]:
        """
        Runs a detection cycle and returns a plan if equilibrium is detected.
        
        Returns:
            List of dictionaries with coordinated change plan if at equilibrium, or None if not at equilibrium
        """
        equilibrium_sets = self.detect_equilibrium()
        if not equilibrium_sets:
            return None
        
        # Generate plans for each equilibrium set
        all_plans = []
        for module_set in equilibrium_sets:
            plan = self.force_coordinated_change(module_set)
            if plan:
                all_plans.extend(plan)
        
        return all_plans if all_plans else None

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
        Get the current equilibrium state information for all tracked modules.
        
        Returns:
            Dictionary containing equilibrium state information including:
            - equilibrium: bool indicating if system is at Nash equilibrium
            - stagnant_modules: list of modules that are stagnant
            - cycles_without_improvement: number of cycles without improvement
            - module_scores: current scores for all modules
            - interaction_stats: statistics for all module interactions
        """
        return {
            'equilibrium': self.detect_equilibrium(),
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
            'detect_equilibrium': self.detect_equilibrium,
            'is_nash_equilibrium': self.is_nash_equilibrium,
            'detect_nash_equilibrium': self.detect_nash_equilibrium,
            'detect_nash_equilibria': self.detect_nash_equilibria,
            'force_coordinated_change': self.force_coordinated_change,
            'apply_coordinated_change': self.apply_coordinated_change,
            'run_detection_cycle': self.run_detection_cycle,
            'get_equilibrium_state': self.get_equilibrium_state,
            'record_mutation_outcome': self.record_mutation_outcome,
            'track_module_interactions': self.track_module_interactions,
            'increment_cycle': self.increment_cycle,
            'reset': self.reset
        }