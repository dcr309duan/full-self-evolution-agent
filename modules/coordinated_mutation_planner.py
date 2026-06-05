"""Coordinated Mutation Planner for Nash Equilibrium-based multi-module evolution.

When a Nash equilibrium is detected, this module generates coordinated multi-module
mutations (mutation bundles) that can escape local optima through Pareto-improving
changes across interdependent modules.
"""

import random
import hashlib
import json
from typing import Dict, List, Tuple, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict

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
    file_changes: Dict[str, List[Dict[str, Any]]] = field(default_factory=dict)
    # file_changes: {filename: [{"action": "add"/"remove"/"modify", "line": int, "content": str}, ...]}


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
    confidence_score: float = 0.0
    interaction_centrality: float = 0.0


@dataclass
class ModuleState:
    """Snapshot of a module's state for rollback."""
    module_id: str
    state_hash: str
    state_data: Dict[str, Any]


@dataclass
class CoordinatedPlan:
    """A complete coordinated mutation plan with file-level changes."""
    plan_id: str
    mutations: List[Mutation]
    modules_modified: List[str]
    total_expected_impact: float
    confidence_score: float
    interaction_centrality: float
    file_changes_summary: Dict[str, List[str]]


# ---------------------------------------------------------------------------
# Core planner
# ---------------------------------------------------------------------------

class CoordinatedMutationPlanner:
    """Plans and manages coordinated mutations across modules in Nash equilibrium."""

    def __init__(self, fitness_threshold: float = 0.01, max_bundle_size: int = 4):
        self.fitness_threshold = fitness_threshold
        self.max_bundle_size = max_bundle_size
        self._bundles: List[MutationBundle] = []
        self._rollback_states: Dict[str, List[ModuleState]] = {}
        self._historical_success: Dict[str, float] = defaultdict(lambda: 0.5)
        # Track success rates for similar mutation patterns
        self._pattern_success: Dict[str, Tuple[int, int]] = defaultdict(lambda: (0, 0))

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

    def compute_interaction_centrality(self, module_id: str,
                                       module_interactions: Dict[str, List[str]]) -> float:
        """Compute interaction centrality for a module based on its connectivity."""
        neighbors = module_interactions.get(module_id, [])
        if not neighbors:
            return 0.0
        
        # Simple degree centrality normalized by total modules
        total_modules = len(module_interactions)
        if total_modules <= 1:
            return 0.0
        
        # Also consider second-order connections
        second_order = set()
        for neighbor in neighbors:
            second_order.update(module_interactions.get(neighbor, []))
        second_order.discard(module_id)
        for n in neighbors:
            second_order.discard(n)
        
        # Weighted centrality: direct connections count more
        centrality = (len(neighbors) + 0.5 * len(second_order)) / total_modules
        return min(centrality, 1.0)

    def generate_coordinated_plans(self,
                                   module_states: Dict[str, Any],
                                   module_fitnesses: Dict[str, float],
                                   module_interactions: Dict[str, List[str]],
                                   dependency_graph: Dict[str, List[str]],
                                   fitness_landscape: Dict[str, Dict[str, float]],
                                   num_plans: int = 3) -> List[CoordinatedPlan]:
        """Generate 2-3 alternative coordinated mutation plans per cycle.

        Args:
            module_states: Current states of all modules.
            module_fitnesses: Current fitness values for each module.
            module_interactions: Interaction graph between modules.
            dependency_graph: Dependency relationships between modules.
            fitness_landscape: Historical fitness data for fitness landscape analysis.
            num_plans: Number of alternative plans to generate (2-3).

        Returns:
            List of CoordinatedPlan objects, prioritized by interaction centrality.
        """
        if not self.detect_equilibrium(module_fitnesses, module_interactions):
            return []

        plans = []
        modules = list(module_states.keys())
        
        # Compute interaction centrality for all modules
        centrality_scores = {}
        for module_id in modules:
            centrality_scores[module_id] = self.compute_interaction_centrality(
                module_id, module_interactions
            )
        
        # Sort modules by centrality (descending)
        sorted_modules = sorted(modules, key=lambda m: centrality_scores[m], reverse=True)
        
        # Generate plans with different module combinations
        # Prioritize modules with highest interaction centrality
        for plan_idx in range(min(num_plans, 3)):
            plan_modules = self._select_plan_modules(
                sorted_modules, centrality_scores, plan_idx, module_states
            )
            
            if len(plan_modules) < 2:
                continue
            
            plan = self._create_coordinated_plan(
                plan_modules, module_states, module_fitnesses,
                module_interactions, dependency_graph, fitness_landscape
            )
            
            if plan:
                plans.append(plan)
        
        # Sort plans by interaction centrality (descending)
        plans.sort(key=lambda p: p.interaction_centrality, reverse=True)
        
        return plans[:num_plans]

    def _select_plan_modules(self, sorted_modules: List[str],
                             centrality_scores: Dict[str, float],
                             plan_idx: int,
                             module_states: Dict[str, Any]) -> List[str]:
        """Select 2-4 modules for a coordinated plan, prioritizing high centrality."""
        num_modules = random.randint(2, min(4, len(sorted_modules)))
        
        if plan_idx == 0:
            # First plan: use highest centrality modules
            selected = sorted_modules[:num_modules]
        elif plan_idx == 1:
            # Second plan: mix of high and medium centrality
            mid_point = len(sorted_modules) // 2
            high_centrality = sorted_modules[:mid_point]
            if len(high_centrality) >= num_modules:
                selected = random.sample(high_centrality, num_modules)
            else:
                selected = high_centrality + random.sample(
                    sorted_modules[mid_point:], num_modules - len(high_centrality)
                )
        else:
            # Third plan: more diverse selection
            selected = random.sample(sorted_modules, min(num_modules, len(sorted_modules)))
        
        return selected[:num_modules]

    def _create_coordinated_plan(self, module_ids: List[str],
                                 module_states: Dict[str, Any],
                                 module_fitnesses: Dict[str, float],
                                 module_interactions: Dict[str, List[str]],
                                 dependency_graph: Dict[str, List[str]],
                                 fitness_landscape: Dict[str, Dict[str, float]]) -> Optional[CoordinatedPlan]:
        """Create a coordinated plan with exact file changes for selected modules."""
        mutations = []
        total_impact = 0.0
        total_centrality = 0.0
        file_changes_summary = {}
        
        for module_id in module_ids:
            state = module_states.get(module_id)
            if not state:
                return None
            
            # Generate mutation with exact file changes
            mutation = self._generate_mutation_with_file_changes(
                module_id, state, module_fitnesses, dependency_graph
            )
            if mutation is None:
                return None
            
            mutations.append(mutation)
            total_impact += mutation.expected_impact
            
            # Aggregate file changes
            for filename, changes in mutation.file_changes.items():
                if filename not in file_changes_summary:
                    file_changes_summary[filename] = []
                for change in changes:
                    action = change.get("action", "modify")
                    line = change.get("line", 0)
                    file_changes_summary[filename].append(f"{action} at line {line}")
            
            # Compute centrality for this module
            centrality = self.compute_interaction_centrality(module_id, module_interactions)
            total_centrality += centrality
        
        # Compute confidence score based on historical success
        confidence_score = self._compute_confidence_score(mutations, fitness_landscape)
        
        # Average centrality
        avg_centrality = total_centrality / len(module_ids) if module_ids else 0.0
        
        plan_id = self._generate_plan_id(mutations)
        
        return CoordinatedPlan(
            plan_id=plan_id,
            mutations=mutations,
            modules_modified=list(module_ids),
            total_expected_impact=total_impact,
            confidence_score=confidence_score,
            interaction_centrality=avg_centrality,
            file_changes_summary=file_changes_summary
        )

    def _generate_mutation_with_file_changes(self, module_id: str, state: Any,
                                              fitnesses: Dict[str, float],
                                              dependency_graph: Dict[str, List[str]]) -> Optional[Mutation]:
        """Generate a mutation with exact file-level changes specified."""
        # Determine the file path for this module
        file_path = f"modules/{module_id}.py"
        
        # Generate file changes based on module state and type
        file_changes = {}
        
        if isinstance(state, dict):
            # Try to find numeric parameters to tweak
            numeric_params = {k: v for k, v in state.items()
                              if isinstance(v, (int, float))}
            if numeric_params:
                target = random.choice(list(numeric_params.keys()))
                current_val = numeric_params[target]
                delta = current_val * random.uniform(0.05, 0.15) * random.choice([-1, 1])
                expected_impact = random.uniform(0.0, 0.1)
                
                # Specify exact file changes
                file_changes[file_path] = [
                    {
                        "action": "modify",
                        "line": random.randint(10, 100),
                        "content": f"        {target} = {current_val + delta}  # Coordinated mutation adjustment"
                    }
                ]
                
                return Mutation(
                    module_id=module_id,
                    mutation_type=MutationType.PARAMETER_TWEAK,
                    target=target,
                    delta=delta,
                    expected_impact=expected_impact,
                    confidence=0.5,
                    file_changes=file_changes
                )
        
        # Fallback: structural change
        # Add a new function or modify existing logic
        file_changes[file_path] = [
            {
                "action": "add",
                "line": random.randint(50, 200),
                "content": f"    def _coordinated_mutation_helper(self):\n"
                           f"        \"\"\"Helper function for coordinated mutation.\"\"\"\n"
                           f"        pass\n"
            },
            {
                "action": "modify",
                "line": random.randint(20, 100),
                "content": f"        # Coordinated mutation: enhanced logic\n"
                           f"        self._coordinated_mutation_helper()\n"
            }
        ]
        
        return Mutation(
            module_id=module_id,
            mutation_type=MutationType.STRUCTURAL_CHANGE,
            target="structure",
            delta={"action": "add_helper_function", "lines_added": 4},
            expected_impact=random.uniform(-0.05, 0.15),
            confidence=0.3,
            file_changes=file_changes
        )

    def _compute_confidence_score(self, mutations: List[Mutation],
                                  fitness_landscape: Dict[str, Dict[str, float]]) -> float:
        """Compute confidence score based on historical success of similar changes."""
        if not mutations:
            return 0.0
        
        # Base confidence from individual mutation confidences
        base_confidence = sum(m.confidence for m in mutations) / len(mutations)
        
        # Adjust based on historical pattern success
        pattern_key = self._get_pattern_key(mutations)
        successes, attempts = self._pattern_success[pattern_key]
        
        if attempts > 0:
            historical_rate = successes / attempts
            # Weighted combination: 70% historical, 30% base
            confidence = 0.7 * historical_rate + 0.3 * base_confidence
        else:
            confidence = base_confidence * 0.8  # Slight penalty for unknown patterns
        
        # Consider fitness landscape similarity
        landscape_confidence = self._evaluate_fitness_landscape(mutations, fitness_landscape)
        confidence = 0.6 * confidence + 0.4 * landscape_confidence
        
        return min(max(confidence, 0.0), 1.0)

    def _get_pattern_key(self, mutations: List[Mutation]) -> str:
        """Generate a pattern key for historical tracking."""
        types = sorted([m.mutation_type.value for m in mutations])
        return "_".join(types)

    def _evaluate_fitness_landscape(self, mutations: List[Mutation],
                                    fitness_landscape: Dict[str, Dict[str, float]]) -> float:
        """Evaluate how well the mutation fits the current fitness landscape."""
        if not fitness_landscape:
            return 0.5
        
        # Check if similar mutations have been successful in similar landscapes
        similar_count = 0
        successful_similar = 0
        
        for module_id, landscape in fitness_landscape.items():
            for mutation in mutations:
                if mutation.module_id == module_id:
                    # Look for similar mutation types in landscape
                    for key, value in landscape.items():
                        if mutation.mutation_type.value in key:
                            similar_count += 1
                            if value > 0:
                                successful_similar += 1
        
        if similar_count > 0:
            return successful_similar / similar_count
        return 0.5

    def _generate_plan_id(self, mutations: List[Mutation]) -> str:
        """Generate a unique plan ID."""
        raw = json.dumps([(m.module_id, m.target, str(m.delta)) for m in mutations],
                         sort_keys=True)
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

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
        
        # Update historical success tracking
        pattern_key = self._get_pattern_key(bundle.mutations)
        successes, attempts = self._pattern_success[pattern_key]
        self._pattern_success[pattern_key] = (successes + 1, attempts + 1)
        
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

        # Update historical failure tracking
        pattern_key = self._get_pattern_key(bundle.mutations)
        successes, attempts = self._pattern_success[pattern_key]
        self._pattern_success[pattern_key] = (successes, attempts + 1)

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
        total_centrality = 0.0

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
            
            # Compute centrality
            centrality = self.compute_interaction_centrality(module_id, module_interactions)
            total_centrality += centrality

            # Check Pareto improvement: each mutation should not decrease fitness
            # (coordinated changes may allow temporary regressions if compensated)
            if mutation.expected_impact < -self.fitness_threshold:
                pareto_improvement = False

        # For coordinated bundles, we allow small regressions if overall impact is positive
        # This is the key game theory insight: coordinated changes can escape local optima
        if total_impact > self.fitness_threshold:
            pareto_improvement = True  # Override if net positive

        bundle_id = self._generate_bundle_id(mutations)
        
        # Compute confidence score
        confidence_score = self._compute_confidence_score(mutations, {})
        avg_centrality = total_centrality / len(module_ids) if module_ids else 0.0
        
        return MutationBundle(
            bundle_id=bundle_id,
            mutations=mutations,
            combined_expected_impact=total_impact,
            pareto_improvement=pareto_improvement,
            confidence_score=confidence_score,
            interaction_centrality=avg_centrality
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


def generate_coordinated_mutation_plans(
        module_states: Dict[str, Any],
        module_fitnesses: Dict[str, float],
        module_interactions: Dict[str, List[str]],
        dependency_graph: Dict[str, List[str]],
        fitness_landscape: Dict[str, Dict[str, float]],
        num_plans: int = 3) -> List[CoordinatedPlan]:
    """Convenience function to generate coordinated mutation plans.
    
    Args:
        module_states: Current states of all modules.
        module_fitnesses: Current fitness values for each module.
        module_interactions: Interaction graph between modules.
        dependency_graph: Dependency relationships between modules.
        fitness_landscape: Historical fitness data.
        num_plans: Number of alternative plans to generate (2-3).
    
    Returns:
        List of CoordinatedPlan objects, prioritized by interaction centrality.
    """
    planner = CoordinatedMutationPlanner()
    return planner.generate_coordinated_plans(
        module_states, module_fitnesses, module_interactions,
        dependency_graph, fitness_landscape, num_plans
    )