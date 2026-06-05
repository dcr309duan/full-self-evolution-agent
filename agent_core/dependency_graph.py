"""
Dependency Graph Module

This module provides a directed acyclic graph (DAG) data structure for modeling
prerequisites between goals and capabilities. It supports adding edges (prerequisite
relationships), topological sorting, cycle detection, and serialization/deserialization.
"""

from __future__ import annotations

import json
from collections import defaultdict, deque
from typing import Any, Dict, List, Optional, Set, Tuple, Union


class DependencyGraphError(Exception):
    """Base exception for dependency graph errors."""

    pass


class CycleDetectedError(DependencyGraphError):
    """Raised when a cycle is detected in the dependency graph."""

    def __init__(self, cycle_nodes: List[str]) -> None:
        self.cycle_nodes = cycle_nodes
        super().__init__(f"Circular dependency detected: {' -> '.join(cycle_nodes)}")


class NodeNotFoundError(DependencyGraphError):
    """Raised when a node is not found in the graph."""

    def __init__(self, node_id: str) -> None:
        self.node_id = node_id
        super().__init__(f"Node '{node_id}' not found in the dependency graph.")


class EdgeAlreadyExistsError(DependencyGraphError):
    """Raised when an edge already exists."""

    def __init__(self, from_node: str, to_node: str) -> None:
        super().__init__(f"Edge from '{from_node}' to '{to_node}' already exists.")


class NodeType:
    """Constants for node types."""

    GOAL = "goal"
    CAPABILITY = "capability"


class DependencyNode:
    """Represents a node in the dependency graph (either a goal or a capability)."""

    def __init__(self, node_id: str, node_type: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        """
        Initialize a dependency node.

        Args:
            node_id: Unique identifier for the node.
            node_type: Type of node ('goal' or 'capability').
            metadata: Optional dictionary of additional metadata.

        Raises:
            ValueError: If node_type is invalid.
        """
        if node_type not in (NodeType.GOAL, NodeType.CAPABILITY):
            raise ValueError(f"Invalid node type: {node_type}. Must be 'goal' or 'capability'.")

        self.id: str = node_id
        self.type: str = node_type
        self.metadata: Dict[str, Any] = metadata or {}

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the node to a dictionary."""
        return {
            "id": self.id,
            "type": self.type,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> DependencyNode:
        """Deserialize a node from a dictionary."""
        return cls(
            node_id=data["id"],
            node_type=data["type"],
            metadata=data.get("metadata", {}),
        )

    def __repr__(self) -> str:
        return f"DependencyNode(id='{self.id}', type='{self.type}')"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, DependencyNode):
            return NotImplemented
        return self.id == other.id and self.type == other.type

    def __hash__(self) -> int:
        return hash((self.id, self.type))


class DependencyGraph:
    """
    Directed Acyclic Graph (DAG) for modeling dependencies between goals and capabilities.

    An edge from node A to node B means "A depends on B" or "B is a prerequisite for A".
    """

    def __init__(self) -> None:
        """Initialize an empty dependency graph."""
        self._nodes: Dict[str, DependencyNode] = {}
        # adjacency list: node_id -> set of node_ids that depend on it (incoming edges)
        self._incoming: Dict[str, Set[str]] = defaultdict(set)
        # adjacency list: node_id -> set of node_ids it depends on (outgoing edges)
        self._outgoing: Dict[str, Set[str]] = defaultdict(set)

    # --------------------------------------------------------------------------
    # Node management
    # --------------------------------------------------------------------------

    def add_node(self, node: DependencyNode) -> None:
        """
        Add a node to the graph.

        Args:
            node: The node to add.

        Raises:
            ValueError: If a node with the same ID already exists.
        """
        if node.id in self._nodes:
            raise ValueError(f"Node with ID '{node.id}' already exists.")
        self._nodes[node.id] = node

    def remove_node(self, node_id: str) -> None:
        """
        Remove a node and all its edges from the graph.

        Args:
            node_id: ID of the node to remove.

        Raises:
            NodeNotFoundError: If the node does not exist.
        """
        if node_id not in self._nodes:
            raise NodeNotFoundError(node_id)

        # Remove all edges involving this node
        for successor in list(self._outgoing[node_id]):
            self._incoming[successor].discard(node_id)
        for predecessor in list(self._incoming[node_id]):
            self._outgoing[predecessor].discard(node_id)

        # Clean up adjacency lists
        del self._outgoing[node_id]
        del self._incoming[node_id]
        del self._nodes[node_id]

    def get_node(self, node_id: str) -> DependencyNode:
        """
        Get a node by its ID.

        Args:
            node_id: ID of the node.

        Returns:
            The node.

        Raises:
            NodeNotFoundError: If the node does not exist.
        """
        if node_id not in self._nodes:
            raise NodeNotFoundError(node_id)
        return self._nodes[node_id]

    def has_node(self, node_id: str) -> bool:
        """Check if a node exists in the graph."""
        return node_id in self._nodes

    def get_all_nodes(self) -> List[DependencyNode]:
        """Get all nodes in the graph."""
        return list(self._nodes.values())

    def get_nodes_by_type(self, node_type: str) -> List[DependencyNode]:
        """
        Get all nodes of a specific type.

        Args:
            node_type: 'goal' or 'capability'.

        Returns:
            List of nodes matching the type.
        """
        return [node for node in self._nodes.values() if node.type == node_type]

    # --------------------------------------------------------------------------
    # Edge management
    # --------------------------------------------------------------------------

    def add_edge(self, from_node: str, to_node: str) -> None:
        """
        Add a directed edge from 'from_node' to 'to_node'.
        This means 'from_node' depends on 'to_node' (to_node is a prerequisite).

        Args:
            from_node: ID of the dependent node.
            to_node: ID of the prerequisite node.

        Raises:
            NodeNotFoundError: If either node does not exist.
            EdgeAlreadyExistsError: If the edge already exists.
            CycleDetectedError: If adding this edge would create a cycle.
        """
        if from_node not in self._nodes:
            raise NodeNotFoundError(from_node)
        if to_node not in self._nodes:
            raise NodeNotFoundError(to_node)

        if to_node in self._outgoing[from_node]:
            raise EdgeAlreadyExistsError(from_node, to_node)

        # Temporarily add the edge to check for cycles
        self._outgoing[from_node].add(to_node)
        self._incoming[to_node].add(from_node)

        try:
            if self._detect_cycle():
                # Rollback
                self._outgoing[from_node].discard(to_node)
                self._incoming[to_node].discard(from_node)
                raise CycleDetectedError(self._find_cycle_path())
        except CycleDetectedError:
            # Rollback and re-raise
            self._outgoing[from_node].discard(to_node)
            self._incoming[to_node].discard(from_node)
            raise

    def remove_edge(self, from_node: str, to_node: str) -> None:
        """
        Remove a directed edge from the graph.

        Args:
            from_node: ID of the dependent node.
            to_node: ID of the prerequisite node.

        Raises:
            NodeNotFoundError: If either node does not exist.
            ValueError: If the edge does not exist.
        """
        if from_node not in self._nodes:
            raise NodeNotFoundError(from_node)
        if to_node not in self._nodes:
            raise NodeNotFoundError(to_node)

        if to_node not in self._outgoing[from_node]:
            raise ValueError(f"Edge from '{from_node}' to '{to_node}' does not exist.")

        self._outgoing[from_node].discard(to_node)
        self._incoming[to_node].discard(from_node)

    def has_edge(self, from_node: str, to_node: str) -> bool:
        """Check if an edge exists from 'from_node' to 'to_node'."""
        return to_node in self._outgoing.get(from_node, set())

    def get_prerequisites(self, node_id: str) -> List[str]:
        """
        Get the IDs of nodes that the given node directly depends on (prerequisites).

        Args:
            node_id: ID of the node.

        Returns:
            List of prerequisite node IDs.

        Raises:
            NodeNotFoundError: If the node does not exist.
        """
        if node_id not in self._nodes:
            raise NodeNotFoundError(node_id)
        return list(self._outgoing[node_id])

    def get_dependents(self, node_id: str) -> List[str]:
        """
        Get the IDs of nodes that directly depend on the given node.

        Args:
            node_id: ID of the node.

        Returns:
            List of dependent node IDs.

        Raises:
            NodeNotFoundError: If the node does not exist.
        """
        if node_id not in self._nodes:
            raise NodeNotFoundError(node_id)
        return list(self._incoming[node_id])

    # --------------------------------------------------------------------------
    # Cycle detection
    # --------------------------------------------------------------------------

    def _detect_cycle(self) -> bool:
        """
        Detect if the graph contains a cycle using DFS.

        Returns:
            True if a cycle exists, False otherwise.
        """
        WHITE, GRAY, BLACK = 0, 1, 2
        color: Dict[str, int] = {node_id: WHITE for node_id in self._nodes}

        def dfs(node_id: str) -> bool:
            color[node_id] = GRAY
            for neighbor in self._outgoing[node_id]:
                if color[neighbor] == GRAY:
                    return True
                if color[neighbor] == WHITE and dfs(neighbor):
                    return True
            color[node_id] = BLACK
            return False

        for node_id in self._nodes:
            if color[node_id] == WHITE:
                if dfs(node_id):
                    return True
        return False

    def _find_cycle_path(self) -> List[str]:
        """
        Find one cycle path in the graph.

        Returns:
            List of node IDs forming a cycle.

        Raises:
            ValueError: If no cycle exists.
        """
        WHITE, GRAY, BLACK = 0, 1, 2
        color: Dict[str, int] = {node_id: WHITE for node_id in self._nodes}
        parent: Dict[str, Optional[str]] = {}

        def dfs(node_id: str, path: List[str]) -> Optional[List[str]]:
            color[node_id] = GRAY
            path.append(node_id)
            for neighbor in self._outgoing[node_id]:
                if color[neighbor] == GRAY:
                    # Found cycle, extract it
                    cycle_start = path.index(neighbor)
                    return path[cycle_start:] + [neighbor]
                if color[neighbor] == WHITE:
                    parent[neighbor] = node_id
                    result = dfs(neighbor, path)
                    if result:
                        return result
            path.pop()
            color[node_id] = BLACK
            return None

        for node_id in self._nodes:
            if color[node_id] == WHITE:
                result = dfs(node_id, [])
                if result:
                    return result

        raise ValueError("No cycle found in the graph.")

    def is_acyclic(self) -> bool:
        """Check if the graph is acyclic."""
        return not self._detect_cycle()

    # --------------------------------------------------------------------------
    # Topological sort
    # --------------------------------------------------------------------------

    def topological_sort(self) -> List[str]:
        """
        Perform a topological sort of the graph using Kahn's algorithm.

        Returns:
            List of node IDs in topological order (prerequisites first).

        Raises:
            CycleDetectedError: If the graph contains a cycle.
        """
        if self._detect_cycle():
            raise CycleDetectedError(self._find_cycle_path())

        # Compute in-degree (number of prerequisites) for each node
        in_degree: Dict[str, int] = {}
        for node_id in self._nodes:
            in_degree[node_id] = len(self._outgoing[node_id])

        # Initialize queue with nodes that have no prerequisites
        queue = deque([node_id for node_id, degree in in_degree.items() if degree == 0])

        sorted_nodes: List[str] = []
        while queue:
            node_id = queue.popleft()
            sorted_nodes.append(node_id)

            # Decrease in-degree of all dependents
            for dependent in self._incoming[node_id]:
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    queue.append(dependent)

        # If not all nodes are sorted, there's a cycle (shouldn't happen due to check above)
        if len(sorted_nodes) != len(self._nodes):
            raise CycleDetectedError(self._find_cycle_path())

        return sorted_nodes

    def get_dependency_chain(self, node_id: str) -> List[str]:
        """
        Get the full dependency chain for a node (all prerequisites recursively).

        Args:
            node_id: ID of the node.

        Returns:
            List of node IDs representing the dependency chain (including the node itself).

        Raises:
            NodeNotFoundError: If the node does not exist.
        """
        if node_id not in self._nodes:
            raise NodeNotFoundError(node_id)

        visited: Set[str] = set()
        chain: List[str] = []

        def dfs(current: str) -> None:
            if current in visited:
                return
            visited.add(current)
            for prereq in self._outgoing[current]:
                dfs(prereq)
            chain.append(current)

        dfs(node_id)
        return chain

    # --------------------------------------------------------------------------
    # Serialization / Deserialization
    # --------------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the entire graph to a dictionary."""
        nodes = [node.to_dict() for node in self._nodes.values()]
        edges = []
        for from_node in self._outgoing:
            for to_node in self._outgoing[from_node]:
                edges.append({"from": from_node, "to": to_node})
        return {
            "nodes": nodes,
            "edges": edges,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> DependencyGraph:
        """
        Deserialize a graph from a dictionary.

        Args:
            data: Dictionary with 'nodes' and 'edges' keys.

        Returns:
            A new DependencyGraph instance.

        Raises:
            ValueError: If the data is malformed or contains cycles.
        """
        graph = cls()

        # Add nodes
        for node_data in data.get("nodes", []):
            node = DependencyNode.from_dict(node_data)
            graph._nodes[node.id] = node

        # Add edges
        for edge_data in data.get("edges", []):
            from_node = edge_data["from"]
            to_node = edge_data["to"]
            if from_node not in graph._nodes:
                raise ValueError(f"Edge references unknown node '{from_node}'.")
            if to_node not in graph._nodes:
                raise ValueError(f"Edge references unknown node '{to_node}'.")
            graph._outgoing[from_node].add(to_node)
            graph._incoming[to_node].add(from_node)

        # Validate no cycles
        if graph._detect_cycle():
            raise ValueError("The deserialized graph contains a cycle.")

        return graph

    def to_json(self, indent: int = 2) -> str:
        """Serialize the graph to a JSON string."""
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_json(cls, json_str: str) -> DependencyGraph:
        """
        Deserialize a graph from a JSON string.

        Args:
            json_str: JSON string representing the graph.

        Returns:
            A new DependencyGraph instance.
        """
        data = json.loads(json_str)
        return cls.from_dict(data)

    def save_to_file(self, filepath: str) -> None:
        """Save the graph to a JSON file."""
        with open(filepath, "w") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load_from_file(cls, filepath: str) -> DependencyGraph:
        """Load a graph from a JSON file."""
        with open(filepath, "r") as f:
            data = json.load(f)
        return cls.from_dict(data)

    # --------------------------------------------------------------------------
    # Utility methods
    # --------------------------------------------------------------------------

    def __len__(self) -> int:
        """Return the number of nodes in the graph."""
        return len(self._nodes)

    def __contains__(self, node_id: str) -> bool:
        """Check if a node exists in the graph."""
        return node_id in self._nodes

    def __repr__(self) -> str:
        return f"DependencyGraph(nodes={len(self._nodes)}, edges={sum(len(v) for v in self._outgoing.values())})"