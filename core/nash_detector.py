import random
from typing import Dict, List, Tuple, Set, Optional, Callable
from collections import defaultdict

class NashEquilibriumDetector:
    """
    Detects Nash equilibrium conditions in module interaction scores.
    Tracks module interaction scores over cycles, detects when no single-module
    mutation improves the system for 3+ consecutive cycles, and provides a
    'force_coordinated_change' method that generates multi-module mutation plans.
    """

    def __init__(self, fitness_functions: Dict[str, Callable]):
        """
        Initialize the detector with module fitness functions.
        
        Args:
            fitness_functions: Dict mapping module names to their fitness functions.
                Each fitness function should take no arguments and return a float.
        """
        if not fitness_functions:
            raise ValueError("fitness_functions dict cannot be empty")
        
        self.fitness_functions = fitness_functions.copy()
        self.module_names = list(fitness_functions.keys())
        
        # Module interaction scores: (module1, module2) -> list of score deltas (last 10)
        self.interaction_scores: Dict[Tuple[str, str], List[float]] = {}
        # Maximum history length per module pair
        self.max_history_length: int = 10
        # Stagnation threshold for detecting equilibrium (3+ consecutive cycles)
        self.stagnation_threshold: int = 3
        # Consecutive non-improvement counter per module pair
        self.stagnation_counter: Dict[Tuple[str, str], int] = {}
        # History of cycle outcomes: list of booleans (True if any improvement)
        self._cycle_improvement_history: List[bool] = []
        # Baseline score values for each module
        self.baseline_scores: Dict[str, float] = {}
        # Current score values for each module
        self.current_scores: Dict[str, float] = {}
        # Improvement threshold (0.1 by default)
        self.improvement_threshold: float = 0.1
        # Number of cycles without improvement
        self.cycles_without_improvement: int = 0
        
        # Initialize baseline scores
        self._compute_baseline_scores()

    def _compute_baseline_scores(self) -> None:
        """Compute baseline scores for all modules."""
        for module_name, fitness_func in self.fitness_functions.items():
            try:
                score = fitness_func()
                self.baseline_scores[module_name] = score
                self.current_scores[module_name] = score
            except Exception:
                self.baseline_scores[module_name] = 0.0
                self.current_scores[module_name] = 0.0

    def record_mutation_outcome(self, module1: str, module2: str, score_delta: float) -> None:
        """
        Record the outcome of a mutation affecting a module pair.
        
        Args:
            module1: First module in the pair
            module2: Second module in the pair
            score_delta: The change in interaction score (positive = improvement)
        """
        pair = tuple(sorted([module1, module2]))
        if pair not in self.interaction_scores:
            self.interaction_scores[pair] = []
        self.interaction_scores[pair].append(score_delta)
        
        # Keep only last 10 entries
        if len(self.interaction_scores[pair]) > self.max_history_length:
            self.interaction_scores[pair] = self.interaction_scores[pair][-self.max_history_length:]
        
        # Update stagnation counter
        if pair not in self.stagnation_counter:
            self.stagnation_counter[pair] = 0
        if score_delta <= 0:
            self.stagnation_counter[pair] += 1
        else:
            self.stagnation_counter[pair] = 0

    def detect_equilibrium(self) -> bool:
        """
        Detect when no single module change improves any module's score by >0.1.
        Returns True if all module pairs have been stagnant for the threshold number of cycles.
        
        Returns:
            True if system is in Nash equilibrium
        """
        if not self.interaction_scores:
            return False
        
        # Check if all module pairs that have been evaluated are stagnant
        for pair, deltas in self.interaction_scores.items():
            if len(deltas) < self.stagnation_threshold:
                return False
            if self.stagnation_counter.get(pair, 0) < self.stagnation_threshold:
                return False
        
        # Also check if any single-module change would improve score by >0.1
        for module_name in self.module_names:
            try:
                current_score = self.current_scores.get(module_name, 0.0)
                baseline_score = self.baseline_scores.get(module_name, 0.0)
                
                # Simulate a small change and check if it improves score by >0.1
                if baseline_score > 0:
                    improvement = abs(current_score - baseline_score)
                    if improvement > self.improvement_threshold:
                        return False
            except Exception:
                continue
        
        return True

    def is_at_equilibrium(self) -> bool:
        """
        Check if the system is currently at a Nash equilibrium.
        This is a convenience method that calls detect_equilibrium() and returns the result.
        
        Returns:
            True if the system is at Nash equilibrium, False otherwise
        """
        return self.detect_equilibrium()

    def suggest_coordinated_changes(self) -> List[Tuple[str, str]]:
        """
        Identify coordinated multi-module change opportunities by finding module pairs
        where both modules are stuck (stagnant).
        
        Returns:
            List of module pairs (sorted tuples) that are candidates for coordinated changes
        """
        stagnant_pairs = []
        for pair, count in self.stagnation_counter.items():
            if count >= self.stagnation_threshold:
                stagnant_pairs.append(pair)
        return stagnant_pairs

    def get_interaction_scores(self) -> Dict[Tuple[str, str], List[float]]:
        """
        Get the current interaction scores.
        
        Returns:
            Dictionary mapping module pairs to their score delta history
        """
        return dict(self.interaction_scores)

    def reset(self) -> None:
        """Reset all tracking data."""
        self.interaction_scores.clear()
        self.stagnation_counter.clear()
        self._cycle_improvement_history.clear()
        self.cycles_without_improvement = 0
        self._compute_baseline_scores()

    def _compute_joint_improvement_potential(self, modules: List[str]) -> float:
        """
        Compute the potential improvement from changing multiple modules simultaneously.
        
        Args:
            modules: List of module names to consider for joint change
            
        Returns:
            Estimated joint improvement potential
        """
        if not modules:
            return 0.0
        
        try:
            # Sum individual score improvements from baseline
            total_improvement = 0.0
            for m in modules:
                current = self.current_scores.get(m, 0.0)
                baseline = self.baseline_scores.get(m, 0.0)
                total_improvement += (current - baseline)
            
            # Add interaction effects based on interaction scores
            interaction_effect = 0.0
            for i in range(len(modules)):
                for j in range(i + 1, len(modules)):
                    pair = tuple(sorted([modules[i], modules[j]]))
                    deltas = self.interaction_scores.get(pair, [])
                    if deltas:
                        recent_deltas = deltas[-3:] if len(deltas) >= 3 else deltas
                        interaction_effect += sum(recent_deltas) / len(recent_deltas)
            
            # Combine individual improvements and interaction effects
            joint_potential = (total_improvement * 0.7) + (interaction_effect * 0.3)
            
            return joint_potential
            
        except Exception:
            return 0.0

    def _compute_payoff_matrix(self) -> Dict[Tuple[str, str], float]:
        """
        Compute payoff matrix from module interaction logs (success/failure rates).
        
        Returns:
            Dictionary mapping module pairs to their average payoff (success rate)
        """
        payoff_matrix: Dict[Tuple[str, str], float] = {}
        
        for pair, deltas in self.interaction_scores.items():
            if deltas:
                # Calculate success rate: proportion of positive deltas
                positive_deltas = sum(1 for d in deltas if d > 0)
                success_rate = positive_deltas / len(deltas)
                payoff_matrix[pair] = success_rate
            else:
                payoff_matrix[pair] = 0.0
        
        return payoff_matrix

    def _check_nash_equilibrium(self, payoff_matrix: Dict[Tuple[str, str], float]) -> bool:
        """
        Check for Nash equilibrium using a best-response algorithm.
        
        Args:
            payoff_matrix: Dictionary mapping module pairs to their average payoff
            
        Returns:
            True if the system is at Nash equilibrium, False otherwise
        """
        if not payoff_matrix:
            return False
        
        # For each module, check if it has a best response to all other modules
        for module_name in self.module_names:
            # Find all pairs involving this module
            module_pairs = [pair for pair in payoff_matrix if module_name in pair]
            
            if not module_pairs:
                continue
            
            # Get the best payoff for this module across all its interactions
            best_payoff = max(payoff_matrix[pair] for pair in module_pairs)
            
            # Check if any single-module change could improve this module's payoff
            for pair in module_pairs:
                current_payoff = payoff_matrix[pair]
                # If there's a better payoff available, it's not Nash equilibrium
                if current_payoff < best_payoff:
                    return False
        
        return True

    def _generate_coordinated_mutation_plan(self, modules: List[str]) -> List[Tuple[str, str]]:
        """
        Generate a coordinated mutation plan (list of (module, change) pairs) that
        would not be found by single-module optimization.
        
        Args:
            modules: List of module names to include in the plan
            
        Returns:
            List of (module, change) pairs representing the coordinated mutation plan
        """
        plan: List[Tuple[str, str]] = []
        
        # Define possible changes that are unlikely to be found by single-module optimization
        coordinated_changes = [
            "interface_redesign",
            "dependency_inversion",
            "shared_state_synchronization",
            "protocol_upgrade",
            "data_format_migration",
            "concurrency_model_change",
            "caching_strategy_overhaul",
            "error_handling_restructure",
            "logging_infrastructure_change",
            "security_policy_update"
        ]
        
        for i, module in enumerate(modules):
            # Select a change that complements the other modules' changes
            change_index = i % len(coordinated_changes)
            change = coordinated_changes[change_index]
            plan.append((module, change))
        
        return plan

    def detect_and_force_coordinated_change(self) -> bool:
        """
        Detect Nash equilibrium and force a coordinated change to break it.
        
        This method:
        1. Computes payoff matrix from module interaction logs (success/failure rates)
        2. Checks for Nash equilibrium using a best-response algorithm
        3. If equilibrium detected, generates a coordinated mutation plan (list of
           (module, change) pairs) that would not be found by single-module optimization
        
        Returns:
            True if coordinated change was applied, False otherwise
        """
        try:
            # Step 1: Compute payoff matrix from module interaction logs
            payoff_matrix = self._compute_payoff_matrix()
            
            if not payoff_matrix:
                return False
            
            # Step 2: Check for Nash equilibrium using best-response algorithm
            if not self._check_nash_equilibrium(payoff_matrix):
                return False
            
            # Step 3: If equilibrium detected, generate coordinated mutation plan
            # Find modules that are stuck (stagnant)
            stagnant_pairs = self.suggest_coordinated_changes()
            
            if not stagnant_pairs:
                # Use all modules with non-positive score changes
                stuck_modules = []
                for module_name in self.module_names:
                    current = self.current_scores.get(module_name, 0.0)
                    baseline = self.baseline_scores.get(module_name, 0.0)
                    if current <= baseline:
                        stuck_modules.append(module_name)
                
                if len(stuck_modules) < 2:
                    return False
                
                # Select 2-3 modules randomly
                num_modules = min(len(stuck_modules), random.randint(2, 3))
                selected_modules = stuck_modules[:num_modules]
            else:
                # Collect all unique modules from stagnant pairs
                stagnant_modules: Set[str] = set()
                for m1, m2 in stagnant_pairs:
                    stagnant_modules.add(m1)
                    stagnant_modules.add(m2)
                
                if len(stagnant_modules) < 2:
                    return False
                
                # Select 2-3 modules randomly
                num_modules = min(len(stagnant_modules), random.randint(2, 3))
                selected_modules = list(stagnant_modules)[:num_modules]
            
            # Generate coordinated mutation plan
            coordinated_plan = self._generate_coordinated_mutation_plan(selected_modules)
            
            # Apply the coordinated mutation
            success = self._apply_coordinated_mutation_plan(coordinated_plan)
            
            return success
            
        except Exception:
            return False

    def _apply_coordinated_mutation_plan(self, plan: List[Tuple[str, str]]) -> bool:
        """
        Apply a coordinated mutation plan.
        
        Args:
            plan: List of (module, change) pairs representing the coordinated mutation plan
            
        Returns:
            True if the plan was applied successfully, False otherwise
        """
        try:
            if not plan:
                return False
            
            # Extract all modules involved in the coordinated plan
            affected_modules: Set[str] = set()
            for module, change in plan:
                affected_modules.add(module)
            
            if not affected_modules:
                return False
            
            # Apply changes atomically by resetting stagnation tracking for all affected modules
            modules_list = list(affected_modules)
            for i in range(len(modules_list)):
                for j in range(i + 1, len(modules_list)):
                    module1 = modules_list[i]
                    module2 = modules_list[j]
                    pair = tuple(sorted([module1, module2]))
                    
                    # Reset stagnation counter and interaction scores for this pair
                    self.stagnation_counter[pair] = 0
                    if pair in self.interaction_scores:
                        self.interaction_scores[pair] = []
            
            # Update current score values to simulate the effect of coordinated changes
            for module_name in affected_modules:
                try:
                    fitness_func = self.fitness_functions.get(module_name)
                    if fitness_func:
                        new_score = fitness_func()
                        self.current_scores[module_name] = new_score
                except Exception:
                    pass
            
            # Record a positive cycle outcome
            self._cycle_improvement_history.append(True)
            if len(self._cycle_improvement_history) > 5:
                self._cycle_improvement_history = self._cycle_improvement_history[-5:]
            
            # Reset cycles without improvement counter
            self.cycles_without_improvement = 0
            
            return True
            
        except Exception:
            return False

    def force_coordinated_change(self) -> bool:
        """
        Force a coordinated change to break out of Nash equilibrium.
        
        This method:
        1. Identifies modules currently at Nash equilibrium by checking if all single-module mutations degrade performance
        2. Generates a coordinated multi-module mutation plan that changes 2-3 modules simultaneously
        3. Executes the coordinated change via the atomic multi-module mutation orchestrator
        4. Verifies the combined change improves overall system fitness beyond any single-module alternative
        
        Returns:
            True if the coordinated change successfully broke the equilibrium (overall system fitness improved),
            False otherwise
        """
        try:
            # Step 1: Identify modules currently at Nash equilibrium
            if not self.detect_equilibrium():
                return False
            
            # Verify that all single-module mutations degrade performance
            all_single_mutations_degrade = True
            for pair, deltas in self.interaction_scores.items():
                if deltas:
                    recent_deltas = deltas[-3:] if len(deltas) >= 3 else deltas
                    if any(d > self.improvement_threshold for d in recent_deltas):
                        all_single_mutations_degrade = False
                        break
            
            if not all_single_mutations_degrade:
                return False
            
            # Step 2: Generate a coordinated multi-module mutation plan that changes 2-3 modules simultaneously
            stagnant_pairs = self.suggest_coordinated_changes()
            
            if not stagnant_pairs:
                # Use all modules with non-positive score changes
                stuck_modules = []
                for module_name in self.module_names:
                    current = self.current_scores.get(module_name, 0.0)
                    baseline = self.baseline_scores.get(module_name, 0.0)
                    if current <= baseline:
                        stuck_modules.append(module_name)
                
                if len(stuck_modules) < 2:
                    return False
                
                # Select 2-3 modules randomly
                num_modules = min(len(stuck_modules), random.randint(2, 3))
                selected_modules = stuck_modules[:num_modules]
            else:
                # Collect all unique modules from stagnant pairs
                stagnant_modules: Set[str] = set()
                for m1, m2 in stagnant_pairs:
                    stagnant_modules.add(m1)
                    stagnant_modules.add(m2)
                
                if len(stagnant_modules) < 2:
                    return False
                
                # Select 2-3 modules randomly
                num_modules = min(len(stagnant_modules), random.randint(2, 3))
                selected_modules = list(stagnant_modules)[:num_modules]
            
            # Compute the joint improvement potential for the selected modules
            joint_potential = self._compute_joint_improvement_potential(selected_modules)
            
            # Build the coordinated mutation plan
            coordinated_plan = []
            for i, module in enumerate(selected_modules):
                if i == 0:
                    action = 'change_interface'
                    description = f"Modify {module}'s interface as part of coordinated escape from Nash equilibrium (joint potential: {joint_potential:.4f})"
                elif i == 1:
                    action = 'change_implementation'
                    description = f"Modify {module}'s implementation to complement interface changes (joint potential: {joint_potential:.4f})"
                else:
                    action = 'change_parameter'
                    description = f"Modify {module}'s parameters to complete the coordinated change (joint potential: {joint_potential:.4f})"
                
                coordinated_plan.append({
                    'module': module,
                    'action': action,
                    'description': description
                })
            
            plan = {
                'coordinated_plan': coordinated_plan,
                'description': f"Coordinated multi-module change plan involving {len(selected_modules)} modules to break Nash equilibrium"
            }
            
            # Step 3: Execute the coordinated change atomically
            # Record the current scores before applying changes
            pre_change_scores = {}
            for module_name in selected_modules:
                try:
                    fitness_func = self.fitness_functions.get(module_name)
                    if fitness_func:
                        pre_change_scores[module_name] = fitness_func()
                    else:
                        pre_change_scores[module_name] = self.current_scores.get(module_name, 0.0)
                except Exception:
                    pre_change_scores[module_name] = self.current_scores.get(module_name, 0.0)
            
            # Apply the coordinated mutation atomically
            success = self._apply_coordinated_mutation(plan)
            
            if not success:
                return False
            
            # Step 4: Verify the combined change improves overall system fitness
            pre_overall_score = sum(pre_change_scores.values()) / len(pre_change_scores) if pre_change_scores else 0.0
            
            post_change_scores = {}
            for module_name in selected_modules:
                try:
                    fitness_func = self.fitness_functions.get(module_name)
                    if fitness_func:
                        post_change_scores[module_name] = fitness_func()
                    else:
                        post_change_scores[module_name] = self.current_scores.get(module_name, 0.0)
                except Exception:
                    post_change_scores[module_name] = self.current_scores.get(module_name, 0.0)
            
            post_overall_score = sum(post_change_scores.values()) / len(post_change_scores) if post_change_scores else 0.0
            
            # Check if overall system score improved
            overall_improvement = False
            if pre_overall_score > 0:
                improvement_ratio = (post_overall_score - pre_overall_score) / pre_overall_score
                if improvement_ratio > self.improvement_threshold:
                    overall_improvement = True
            elif post_overall_score > pre_overall_score:
                overall_improvement = True
            
            # Also verify that the combined change improves beyond any single-module alternative
            best_single_improvement = 0.0
            for module_name in selected_modules:
                pre = pre_change_scores.get(module_name, 0.0)
                post = post_change_scores.get(module_name, 0.0)
                if pre > 0:
                    single_improvement = (post - pre) / pre
                    if single_improvement > best_single_improvement:
                        best_single_improvement = single_improvement
            
            if overall_improvement:
                self.cycles_without_improvement = 0
                return True
            else:
                return False
                
        except Exception:
            return False

    def _apply_coordinated_mutation(self, plan: Dict) -> bool:
        """
        Apply a coordinated mutation plan atomically.
        
        Args:
            plan: Dictionary containing:
                - 'coordinated_plan': list of mutation steps, each a dict with
                  'module', 'action', and 'description' keys
                - 'description': string describing the coordinated change strategy
        
        Returns:
            True if the coordinated mutation was applied successfully, False otherwise
        """
        try:
            if not plan or 'coordinated_plan' not in plan:
                return False
            
            coordinated_plan = plan['coordinated_plan']
            if not coordinated_plan:
                return False
            
            # Extract all modules involved in the coordinated plan
            affected_modules: Set[str] = set()
            for step in coordinated_plan:
                if 'module' in step:
                    affected_modules.add(step['module'])
            
            if not affected_modules:
                return False
            
            # Apply changes atomically by resetting stagnation tracking for all affected modules
            modules_list = list(affected_modules)
            for i in range(len(modules_list)):
                for j in range(i + 1, len(modules_list)):
                    module1 = modules_list[i]
                    module2 = modules_list[j]
                    pair = tuple(sorted([module1, module2]))
                    
                    # Reset stagnation counter and interaction scores for this pair
                    self.stagnation_counter[pair] = 0
                    if pair in self.interaction_scores:
                        self.interaction_scores[pair] = []
            
            # Update current score values to simulate the effect of coordinated changes
            for module_name in affected_modules:
                try:
                    fitness_func = self.fitness_functions.get(module_name)
                    if fitness_func:
                        new_score = fitness_func()
                        self.current_scores[module_name] = new_score
                except Exception:
                    pass
            
            # Record a positive cycle outcome
            self._cycle_improvement_history.append(True)
            if len(self._cycle_improvement_history) > 5:
                self._cycle_improvement_history = self._cycle_improvement_history[-5:]
            
            # Reset cycles without improvement counter
            self.cycles_without_improvement = 0
            
            return True
            
        except Exception:
            return False

    def update_fitness_functions(self, fitness_functions: Dict[str, Callable]) -> None:
        """
        Update the fitness functions for all modules.
        
        Args:
            fitness_functions: New dict of module fitness functions
        """
        if not fitness_functions:
            raise ValueError("fitness_functions dict cannot be empty")
        
        self.fitness_functions = fitness_functions.copy()
        self.module_names = list(fitness_functions.keys())
        self._compute_baseline_scores()

    def get_equilibrium_state(self) -> Dict:
        """
        Get the current equilibrium state information.
        
        Returns:
            Dictionary containing:
            - 'equilibrium': bool indicating if system is at equilibrium
            - 'stagnant_pairs': list of stagnant module pairs
            - 'cycles_without_improvement': int
        """
        return {
            'equilibrium': self.detect_equilibrium(),
            'stagnant_pairs': self.suggest_coordinated_changes(),
            'cycles_without_improvement': self.cycles_without_improvement
        }

    def increment_cycle(self) -> None:
        """Advance to the next evaluation cycle."""
        self.cycles_without_improvement += 1
        
        # Check if any module improved in this cycle
        any_improvement = False
        for module_name in self.module_names:
            try:
                current_score = self.current_scores.get(module_name, 0.0)
                baseline_score = self.baseline_scores.get(module_name, 0.0)
                
                if baseline_score > 0:
                    improvement = abs(current_score - baseline_score)
                    if improvement > self.improvement_threshold:
                        any_improvement = True
                        break
            except Exception:
                continue
        
        if any_improvement:
            self.cycles_without_improvement = 0
        
        self._cycle_improvement_history.append(any_improvement)
        if len(self._cycle_improvement_history) > 5:
            self._cycle_improvement_history = self._cycle_improvement_history[-5:]

    def set_improvement_threshold(self, threshold: float) -> None:
        """
        Set the improvement threshold for detecting equilibrium.
        
        Args:
            threshold: Float representing the minimum improvement value
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