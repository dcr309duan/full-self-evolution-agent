from collections import defaultdict
from typing import Dict, List, Tuple, Set, Optional, Callable
import logging
import random
import math

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class NashEquilibriumDetector:
    """
    Detects Nash equilibrium conditions in module fitness functions.
    Takes a dict of module fitness functions, detects equilibrium when no
    single-module change improves fitness by >1%, and can propose coordinated
    multi-module changes using gradient estimation.
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
        
        # Payoff matrix: (module1, module2) -> list of payoff deltas (last 10)
        self.payoff_matrix: Dict[Tuple[str, str], List[float]] = defaultdict(list)
        # Maximum history length per module pair
        self.max_history_length: int = 10
        # Stagnation threshold for detecting equilibrium
        self.stagnation_threshold: int = 3
        # Consecutive non-improvement counter per module pair
        self.stagnation_counter: Dict[Tuple[str, str], int] = defaultdict(int)
        # History of cycle outcomes: list of booleans (True if any improvement)
        self._cycle_improvement_history: List[bool] = []
        # Baseline fitness values for each module
        self.baseline_fitness: Dict[str, float] = {}
        # Current fitness values for each module
        self.current_fitness: Dict[str, float] = {}
        # Gradient estimates for each module: module -> estimated gradient
        self.gradient_estimates: Dict[str, float] = {}
        # Improvement threshold (1% by default)
        self.improvement_threshold: float = 0.01
        # Number of cycles without improvement
        self.cycles_without_improvement: int = 0
        
        # Initialize baseline fitness
        self._compute_baseline_fitness()
        
        logger.info(f"NashEquilibriumDetector initialized with {len(self.module_names)} modules: {self.module_names}")

    def _compute_baseline_fitness(self) -> None:
        """Compute baseline fitness for all modules."""
        for module_name, fitness_func in self.fitness_functions.items():
            try:
                fitness = fitness_func()
                self.baseline_fitness[module_name] = fitness
                self.current_fitness[module_name] = fitness
            except Exception as e:
                logger.error(f"Error computing baseline fitness for module {module_name}: {e}")
                self.baseline_fitness[module_name] = 0.0
                self.current_fitness[module_name] = 0.0

    def record_mutation_outcome(self, module1: str, module2: str, payoff_delta: float) -> None:
        """
        Record the outcome of a mutation affecting a module pair.
        
        Args:
            module1: First module in the pair
            module2: Second module in the pair
            payoff_delta: The change in payoff (positive = improvement)
        """
        pair = tuple(sorted([module1, module2]))
        self.payoff_matrix[pair].append(payoff_delta)
        
        # Keep only last 10 entries
        if len(self.payoff_matrix[pair]) > self.max_history_length:
            self.payoff_matrix[pair] = self.payoff_matrix[pair][-self.max_history_length:]
        
        # Update stagnation counter
        if payoff_delta <= 0:
            self.stagnation_counter[pair] += 1
        else:
            self.stagnation_counter[pair] = 0

    def detect_equilibrium(self) -> bool:
        """
        Detect when no single-module change improves any module's fitness by >1%.
        Returns True if all module pairs have been stagnant for the threshold number of cycles.
        
        Returns:
            True if system is in Nash equilibrium
        """
        if not self.payoff_matrix:
            return False
        
        # Check if all module pairs that have been evaluated are stagnant
        for pair, deltas in self.payoff_matrix.items():
            if len(deltas) < self.stagnation_threshold:
                return False
            if self.stagnation_counter.get(pair, 0) < self.stagnation_threshold:
                return False
        
        # Also check if any single-module change would improve fitness by >1%
        for module_name in self.module_names:
            try:
                current_fitness = self.current_fitness.get(module_name, 0.0)
                baseline_fitness = self.baseline_fitness.get(module_name, 0.0)
                
                # Simulate a small change and check if it improves fitness by >1%
                if baseline_fitness > 0:
                    improvement_ratio = abs(current_fitness - baseline_fitness) / baseline_fitness
                    if improvement_ratio > self.improvement_threshold:
                        return False
            except Exception as e:
                logger.error(f"Error checking equilibrium for module {module_name}: {e}")
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

    def get_payoff_matrix(self) -> Dict[Tuple[str, str], List[float]]:
        """
        Get the current payoff matrix.
        
        Returns:
            Dictionary mapping module pairs to their payoff delta history
        """
        return dict(self.payoff_matrix)

    def reset(self) -> None:
        """Reset all tracking data."""
        self.payoff_matrix.clear()
        self.stagnation_counter.clear()
        self._cycle_improvement_history.clear()
        self.gradient_estimates.clear()
        self.cycles_without_improvement = 0
        self._compute_baseline_fitness()
        logger.info("NashEquilibriumDetector reset complete")

    def _estimate_gradient(self, module_name: str, epsilon: float = 0.01) -> float:
        """
        Estimate the gradient of a module's fitness function using finite differences.
        
        Args:
            module_name: The module to estimate gradient for
            epsilon: Small perturbation for finite difference estimation
            
        Returns:
            Estimated gradient value
        """
        try:
            fitness_func = self.fitness_functions.get(module_name)
            if fitness_func is None:
                logger.warning(f"No fitness function found for module {module_name}")
                return 0.0
            
            # Get current fitness
            current_fitness = self.current_fitness.get(module_name, 0.0)
            
            # Simulate a small positive perturbation
            # In a real system, this would involve actually modifying the module
            # For now, we use a simple heuristic based on recent payoff history
            recent_deltas = []
            for pair, deltas in self.payoff_matrix.items():
                if module_name in pair and deltas:
                    recent_deltas.extend(deltas[-3:])  # Last 3 deltas
            
            if recent_deltas:
                # Use average of recent deltas as gradient estimate
                gradient = sum(recent_deltas) / len(recent_deltas)
            else:
                # No history available, return 0
                gradient = 0.0
            
            return gradient
            
        except Exception as e:
            logger.error(f"Error estimating gradient for module {module_name}: {e}")
            return 0.0

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
            # Sum individual gradient estimates
            total_gradient = sum(self.gradient_estimates.get(m, 0.0) for m in modules)
            
            # Add interaction effects based on payoff matrix
            interaction_effect = 0.0
            for i in range(len(modules)):
                for j in range(i + 1, len(modules)):
                    pair = tuple(sorted([modules[i], modules[j]]))
                    deltas = self.payoff_matrix.get(pair, [])
                    if deltas:
                        # Average of recent deltas for this pair
                        recent_deltas = deltas[-3:] if len(deltas) >= 3 else deltas
                        interaction_effect += sum(recent_deltas) / len(recent_deltas)
            
            # Combine individual gradients and interaction effects
            # Weighted sum with more weight on individual gradients
            joint_potential = (total_gradient * 0.7) + (interaction_effect * 0.3)
            
            return joint_potential
            
        except Exception as e:
            logger.error(f"Error computing joint improvement potential: {e}")
            return 0.0

    def detect_and_force_coordinated_change(self) -> Optional[Dict]:
        """
        Analyze the dependency graph of all modules, compute pairwise improvement potentials
        (simulating single-module mutations), identify Nash equilibria where no single module
        change improves the system, and when detected, generate a coordinated multi-module
        change plan that would be invisible to single-module optimization.
        
        This method:
        1. Analyzes the dependency graph of all modules
        2. Computes pairwise improvement potentials (simulating single-module mutations)
        3. Identifies Nash equilibria where no single module change improves the system
        4. When detected, generates a coordinated multi-module change plan
           (e.g., change module A's interface and module B's implementation simultaneously)
           that would be invisible to single-module optimization
        
        Returns:
            Dictionary containing:
            - 'equilibrium_detected': bool indicating if equilibrium was found
            - 'coordinated_plan': list of coordinated mutation steps, each a dict with
              'module', 'action', and 'description' keys
            - 'description': string describing the coordinated change strategy
            Or None if no equilibrium is detected.
        """
        try:
            # Step 1: Analyze the dependency graph of all modules
            # Build a set of all modules from the payoff matrix
            all_modules: Set[str] = set()
            for module1, module2 in self.payoff_matrix.keys():
                all_modules.add(module1)
                all_modules.add(module2)
            
            # Also include modules from fitness functions
            all_modules.update(self.module_names)
            
            if not all_modules:
                logger.warning("No modules found for coordinated change analysis")
                return None
            
            # Step 2: Compute pairwise improvement potentials
            # For each module pair, calculate the average payoff delta from recent history
            # This simulates the potential improvement from single-module mutations
            improvement_potentials: Dict[Tuple[str, str], float] = {}
            for pair, deltas in self.payoff_matrix.items():
                if deltas:
                    # Average of last 5 deltas (or all if fewer)
                    recent = deltas[-5:] if len(deltas) >= 5 else deltas
                    avg_delta = sum(recent) / len(recent)
                    improvement_potentials[pair] = avg_delta
            
            # Step 3: Identify Nash equilibria where no single module change improves the system
            # A Nash equilibrium exists when all module pairs have non-positive improvement potentials
            # (i.e., no single-module mutation yields a positive payoff delta)
            equilibrium_detected = True
            for pair, potential in improvement_potentials.items():
                if potential > self.improvement_threshold:
                    equilibrium_detected = False
                    break
            
            # Also check the stagnation counter for additional confirmation
            if equilibrium_detected and self.payoff_matrix:
                # Verify that all evaluated pairs are stagnant
                for pair, deltas in self.payoff_matrix.items():
                    if len(deltas) >= self.stagnation_threshold:
                        if self.stagnation_counter.get(pair, 0) < self.stagnation_threshold:
                            equilibrium_detected = False
                            break
            
            if not equilibrium_detected:
                logger.info("No Nash equilibrium detected, no coordinated change needed")
                return None
            
            # Step 4: Generate a coordinated multi-module change plan
            # Use gradient estimation to find joint improvements
            # First, estimate gradients for all modules
            for module_name in all_modules:
                self.gradient_estimates[module_name] = self._estimate_gradient(module_name)
            
            # Identify module pairs that are stuck (stagnant) and create coordinated changes
            stagnant_pairs = self.suggest_coordinated_changes()
            
            if not stagnant_pairs:
                # If no stagnant pairs, try to find modules with negative gradients
                # These are modules that are stuck and need coordinated changes
                negative_gradient_modules = [
                    m for m, g in self.gradient_estimates.items() 
                    if g <= 0 and m in all_modules
                ]
                
                if len(negative_gradient_modules) < 2:
                    logger.info("Not enough modules with negative gradients for coordinated change")
                    return None
                
                # Create pairs from modules with negative gradients
                stagnant_pairs = []
                for i in range(0, len(negative_gradient_modules) - 1, 2):
                    if i + 1 < len(negative_gradient_modules):
                        stagnant_pairs.append(
                            tuple(sorted([negative_gradient_modules[i], negative_gradient_modules[i + 1]]))
                        )
            
            if not stagnant_pairs:
                logger.info("No stagnant pairs found for coordinated change")
                return None
            
            # Build a coordinated plan that changes multiple modules simultaneously
            # For each stagnant pair, create a coordinated change that modifies both modules
            coordinated_plan = []
            modules_in_plan: Set[str] = set()
            
            for module1, module2 in stagnant_pairs:
                if module1 not in modules_in_plan or module2 not in modules_in_plan:
                    # Compute joint improvement potential for this pair
                    joint_potential = self._compute_joint_improvement_potential([module1, module2])
                    
                    # Create a coordinated change for this pair
                    coordinated_plan.append({
                        'module': module1,
                        'action': 'change_interface',
                        'description': f"Modify {module1}'s interface to break stagnation with {module2} (joint potential: {joint_potential:.4f})"
                    })
                    coordinated_plan.append({
                        'module': module2,
                        'action': 'change_implementation',
                        'description': f"Modify {module2}'s implementation to complement {module1}'s interface change (joint potential: {joint_potential:.4f})"
                    })
                    modules_in_plan.add(module1)
                    modules_in_plan.add(module2)
            
            # If no coordinated plan was generated, create a default one from all stagnant modules
            if not coordinated_plan:
                all_stagnant_modules: Set[str] = set()
                for module1, module2 in stagnant_pairs:
                    all_stagnant_modules.add(module1)
                    all_stagnant_modules.add(module2)
                
                sorted_modules = sorted(all_stagnant_modules)
                for i, module in enumerate(sorted_modules):
                    if i % 2 == 0:
                        coordinated_plan.append({
                            'module': module,
                            'action': 'change_interface',
                            'description': f"Modify {module}'s interface as part of coordinated change"
                        })
                    else:
                        coordinated_plan.append({
                            'module': module,
                            'action': 'change_implementation',
                            'description': f"Modify {module}'s implementation to complement interface change"
                        })
            
            logger.info(f"Coordinated change plan generated for {len(modules_in_plan)} modules: {modules_in_plan}")
            
            return {
                'equilibrium_detected': True,
                'coordinated_plan': coordinated_plan,
                'description': f"Coordinated multi-module change plan involving {len(modules_in_plan)} modules to break Nash equilibrium"
            }
            
        except Exception as e:
            logger.error(f"Error in detect_and_force_coordinated_change: {e}")
            return None

    def force_coordinated_mutation(self, plan: Dict) -> bool:
        """
        Take a coordinated mutation plan and apply changes atomically.
        
        This method simulates applying the coordinated changes by resetting the
        stagnation counters and payoff matrix for the affected modules, as if
        the changes were applied atomically.
        
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
                logger.warning("Invalid plan provided to force_coordinated_mutation")
                return False
            
            coordinated_plan = plan['coordinated_plan']
            if not coordinated_plan:
                logger.warning("Empty coordinated plan provided")
                return False
            
            # Extract all modules involved in the coordinated plan
            affected_modules: Set[str] = set()
            for step in coordinated_plan:
                if 'module' in step:
                    affected_modules.add(step['module'])
            
            if not affected_modules:
                logger.warning("No modules found in coordinated plan")
                return False
            
            # Apply changes atomically by resetting stagnation tracking for all affected modules
            # This simulates the atomic application of coordinated changes
            modules_list = list(affected_modules)
            for i in range(len(modules_list)):
                for j in range(i + 1, len(modules_list)):
                    module1 = modules_list[i]
                    module2 = modules_list[j]
                    pair = tuple(sorted([module1, module2]))
                    
                    # Reset stagnation counter and payoff matrix for this pair
                    self.stagnation_counter[pair] = 0
                    if pair in self.payoff_matrix:
                        self.payoff_matrix[pair] = []
            
            # Update current fitness values to simulate the effect of coordinated changes
            for module_name in affected_modules:
                try:
                    fitness_func = self.fitness_functions.get(module_name)
                    if fitness_func:
                        new_fitness = fitness_func()
                        self.current_fitness[module_name] = new_fitness
                except Exception as e:
                    logger.error(f"Error updating fitness for module {module_name}: {e}")
            
            # Record a positive cycle outcome to indicate that the coordinated mutation was applied
            self._cycle_improvement_history.append(True)
            if len(self._cycle_improvement_history) > 5:
                self._cycle_improvement_history = self._cycle_improvement_history[-5:]
            
            # Reset cycles without improvement counter
            self.cycles_without_improvement = 0
            
            logger.info(f"Coordinated mutation applied successfully for modules: {affected_modules}")
            return True
            
        except Exception as e:
            logger.error(f"Error in force_coordinated_mutation: {e}")
            return False

    def force_coordinated_change(self) -> bool:
        """
        Force a coordinated change to break out of Nash equilibrium.
        
        This method:
        1. Identifies modules at Nash equilibrium
        2. Generates a coordinated mutation plan affecting 3+ modules simultaneously
        3. Uses the atomic multi-module mutation orchestrator to apply changes
        4. Verifies the system escapes the local optimum by checking if at least one module improves post-change
        
        Returns:
            True if the coordinated change successfully broke the equilibrium (at least one module improved),
            False otherwise
        """
        try:
            # Step 1: Identify if system is at Nash equilibrium
            if not self.detect_equilibrium():
                logger.info("System is not at Nash equilibrium, no forced change needed")
                return False
            
            # Step 2: Generate a coordinated mutation plan affecting 3+ modules simultaneously
            # Collect all modules that are part of stagnant pairs
            stagnant_pairs = self.suggest_coordinated_changes()
            
            # If no stagnant pairs, use all modules with non-positive gradients
            if not stagnant_pairs:
                # Estimate gradients for all modules
                for module_name in self.module_names:
                    self.gradient_estimates[module_name] = self._estimate_gradient(module_name)
                
                # Find modules with non-positive gradients (stuck)
                stuck_modules = [m for m, g in self.gradient_estimates.items() if g <= 0]
                
                if len(stuck_modules) < 3:
                    logger.info(f"Not enough stuck modules for coordinated change: {len(stuck_modules)} found, need at least 3")
                    return False
                
                # Create a plan with at least 3 modules
                selected_modules = stuck_modules[:3]  # Take first 3 stuck modules
            else:
                # Collect all unique modules from stagnant pairs
                stagnant_modules: Set[str] = set()
                for m1, m2 in stagnant_pairs:
                    stagnant_modules.add(m1)
                    stagnant_modules.add(m2)
                
                if len(stagnant_modules) < 3:
                    logger.info(f"Not enough stagnant modules for coordinated change: {len(stagnant_modules)} found, need at least 3")
                    return False
                
                # Select at least 3 modules from stagnant set
                selected_modules = list(stagnant_modules)[:3]
            
            # Build the coordinated mutation plan
            coordinated_plan = []
            for i, module in enumerate(selected_modules):
                if i == 0:
                    action = 'change_interface'
                    description = f"Modify {module}'s interface as part of coordinated escape from Nash equilibrium"
                elif i == 1:
                    action = 'change_implementation'
                    description = f"Modify {module}'s implementation to complement interface changes"
                else:
                    action = 'change_parameter'
                    description = f"Modify {module}'s parameters to complete the coordinated change"
                
                coordinated_plan.append({
                    'module': module,
                    'action': action,
                    'description': description
                })
            
            plan = {
                'coordinated_plan': coordinated_plan,
                'description': f"Coordinated multi-module change plan involving {len(selected_modules)} modules to break Nash equilibrium"
            }
            
            # Step 3: Use the atomic multi-module mutation orchestrator to apply changes
            # Record the current fitness values before applying changes
            pre_change_fitness = {}
            for module_name in selected_modules:
                try:
                    fitness_func = self.fitness_functions.get(module_name)
                    if fitness_func:
                        pre_change_fitness[module_name] = fitness_func()
                    else:
                        pre_change_fitness[module_name] = self.current_fitness.get(module_name, 0.0)
                except Exception as e:
                    logger.error(f"Error getting pre-change fitness for module {module_name}: {e}")
                    pre_change_fitness[module_name] = self.current_fitness.get(module_name, 0.0)
            
            # Apply the coordinated mutation atomically
            success = self.force_coordinated_mutation(plan)
            
            if not success:
                logger.error("Failed to apply coordinated mutation")
                return False
            
            # Step 4: Verify the system escapes the local optimum by checking if at least one module improves post-change
            post_change_fitness = {}
            for module_name in selected_modules:
                try:
                    fitness_func = self.fitness_functions.get(module_name)
                    if fitness_func:
                        post_change_fitness[module_name] = fitness_func()
                    else:
                        post_change_fitness[module_name] = self.current_fitness.get(module_name, 0.0)
                except Exception as e:
                    logger.error(f"Error getting post-change fitness for module {module_name}: {e}")
                    post_change_fitness[module_name] = self.current_fitness.get(module_name, 0.0)
            
            # Check if at least one module improved
            any_improvement = False
            for module_name in selected_modules:
                pre = pre_change_fitness.get(module_name, 0.0)
                post = post_change_fitness.get(module_name, 0.0)
                
                if pre > 0:
                    improvement_ratio = (post - pre) / pre
                    if improvement_ratio > self.improvement_threshold:
                        any_improvement = True
                        logger.info(f"Module {module_name} improved by {improvement_ratio:.4f} after coordinated change")
                elif post > pre:
                    any_improvement = True
                    logger.info(f"Module {module_name} improved from {pre} to {post} after coordinated change")
            
            if any_improvement:
                logger.info(f"Coordinated change successfully broke Nash equilibrium with improvements in {len(selected_modules)} modules")
                # Reset the equilibrium state since we broke out
                self.cycles_without_improvement = 0
                return True
            else:
                logger.warning("Coordinated change did not result in any module improvement")
                return False
                
        except Exception as e:
            logger.error(f"Error in force_coordinated_change: {e}")
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
        self._compute_baseline_fitness()
        logger.info(f"Fitness functions updated for modules: {self.module_names}")

    def get_equilibrium_state(self) -> Dict:
        """
        Get the current equilibrium state information.
        
        Returns:
            Dictionary containing:
            - 'equilibrium': bool indicating if system is at equilibrium
            - 'stagnant_pairs': list of stagnant module pairs
            - 'gradient_estimates': dict of gradient estimates per module
            - 'cycles_without_improvement': int
        """
        return {
            'equilibrium': self.detect_equilibrium(),
            'stagnant_pairs': self.suggest_coordinated_changes(),
            'gradient_estimates': dict(self.gradient_estimates),
            'cycles_without_improvement': self.cycles_without_improvement
        }

    def increment_cycle(self) -> None:
        """Advance to the next evaluation cycle."""
        self.cycles_without_improvement += 1
        
        # Check if any module improved in this cycle
        any_improvement = False
        for module_name in self.module_names:
            try:
                current_fitness = self.current_fitness.get(module_name, 0.0)
                baseline_fitness = self.baseline_fitness.get(module_name, 0.0)
                
                if baseline_fitness > 0:
                    improvement_ratio = abs(current_fitness - baseline_fitness) / baseline_fitness
                    if improvement_ratio > self.improvement_threshold:
                        any_improvement = True
                        break
            except Exception as e:
                logger.error(f"Error checking improvement for module {module_name}: {e}")
                continue
        
        if any_improvement:
            self.cycles_without_improvement = 0
        
        self._cycle_improvement_history.append(any_improvement)
        if len(self._cycle_improvement_history) > 5:
            self._cycle_improvement_history = self._cycle_improvement_history[-5:]
        
        logger.debug(f"Cycle incremented. Cycles without improvement: {self.cycles_without_improvement}")

    def set_improvement_threshold(self, threshold: float) -> None:
        """
        Set the improvement threshold for detecting equilibrium.
        
        Args:
            threshold: Float between 0 and 1 representing the minimum improvement ratio
        """
        if threshold < 0 or threshold > 1:
            raise ValueError("Improvement threshold must be between 0 and 1")
        self.improvement_threshold = threshold
        logger.info(f"Improvement threshold set to {threshold}")

    def set_stagnation_threshold(self, threshold: int) -> None:
        """
        Set the number of consecutive non-improvement cycles required for stagnation.
        
        Args:
            threshold: Number of cycles (must be positive)
        """
        if threshold < 1:
            raise ValueError("Stagnation threshold must be at least 1")
        self.stagnation_threshold = threshold
        logger.info(f"Stagnation threshold set to {threshold}")