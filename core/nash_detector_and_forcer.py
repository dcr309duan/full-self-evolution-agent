import json
from collections import defaultdict, deque
from itertools import combinations
from typing import List, Dict, Tuple, Optional, Any, Deque, Set
from datetime import datetime


class NashDetector:
    """
    Tracks module interaction scores and detects when no single-module change improves the system.
    Uses only standard library imports.
    """
    
    def __init__(self, num_modules: int = 5, nash_threshold: int = 5):
        self.num_modules = num_modules
        self.nash_threshold = nash_threshold
        self._random_seed = 123456789
        
        # Per-module pair mutation outcome history (last 20 per pair)
        self.mutation_outcomes: Dict[Tuple[int, int], List[float]] = defaultdict(lambda: deque(maxlen=20))
        
        # Module fitness scores
        self.fitness_scores: List[float] = [0.0] * num_modules
        
        # Dependency matrix (module_i -> list of dependency strengths)
        self.dependency_matrix: List[List[float]] = [
            [self._random() for _ in range(num_modules)] for _ in range(num_modules)
        ]
        
        # Equilibrium tracking
        self.in_equilibrium: bool = False
        self.equilibrium_iterations: int = 0
        self.consecutive_no_improvement: int = 0
        self.equilibrium_pairs: List[Tuple[int, int]] = []
        
        # Performance window for tracking
        self.performance_window: Deque[Dict[str, Any]] = deque(maxlen=50)
        
        # Change history
        self.change_history: List[Dict[str, Any]] = []
        
        # Improvement threshold
        self.improvement_threshold: float = 0.05
        
        # Module interaction graph tracking co-modifications in last 10 cycles
        self.module_interaction_graph: Dict[Tuple[int, int], int] = defaultdict(int)
        self.interaction_cycle_count: int = 0
        self.max_interaction_cycles: int = 10
        
        # Track which modules have been modified together in recent cycles
        self.recent_co_modifications: Deque[Set[Tuple[int, int]]] = deque(maxlen=10)
        
    def _random(self) -> float:
        """Simple linear congruential generator for reproducibility."""
        self._random_seed = (self._random_seed * 1103515245 + 12345) & 0x7fffffff
        return self._random_seed / 0x7fffffff
    
    def set_module_metrics(self, module_idx: int, success_rate: float, 
                          dependency_count: int, response_time: float = 0.0) -> None:
        """Set metrics for a specific module and update its fitness score."""
        self.fitness_scores[module_idx] = (
            success_rate * (1.0 / (1.0 + dependency_count)) * (1.0 / (1.0 + response_time))
        )
    
    def record_mutation_outcome(self, module_i: int, module_j: int, fitness_change: float) -> None:
        """
        Record the outcome of a mutation between two modules.
        Maintains a sliding window of the last 20 outcomes per pair.
        """
        key = (module_i, module_j)
        self.mutation_outcomes[key].append(fitness_change)
    
    def record_co_modification(self, modules: List[int]) -> None:
        """
        Record that a set of modules were modified together in the current cycle.
        Updates the module interaction graph.
        """
        if len(modules) < 2:
            return
        
        # Create set of all pairs from the modified modules
        current_pairs: Set[Tuple[int, int]] = set()
        for i in range(len(modules)):
            for j in range(i + 1, len(modules)):
                pair = (min(modules[i], modules[j]), max(modules[i], modules[j]))
                current_pairs.add(pair)
                self.module_interaction_graph[pair] += 1
        
        # Add to recent co-modifications deque
        self.recent_co_modifications.append(current_pairs)
        
        # Clean up old interactions (keep only last max_interaction_cycles)
        self._cleanup_old_interactions()
        
        self.interaction_cycle_count += 1
    
    def _cleanup_old_interactions(self) -> None:
        """
        Remove interaction counts that are older than max_interaction_cycles.
        This ensures the graph only reflects recent co-modifications.
        """
        if len(self.recent_co_modifications) < self.max_interaction_cycles:
            return
        
        # When deque is full, the oldest entry is automatically removed
        # We need to decrement counts for pairs that are no longer in the window
        # Since deque handles removal, we rebuild counts from current window
        self.module_interaction_graph.clear()
        for cycle_pairs in self.recent_co_modifications:
            for pair in cycle_pairs:
                self.module_interaction_graph[pair] += 1
    
    def get_co_modified_pairs(self, min_interactions: int = 1) -> List[Tuple[int, int]]:
        """
        Get all module pairs that have been co-modified at least min_interactions times
        in the last max_interaction_cycles cycles.
        """
        return [pair for pair, count in self.module_interaction_graph.items() 
                if count >= min_interactions]
    
    def get_missing_co_modifications(self) -> List[Tuple[int, int]]:
        """
        Identify module pairs that haven't been co-modified but should be,
        based on dependency analysis. Returns pairs that have strong dependencies
        but no recent co-modifications.
        """
        missing_pairs = []
        
        # Get pairs that have been co-modified recently
        co_modified = set(self.get_co_modified_pairs(min_interactions=1))
        
        # Analyze dependency strength to find pairs that should be co-modified
        for i in range(self.num_modules):
            for j in range(i + 1, self.num_modules):
                pair = (i, j)
                
                # Skip if already co-modified
                if pair in co_modified:
                    continue
                
                # Calculate dependency strength between modules
                dep_strength = (
                    self.dependency_matrix[i][j] + 
                    self.dependency_matrix[j][i]
                ) / 2.0
                
                # If dependency is strong, suggest co-modification
                if dep_strength > 0.7:  # Threshold for strong dependency
                    missing_pairs.append(pair)
        
        return missing_pairs
    
    def _simulate_single_module_change(self, module_idx: int) -> float:
        """
        Simulate a change to a single module and compute the resulting fitness score.
        Returns the new fitness score.
        """
        original_deps = self.dependency_matrix[module_idx][:]
        
        # Try a small change to one dependency
        dep_idx = int(self._random() * self.num_modules)
        original_value = self.dependency_matrix[module_idx][dep_idx]
        self.dependency_matrix[module_idx][dep_idx] = min(1.0, original_value + 0.1)
        
        # Compute new fitness score
        new_score = 0.0
        for j in range(self.num_modules):
            new_score += self.dependency_matrix[module_idx][j] * (
                self.fitness_scores[j] if j != module_idx else 1.0
            )
        new_score += self._random() * 0.1 - 0.05
        
        # Restore original
        self.dependency_matrix[module_idx] = original_deps
        
        return new_score
    
    def _check_single_module_improvement(self) -> Tuple[bool, List[Dict[str, Any]]]:
        """
        Check if any single-module change improves the system's fitness score.
        Returns (improvement_found, improvement_details).
        """
        improvement_found = False
        improvement_details = []
        
        for module_idx in range(self.num_modules):
            original_score = self.fitness_scores[module_idx]
            new_score = self._simulate_single_module_change(module_idx)
            
            if new_score > original_score * (1 + self.improvement_threshold):
                improvement_found = True
                improvement_details.append({
                    'module': module_idx,
                    'original_score': original_score,
                    'new_score': new_score,
                    'improvement': new_score - original_score
                })
        
        return improvement_found, improvement_details
    
    def check_equilibrium(self) -> Tuple[bool, List[Dict[str, Any]]]:
        """
        Check if the system is in Nash equilibrium.
        Analyzes the last 20 mutation outcomes per module pair and checks if any
        single-module change improves the system's fitness score.
        
        Returns:
            Tuple[bool, List[Dict]]: (is_equilibrium, improvement_details)
        """
        # Check if any single-module change improves fitness
        improvement_found, improvement_details = self._check_single_module_improvement()
        
        # Also check mutation outcome history for recent improvements
        for key, outcomes in self.mutation_outcomes.items():
            if len(outcomes) >= 20:
                recent_outcomes = list(outcomes)[-20:]
                avg_change = sum(recent_outcomes) / len(recent_outcomes)
                if avg_change > self.improvement_threshold:
                    improvement_found = True
                    improvement_details.append({
                        'module_pair': key,
                        'avg_fitness_change': avg_change,
                        'source': 'mutation_history'
                    })
        
        if not improvement_found:
            self.consecutive_no_improvement += 1
        else:
            self.consecutive_no_improvement = 0
        
        # Nash equilibrium detected when no improvement for N consecutive checks
        is_nash = self.consecutive_no_improvement >= self.nash_threshold
        
        if is_nash:
            self.in_equilibrium = True
            self.equilibrium_iterations += 1
            
            # Find equilibrium pairs (modules with similar fitness scores)
            self.equilibrium_pairs = []
            for i in range(self.num_modules):
                for j in range(i + 1, self.num_modules):
                    if abs(self.fitness_scores[i] - self.fitness_scores[j]) < 0.001:
                        self.equilibrium_pairs.append((i, j))
        else:
            self.in_equilibrium = False
            self.equilibrium_pairs = []
        
        # Update performance window
        window_entry = {
            'timestamp': len(self.change_history),
            'fitness_scores': self.fitness_scores[:],
            'in_equilibrium': is_nash,
            'consecutive_no_improvement': self.consecutive_no_improvement
        }
        self.performance_window.append(window_entry)
        
        return is_nash, improvement_details
    
    def get_system_state(self) -> Dict[str, Any]:
        """Return the current system state."""
        return {
            'num_modules': self.num_modules,
            'dependency_matrix': [row[:] for row in self.dependency_matrix],
            'fitness_scores': self.fitness_scores[:],
            'in_equilibrium': self.in_equilibrium,
            'equilibrium_pairs': self.equilibrium_pairs,
            'equilibrium_iterations': self.equilibrium_iterations,
            'consecutive_no_improvement': self.consecutive_no_improvement,
            'nash_threshold': self.nash_threshold,
            'performance_window': list(self.performance_window),
            'change_history': self.change_history,
            'mutation_outcomes': {
                str(k): list(v) for k, v in self.mutation_outcomes.items()
            },
            'module_interaction_graph': {
                str(k): v for k, v in self.module_interaction_graph.items()
            },
            'missing_co_modifications': self.get_missing_co_modifications(),
            'interaction_cycle_count': self.interaction_cycle_count
        }
    
    def reset(self) -> None:
        """Reset all tracked state to initial values."""
        self._random_seed = 123456789
        self.mutation_outcomes.clear()
        self.fitness_scores = [0.0] * self.num_modules
        self.dependency_matrix = [
            [self._random() for _ in range(self.num_modules)] for _ in range(self.num_modules)
        ]
        self.in_equilibrium = False
        self.equilibrium_iterations = 0
        self.consecutive_no_improvement = 0
        self.equilibrium_pairs = []
        self.performance_window.clear()
        self.change_history.clear()
        self.module_interaction_graph.clear()
        self.recent_co_modifications.clear()
        self.interaction_cycle_count = 0


class MultiModuleForcer:
    """
    Generates coordinated changes across 3+ modules to escape Nash equilibria.
    Uses only standard library imports.
    """
    
    def __init__(self, detector: NashDetector):
        self.detector = detector
        self._random_seed = 987654321
        
    def _random(self) -> float:
        """Simple linear congruential generator for reproducibility."""
        self._random_seed = (self._random_seed * 1103515245 + 12345) & 0x7fffffff
        return self._random_seed / 0x7fffffff
    
    def _select_modules_for_change(self) -> List[int]:
        """
        Select 3+ modules for coordinated change.
        Prioritizes modules that are part of equilibrium pairs.
        Also considers missing co-modifications to suggest combinations
        that haven't been tried together recently.
        """
        num_modules = self.detector.num_modules
        equilibrium_pairs = self.detector.equilibrium_pairs
        fitness_scores = self.detector.fitness_scores
        missing_pairs = self.detector.get_missing_co_modifications()
        
        # Try to include modules from missing co-modification pairs
        if missing_pairs:
            modules_from_missing = set()
            for pair in missing_pairs:
                modules_from_missing.add(pair[0])
                modules_from_missing.add(pair[1])
            
            if len(modules_from_missing) >= 3:
                selected = list(modules_from_missing)
                selected.sort(key=lambda x: fitness_scores[x] if x < len(fitness_scores) else 0)
                num_to_select = min(3 + int(self._random() * 2), len(selected), num_modules)
                return selected[:num_to_select]
        
        if equilibrium_pairs:
            modules_in_equilibrium = set()
            for pair in equilibrium_pairs:
                modules_in_equilibrium.add(pair[0])
                modules_in_equilibrium.add(pair[1])
            
            if len(modules_in_equilibrium) >= 3:
                selected = list(modules_in_equilibrium)
                # Sort by fitness score (ascending) to target weaker modules
                selected.sort(key=lambda x: fitness_scores[x] if x < len(fitness_scores) else 0)
                # Select 3-4 modules
                num_to_select = min(3 + int(self._random() * 2), len(selected), num_modules)
                return selected[:num_to_select]
        
        # Fallback: select modules with lowest fitness scores
        modules_with_scores = [(i, fitness_scores[i]) for i in range(num_modules)]
        modules_with_scores.sort(key=lambda x: x[1])
        num_to_select = min(3 + int(self._random() * 2), num_modules)
        return [m[0] for m in modules_with_scores[:num_to_select]]
    
    def _generate_swap_change(self, module_idx: int) -> Dict[str, Any]:
        """Generate a swap change for a module."""
        num_modules = self.detector.num_modules
        indices = list(range(num_modules))
        j1 = indices[int(self._random() * len(indices))]
        indices.remove(j1)
        j2 = indices[int(self._random() * len(indices))]
        
        original = self.detector.dependency_matrix[module_idx][:]
        new_deps = original[:]
        new_deps[j1], new_deps[j2] = new_deps[j2], new_deps[j1]
        
        return {
            'module': module_idx,
            'type': 'swap',
            'indices': (j1, j2),
            'original': original,
            'new': new_deps
        }
    
    def _generate_shift_change(self, module_idx: int) -> Dict[str, Any]:
        """Generate a shift change for a module."""
        shift_amount = self._random() * 0.4 - 0.2
        
        original = self.detector.dependency_matrix[module_idx][:]
        new_deps = []
        for j in range(self.detector.num_modules):
            new_val = max(0.0, min(1.0, original[j] + shift_amount))
            new_deps.append(new_val)
        
        return {
            'module': module_idx,
            'type': 'shift',
            'amount': shift_amount,
            'original': original,
            'new': new_deps
        }
    
    def _generate_reset_change(self, module_idx: int) -> Dict[str, Any]:
        """Generate a reset change for a module."""
        num_modules = self.detector.num_modules
        num_to_reset = int(self._random() * max(1, num_modules // 2)) + 1
        indices = list(range(num_modules))
        indices_to_reset = []
        for _ in range(num_to_reset):
            idx = indices[int(self._random() * len(indices))]
            indices_to_reset.append(idx)
            indices.remove(idx)
        
        original = self.detector.dependency_matrix[module_idx][:]
        new_deps = original[:]
        for j in indices_to_reset:
            new_deps[j] = self._random()
        
        return {
            'module': module_idx,
            'type': 'reset',
            'indices_reset': indices_to_reset,
            'original': original,
            'new': new_deps
        }
    
    def _score_combination(self, modules: List[int]) -> float:
        """
        Score a multi-module combination based on fitness scores and diversity.
        Higher scores indicate more promising combinations.
        """
        if not modules:
            return 0.0
        
        fitness_scores = self.detector.fitness_scores
        
        # Base score from average fitness
        avg_fitness = sum(fitness_scores[m] for m in modules if m < len(fitness_scores)) / len(modules)
        
        # Diversity bonus: prefer modules with different fitness levels
        fitness_values = [fitness_scores[m] for m in modules if m < len(fitness_scores)]
        if len(fitness_values) > 1:
            diversity = max(fitness_values) - min(fitness_values)
        else:
            diversity = 0.0
        
        # Size bonus: prefer larger combinations (up to 4)
        size_bonus = len(modules) / 4.0
        
        # Improvement potential: modules with lower fitness have more room for improvement
        improvement_potential = 0.0
        for m in modules:
            if m < len(fitness_scores):
                improvement_potential += (1.0 - fitness_scores[m])
        improvement_potential = improvement_potential / len(modules) if modules else 0.0
        
        # Combined score
        score = avg_fitness * 0.3 + diversity * 0.2 + size_bonus * 0.2 + improvement_potential * 0.3
        return score
    
    def force_multi_module_change(self) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Generate and apply a coordinated multi-module mutation plan.
        When equilibrium is detected, generates changes across 3+ modules
        that would be invisible to single-module optimization.
        
        Returns:
            Tuple[Dict, Dict]: (mutation_plan, execution_record)
        """
        modules_to_change = self._select_modules_for_change()
        
        # Score this combination
        combination_score = self._score_combination(modules_to_change)
        
        mutation_plan = {
            'type': 'coordinated_mutation',
            'modules_changed': modules_to_change,
            'mutations': [],
            'rationale': 'Coordinated multi-module change to escape local optimum',
            'combination_score': combination_score
        }
        
        for module_idx in modules_to_change:
            mutation_type = int(self._random() * 3)
            
            if mutation_type == 0:
                mutation = self._generate_swap_change(module_idx)
            elif mutation_type == 1:
                mutation = self._generate_shift_change(module_idx)
            else:
                mutation = self._generate_reset_change(module_idx)
            
            mutation_plan['mutations'].append(mutation)
        
        # Apply the changes
        execution_record = {
            'type': 'coordinated_mutation_executed',
            'modules_changed': modules_to_change,
            'mutations_applied': []
        }
        
        for mutation in mutation_plan['mutations']:
            module_idx = mutation['module']
            new_deps = mutation['new']
            
            self.detector.dependency_matrix[module_idx] = new_deps[:]
            
            execution_record['mutations_applied'].append({
                'module': module_idx,
                'type': mutation['type'],
                'new_dependencies': new_deps
            })
        
        self.detector.change_history.append(execution_record)
        
        # Record mutation outcomes for each pair
        for i in range(len(modules_to_change)):
            for j in range(i + 1, len(modules_to_change)):
                fitness_change = self._random() * 0.2 - 0.1  # Simulated fitness change
                self.detector.record_mutation_outcome(modules_to_change[i], modules_to_change[j], fitness_change)
        
        # Record co-modification in the interaction graph
        self.detector.record_co_modification(modules_to_change)
        
        return mutation_plan, execution_record


class NashDetectorAndForcer:
    """
    Combined class that integrates NashDetector and MultiModuleForcer
    with the evolution orchestrator via a simple API.
    Uses only standard library imports.
    """
    
    def __init__(self, num_modules: int = 5, nash_threshold: int = 5):
        self.detector = NashDetector(num_modules, nash_threshold)
        self.forcer = MultiModuleForcer(self.detector)
        
    def set_module_metrics(self, module_idx: int, success_rate: float, 
                          dependency_count: int, response_time: float = 0.0) -> None:
        """Set metrics for a specific module."""
        self.detector.set_module_metrics(module_idx, success_rate, dependency_count, response_time)
    
    def record_mutation_outcome(self, module_i: int, module_j: int, fitness_change: float) -> None:
        """Record mutation outcome between two modules."""
        self.detector.record_mutation_outcome(module_i, module_j, fitness_change)
    
    def check_equilibrium(self) -> Tuple[bool, List[Dict[str, Any]]]:
        """Check if system is in Nash equilibrium."""
        return self.detector.check_equilibrium()
    
    def force_multi_module_change(self) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Force a coordinated multi-module change."""
        return self.forcer.force_multi_module_change()
    
    def get_system_state(self) -> Dict[str, Any]:
        """Return current system state."""
        return self.detector.get_system_state()
    
    def reset(self) -> None:
        """Reset all state."""
        self.detector.reset()


def run_tests() -> bool:
    """
    Internal test function that can be called standalone.
    Tests the NashDetectorAndForcer class functionality.
    
    Returns:
        bool: True if all tests pass, False otherwise.
    """
    print("Running NashDetectorAndForcer tests...")
    all_passed = True
    
    # Test 1: Basic initialization
    try:
        detector = NashDetectorAndForcer(num_modules=5, nash_threshold=3)
        assert detector.detector.num_modules == 5
        assert detector.detector.nash_threshold == 3
        assert len(detector.detector.fitness_scores) == 5
        assert len(detector.detector.dependency_matrix) == 5
        print("  [PASS] Test 1: Basic initialization")
    except Exception as e:
        print(f"  [FAIL] Test 1: Basic initialization - {e}")
        all_passed = False
    
    # Test 2: Set module metrics
    try:
        detector = NashDetectorAndForcer(num_modules=3)
        detector.set_module_metrics(0, 0.8, 2, 0.1)
        detector.set_module_metrics(1, 0.6, 3, 0.2)
        detector.set_module_metrics(2, 0.9, 1, 0.05)
        assert detector.detector.fitness_scores[0] > 0
        assert detector.detector.fitness_scores[1] > 0
        assert detector.detector.fitness_scores[2] > 0
        print("  [PASS] Test 2: Set module metrics")
    except Exception as e:
        print(f"  [FAIL] Test 2: Set module metrics - {e}")
        all_passed = False
    
    # Test 3: Record mutation outcomes
    try:
        detector = NashDetectorAndForcer(num_modules=3)
        for _ in range(25):
            detector.record_mutation_outcome(0, 1, 0.1)
        key = (0, 1)
        assert len(detector.detector.mutation_outcomes[key]) == 20  # Should be capped at 20
        print("  [PASS] Test 3: Record mutation outcomes (capped at 20)")
    except Exception as e:
        print(f"  [FAIL] Test 3: Record mutation outcomes - {e}")
        all_passed = False
    
    # Test 4: Equilibrium detection (no improvement)
    try:
        detector = NashDetectorAndForcer(num_modules=3, nash_threshold=3)
        # Set high fitness scores to make improvement unlikely
        for i in range(3):
            detector.set_module_metrics(i, 0.95, 1, 0.01)
        
        # Check equilibrium multiple times
        for _ in range(5):
            is_equilibrium, details = detector.check_equilibrium()
        
        assert detector.detector.in_equilibrium
        print("  [PASS] Test 4: Equilibrium detection")
    except Exception as e:
        print(f"  [FAIL] Test 4: Equilibrium detection - {e}")
        all_passed = False
    
    # Test 5: Multi-module change generation (3+ modules)
    try:
        detector = NashDetectorAndForcer(num_modules=5, nash_threshold=3)
        # Set some modules in equilibrium
        for i in range(5):
            detector.set_module_metrics(i, 0.5, 2, 0.1)
        
        # Force equilibrium
        for _ in range(5):
            detector.check_equilibrium()
        
        mutation_plan, execution_record = detector.force_multi_module_change()
        
        assert 'modules_changed' in mutation_plan
        assert len(mutation_plan['modules_changed']) >= 3
        assert len(mutation_plan['modules_changed']) <= 4
        assert len(mutation_plan['mutations']) == len(mutation_plan['modules_changed'])
        assert 'mutations_applied' in execution_record
        print("  [PASS] Test 5: Multi-module change generation (3+ modules)")
    except Exception as e:
        print(f"  [FAIL] Test 5: Multi-module change generation - {e}")
        all_passed = False
    
    # Test 6: Change application modifies dependency matrix
    try:
        detector = NashDetectorAndForcer(num_modules=3)
        original_matrix = [row[:] for row in detector.detector.dependency_matrix]
        
        for _ in range(3):
            detector.check_equilibrium()
        
        mutation_plan, execution_record = detector.force_multi_module_change()
        
        # Check that at least one dependency changed
        matrix_changed = False
        for i in range(3):
            if detector.detector.dependency_matrix[i] != original_matrix[i]:
                matrix_changed = True
                break
        
        assert matrix_changed
        print("  [PASS] Test 6: Change application modifies dependency matrix")
    except Exception as e:
        print(f"  [FAIL] Test 6: Change application modifies dependency matrix - {e}")
        all_passed = False
    
    # Test 7: Reset functionality
    try:
        detector = NashDetectorAndForcer(num_modules=3)
        detector.set_module_metrics(0, 0.9, 1, 0.1)
        detector.check_equilibrium()
        detector.force_multi_module_change()
        
        detector.reset()
        
        assert detector.detector.fitness_scores == [0.0, 0.0, 0.0]
        assert not detector.detector.in_equilibrium
        assert detector.detector.consecutive_no_improvement == 0
        assert len(detector.detector.change_history) == 0
        print("  [PASS] Test 7: Reset functionality")
    except Exception as e:
        print(f"  [FAIL] Test 7: Reset functionality - {e}")
        all_passed = False
    
    # Test 8: System state reporting
    try:
        detector = NashDetectorAndForcer(num_modules=3)
        detector.set_module_metrics(0, 0.8, 2, 0.1)
        detector.set_module_metrics(1, 0.7, 3, 0.2)
        detector.set_module_metrics(2, 0.9, 1, 0.05)
        
        state = detector.get_system_state()
        
        assert 'num_modules' in state
        assert 'fitness_scores' in state
        assert 'dependency_matrix' in state
        assert 'in_equilibrium' in state
        assert 'mutation_outcomes' in state
        assert 'module_interaction_graph' in state
        assert 'missing_co_modifications' in state
        print("  [PASS] Test 8: System state reporting")
    except Exception as e:
        print(f"  [FAIL] Test 8: System state reporting - {e}")
        all_passed = False
    
    # Test 9: Combination scoring
    try:
        detector = NashDetectorAndForcer(num_modules=5)
        detector.set_module_metrics(0, 0.9, 1, 0.1)
        detector.set_module_metrics(1, 0.5, 3, 0.3)
        detector.set_module_metrics(2, 0.7, 2, 0.2)
        
        score1 = detector.forcer._score_combination([0, 1])
        score2 = detector.forcer._score_combination([0, 1, 2])
        
        assert score1 > 0
        assert score2 > 0
        print("  [PASS] Test 9: Combination scoring")
    except Exception as e:
        print(f"  [FAIL] Test 9: Combination scoring - {e}")
        all_passed = False
    
    # Test 10: Mutation types
    try:
        detector = NashDetectorAndForcer(num_modules=5)
        swap = detector.forcer._generate_swap_change(0)
        shift = detector.forcer._generate_shift_change(1)
        reset = detector.forcer._generate_reset_change(2)
        
        assert swap['type'] == 'swap'
        assert shift['type'] == 'shift'
        assert reset['type'] == 'reset'
        assert len(swap['original']) == 5
        assert len(shift['new']) == 5
        assert len(reset['indices_reset']) >= 1
        print("  [PASS] Test 10: Mutation types")
    except Exception as e:
        print(f"  [FAIL] Test 10: Mutation types - {e}")
        all_passed = False
    
    # Test 11: Module interaction graph tracking
    try:
        detector = NashDetectorAndForcer(num_modules=5)
        
        # Record some co-modifications
        detector.detector.record_co_modification([0, 1, 2])
        detector.detector.record_co_modification([1, 2, 3])
        detector.detector.record_co_modification([0, 2, 4])
        
        # Check that pairs are tracked
        co_modified = detector.detector.get_co_modified_pairs(min_interactions=1)
        assert (0, 1) in co_modified
        assert (1, 2) in co_modified
        assert (0, 2) in co_modified
        
        # Check interaction counts
        assert detector.detector.module_interaction_graph[(0, 1)] == 1
        assert detector.detector.module_interaction_graph[(1, 2)] == 2  # Appears in two cycles
        
        print("  [PASS] Test 11: Module interaction graph tracking")
    except Exception as e:
        print(f"  [FAIL] Test 11: Module interaction graph tracking - {e}")
        all_passed = False
    
    # Test 12: Missing co-modifications detection
    try:
        detector = NashDetectorAndForcer(num_modules=3)
        
        # Set strong dependencies between some modules
        detector.detector.dependency_matrix[0][1] = 0.9
        detector.detector.dependency_matrix[1][0] = 0.8
        detector.detector.dependency_matrix[0][2] = 0.3
        detector.detector.dependency_matrix[2][0] = 0.2
        
        # Record co-modification for (0,1) only
        detector.detector.record_co_modification([0, 1])
        
        # Check that (0,2) is identified as missing (strong dependency, not co-modified)
        missing = detector.detector.get_missing_co_modifications()
        assert (0, 2) in missing or (2, 0) in missing
        
        print("  [PASS] Test 12: Missing co-modifications detection")
    except Exception as e:
        print(f"  [FAIL] Test 12: Missing co-modifications detection - {e}")
        all_passed = False
    
    # Test 13: Interaction graph cleanup after max cycles
    try:
        detector = NashDetectorAndForcer(num_modules=3)
        
        # Record co-modifications for more than max_interaction_cycles
        for i in range(15):
            detector.detector.record_co_modification([0, 1])
        
        # After 15 cycles with max 10, only last 10 should be tracked
        assert len(detector.detector.recent_co_modifications) == 10
        
        print("  [PASS] Test 13: Interaction graph cleanup after max cycles")
    except Exception as e:
        print(f"  [FAIL] Test 13: Interaction graph cleanup after max cycles - {e}")
        all_passed = False
    
    if all_passed:
        print("All tests passed!")
    else:
        print("Some tests failed!")
    
    return all_passed


if __name__ == "__main__":
    run_tests()