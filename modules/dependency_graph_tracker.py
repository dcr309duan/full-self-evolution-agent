"""Module for tracking downstream dependencies in the dependency graph.

This module provides functionality to traverse the dependency graph and find
all modules that depend on a given module, which is essential for determining
the impact of mutations in the predictor system.
"""

from typing import Set, Dict, List, Optional
from collections import defaultdict


class DependencyGraphTracker:
    """Tracks and queries the dependency graph for downstream dependencies."""

    def __init__(self, dependency_graph: Optional[Dict[str, Set[str]]] = None):
        """Initialize the tracker with an optional dependency graph.

        Args:
            dependency_graph: A dictionary mapping module paths to sets of
                modules they depend on. If None, an empty graph is created.
        """
        self.dependency_graph = dependency_graph or defaultdict(set)
        self._reverse_graph: Optional[Dict[str, Set[str]]] = None

    def set_dependency_graph(self, graph: Dict[str, Set[str]]) -> None:
        """Set or update the dependency graph and invalidate the reverse graph.

        Args:
            graph: A dictionary mapping module paths to sets of modules
                they depend on.
        """
        self.dependency_graph = graph
        self._reverse_graph = None

    def _build_reverse_graph(self) -> Dict[str, Set[str]]:
        """Build a reverse dependency graph (module -> modules that depend on it).

        Returns:
            A dictionary mapping each module to the set of modules that
            depend on it.
        """
        if self._reverse_graph is not None:
            return self._reverse_graph

        reverse_graph: Dict[str, Set[str]] = defaultdict(set)
        for module, dependencies in self.dependency_graph.items():
            for dep in dependencies:
                reverse_graph[dep].add(module)

        self._reverse_graph = reverse_graph
        return reverse_graph

    def get_downstream_modules(
        self, module_path: str, depth: int = 1
    ) -> Set[str]:
        """Get all modules that depend on the given module, up to specified depth.

        Traverses the reverse dependency graph to find all modules that
        directly or indirectly depend on the given module.

        Args:
            module_path: The path of the module to find downstream dependencies for.
            depth: Maximum depth of dependency traversal. Default is 1 (direct
                dependents only). Use -1 for unlimited depth.

        Returns:
            A set of module paths that depend on the given module.

        Raises:
            ValueError: If depth is 0 or less than -1.
        """
        if depth == 0:
            raise ValueError("Depth must be 1 or greater, or -1 for unlimited depth.")
        if depth < -1:
            raise ValueError("Depth cannot be less than -1.")

        reverse_graph = self._build_reverse_graph()
        downstream_modules: Set[str] = set()
        visited: Set[str] = set()

        def _traverse(current_module: str, current_depth: int) -> None:
            """Recursively traverse the reverse graph to find downstream modules.

            Args:
                current_module: The module to find dependents for.
                current_depth: Current depth in the traversal.
            """
            if current_module in visited:
                return
            visited.add(current_module)

            if depth != -1 and current_depth > depth:
                return

            dependents = reverse_graph.get(current_module, set())
            for dependent in dependents:
                if dependent not in downstream_modules:
                    downstream_modules.add(dependent)
                    _traverse(dependent, current_depth + 1)

        _traverse(module_path, 1)
        return downstream_modules

    def get_upstream_modules(
        self, module_path: str, depth: int = 1
    ) -> Set[str]:
        """Get all modules that the given module depends on, up to specified depth.

        Traverses the dependency graph to find all modules that the given
        module directly or indirectly depends on.

        Args:
            module_path: The path of the module to find upstream dependencies for.
            depth: Maximum depth of dependency traversal. Default is 1 (direct
                dependencies only). Use -1 for unlimited depth.

        Returns:
            A set of module paths that the given module depends on.

        Raises:
            ValueError: If depth is 0 or less than -1.
        """
        if depth == 0:
            raise ValueError("Depth must be 1 or greater, or -1 for unlimited depth.")
        if depth < -1:
            raise ValueError("Depth cannot be less than -1.")

        upstream_modules: Set[str] = set()
        visited: Set[str] = set()

        def _traverse(current_module: str, current_depth: int) -> None:
            """Recursively traverse the graph to find upstream modules.

            Args:
                current_module: The module to find dependencies for.
                current_depth: Current depth in the traversal.
            """
            if current_module in visited:
                return
            visited.add(current_module)

            if depth != -1 and current_depth > depth:
                return

            dependencies = self.dependency_graph.get(current_module, set())
            for dep in dependencies:
                if dep not in upstream_modules:
                    upstream_modules.add(dep)
                    _traverse(dep, current_depth + 1)

        _traverse(module_path, 1)
        return upstream_modules

    def add_dependency(self, module: str, dependency: str) -> None:
        """Add a dependency relationship to the graph.

        Args:
            module: The module that has the dependency.
            dependency: The module that is depended upon.
        """
        self.dependency_graph[module].add(dependency)
        self._reverse_graph = None  # Invalidate reverse graph

    def remove_dependency(self, module: str, dependency: str) -> None:
        """Remove a dependency relationship from the graph.

        Args:
            module: The module that has the dependency.
            dependency: The module that is depended upon.
        """
        if module in self.dependency_graph:
            self.dependency_graph[module].discard(dependency)
            if not self.dependency_graph[module]:
                del self.dependency_graph[module]
            self._reverse_graph = None  # Invalidate reverse graph

    def clear(self) -> None:
        """Clear the entire dependency graph."""
        self.dependency_graph.clear()
        self._reverse_graph = None


def get_downstream_modules(
    module_path: str, depth: int = 1, graph: Optional[Dict[str, Set[str]]] = None
) -> Set[str]:
    """Convenience function to get downstream modules without creating a tracker.

    Args:
        module_path: The path of the module to find downstream dependencies for.
        depth: Maximum depth of dependency traversal. Default is 1.
        graph: Optional dependency graph. If None, an empty graph is used.

    Returns:
        A set of module paths that depend on the given module.
    """
    tracker = DependencyGraphTracker(graph)
    return tracker.get_downstream_modules(module_path, depth)