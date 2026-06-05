import json
from collections import defaultdict, deque
from typing import List, Dict, Tuple, Optional, Set, Any
import random

class ModuleInteractionTracker:
    """
    Tracks pairwise module interaction success/failure rates and detects
    when no single-module change improves the system (Nash equilibrium).
    """
    
    def __init__(self, num_modules: int = 5, sliding_window_size: int = 20):
        self.num_modules = num_modules
        self.sliding_window_size = sliding_window_size
        
        # Track interaction pairs (caller, callee) and their success rates
        self.module_interaction_pairs: Dict[Tuple[int, int], Dict[str, Any]] = defaultdict(
            lambda: {"success_count": 0, "total_count": 0, "success_rate": 0.0, "last_cycles": deque(maxlen=sliding_window_size)}
        )
        
        # Sliding window for tracking interaction history
        self.interaction_history: deque = deque(maxlen=sliding_window_size)
        self.interaction_frequencies: Dict[Tuple[int, int], int] = defaultdict(int)
        self.interaction_success_rates: Dict[Tuple[int, int], float] = defaultdict(float)
        
        # Track improvement history per module
        self.module_improvement_history: Dict[int, deque] = defaultdict(lambda: deque(maxlen=3))
        
        # Equilibrium detection parameters
        self.improvement_threshold: float = 0.05  # 5% threshold
        self.equilibrium_window: int = 5
        self.equilibrium_tolerance: float = 0.001
        self.consecutive_no_improvement: int = 0
        self.in_equilibrium: bool = False
        self.equilibrium_pairs: List[Tuple[int, int]] = []
        
    def record_interaction(self, module_i: int, module_j: int, success: bool) -> None:
        """Record an interaction between two modules."""
        interaction_key = (min(module_i, module_j), max(module_i, module_j))
        self.interaction_history.append((interaction_key, success))
        
        # Update frequencies and success rates based on sliding window
        self.interaction_frequencies.clear()
        success_counts = defaultdict(int)
        total_counts = defaultdict(int)
        
        for key, suc in self.interaction_history:
            total_counts[key] += 1
            if suc:
                success_counts[key] += 1
        
        for key in total_counts:
            self.interaction_frequencies[key] = total_counts[key]
            self.interaction_success_rates[key] = success_counts[key] / total_counts[key]
        
        # Update module interaction pairs tracking
        pair_key = (module_i, module_j)
        pair_data = self.module_interaction_pairs[pair_key]
        pair_data["total_count"] += 1
        if success:
            pair_data["success_count"] += 1
        pair_data["success_rate"] = pair_data["success_count"] / pair_data["total_count"] if pair_data["total_count"] > 0 else 0.0
        pair_data["last_cycles"].append(success)
    
    def update_module_improvement(self, module_idx: int, improved: bool) -> None:
        """Update the improvement history for a specific module."""
        self.module_improvement_history[module_idx].append(improved)
    
    def detect_nash_equilibrium(self, module_scores: List[float], dependency_matrix: List[List[float]]) -> Tuple[bool, List[Tuple[int, int]]]:
        """
        Detect if the system is in Nash equilibrium.
        
        A Nash equilibrium exists when no single module can improve its score
        by more than 5% through a change in its dependencies.
        
        Args:
            module_scores: Current scores for each module
            dependency_matrix: Current dependency matrix
            
        Returns:
            Tuple of (is_in_equilibrium, list_of_equilibrium_pairs)
        """
        if len(module_scores) < self.equilibrium_window:
            return False, []
        
        # Check if any single-module change improves the system by more than 5%
        improvement_found = False
        for module_idx in range(self.num_modules):
            original_deps = dependency_matrix[module_idx].copy()
            
            # Try increasing a random dependency
            dep_idx = random.randint(0, self.num_modules - 1)
            original_value = dependency_matrix[module_idx][dep_idx]
            dependency_matrix[module_idx][dep_idx] = min(1.0, original_value + 0.1)
            
            # Compute new score for this module
            new_score = self._compute_module_score(module_idx, module_scores, dependency_matrix)
            
            # Restore original
            dependency_matrix[module_idx] = original_deps
            
            # If improvement found (more than 5%), not in equilibrium
            if new_score > module_scores[module_idx] * (1 + self.improvement_threshold):
                improvement_found = True
                break
        
        if improvement_found:
            self.consecutive_no_improvement = 0
            return False, []
        
        # Check if all modules have reached a local optimum
        all_modules_optimal = True
        equilibrium_pairs = []
        
        for module_idx in range(self.num_modules):
            module_success_rates = []
            for pair_key, pair_data in self.module_interaction_pairs.items():
                if module_idx in pair_key:
                    module_success_rates.append(pair_data["success_rate"])
            
            if not module_success_rates:
                all_modules_optimal = False
                continue
            
            avg_success_rate = sum(module_success_rates) / len(module_success_rates)
            if avg_success_rate <= 0.8:
                all_modules_optimal = False
                continue
            
            module_improvement_history = self.module_improvement_history[module_idx]
            if len(module_improvement_history) < 3:
                all_modules_optimal = False
                continue
            
            has_improvement = any(module_improvement_history)
            if has_improvement:
                all_modules_optimal = False
                continue
            
            # This module is at local optimum, find its equilibrium pairs
            for pair_key, pair_data in self.module_interaction_pairs.items():
                if module_idx in pair_key and pair_data["success_rate"] > 0.8:
                    other_module = pair_key[0] if pair_key[1] == module_idx else pair_key[1]
                    other_improvement_history = self.module_improvement_history[other_module]
                    if len(other_improvement_history) >= 3 and not any(other_improvement_history):
                        other_success_rates = []
                        for other_pair_key, other_pair_data in self.module_interaction_pairs.items():
                            if other_module in other_pair_key:
                                other_success_rates.append(other_pair_data["success_rate"])
                        if other_success_rates:
                            other_avg_success_rate = sum(other_success_rates) / len(other_success_rates)
                            if other_avg_success_rate > 0.8:
                                equilibrium_pairs.append(pair_key)
        
        if all_modules_optimal and equilibrium_pairs:
            self.consecutive_no_improvement += 1
            if self.consecutive_no_improvement >= 3:
                self.in_equilibrium = True
                self.equilibrium_pairs = equilibrium_pairs
                return True, equilibrium_pairs
        
        self.consecutive_no_improvement = 0
        return False, []
    
    def _compute_module_score(self, module_idx: int, module_scores: List[float], dependency_matrix: List[List[float]]) -> float:
        """Compute score for a single module based on dependencies."""
        score = 0.0
        for j in range(self.num_modules):
            score += dependency_matrix[module_idx][j] * (module_scores[j] if j != module_idx else 1.0)
        score += random.uniform(-0.05, 0.05)
        return score
    
    def get_interaction_stats(self) -> Dict[str, Any]:
        """Get current interaction statistics."""
        return {
            "interaction_frequencies": dict(self.interaction_frequencies),
            "interaction_success_rates": dict(self.interaction_success_rates),
            "module_interaction_pairs": {str(k): dict(v) for k, v in self.module_interaction_pairs.items()},
            "equilibrium_pairs": self.equilibrium_pairs,
            "in_equilibrium": self.in_equilibrium
        }


class CoordinatedMutationPlanner:
    """
    Identifies 2-3 module combinations to mutate simultaneously
    to escape Nash equilibria.
    """
    
    def __init__(self, num_modules: int = 5):
        self.num_modules = num_modules
        
    def plan_mutations(self, equilibrium_pairs: List[Tuple[int, int]], 
                      interaction_frequencies: Dict[Tuple[int, int], int],
                      dependency_matrix: List[List[float]]) -> Dict[str, Any]:
        """
        Plan coordinated mutations for 2-3 modules based on equilibrium pairs.
        
        Args:
            equilibrium_pairs: List of module pairs in equilibrium
            interaction_frequencies: Frequency of interactions between modules
            dependency_matrix: Current dependency matrix
            
        Returns:
            Dictionary with mutation plan
        """
        # Select modules to mutate based on equilibrium pairs
        modules_to_mutate = self._select_modules_for_mutation(equilibrium_pairs, interaction_frequencies)
        
        if len(modules_to_mutate) < 2:
            # Fall back to random selection if not enough modules identified
            modules_to_mutate = random.sample(range(self.num_modules), min(3, self.num_modules))
        
        # Build mutation plan
        mutation_plan = {
            "type": "coordinated_mutation",
            "modules_changed": modules_to_mutate,
            "mutations": [],
            "rationale": "Simultaneous changes to escape single-module optimization"
        }
        
        for module_idx in modules_to_mutate:
            mutation_type = random.choice(["dependency_shift", "dependency_swap", "dependency_reset"])
            
            if mutation_type == "dependency_shift":
                shift_amount = random.uniform(-0.2, 0.2)
                original = dependency_matrix[module_idx].copy()
                new_deps = []
                for j in range(self.num_modules):
                    new_val = max(0.0, min(1.0, dependency_matrix[module_idx][j] + shift_amount))
                    new_deps.append(new_val)
                mutation_plan["mutations"].append({
                    "module": module_idx,
                    "type": "shift",
                    "amount": shift_amount,
                    "original": original,
                    "new": new_deps
                })
                
            elif mutation_type == "dependency_swap":
                j1, j2 = random.sample(range(self.num_modules), 2)
                original = dependency_matrix[module_idx].copy()
                new_deps = original.copy()
                new_deps[j1], new_deps[j2] = new_deps[j2], new_deps[j1]
                mutation_plan["mutations"].append({
                    "module": module_idx,
                    "type": "swap",
                    "indices": (j1, j2),
                    "original": original,
                    "new": new_deps
                })
                
            else:  # dependency_reset
                num_to_reset = random.randint(1, max(1, self.num_modules // 2))
                indices_to_reset = random.sample(range(self.num_modules), num_to_reset)
                original = dependency_matrix[module_idx].copy()
                new_deps = original.copy()
                for j in indices_to_reset:
                    new_deps[j] = random.random()
                mutation_plan["mutations"].append({
                    "module": module_idx,
                    "type": "reset",
                    "indices_reset": indices_to_reset,
                    "original": original,
                    "new": new_deps
                })
        
        return mutation_plan
    
    def _select_modules_for_mutation(self, equilibrium_pairs: List[Tuple[int, int]],
                                    interaction_frequencies: Dict[Tuple[int, int], int]) -> List[int]:
        """Select 2-3 modules for coordinated mutation based on equilibrium analysis."""
        if not equilibrium_pairs:
            return random.sample(range(self.num_modules), min(3, self.num_modules))
        
        # Collect all modules involved in equilibrium pairs
        modules_in_equilibrium = set()
        for pair in equilibrium_pairs:
            modules_in_equilibrium.add(pair[0])
            modules_in_equilibrium.add(pair[1])
        
        # If we have enough modules, select from equilibrium pairs
        if len(modules_in_equilibrium) >= 2:
            selected = list(modules_in_equilibrium)
            if len(selected) > 3:
                # Prioritize modules with highest interaction frequencies
                module_frequencies = defaultdict(int)
                for (i, j), freq in interaction_frequencies.items():
                    if i in modules_in_equilibrium:
                        module_frequencies[i] += freq
                    if j in modules_in_equilibrium:
                        module_frequencies[j] += freq
                
                sorted_modules = sorted(module_frequencies.items(), key=lambda x: x[1], reverse=True)
                selected = [m[0] for m in sorted_modules[:3]]
            
            return selected[:3]
        
        # Fall back to random selection
        return random.sample(range(self.num_modules), min(3, self.num_modules))


class NashDetectorAndForcer:
    """
    A self-contained module for detecting Nash equilibria in a system of interacting modules
    and forcing coordinated multi-module changes to escape suboptimal equilibria.
    
    Uses only standard library: json, collections, random, typing.
    No external imports.
    """

    def __init__(self, num_modules: int = 5, random_seed: Optional[int] = None):
        """
        Initialize the detector/forcer with a given number of modules.
        
        Args:
            num_modules: Number of modules in the system (default 5)
            random_seed: Optional seed for reproducibility
        """
        if random_seed is not None:
            random.seed(random_seed)
        
        self.num_modules = num_modules
        # Dependency matrix: dependency[i][j] = strength of influence from module j to module i
        # Initialized with random values between 0.0 and 1.0
        self.dependency_matrix: List[List[float]] = [
            [random.random() for _ in range(num_modules)]
            for _ in range(num_modules)
        ]
        
        # Current scores for each module (simulating module interaction outcomes)
        self.module_scores: List[float] = [0.0 for _ in range(num_modules)]
        
        # History of scores for equilibrium detection
        self.score_history: List[List[float]] = []
        
        # Initialize sub-modules
        self.interaction_tracker = ModuleInteractionTracker(num_modules)
        self.mutation_planner = CoordinatedMutationPlanner(num_modules)
        
        # Equilibrium detection parameters
        self.equilibrium_window: int = 5  # Number of recent iterations to check
        self.equilibrium_tolerance: float = 0.001  # Max score change to consider stable
        
        # Current equilibrium state
        self.in_equilibrium: bool = False
        self.equilibrium_iterations: int = 0
        
        # Track consecutive cycles without improvement
        self.consecutive_no_improvement: int = 0
        self.equilibrium_detected: bool = False
        
        # Track module interaction pairs (caller, callee) and their success rates
        self.module_interaction_pairs: Dict[Tuple[int, int], Dict[str, Any]] = defaultdict(
            lambda: {"success_count": 0, "total_count": 0, "success_rate": 0.0, "last_cycles": deque(maxlen=20)}
        )
        
        # Track improvement history per module
        self.module_improvement_history: Dict[int, deque] = defaultdict(lambda: deque(maxlen=3))
        
        # List of module pairs in equilibrium
        self.equilibrium_pairs: List[Tuple[int, int]] = []

    def set_dependency_matrix(self, matrix: List[List[float]]) -> None:
        """
        Set a custom dependency matrix.
        
        Args:
            matrix: Square matrix where matrix[i][j] is influence from j to i
        """
        if len(matrix) != self.num_modules:
            raise ValueError(f"Matrix must have {self.num_modules} rows")
        for row in matrix:
            if len(row) != self.num_modules:
                raise ValueError(f"Each row must have {self.num_modules} elements")
        self.dependency_matrix = matrix

    def compute_module_score(self, module_idx: int) -> float:
        """
        Compute the score for a single module based on its dependencies.
        
        The score is a weighted sum of influences from all modules,
        with a small random perturbation to simulate stochastic interactions.
        
        Args:
            module_idx: Index of the module to score
            
        Returns:
            Computed score for the module
        """
        score = 0.0
        for j in range(self.num_modules):
            # Weighted contribution from module j to module i
            score += self.dependency_matrix[module_idx][j] * (self.module_scores[j] if j != module_idx else 1.0)
        
        # Add small random noise to simulate stochasticity
        score += random.uniform(-0.05, 0.05)
        
        return score

    def update_all_scores(self) -> List[float]:
        """
        Update scores for all modules based on current dependencies.
        
        Returns:
            Updated list of module scores
        """
        new_scores = []
        for i in range(self.num_modules):
            new_scores.append(self.compute_module_score(i))
        
        self.module_scores = new_scores
        self.score_history.append(new_scores.copy())
        
        # Keep history bounded
        if len(self.score_history) > 100:
            self.score_history.pop(0)
        
        return new_scores

    def record_interaction(self, module_i: int, module_j: int, success: bool) -> None:
        """
        Record an interaction between two modules and update frequencies/success rates.
        
        Args:
            module_i: First module index
            module_j: Second module index
            success: Whether the interaction was successful
        """
        # Delegate to interaction tracker
        self.interaction_tracker.record_interaction(module_i, module_j, success)
        
        # Also maintain backward compatibility with existing tracking
        interaction_key = (min(module_i, module_j), max(module_i, module_j))
        
        # Update module interaction pairs tracking
        pair_key = (module_i, module_j)
        pair_data = self.module_interaction_pairs[pair_key]
        pair_data["total_count"] += 1
        if success:
            pair_data["success_count"] += 1
        pair_data["success_rate"] = pair_data["success_count"] / pair_data["total_count"] if pair_data["total_count"] > 0 else 0.0
        pair_data["last_cycles"].append(success)

    def detect_nash_equilibrium(self) -> bool:
        """
        Enhanced Nash equilibrium detection function that analyzes module interaction
        frequencies and success rates over the last 20 cycles, identifying when no
        single module change improves any metric by more than 5%.
        
        A Nash equilibrium exists when:
        1. No single module can improve its score by changing its dependencies
           (within a 5% threshold) for 3+ consecutive cycles.
        2. Module interaction frequencies and success rates have stabilized
           over the last 20 cycles.
        
        Returns:
            True if system is in Nash equilibrium, False otherwise
        """
        # Check if we have enough history
        if len(self.score_history) < self.equilibrium_window:
            return False
        
        # Check if scores have stabilized
        recent_scores = self.score_history[-self.equilibrium_window:]
        
        # Check if scores are stable over the window
        for i in range(self.num_modules):
            scores_i = [s[i] for s in recent_scores]
            if max(scores_i) - min(scores_i) > self.equilibrium_tolerance:
                self.consecutive_no_improvement = 0
                return False
        
        # Use interaction tracker for equilibrium detection
        is_equilibrium, equilibrium_pairs = self.interaction_tracker.detect_nash_equilibrium(
            self.module_scores, self.dependency_matrix
        )
        
        if is_equilibrium:
            self.in_equilibrium = True
            self.equilibrium_iterations += 1
            self.equilibrium_detected = True
            self.equilibrium_pairs = equilibrium_pairs
            return True
        
        return False

    def _check_interaction_stability(self) -> bool:
        """
        Check if module interaction frequencies and success rates have stabilized
        over the last 20 cycles.
        
        Returns:
            True if interactions are stable, False otherwise
        """
        # If we don't have enough interaction history, consider it unstable
        if len(self.interaction_tracker.interaction_history) < 10:
            return False
        
        # Check if interaction frequencies are consistent
        # (i.e., no single interaction dominates)
        if not self.interaction_tracker.interaction_frequencies:
            return False
        
        total_interactions = sum(self.interaction_tracker.interaction_frequencies.values())
        if total_interactions == 0:
            return False
        
        # Check if any interaction has an unusually high frequency (>50% of total)
        for key, freq in self.interaction_tracker.interaction_frequencies.items():
            if freq / total_interactions > 0.5:
                return False
        
        # Check if success rates are stable (not too volatile)
        if self.interaction_tracker.interaction_success_rates:
            rates = list(self.interaction_tracker.interaction_success_rates.values())
            if rates:
                avg_rate = sum(rates) / len(rates)
                # If average success rate is too low or too high, consider it unstable
                if avg_rate < 0.2 or avg_rate > 0.9:
                    return False
        
        return True

    def check_equilibrium(self) -> bool:
        """
        Legacy equilibrium check method that delegates to the enhanced detection.
        
        Returns:
            True if system is in equilibrium, False otherwise
        """
        return self.detect_nash_equilibrium()

    def force_coordinated_change(self, num_modules_to_change: int = 3) -> Dict[str, Any]:
        """
        Enhanced coordinated multi-module force function that generates simultaneous
        changes to 3 modules when equilibrium is detected.
        
        Generates simultaneous mutations across 3 interdependent modules and returns the plan
        to the orchestrator for execution. The changes are designed to escape local optima
        that single-module changes cannot overcome.
        
        Args:
            num_modules_to_change: Number of modules to mutate (default 3, clamped to 3)
            
        Returns:
            Dictionary describing the forced change plan for the orchestrator
        """
        # Always use 3 modules as per requirement
        num_modules_to_change = 3
        
        # Use mutation planner to generate coordinated mutations
        mutation_plan = self.mutation_planner.plan_mutations(
            self.equilibrium_pairs,
            self.interaction_tracker.interaction_frequencies,
            self.dependency_matrix
        )
        
        return mutation_plan

    def _select_interdependent_modules(self, num_modules: int) -> List[int]:
        """
        Select interdependent modules based on interaction frequencies.
        
        Args:
            num_modules: Number of modules to select
            
        Returns:
            List of module indices that are interdependent
        """
        if not self.interaction_tracker.interaction_frequencies:
            # Fall back to random selection if no interaction data
            return random.sample(range(self.num_modules), num_modules)
        
        # Sort interactions by frequency (most frequent first)
        sorted_interactions = sorted(
            self.interaction_tracker.interaction_frequencies.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        selected_modules = set()
        for (i, j), freq in sorted_interactions:
            if len(selected_modules) >= num_modules:
                break
            selected_modules.add(i)
            if len(selected_modules) < num_modules:
                selected_modules.add(j)
        
        # If we don't have enough modules, add random ones
        while len(selected_modules) < num_modules:
            candidate = random.randint(0, self.num_modules - 1)
            if candidate not in selected_modules:
                selected_modules.add(candidate)
        
        return list(selected_modules)[:num_modules]

    def execute_coordinated_change(self, mutation_plan: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a coordinated change plan that was generated by force_coordinated_change.
        
        This method applies the mutations to the dependency matrix and updates scores.
        
        Args:
            mutation_plan: The plan dictionary returned by force_coordinated_change
            
        Returns:
            Dictionary with execution results
        """
        execution_record = {
            "type": "coordinated_mutation_executed",
            "modules_changed": mutation_plan["modules_changed"],
            "mutations_applied": []
        }
        
        for mutation in mutation_plan["mutations"]:
            module_idx = mutation["module"]
            new_deps = mutation["new"]
            
            # Apply the new dependencies
            self.dependency_matrix[module_idx] = new_deps.copy()
            
            execution_record["mutations_applied"].append({
                "module": module_idx,
                "type": mutation["type"],
                "new_dependencies": new_deps
            })
        
        # Update scores after forced change
        self.update_all_scores()
        self.in_equilibrium = False
        self.equilibrium_detected = False
        self.consecutive_no_improvement = 0
        
        return execution_record

    def run_equilibrium_cycle(self, max_iterations: int = 100) -> Dict[str, Any]:
        """
        Run a full equilibrium detection and forcing cycle.
        
        Continuously updates scores, checks for equilibrium, and forces
        coordinated changes when equilibrium is detected.
        
        Args:
            max_iterations: Maximum number of iterations to run
            
        Returns:
            Dictionary with cycle results
        """
        results = {
            "iterations": 0,
            "equilibria_detected": 0,
            "coordinated_changes_forced": 0,
            "final_scores": [],
            "history": []
        }
        
        for iteration in range(max_iterations):
            # Update scores
            scores = self.update_all_scores()
            
            # Record interactions between modules (simulated)
            for i in range(self.num_modules):
                for j in range(i + 1, self.num_modules):
                    interaction_success = random.random() > 0.3  # 70% success rate
                    self.record_interaction(i, j, interaction_success)
            
            # Check for equilibrium using enhanced detection
            if self.detect_nash_equilibrium():
                results["equilibria_detected"] += 1
                
                # Generate coordinated change plan (always 3 modules)
                num_to_change = 3
                change_plan = self.force_coordinated_change(num_to_change)
                
                # Execute the plan
                execution = self.execute_coordinated_change(change_plan)
                results["coordinated_changes_forced"] += 1
                results["history"].append({
                    "iteration": iteration,
                    "type": "coordinated_change",
                    "plan": change_plan,
                    "execution": execution
                })
            
            results["iterations"] = iteration + 1
        
        results["final_scores"] = self.module_scores.copy()
        return results

    def get_orchestrator_api(self) -> Dict[str, Any]:
        """
        Simple API for integration with the evolution orchestrator.
        
        Returns a dictionary with methods that the orchestrator can call:
        - 'detect_equilibrium': Check if system is in Nash equilibrium
        - 'force_change': Generate and optionally execute a coordinated change
        - 'get_state': Get current system state summary
        
        Returns:
            Dictionary with API methods (as callable functions)
        """
        def detect_equilibrium() -> bool:
            """Check if the system is in Nash equilibrium."""
            return self.detect_nash_equilibrium()
        
        def force_change(execute: bool = True) -> Dict[str, Any]:
            """
            Generate and optionally execute a coordinated change.
            
            Args:
                execute: If True, execute the change immediately. If False, return plan only.
                
            Returns:
                Dictionary with change plan or execution result
            """
            num_to_change = 3
            plan = self.force_coordinated_change(num_to_change)
            if execute:
                result = self.execute_coordinated_change(plan)
                return result
            return plan
        
        def get_state() -> Dict[str, Any]:
            """Get current system state summary."""
            return self.get_system_summary()
        
        return {
            "detect_equilibrium": detect_equilibrium,
            "force_change": force_change,
            "get_state": get_state
        }

    def to_json(self) -> str:
        """
        Serialize the current state to JSON.
        
        Returns:
            JSON string representation
        """
        state = {
            "num_modules": self.num_modules,
            "dependency_matrix": self.dependency_matrix,
            "module_scores": self.module_scores,
            "in_equilibrium": self.in_equilibrium,
            "equilibrium_iterations": self.equilibrium_iterations,
            "consecutive_no_improvement": self.consecutive_no_improvement,
            "interaction_frequencies": {str(k): v for k, v in self.interaction_tracker.interaction_frequencies.items()},
            "interaction_success_rates": {str(k): v for k, v in self.interaction_tracker.interaction_success_rates.items()},
            "module_interaction_pairs": {str(k): dict(v) for k, v in self.module_interaction_pairs.items()},
            "equilibrium_pairs": [list(pair) for pair in self.equilibrium_pairs]
        }
        return json.dumps(state, indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> 'NashDetectorAndForcer':
        """
        Deserialize from JSON string.
        
        Args:
            json_str: JSON string representation
            
        Returns:
            New NashDetectorAndForcer instance
        """
        state = json.loads(json_str)
        instance = cls(num_modules=state["num_modules"])
        instance.dependency_matrix = state["dependency_matrix"]
        instance.module_scores = state["module_scores"]
        instance.in_equilibrium = state["in_equilibrium"]
        instance.equilibrium_iterations = state["equilibrium_iterations"]
        instance.consecutive_no_improvement = state.get("consecutive_no_improvement", 0)
        
        # Restore interaction data
        for key_str, freq in state.get("interaction_frequencies", {}).items():
            key = tuple(map(int, key_str.strip("()").split(", ")))
            instance.interaction_tracker.interaction_frequencies[key] = freq
        
        for key_str, rate in state.get("interaction_success_rates", {}).items():
            key = tuple(map(int, key_str.strip("()").split(", ")))
            instance.interaction_tracker.interaction_success_rates[key] = rate
        
        # Restore module interaction pairs
        for key_str, pair_data in state.get("module_interaction_pairs", {}).items():
            key = tuple(map(int, key_str.strip("()").split(", ")))
            instance.module_interaction_pairs[key] = {
                "success_count": pair_data["success_count"],
                "total_count": pair_data["total_count"],
                "success_rate": pair_data["success_rate"],
                "last_cycles": deque(pair_data.get("last_cycles", []), maxlen=20)
            }
        
        # Restore equilibrium pairs
        instance.equilibrium_pairs = [tuple(pair) for pair in state.get("equilibrium_pairs", [])]
        
        return instance

    def get_system_summary(self) -> Dict[str, Any]:
        """
        Get a summary of the current system state.
        
        Returns:
            Dictionary with system summary
        """
        return {
            "num_modules": self.num_modules,
            "average_score": sum(self.module_scores) / self.num_modules if self.num_modules > 0 else 0.0,
            "max_score": max(self.module_scores) if self.module_scores else 0.0,
            "min_score": min(self.module_scores) if self.module_scores else 0.0,
            "in_equilibrium": self.in_equilibrium,
            "equilibrium_iterations": self.equilibrium_iterations,
            "consecutive_no_improvement": self.consecutive_no_improvement,
            "dependency_density": sum(
                sum(1 for val in row if val > 0.5) for row in self.dependency_matrix
            ) / (self.num_modules ** 2) if self.num_modules > 0 else 0.0,
            "interaction_frequencies": dict(self.interaction_tracker.interaction_frequencies),
            "interaction_success_rates": dict(self.interaction_tracker.interaction_success_rates),
            "module_interaction_pairs": {str(k): dict(v) for k, v in self.module_interaction_pairs.items()},
            "equilibrium_pairs": self.equilibrium_pairs
        }

    def detect_nash_equilibrium_with_pairs(self) -> Tuple[bool, List[Tuple[int, int]]]:
        """
        Enhanced Nash equilibrium detection that tracks module interaction pairs (caller, callee)
        and their success rates. Detects when no single module change improves the system by
        checking if all modules have reached a local optimum (success rate > 0.8 and no improvement
        in last 3 cycles). Returns a list of module pairs that are in equilibrium and need
        coordinated changes.
        
        Returns:
            Tuple of (is_in_equilibrium, list_of_equilibrium_pairs)
        """
        # Check if we have enough history
        if len(self.score_history) < self.equilibrium_window:
            return False, []
        
        # Check if scores have stabilized
        recent_scores = self.score_history[-self.equilibrium_window:]
        
        # Check if scores are stable over the window
        for i in range(self.num_modules):
            scores_i = [s[i] for s in recent_scores]
            if max(scores_i) - min(scores_i) > self.equilibrium_tolerance:
                self.consecutive_no_improvement = 0
                return False, []
        
        # Use interaction tracker for equilibrium detection
        is_equilibrium, equilibrium_pairs = self.interaction_tracker.detect_nash_equilibrium(
            self.module_scores, self.dependency_matrix
        )
        
        if is_equilibrium:
            self.in_equilibrium = True
            self.equilibrium_iterations += 1
            self.equilibrium_detected = True
            self.equilibrium_pairs = equilibrium_pairs
            return True, equilibrium_pairs
        
        return False, []

    def update_module_improvement(self, module_idx: int, improved: bool) -> None:
        """
        Update the improvement history for a specific module.
        
        Args:
            module_idx: Index of the module
            improved: Whether the module improved in this cycle
        """
        self.module_improvement_history[module_idx].append(improved)
        self.interaction_tracker.update_module_improvement(module_idx, improved)

    def detect_nash_equilibrium_with_stats(self, module_stats: Dict[Tuple[int, int], Dict[str, int]]) -> List[Tuple[int, int]]:
        """
        Nash equilibrium detection function that tracks module interaction frequencies and success rates.
        
        Accepts a dictionary of module interaction stats (module_pair -> {attempts, successes, failures}),
        identifies pairs where no single module change improves the success rate by more than 5%
        over the last 10 attempts, and returns a list of module pairs at equilibrium.
        
        Args:
            module_stats: Dictionary mapping module pairs (i, j) to their interaction stats.
                         Each stat dict must have 'attempts', 'successes', and 'failures' keys.
                         Example: {(0, 1): {'attempts': 10, 'successes': 8, 'failures': 2}}
        
        Returns:
            List of module pairs (tuples) that are at Nash equilibrium
        """
        equilibrium_pairs = []
        
        # Process each module pair
        for pair_key, stats in module_stats.items():
            # Validate stats
            if 'attempts' not in stats or 'successes' not in stats or 'failures' not in stats:
                continue
            
            attempts = stats['attempts']
            successes = stats['successes']
            failures = stats['failures']
            
            # Need at least 10 attempts to evaluate equilibrium
            if attempts < 10:
                continue
            
            # Calculate current success rate
            current_success_rate = successes / attempts if attempts > 0 else 0.0
            
            # Check if no single module change improves the success rate by more than 5%
            # We simulate changes by considering what happens