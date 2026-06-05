from typing import List, Dict, Any, Optional, Tuple
from collections import defaultdict, deque
import networkx as nx

class GoalDecomposer:
    """
    Decomposes abstract goal descriptions into ordered sub-goals with dependencies and readiness scores.
    Uses a self-model knowledge graph to determine dependency relationships and topological ordering.
    """

    def __init__(self, knowledge_graph: Optional[Dict[str, Any]] = None):
        """
        Initialize the GoalDecomposer with an optional knowledge graph.
        
        Args:
            knowledge_graph: A dictionary representing the self-model knowledge graph.
                            Expected format: {node_id: {dependencies: [...], tests: [...], interfaces: [...], ...}}
        """
        self.knowledge_graph = knowledge_graph or {}
        self._dependency_graph = nx.DiGraph()
        self._build_dependency_graph()

    def _build_dependency_graph(self) -> None:
        """Build a directed graph from the knowledge graph dependencies."""
        self._dependency_graph.clear()
        for node_id, node_data in self.knowledge_graph.items():
            self._dependency_graph.add_node(node_id)
            for dep in node_data.get('dependencies', []):
                self._dependency_graph.add_edge(dep, node_id)

    def set_knowledge_graph(self, knowledge_graph: Dict[str, Any]) -> None:
        """Update the knowledge graph and rebuild the dependency graph."""
        self.knowledge_graph = knowledge_graph
        self._build_dependency_graph()

    def _check_module_readiness(self, node_id: str) -> float:
        """
        Calculate readiness score for a module based on:
        - Has tests (0.4 weight)
        - Has interfaces (0.3 weight)
        - Has documentation (0.2 weight)
        - Has implementation (0.1 weight)
        
        Args:
            node_id: The module identifier
            
        Returns:
            Readiness score between 0.0 and 1.0
        """
        node_data = self.knowledge_graph.get(node_id, {})
        score = 0.0
        
        # Check for tests
        if node_data.get('tests'):
            score += 0.4
        elif node_data.get('has_tests', False):
            score += 0.4
            
        # Check for interfaces
        if node_data.get('interfaces'):
            score += 0.3
        elif node_data.get('has_interfaces', False):
            score += 0.3
            
        # Check for documentation
        if node_data.get('documentation'):
            score += 0.2
        elif node_data.get('has_documentation', False):
            score += 0.2
            
        # Check for implementation
        if node_data.get('implementation'):
            score += 0.1
        elif node_data.get('has_implementation', False):
            score += 0.1
            
        return min(score, 1.0)

    def decompose_goal(self, goal_description: str) -> List[Dict[str, Any]]:
        """
        Decompose an abstract goal description into ordered sub-goals.
        
        Args:
            goal_description: Abstract description of the goal to decompose
            
        Returns:
            List of dictionaries, each containing:
                - 'id': sub-goal identifier
                - 'description': sub-goal description
                - 'dependencies': list of dependency identifiers
                - 'readiness_score': float between 0.0 and 1.0
                - 'level': topological level (0 for no dependencies)
        """
        # Parse goal description to identify relevant modules
        relevant_nodes = self._identify_relevant_nodes(goal_description)
        
        if not relevant_nodes:
            return []
        
        # Build subgraph for relevant nodes
        subgraph = self._dependency_graph.subgraph(relevant_nodes)
        
        # Perform topological sort
        try:
            topological_order = list(nx.topological_sort(subgraph))
        except nx.NetworkXUnfeasible:
            # Handle cycles - use a heuristic ordering
            topological_order = self._heuristic_ordering(subgraph)
        
        # Calculate levels and readiness scores
        levels = self._calculate_levels(subgraph)
        
        # Build result
        result = []
        for node_id in topological_order:
            node_data = self.knowledge_graph.get(node_id, {})
            result.append({
                'id': node_id,
                'description': node_data.get('description', f"Sub-goal: {node_id}"),
                'dependencies': list(subgraph.predecessors(node_id)),
                'readiness_score': self._check_module_readiness(node_id),
                'level': levels.get(node_id, 0)
            })
        
        return result

    def _identify_relevant_nodes(self, goal_description: str) -> List[str]:
        """
        Identify relevant nodes from the knowledge graph based on the goal description.
        
        Args:
            goal_description: Abstract goal description
            
        Returns:
            List of relevant node identifiers
        """
        # Simple keyword-based matching
        keywords = goal_description.lower().split()
        relevant_nodes = []
        
        for node_id, node_data in self.knowledge_graph.items():
            node_keywords = node_data.get('keywords', [])
            node_description = node_data.get('description', '').lower()
            
            # Check if any keyword matches
            if any(keyword in node_id.lower() for keyword in keywords):
                relevant_nodes.append(node_id)
            elif any(keyword in node_description for keyword in keywords):
                relevant_nodes.append(node_id)
            elif any(keyword in node_keywords for keyword in keywords):
                relevant_nodes.append(node_id)
        
        # If no direct matches, include all nodes (fallback)
        if not relevant_nodes:
            relevant_nodes = list(self.knowledge_graph.keys())
        
        return relevant_nodes

    def _calculate_levels(self, graph: nx.DiGraph) -> Dict[str, int]:
        """
        Calculate topological levels for nodes in the graph.
        
        Args:
            graph: Directed graph
            
        Returns:
            Dictionary mapping node_id to level (0 for no dependencies)
        """
        levels = {}
        
        # Use BFS to calculate levels
        for node in graph.nodes():
            if graph.in_degree(node) == 0:
                levels[node] = 0
        
        # Propagate levels
        changed = True
        while changed:
            changed = False
            for node in graph.nodes():
                if node not in levels:
                    predecessors = list(graph.predecessors(node))
                    if all(pred in levels for pred in predecessors):
                        if predecessors:
                            levels[node] = max(levels[pred] for pred in predecessors) + 1
                        else:
                            levels[node] = 0
                        changed = True
        
        # Assign remaining nodes
        for node in graph.nodes():
            if node not in levels:
                levels[node] = 0
        
        return levels

    def _heuristic_ordering(self, graph: nx.DiGraph) -> List[str]:
        """
        Heuristic ordering for graphs with cycles.
        Uses a greedy approach based on dependency count.
        
        Args:
            graph: Directed graph (possibly with cycles)
            
        Returns:
            List of node identifiers in heuristic order
        """
        # Count dependencies for each node
        dep_counts = {node: graph.in_degree(node) for node in graph.nodes()}
        
        # Sort by dependency count (fewer dependencies first)
        ordered = sorted(dep_counts.keys(), key=lambda x: (dep_counts[x], x))
        
        return ordered

    def get_dependency_chain(self, node_id: str) -> List[str]:
        """
        Get the full dependency chain for a specific node.
        
        Args:
            node_id: The node to get dependencies for
            
        Returns:
            List of node identifiers in dependency order (dependencies first)
        """
        if node_id not in self._dependency_graph:
            return []
        
        # Get all ancestors (dependencies)
        ancestors = nx.ancestors(self._dependency_graph, node_id)
        
        # Sort by topological order
        subgraph = self._dependency_graph.subgraph(ancestors | {node_id})
        try:
            order = list(nx.topological_sort(subgraph))
        except nx.NetworkXUnfeasible:
            order = self._heuristic_ordering(subgraph)
        
        # Remove the target node from the end (it will be added separately)
        if node_id in order:
            order.remove(node_id)
        
        return order + [node_id]

    def get_readiness_report(self) -> Dict[str, float]:
        """
        Get readiness scores for all modules in the knowledge graph.
        
        Returns:
            Dictionary mapping module IDs to their readiness scores
        """
        return {
            node_id: self._check_module_readiness(node_id)
            for node_id in self.knowledge_graph
        }