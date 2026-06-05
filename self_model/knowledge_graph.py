from __future__ import annotations
import json
from typing import Any, Dict, List, Optional, Set, Tuple, Union


class KnowledgeGraph:
    """
    A simple in-memory knowledge graph representing system components,
    modules, functions, schemas (nodes) and their relationships
    (edges) such as dependencies, interfaces, and contracts.
    """

    def __init__(self) -> None:
        # Node storage: node_id -> node_data (dict)
        self._nodes: Dict[str, Dict[str, Any]] = {}
        # Adjacency list: node_id -> list of (target_id, edge_data)
        self._edges: Dict[str, List[Tuple[str, Dict[str, Any]]]] = {}

    # ------------------------------------------------------------------
    # Node operations
    # ------------------------------------------------------------------

    def add_node(
        self,
        node_id: str,
        node_type: str = "component",
        **attributes: Any,
    ) -> None:
        """
        Add a node to the graph.

        Args:
            node_id: Unique identifier for the node.
            node_type: Type of node (e.g., 'component', 'module', 'function', 'schema').
            **attributes: Additional key-value attributes to store with the node.
        """
        if node_id in self._nodes:
            raise ValueError(f"Node '{node_id}' already exists.")
        self._nodes[node_id] = {"type": node_type, **attributes}
        # Ensure adjacency list entry exists
        if node_id not in self._edges:
            self._edges[node_id] = []

    def remove_node(self, node_id: str) -> None:
        """Remove a node and all its incident edges."""
        if node_id not in self._nodes:
            raise KeyError(f"Node '{node_id}' not found.")
        # Remove all edges pointing to this node
        for src in list(self._edges.keys()):
            self._edges[src] = [
                (tgt, data) for tgt, data in self._edges[src] if tgt != node_id
            ]
        # Remove outgoing edges and node data
        self._edges.pop(node_id, None)
        self._nodes.pop(node_id)

    def get_node(self, node_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve node data by ID, or None if not found."""
        return self._nodes.get(node_id)

    def get_all_nodes(self) -> Dict[str, Dict[str, Any]]:
        """Return a copy of all nodes."""
        return dict(self._nodes)

    # ------------------------------------------------------------------
    # Edge operations
    # ------------------------------------------------------------------

    def add_edge(
        self,
        source: str,
        target: str,
        edge_type: str = "dependency",
        **attributes: Any,
    ) -> None:
        """
        Add a directed edge from source to target.

        Args:
            source: Source node ID.
            target: Target node ID.
            edge_type: Type of relationship (e.g., 'dependency', 'interface', 'contract').
            **attributes: Additional attributes for the edge.
        """
        if source not in self._nodes:
            raise KeyError(f"Source node '{source}' not found.")
        if target not in self._nodes:
            raise KeyError(f"Target node '{target}' not found.")
        edge_data = {"type": edge_type, **attributes}
        self._edges.setdefault(source, []).append((target, edge_data))

    def remove_edge(self, source: str, target: str) -> None:
        """Remove all edges from source to target."""
        if source not in self._edges:
            raise KeyError(f"No edges from '{source}'.")
        original_count = len(self._edges[source])
        self._edges[source] = [
            (tgt, data) for tgt, data in self._edges[source] if tgt != target
        ]
        if len(self._edges[source]) == original_count:
            raise KeyError(f"No edge from '{source}' to '{target}' found.")

    def get_edges(self, node_id: Optional[str] = None) -> List[Tuple[str, str, Dict[str, Any]]]:
        """
        Return all edges, optionally filtered by source node.

        Returns list of (source, target, edge_data) tuples.
        """
        result: List[Tuple[str, str, Dict[str, Any]]] = []
        for src, targets in self._edges.items():
            if node_id is not None and src != node_id:
                continue
            for tgt, data in targets:
                result.append((src, tgt, data))
        return result

    # ------------------------------------------------------------------
    # Query methods
    # ------------------------------------------------------------------

    def query(
        self,
        node_type: Optional[str] = None,
        edge_type: Optional[str] = None,
        **filters: Any,
    ) -> List[Dict[str, Any]]:
        """
        Query nodes with optional filters.

        Args:
            node_type: Filter by node type.
            edge_type: If provided, only return nodes that have at least one
                       incident edge of this type (incoming or outgoing).
            **filters: Additional attribute key-value pairs to match on nodes.

        Returns:
            List of node data dicts (each includes 'id' key).
        """
        results = []
        for nid, ndata in self._nodes.items():
            # Filter by type
            if node_type is not None and ndata.get("type") != node_type:
                continue
            # Filter by additional attributes
            if not all(ndata.get(k) == v for k, v in filters.items()):
                continue
            # Filter by edge type if requested
            if edge_type is not None:
                has_edge = False
                # Check outgoing edges
                for tgt, edata in self._edges.get(nid, []):
                    if edata.get("type") == edge_type:
                        has_edge = True
                        break
                # Check incoming edges
                if not has_edge:
                    for src, targets in self._edges.items():
                        if src == nid:
                            continue
                        for tgt, edata in targets:
                            if tgt == nid and edata.get("type") == edge_type:
                                has_edge = True
                                break
                        if has_edge:
                            break
                if not has_edge:
                    continue
            # Include node id in returned data
            node_copy = dict(ndata)
            node_copy["id"] = nid
            results.append(node_copy)
        return results

    def find_path(
        self,
        start: str,
        end: str,
        edge_type: Optional[str] = None,
    ) -> Optional[List[str]]:
        """
        Simple BFS to find a directed path from start to end.
        Returns list of node IDs forming the path, or None.
        """
        if start not in self._nodes or end not in self._nodes:
            return None
        visited: Set[str] = set()
        queue: List[Tuple[str, List[str]]] = [(start, [start])]
        while queue:
            current, path = queue.pop(0)
            if current == end:
                return path
            if current in visited:
                continue
            visited.add(current)
            for neighbor, edata in self._edges.get(current, []):
                if edge_type is not None and edata.get("type") != edge_type:
                    continue
                if neighbor not in visited:
                    queue.append((neighbor, path + [neighbor]))
        return None

    def get_neighbors(
        self,
        node_id: str,
        edge_type: Optional[str] = None,
        direction: str = "outgoing",
    ) -> List[Tuple[str, Dict[str, Any]]]:
        """
        Get neighbors of a node.

        Args:
            node_id: The node to query.
            edge_type: Optional filter on edge type.
            direction: 'outgoing', 'incoming', or 'both'.

        Returns:
            List of (neighbor_id, edge_data) tuples.
        """
        if node_id not in self._nodes:
            raise KeyError(f"Node '{node_id}' not found.")
        neighbors: List[Tuple[str, Dict[str, Any]]] = []
        if direction in ("outgoing", "both"):
            for tgt, edata in self._edges.get(node_id, []):
                if edge_type is None or edata.get("type") == edge_type:
                    neighbors.append((tgt, edata))
        if direction in ("incoming", "both"):
            for src, targets in self._edges.items():
                if src == node_id:
                    continue
                for tgt, edata in targets:
                    if tgt == node_id:
                        if edge_type is None or edata.get("type") == edge_type:
                            neighbors.append((src, edata))
        return neighbors

    # ------------------------------------------------------------------
    # Serialization / Deserialization
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the graph to a dictionary."""
        # Convert edges to a serializable format
        edges_serializable: Dict[str, List[Dict[str, Any]]] = {}
        for src, targets in self._edges.items():
            edges_serializable[src] = [
                {"target": tgt, "data": data} for tgt, data in targets
            ]
        return {
            "nodes": self._nodes,
            "edges": edges_serializable,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> KnowledgeGraph:
        """Deserialize a graph from a dictionary."""
        kg = cls()
        kg._nodes = dict(data.get("nodes", {}))
        kg._edges = {}
        for src, edge_list in data.get("edges", {}).items():
            kg._edges[src] = [
                (entry["target"], dict(entry["data"])) for entry in edge_list
            ]
        return kg

    def to_json(self, indent: int = 2) -> str:
        """Serialize the graph to a JSON string."""
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_json(cls, json_str: str) -> KnowledgeGraph:
        """Deserialize a graph from a JSON string."""
        data = json.loads(json_str)
        return cls.from_dict(data)

    def save(self, filepath: str) -> None:
        """Save the graph to a JSON file."""
        with open(filepath, "w") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load(cls, filepath: str) -> KnowledgeGraph:
        """Load a graph from a JSON file."""
        with open(filepath, "r") as f:
            data = json.load(f)
        return cls.from_dict(data)

    def __repr__(self) -> str:
        return (
            f"KnowledgeGraph(nodes={len(self._nodes)}, edges={sum(len(v) for v in self._edges.values())})"
        )