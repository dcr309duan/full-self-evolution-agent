import json
import os
import datetime
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class Mutation:
    """Represents a single mutation to apply to a module."""
    module_name: str
    mutation_type: str
    payload: Dict[str, Any]
    rollback_payload: Dict[str, Any]


@dataclass
class Plan:
    """A coordinated multi-module mutation plan with rollback support."""
    modules_to_change: List[str]
    mutations: List[Mutation]
    expected_fitness_gain: float
    rollback_plan: List[Dict[str, Any]] = field(default_factory=list)


class CoordinatedMutationPlanner:
    """
    Generates coordinated multi-module mutation plans to break Nash equilibria.
    Reads equilibrium state from JSON file and outputs plan as JSON.
    """

    def __init__(self, equilibrium_file: str = "equilibrium_state.json"):
        self.equilibrium_file = equilibrium_file
        self.module_registry: Dict[str, Any] = {}
        self.dependency_graph: Dict[str, List[str]] = {}
        self.interaction_frequencies: Dict[str, int] = {}
        self.recent_successes: Dict[str, float] = {}

    def load_equilibrium_state(self) -> Optional[Dict[str, Any]]:
        """Read equilibrium state from JSON file."""
        if not os.path.exists(self.equilibrium_file):
            return None
        try:
            with open(self.equilibrium_file, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return None

    def build_dependency_graph(self, equilibrium_state: Dict[str, Any]) -> None:
        """Build dependency graph from equilibrium state."""
        modules = equilibrium_state.get('modules', [])
        for module in modules:
            module_name = module.get('name', '')
            deps = module.get('dependencies', [])
            self.dependency_graph[module_name] = deps
            self.module_registry[module_name] = module
            self.interaction_frequencies[module_name] = module.get('interaction_frequency', 0)
            self.recent_successes[module_name] = module.get('recent_success', 1.0)

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

        target_modules = self._select_target_modules(equilibrium_modules)
        if not target_modules:
            return None

        mutations = []
        rollback_plan = []
        expected_gain = 0.0

        if len(target_modules) >= 2:
            donor_module = target_modules[0]
            receiver_module = target_modules[1]

            new_func_name = f"_coordinated_{datetime.datetime.now().strftime('%H%M%S')}"

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
            rollback_plan.append({
                'module': donor_module,
                'action': 'remove_function',
                'function_name': new_func_name
            })

            receiver_mutation = Mutation(
                module_name=receiver_module,
                mutation_type='new_call',
                payload={
                    'target_module': donor_module,
                    'function_name': new_func_name,
                    'call_site': 'init'
                },
                rollback_payload={
                    'target_module': donor_module,
                    'function_name': new_func_name,
                    'action': 'remove_call'
                }
            )
            mutations.append(receiver_mutation)
            rollback_plan.append({
                'module': receiver_module,
                'action': 'remove_call',
                'target_module': donor_module,
                'function_name': new_func_name
            })

            if len(target_modules) >= 3:
                third_module = target_modules[2]
                third_mutation = Mutation(
                    module_name=third_module,
                    mutation_type='modify_parameter',
                    payload={
                        'parameter_name': 'threshold',
                        'new_value': 0.5
                    },
                    rollback_payload={
                        'parameter_name': 'threshold',
                        'old_value': 0.0
                    }
                )
                mutations.append(third_mutation)
                rollback_plan.append({
                    'module': third_module,
                    'action': 'restore_parameter',
                    'parameter_name': 'threshold'
                })

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
        """Select 2-3 modules from candidates using heuristic: highest interaction frequency and lowest recent success."""
        if not candidates:
            return []

        scored_modules = []
        for module in candidates:
            freq = self.interaction_frequencies.get(module, 0)
            success = self.recent_successes.get(module, 1.0)
            score = freq * (1.0 - success)
            scored_modules.append((score, module))

        scored_modules.sort(key=lambda x: x[0], reverse=True)

        selected = []
        for score, module in scored_modules:
            if len(selected) >= 3:
                break
            if module not in selected:
                selected.append(module)

        if len(selected) < 2:
            return candidates[:min(3, len(candidates))]

        return selected

    def _estimate_fitness_gain(
        self,
        modules: List[str],
        equilibrium_state: Dict[str, Any]
    ) -> float:
        """Estimate the expected fitness gain from breaking the equilibrium."""
        base_fitness = equilibrium_state.get('fitness', 0.0)
        return base_fitness * 0.1 + 0.05 * len(modules)

    def generate_plan(self) -> Optional[Dict[str, Any]]:
        """Main method: load equilibrium state, generate plan, return as dict."""
        equilibrium_state = self.load_equilibrium_state()
        if equilibrium_state is None:
            return None

        self.build_dependency_graph(equilibrium_state)

        equilibrium_modules = equilibrium_state.get('equilibrium_modules', [])
        if not equilibrium_modules:
            equilibrium_modules = list(self.module_registry.keys())

        plan = self.plan_break_equilibrium(equilibrium_modules, equilibrium_state)
        if plan is None:
            return None

        return {
            'timestamp': datetime.datetime.now().isoformat(),
            'modules_to_change': plan.modules_to_change,
            'mutations': [
                {
                    'module_name': m.module_name,
                    'mutation_type': m.mutation_type,
                    'payload': m.payload,
                    'rollback_payload': m.rollback_payload
                }
                for m in plan.mutations
            ],
            'expected_fitness_gain': plan.expected_fitness_gain,
            'rollback_plan': plan.rollback_plan
        }

    def save_plan(self, plan_dict: Dict[str, Any], output_file: str = "mutation_plan.json") -> None:
        """Save the plan as a JSON file."""
        with open(output_file, 'w') as f:
            json.dump(plan_dict, f, indent=2)

    def run(self, output_file: str = "mutation_plan.json") -> bool:
        """Execute the full workflow: load, plan, save."""
        plan_dict = self.generate_plan()
        if plan_dict is None:
            return False
        self.save_plan(plan_dict, output_file)
        return True

    def plan_coordinated_mutations(self, equilibrium_state: Dict[str, Any]) -> List[tuple]:
        """
        Plan coordinated mutations based on equilibrium state.
        Returns list of tuples (module_name, mutation_type, params).
        """
        self.build_dependency_graph(equilibrium_state)
        equilibrium_modules = equilibrium_state.get('equilibrium_modules', [])
        if not equilibrium_modules:
            equilibrium_modules = list(self.module_registry.keys())

        target_modules = self._select_target_modules(equilibrium_modules)
        if not target_modules or len(target_modules) < 2:
            return []

        coordinated_mutations = []

        donor_module = target_modules[0]
        receiver_module = target_modules[1]

        coordinated_mutations.append((
            donor_module,
            'new_function',
            {
                'function_name': f"_coordinated_{datetime.datetime.now().strftime('%H%M%S')}",
                'function_body': 'return None',
                'export': True
            }
        ))

        coordinated_mutations.append((
            receiver_module,
            'new_call',
            {
                'target_module': donor_module,
                'function_name': f"_coordinated_{datetime.datetime.now().strftime('%H%M%S')}",
                'call_site': 'init'
            }
        ))

        if len(target_modules) >= 3:
            third_module = target_modules[2]
            coordinated_mutations.append((
                third_module,
                'modify_parameter',
                {
                    'parameter_name': 'threshold',
                    'new_value': 0.5
                }
            ))

        return coordinated_mutations

    def create_coordinated_mutation_plan(
        self,
        modules_to_modify: List[str],
        equilibrium_state: Dict[str, Any]
    ) -> Optional[Plan]:
        """
        Create a coordinated mutation plan that changes all modules in a consistent way.
        Validates that combined changes are non-conflicting and produces a rollback plan.
        """
        if not modules_to_modify or len(modules_to_modify) < 2:
            return None

        self.build_dependency_graph(equilibrium_state)

        # Validate that modules exist in registry
        for module in modules_to_modify:
            if module not in self.module_registry:
                return None

        # Check for conflicts in dependency graph
        if not self._validate_non_conflicting(modules_to_modify):
            return None

        mutations = []
        rollback_plan = []
        expected_gain = 0.0

        # Generate consistent mutations across all modules
        base_function_name = f"_coordinated_{datetime.datetime.now().strftime('%H%M%S')}"

        for i, module in enumerate(modules_to_modify):
            if i == 0:
                # First module gets a new function
                mutation = Mutation(
                    module_name=module,
                    mutation_type='new_function',
                    payload={
                        'function_name': base_function_name,
                        'function_body': f'return {i}',
                        'export': True
                    },
                    rollback_payload={
                        'function_name': base_function_name,
                        'action': 'remove'
                    }
                )
                rollback_plan.append({
                    'module': module,
                    'action': 'remove_function',
                    'function_name': base_function_name
                })
            elif i == 1:
                # Second module calls the first module's function
                mutation = Mutation(
                    module_name=module,
                    mutation_type='new_call',
                    payload={
                        'target_module': modules_to_modify[0],
                        'function_name': base_function_name,
                        'call_site': 'init'
                    },
                    rollback_payload={
                        'target_module': modules_to_modify[0],
                        'function_name': base_function_name,
                        'action': 'remove_call'
                    }
                )
                rollback_plan.append({
                    'module': module,
                    'action': 'remove_call',
                    'target_module': modules_to_modify[0],
                    'function_name': base_function_name
                })
            else:
                # Additional modules get parameter modifications
                mutation = Mutation(
                    module_name=module,
                    mutation_type='modify_parameter',
                    payload={
                        'parameter_name': f'coordinated_param_{i}',
                        'new_value': i * 0.1
                    },
                    rollback_payload={
                        'parameter_name': f'coordinated_param_{i}',
                        'old_value': 0.0
                    }
                )
                rollback_plan.append({
                    'module': module,
                    'action': 'restore_parameter',
                    'parameter_name': f'coordinated_param_{i}'
                })

            mutations.append(mutation)

        expected_gain = self._estimate_fitness_gain(modules_to_modify, equilibrium_state)

        return Plan(
            modules_to_change=modules_to_modify,
            mutations=mutations,
            expected_fitness_gain=expected_gain,
            rollback_plan=rollback_plan
        )

    def _validate_non_conflicting(self, modules: List[str]) -> bool:
        """
        Validate that the combined changes across modules are non-conflicting.
        Checks for circular dependencies and overlapping modifications.
        """
        # Check for circular dependencies
        for module in modules:
            visited = set()
            stack = [module]
            while stack:
                current = stack.pop()
                if current in visited:
                    return False
                visited.add(current)
                deps = self.dependency_graph.get(current, [])
                for dep in deps:
                    if dep in modules and dep not in visited:
                        stack.append(dep)

        # Check that no module is both a donor and receiver in conflicting ways
        for i, mod1 in enumerate(modules):
            for j, mod2 in enumerate(modules):
                if i != j:
                    deps1 = self.dependency_graph.get(mod1, [])
                    deps2 = self.dependency_graph.get(mod2, [])
                    if mod2 in deps1 and mod1 in deps2:
                        return False

        return True

    def generate_rollback_plan(self, plan: Plan) -> List[Dict[str, Any]]:
        """
        Generate a comprehensive rollback plan for the coordinated mutation.
        Returns ordered list of rollback actions.
        """
        rollback_actions = []

        # Reverse the order of mutations for safe rollback
        for mutation in reversed(plan.mutations):
            rollback_action = {
                'module': mutation.module_name,
                'action': 'rollback',
                'mutation_type': mutation.mutation_type,
                'rollback_payload': mutation.rollback_payload
            }
            rollback_actions.append(rollback_action)

        return rollback_actions

    def plan_with_validation(
        self,
        modules_to_modify: List[str],
        equilibrium_state: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Full workflow: create plan, validate, generate rollback, return as dict.
        """
        plan = self.create_coordinated_mutation_plan(modules_to_modify, equilibrium_state)
        if plan is None:
            return None

        # Generate comprehensive rollback plan
        plan.rollback_plan = self.generate_rollback_plan(plan)

        return {
            'timestamp': datetime.datetime.now().isoformat(),
            'modules_to_change': plan.modules_to_change,
            'mutations': [
                {
                    'module_name': m.module_name,
                    'mutation_type': m.mutation_type,
                    'payload': m.payload,
                    'rollback_payload': m.rollback_payload
                }
                for m in plan.mutations
            ],
            'expected_fitness_gain': plan.expected_fitness_gain,
            'rollback_plan': plan.rollback_plan,
            'validation_status': 'validated'
        }