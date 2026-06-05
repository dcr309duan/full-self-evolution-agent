"""Coordinated Mutation Plan Module.

This module provides functionality to create and manage coordinated mutation plans
that apply changes to multiple modules in dependency order while ensuring no
circular dependencies exist and providing rollback capabilities.
"""

import copy
from typing import Any, Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field


class CircularDependencyError(Exception):
    """Raised when circular dependencies are detected between modules."""
    pass


@dataclass
class ModuleChange:
    """Represents a change to be applied to a single module."""
    module_name: str
    changes: Dict[str, Any]
    dependencies: List[str] = field(default_factory=list)
    rollback_snapshot: Optional[Dict[str, Any]] = None


@dataclass
class CoordinatedMutationPlan:
    """A coordinated mutation plan that applies changes in dependency order.
    
    Attributes:
        module_changes: List of ModuleChange objects representing changes to apply.
        ordered_changes: Changes sorted by dependency order (topological sort).
        has_circular_dependency: Whether circular dependencies were detected.
    """
    module_changes: List[ModuleChange] = field(default_factory=list)
    ordered_changes: List[ModuleChange] = field(default_factory=list)
    has_circular_dependency: bool = False
    
    def __post_init__(self):
        """Validate and order changes after initialization."""
        if self.module_changes:
            self._validate_and_order()
    
    def _build_dependency_graph(self) -> Dict[str, Set[str]]:
        """Build a dependency graph from the module changes.
        
        Returns:
            Dictionary mapping module names to sets of their dependencies.
        """
        graph: Dict[str, Set[str]] = {}
        for change in self.module_changes:
            graph[change.module_name] = set(change.dependencies)
        return graph
    
    def _topological_sort(self) -> List[str]:
        """Perform topological sort on the dependency graph.
        
        Returns:
            List of module names in dependency order.
            
        Raises:
            CircularDependencyError: If circular dependencies are detected.
        """
        graph = self._build_dependency_graph()
        in_degree: Dict[str, int] = {node: 0 for node in graph}
        
        # Calculate in-degrees
        for node in graph:
            for dep in graph[node]:
                if dep in in_degree:
                    in_degree[dep] += 1
        
        # Start with nodes that have no dependencies
        queue = [node for node, degree in in_degree.items() if degree == 0]
        sorted_order = []
        
        while queue:
            node = queue.pop(0)
            sorted_order.append(node)
            
            # Reduce in-degree of dependent nodes
            for other_node in graph:
                if node in graph[other_node]:
                    in_degree[other_node] -= 1
                    if in_degree[other_node] == 0:
                        queue.append(other_node)
        
        # Check for circular dependencies
        if len(sorted_order) != len(graph):
            self.has_circular_dependency = True
            raise CircularDependencyError(
                f"Circular dependency detected. "
                f"Sorted {len(sorted_order)} of {len(graph)} modules."
            )
        
        return sorted_order
    
    def _validate_and_order(self) -> None:
        """Validate dependencies and order changes topologically."""
        sorted_modules = self._topological_sort()
        
        # Create lookup for module changes
        change_map = {c.module_name: c for c in self.module_changes}
        
        # Order changes according to topological sort
        self.ordered_changes = [
            change_map[module_name] for module_name in sorted_modules
            if module_name in change_map
        ]
    
    def add_module_change(self, module_change: ModuleChange) -> None:
        """Add a module change to the plan and re-validate.
        
        Args:
            module_change: The ModuleChange to add.
            
        Raises:
            CircularDependencyError: If adding this change creates a circular dependency.
        """
        self.module_changes.append(module_change)
        self._validate_and_order()
    
    def take_snapshots(self, module_states: Dict[str, Dict[str, Any]]) -> None:
        """Take rollback snapshots for all modules in the plan.
        
        Args:
            module_states: Dictionary mapping module names to their current state.
        """
        for change in self.module_changes:
            if change.module_name in module_states:
                change.rollback_snapshot = copy.deepcopy(
                    module_states[change.module_name]
                )
    
    def get_rollback_plan(self) -> List[ModuleChange]:
        """Get changes in reverse order for rollback.
        
        Returns:
            List of ModuleChange objects in reverse dependency order.
        """
        return list(reversed(self.ordered_changes))
    
    def get_execution_order(self) -> List[str]:
        """Get the order in which modules should be modified.
        
        Returns:
            List of module names in execution order.
        """
        return [change.module_name for change in self.ordered_changes]
    
    def validate_dependencies(self, available_modules: Set[str]) -> bool:
        """Validate that all dependencies are available.
        
        Args:
            available_modules: Set of available module names.
            
        Returns:
            True if all dependencies are available, False otherwise.
        """
        for change in self.module_changes:
            for dep in change.dependencies:
                if dep not in available_modules:
                    return False
        return True
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert the plan to a dictionary for serialization.
        
        Returns:
            Dictionary representation of the plan.
        """
        return {
            "module_changes": [
                {
                    "module_name": c.module_name,
                    "changes": c.changes,
                    "dependencies": c.dependencies,
                    "has_rollback": c.rollback_snapshot is not None,
                }
                for c in self.module_changes
            ],
            "execution_order": self.get_execution_order(),
            "has_circular_dependency": self.has_circular_dependency,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CoordinatedMutationPlan":
        """Create a plan from a dictionary.
        
        Args:
            data: Dictionary containing plan data.
            
        Returns:
            New CoordinatedMutationPlan instance.
        """
        module_changes = [
            ModuleChange(
                module_name=item["module_name"],
                changes=item["changes"],
                dependencies=item.get("dependencies", []),
            )
            for item in data["module_changes"]
        ]
        return cls(module_changes=module_changes)


def create_coordinated_mutation_plan(
    module_changes: List[ModuleChange],
) -> CoordinatedMutationPlan:
    """Create a coordinated mutation plan from a list of module changes.
    
    This is a convenience function that validates dependencies and creates
    an ordered plan.
    
    Args:
        module_changes: List of ModuleChange objects.
        
    Returns:
        CoordinatedMutationPlan with validated and ordered changes.
        
    Raises:
        CircularDependencyError: If circular dependencies are detected.
    """
    plan = CoordinatedMutationPlan(module_changes=module_changes)
    return plan


def validate_no_circular_dependencies(
    module_changes: List[ModuleChange],
) -> bool:
    """Validate that no circular dependencies exist in the changes.
    
    Args:
        module_changes: List of ModuleChange objects to validate.
        
    Returns:
        True if no circular dependencies, False otherwise.
    """
    try:
        plan = CoordinatedMutationPlan(module_changes=module_changes)
        return not plan.has_circular_dependency
    except CircularDependencyError:
        return False