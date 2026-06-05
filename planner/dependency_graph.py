import re
from typing import Dict, List, Set, Tuple, Optional
from collections import defaultdict, deque


class DependencyGraph:
    """
    A directed acyclic graph (DAG) representing dependencies between goals/capabilities.
    Supports parsing dependency edges from goal descriptions, topological sorting,
    and identifying blocked vs. ready goals.
    """

    def __init__(self):
        # adjacency list: node -> list of nodes that depend on it (dependents)
        self._forward: Dict[str, List[str]] = defaultdict(list)
        # adjacency list: node -> list of nodes it depends on (prerequisites)
        self._reverse: Dict[str, List[str]] = defaultdict(list)
        # set of all nodes
        self._nodes: Set[str] = set()
        # cache for topological sort (invalidated on changes)
        self._topo_cache: Optional[List[str]] = None

    def add_dependency(self, dependent: str, prerequisite: str) -> None:
        """
        Add a directed edge: prerequisite -> dependent.
        That is, 'dependent' depends on 'prerequisite'.
        """
        if dependent == prerequisite:
            return  # self-loop ignored
        self._nodes.add(dependent)
        self._nodes.add(prerequisite)
        self._forward[prerequisite].append(dependent)
        self._reverse[dependent].append(prerequisite)
        self._topo_cache = None  # invalidate cache

    def add_node(self, node: str) -> None:
        """Add a node with no dependencies."""
        self._nodes.add(node)

    def remove_node(self, node: str) -> None:
        """Remove a node and all its incident edges."""
        if node not in self._nodes:
            return
        # remove forward edges
        for prereq in self._reverse[node]:
            if prereq in self._forward:
                self._forward[prereq] = [d for d in self._forward[prereq] if d != node]
        # remove reverse edges
        for dep in self._forward[node]:
            if dep in self._reverse:
                self._reverse[dep] = [p for p in self._reverse[dep] if p != node]
        # clean up empty lists
        self._forward.pop(node, None)
        self._reverse.pop(node, None)
        self._nodes.discard(node)
        self._topo_cache = None

    def get_prerequisites(self, node: str) -> List[str]:
        """Return list of prerequisites for a given node."""
        return self._reverse.get(node, [])

    def get_dependents(self, node: str) -> List[str]:
        """Return list of nodes that directly depend on the given node."""
        return self._forward.get(node, [])

    def has_cycle(self) -> bool:
        """Check if the graph contains a cycle using DFS."""
        visited: Set[str] = set()
        rec_stack: Set[str] = set()

        def dfs(node: str) -> bool:
            visited.add(node)
            rec_stack.add(node)
            for neighbor in self._forward.get(node, []):
                if neighbor not in visited:
                    if dfs(neighbor):
                        return True
                elif neighbor in rec_stack:
                    return True
            rec_stack.discard(node)
            return False

        for node in self._nodes:
            if node not in visited:
                if dfs(node):
                    return True
        return False

    def topological_sort(self) -> List[str]:
        """
        Return a topological ordering of all nodes (Kahn's algorithm).
        Raises ValueError if a cycle is detected.
        """
        if self._topo_cache is not None:
            return self._topo_cache

        # compute in-degree (number of prerequisites)
        in_degree: Dict[str, int] = {node: 0 for node in self._nodes}
        for node in self._nodes:
            for prereq in self._reverse.get(node, []):
                in_degree[node] += 1

        # queue of nodes with no prerequisites
        queue = deque([node for node, deg in in_degree.items() if deg == 0])
        topo_order: List[str] = []

        while queue:
            node = queue.popleft()
            topo_order.append(node)
            for dependent in self._forward.get(node, []):
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    queue.append(dependent)

        if len(topo_order) != len(self._nodes):
            raise ValueError("Graph contains a cycle; topological sort not possible.")

        self._topo_cache = topo_order
        return topo_order

    def get_blocked_goals(self, satisfied: Set[str]) -> Set[str]:
        """
        Return set of goals whose prerequisites are not fully satisfied.
        A goal is blocked if it has at least one prerequisite not in 'satisfied'.
        """
        blocked: Set[str] = set()
        for node in self._nodes:
            prereqs = set(self._reverse.get(node, []))
            if prereqs and not prereqs.issubset(satisfied):
                blocked.add(node)
        return blocked

    def get_ready_goals(self, satisfied: Set[str]) -> Set[str]:
        """
        Return set of goals whose all prerequisites are satisfied.
        A goal is ready if all its prerequisites are in 'satisfied'.
        """
        ready: Set[str] = set()
        for node in self._nodes:
            prereqs = set(self._reverse.get(node, []))
            if prereqs.issubset(satisfied):
                ready.add(node)
        return ready

    def parse_from_goal_list(self, goals: List[str]) -> None:
        """
        Parse a list of goal/capability descriptions and extract dependency edges.
        Recognizes patterns like:
          - "goal depends on prerequisite"
          - "goal -> prerequisite"
          - "goal requires prerequisite"
        Also handles multi-word names (quoted or unquoted).
        """
        # Pattern 1: "X depends on Y" or "X depends on Y and Z"
        pattern1 = re.compile(
            r'([A-Za-z0-9_ -]+?)\s+(?:depends?\s+on|requires?)\s+(.+)',
            re.IGNORECASE
        )
        # Pattern 2: "X -> Y" (arrow notation)
        pattern2 = re.compile(
            r'([A-Za-z0-9_ -]+?)\s*->\s*([A-Za-z0-9_ -]+)'
        )
        # Pattern 3: "X depends on Y" (simpler)
        pattern3 = re.compile(
            r'([A-Za-z0-9_ -]+?)\s+depends?\s+on\s+([A-Za-z0-9_ -]+)',
            re.IGNORECASE
        )

        for goal_desc in goals:
            goal_desc = goal_desc.strip()
            if not goal_desc:
                continue

            # Try pattern 1 (supports "and" for multiple prerequisites)
            match = pattern1.search(goal_desc)
            if match:
                dependent = match.group(1).strip()
                prereq_part = match.group(2).strip()
                # Split on "and" or "," to get multiple prerequisites
                prereqs = re.split(r'\s+(?:and|,)\s+', prereq_part)
                for prereq in prereqs:
                    prereq = prereq.strip()
                    if prereq:
                        self.add_dependency(dependent, prereq)
                continue

            # Try pattern 2 (arrow)
            match = pattern2.search(goal_desc)
            if match:
                dependent = match.group(2).strip()
                prerequisite = match.group(1).strip()
                self.add_dependency(dependent, prerequisite)
                continue

            # Try pattern 3 (simple)
            match = pattern3.search(goal_desc)
            if match:
                dependent = match.group(1).strip()
                prerequisite = match.group(2).strip()
                self.add_dependency(dependent, prerequisite)
                continue

            # If no dependency pattern found, just add as a node
            self.add_node(goal_desc)

    def __repr__(self) -> str:
        return (f"DependencyGraph(nodes={len(self._nodes)}, "
                f"edges={sum(len(v) for v in self._forward.values())})")

    def get_nodes(self) -> Set[str]:
        """Return the set of all nodes in the graph."""
        return self._nodes.copy()

    def clear(self) -> None:
        """Remove all nodes and edges."""
        self._forward.clear()
        self._reverse.clear()
        self._nodes.clear()
        self._topo_cache = None