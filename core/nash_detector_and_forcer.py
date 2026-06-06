import json
from typing import List, Dict, Tuple, Optional, Any, Deque
from collections import defaultdict, deque

class DependencyGraphAnalyzer:
    """
    Analyzes import statements from Python source files to build a dependency graph.
    Uses only standard library (ast, os, sys).
    """
    
    def __init__(self, root_dir="."):
        self.root_dir = root_dir
        self.dependency_graph = defaultdict(set)
        self.module_imports = defaultdict(list)
        self.all_modules = set()
        
    def _get_python_files(self):
        """Recursively find all Python files in the root directory."""
        import os
        python_files = []
        for root, dirs, files in os.walk(self.root_dir):
            for file in files:
                if file.endswith('.py'):
                    python_files.append(os.path.join(root, file))
        return python_files
    
    def _parse_imports(self, filepath):
        """Parse import statements from a Python file using ast."""
        import ast
        imports = []
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                tree = ast.parse(f.read(), filename=filepath)
            
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.append(('import', alias.name))
                elif isinstance(node, ast.ImportFrom):
                    module = node.module if node.module else ''
                    for alias in node.names:
                        imports.append(('from', module, alias.name))
        except (SyntaxError, IOError) as e:
            print(f"Warning: Could not parse {filepath}: {e}")
        return imports
    
    def _get_module_name(self, filepath):
        """Convert filepath to module name relative to root."""
        import os
        rel_path = os.path.relpath(filepath, self.root_dir)
        module_name = rel_path.replace(os.sep, '.').replace('.py', '')
        if module_name.endswith('.__init__'):
            module_name = module_name[:-9]
        return module_name
    
    def analyze(self):
        """Build the dependency graph by analyzing all Python files."""
        python_files = self._get_python_files()
        
        for filepath in python_files:
            module_name = self._get_module_name(filepath)
            self.all_modules.add(module_name)
            imports = self._parse_imports(filepath)
            self.module_imports[module_name] = imports
            
            for imp in imports:
                if imp[0] == 'import':
                    self.dependency_graph[module_name].add(imp[1])
                elif imp[0] == 'from':
                    self.dependency_graph[module_name].add(imp[1])
        
        return self.dependency_graph
    
    def get_dependency_graph(self):
        """Return the dependency graph as a dictionary."""
        return {k: list(v) for k, v in self.dependency_graph.items()}
    
    def get_module_imports(self):
        """Return all imports per module."""
        return dict(self.module_imports)
    
    def get_all_modules(self):
        """Return set of all discovered modules."""
        return self.all_modules


class NashEquilibriumChecker:
    """
    Verifies that no single module change improves any metric.
    Uses only standard library.
    """
    
    def __init__(self, num_modules=5):
        self.num_modules = num_modules
        self.module_metrics = {
            'success_rate': [0.0] * num_modules,
            'dependency_count': [0] * num_modules,
            'fitness_score': [0.0] * num_modules,
            'response_time': [0.0] * num_modules
        }
        self.improvement_threshold = 0.05
        self._random_seed = 123456789
        
    def _random(self):
        """Simple linear congruential generator for reproducibility."""
        self._random_seed = (self._random_seed * 1103515245 + 12345) & 0x7fffffff
        return self._random_seed / 0x7fffffff
    
    def set_module_metrics(self, module_idx, success_rate, dependency_count, response_time=0.0):
        """Set metrics for a specific module."""
        self.module_metrics['success_rate'][module_idx] = success_rate
        self.module_metrics['dependency_count'][module_idx] = dependency_count
        self.module_metrics['response_time'][module_idx] = response_time
        self.module_metrics['fitness_score'][module_idx] = (
            success_rate * (1.0 / (1.0 + dependency_count)) * (1.0 / (1.0 + response_time))
        )
    
    def _simulate_single_module_change(self, module_idx, dependency_matrix):
        """Simulate a change to a single module and compute new metrics."""
        original_deps = dependency_matrix[module_idx][:]
        
        # Try a small change to one dependency
        dep_idx = int(self._random() * self.num_modules)
        original_value = dependency_matrix[module_idx][dep_idx]
        dependency_matrix[module_idx][dep_idx] = min(1.0, original_value + 0.1)
        
        # Compute new fitness score
        new_score = 0.0
        for j in range(self.num_modules):
            new_score += dependency_matrix[module_idx][j] * (
                self.module_metrics['fitness_score'][j] if j != module_idx else 1.0
            )
        new_score += self._random() * 0.1 - 0.05
        
        # Restore original
        dependency_matrix[module_idx] = original_deps
        
        return new_score
    
    def check_nash_equilibrium(self, dependency_matrix):
        """
        Check if the system is in Nash equilibrium.
        Returns True if no single module change improves any metric.
        """
        improvement_found = False
        improvement_details = []
        
        for module_idx in range(self.num_modules):
            original_score = self.module_metrics['fitness_score'][module_idx]
            new_score = self._simulate_single_module_change(module_idx, dependency_matrix)
            
            if new_score > original_score * (1 + self.improvement_threshold):
                improvement_found = True
                improvement_details.append({
                    'module': module_idx,
                    'original_score': original_score,
                    'new_score': new_score,
                    'improvement': new_score - original_score
                })
        
        return not improvement_found, improvement_details
    
    def get_metrics_summary(self):
        """Return a summary of all module metrics."""
        return {
            'success_rates': self.module_metrics['success_rate'][:],
            'dependency_counts': self.module_metrics['dependency_count'][:],
            'fitness_scores': self.module_metrics['fitness_score'][:],
            'response_times': self.module_metrics['response_time'][:]
        }


class MultiModuleForcer:
    """
    Generates coordinated changes across 2-3 modules simultaneously.
    Uses only standard library.
    """
    
    def __init__(self, num_modules=5):
        self.num_modules = num_modules
        self.dependency_matrix = [[self._random() for _ in range(num_modules)] for _ in range(num_modules)]
        self._random_seed = 123456789
        self.change_history = []
        
    def _random(self):
        """Simple linear congruential generator for reproducibility."""
        self._random_seed = (self._random_seed * 1103515245 + 12345) & 0x7fffffff
        return self._random_seed / 0x7fffffff
    
    def set_dependency_matrix(self, matrix):
        """Set the dependency matrix."""
        self.dependency_matrix = [row[:] for row in matrix]
    
    def _select_modules_for_change(self, equilibrium_pairs=None, fitness_scores=None):
        """Select 2-3 modules for coordinated change."""
        if equilibrium_pairs and len(equilibrium_pairs) > 0:
            modules_in_equilibrium = set()
            for pair in equilibrium_pairs:
                modules_in_equilibrium.add(pair[0])
                modules_in_equilibrium.add(pair[1])
            
            if len(modules_in_equilibrium) >= 2:
                selected = list(modules_in_equilibrium)
                if len(selected) > 3:
                    if fitness_scores:
                        selected.sort(key=lambda x: fitness_scores[x] if x < len(fitness_scores) else 0)
                    selected = selected[:3]
                return selected[:3]
        
        # Fallback: select random modules
        modules = list(range(self.num_modules))
        result = []
        indices = list(range(len(modules)))
        num_to_select = min(2 + int(self._random() * 2), self.num_modules)  # 2 or 3 modules
        for _ in range(num_to_select):
            idx = indices[int(self._random() * len(indices))]
            result.append(modules[idx])
            indices.remove(idx)
        return result
    
    def _generate_swap_change(self, module_idx):
        """Generate a swap change for a module."""
        indices = list(range(self.num_modules))
        j1 = indices[int(self._random() * len(indices))]
        indices.remove(j1)
        j2 = indices[int(self._random() * len(indices))]
        
        original = self.dependency_matrix[module_idx][:]
        new_deps = original[:]
        new_deps[j1], new_deps[j2] = new_deps[j2], new_deps[j1]
        
        return {
            'module': module_idx,
            'type': 'swap',
            'indices': (j1, j2),
            'original': original,
            'new': new_deps
        }
    
    def _generate_shift_change(self, module_idx):
        """Generate a shift change for a module."""
        shift_amount = self._random() * 0.4 - 0.2
        
        original = self.dependency_matrix[module_idx][:]
        new_deps = []
        for j in range(self.num_modules):
            new_val = max(0.0, min(1.0, original[j] + shift_amount))
            new_deps.append(new_val)
        
        return {
            'module': module_idx,
            'type': 'shift',
            'amount': shift_amount,
            'original': original,
            'new': new_deps
        }
    
    def _generate_reset_change(self, module_idx):
        """Generate a reset change for a module."""
        num_to_reset = int(self._random() * max(1, self.num_modules // 2)) + 1
        indices = list(range(self.num_modules))
        indices_to_reset = []
        for _ in range(num_to_reset):
            idx = indices[int(self._random() * len(indices))]
            indices_to_reset.append(idx)
            indices.remove(idx)
        
        original = self.dependency_matrix[module_idx][:]
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
    
    def _score_combination(self, modules, fitness_scores):
        """Score a multi-module combination based on fitness scores and diversity."""
        if not modules or not fitness_scores:
            return 0.0
        
        # Base score from average fitness
        avg_fitness = sum(fitness_scores[m] for m in modules if m < len(fitness_scores)) / len(modules)
        
        # Diversity bonus: prefer modules with different fitness levels
        fitness_values = [fitness_scores[m] for m in modules if m < len(fitness_scores)]
        if len(fitness_values) > 1:
            diversity = max(fitness_values) - min(fitness_values)
        else:
            diversity = 0.0
        
        # Size bonus: prefer larger combinations (up to 3)
        size_bonus = len(modules) / 3.0
        
        # Combined score
        score = avg_fitness * 0.5 + diversity * 0.3 + size_bonus * 0.2
        return score
    
    def force_multi_module_change(self, equilibrium_pairs=None, fitness_scores=None):
        """
        Generate a coordinated multi-module change plan.
        Returns a dictionary describing the changes to make.
        """
        modules_to_change = self._select_modules_for_change(equilibrium_pairs, fitness_scores)
        
        # Score this combination
        combination_score = self._score_combination(modules_to_change, fitness_scores)
        
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
        
        return mutation_plan
    
    def apply_change(self, mutation_plan):
        """Apply a mutation plan to the dependency matrix."""
        execution_record = {
            'type': 'coordinated_mutation_executed',
            'modules_changed': mutation_plan['modules_changed'],
            'mutations_applied': []
        }
        
        for mutation in mutation_plan['mutations']:
            module_idx = mutation['module']
            new_deps = mutation['new']
            
            self.dependency_matrix[module_idx] = new_deps[:]
            
            execution_record['mutations_applied'].append({
                'module': module_idx,
                'type': mutation['type'],
                'new_dependencies': new_deps
            })
        
        self.change_history.append(execution_record)
        return execution_record
    
    def get_change_history(self):
        """Return the history of applied changes."""
        return self.change_history
    
    def reset(self):
        """Reset all tracked state to initial values."""
        self.dependency_matrix = [[self._random() for _ in range(self.num_modules)] for _ in range(self.num_modules)]
        self.change_history = []
        self._random_seed = 123456789


class NashState:
    """
    Maintains a history of module interactions (success/failure per module pair),
    computes whether the system is in equilibrium using a convergence metric,
    and exposes a force_multi_module_change method that generates and applies coordinated mutations.
    """
    
    def __init__(self, num_modules=5):
        self.num_modules = num_modules
        self.interaction_history = {}  # (module_i, module_j) -> list of (success, timestamp)
        self.convergence_threshold = 0.01
        self.equilibrium_state = False
        self.equilibrium_iterations = 0
        self._random_seed = 123456789
        self.dependency_matrix = [[self._random() for _ in range(num_modules)] for _ in range(num_modules)]
        self.module_scores = [0.0 for _ in range(num_modules)]
        self.change_history = []
        self.sliding_window_size = 50
        self.performance_window = deque(maxlen=self.sliding_window_size)
        self.consecutive_no_improvement = 0
        self.nash_threshold = 5
        
    def _random(self):
        """Simple linear congruential generator for reproducibility."""
        self._random_seed = (self._random_seed * 1103515245 + 12345) & 0x7fffffff
        return self._random_seed / 0x7fffffff
    
    def record_interaction(self, module_i, module_j, success):
        """
        Record a module interaction result.
        
        Args:
            module_i: Index of first module
            module_j: Index of second module
            success: Boolean indicating whether the interaction was successful
        """
        key = (module_i, module_j)
        if key not in self.interaction_history:
            self.interaction_history[key] = []
        self.interaction_history[key].append((success, len(self.change_history)))
        
        # Update module scores based on interaction success
        if success:
            self.module_scores[module_i] = min(1.0, self.module_scores[module_i] + 0.05)
            self.module_scores[module_j] = min(1.0, self.module_scores[module_j] + 0.05)
        else:
            self.module_scores[module_i] = max(0.0, self.module_scores[module_i] - 0.05)
            self.module_scores[module_j] = max(0.0, self.module_scores[module_j] - 0.05)
    
    def get_interaction_success_rate(self, module_i, module_j):
        """
        Get the success rate for interactions between two modules.
        
        Args:
            module_i: Index of first module
            module_j: Index of second module
            
        Returns:
            float: Success rate (0.0 to 1.0), or 0.0 if no interactions recorded
        """
        key = (module_i, module_j)
        if key not in self.interaction_history or not self.interaction_history[key]:
            return 0.0
        
        successes = sum(1 for s, _ in self.interaction_history[key] if s)
        return successes / len(self.interaction_history[key])
    
    def compute_convergence_metric(self):
        """
        Compute a convergence metric based on the stability of module scores.
        Returns a value between 0 and 1, where 0 means no convergence and 1 means fully converged.
        """
        if len(self.performance_window) < 2:
            return 0.0
        
        # Get the last two window entries
        recent = list(self.performance_window)[-2:]
        
        # Compute the change in scores
        score_changes = []
        for i in range(self.num_modules):
            old_score = recent[0].get('fitness_scores', [0.0] * self.num_modules)[i]
            new_score = recent[1].get('fitness_scores', [0.0] * self.num_modules)[i]
            score_changes.append(abs(new_score - old_score))
        
        # Average change
        avg_change = sum(score_changes) / len(score_changes) if score_changes else 0.0
        
        # Convert to convergence metric (1 - normalized change)
        convergence = 1.0 - min(1.0, avg_change / self.convergence_threshold)
        return convergence
    
    def check_equilibrium(self):
        """
        Check if the system is in equilibrium based on the convergence metric.
        Returns True if the convergence metric exceeds the threshold.
        """
        convergence = self.compute_convergence_metric()
        
        # Update performance window with current state
        window_entry = {
            'timestamp': len(self.change_history),
            'fitness_scores': self.module_scores[:],
            'convergence': convergence
        }
        self.performance_window.append(window_entry)
        
        # Check if converged
        if convergence >= 0.95:  # 95% convergence threshold
            self.consecutive_no_improvement += 1
        else:
            self.consecutive_no_improvement = 0
        
        # Equilibrium detected when no improvement for N consecutive checks
        self.equilibrium_state = self.consecutive_no_improvement >= self.nash_threshold
        
        if self.equilibrium_state:
            self.equilibrium_iterations += 1
        
        return self.equilibrium_state, {
            'convergence': convergence,
            'consecutive_no_improvement': self.consecutive_no_improvement,
            'equilibrium_iterations': self.equilibrium_iterations
        }
    
    def _select_modules_for_change(self):
        """Select 2-3 modules for coordinated change based on interaction history."""
        # Find modules with lowest success rates
        module_success_rates = []
        for i in range(self.num_modules):
            total_interactions = 0
            successful_interactions = 0
            for j in range(self.num_modules):
                if i != j:
                    key = (i, j)
                    if key in self.interaction_history:
                        for s, _ in self.interaction_history[key]:
                            total_interactions += 1
                            if s:
                                successful_interactions += 1
            if total_interactions > 0:
                rate = successful_interactions / total_interactions
            else:
                rate = 0.5  # Default for modules with no interactions
            module_success_rates.append((i, rate))
        
        # Sort by success rate (ascending) and select bottom 2-3
        module_success_rates.sort(key=lambda x: x[1])
        num_to_select = min(2 + int(self._random() * 2), self.num_modules)
        selected = [m[0] for m in module_success_rates[:num_to_select]]
        
        return selected
    
    def _generate_swap_change(self, module_idx):
        """Generate a swap change for a module."""
        indices = list(range(self.num_modules))
        j1 = indices[int(self._random() * len(indices))]
        indices.remove(j1)
        j2 = indices[int(self._random() * len(indices))]
        
        original = self.dependency_matrix[module_idx][:]
        new_deps = original[:]
        new_deps[j1], new_deps[j2] = new_deps[j2], new_deps[j1]
        
        return {
            'module': module_idx,
            'type': 'swap',
            'indices': (j1, j2),
            'original': original,
            'new': new_deps
        }
    
    def _generate_shift_change(self, module_idx):
        """Generate a shift change for a module."""
        shift_amount = self._random() * 0.4 - 0.2
        
        original = self.dependency_matrix[module_idx][:]
        new_deps = []
        for j in range(self.num_modules):
            new_val = max(0.0, min(1.0, original[j] + shift_amount))
            new_deps.append(new_val)
        
        return {
            'module': module_idx,
            'type': 'shift',
            'amount': shift_amount,
            'original': original,
            'new': new_deps
        }
    
    def _generate_reset_change(self, module_idx):
        """Generate a reset change for a module."""
        num_to_reset = int(self._random() * max(1, self.num_modules // 2)) + 1
        indices = list(range(self.num_modules))
        indices_to_reset = []
        for _ in range(num_to_reset):
            idx = indices[int(self._random() * len(indices))]
            indices_to_reset.append(idx)
            indices.remove(idx)
        
        original = self.dependency_matrix[module_idx][:]
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
    
    def force_multi_module_change(self):
        """
        Generate and apply coordinated mutations to escape equilibrium.
        Returns a dictionary describing the changes made.
        """
        modules_to_change = self._select_modules_for_change()
        
        mutation_plan = {
            'type': 'coordinated_mutation',
            'modules_changed': modules_to_change,
            'mutations': [],
            'rationale': 'Coordinated multi-module change to escape local optimum'
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
            
            self.dependency_matrix[module_idx] = new_deps[:]
            
            execution_record['mutations_applied'].append({
                'module': module_idx,
                'type': mutation['type'],
                'new_dependencies': new_deps
            })
        
        self.change_history.append(execution_record)
        
        return mutation_plan, execution_record
    
    def get_state(self):
        """Return the current state of the NashState."""
        return {
            'num_modules': self.num_modules,
            'dependency_matrix': [row[:] for row in self.dependency_matrix],
            'module_scores': self.module_scores[:],
            'equilibrium_state': self.equilibrium_state,
            'equilibrium_iterations': self.equilibrium_iterations,
            'consecutive_no_improvement': self.consecutive_no_improvement,
            'convergence_threshold': self.convergence_threshold,
            'interaction_history': {
                str(k): v for k, v in self.interaction_history.items()
            },
            'change_history': self.change_history,
            'performance_window': list(self.performance_window)
        }
    
    def reset(self):
        """Reset all tracked state to initial values."""
        self.interaction_history = {}
        self.equilibrium_state = False
        self.equilibrium_iterations = 0
        self._random_seed = 123456789
        self.dependency_matrix = [[self._random() for _ in range(self.num_modules)] for _ in range(self.num_modules)]
        self.module_scores = [0.0 for _ in range(self.num_modules)]
        self.change_history = []
        self.performance_window = deque(maxlen=self.sliding_window_size)
        self.consecutive_no_improvement = 0


class NashDetectorAndForcer:
    """
    A self-contained module for detecting Nash equilibria in a system of interacting modules
    and forcing coordinated multi-module changes to escape suboptimal equilibria.
    
    Includes:
    1) Dependency graph analyzer that parses import statements from all core modules
    2) Nash equilibrium checker that verifies no single module change improves any metric
    3) Multi-module forcer that generates coordinated changes across 2-3 modules simultaneously
    4) Per-module performance tracking over a sliding window of 50 cycles
    5) Nash equilibrium detection when no single module change improves performance for N consecutive attempts
    6) Simple scoring system to identify the most promising multi-module combinations
    7) NashState class that maintains interaction history and computes convergence
    
    Uses only standard library (json, typing, collections).
    """
    
    def __init__(self, num_modules=5, root_dir='.', nash_threshold=5):
        self.num_modules = num_modules
        self.root_dir = root_dir
        self.nash_threshold = nash_threshold  # N consecutive attempts with no improvement
        self._random_seed = 123456789
        
        # Initialize components
        self.dependency_analyzer = DependencyGraphAnalyzer(root_dir)
        self.equilibrium_checker = NashEquilibriumChecker(num_modules)
        self.multi_module_forcer = MultiModuleForcer(num_modules)
        self.nash_state = NashState(num_modules)
        
        # State variables
        self.dependency_matrix = [[self._random() for _ in range(num_modules)] for _ in range(num_modules)]
        self.module_scores = [0.0 for _ in range(num_modules)]
        self.score_history = []
        self.equilibrium_pairs = []
        self.in_equilibrium = False
        self.equilibrium_iterations = 0
        self.consecutive_no_improvement = 0
        
        # Sliding window for performance tracking (50 cycles)
        self.sliding_window_size = 50
        self.performance_window = deque(maxlen=self.sliding_window_size)
        self.module_performance_history = [deque(maxlen=self.sliding_window_size) for _ in range(num_modules)]
        
        # Lightweight integration state
        self.lightweight_module_metrics = {}  # module_name -> performance_metric
        self.lightweight_consecutive_no_improvement = 0
        self.lightweight_equilibrium_detected = False
        self.lightweight_check_history = deque(maxlen=10)  # Track last 10 checks
        
        # Run inline tests
        self._run_tests()
    
    def _random(self):
        """Simple linear congruential generator for reproducibility."""
        self._random_seed = (self._random_seed * 1103515245 + 12345) & 0x7fffffff
        return self._random_seed / 0x7fffffff
    
    def analyze_dependencies(self):
        """Analyze dependencies from Python source files."""
        dependency_graph = self.dependency_analyzer.analyze()
        return dependency_graph
    
    def set_module_metrics(self, module_idx, success_rate, dependency_count, response_time=0.0):
        """Set metrics for a specific module."""
        self.equilibrium_checker.set_module_metrics(
            module_idx, success_rate, dependency_count, response_time
        )
        self.module_scores[module_idx] = success_rate * (1.0 / (1.0 + dependency_count))
        
        # Update performance history
        self.module_performance_history[module_idx].append(self.module_scores[module_idx])
    
    def _update_performance_window(self):
        """Update the sliding window with current performance metrics."""
        metrics = self.equilibrium_checker.get_metrics_summary()
        window_entry = {
            'timestamp': len(self.score_history),
            'fitness_scores': metrics['fitness_scores'][:],
            'success_rates': metrics['success_rates'][:],
            'dependency_counts': metrics['dependency_counts'][:],
            'response_times': metrics['response_times'][:]
        }
        self.performance_window.append(window_entry)
        self.score_history.append(window_entry)
    
    def _check_nash_equilibrium(self):
        """
        Check if the system is in Nash equilibrium.
        Returns True if no single module change improves performance for N consecutive attempts.
        """
        # Check if we have enough history
        if len(self.performance_window) < self.nash_threshold:
            return False, []
        
        # Check consecutive no-improvement
        improvement_found = False
        improvement_details = []
        
        for module_idx in range(self.num_modules):
            original_score = self.equilibrium_checker.module_metrics['fitness_score'][module_idx]
            new_score = self.equilibrium_checker._simulate_single_module_change(
                module_idx, self.dependency_matrix
            )
            
            if new_score > original_score * (1 + self.equilibrium_checker.improvement_threshold):
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
        
        # Nash equilibrium detected when no improvement for N consecutive attempts
        is_nash = self.consecutive_no_improvement >= self.nash_threshold
        
        if is_nash:
            self.in_equilibrium = True
            self.equilibrium_iterations += 1
            
            # Find equilibrium pairs
            self.equilibrium_pairs = []
            metrics = self.equilibrium_checker.get_metrics_summary()
            for i in range(self.num_modules):
                for j in range(i + 1, self.num_modules):
                    if abs(metrics['fitness_scores'][i] - metrics['fitness_scores'][j]) < 0.001:
                        self.equilibrium_pairs.append((i, j))
        else:
            self.in_equilibrium = False
            self.equilibrium_pairs = []
        
        return is_nash, improvement_details
    
    def check_equilibrium(self):
        """
        Check if the system is in Nash equilibrium.
        Returns True if no single module change improves any metric.
        """
        # Update performance window
        self._update_performance_window()
        
        # Check Nash equilibrium
        is_equilibrium, improvement_details = self._check_nash_equilibrium()
        
        return is_equilibrium, improvement_details
    
    def _score_multi_module_combination(self, modules):
        """
        Score a multi-module combination using a simple scoring system.
        Higher scores indicate more promising combinations.
        """
        if not modules:
            return 0.0
        
        metrics = self.equilibrium_checker.get_metrics_summary()
        fitness_scores = metrics['fitness_scores']
        
        # Base score: average fitness of selected modules
        avg_fitness = sum(fitness_scores[m] for m in modules if m < len(fitness_scores)) / len(modules)
        
        # Diversity score: standard deviation of fitness scores
        if len(modules) > 1:
            fitness_values = [fitness_scores[m] for m in modules if m < len(fitness_scores)]
            mean = sum(fitness_values) / len(fitness_values)
            variance = sum((f - mean) ** 2 for f in fitness_values) / len(fitness_values)
            diversity = variance ** 0.5
        else:
            diversity = 0.0
        
        # Size bonus: prefer combinations with more modules (up to 3)
        size_bonus = len(modules) / 3.0
        
        # Improvement potential: check if modules have room for improvement
        improvement_potential = 0.0
        for m in modules:
            if m < len(fitness_scores):
                # Modules with lower fitness have more room for improvement
                improvement_potential += (1.0 - fitness_scores[m])
        improvement_potential = improvement_potential / len(modules) if modules else 0.0
        
        # Combined score (weighted sum)
        score = (avg_fitness * 0.3 + 
                 diversity * 0.2 + 
                 size_bonus * 0.2 + 
                 improvement_potential * 0.3)
        
        return score
    
    def force_multi_module_change(self):
        """
        Generate and apply a coordinated multi-module change.
        Returns the mutation plan and execution record.
        """
        metrics = self.equilibrium_checker.get_metrics_summary()
        
        # Generate mutation plan
        mutation_plan = self.multi_module_forcer.force_multi_module_change(
            self.equilibrium_pairs,
            metrics['fitness_scores']
        )
        
        # Score the combination
        combination_score = self._score_multi_module_combination(
            mutation_plan['modules_changed']
        )
        mutation_plan['combination_score'] = combination_score
        
        # Apply the change
        execution_record = self.multi_module_forcer.apply_change(mutation_plan)
        
        # Update dependency matrix
        self.dependency_matrix = [row[:] for row in self.multi_module_forcer.dependency_matrix]
        
        return mutation_plan, execution_record
    
    def get_system_state(self):
        """Return the current system state."""
        return {
            'num_modules': self.num_modules,
            'dependency_matrix': [row[:] for row in self.dependency_matrix],
            'module_scores': self.module_scores[:],
            'in_equilibrium': self.in_equilibrium,
            'equilibrium_pairs': self.equilibrium_pairs,
            'equilibrium_iterations': self.equilibrium_iterations,
            'consecutive_no_improvement': self.consecutive_no_improvement,
            'nash_threshold': self.nash_threshold,
            'sliding_window_size': self.sliding_window_size,
            'performance_window': list(self.performance_window),
            'module_performance_history': [list(h) for h in self.module_performance_history],
            'metrics': self.equilibrium_checker.get_metrics_summary(),
            'dependency_graph': self.dependency_analyzer.get_dependency_graph(),
            'change_history': self.multi_module_forcer.get_change_history(),
            'lightweight_equilibrium_detected': self.lightweight_equilibrium_detected,
            'lightweight_consecutive_no_improvement': self.lightweight_consecutive_no_improvement,
            'lightweight_module_metrics': dict(self.lightweight_module_metrics),
            'nash_state': self.nash_state.get_state()
        }
    
    def reset(self):
        """Reset all tracked state to initial values."""
        self.dependency_matrix = [[self._random() for _ in range(self.num_modules)] for _ in range(self.num_modules)]
        self.module_scores = [0.0 for _ in range(self.num_modules)]
        self.score_history = []
        self.equilibrium_pairs = []
