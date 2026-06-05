from collections import defaultdict
from typing import Dict, Set, List, Optional, Any


class GoalDependencyGraph:
    """
    A directed acyclic graph (DAG) of goals and their dependencies.
    Maintains adjacency lists using sets for O(1) lookups.
    """

    def __init__(self):
        # adjacency list: goal -> set of prerequisites (dependencies)
        self._prerequisites: Dict[str, Set[str]] = defaultdict(set)
        # reverse adjacency: goal -> set of dependents (goals that depend on it)
        self._dependents: Dict[str, Set[str]] = defaultdict(set)
        # set of goals that have been marked as met
        self._met: Set[str] = set()

    def add_goal(self, name: str, dependencies: Optional[List[str]] = None) -> None:
        """
        Add a goal with its dependencies (prerequisites).
        If the goal already exists, its dependencies are updated.
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

        # Remove the goal itself
        del self._prerequisites[name]
        if name in self._dependents:
            del self._dependents[name]
        self._met.discard(name)

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

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize the graph to a dictionary.
        """
        return {
            "prerequisites": {k: list(v) for k, v in self._prerequisites.items()},
            "met": list(self._met)
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GoalDependencyGraph":
        """
        Deserialize a graph from a dictionary.
        """
        graph = cls()
        for goal, prereqs in data.get("prerequisites", {}).items():
            graph.add_goal(goal, prereqs)
        for goal in data.get("met", []):
            graph.mark_met(goal)
        return graph

    def __contains__(self, name: str) -> bool:
        return name in self._prerequisites

    def __len__(self) -> int:
        return len(self._prerequisites)

    def __repr__(self) -> str:
        return f"GoalDependencyGraph(goals={set(self._prerequisites.keys())})"