from typing import List, Dict, Any, Optional
from collections import deque
import json
import os

class GoalPrioritizer:
    """
    A GoalPrioritizer that assigns priority scores to goals based on their depth in a DAG,
    supports dynamic reordering of a goal queue when dependencies resolve,
    and allows manual priority overrides via a configuration file.
    """

    def __init__(self, dependency_graph: Optional[Any] = None, config_path: Optional[str] = None):
        """
        Initialize the GoalPrioritizer.

        Args:
            dependency_graph: An object with a topological_order property (list of goal IDs).
            config_path: Path to a JSON configuration file for manual priority overrides.
        """
        self.dependency_graph = dependency_graph
        self.config_path = config_path
        self.manual_overrides: Dict[str, int] = {}
        self._load_config()

    def _load_config(self) -> None:
        """Load manual priority overrides from the configuration file if it exists."""
        if self.config_path and os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r') as f:
                    config = json.load(f)
                    self.manual_overrides = config.get('priority_overrides', {})
            except (json.JSONDecodeError, IOError) as e:
                print(f"Warning: Could not load config file {self.config_path}: {e}")
                self.manual_overrides = {}

    def _compute_depth(self, topo_order: List[str]) -> Dict[str, int]:
        """
        Compute depth for each goal in the topological order.
        Depth is defined as the number of dependencies (predecessors) in the DAG.
        Deeper goals (more prerequisites) get higher priority after prerequisites are met.

        Args:
            topo_order: List of goal IDs in topological order.

        Returns:
            Dictionary mapping goal ID to depth score (higher = deeper).
        """
        depth_map: Dict[str, int] = {}
        # In a topological order, the position roughly corresponds to depth.
        # We assign depth based on index: later goals are deeper.
        for idx, goal_id in enumerate(topo_order):
            depth_map[goal_id] = idx
        return depth_map

    def assign_priorities(self, topo_order: Optional[List[str]] = None) -> Dict[str, int]:
        """
        Assign priority scores to goals based on depth in the DAG.
        Priority = depth (higher depth = higher priority after prerequisites are met).
        Manual overrides take precedence.

        Args:
            topo_order: Optional list of goal IDs in topological order.
                        If not provided, uses the dependency_graph's topological_order.

        Returns:
            Dictionary mapping goal ID to priority score (higher = higher priority).
        """
        if topo_order is None:
            if self.dependency_graph is None:
                raise ValueError("No topological order provided and no dependency_graph set.")
            topo_order = self.dependency_graph.topological_order

        depth_map = self._compute_depth(topo_order)
        priorities: Dict[str, int] = {}

        for goal_id in topo_order:
            if goal_id in self.manual_overrides:
                priorities[goal_id] = self.manual_overrides[goal_id]
            else:
                priorities[goal_id] = depth_map.get(goal_id, 0)

        return priorities

    def reorder_queue(self, current_queue: List[str], resolved_goals: set) -> List[str]:
        """
        Reorder the goal queue dynamically when dependencies resolve.
        Goals whose dependencies are all resolved are moved to the front,
        sorted by priority (higher priority first).

        Args:
            current_queue: Current list of goal IDs in the queue.
            resolved_goals: Set of goal IDs that have been resolved (dependencies met).

        Returns:
            Reordered list of goal IDs.
        """
        # Get topological order to compute priorities
        if self.dependency_graph is not None:
            topo_order = self.dependency_graph.topological_order
        else:
            topo_order = current_queue

        priorities = self.assign_priorities(topo_order)

        # Separate goals that are ready (all dependencies resolved) vs not ready
        ready_goals = []
        not_ready_goals = []

        # We need to know dependencies for each goal to check if resolved
        # For simplicity, assume resolved_goals contains all goals whose prerequisites are met.
        # If a goal is in resolved_goals, it's ready.
        for goal_id in current_queue:
            if goal_id in resolved_goals:
                ready_goals.append(goal_id)
            else:
                not_ready_goals.append(goal_id)

        # Sort ready goals by priority descending (higher priority first)
        ready_goals.sort(key=lambda g: priorities.get(g, 0), reverse=True)

        # Return ready goals first, then the rest (maintaining original order for not ready)
        return ready_goals + not_ready_goals

    def update_config(self, config_path: str) -> None:
        """Update the configuration file path and reload overrides."""
        self.config_path = config_path
        self._load_config()

    def set_manual_override(self, goal_id: str, priority: int) -> None:
        """Set a manual priority override for a specific goal."""
        self.manual_overrides[goal_id] = priority

    def clear_manual_overrides(self) -> None:
        """Clear all manual priority overrides."""
        self.manual_overrides = {}