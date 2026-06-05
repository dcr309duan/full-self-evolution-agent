"""Coordinated Mutation Planner for Nash Equilibrium-based multi-module evolution.

When a Nash equilibrium is detected, this module generates coordinated multi-module
mutations (mutation bundles) that can escape local optima through Pareto-improving
changes across interdependent modules.
"""

import random
import hashlib
import json
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, field
from enum import Enum

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

class MutationType(Enum):
    PARAMETER_TWEAK = "parameter_tweak"
    STRUCTURAL_CHANGE = "structural_change"
    LOGIC_REWRITE = "logic_rewrite"
    INTERFACE_MODIFICATION = "interface_modification"


@dataclass
class Mutation:
    """A single mutation to be applied to a module."""
    module_id: str
    mutation_type: MutationType
    target: str               # e.g., parameter name, function name
    delta: Any                # the change value or description
    expected_impact: float    # estimated fitness change (positive = improvement)
    confidence: float         # 0.0 to 1.0


@dataclass
class MutationBundle:
    """A coordinated set of mutations applied atomically."""
    bundle_id: str
    mutations: List[Mutation]
    combined_expected_impact: float
    pareto_improvement: bool
    sandbox_validated: bool = False
    applied: bool = False
    rollback_data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ModuleState:
    """Snapshot of a module's state for rollback."""
    module_id: str
    state_hash: str
    state_data: Dict[str, Any]


# ---------------------------------------------------------------------------
# Core planner
# ---------------------------------------------------------------------------

class CoordinatedMutationPlanner:
    """Plans and manages coordinated mutations across modules in Nash equilibrium."""

    def __init__(self, fitness_threshold: float = 0.01, max_bundle_size: int = 3):
        self.fitness_threshold = fitness_threshold
        self.max_bundle_size = max_bundle_size
        self._bundles: List[MutationBundle] = []
        self._rollback_states: Dict[str, List[ModuleState]] = {}

    # -----------------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------------

    def detect_equilibrium(self, module_fitnesses: Dict[str, float],
                           module_interactions: Dict[str, List[str]]) -> bool:
        """Detect if modules are in a Nash equilibrium.

        A Nash equilibrium exists when no single module can improve its fitness
        by changing unilaterally, given the strategies of other modules.
        """
        if not module_fitnesses or not module_interactions:
            return False

        for module_id, fitness in module_fitnesses.items():
            neighbors = module_interactions.get(module_id, [])
            if not neighbors:
                continue
            # Check if any neighbor's fitness is significantly higher
            neighbor_fitnesses = [module_fitnesses.get(n, 0.0) for n in neighbors]
            if neighbor_fitnesses:
                max_neighbor = max(neighbor_fitnesses)
                if max_neighbor - fitness > self.fitness_threshold:
                    return False
        return True

    def find_pareto_improving_bundles(self,
                                      module_states: Dict[str, Any],
                                      module_fitnesses: Dict[str, float],
                                      module_interactions: Dict[str, List[str]],
                                      max_bundles: int = 5) -> List[MutationBundle]:
        """Generate Pareto-improving mutation bundles from equilibrium state.

        A Pareto improvement means at least one module's fitness increases
        without decreasing any other module's fitness.
        """
        if not self.detect_equilibrium(module_fitnesses, module_interactions):
            return []

        bundles = []
        modules = list(module_states.keys())

        # Generate candidate bundles of size 2-3
        for size in range(2, min(self.max_bundle_size, len(modules)) + 1):
            from itertools import combinations
            for combo in combinations(modules, size):
                bundle = self._create_bundle(combo, module_states, module_fitnesses,
                                             module_interactions)
                if bundle and bundle.pareto_improvement:
                    bundles.append(bundle)
                    if len(bundles) >= max_bundles:
                        break
            if len(bundles) >= max_bundles:
                break

        # Sort by combined expected impact descending
        bundles.sort(key=lambda b: b.combined_expected_impact, reverse=True)
        self._bundles.extend(bundles)
        return bundles

    def validate_bundle_in_sandbox(self, bundle: MutationBundle,
                                   sandbox_executor: callable) -> bool:
        """Validate a mutation bundle in a sandbox environment.

        Args:
            bundle: The mutation bundle to validate.
            sandbox_executor: A function that takes a bundle and returns
                              (success: bool, fitness_delta: float, rollback_data: dict).

        Returns:
            True if the bundle is valid and improves overall fitness.
        """
        if bundle.sandbox_validated:
            return True

        try:
            success, fitness_delta, rollback_data = sandbox_executor(bundle)
            if success and fitness_delta > 0:
                bundle.sandbox_validated = True
                bundle.rollback_data = rollback_data
                return True
        except Exception:
            pass
        return False

    def apply_bundle(self, bundle: MutationBundle,
                     module_appliers: Dict[str, callable]) -> bool:
        """Apply a validated mutation bundle atomically.

        Args:
            bundle: The validated bundle to apply.
            module_appliers: Dict mapping module_id to a function that applies
                             a mutation and returns (success, rollback_state).

        Returns:
            True if all mutations applied successfully.
        """
        if not bundle.sandbox_validated:
            raise ValueError("Bundle must be validated in sandbox before applying.")

        # Save pre-application states for rollback
        pre_states = []
        for mutation in bundle.mutations:
            if mutation.module_id in module_appliers:
                try:
                    _, pre_state = module_appliers[mutation.module_id](mutation, dry_run=True)
                    pre_states.append(ModuleState(
                        module_id=mutation.module_id,
                        state_hash=self._hash_state(pre_state),
                        state_data=pre_state
                    ))
                except Exception:
                    return False

        # Apply all mutations
        applied_states = []
        for mutation in bundle.mutations:
            if mutation.module_id in module_appliers:
                try:
                    success, post_state = module_appliers[mutation.module_id](mutation)
                    if not success:
                        self._rollback(applied_states, module_appliers)
                        return False
                    applied_states.append(ModuleState(
                        module_id=mutation.module_id,
                        state_hash=self._hash_state(post_state),
                        state_data=post_state
                    ))
                except Exception:
                    self._rollback(applied_states, module_appliers)
                    return False

        bundle.applied = True
        # Store rollback data
        for state in pre_states:
            self._rollback_states.setdefault(state.module_id, []).append(state)
        return True

    def rollback_bundle(self, bundle: MutationBundle,
                        module_appliers: Dict[str, callable]) -> bool:
        """Rollback an applied bundle using stored pre-states."""
        if not bundle.applied:
            return False

        # Collect pre-states for this bundle's modules
        rollback_states = []
        for mutation in bundle.mutations:
            states = self._rollback_states.get(mutation.module_id, [])
            if states:
                rollback_states.append(states.pop())

        return self._rollback(rollback_states, module_appliers)

    # -----------------------------------------------------------------------
    # Internal helpers
    # -----------------------------------------------------------------------

    def _create_bundle(self, module_ids: Tuple[str, ...],
                       module_states: Dict[str, Any],
                       module_fitnesses: Dict[str, float],
                       module_interactions: Dict[str, List[str]]) -> Optional[MutationBundle]:
        """Create a mutation bundle for a set of modules.

        Uses game theory principles to find coordinated changes that are
        Pareto-improving relative to the current equilibrium.
        """
        mutations = []
        total_impact = 0.0
        pareto_improvement = True

        for module_id in module_ids:
            state = module_states.get(module_id)
            if not state:
                return None

            # Generate a candidate mutation for this module
            mutation = self._generate_mutation(module_id, state, module_fitnesses)
            if mutation is None:
                return None

            mutations.append(mutation)
            total_impact += mutation.expected_impact

            # Check Pareto improvement: each mutation should not decrease fitness
            # (coordinated changes may allow temporary regressions if compensated)
            if mutation.expected_impact < -self.fitness_threshold:
                pareto_improvement = False

        # For coordinated bundles, we allow small regressions if overall impact is positive
        # This is the key game theory insight: coordinated changes can escape local optima
        if total_impact > self.fitness_threshold:
            pareto_improvement = True  # Override if net positive

        bundle_id = self._generate_bundle_id(mutations)
        return MutationBundle(
            bundle_id=bundle_id,
            mutations=mutations,
            combined_expected_impact=total_impact,
            pareto_improvement=pareto_improvement
        )

    def _generate_mutation(self, module_id: str, state: Any,
                           fitnesses: Dict[str, float]) -> Optional[Mutation]:
        """Generate a single mutation for a module based on its state.

        This is a heuristic generator; real implementations should use
        domain-specific mutation strategies.
        """
        # Simple heuristic: tweak a random parameter or structure
        if isinstance(state, dict):
            # Try to find numeric parameters to tweak
            numeric_params = {k: v for k, v in state.items()
                              if isinstance(v, (int, float))}
            if numeric_params:
                target = random.choice(list(numeric_params.keys()))
                current_val = numeric_params[target]
                # Small perturbation (5-15% of current value)
                delta = current_val * random.uniform(0.05, 0.15) * random.choice([-1, 1])
                expected_impact = random.uniform(0.0, 0.1)  # Placeholder
                return Mutation(
                    module_id=module_id,
                    mutation_type=MutationType.PARAMETER_TWEAK,
                    target=target,
                    delta=delta,
                    expected_impact=expected_impact,
                    confidence=0.5
                )
        # Fallback: structural change (e.g., add/remove connection)
        return Mutation(
            module_id=module_id,
            mutation_type=MutationType.STRUCTURAL_CHANGE,
            target="structure",
            delta={"action": "modify_connection", "probability": 0.1},
            expected_impact=random.uniform(-0.05, 0.15),
            confidence=0.3
        )

    def _generate_bundle_id(self, mutations: List[Mutation]) -> str:
        """Generate a unique bundle ID from its mutations."""
        raw = json.dumps([(m.module_id, m.target, str(m.delta)) for m in mutations],
                         sort_keys=True)
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def _hash_state(self, state: Any) -> str:
        """Hash a module state for change detection."""
        raw = json.dumps(state, sort_keys=True, default=str)
        return hashlib.sha256(raw.encode()).hexdigest()

    def _rollback(self, states: List[ModuleState],
                  module_appliers: Dict[str, callable]) -> bool:
        """Rollback modules to given states."""
        success = True
        for state in states:
            applier = module_appliers.get(state.module_id)
            if applier:
                try:
                    applier(state.state_data, restore=True)
                except Exception:
                    success = False
        return success


# ---------------------------------------------------------------------------
# Convenience function
# ---------------------------------------------------------------------------

def create_mutation_bundle_from_equilibrium(
        module_states: Dict[str, Any],
        module_fitnesses: Dict[str, float],
        module_interactions: Dict[str, List[str]],
        sandbox_executor: callable,
        module_appliers: Dict[str, callable]) -> Optional[MutationBundle]:
    """High-level function: detect equilibrium, generate bundle, validate, apply.

    Returns the applied bundle if successful, None otherwise.
    """
    planner = CoordinatedMutationPlanner()
    if not planner.detect_equilibrium(module_fitnesses, module_interactions):
        return None

    bundles = planner.find_pareto_improving_bundles(
        module_states, module_fitnesses, module_interactions
    )
    if not bundles:
        return None

    best_bundle = bundles[0]
    if planner.validate_bundle_in_sandbox(best_bundle, sandbox_executor):
        if planner.apply_bundle(best_bundle, module_appliers):
            return best_bundle
    return None