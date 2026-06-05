"""Coordinated Mutation Plan for multi-module changes.

This module provides the CoordinatedMutationPlan class which orchestrates
coordinated changes across multiple modules to move the system away from
equilibrium states while ensuring consistency.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


class ChangeType(Enum):
    """Types of changes that can be applied to a module."""
    ADD_FUNCTION = "add_function"
    MODIFY_FUNCTION = "modify_function"
    REMOVE_FUNCTION = "remove_function"
    ADD_CLASS = "add_class"
    MODIFY_CLASS = "modify_class"
    ADD_DEPENDENCY = "add_dependency"
    REMOVE_DEPENDENCY = "remove_dependency"
    MODIFY_INTERFACE = "modify_interface"
    ADD_CONSTANT = "add_constant"
    MODIFY_CONSTANT = "modify_constant"


@dataclass
class ModuleChange:
    """Represents a single change to a module."""
    module_name: str
    change_type: ChangeType
    target: str  # The specific function/class/constant name
    description: str
    dependencies: List[str] = field(default_factory=list)  # Modules this change depends on
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate the change after initialization."""
        if not self.module_name:
            raise ValueError("module_name cannot be empty")
        if not self.target:
            raise ValueError("target cannot be empty")
        if not self.description:
            raise ValueError("description cannot be empty")


@dataclass
class MutationPlan:
    """A complete coordinated mutation plan across multiple modules."""
    changes: List[ModuleChange] = field(default_factory=list)
    description: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def add_change(self, change: ModuleChange) -> None:
        """Add a change to the plan."""
        self.changes.append(change)

    def get_modules_affected(self) -> Set[str]:
        """Get the set of all modules affected by this plan."""
        return {change.module_name for change in self.changes}

    def get_change_count(self) -> int:
        """Get the total number of changes in the plan."""
        return len(self.changes)


class CoordinatedMutationPlan:
    """Generates and validates coordinated multi-module mutation plans.

    This class takes a list of modules to modify and generates a coordinated
    set of changes that move the system away from equilibrium while ensuring
    no circular dependencies are introduced.
    """

    def __init__(self, modules_to_modify: List[str]) -> None:
        """Initialize the coordinated mutation plan.

        Args:
            modules_to_modify: List of module names to include in the plan.

        Raises:
            ValueError: If modules_to_modify is empty or contains duplicates.
        """
        if not modules_to_modify:
            raise ValueError("At least one module must be specified for modification")

        if len(modules_to_modify) != len(set(modules_to_modify)):
            raise ValueError("Duplicate module names are not allowed")

        self._modules_to_modify: List[str] = modules_to_modify
        self._changes: List[ModuleChange] = []
        self._dependency_graph: Dict[str, Set[str]] = {}
        self._validated: bool = False

        # Initialize dependency graph for all modules
        for module in modules_to_modify:
            self._dependency_graph[module] = set()

        logger.info(f"Initialized CoordinatedMutationPlan for modules: {modules_to_modify}")

    def add_change(self, change: ModuleChange) -> None:
        """Add a change to the mutation plan.

        Args:
            change: The ModuleChange to add.

        Raises:
            ValueError: If the change's module is not in the plan's scope.
        """
        if change.module_name not in self._modules_to_modify:
            raise ValueError(
                f"Module '{change.module_name}' is not in the plan's scope. "
                f"Scope includes: {self._modules_to_modify}"
            )

        self._changes.append(change)
        self._validated = False
        logger.debug(f"Added change: {change.change_type.value} on {change.module_name}.{change.target}")

    def add_dependency(self, from_module: str, to_module: str) -> None:
        """Add a dependency between two modules in the plan.

        Args:
            from_module: The module that depends on to_module.
            to_module: The module that from_module depends on.

        Raises:
            ValueError: If either module is not in the plan's scope.
        """
        if from_module not in self._modules_to_modify:
            raise ValueError(f"Module '{from_module}' is not in the plan's scope")
        if to_module not in self._modules_to_modify:
            raise ValueError(f"Module '{to_module}' is not in the plan's scope")

        self._dependency_graph[from_module].add(to_module)
        self._validated = False
        logger.debug(f"Added dependency: {from_module} -> {to_module}")

    def generate_equilibrium_breaking_plan(self) -> MutationPlan:
        """Generate a coordinated plan that breaks the current equilibrium.

        This method creates changes that introduce new interfaces, modify
        existing ones, and add dependencies to move the system away from
        a stable equilibrium state.

        Returns:
            A MutationPlan containing the coordinated changes.

        Raises:
            RuntimeError: If the generated plan has circular dependencies.
        """
        plan = MutationPlan(
            description="Coordinated mutation to break system equilibrium"
        )

        # Phase 1: Add new interfaces to create asymmetry
        for i, module in enumerate(self._modules_to_modify):
            change = ModuleChange(
                module_name=module,
                change_type=ChangeType.ADD_FUNCTION,
                target=f"mutation_interface_{i}",
                description=f"Add new interface to break equilibrium in {module}",
                dependencies=[]
            )
            plan.add_change(change)
            self.add_change(change)

        # Phase 2: Modify existing interfaces to create coupling
        for i, module in enumerate(self._modules_to_modify):
            next_module = self._modules_to_modify[(i + 1) % len(self._modules_to_modify)]
            change = ModuleChange(
                module_name=module,
                change_type=ChangeType.MODIFY_INTERFACE,
                target="process",
                description=f"Modify interface to depend on {next_module}",
                dependencies=[next_module]
            )
            plan.add_change(change)
            self.add_change(change)
            self.add_dependency(module, next_module)

        # Phase 3: Add constants to create parameter diversity
        for i, module in enumerate(self._modules_to_modify):
            change = ModuleChange(
                module_name=module,
                change_type=ChangeType.ADD_CONSTANT,
                target=f"EQUILIBRIUM_BREAKER_{i}",
                description=f"Add diversity constant to {module}",
                dependencies=[]
            )
            plan.add_change(change)
            self.add_change(change)

        # Validate the generated plan
        if not self.validate():
            raise RuntimeError("Generated plan has circular dependencies")

        logger.info(f"Generated equilibrium-breaking plan with {len(plan.changes)} changes")
        return plan

    def validate(self) -> bool:
        """Validate that the mutation plan has no circular dependencies.

        Uses topological sort to detect cycles in the dependency graph.

        Returns:
            True if the plan is valid (no circular dependencies), False otherwise.
        """
        if self._validated:
            return True

        # Build the full dependency graph from all changes
        full_graph: Dict[str, Set[str]] = {}
        for module in self._modules_to_modify:
            full_graph[module] = set(self._dependency_graph.get(module, set()))

        # Add dependencies from changes
        for change in self._changes:
            for dep in change.dependencies:
                if dep in self._modules_to_modify:
                    full_graph[change.module_name].add(dep)

        # Perform topological sort (Kahn's algorithm)
        in_degree: Dict[str, int] = {module: 0 for module in full_graph}
        for module in full_graph:
            for dependency in full_graph[module]:
                if dependency in in_degree:
                    in_degree[dependency] += 1

        queue: List[str] = [
            module for module, degree in in_degree.items() if degree == 0
        ]
        sorted_count = 0

        while queue:
            module = queue.pop(0)
            sorted_count += 1

            for dependent in full_graph:
                if module in full_graph[dependent]:
                    in_degree[dependent] -= 1
                    if in_degree[dependent] == 0:
                        queue.append(dependent)

        self._validated = (sorted_count == len(self._modules_to_modify))

        if self._validated:
            logger.info("Mutation plan validation passed - no circular dependencies")
        else:
            logger.warning(
                f"Mutation plan validation failed - circular dependencies detected "
                f"(sorted {sorted_count} of {len(self._modules_to_modify)} modules)"
            )

        return self._validated

    def get_changes(self) -> List[ModuleChange]:
        """Get all changes in the plan.

        Returns:
            List of ModuleChange objects.
        """
        return list(self._changes)

    def get_modules(self) -> List[str]:
        """Get the list of modules in the plan.

        Returns:
            List of module names.
        """
        return list(self._modules_to_modify)

    def get_dependency_graph(self) -> Dict[str, Set[str]]:
        """Get the dependency graph of the plan.

        Returns:
            Dictionary mapping module names to sets of their dependencies.
        """
        return {k: set(v) for k, v in self._dependency_graph.items()}

    def clear(self) -> None:
        """Clear all changes and reset the plan."""
        self._changes.clear()
        self._dependency_graph = {module: set() for module in self._modules_to_modify}
        self._validated = False
        logger.info("Cleared all changes from the mutation plan")

    def __len__(self) -> int:
        """Get the number of changes in the plan."""
        return len(self._changes)

    def __repr__(self) -> str:
        """Get a string representation of the plan."""
        return (
            f"CoordinatedMutationPlan("
            f"modules={self._modules_to_modify}, "
            f"changes={len(self._changes)}, "
            f"validated={self._validated})"
        )