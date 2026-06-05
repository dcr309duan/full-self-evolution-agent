from collections import defaultdict
from typing import Dict, Set, List, Optional, Any


class GoalDependencyGraph:
    """
    A directed acyclic graph (DAG) of goals and their dependencies.
    Maintains adjacency lists using sets for O(1) lookups.
    Supports multiple node types including regular goals, benchmark creation goals,
    and coordinated mutation goals.
    """

    # Node type constants
    GOAL = "GOAL"
    BENCHMARK_CREATION = "BENCHMARK_CREATION"
    COORDINATED_MUTATION = "COORDINATED_MUTATION"

    def __init__(self):
        # adjacency list: goal -> set of prerequisites (dependencies)
        self._prerequisites: Dict[str, Set[str]] = defaultdict(set)
        # reverse adjacency: goal -> set of dependents (goals that depend on it)
        self._dependents: Dict[str, Set[str]] = defaultdict(set)
        # set of goals that have been marked as met
        self._met: Set[str] = set()
        # node type mapping: node_name -> type string
        self._node_types: Dict[str, str] = {}
        # adjacency list for coordinated mutation relationships: mutation_node -> set of mutation nodes it coordinates with
        self._coordinated_with: Dict[str, Set[str]] = defaultdict(set)
        # risk level mapping: goal_name -> risk level (0-10)
        self._risk_levels: Dict[str, int] = {}
        # reward level mapping: goal_name -> reward level (0-10)
        self._reward_levels: Dict[str, int] = {}
        # critical infrastructure flag: goal_name -> bool
        self._critical_infrastructure: Dict[str, bool] = {}

    def add_goal(self, name: str, dependencies: Optional[List[str]] = None, 
                 node_type: str = GOAL, risk_level: int = 0, reward_level: int = 0,
                 is_critical_infrastructure: bool = False) -> None:
        """
        Add a goal with its dependencies (prerequisites).
        If the goal already exists, its dependencies are updated.
        
        Args:
            name: The name of the goal/node
            dependencies: List of prerequisite node names
            node_type: Type of node (GOAL, BENCHMARK_CREATION, or COORDINATED_MUTATION)
            risk_level: Risk level of the goal (0-10, higher = more risky)
            reward_level: Reward level of the goal (0-10, higher = more rewarding)
            is_critical_infrastructure: Whether the goal touches critical infrastructure
        """
        if dependencies is None:
            dependencies = []

        # Remove old dependencies if goal already exists
        if name in self._prerequisites:
            old_deps = self._prerequisites[name]
            for dep in old_deps:
                self._dependents[dep].discard(name)
                if not self._dependents[dep]:
                    del self._dependents[dep]
            del self._prerequisites[name]

        # Add new dependencies
        self._prerequisites[name] = set(dependencies)
        for dep in dependencies:
            self._dependents[dep].add(name)

        # Ensure the goal is in the dependents dict even if no one depends on it yet
        if name not in self._dependents:
            self._dependents[name] = set()

        # Set node type
        self._node_types[name] = node_type
        
        # Set risk, reward, and critical infrastructure attributes
        self._risk_levels[name] = max(0, min(10, risk_level))
        self._reward_levels[name] = max(0, min(10, reward_level))
        self._critical_infrastructure[name] = is_critical_infrastructure

    def remove_goal(self, name: str) -> None:
        """
        Remove a goal and all references to it from the graph.
        """
        if name not in self._prerequisites:
            raise KeyError(f"Goal '{name}' not found in the graph")

        # Remove this goal from its dependencies' dependents lists
        for dep in self._prerequisites[name]:
            self._dependents[dep].discard(name)
            if not self._dependents[dep]:
                del self._dependents[dep]

        # Remove this goal from its dependents' prerequisites lists
        for dependent in list(self._dependents.get(name, set())):
            self._prerequisites[dependent].discard(name)
            if not self._prerequisites[dependent]:
                del self._prerequisites[dependent]

        # Remove coordinated_with relationships
        if name in self._coordinated_with:
            for other in self._coordinated_with[name]:
                self._coordinated_with[other].discard(name)
                if not self._coordinated_with[other]:
                    del self._coordinated_with[other]
            del self._coordinated_with[name]

        # Remove the goal itself
        del self._prerequisites[name]
        if name in self._dependents:
            del self._dependents[name]
        self._met.discard(name)
        self._node_types.pop(name, None)
        self._risk_levels.pop(name, None)
        self._reward_levels.pop(name, None)
        self._critical_infrastructure.pop(name, None)

    def get_dependents(self, name: str) -> Set[str]:
        """
        Get all goals that directly depend on the given goal.
        """
        return self._dependents.get(name, set()).copy()

    def get_prerequisites(self, name: str) -> Set[str]:
        """
        Get all direct prerequisites of the given goal.
        """
        return self._prerequisites.get(name, set()).copy()

    def is_met(self, name: str) -> bool:
        """
        Check if a goal has been marked as met.
        """
        return name in self._met

    def mark_met(self, name: str) -> None:
        """
        Mark a goal as met.
        """
        if name not in self._prerequisites:
            raise KeyError(f"Goal '{name}' not found in the graph")
        self._met.add(name)

    def mark_unmet(self, name: str) -> None:
        """
        Mark a goal as unmet.
        """
        self._met.discard(name)

    def get_node_type(self, name: str) -> Optional[str]:
        """
        Get the type of a node (GOAL, BENCHMARK_CREATION, or COORDINATED_MUTATION).
        Returns None if the node doesn't exist.
        """
        return self._node_types.get(name)

    def get_blocked_goals(self) -> Set[str]:
        """
        Get all goals that have unmet prerequisites.
        """
        blocked = set()
        for goal, prereqs in self._prerequisites.items():
            if not prereqs.issubset(self._met):
                blocked.add(goal)
        return blocked

    def get_ready_goals(self) -> Set[str]:
        """
        Get all goals whose prerequisites are all met (ready to be worked on).
        Excludes goals that are already met.
        """
        ready = set()
        for goal in self._prerequisites:
            if goal not in self._met:
                prereqs = self._prerequisites[goal]
                if prereqs.issubset(self._met):
                    ready.add(goal)
        return ready

    def get_goals_by_type(self, node_type: str) -> Set[str]:
        """
        Get all nodes of a specific type.
        """
        return {name for name, ntype in self._node_types.items() if ntype == node_type}

    def add_coordinated_mutation(self, name: str, dependencies: Optional[List[str]] = None,
                                  coordinated_with: Optional[List[str]] = None,
                                  risk_level: int = 0, reward_level: int = 0,
                                  is_critical_infrastructure: bool = False) -> None:
        """
        Add a coordinated mutation node with its dependencies and coordination relationships.
        
        Args:
            name: The name of the coordinated mutation node
            dependencies: List of prerequisite node names (typically the modules being changed)
            coordinated_with: List of other coordinated mutation nodes this is coordinated with
            risk_level: Risk level of the goal (0-10, higher = more risky)
            reward_level: Reward level of the goal (0-10, higher = more rewarding)
            is_critical_infrastructure: Whether the goal touches critical infrastructure
        """
        self.add_goal(name, dependencies, self.COORDINATED_MUTATION, 
                     risk_level, reward_level, is_critical_infrastructure)
        
        if coordinated_with:
            for other in coordinated_with:
                self.add_coordination_edge(name, other)

    def add_coordination_edge(self, node1: str, node2: str) -> None:
        """
        Add an 'is_coordinated_with' relationship between two mutation nodes.
        Both nodes must exist and be of type COORDINATED_MUTATION.
        
        Args:
            node1: First coordinated mutation node
            node2: Second coordinated mutation node
        """
        if node1 not in self._node_types or self._node_types[node1] != self.COORDINATED_MUTATION:
            raise ValueError(f"Node '{node1}' is not a COORDINATED_MUTATION node")
        if node2 not in self._node_types or self._node_types[node2] != self.COORDINATED_MUTATION:
            raise ValueError(f"Node '{node2}' is not a COORDINATED_MUTATION node")
        
        self._coordinated_with[node1].add(node2)
        self._coordinated_with[node2].add(node1)

    def get_coordinated_mutations(self, name: str) -> Set[str]:
        """
        Get all coordinated mutation nodes that are coordinated with the given node.
        """
        return self._coordinated_with.get(name, set()).copy()

    def get_dependency_completeness_score(self, name: str) -> float:
        """
        Compute a 'dependency completeness score' for a given goal.
        Traverses the dependency graph and returns a ratio of how many required
        dependencies are already satisfied (have working implementations) vs. missing.
        
        Args:
            name: The name of the goal to compute the score for.
            
        Returns:
            A float between 0.0 and 1.0 representing the ratio of satisfied
            dependencies to total dependencies. Returns 1.0 if the goal has no
            dependencies or if all dependencies are met.
            
        Raises:
            KeyError: If the goal does not exist in the graph.
        """
        if name not in self._prerequisites:
            raise KeyError(f"Goal '{name}' not found in the graph")
        
        # Collect all transitive dependencies (including the goal itself for completeness)
        all_deps = set()
        self._collect_transitive_dependencies(name, all_deps)
        
        # Remove the goal itself from the set to only count its dependencies
        all_deps.discard(name)
        
        if not all_deps:
            return 1.0
        
        # Count how many of these dependencies are met
        met_count = sum(1 for dep in all_deps if dep in self._met)
        
        return met_count / len(all_deps)

    def _collect_transitive_dependencies(self, name: str, visited: Set[str]) -> None:
        """
        Helper method to recursively collect all transitive dependencies of a goal.
        
        Args:
            name: The current node being traversed
            visited: Set to collect all visited nodes (including the starting node)
        """
        if name in visited:
            return
        visited.add(name)
        for dep in self._prerequisites.get(name, set()):
            self._collect_transitive_dependencies(dep, visited)

    def get_sandbox_safe_goals(self) -> Set[str]:
        """
        Identify goals which would benefit most from sandboxed execution.
        These are goals that are high risk, high reward, or touch critical infrastructure.
        
        Returns:
            A set of goal names that are candidates for sandboxed execution.
        """
        sandbox_candidates = set()
        
        for goal in self._prerequisites:
            # Check if goal has risk level >= 7 (high risk)
            if self._risk_levels.get(goal, 0) >= 7:
                sandbox_candidates.add(goal)
            
            # Check if goal has reward level >= 7 (high reward)
            if self._reward_levels.get(goal, 0) >= 7:
                sandbox_candidates.add(goal)
            
            # Check if goal touches critical infrastructure
            if self._critical_infrastructure.get(goal, False):
                sandbox_candidates.add(goal)
        
        return sandbox_candidates

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize the graph to a dictionary.
        """
        return {
            "prerequisites": {k: list(v) for k, v in self._prerequisites.items()},
            "met": list(self._met),
            "node_types": dict(self._node_types),
            "coordinated_with": {k: list(v) for k, v in self._coordinated_with.items()},
            "risk_levels": dict(self._risk_levels),
            "reward_levels": dict(self._reward_levels),
            "critical_infrastructure": dict(self._critical_infrastructure)
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GoalDependencyGraph":
        """
        Deserialize a graph from a dictionary.
        """
        graph = cls()
        node_types = data.get("node_types", {})
        risk_levels = data.get("risk_levels", {})
        reward_levels = data.get("reward_levels", {})
        critical_infrastructure = data.get("critical_infrastructure", {})
        
        for goal, prereqs in data.get("prerequisites", {}).items():
            node_type = node_types.get(goal, cls.GOAL)
            risk = risk_levels.get(goal, 0)
            reward = reward_levels.get(goal, 0)
            critical = critical_infrastructure.get(goal, False)
            graph.add_goal(goal, prereqs, node_type, risk, reward, critical)
        
        for goal in data.get("met", []):
            graph.mark_met(goal)
        
        # Restore coordinated_with relationships
        coordinated_with = data.get("coordinated_with", {})
        for node, others in coordinated_with.items():
            for other in others:
                if node in graph and other in graph:
                    graph._coordinated_with[node].add(other)
        
        return graph

    def __contains__(self, name: str) -> bool:
        return name in self._prerequisites

    def __len__(self) -> int:
        return len(self._prerequisites)

    def __repr__(self) -> str:
        return f"GoalDependencyGraph(goals={set(self._prerequisites.keys())})"