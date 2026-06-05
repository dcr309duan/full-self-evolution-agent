from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple
import copy
import random


@dataclass
class Mutation:
    """Represents a single mutation to apply to a module."""
    module_name: str
    mutation_type: str  # e.g., 'new_function', 'new_call', 'refactor'
    payload: Dict[str, Any]
    rollback_payload: Dict[str, Any]


@dataclass
class Plan:
    """A coordinated multi-module mutation plan with rollback support."""
    modules_to_change: List[str]
    mutations: List[Mutation]
    expected_fitness_gain: float
    rollback_plan: List[Callable[[], None]] = field(default_factory=list)


class CoordinatedMutationPlanner:
    """
    Generates coordinated multi-module mutation plans to break Nash equilibria.
    Each plan ensures individual mutations are neutral but collectively beneficial.
    """

    def __init__(self, module_registry: Dict[str, Any], dependency_graph: Dict[str, List[str]]):
        self.module_registry = module_registry
        self.dependency_graph = dependency_graph

    def plan_break_equilibrium(
        self,
        equilibrium_modules: List[str],
        equilibrium_state: Dict[str, Any]
    ) -> Optional[Plan]:
        """
        Given a set of modules in equilibrium, generate a coordinated mutation plan.
        Returns None if no viable plan can be formed.
        """
        if len(equilibrium_modules) < 2:
            return None

        # Select 2-3 modules that are interdependent
        target_modules = self._select_target_modules(equilibrium_modules)
        if not target_modules:
            return None

        mutations = []
        rollback_plan = []
        expected_gain = 0.0

        # Example: Create a new function in module A and a call to it in module B
        if len(target_modules) >= 2:
            donor_module = target_modules[0]
            receiver_module = target_modules[1]

            # Generate a new function name
            new_func_name = f"_coordinated_{random.randint(1000, 9999)}"

            # Mutation for donor: export a new function
            donor_mutation = Mutation(
                module_name=donor_module,
                mutation_type='new_function',
                payload={
                    'function_name': new_func_name,
                    'function_body': 'return None',
                    'export': True
                },
                rollback_payload={
                    'function_name': new_func_name,
                    'action': 'remove'
                }
            )
            mutations.append(donor_mutation)
            rollback_plan.append(
                lambda m=donor_mutation: self._apply_rollback(m)
            )

            # Mutation for receiver: call the new function
            receiver_mutation = Mutation(
                module_name=receiver_module,
                mutation_type='new_call',
                payload={
                    'target_module': donor_module,
                    'function_name': new_func_name,
                    'call_site': 'init'  # or some strategic location
                },
                rollback_payload={
                    'target_module': donor_module,
                    'function_name': new_func_name,
                    'action': 'remove_call'
                }
            )
            mutations.append(receiver_mutation)
            rollback_plan.append(
                lambda m=receiver_mutation: self._apply_rollback(m)
            )

            # Estimate fitness gain (simplified heuristic)
            expected_gain = self._estimate_fitness_gain(
                target_modules, equilibrium_state
            )

        return Plan(
            modules_to_change=target_modules,
            mutations=mutations,
            expected_fitness_gain=expected_gain,
            rollback_plan=rollback_plan
        )

    def _select_target_modules(self, candidates: List[str]) -> List[str]:
        """
        Select 2-3 modules from candidates that have dependency relationships.
        """
        if not candidates:
            return []

        # Prefer modules that depend on each other
        for module in candidates:
            deps = self.dependency_graph.get(module, [])
            for dep in deps:
                if dep in candidates and dep != module:
                    return [module, dep]

        # Fallback: pick first 2-3
        return candidates[:min(3, len(candidates))]

    def _estimate_fitness_gain(
        self,
        modules: List[str],
        equilibrium_state: Dict[str, Any]
    ) -> float:
        """
        Estimate the expected fitness gain from breaking the equilibrium.
        Uses a simple heuristic based on module centrality and current fitness.
        """
        base_fitness = equilibrium_state.get('fitness', 0.0)
        # Breaking equilibrium typically yields diminishing returns
        # but can unlock new cooperative behaviors
        return base_fitness * 0.1 + 0.05 * len(modules)

    def _apply_rollback(self, mutation: Mutation) -> None:
        """
        Apply the rollback for a given mutation.
        This is a placeholder; actual implementation depends on module system.
        """
        module = self.module_registry.get(mutation.module_name)
        if module is None:
            return

        action = mutation.rollback_payload.get('action')
        if action == 'remove':
            func_name = mutation.rollback_payload.get('function_name')
            if hasattr(module, func_name):
                delattr(module, func_name)
        elif action == 'remove_call':
            # Placeholder for call removal logic
            pass

    def execute_plan(self, plan: Plan) -> bool:
        """
        Execute a coordinated mutation plan atomically.
        Returns True if successful, False if rollback was triggered.
        """
        try:
            for mutation in plan.mutations:
                self._apply_mutation(mutation)
            return True
        except Exception as e:
            # Rollback all mutations
            for rollback_fn in plan.rollback_plan:
                try:
                    rollback_fn()
                except Exception:
                    pass
            return False

    def _apply_mutation(self, mutation: Mutation) -> None:
        """
        Apply a single mutation to the target module.
        This is a placeholder; actual implementation depends on module system.
        """
        module = self.module_registry.get(mutation.module_name)
        if module is None:
            raise ValueError(f"Module {mutation.module_name} not found")

        if mutation.mutation_type == 'new_function':
            func_name = mutation.payload['function_name']
            func_body = mutation.payload.get('function_body', 'return None')
            # Create a new function dynamically
            exec(f"def {func_name}():\n    {func_body}", module.__dict__)
        elif mutation.mutation_type == 'new_call':
            # Placeholder for adding a call to another module's function
            pass