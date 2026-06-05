"""Dependency graph for managing causal prerequisites between capabilities/modules."""

import json
import yaml
from typing import Dict, List, Optional, Set, Tuple


class DependencyGraph:
    """Formal causal dependency graph for self-model knowledge."""

    def __init__(self, knowledge_graph: Optional[Dict] = None):
        """
        Initialize dependency graph.

        Args:
            knowledge_graph: Optional dict representing the self-model knowledge graph.
                Expected structure: {module_id: {"prerequisites": [list of module_ids], ...}}
        """
        self._graph: Dict[str, Dict] = knowledge_graph or {}
        self._completion_status: Dict[str, bool] = {}
        self._initialize_completion()

    def _initialize_completion(self) -> None:
        """Set all known modules to incomplete initially."""
        for module_id in self._graph:
            self._completion_status[module_id] = False

    # ------------------------------------------------------------------
    # Loading / Persistence
    # ------------------------------------------------------------------

    def load_from_json(self, filepath: str) -> None:
        """Load knowledge graph from a JSON file."""
        with open(filepath, 'r') as f:
            data = json.load(f)
        self._graph = data
        self._initialize_completion()

    def load_from_yaml(self, filepath: str) -> None:
        """Load knowledge graph from a YAML file."""
        with open(filepath, 'r') as f:
            data = yaml.safe_load(f)
        self._graph = data
        self._initialize_completion()

    def save_to_json(self, filepath: str) -> None:
        """Export dependency manifest to JSON."""
        manifest = self._build_manifest()
        with open(filepath, 'w') as f:
            json.dump(manifest, f, indent=2)

    def save_to_yaml(self, filepath: str) -> None:
        """Export dependency manifest to YAML."""
        manifest = self._build_manifest()
        with open(filepath, 'w') as f:
            yaml.dump(manifest, f, default_flow_style=False)

    def _build_manifest(self) -> Dict:
        """Build a machine-readable dependency manifest."""
        manifest = {}
        for module_id, info in self._graph.items():
            manifest[module_id] = {
                "prerequisites": info.get("prerequisites", []),
                "complete": self._completion_status.get(module_id, False)
            }
        return manifest

    # ------------------------------------------------------------------
    # Query Methods
    # ------------------------------------------------------------------

    def get_prerequisites(self, goal: str) -> List[str]:
        """
        Return the direct prerequisites for a given goal/module.

        Args:
            goal: The module/capability identifier.

        Returns:
            List of prerequisite module IDs.

        Raises:
            KeyError: If the goal is not in the knowledge graph.
        """
        if goal not in self._graph:
            raise KeyError(f"Goal '{goal}' not found in dependency graph.")
        return self._graph[goal].get("prerequisites", [])

    def get_all_prerequisites(self, goal: str) -> Set[str]:
        """
        Return all transitive prerequisites for a given goal/module.

        Args:
            goal: The module/capability identifier.

        Returns:
            Set of all prerequisite module IDs (including indirect).

        Raises:
            KeyError: If the goal is not in the knowledge graph.
        """
        if goal not in self._graph:
            raise KeyError(f"Goal '{goal}' not found in dependency graph.")

        visited: Set[str] = set()
        stack = [goal]

        while stack:
            current = stack.pop()
            if current in visited:
                continue
            visited.add(current)
            for prereq in self._graph[current].get("prerequisites", []):
                if prereq not in visited:
                    stack.append(prereq)

        visited.discard(goal)
        return visited

    def get_incomplete_dependencies(self, goal: str) -> List[str]:
        """
        Return all incomplete prerequisites (direct and transitive) for a goal.

        Args:
            goal: The module/capability identifier.

        Returns:
            List of incomplete prerequisite module IDs.

        Raises:
            KeyError: If the goal is not in the knowledge graph.
        """
        all_prereqs = self.get_all_prerequisites(goal)
        incomplete = [
            mod for mod in all_prereqs
            if not self._completion_status.get(mod, False)
        ]
        return incomplete

    # ------------------------------------------------------------------
    # Status Methods
    # ------------------------------------------------------------------

    def mark_complete(self, module: str) -> None:
        """
        Mark a module as complete.

        Args:
            module: The module identifier to mark complete.

        Raises:
            KeyError: If the module is not in the knowledge graph.
        """
        if module not in self._graph:
            raise KeyError(f"Module '{module}' not found in dependency graph.")
        self._completion_status[module] = True

    def mark_incomplete(self, module: str) -> None:
        """
        Mark a module as incomplete.

        Args:
            module: The module identifier to mark incomplete.

        Raises:
            KeyError: If the module is not in the knowledge graph.
        """
        if module not in self._graph:
            raise KeyError(f"Module '{module}' not found in dependency graph.")
        self._completion_status[module] = False

    def is_complete(self, module: str) -> bool:
        """
        Check if a module is marked complete.

        Args:
            module: The module identifier.

        Returns:
            True if complete, False otherwise.

        Raises:
            KeyError: If the module is not in the knowledge graph.
        """
        if module not in self._graph:
            raise KeyError(f"Module '{module}' not found in dependency graph.")
        return self._completion_status.get(module, False)

    def reset_completion(self) -> None:
        """Reset all completion statuses to incomplete."""
        self._initialize_completion()

    # ------------------------------------------------------------------
    # Graph Manipulation
    # ------------------------------------------------------------------

    def add_module(self, module_id: str, prerequisites: Optional[List[str]] = None) -> None:
        """
        Add a new module to the dependency graph.

        Args:
            module_id: Identifier for the new module.
            prerequisites: Optional list of prerequisite module IDs.
        """
        if module_id in self._graph:
            raise ValueError(f"Module '{module_id}' already exists in the graph.")
        self._graph[module_id] = {"prerequisites": prerequisites or []}
        self._completion_status[module_id] = False

    def remove_module(self, module_id: str) -> None:
        """
        Remove a module from the dependency graph.

        Args:
            module_id: Identifier of the module to remove.

        Raises:
            KeyError: If the module is not in the graph.
        """
        if module_id not in self._graph:
            raise KeyError(f"Module '{module_id}' not found in dependency graph.")
        del self._graph[module_id]
        self._completion_status.pop(module_id, None)

    def add_prerequisite(self, module: str, prerequisite: str) -> None:
        """
        Add a prerequisite relationship.

        Args:
            module: The module that depends on the prerequisite.
            prerequisite: The prerequisite module.

        Raises:
            KeyError: If either module is not in the graph.
        """
        if module not in self._graph:
            raise KeyError(f"Module '{module}' not found in dependency graph.")
        if prerequisite not in self._graph:
            raise KeyError(f"Prerequisite '{prerequisite}' not found in dependency graph.")
        prereqs = self._graph[module].setdefault("prerequisites", [])
        if prerequisite not in prereqs:
            prereqs.append(prerequisite)

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        return f"DependencyGraph(modules={len(self._graph)}, completed={sum(self._completion_status.values())})"