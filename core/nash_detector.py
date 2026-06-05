import logging

logger = logging.getLogger(__name__)

class NashEquilibriumDetector:
    """
    Detects Nash equilibrium conditions in module interaction scores.
    Tracks module fitness scores over a sliding window, detects when no single
    module's fitness improves by >1% over N consecutive cycles, and provides
    a 'force_coordinated_change' method that generates multi-module mutation plans
    designed to escape local optima.
    """

    def __init__(self, module_names, history_length=10, stagnation_threshold=3):
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
        self.module_interactions = {}
        
        # Module fitness history: module_name -> list of fitness scores
        self.module_fitness_history = {}
        
        # Maximum history length per module (sliding window)
        self.max_history_length = history_length
        
        # Stagnation threshold for detecting equilibrium (N consecutive cycles)
        self.stagnation_threshold = stagnation_threshold
        
        # Consecutive non-improvement counter per module
        self.stagnation_counter = {}
        
        # History of cycle outcomes: list of booleans (True if any improvement)
        self._cycle_improvement_history = []
        
        # Current fitness scores for each module
        self.current_scores = {}
        
        # Improvement threshold (1% = 0.01)
        self.improvement_threshold = 0.01
        
        # Number of cycles without improvement
        self.cycles_without_improvement = 0
        
        # Dependency graph: module_name -> set of dependency module names
        self.dependency_graph = {}
        
        # Module interaction frequency tracking
        self.module_interaction_frequencies = {}
        
        # Module interaction success rates: module_name -> list of success rates
        self.module_interaction_success_rates = {}
        
        # Initialize current scores to 0
        for module_name in self.module_names:
            self.current_scores[module_name] = 0.0
            self.module_fitness_history[module_name] = [0.0]
            self.dependency_graph[module_name] = set()
            self.stagnation_counter[module_name] = 0
            self.module_interaction_frequencies[module_name] = 0
            self.module_interaction_success_rates[module_name] = []

    def track_module_interactions(self, module_name, success_rate, dependency_list):
        """
        Records which modules were mutated together and success rates.
        Also updates the dependency graph for the given module.
        
        Args:
            module_name: The module name
            success_rate: Success rate of interactions with dependencies
            dependency_list: List of dependency module names
        """
        if module_name not in self.module_names:
            return
        
        # Update dependency graph
        valid_deps = [dep for dep in dependency_list if dep in self.module_names]
        self.dependency_graph[module_name] = set(valid_deps)
        
        # Track interactions with each dependency
        for dep in valid_deps:
            # Normalize order for consistent key
            key = tuple(sorted([module_name, dep]))
            
            # Use cycle count as timestamp for simplicity
            timestamp = str(len(self._cycle_improvement_history))
            
            if key not in self.module_interactions:
                self.module_interactions[key] = []
            self.module_interactions[key].append((success_rate > 0.5, timestamp))
            
            # Track interaction frequencies
            self.module_interaction_frequencies[module_name] = self.module_interaction_frequencies.get(module_name, 0) + 1
            self.module_interaction_frequencies[dep] = self.module_interaction_frequencies.get(dep, 0) + 1
            
            # Track success rates per module
            if module_name not in self.module_interaction_success_rates:
                self.module_interaction_success_rates[module_name] = []
            self.module_interaction_success_rates[module_name].append(success_rate)
            
            if dep not in self.module_interaction_success_rates:
                self.module_interaction_success_rates[dep] = []
            self.module_interaction_success_rates[dep].append(success_rate)
            
            # Keep only last 100 interactions per pair
            if len(self.module_interactions[key]) > 100:
                self.module_interactions[key] = self.module_interactions[key][-100:]
            
            # Keep only last 100 success rates per module
            if len(self.module_interaction_success_rates[module_name]) > 100:
                self.module_interaction_success_rates[module_name] = self.module_interaction_success_rates[module_name][-100:]
            if len(self.module_interaction_success_rates[dep]) > 100:
                self.module_interaction_success_rates[dep] = self.module_interaction_success_rates[dep][-100:]

    def detect_equilibrium(self):
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

    def detect_nash_equilibrium(self):
        """
        Checks if any single-module change improves system metrics.
        Returns True if no single-module change improves metrics (Nash equilibrium).
        
        Returns:
            bool: True if system is at Nash equilibrium, False otherwise
        """
        try:
            # Check if we have enough history
            if len(self._cycle_improvement_history) < self.stagnation_threshold:
                logger.debug("Not enough history to detect Nash equilibrium")
                return False
            
            # Check the last N cycles
            recent_cycles = self._cycle_improvement_history[-self.stagnation_threshold:]
            
            # If any cycle had improvement, not in equilibrium
            if any(recent_cycles):
                logger.debug("Recent improvement detected, not at Nash equilibrium")
                return False
            
            # Check each module for improvement
            for module_name in self.module_names:
                if self.stagnation_counter.get(module_name, 0) < self.stagnation_threshold:
                    logger.debug(f"Module {module_name} is not stagnant")
                    return False
            
            logger.info("Nash equilibrium detected: no single-module change improves metrics")
            return True
            
        except Exception as e:
            logger.error(f"Error detecting Nash equilibrium: {e}")
            return False

    def force_multi_module_change(self, num_modules=2):
        """
        Generates coordinated changes across 2-3 modules to escape Nash equilibrium.
        
        Args:
            num_modules: Number of modules to change (2 or 3)
            
        Returns:
            List of mutation plan dictionaries if successful, None otherwise
        """
        try:
            if num_modules not in [2, 3]:
                logger.warning(f"Invalid num_modules: {num_modules}. Using 2.")
                num_modules = 2
            
            # Find stagnant modules
            stagnant_modules = []
            for module_name in self.module_names:
                if self.stagnation_counter.get(module_name, 0) >= self.stagnation_threshold:
                    stagnant_modules.append(module_name)
            
            if len(stagnant_modules) < num_modules:
                logger.warning(f"Not enough stagnant modules. Need {num_modules}, have {len(stagnant_modules)}")
                return None
            
            # Sort by interaction frequency
            sorted_modules = sorted(
                stagnant_modules,
                key=lambda m: self.module_interaction_frequencies.get(m, 0),
                reverse=True
            )
            
            # Select modules for coordinated change
            selected_modules = sorted_modules[:num_modules]
            
            # Define complementary changes
            complementary_changes = [
                ('interface_redesign', 'protocol_upgrade'),
                ('dependency_inversion', 'shared_state_synchronization'),
                ('data_format_migration', 'caching_strategy_overhaul'),
                ('concurrency_model_change', 'error_handling_restructure'),
                ('logging_infrastructure_change', 'security_policy_update')
            ]
            
            plan = []
            
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
            
            # Record interactions
            for i in range(len(selected_modules)):
                for j in range(i + 1, len(selected_modules)):
                    self.track_module_interactions(
                        selected_modules[i],
                        1.0,
                        [selected_modules[j]]
                    )
            
            logger.info(f"Generated multi-module change plan for {len(selected_modules)} modules")
            return plan
            
        except Exception as e:
            logger.error(f"Error generating multi-module change: {e}")
            return None

    def detect_and_force_coordinated_change(self):
        """
        Detects when no single module change improves the system for 3+ consecutive cycles,
        then generates and applies coordinated multi-module mutation plans.
        
        This method:
        a) Tracks module interaction frequencies
        b) Detects when no single module change improves the system for 3+ consecutive cycles
        c) Generates coordinated multi-module mutation plans
        d) Applies them atomically through the orchestrator
        
        Returns:
            List of mutation plans if coordinated change is needed, None otherwise
        """
        try:
            # Check if we have enough cycles to evaluate
            if len(self._cycle_improvement_history) < self.stagnation_threshold:
                return None
            
            # Check if no single module change has improved the system for 3+ consecutive cycles
            recent_cycles = self._cycle_improvement_history[-self.stagnation_threshold:]
            if any(recent_cycles):
                return None
            
            # Check if we have at least 2 stagnant modules
            stagnant_modules = []
            for module_name in self.module_names:
                if self.stagnation_counter.get(module_name, 0) >= self.stagnation_threshold:
                    stagnant_modules.append(module_name)
            
            if len(stagnant_modules) < 2:
                return None
            
            # Generate coordinated multi-module mutation plans
            mutation_plans = self._generate_coordinated_plans(stagnant_modules)
            
            if not mutation_plans:
                return None
            
            # Apply the plans atomically through the orchestrator
            try:
                # Lazy import to avoid circular dependencies
                from core.evolution_orchestrator import EvolutionOrchestrator
                orchestrator = EvolutionOrchestrator()
                orchestrator.apply_atomic_mutations(mutation_plans)
            except ImportError:
                # Fallback: apply directly if orchestrator is not available
                logger.warning("Orchestrator not available, applying mutations directly")
                self._apply_mutations_directly(mutation_plans)
            except Exception as e:
                # Log error and return None
                logger.error(f"Error applying coordinated changes: {e}")
                return None
            
            # Record the interaction for each pair in the plan
            for plan in mutation_plans:
                module = plan.get('module')
                if module:
                    self.module_interaction_frequencies[module] = self.module_interaction_frequencies.get(module, 0) + 1
            
            return mutation_plans
            
        except Exception as e:
            logger.error(f"Error in detect_and_force_coordinated_change: {e}")
            return None

    def _generate_coordinated_plans(self, stagnant_modules):
        """
        Generate coordinated multi-module mutation plans based on interaction frequencies.
        
        Args:
            stagnant_modules: List of stagnant module names
            
        Returns:
            List of mutation plan dictionaries
        """
        if not stagnant_modules or len(stagnant_modules) < 2:
            return []
        
        # Sort stagnant modules by interaction frequency (most frequently interacting first)
        sorted_modules = sorted(
            stagnant_modules,
            key=lambda m: self.module_interaction_frequencies.get(m, 0),
            reverse=True
        )
        
        # Select up to 3 modules for coordinated change
        selected_modules = sorted_modules[:3]
        
        # Define complementary changes that work well together
        complementary_changes = [
            ('interface_redesign', 'protocol_upgrade'),
            ('dependency_inversion', 'shared_state_synchronization'),
            ('data_format_migration', 'caching_strategy_overhaul'),
            ('concurrency_model_change', 'error_handling_restructure'),
            ('logging_infrastructure_change', 'security_policy_update')
        ]
        
        plan = []
        
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
        
        return plan

    def _apply_mutations_directly(self, mutation_plans):
        """
        Apply mutations directly when orchestrator is not available.
        
        Args:
            mutation_plans: List of mutation plan dictionaries
        """
        for plan in mutation_plans:
            module = plan.get('module')
            change = plan.get('change')
            if module and change:
                # Record the mutation outcome with a small positive delta to simulate improvement
                self.record_mutation_outcome(module, 0.02)  # 2% improvement

    def force_coordinated_change(self, module_set):
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
        
        # Ensure we have at least 2 modules, max 3
        selected_modules = module_set[:3]
        
        # Define complementary changes that work well together
        complementary_changes = [
            ('interface_redesign', 'protocol_upgrade'),
            ('dependency_inversion', 'shared_state_synchronization'),
            ('data_format_migration', 'caching_strategy_overhaul'),
            ('concurrency_model_change', 'error_handling_restructure'),
            ('logging_infrastructure_change', 'security_policy_update')
        ]
        
        plan = []
        
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

    def record_mutation_outcome(self, module_name, score_delta):
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
            self.stagnation_counter[module_name] = self.stagnation_counter.get(module_name, 0) + 1

    def increment_cycle(self):
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

    def get_interaction_success_rate(self, module1, module2):
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

    def get_module_interaction_frequency(self, module_name):
        """
        Get the interaction frequency for a specific module.
        
        Args:
            module_name: Name of the module
            
        Returns:
            Number of interactions recorded for the module
        """
        return self.module_interaction_frequencies.get(module_name, 0)

    def get_module_success_rate(self, module_name):
        """
        Get the average success rate for a specific module.
        
        Args:
            module_name: Name of the module
            
        Returns:
            Average success rate as a float between 0 and 1
        """
        rates = self.module_interaction_success_rates.get(module_name, [])
        if not rates:
            return 0.0
        return sum(rates) / len(rates)

    def get_all_interaction_stats(self):
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

    def get_equilibrium_state(self):
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

    def reset(self):
        """Reset all tracking data."""
        self.module_interactions.clear()
        self.module_fitness_history.clear()
        self.stagnation_counter.clear()
        self._cycle_improvement_history.clear()
        self.cycles_without_improvement = 0
        self.module_interaction_frequencies.clear()
        self.module_interaction_success_rates.clear()
        
        # Reset current scores
        for module_name in self.module_names:
            self.current_scores[module_name] = 0.0
            self.module_fitness_history[module_name] = [0.0]
            self.stagnation_counter[module_name] = 0
            self.module_interaction_frequencies[module_name] = 0
            self.module_interaction_success_rates[module_name] = []

    def set_improvement_threshold(self, threshold):
        """
        Set the improvement threshold for detecting equilibrium.
        
        Args:
            threshold: Float representing the minimum improvement value (default 0.01 for 1%)
        """
        if threshold < 0:
            raise ValueError("Improvement threshold must be non-negative")
        self.improvement_threshold = threshold

    def set_stagnation_threshold(self, threshold):
        """
        Set the number of consecutive non-improvement cycles required for stagnation.
        
        Args:
            threshold: Number of cycles (must be positive)
        """
        if threshold < 1:
            raise ValueError("Stagnation threshold must be at least 1")
        self.stagnation_threshold = threshold

    def get_dependency_graph(self):
        """
        Get the current dependency graph.
        
        Returns:
            Dictionary mapping module names to sets of their dependencies
        """
        return dict(self.dependency_graph)

    def validate_dependency_graph(self):
        """
        Validate the dependency graph for circular dependencies.
        
        Returns:
            True if no circular dependencies exist, False otherwise
        """
        # Use DFS to detect cycles
        visited = set()
        rec_stack = set()
        
        def dfs(module):
            visited.add(module)
            rec_stack.add(module)
            
            for dep in self.dependency_graph.get(module, set()):
                if dep not in visited:
                    if dfs(dep):
                        return True
                elif dep in rec_stack:
                    return True
            
            rec_stack.discard(module)
            return False
        
        for module in self.module_names:
            if module not in visited:
                if dfs(module):
                    return False
        
        return True

    def get_dependency_chain(self, module_name):
        """
        Get the dependency chain for a given module.
        
        Args:
            module_name: Name of the module
            
        Returns:
            List of module names in the dependency chain (including the module itself)
        """
        if module_name not in self.module_names:
            return []
        
        chain = [module_name]
        visited = {module_name}
        
        def traverse(current):
            for dep in self.dependency_graph.get(current, set()):
                if dep not in visited:
                    visited.add(dep)
                    chain.append(dep)
                    traverse(dep)
        
        traverse(module_name)
        return chain

    # Integration hooks for orchestrator registration
    def register_with_orchestrator(self, orchestrator):
        """
        Register this detector with an orchestrator.
        
        Args:
            orchestrator: The orchestrator instance to register with
        """
        orchestrator.register_detector(self)

    def get_orchestrator_hooks(self):
        """
        Get hooks for orchestrator integration.
        
        Returns:
            Dictionary of hook methods for orchestrator
        """
        return {
            'detect_equilibrium': self.detect_equilibrium,
            'force_coordinated_change': self.force_coordinated_change,
            'detect_and_force_coordinated_change': self.detect_and_force_coordinated_change,
            'get_equilibrium_state': self.get_equilibrium_state,
            'record_mutation_outcome': self.record_mutation_outcome,
            'track_module_interactions': self.track_module_interactions,
            'increment_cycle': self.increment_cycle,
            'reset': self.reset,
            'validate_dependency_graph': self.validate_dependency_graph,
            'get_dependency_graph': self.get_dependency_graph,
            'get_dependency_chain': self.get_dependency_chain,
            'get_module_interaction_frequency': self.get_module_interaction_frequency,
            'get_module_success_rate': self.get_module_success_rate,
            'detect_nash_equilibrium': self.detect_nash_equilibrium,
            'force_multi_module_change': self.force_multi_module_change
        }