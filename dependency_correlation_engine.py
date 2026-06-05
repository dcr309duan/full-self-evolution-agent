"""
dependency_correlation_engine.py

Build a dependency correlation engine that:
(1) parses all existing module files to extract import statements and function call references,
(2) builds a directed dependency graph,
(3) detects circular dependencies and integration conflicts,
(4) scores each dependency edge by 'conflict risk' based on recent failure history.
"""

import ast
import os
import sys
from collections import defaultdict, deque
from typing import Dict, List, Set, Tuple, Optional, Any

class DependencyCorrelationEngine:
    """
    Engine to parse modules, build dependency graph, detect conflicts, and score edges.
    """

    def __init__(self, project_root: str = "."):
        self.project_root = os.path.abspath(project_root)
        self.module_files: Dict[str, str] = {}  # module_name -> file_path
        self.import_graph: Dict[str, Set[str]] = defaultdict(set)  # module -> set of imported modules
        self.function_call_graph: Dict[str, Set[str]] = defaultdict(set)  # module -> set of called functions (module.func)
        self.failure_history: Dict[str, List[float]] = defaultdict(list)  # module -> list of failure timestamps or scores
        self.dependency_graph: Dict[str, Dict[str, Any]] = defaultdict(dict)  # module -> {dependency: edge_data}

    def discover_modules(self) -> None:
        """Walk through project root and collect all Python files."""
        for root, dirs, files in os.walk(self.project_root):
            # Skip hidden directories and common non-source dirs
            dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ('__pycache__', 'venv', 'env')]
            for file in files:
                if file.endswith('.py'):
                    full_path = os.path.join(root, file)
                    # Compute module name relative to project root
                    rel_path = os.path.relpath(full_path, self.project_root)
                    module_name = rel_path.replace(os.sep, '.')[:-3]  # remove .py
                    if module_name.endswith('.__init__'):
                        module_name = module_name[:-9]  # remove .__init__
                    self.module_files[module_name] = full_path

    def parse_module(self, module_name: str, file_path: str) -> None:
        """Parse a single Python file to extract imports and function calls."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                tree = ast.parse(f.read(), filename=file_path)
        except (SyntaxError, UnicodeDecodeError) as e:
            print(f"Warning: Could not parse {file_path}: {e}", file=sys.stderr)
            return

        # Extract imports
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imported_module = alias.name.split('.')[0]  # top-level module
                    if imported_module not in ('builtins', 'sys', 'os', 'ast', 'collections', 'typing', 'defaultdict', 'deque'):
                        self.import_graph[module_name].add(imported_module)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imported_module = node.module.split('.')[0]
                    if imported_module not in ('builtins', 'sys', 'os', 'ast', 'collections', 'typing', 'defaultdict', 'deque'):
                        self.import_graph[module_name].add(imported_module)

        # Extract function calls (module.function pattern)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
                    called_module = func.value.id
                    called_function = f"{called_module}.{func.attr}"
                    if called_module in self.module_files:
                        self.function_call_graph[module_name].add(called_function)

    def build_graph(self) -> None:
        """Parse all discovered modules and build the dependency graph."""
        self.discover_modules()
        for module_name, file_path in self.module_files.items():
            self.parse_module(module_name, file_path)

        # Build dependency_graph with initial data
        for module, deps in self.import_graph.items():
            for dep in deps:
                self.dependency_graph[module][dep] = {
                    'type': 'import',
                    'conflict_risk': 0.0,
                    'circular': False,
                    'interface_conflict': False
                }
        for module, calls in self.function_call_graph.items():
            for call in calls:
                parts = call.split('.')
                if len(parts) >= 2:
                    dep = parts[0]
                    if dep in self.module_files:
                        if dep not in self.dependency_graph[module]:
                            self.dependency_graph[module][dep] = {
                                'type': 'function_call',
                                'conflict_risk': 0.0,
                                'circular': False,
                                'interface_conflict': False
                            }

    def detect_circular_dependencies(self) -> List[List[str]]:
        """Detect circular dependencies using DFS. Returns list of cycles (each cycle is list of module names)."""
        visited = set()
        rec_stack = set()
        cycles = []

        def dfs(module: str, path: List[str]) -> None:
            visited.add(module)
            rec_stack.add(module)
            path.append(module)

            for dep in self.dependency_graph.get(module, {}):
                if dep not in visited:
                    dfs(dep, path)
                elif dep in rec_stack:
                    # Found a cycle
                    cycle_start = path.index(dep)
                    cycle = path[cycle_start:] + [dep]
                    cycles.append(cycle)
                    # Mark edges as circular
                    for i in range(len(cycle)-1):
                        src = cycle[i]
                        dst = cycle[i+1]
                        if dst in self.dependency_graph.get(src, {}):
                            self.dependency_graph[src][dst]['circular'] = True

            path.pop()
            rec_stack.discard(module)

        for module in list(self.dependency_graph.keys()):
            if module not in visited:
                dfs(module, [])

        # Also check modules that only appear as dependencies
        all_modules = set(self.module_files.keys())
        for module in all_modules:
            if module not in visited:
                dfs(module, [])

        return cycles

    def detect_interface_conflicts(self) -> List[Tuple[str, str, str]]:
        """
        Detect integration conflicts: module A imports B, but B's latest mutation broke A's expected interface.
        This is a heuristic: we check if B has changed its public API (functions/classes) and A uses something that no longer exists.
        Returns list of (A, B, details) tuples.
        """
        conflicts = []
        # Build a map of module -> set of exported names (functions, classes, etc.)
        module_exports: Dict[str, Set[str]] = defaultdict(set)
        for module_name, file_path in self.module_files.items():
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    tree = ast.parse(f.read(), filename=file_path)
                for node in ast.iter_child_nodes(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                        module_exports[module_name].add(node.name)
                    elif isinstance(node, ast.Assign):
                        for target in node.targets:
                            if isinstance(target, ast.Name):
                                module_exports[module_name].add(target.id)
            except Exception:
                pass

        # For each dependency edge, check if the dependent module uses something that is no longer exported
        for module, deps in self.dependency_graph.items():
            for dep, edge_data in deps.items():
                if edge_data['type'] == 'function_call':
                    # Extract function name from the call
                    # We need to re-parse module to find specific calls to dep
                    try:
                        with open(self.module_files[module], 'r', encoding='utf-8') as f:
                            tree = ast.parse(f.read(), filename=self.module_files[module])
                        for node in ast.walk(tree):
                            if isinstance(node, ast.Call):
                                func = node.func
                                if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
                                    if func.value.id == dep:
                                        called_name = func.attr
                                        if called_name not in module_exports.get(dep, set()):
                                            conflicts.append((module, dep, f"Function '{called_name}' not found in {dep}"))
                                            edge_data['interface_conflict'] = True
                    except Exception:
                        pass
                elif edge_data['type'] == 'import':
                    # Check if imported names exist
                    try:
                        with open(self.module_files[module], 'r', encoding='utf-8') as f:
                            tree = ast.parse(f.read(), filename=self.module_files[module])
                        for node in ast.walk(tree):
                            if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith(dep):
                                for alias in node.names:
                                    if alias.name not in module_exports.get(dep, set()):
                                        conflicts.append((module, dep, f"Name '{alias.name}' not found in {dep}"))
                                        edge_data['interface_conflict'] = True
                    except Exception:
                        pass
        return conflicts

    def score_conflict_risk(self, failure_weight: float = 1.0, recency_factor: float = 0.5) -> None:
        """
        Score each dependency edge by conflict risk based on recent failure history.
        failure_history: dict of module -> list of failure timestamps (or scores, higher = more recent).
        We compute a risk score for each edge: risk = sum over failures in dependent module of (weight * recency_factor^age)
        """
        # Normalize failure history to a per-module failure score (higher = more recent failures)
        module_failure_score: Dict[str, float] = defaultdict(float)
        for module, failures in self.failure_history.items():
            if failures:
                # Simple scoring: count failures, weighted by recency (assuming timestamps sorted ascending)
                # If failures are timestamps, compute age relative to latest
                if isinstance(failures[0], (int, float)):
                    latest = max(failures)
                    for f in failures:
                        age = latest - f
                        module_failure_score[module] += failure_weight * (recency_factor ** age)
                else:
                    # Assume they are just counts or scores
                    module_failure_score[module] = sum(failures) * failure_weight

        # For each edge, risk = failure_score of the dependent module (the one that depends)
        for module, deps in self.dependency_graph.items():
            for dep, edge_data in deps.items():
                base_risk = module_failure_score.get(module, 0.0)
                # Additional risk if circular or interface conflict
                if edge_data.get('circular'):
                    base_risk += 0.5
                if edge_data.get('interface_conflict'):
                    base_risk += 1.0
                edge_data['conflict_risk'] = min(base_risk, 10.0)  # cap at 10

    def add_failure_event(self, module_name: str, timestamp: float = None) -> None:
        """Record a failure event for a module (used for risk scoring)."""
        if timestamp is None:
            import time
            timestamp = time.time()
        self.failure_history[module_name].append(timestamp)

    def get_high_risk_edges(self, threshold: float = 1.0) -> List[Tuple[str, str, Dict]]:
        """Return dependency edges with conflict risk above threshold."""
        high_risk = []
        for module, deps in self.dependency_graph.items():
            for dep, edge_data in deps.items():
                if edge_data['conflict_risk'] >= threshold:
                    high_risk.append((module, dep, edge_data))
        return high_risk

    def report(self) -> Dict[str, Any]:
        """Generate a comprehensive report of the dependency analysis."""
        cycles = self.detect_circular_dependencies()
        conflicts = self.detect_interface_conflicts()
        self.score_conflict_risk()

        return {
            'modules': list(self.module_files.keys()),
            'dependency_graph': {k: dict(v) for k, v in self.dependency_graph.items()},
            'circular_dependencies': cycles,
            'interface_conflicts': conflicts,
            'high_risk_edges': self.get_high_risk_edges(),
            'failure_history': dict(self.failure_history)
        }


# Example usage (if run as script)
if __name__ == "__main__":
    engine = DependencyCorrelationEngine(".")
    engine.build_graph()
    report = engine.report()
    print("Modules found:", len(report['modules']))
    print("Circular dependencies:", report['circular_dependencies'])
    print("Interface conflicts:", report['interface_conflicts'])
    print("High risk edges:", report['high_risk_edges'])