from typing import Any, Dict, List, Set, Tuple
from collections import defaultdict, deque
import random

class DependencyGraphManager:
    """
    Manages a directed dependency graph and provides methods to refactor it
    based on redesign signals from failure analysis.
    """

    def __init__(self, graph: Dict[str, Set[str]] = None):
        """
        Initialize with an optional dependency graph.
        Graph is represented as a dictionary mapping nodes to sets of dependencies.
        """
        self.graph = graph if graph else {}

    def add_node(self, node: str, dependencies: Set[str] = None):
        """Add a node with optional dependencies."""
        if node not in self.graph:
            self.graph[node] = set()
        if dependencies:
            self.graph[node].update(dependencies)

    def add_dependency(self, node: str, dependency: str):
        """Add a single dependency to a node."""
        if node not in self.graph:
            self.graph[node] = set()
        self.graph[node].add(dependency)

    def remove_dependency(self, node: str, dependency: str):
        """Remove a single dependency from a node."""
        if node in self.graph and dependency in self.graph[node]:
            self.graph[node].remove(dependency)

    def get_dependencies(self, node: str) -> Set[str]:
        """Get dependencies of a node."""
        return self.graph.get(node, set())

    def get_dependents(self, node: str) -> Set[str]:
        """Get all nodes that depend on the given node."""
        dependents = set()
        for n, deps in self.graph.items():
            if node in deps:
                dependents.add(n)
        return dependents

    def has_cycle(self) -> bool:
        """Check if the graph contains any cycles."""
        visited = set()
        rec_stack = set()

        def dfs(node):
            visited.add(node)
            rec_stack.add(node)
            for neighbor in self.graph.get(node, set()):
                if neighbor not in visited:
                    if dfs(neighbor):
                        return True
                elif neighbor in rec_stack:
                    return True
            rec_stack.remove(node)
            return False

        for node in self.graph:
            if node not in visited:
                if dfs(node):
                    return True
        return False

    def find_cycles(self) -> List[List[str]]:
        """Find all cycles in the graph."""
        cycles = []
        visited = set()
        path = []

        def dfs(node):
            visited.add(node)
            path.append(node)
            for neighbor in self.graph.get(node, set()):
                if neighbor not in visited:
                    dfs(neighbor)
                elif neighbor in path:
                    # Found a cycle
                    cycle_start = path.index(neighbor)
                    cycle = path[cycle_start:] + [neighbor]
                    cycles.append(cycle)
            path.pop()

        for node in self.graph:
            if node not in visited:
                dfs(node)
        return cycles

    def break_cycle(self, cycle: List[str]) -> str:
        """
        Break a single cycle by removing one dependency.
        Returns the removed dependency as a tuple (from_node, to_node).
        """
        if len(cycle) < 2:
            return None
        
        # Remove the last edge that completes the cycle
        from_node = cycle[-2]
        to_node = cycle[-1]
        
        if to_node in self.graph.get(from_node, set()):
            self.graph[from_node].remove(to_node)
            return (from_node, to_node)
        return None

    def add_redundancy(self, node: str, redundancy_factor: float = 0.3):
        """
        Add redundant dependencies to a node to improve fault tolerance.
        redundancy_factor determines how many extra dependencies to add.
        """
        if node not in self.graph:
            return
        
        current_deps = self.graph[node]
        all_other_nodes = [n for n in self.graph if n != node and n not in current_deps]
        
        if not all_other_nodes:
            return
        
        num_redundant = max(1, int(len(current_deps) * redundancy_factor))
        num_redundant = min(num_redundant, len(all_other_nodes))
        
        redundant_nodes = random.sample(all_other_nodes, num_redundant)
        self.graph[node].update(redundant_nodes)

    def simplify_complex_dependencies(self, node: str, max_deps: int = 5):
        """
        Simplify overly complex dependency chains for a node.
        Removes dependencies beyond max_deps, keeping the most critical ones.
        """
        if node not in self.graph:
            return
        
        deps = self.graph[node]
        if len(deps) <= max_deps:
            return
        
        # Keep only the first max_deps dependencies (or implement a more sophisticated selection)
        deps_list = list(deps)
        self.graph[node] = set(deps_list[:max_deps])

    def refactor_dependencies(self, signal: Dict[str, Any]) -> Dict[str, Any]:
        """
        Refactor the dependency graph based on a redesign signal from failure analysis.
        
        signal: A dictionary containing:
            - 'type': str - one of 'cycle', 'redundancy', 'complexity', 'mixed'
            - 'nodes': List[str] - nodes to refactor
            - 'parameters': Dict - additional parameters (e.g., redundancy_factor, max_deps)
        
        Returns a dictionary with the results of the refactoring.
        """
        result = {
            'actions_taken': [],
            'modified_nodes': set(),
            'errors': []
        }
        
        signal_type = signal.get('type', 'cycle')
        nodes = signal.get('nodes', [])
        parameters = signal.get('parameters', {})
        
        if signal_type == 'cycle':
            # Break cycles involving the specified nodes
            cycles = self.find_cycles()
            for cycle in cycles:
                # Check if cycle involves any of the specified nodes
                if any(node in cycle for node in nodes):
                    removed_edge = self.break_cycle(cycle)
                    if removed_edge:
                        result['actions_taken'].append(f"Broken cycle by removing {removed_edge}")
                        result['modified_nodes'].update(removed_edge)
        
        elif signal_type == 'redundancy':
            # Add redundancy to specified nodes
            redundancy_factor = parameters.get('redundancy_factor', 0.3)
            for node in nodes:
                self.add_redundancy(node, redundancy_factor)
                result['actions_taken'].append(f"Added redundancy to {node}")
                result['modified_nodes'].add(node)
        
        elif signal_type == 'complexity':
            # Simplify complex dependencies for specified nodes
            max_deps = parameters.get('max_deps', 5)
            for node in nodes:
                self.simplify_complex_dependencies(node, max_deps)
                result['actions_taken'].append(f"Simplified dependencies for {node}")
                result['modified_nodes'].add(node)
        
        elif signal_type == 'mixed':
            # Handle mixed signals: break cycles first, then add redundancy or simplify
            cycles = self.find_cycles()
            for cycle in cycles:
                if any(node in cycle for node in nodes):
                    removed_edge = self.break_cycle(cycle)
                    if removed_edge:
                        result['actions_taken'].append(f"Broken cycle by removing {removed_edge}")
                        result['modified_nodes'].update(removed_edge)
            
            redundancy_factor = parameters.get('redundancy_factor', 0.3)
            max_deps = parameters.get('max_deps', 5)
            
            for node in nodes:
                if parameters.get('add_redundancy', False):
                    self.add_redundancy(node, redundancy_factor)
                    result['actions_taken'].append(f"Added redundancy to {node}")
                    result['modified_nodes'].add(node)
                if parameters.get('simplify', False):
                    self.simplify_complex_dependencies(node, max_deps)
                    result['actions_taken'].append(f"Simplified dependencies for {node}")
                    result['modified_nodes'].add(node)
        
        else:
            result['errors'].append(f"Unknown signal type: {signal_type}")
        
        return result

    def get_graph(self) -> Dict[str, Set[str]]:
        """Return the current dependency graph."""
        return self.graph

    def __repr__(self):
        return f"DependencyGraphManager({self.graph})"