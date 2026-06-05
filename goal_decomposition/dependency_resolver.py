from typing import Dict, List, Set, Tuple, Optional
from collections import defaultdict, deque
import json
import os


class DependencyResolver:
    """
    Resolves dependencies for goal decomposition using a knowledge graph.
    Implements Kahn's algorithm for topological sorting and critical path identification.
    """

    def __init__(self, knowledge_graph_path: Optional[str] = None):
        """
        Initialize the DependencyResolver.

        Args:
            knowledge_graph_path: Path to the self-model knowledge graph JSON file.
                                  If None, uses default path.
        """
        self.knowledge_graph: Dict = {}
        self.graph_path = knowledge_graph_path or os.path.join(
            os.path.dirname(__file__), "self_model_knowledge_graph.json"
        )
        self._load_knowledge_graph()

    def _load_knowledge_graph(self) -> None:
        """Load the self-model knowledge graph from file."""
        if not os.path.exists(self.graph_path):
            raise FileNotFoundError(
                f"Knowledge graph file not found: {self.graph_path}"
            )
        with open(self.graph_path, "r") as f:
            self.knowledge_graph = json.load(f)

    def _get_all_components(self, goal: str) -> Set[str]:
        """
        Identify all components related to the given goal.

        Args:
            goal: The goal identifier to find components for.

        Returns:
            Set of component identifiers related to the goal.
        """
        related_components = set()
        if goal in self.knowledge_graph:
            # Directly related components
            related_components.add(goal)
            # Recursively find all sub-components
            stack = [goal]
            while stack:
                current = stack.pop()
                if current in self.knowledge_graph:
                    for dep in self.knowledge_graph[current].get("dependencies", []):
                        if dep not in related_components:
                            related_components.add(dep)
                            stack.append(dep)
                    for sub in self.knowledge_graph[current].get("sub_goals", []):
                        if sub not in related_components:
                            related_components.add(sub)
                            stack.append(sub)
        return related_components

    def _build_dependency_graph(self, components: Set[str]) -> Dict[str, List[str]]:
        """
        Build a directed graph of dependencies from the set of components.

        Args:
            components: Set of component identifiers.

        Returns:
            Dictionary mapping each component to its list of dependencies.
        """
        graph: Dict[str, List[str]] = {}
        for comp in components:
            if comp in self.knowledge_graph:
                deps = self.knowledge_graph[comp].get("dependencies", [])
                # Only include dependencies that are in our component set
                graph[comp] = [d for d in deps if d in components]
            else:
                graph[comp] = []
        return graph

    def _kahn_topological_sort(
        self, graph: Dict[str, List[str]]
    ) -> Tuple[List[str], bool]:
        """
        Perform topological sorting using Kahn's algorithm.

        Args:
            graph: Dependency graph as adjacency list.

        Returns:
            Tuple of (topological order list, bool indicating if DAG is valid).
        """
        # Calculate in-degree for each node
        in_degree: Dict[str, int] = {node: 0 for node in graph}
        for node in graph:
            for dep in graph[node]:
                if dep in in_degree:
                    in_degree[dep] += 1

        # Initialize queue with nodes having zero in-degree
        queue = deque([node for node in graph if in_degree[node] == 0])
        topological_order = []

        while queue:
            node = queue.popleft()
            topological_order.append(node)

            # Decrease in-degree of neighbors
            for neighbor in graph.get(node, []):
                if neighbor in in_degree:
                    in_degree[neighbor] -= 1
                    if in_degree[neighbor] == 0:
                        queue.append(neighbor)

        # Check if all nodes were processed (no cycles)
        is_dag = len(topological_order) == len(graph)
        return topological_order, is_dag

    def _compute_earliest_times(
        self, graph: Dict[str, List[str]], topological_order: List[str]
    ) -> Dict[str, int]:
        """
        Compute earliest start times for each node.

        Args:
            graph: Dependency graph.
            topological_order: List of nodes in topological order.

        Returns:
            Dictionary mapping node to its earliest start time.
        """
        earliest: Dict[str, int] = {node: 0 for node in graph}
        for node in topological_order:
            for dep in graph.get(node, []):
                # Each dependency adds 1 unit of time (can be customized)
                earliest[dep] = max(earliest[dep], earliest[node] + 1)
        return earliest

    def _compute_latest_times(
        self,
        graph: Dict[str, List[str]],
        topological_order: List[str],
        earliest: Dict[str, int],
    ) -> Dict[str, int]:
        """
        Compute latest start times for each node.

        Args:
            graph: Dependency graph.
            topological_order: List of nodes in topological order.
            earliest: Earliest start times.

        Returns:
            Dictionary mapping node to its latest start time.
        """
        # Reverse graph for backward pass
        reverse_graph: Dict[str, List[str]] = defaultdict(list)
        for node in graph:
            for dep in graph[node]:
                reverse_graph[dep].append(node)

        # Initialize latest times with the maximum earliest time
        max_time = max(earliest.values()) if earliest else 0
        latest: Dict[str, int] = {node: max_time for node in graph}

        # Process in reverse topological order
        for node in reversed(topological_order):
            for successor in reverse_graph.get(node, []):
                latest[node] = min(latest[node], latest[successor] - 1)

        return latest

    def _identify_critical_path(
        self,
        graph: Dict[str, List[str]],
        earliest: Dict[str, int],
        latest: Dict[str, int],
    ) -> List[str]:
        """
        Identify the critical path (nodes with zero slack).

        Args:
            graph: Dependency graph.
            earliest: Earliest start times.
            latest: Latest start times.

        Returns:
            List of nodes on the critical path in order.
        """
        critical_nodes = [
            node for node in graph if earliest.get(node, 0) == latest.get(node, 0)
        ]
        # Sort critical nodes by their earliest time to maintain order
        critical_nodes.sort(key=lambda n: earliest.get(n, 0))
        return critical_nodes

    def resolve_goal(self, goal: str) -> Dict:
        """
        Resolve dependencies for a given goal and return a DAG with critical path.

        Args:
            goal: The goal identifier to resolve.

        Returns:
            Dictionary containing:
                - 'goal': The input goal
                - 'components': Set of related components
                - 'topological_order': Topological ordering of components
                - 'is_dag': Whether the dependency graph is a valid DAG
                - 'critical_path': List of nodes on the critical path
                - 'earliest_times': Earliest start times for each component
                - 'latest_times': Latest start times for each component
                - 'graph': The dependency graph adjacency list
        """
        # Step 1: Identify all components related to the goal
        components = self._get_all_components(goal)

        # Step 2: Build dependency graph
        graph = self._build_dependency_graph(components)

        # Step 3: Compute topological order using Kahn's algorithm
        topological_order, is_dag = self._kahn_topological_sort(graph)

        if not is_dag:
            # If there's a cycle, return partial results
            return {
                "goal": goal,
                "components": components,
                "topological_order": topological_order,
                "is_dag": False,
                "critical_path": [],
                "earliest_times": {},
                "latest_times": {},
                "graph": graph,
                "error": "Cycle detected in dependency graph",
            }

        # Step 4: Compute earliest and latest times for critical path
        earliest = self._compute_earliest_times(graph, topological_order)
        latest = self._compute_latest_times(graph, topological_order, earliest)
        critical_path = self._identify_critical_path(graph, earliest, latest)

        return {
            "goal": goal,
            "components": components,
            "topological_order": topological_order,
            "is_dag": True,
            "critical_path": critical_path,
            "earliest_times": earliest,
            "latest_times": latest,
            "graph": graph,
        }

    def get_sub_goal_dag(self, goal: str) -> Dict:
        """
        Convenience method to get the DAG of sub-goals with critical path.

        Args:
            goal: The goal identifier.

        Returns:
            Dictionary with DAG structure and critical path information.
        """
        result = self.resolve_goal(goal)
        # Extract only sub-goal related information if needed
        sub_goals = {}
        for comp in result.get("components", set()):
            if comp in self.knowledge_graph:
                sub_goals[comp] = {
                    "dependencies": self.knowledge_graph[comp].get("dependencies", []),
                    "sub_goals": self.knowledge_graph[comp].get("sub_goals", []),
                    "description": self.knowledge_graph[comp].get("description", ""),
                }
        result["sub_goals"] = sub_goals
        return result