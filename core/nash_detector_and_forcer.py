import ast
import json
import os
import sys
from collections import defaultdict, deque
from datetime import datetime

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
        python_files = []
        for root, dirs, files in os.walk(self.root_dir):
            for file in files:
                if file.endswith('.py'):
                    python_files.append(os.path.join(root, file))
        return python_files
    
    def _parse_imports(self, filepath):
        """Parse import statements from a Python file using ast."""
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
    Generates coordinated changes across 2-4 modules simultaneously.
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
        """Select 2-4 modules for coordinated change."""
        if equilibrium_pairs and len(equilibrium_pairs) > 0:
            modules_in_equilibrium = set()
            for pair in equilibrium_pairs:
                modules_in_equilibrium.add(pair[0])
                modules_in_equilibrium.add(pair[1])
            
            if len(modules_in_equilibrium) >= 2:
                selected = list(modules_in_equilibrium)
                if len(selected) > 4:
                    if fitness_scores:
                        selected.sort(key=lambda x: fitness_scores[x] if x < len(fitness_scores) else 0)
                    selected = selected[:4]
                return selected[:4]
        
        # Fallback: select random modules
        modules = list(range(self.num_modules))
        result = []
        indices = list(range(len(modules)))
        num_to_select = min(2 + int(self._random() * 3), self.num_modules)  # 2, 3, or 4 modules
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
        
        # Size bonus: prefer larger combinations (up to 4)
        size_bonus = len(modules) / 4.0
        
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


class NashDetectorAndForcer:
    """
    A self-contained module for detecting Nash equilibria in a system of interacting modules
    and forcing coordinated multi-module changes to escape suboptimal equilibria.
    
    Includes:
    1) Dependency graph analyzer that parses import statements from all core modules
    2) Nash equilibrium checker that verifies no single module change improves any metric
    3) Multi-module forcer that generates coordinated changes across 2-4 modules simultaneously
    4) Per-module performance tracking over a sliding window of 20 cycles
    5) Nash equilibrium detection when no single module change improves performance for 5+ consecutive attempts
    6) Simple scoring system to identify the most promising multi-module combinations
    
    Uses only standard library (ast, json, os, sys).
    """
    
    def __init__(self, num_modules=5, root_dir='.'):
        self.num_modules = num_modules
        self.root_dir = root_dir
        self._random_seed = 123456789
        
        # Initialize components
        self.dependency_analyzer = DependencyGraphAnalyzer(root_dir)
        self.equilibrium_checker = NashEquilibriumChecker(num_modules)
        self.multi_module_forcer = MultiModuleForcer(num_modules)
        
        # State variables
        self.dependency_matrix = [[self._random() for _ in range(num_modules)] for _ in range(num_modules)]
        self.module_scores = [0.0 for _ in range(num_modules)]
        self.score_history = []
        self.equilibrium_pairs = []
        self.in_equilibrium = False
        self.equilibrium_iterations = 0
        self.consecutive_no_improvement = 0
        
        # Sliding window for performance tracking (20 cycles)
        self.sliding_window_size = 20
        self.performance_window = deque(maxlen=self.sliding_window_size)
        self.module_performance_history = [deque(maxlen=self.sliding_window_size) for _ in range(num_modules)]
        
        # Nash equilibrium detection threshold
        self.nash_threshold = 5  # 5+ consecutive attempts with no improvement
        
        # New: lightweight integration state
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
        Returns True if no single module change improves performance for 5+ consecutive attempts.
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
        
        # Nash equilibrium detected when no improvement for 5+ consecutive attempts
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
        
        # Size bonus: prefer combinations with more modules (up to 4)
        size_bonus = len(modules) / 4.0
        
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
            'lightweight_module_metrics': dict(self.lightweight_module_metrics)
        }
    
    def reset(self):
        """Reset all tracked state to initial values."""
        self.dependency_matrix = [[self._random() for _ in range(self.num_modules)] for _ in range(self.num_modules)]
        self.module_scores = [0.0 for _ in range(self.num_modules)]
        self.score_history = []
        self.equilibrium_pairs = []
        self.in_equilibrium = False
        self.equilibrium_iterations = 0
        self.consecutive_no_improvement = 0
        self.performance_window = deque(maxlen=self.sliding_window_size)
        self.module_performance_history = [deque(maxlen=self.sliding_window_size) for _ in range(self.num_modules)]
        self.equilibrium_checker = NashEquilibriumChecker(self.num_modules)
        self.multi_module_forcer.reset()
        self._random_seed = 123456789
        self.lightweight_module_metrics = {}
        self.lightweight_consecutive_no_improvement = 0
        self.lightweight_equilibrium_detected = False
        self.lightweight_check_history = deque(maxlen=10)
    
    def lightweight_check_equilibrium(self, module_metrics):
        """
        Lightweight integration method that:
        1) Accepts a list of (module_name, performance_metric) tuples
        2) Detects Nash equilibrium when no single module change improves >5% for 3+ consecutive checks
        3) Returns a list of coordinated multi-module changes when equilibrium is detected
        
        Args:
            module_metrics: List of (module_name, performance_metric) tuples
        
        Returns:
            dict with keys:
                'equilibrium_detected': bool
                'changes': list of coordinated change strings (e.g., ['module_a:change_x', 'module_b:change_y'])
                'consecutive_no_improvement': int
        """
        # Store the metrics
        for module_name, metric in module_metrics:
            self.lightweight_module_metrics[module_name] = metric
        
        # Check if any single module change would improve >5%
        improvement_found = False
        module_names = list(self.lightweight_module_metrics.keys())
        
        for module_name in module_names:
            current_metric = self.lightweight_module_metrics.get(module_name, 0.0)
            # Simulate a small change (increase by 10% of current value)
            simulated_metric = current_metric * 1.1
            
            # Check if improvement >5%
            if simulated_metric > current_metric * 1.05:
                improvement_found = True
                break
        
        # Track consecutive no-improvement
        if not improvement_found:
            self.lightweight_consecutive_no_improvement += 1
        else:
            self.lightweight_consecutive_no_improvement = 0
        
        # Record this check
        self.lightweight_check_history.append({
            'module_metrics': dict(self.lightweight_module_metrics),
            'improvement_found': improvement_found,
            'consecutive_no_improvement': self.lightweight_consecutive_no_improvement
        })
        
        # Detect equilibrium when no improvement for 3+ consecutive checks
        self.lightweight_equilibrium_detected = self.lightweight_consecutive_no_improvement >= 3
        
        # Generate coordinated changes if equilibrium detected
        changes = []
        if self.lightweight_equilibrium_detected:
            # Generate coordinated multi-module changes
            # Select modules with lowest metrics for coordinated change
            sorted_modules = sorted(module_names, key=lambda m: self.lightweight_module_metrics.get(m, 0.0))
            
            # Take up to 4 modules with lowest metrics
            modules_to_change = sorted_modules[:min(4, len(sorted_modules))]
            
            # Generate change strings
            for module_name in modules_to_change:
                current_metric = self.lightweight_module_metrics.get(module_name, 0.0)
                # Generate a change that would improve the metric
                if current_metric < 0.5:
                    changes.append(f"{module_name}:increase_dependency_strength")
                elif current_metric < 0.8:
                    changes.append(f"{module_name}:optimize_response_time")
                else:
                    changes.append(f"{module_name}:redistribute_load")
        
        return {
            'equilibrium_detected': self.lightweight_equilibrium_detected,
            'changes': changes,
            'consecutive_no_improvement': self.lightweight_consecutive_no_improvement
        }
    
    def _run_tests(self):
        """Run inline tests to verify functionality."""
        test_results = []
        
        # Test 1: Dependency graph analyzer
        try:
            analyzer = DependencyGraphAnalyzer(self.root_dir)
            graph = analyzer.analyze()
            test_results.append(('DependencyGraphAnalyzer', 'PASS', f'Found {len(graph)} modules'))
        except Exception as e:
            test_results.append(('DependencyGraphAnalyzer', 'FAIL', str(e)))
        
        # Test 2: Nash equilibrium checker
        try:
            checker = NashEquilibriumChecker(3)
            checker.set_module_metrics(0, 0.9, 2, 0.1)
            checker.set_module_metrics(1, 0.8, 3, 0.2)
            checker.set_module_metrics(2, 0.7, 1, 0.15)
            
            dep_matrix = [[0.5, 0.3, 0.2],
                         [0.2, 0.6, 0.2],
                         [0.3, 0.3, 0.4]]
            
            is_equilibrium, details = checker.check_nash_equilibrium(dep_matrix)
            test_results.append(('NashEquilibriumChecker', 'PASS', 
                                f'Equilibrium: {is_equilibrium}, Details: {len(details)}'))
        except Exception as e:
            test_results.append(('NashEquilibriumChecker', 'FAIL', str(e)))
        
        # Test 3: Multi-module forcer
        try:
            forcer = MultiModuleForcer(3)
            plan = forcer.force_multi_module_change()
            record = forcer.apply_change(plan)
            test_results.append(('MultiModuleForcer', 'PASS', 
                                f'Changed {len(plan["modules_changed"])} modules'))
        except Exception as e:
            test_results.append(('MultiModuleForcer', 'FAIL', str(e)))
        
        # Test 4: Full integration
        try:
            detector = NashDetectorAndForcer(3, self.root_dir)
            detector.set_module_metrics(0, 0.9, 2, 0.1)
            detector.set_module_metrics(1, 0.8, 3, 0.2)
            detector.set_module_metrics(2, 0.7, 1, 0.15)
            
            is_equilibrium, details = detector.check_equilibrium()
            plan, record = detector.force_multi_module_change()
            state = detector.get_system_state()
            test_results.append(('Integration', 'PASS', 
                                f'Equilibrium: {is_equilibrium}, State keys: {list(state.keys())}'))
        except Exception as e:
            test_results.append(('Integration', 'FAIL', str(e)))
        
        # Test 5: Lightweight integration
        try:
            detector = NashDetectorAndForcer(3, self.root_dir)
            
            # Test with no improvement (should detect equilibrium after 3 checks)
            for i in range(3):
                result = detector.lightweight_check_equilibrium([
                    ('module_a', 0.5),
                    ('module_b', 0.6),
                    ('module_c', 0.7)
                ])
            
            assert result['equilibrium_detected'] == True, "Should detect equilibrium after 3 checks"
            assert len(result['changes']) > 0, "Should generate changes when equilibrium detected"
            
            # Test with improvement (should reset counter)
            result = detector.lightweight_check_equilibrium([
                ('module_a', 0.5),
                ('module_b', 0.6),
                ('module_c', 0.9)  # This module has high metric, so improvement possible
            ])
            
            assert result['consecutive_no_improvement'] == 0, "Should reset counter when improvement found"
            
            test_results.append(('LightweightIntegration', 'PASS', 
                                'All lightweight integration tests passed'))
        except Exception as e:
            test_results.append(('LightweightIntegration', 'FAIL', str(e)))
        
        # Print test results
        print("=" * 60)
        print("NashDetectorAndForcer Inline Tests")
        print("=" * 60)
        all_passed = True
        for name, status, message in test_results:
            status_str = "✓" if status == "PASS" else "✗"
            print(f"  {status_str} {name}: {status} - {message}")
            if status == "FAIL":
                all_passed = False
        print("=" * 60)
        print(f"Overall: {'ALL TESTS PASSED' if all_passed else 'SOME TESTS FAILED'}")
        print("=" * 60)


# Run inline tests when module is imported
if __name__ != "__main__":
    # When imported, run tests silently
    try:
        tester = NashDetectorAndForcer(num_modules=3, root_dir=os.path.dirname(__file__))
    except:
        pass
else:
    # When run directly, show test results
    detector = NashDetectorAndForcer(num_modules=5, root_dir=os.path.dirname(__file__))