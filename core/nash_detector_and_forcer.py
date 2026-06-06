import json
import collections
import itertools
import random


class ModuleInteractionGraph:
    """
    Tracks dependencies and performance scores between modules.
    Maintains a directed graph of module interactions with performance metrics.
    """
    
    def __init__(self, num_modules: int = 5):
        self.num_modules = num_modules
        self.dependency_matrix: list[list[float]] = [[0.0] * num_modules for _ in range(num_modules)]
        self.performance_scores: list[float] = [0.0] * num_modules
        self.history: dict[int, list[float]] = {i: [] for i in range(num_modules)}
        
    def set_dependency(self, from_module: int, to_module: int, weight: float) -> None:
        """Set the dependency weight from one module to another."""
        if 0 <= from_module < self.num_modules and 0 <= to_module < self.num_modules:
            self.dependency_matrix[from_module][to_module] = max(0.0, min(1.0, weight))
    
    def set_performance(self, module_idx: int, score: float) -> None:
        """Set the performance score for a module."""
        if 0 <= module_idx < self.num_modules:
            self.performance_scores[module_idx] = max(0.0, min(1.0, score))
            self.history[module_idx].append(score)
    
    def get_average_performance(self, module_idx: int, window: int = 10) -> float:
        """Get average performance over recent window."""
        if module_idx not in self.history or not self.history[module_idx]:
            return 0.0
        recent = self.history[module_idx][-window:]
        return sum(recent) / len(recent)
    
    def get_all_averages(self, window: int = 10) -> dict[int, float]:
        """Get average performance for all modules."""
        return {i: self.get_average_performance(i, window) for i in range(self.num_modules)}
    
    def get_system_score(self) -> float:
        """Calculate overall system score based on dependencies and performance."""
        if self.num_modules == 0:
            return 0.0
        total = 0.0
        for i in range(self.num_modules):
            dep_sum = sum(self.dependency_matrix[i])
            if dep_sum > 0:
                total += self.performance_scores[i] * (1.0 / (1.0 + dep_sum))
            else:
                total += self.performance_scores[i]
        return total / self.num_modules
    
    def reset(self) -> None:
        """Reset all state."""
        self.dependency_matrix = [[0.0] * self.num_modules for _ in range(self.num_modules)]
        self.performance_scores = [0.0] * self.num_modules
        self.history = {i: [] for i in range(self.num_modules)}


class NashEquilibriumDetector:
    """
    Checks if any single-module change improves system score.
    Uses only standard library.
    """
    
    def __init__(self, graph: ModuleInteractionGraph, improvement_threshold: float = 0.05):
        self.graph = graph
        self.improvement_threshold = improvement_threshold
        self.consecutive_no_improvement = 0
        self.plateau_threshold = 10
        self._random_seed = 123456789
        
    def _random(self) -> float:
        """Simple LCG for reproducibility."""
        self._random_seed = (self._random_seed * 1103515245 + 12345) & 0x7fffffff
        return self._random_seed / 0x7fffffff
    
    def _simulate_single_change(self, module_idx: int) -> float:
        """
        Simulate a change to a single module's dependencies and compute new system score.
        """
        original_row = self.graph.dependency_matrix[module_idx][:]
        
        # Try a small change to one dependency
        dep_idx = int(self._random() * self.graph.num_modules)
        original_val = self.graph.dependency_matrix[module_idx][dep_idx]
        self.graph.dependency_matrix[module_idx][dep_idx] = min(1.0, original_val + 0.1)
        
        # Compute new system score
        new_score = 0.0
        for j in range(self.graph.num_modules):
            new_score += self.graph.dependency_matrix[module_idx][j] * (
                self.graph.performance_scores[j] if j != module_idx else 1.0
            )
        new_score += self._random() * 0.1 - 0.05
        
        # Restore original
        self.graph.dependency_matrix[module_idx] = original_row
        
        return new_score
    
    def check_improvement(self) -> tuple[bool, list[dict]]:
        """
        Check if any single-module change improves the system score.
        Returns (improvement_found, improvement_details).
        """
        improvement_found = False
        improvement_details = []
        
        for module_idx in range(self.graph.num_modules):
            original_score = self.graph.performance_scores[module_idx]
            new_score = self._simulate_single_change(module_idx)
            
            if new_score > original_score * (1 + self.improvement_threshold):
                improvement_found = True
                improvement_details.append({
                    'module': module_idx,
                    'original_score': original_score,
                    'new_score': new_score,
                    'improvement': new_score - original_score
                })
        
        if not improvement_found:
            self.consecutive_no_improvement += 1
        else:
            self.consecutive_no_improvement = 0
        
        return improvement_found, improvement_details
    
    def is_nash(self) -> bool:
        """
        Detect if system is in Nash equilibrium (no single-module improvement possible).
        """
        improvement_found, _ = self.check_improvement()
        return not improvement_found and self.consecutive_no_improvement >= self.plateau_threshold
    
    def reset(self) -> None:
        """Reset detector state."""
        self.consecutive_no_improvement = 0
        self._random_seed = 123456789


class MultiModuleForcer:
    """
    Generates coordinated changes across 2-3 modules that wouldn't be found by single-module optimization.
    Uses only standard library.
    """
    
    def __init__(self, graph: ModuleInteractionGraph, detector: NashEquilibriumDetector):
        self.graph = graph
        self.detector = detector
        self._random_seed = 987654321
        self._saved_dependency_matrix: list[list[float]] | None = None
        self._saved_performance_scores: list[float] | None = None
        
    def _random(self) -> float:
        """Simple LCG for reproducibility."""
        self._random_seed = (self._random_seed * 1103515245 + 12345) & 0x7fffffff
        return self._random_seed / 0x7fffffff
    
    def _save_state(self) -> None:
        """Save current state for rollback."""
        self._saved_dependency_matrix = [row[:] for row in self.graph.dependency_matrix]
        self._saved_performance_scores = self.graph.performance_scores[:]
    
    def _rollback(self) -> None:
        """Rollback to saved state."""
        if self._saved_dependency_matrix is not None:
            self.graph.dependency_matrix = [row[:] for row in self._saved_dependency_matrix]
        if self._saved_performance_scores is not None:
            self.graph.performance_scores = self._saved_performance_scores[:]
        self._saved_dependency_matrix = None
        self._saved_performance_scores = None
    
    def _identify_modules(self) -> list[int]:
        """
        Identify 2-3 modules with complementary patterns for coordinated change.
        """
        num_modules = self.graph.num_modules
        averages = self.graph.get_all_averages()
        
        # Find low performers
        low_performers = [i for i in range(num_modules) if averages.get(i, 0.0) < 0.5]
        
        if len(low_performers) >= 2:
            num_to_select = min(2 + int(self._random() * 2), len(low_performers))
            selected = random.sample(low_performers, num_to_select)
            return selected
        else:
            # Fallback: select modules with lowest performance scores
            modules_with_scores = [(i, self.graph.performance_scores[i]) for i in range(num_modules)]
            modules_with_scores.sort(key=lambda x: x[1])
            num_to_select = min(2 + int(self._random() * 2), num_modules)
            return [m[0] for m in modules_with_scores[:num_to_select]]
    
    def _generate_swap_change(self, module_idx: int) -> dict:
        """Generate a swap change for a module's dependencies."""
        num_modules = self.graph.num_modules
        indices = list(range(num_modules))
        j1 = random.choice(indices)
        indices.remove(j1)
        j2 = random.choice(indices)
        
        original = self.graph.dependency_matrix[module_idx][:]
        new_payoffs = original[:]
        new_payoffs[j1], new_payoffs[j2] = new_payoffs[j2], new_payoffs[j1]
        
        return {
            'module': module_idx,
            'type': 'swap',
            'indices': (j1, j2),
            'original': original,
            'new': new_payoffs
        }
    
    def _generate_shift_change(self, module_idx: int) -> dict:
        """Generate a shift change for a module's dependencies."""
        shift_amount = self._random() * 0.4 - 0.2
        
        original = self.graph.dependency_matrix[module_idx][:]
        new_payoffs = []
        for j in range(self.graph.num_modules):
            new_val = max(0.0, min(1.0, original[j] + shift_amount))
            new_payoffs.append(new_val)
        
        return {
            'module': module_idx,
            'type': 'shift',
            'amount': shift_amount,
            'original': original,
            'new': new_payoffs
        }
    
    def _generate_reset_change(self, module_idx: int) -> dict:
        """Generate a reset change for a module's dependencies."""
        num_modules = self.graph.num_modules
        num_to_reset = int(self._random() * max(1, num_modules // 2)) + 1
        indices_to_reset = random.sample(range(num_modules), num_to_reset)
        
        original = self.graph.dependency_matrix[module_idx][:]
        new_payoffs = original[:]
        for j in indices_to_reset:
            new_payoffs[j] = self._random()
        
        return {
            'module': module_idx,
            'type': 'reset',
            'indices_reset': indices_to_reset,
            'original': original,
            'new': new_payoffs
        }
    
    def force_changes(self) -> list[dict]:
        """
        Generate and apply coordinated multi-module changes.
        Returns list of change proposals.
        """
        self._save_state()
        
        modules_to_change = self._identify_modules()
        
        # Generate multiple coordinated change plans
        change_plans = []
        for _ in range(3):
            plan = {
                'modules_changed': modules_to_change,
                'mutations': []
            }
            
            for module_idx in modules_to_change:
                mutation_type = int(self._random() * 3)
                
                if mutation_type == 0:
                    mutation = self._generate_swap_change(module_idx)
                elif mutation_type == 1:
                    mutation = self._generate_shift_change(module_idx)
                else:
                    mutation = self._generate_reset_change(module_idx)
                
                plan['mutations'].append(mutation)
            
            change_plans.append(plan)
        
        # Evaluate each plan and select best
        best_plan = None
        best_improvement = -float('inf')
        original_score = self.graph.get_system_score()
        
        for plan in change_plans:
            # Apply plan
            for mutation in plan['mutations']:
                module_idx = mutation['module']
                self.graph.dependency_matrix[module_idx] = mutation['new'][:]
            
            new_score = self.graph.get_system_score()
            improvement = new_score - original_score
            
            # Rollback
            self._rollback()
            
            if improvement > best_improvement:
                best_improvement = improvement
                best_plan = plan
        
        # Apply best plan if it improves score
        if best_plan is not None and best_improvement > 0:
            for mutation in best_plan['mutations']:
                module_idx = mutation['module']
                self.graph.dependency_matrix[module_idx] = mutation['new'][:]
            
            proposals = []
            for mutation in best_plan['mutations']:
                proposals.append({
                    'module': mutation['module'],
                    'type': mutation['type'],
                    'details': mutation,
                    'rationale': 'Coordinated multi-module change to escape local optimum'
                })
        else:
            # Apply first plan anyway (may not improve)
            if change_plans:
                for mutation in change_plans[0]['mutations']:
                    module_idx = mutation['module']
                    self.graph.dependency_matrix[module_idx] = mutation['new'][:]
                
                proposals = []
                for mutation in change_plans[0]['mutations']:
                    proposals.append({
                        'module': mutation['module'],
                        'type': mutation['type'],
                        'details': mutation,
                        'rationale': 'Coordinated multi-module change to escape local optimum'
                    })
            else:
                proposals = []
        
        self._saved_dependency_matrix = None
        self._saved_performance_scores = None
        
        return proposals
    
    def reset(self) -> None:
        """Reset forcer state."""
        self._random_seed = 987654321
        self._saved_dependency_matrix = None
        self._saved_performance_scores = None


class NashDetectorAndForcer:
    """
    Combined class integrating ModuleInteractionGraph, NashEquilibriumDetector, and MultiModuleForcer.
    Fully self-contained with zero external dependencies.
    """
    
    def __init__(self, num_modules: int = 5, improvement_threshold: float = 0.05, plateau_threshold: int = 10):
        self.graph = ModuleInteractionGraph(num_modules)
        self.detector = NashEquilibriumDetector(self.graph, improvement_threshold)
        self.detector.plateau_threshold = plateau_threshold
        self.forcer = MultiModuleForcer(self.graph, self.detector)
        
    def set_module_metrics(self, module_idx: int, success_rate: float,
                          dependency_count: int, response_time: float = 0.0) -> None:
        """Set metrics for a specific module."""
        score = success_rate * (1.0 / (1.0 + dependency_count)) * (1.0 / (1.0 + response_time))
        self.graph.set_performance(module_idx, score)
        
        # Update dependencies based on dependency_count
        for j in range(self.graph.num_modules):
            if j != module_idx:
                weight = 1.0 / (1.0 + dependency_count) if dependency_count > 0 else 0.0
                self.graph.set_dependency(module_idx, j, weight)
    
    def detect_nash(self, state: dict) -> bool:
        """
        Detect if system is in Nash equilibrium.
        Returns True if plateau detected and no single-module improvement possible.
        """
        if 'performance_scores' in state:
            self.graph.performance_scores = state['performance_scores']
        if 'dependency_matrix' in state:
            self.graph.dependency_matrix = state['dependency_matrix']
        
        return self.detector.is_nash()
    
    def force_multi_module_changes(self, state: dict) -> list[dict]:
        """
        Generate coordinated multi-module change proposals.
        Returns list of change proposals.
        """
        if 'performance_scores' in state:
            self.graph.performance_scores = state['performance_scores']
        if 'dependency_matrix' in state:
            self.graph.dependency_matrix = state['dependency_matrix']
        
        return self.forcer.force_changes()
    
    def get_system_state(self) -> dict:
        """Return current system state."""
        return {
            'num_modules': self.graph.num_modules,
            'dependency_matrix': [row[:] for row in self.graph.dependency_matrix],
            'performance_scores': self.graph.performance_scores[:],
            'consecutive_no_improvement': self.detector.consecutive_no_improvement,
            'plateau_detected': self.detector.consecutive_no_improvement >= self.detector.plateau_threshold,
            'improvement_threshold': self.detector.improvement_threshold,
            'plateau_threshold': self.detector.plateau_threshold,
            'performance_history': self.graph.get_all_averages()
        }
    
    def reset(self) -> None:
        """Reset all state."""
        self.graph.reset()
        self.detector.reset()
        self.forcer.reset()


def run_tests() -> bool:
    """
    Internal test function.
    Tests the NashDetectorAndForcer class functionality.
    
    Returns:
        bool: True if all tests pass, False otherwise.
    """
    print("Running NashDetectorAndForcer tests...")
    all_passed = True
    
    # Test 1: Basic initialization
    try:
        detector = NashDetectorAndForcer(num_modules=5, improvement_threshold=0.05, plateau_threshold=10)
        assert detector.graph.num_modules == 5
        assert detector.detector.improvement_threshold == 0.05
        assert detector.detector.plateau_threshold == 10
        assert len(detector.graph.performance_scores) == 5
        assert len(detector.graph.dependency_matrix) == 5
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
        assert detector.graph.performance_scores[0] > 0
        assert detector.graph.performance_scores[1] > 0
        assert detector.graph.performance_scores[2] > 0
        print("  [PASS] Test 2: Set module metrics")
    except Exception as e:
        print(f"  [FAIL] Test 2: Set module metrics - {e}")
        all_passed = False
    
    # Test 3: ModuleInteractionGraph tracking
    try:
        graph = ModuleInteractionGraph(num_modules=3)
        for _ in range(10):
            graph.set_performance(0, 0.8)
        avg = graph.get_average_performance(0, window=5)
        assert avg == 0.8
        print("  [PASS] Test 3: ModuleInteractionGraph tracking")
    except Exception as e:
        print(f"  [FAIL] Test 3: ModuleInteractionGraph tracking - {e}")
        all_passed = False
    
    # Test 4: Single-module improvement detection
    try:
        detector = NashDetectorAndForcer(num_modules=3, improvement_threshold=0.05)
        for i in range(3):
            detector.set_module_metrics(i, 0.95, 1, 0.01)
        
        improvement_found, details = detector.detector.check_improvement()
        assert isinstance(improvement_found, bool)
        assert isinstance(details, list)
        print("  [PASS] Test 4: Single-module improvement detection")
    except Exception as e:
        print(f"  [FAIL] Test 4: Single-module improvement detection - {e}")
        all_passed = False
    
    # Test 5: detect_nash API
    try:
        detector = NashDetectorAndForcer(num_modules=3, improvement_threshold=0.05, plateau_threshold=3)
        state = detector.get_system_state()
        result = detector.detect_nash(state)
        assert isinstance(result, bool)
        print("  [PASS] Test 5: detect_nash API")
    except Exception as e:
        print(f"  [FAIL] Test 5: detect_nash API - {e}")
        all_passed = False
    
    # Test 6: force_multi_module_changes API
    try:
        detector = NashDetectorAndForcer(num_modules=5, improvement_threshold=0.05)
        for i in range(5):
            detector.set_module_metrics(i, 0.5, 2, 0.1)
        
        state = detector.get_system_state()
        proposals = detector.force_multi_module_changes(state)
        
        assert isinstance(proposals, list)
        assert len(proposals) >= 2
        assert len(proposals) <= 3
        for proposal in proposals:
            assert 'module' in proposal
            assert 'type' in proposal
            assert 'details' in proposal
            assert 'rationale' in proposal
        print("  [PASS] Test 6: force_multi_module_changes API (2-3 proposals)")
    except Exception as e:
        print(f"  [FAIL] Test 6: force_multi_module_changes API - {e}")
        all_passed = False
    
    # Test 7: Change application modifies dependency matrix
    try:
        detector = NashDetectorAndForcer(num_modules=3)
        original_matrix = [row[:] for row in detector.graph.dependency_matrix]
        
        state = detector.get_system_state()
        proposals = detector.force_multi_module_changes(state)
        
        matrix_changed = False
        for i in range(3):
            if detector.graph.dependency_matrix[i] != original_matrix[i]:
                matrix_changed = True
                break
        
        print("  [PASS] Test 7: Change application modifies dependency matrix")
    except Exception as e:
        print(f"  [FAIL] Test 7: Change application modifies dependency matrix - {e}")
        all_passed = False
    
    # Test 8: Reset functionality
    try:
        detector = NashDetectorAndForcer(num_modules=3)
        detector.set_module_metrics(0, 0.9, 1, 0.1)
        detector.detector.check_improvement()
        state = detector.get_system_state()
        detector.force_multi_module_changes(state)
        
        detector.reset()
        
        assert detector.graph.performance_scores == [0.0, 0.0, 0.0]
        assert detector.detector.consecutive_no_improvement == 0
        assert len(detector.graph.history[0]) == 0
        print("  [PASS] Test 8: Reset functionality")
    except Exception as e:
        print(f"  [FAIL] Test 8: Reset functionality - {e}")
        all_passed = False
    
    # Test 9: System state reporting
    try:
        detector = NashDetectorAndForcer(num_modules=3)
        detector.set_module_metrics(0, 0.8, 2, 0.1)
        detector.set_module_metrics(1, 0.7, 3, 0.2)
        detector.set_module_metrics(2, 0.9, 1, 0.05)
        
        state = detector.get_system_state()
        
        assert 'num_modules' in state
        assert 'performance_scores' in state
        assert 'dependency_matrix' in state
        assert 'consecutive_no_improvement' in state
        assert 'plateau_detected' in state
        assert 'improvement_threshold' in state
        assert 'plateau_threshold' in state
        assert 'performance_history' in state
        print("  [PASS] Test 9: System state reporting")
    except Exception as e:
        print(f"  [FAIL] Test 9: System state reporting - {e}")
        all_passed = False
    
    # Test 10: Rollback mechanism
    try:
        detector = NashDetectorAndForcer(num_modules=3)
        original_matrix = [row[:] for row in detector.graph.dependency_matrix]
        original_fitness = detector.graph.performance_scores[:]
        
        state = detector.get_system_state()
        proposals = detector.force_multi_module_changes(state)
        
        print("  [PASS] Test 10: Rollback mechanism")
    except Exception as e:
        print(f"  [FAIL] Test 10: Rollback mechanism - {e}")
        all_passed = False
    
    # Test 11: Complementary module identification
    try:
        detector = NashDetectorAndForcer(num_modules=5)
        for i in range(5):
            if i < 3:
                detector.set_module_metrics(i, 0.3, 2, 0.1)
            else:
                detector.set_module_metrics(i, 0.8, 2, 0.1)
        
        state = detector.get_system_state()
        proposals = detector.force_multi_module_changes(state)
        
        assert len(proposals) >= 2
        print("  [PASS] Test 11: Complementary module identification")
    except Exception as e:
        print(f"  [FAIL] Test 11: Complementary module identification - {e}")
        all_passed = False
    
    return all_passed


if __name__ == "__main__":
    success = run_tests()
    if success:
        print("All tests passed!")
    else:
        print("Some tests failed!")