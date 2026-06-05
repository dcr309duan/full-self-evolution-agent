"""system_model.py - Goal Dependency Graph as a component in the system model."""

import json
from typing import Dict, List, Optional, Set, Any
from dataclasses import dataclass, field, asdict


@dataclass
class GoalNode:
    """Represents a single goal in the dependency graph."""
    id: str
    description: str
    status: str = "pending"  # pending, active, achieved, failed
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DependencyEdge:
    """Represents a dependency between two goals."""
    source_id: str
    target_id: str
    dependency_type: str = "requires"  # requires, enables, conflicts
    weight: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)


class GoalDependencyGraph:
    """
    Directed graph representing dependencies between goals.
    Supports querying for failure analysis, curiosity, and meta-mutation.
    """

    def __init__(self):
        self.nodes: Dict[str, GoalNode] = {}
        self.edges: List[DependencyEdge] = []
        self._adjacency: Dict[str, Set[str]] = {}  # source -> set of targets
        self._reverse_adjacency: Dict[str, Set[str]] = {}  # target -> set of sources

    def add_goal(self, goal_id: str, description: str, status: str = "pending",
                 metadata: Optional[Dict[str, Any]] = None) -> GoalNode:
        """Add a goal node to the graph."""
        if goal_id in self.nodes:
            raise ValueError(f"Goal '{goal_id}' already exists.")
        node = GoalNode(id=goal_id, description=description, status=status,
                        metadata=metadata or {})
        self.nodes[goal_id] = node
        self._adjacency.setdefault(goal_id, set())
        self._reverse_adjacency.setdefault(goal_id, set())
        return node

    def add_dependency(self, source_id: str, target_id: str,
                       dependency_type: str = "requires",
                       weight: float = 1.0,
                       metadata: Optional[Dict[str, Any]] = None) -> DependencyEdge:
        """Add a dependency edge from source to target."""
        if source_id not in self.nodes:
            raise ValueError(f"Source goal '{source_id}' not found.")
        if target_id not in self.nodes:
            raise ValueError(f"Target goal '{target_id}' not found.")
        edge = DependencyEdge(
            source_id=source_id,
            target_id=target_id,
            dependency_type=dependency_type,
            weight=weight,
            metadata=metadata or {}
        )
        self.edges.append(edge)
        self._adjacency[source_id].add(target_id)
        self._reverse_adjacency[target_id].add(source_id)
        return edge

    def get_dependencies(self, goal_id: str) -> List[str]:
        """Get goals that this goal depends on (predecessors)."""
        return list(self._reverse_adjacency.get(goal_id, set()))

    def get_dependents(self, goal_id: str) -> List[str]:
        """Get goals that depend on this goal (successors)."""
        return list(self._adjacency.get(goal_id, set()))

    def get_goal(self, goal_id: str) -> Optional[GoalNode]:
        """Retrieve a goal node by ID."""
        return self.nodes.get(goal_id)

    def get_goals_by_status(self, status: str) -> List[GoalNode]:
        """Get all goals with a given status."""
        return [node for node in self.nodes.values() if node.status == status]

    def update_goal_status(self, goal_id: str, new_status: str) -> None:
        """Update the status of a goal."""
        if goal_id not in self.nodes:
            raise ValueError(f"Goal '{goal_id}' not found.")
        self.nodes[goal_id].status = new_status

    def get_impacted_goals(self, goal_id: str) -> Set[str]:
        """Get all goals that would be impacted if this goal fails (transitive dependents)."""
        impacted = set()
        stack = [goal_id]
        while stack:
            current = stack.pop()
            for dependent in self.get_dependents(current):
                if dependent not in impacted:
                    impacted.add(dependent)
                    stack.append(dependent)
        return impacted

    def get_prerequisite_chain(self, goal_id: str) -> List[str]:
        """Get the chain of prerequisites for a goal (transitive dependencies)."""
        chain = []
        stack = [goal_id]
        visited = set()
        while stack:
            current = stack.pop()
            if current in visited:
                continue
            visited.add(current)
            for dep in self.get_dependencies(current):
                if dep not in visited:
                    chain.append(dep)
                    stack.append(dep)
        return chain

    def to_dict(self) -> Dict[str, Any]:
        """Export the graph as a JSON-serializable dict."""
        return {
            "nodes": {gid: asdict(node) for gid, node in self.nodes.items()},
            "edges": [asdict(edge) for edge in self.edges]
        }

    def to_json(self, indent: int = 2) -> str:
        """Export the graph as a JSON string."""
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GoalDependencyGraph":
        """Create a graph from a dict (inverse of to_dict)."""
        graph = cls()
        for gid, node_data in data.get("nodes", {}).items():
            graph.nodes[gid] = GoalNode(**node_data)
            graph._adjacency.setdefault(gid, set())
            graph._reverse_adjacency.setdefault(gid, set())
        for edge_data in data.get("edges", []):
            edge = DependencyEdge(**edge_data)
            graph.edges.append(edge)
            graph._adjacency[edge.source_id].add(edge.target_id)
            graph._reverse_adjacency[edge.target_id].add(edge.source_id)
        return graph


class SystemModel:
    """
    Self-model knowledge graph containing the goal dependency graph
    and other system components.
    """

    def __init__(self):
        self.goal_graph = GoalDependencyGraph()
        self._components: Dict[str, Any] = {}

    def register_component(self, name: str, component: Any) -> None:
        """Register a component in the system model."""
        self._components[name] = component

    def get_component(self, name: str) -> Optional[Any]:
        """Retrieve a registered component."""
        return self._components.get(name)

    def query_goal_graph(self, query_type: str, **kwargs) -> Any:
        """
        Query the goal dependency graph.
        Supported query types:
        - 'dependencies': get dependencies of a goal
        - 'dependents': get dependents of a goal
        - 'impacted': get impacted goals if a goal fails
        - 'prerequisites': get prerequisite chain
        - 'by_status': get goals by status
        """
        if query_type == "dependencies":
            return self.goal_graph.get_dependencies(kwargs["goal_id"])
        elif query_type == "dependents":
            return self.goal_graph.get_dependents(kwargs["goal_id"])
        elif query_type == "impacted":
            return self.goal_graph.get_impacted_goals(kwargs["goal_id"])
        elif query_type == "prerequisites":
            return self.goal_graph.get_prerequisite_chain(kwargs["goal_id"])
        elif query_type == "by_status":
            return self.goal_graph.get_goals_by_status(kwargs["status"])
        else:
            raise ValueError(f"Unknown query type: {query_type}")

    def export_goal_graph(self, as_json: bool = False) -> Any:
        """
        Export the goal dependency graph.
        Returns dict by default, or JSON string if as_json=True.
        """
        if as_json:
            return self.goal_graph.to_json()
        return self.goal_graph.to_dict()

    def to_dict(self) -> Dict[str, Any]:
        """Export the entire system model as a dict."""
        return {
            "goal_graph": self.goal_graph.to_dict(),
            "components": {name: str(type(comp)) for name, comp in self._components.items()}
        }

    def to_json(self, indent: int = 2) -> str:
        """Export the entire system model as JSON."""
        return json.dumps(self.to_dict(), indent=indent)