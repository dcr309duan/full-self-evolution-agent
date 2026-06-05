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

    def execute_coordinated_mutation(self, module_scores: Dict[str, float]) -> bool:
        """Execute coordinated mutation across 2-3 modules atomically.

        Given module names and their current scores, this method generates
        simultaneous changes that improve all modules' scores. Changes are
        applied atomically with rollback if any single change fails.

        Args:
            module_scores: Dictionary mapping module names to their current scores.

        Returns:
            True if all changes were applied successfully, False if rollback occurred.

        Raises:
            ValueError: If module_scores is empty or contains modules not in the plan.
        """
        if not module_scores:
            raise ValueError("module_scores cannot be empty")

        # Validate that all modules in module_scores are in the plan's scope
        for module_name in module_scores:
            if module_name not in self._modules_to_modify:
                raise ValueError(
                    f"Module '{module_name}' is not in the plan's scope. "
                    f"Scope includes: {self._modules_to_modify}"
                )

        # Validate that we have 2-3 modules
        if len(module_scores) < 2 or len(module_scores) > 3:
            raise ValueError(
                f"Coordinated mutation requires 2-3 modules, got {len(module_scores)}"
            )

        logger.info(
            f"Starting coordinated mutation for modules: {list(module_scores.keys())} "
            f"with scores: {module_scores}"
        )

        # Generate a plan that improves all modules' scores
        plan = self._generate_improvement_plan(module_scores)

        # Apply changes atomically with rollback
        applied_changes: List[ModuleChange] = []
        try:
            for change in plan.changes:
                # Simulate applying the change (in real implementation, this would
                # modify the actual module)
                success = self._apply_single_change(change, module_scores)
                if not success:
                    logger.error(
                        f"Failed to apply change: {change.change_type.value} "
                        f"on {change.module_name}.{change.target}"
                    )
                    # Rollback all previously applied changes
                    self._rollback_changes(applied_changes, module_scores)
                    return False
                applied_changes.append(change)

            # Verify that all modules' scores improved
            for module_name, original_score in module_scores.items():
                new_score = self._get_module_score(module_name)
                if new_score <= original_score:
                    logger.warning(
                        f"Module '{module_name}' score did not improve: "
                        f"{original_score} -> {new_score}"
                    )
                    # Rollback all changes
                    self._rollback_changes(applied_changes, module_scores)
                    return False

            logger.info(
                f"Successfully applied {len(applied_changes)} coordinated changes"
            )
            return True

        except Exception as e:
            logger.error(f"Error during coordinated mutation: {e}")
            self._rollback_changes(applied_changes, module_scores)
            return False

    def _generate_improvement_plan(
        self, module_scores: Dict[str, float]
    ) -> MutationPlan:
        """Generate a mutation plan that improves all modules' scores.

        Args:
            module_scores: Dictionary mapping module names to their current scores.

        Returns:
            A MutationPlan containing changes that improve all modules' scores.
        """
        plan = MutationPlan(
            description="Coordinated mutation to improve all module scores"
        )

        module_names = list(module_scores.keys())

        # Generate changes that create mutual dependencies and improvements
        for i, module in enumerate(module_names):
            # Add a new function that improves the module's score
            change = ModuleChange(
                module_name=module,
                change_type=ChangeType.ADD_FUNCTION,
                target=f"improvement_function_{i}",
                description=f"Add improvement function to increase score of {module}",
                dependencies=[]
            )
            plan.add_change(change)
            self.add_change(change)

            # Modify an existing interface to create beneficial coupling
            next_module = module_names[(i + 1) % len(module_names)]
            change = ModuleChange(
                module_name=module,
                change_type=ChangeType.MODIFY_INTERFACE,
                target="process",
                description=f"Modify interface to improve coupling with {next_module}",
                dependencies=[next_module]
            )
            plan.add_change(change)
            self.add_change(change)
            self.add_dependency(module, next_module)

            # Add a constant that optimizes the module's behavior
            change = ModuleChange(
                module_name=module,
                change_type=ChangeType.ADD_CONSTANT,
                target=f"OPTIMIZATION_CONSTANT_{i}",
                description=f"Add optimization constant to improve {module} score",
                dependencies=[]
            )
            plan.add_change(change)
            self.add_change(change)

        # Validate the plan
        if not self.validate():
            raise RuntimeError("Generated improvement plan has circular dependencies")

        return plan

    def _apply_single_change(
        self, change: ModuleChange, module_scores: Dict[str, float]
    ) -> bool:
        """Apply a single change to a module.

        In a real implementation, this would modify the actual module code.
        Here we simulate the application and return success.

        Args:
            change: The ModuleChange to apply.
            module_scores: Dictionary of current module scores.

        Returns:
            True if the change was applied successfully, False otherwise.
        """
        try:
            # Simulate applying the change
            logger.debug(
                f"Applying change: {change.change_type.value} "
                f"on {change.module_name}.{change.target}"
            )

            # In a real implementation, this would:
            # 1. Parse the module's source code
            # 2. Apply the modification
            # 3. Verify the module still compiles/runs
            # 4. Return True if successful

            # For simulation, we always return True
            return True

        except Exception as e:
            logger.error(f"Failed to apply change: {e}")
            return False

    def _rollback_changes(
        self, changes: List[ModuleChange], module_scores: Dict[str, float]
    ) -> None:
        """Rollback a list of previously applied changes.

        Args:
            changes: List of ModuleChange objects to rollback.
            module_scores: Dictionary of original module scores to restore.
        """
        if not changes:
            return

        logger.info(f"Rolling back {len(changes)} changes")

        # Rollback in reverse order
        for change in reversed(changes):
            try:
                # In a real implementation, this would:
                # 1. Parse the module's source code
                # 2. Reverse the modification
                # 3. Verify the module is restored to its original state

                logger.debug(
                    f"Rolling back change: {change.change_type.value} "
                    f"on {change.module_name}.{change.target}"
                )
            except Exception as e:
                logger.error(f"Error during rollback of {change}: {e}")

        # Clear the applied changes from the plan
        for change in changes:
            if change in self._changes:
                self._changes.remove(change)

        logger.info("Rollback completed")

    def _get_module_score(self, module_name: str) -> float:
        """Get the current score of a module.

        In a real implementation, this would query the module's actual score.
        Here we simulate by returning a slightly improved score.

        Args:
            module_name: The name of the module.

        Returns:
            The current score of the module.
        """
        # In a real implementation, this would:
        # 1. Query the module's performance metrics
        # 2. Calculate the score based on various factors
        # 3. Return the computed score

        # For simulation, return a default score
        return 1.0