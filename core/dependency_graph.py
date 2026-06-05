"""Dependency graph builder for Python codebases.

Parses Python files to build a directed graph of imports, supports subgraph
extraction, caching, and circular dependency detection.
"""

import ast
import os
from collections import defaultdict
from functools import lru_cache
from typing import Dict, List, Set, Tuple, Optional


class DependencyGraph:
    """A directed graph representing module dependencies in a Python codebase."""

    def __init__(self, root_dir: str):
        self.root_dir = os.path.abspath(root_dir)
        self._graph: Dict[str, Set[str]] = defaultdict(set)
        self._reverse_graph: Dict[str, Set[str]] = defaultdict(set)
        self._modules: Set[str] = set()
        self._circular_dependencies: Set[Tuple[str, str]] = set()

    def build(self) -> None:
        """Parse all Python files in the root directory and build the dependency graph."""
        for dirpath, _, filenames in os.walk(self.root_dir):
            for filename in filenames:
                if filename.endswith('.py'):
                    filepath = os.path.join(dirpath, filename)
                    module_name = self._path_to_module(filepath)
                    self._modules.add(module_name)
                    self._parse_file(filepath, module_name)

        self._detect_circular_dependencies()

    def _path_to_module(self, filepath: str) -> str:
        """Convert a file path to a Python module name relative to root_dir."""
        rel_path = os.path.relpath(filepath, self.root_dir)
        # Remove .py extension
        module = rel_path.replace('.py', '')
        # Convert path separators to dots
        module = module.replace(os.sep, '.')
        # Handle __init__ files
        if module.endswith('.__init__'):
            module = module[:-9]  # Remove '.__init__'
        return module

    def _parse_file(self, filepath: str, module_name: str) -> None:
        """Parse a single Python file and extract import dependencies."""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                tree = ast.parse(f.read(), filename=filepath)
        except (SyntaxError, UnicodeDecodeError):
            return  # Skip files that can't be parsed

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    self._add_dependency(module_name, alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    # Handle relative imports
                    if node.level:
                        base = module_name.rsplit('.', node.level - 1)[0] if node.level > 1 else module_name
                        if node.level > 1:
                            base = '.'.join(module_name.split('.')[:-node.level + 1])
                        else:
                            base = '.'.join(module_name.split('.')[:-1])
                        full_module = f"{base}.{node.module}" if base else node.module
                    else:
                        full_module = node.module
                    self._add_dependency(module_name, full_module)

    def _add_dependency(self, source: str, target: str) -> None:
        """Add a directed edge from source to target in the graph."""
        if source != target:  # Skip self-imports
            self._graph[source].add(target)
            self._reverse_graph[target].add(source)

    def _detect_circular_dependencies(self) -> None:
        """Detect circular dependencies in the graph using DFS."""
        visited: Set[str] = set()
        rec_stack: Set[str] = set()

        def dfs(node: str, path: List[str]) -> None:
            visited.add(node)
            rec_stack.add(node)
            path.append(node)

            for neighbor in self._graph.get(node, set()):
                if neighbor not in visited:
                    dfs(neighbor, path)
                elif neighbor in rec_stack:
                    # Found a cycle - add all pairs in the cycle
                    cycle_start = path.index(neighbor)
                    cycle_nodes = path[cycle_start:] + [neighbor]
                    for i in range(len(cycle_nodes) - 1):
                        self._circular_dependencies.add(
                            (cycle_nodes[i], cycle_nodes[i + 1])
                        )

            path.pop()
            rec_stack.discard(node)

        for module in self._modules:
            if module not in visited:
                dfs(module, [])

    def get_dependencies(self, module: str) -> Set[str]:
        """Get direct dependencies of a module."""
        return self._graph.get(module, set())

    def get_dependents(self, module: str) -> Set[str]:
        """Get modules that directly depend on the given module."""
        return self._reverse_graph.get(module, set())

    def get_subgraph(self, module: str, depth: int = -1) -> Dict[str, Set[str]]:
        """Extract a subgraph containing the given module and its dependencies.

        Args:
            module: The root module for the subgraph.
            depth: Maximum depth of dependencies to include (-1 for unlimited).

        Returns:
            A dictionary mapping module names to their dependencies within the subgraph.
        """
        if module not in self._modules:
            return {}

        subgraph: Dict[str, Set[str]] = {}
        visited: Set[str] = set()

        def dfs(current: str, current_depth: int) -> None:
            if current in visited or (depth != -1 and current_depth > depth):
                return
            visited.add(current)
            deps = self._graph.get(current, set())
            subgraph[current] = deps & visited  # Only include already visited deps
            for dep in deps:
                if dep in self._modules:
                    dfs(dep, current_depth + 1)

        dfs(module, 0)
        return subgraph

    def has_circular_dependency(self, module_a: str, module_b: str) -> bool:
        """Check if there's a circular dependency between two modules."""
        return (module_a, module_b) in self._circular_dependencies or \
               (module_b, module_a) in self._circular_dependencies

    def get_circular_dependencies(self) -> Set[Tuple[str, str]]:
        """Get all detected circular dependency pairs."""
        return self._circular_dependencies.copy()

    @property
    def modules(self) -> Set[str]:
        """Get all modules in the graph."""
        return self._modules.copy()

    @property
    def graph(self) -> Dict[str, Set[str]]:
        """Get the full dependency graph."""
        return {k: v.copy() for k, v in self._graph.items()}


class CachedDependencyGraph(DependencyGraph):
    """A dependency graph with caching support for performance."""

    def __init__(self, root_dir: str):
        super().__init__(root_dir)
        self._build_cache: Optional[bool] = None

    @lru_cache(maxsize=128)
    def get_dependencies(self, module: str) -> Set[str]:
        return super().get_dependencies(module)

    @lru_cache(maxsize=128)
    def get_dependents(self, module: str) -> Set[str]:
        return super().get_dependents(module)

    @lru_cache(maxsize=64)
    def get_subgraph(self, module: str, depth: int = -1) -> Dict[str, Set[str]]:
        return super().get_subgraph(module, depth)

    def build(self) -> None:
        super().build()
        self._build_cache = True

    def invalidate_cache(self) -> None:
        """Clear all cached results."""
        self.get_dependencies.cache_clear()
        self.get_dependents.cache_clear()
        self.get_subgraph.cache_clear()
        self._build_cache = None


def build_dependency_graph(root_dir: str, use_cache: bool = True) -> DependencyGraph:
    """Convenience function to build a dependency graph for a codebase.

    Args:
        root_dir: Root directory of the Python codebase.
        use_cache: Whether to use caching for improved performance.

    Returns:
        A populated DependencyGraph or CachedDependencyGraph instance.
    """
    graph_class = CachedDependencyGraph if use_cache else DependencyGraph
    graph = graph_class(root_dir)
    graph.build()
    return graph