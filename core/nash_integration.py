"""
core/nash_integration.py

Integration layer connecting the Nash detector to the evolution orchestrator.
Provides hooks for mutation cycle registration, equilibrium state queries,
and methods to trigger multi-module mutations.
"""

from typing import Any, Dict, List, Optional, Tuple, Callable
import logging

from core.nash_detector import NashDetector, NashEquilibriumState

logger = logging.getLogger(__name__)


class NashIntegrationLayer:
    """
    Integration layer that connects the Nash detector to the evolution orchestrator.
    Manages hooks, equilibrium queries, and multi-module mutation triggers.
    """

    def __init__(self, detector: NashDetector):
        """
        Initialize the integration layer with a Nash detector instance.

        Args:
            detector: Initialized NashDetector instance.
        """
        self.detector = detector
        self._pre_mutation_hooks: List[Callable] = []
        self._post_mutation_hooks: List[Callable] = []
        self._equilibrium_query_hooks: List[Callable] = []
        self._module_pool: Dict[str, Any] = {}
        self._orchestrator: Any = None

    def register_orchestrator(self, orchestrator: Any) -> None:
        """
        Register the evolution orchestrator with this integration layer.

        Args:
            orchestrator: The evolution orchestrator instance.
        """
        self._orchestrator = orchestrator
        logger.info("Orchestrator registered with Nash integration layer")

    def register_module_pool(self, module_pool: Dict[str, Any]) -> None:
        """
        Register the module pool for interaction analysis.

        Args:
            module_pool: Dictionary mapping module names to their current state/interface.
        """
        self._module_pool = module_pool
        logger.info("Module pool registered with Nash integration layer")

    def register_pre_mutation_hook(self, hook: Callable) -> None:
        """
        Register a hook to be called before each mutation cycle.

        Args:
            hook: Callable that takes no arguments and returns None.
        """
        self._pre_mutation_hooks.append(hook)
        logger.debug("Pre-mutation hook registered")

    def register_post_mutation_hook(self, hook: Callable) -> None:
        """
        Register a hook to be called after each mutation cycle.

        Args:
            hook: Callable that takes no arguments and returns None.
        """
        self._post_mutation_hooks.append(hook)
        logger.debug("Post-mutation hook registered")

    def register_equilibrium_query_hook(self, hook: Callable) -> None:
        """
        Register a hook for querying equilibrium states.

        Args:
            hook: Callable that takes no arguments and returns List[NashEquilibriumState].
        """
        self._equilibrium_query_hooks.append(hook)
        logger.debug("Equilibrium query hook registered")

    def execute_pre_mutation_hooks(self) -> None:
        """
        Execute all registered pre-mutation hooks.
        """
        for hook in self._pre_mutation_hooks:
            try:
                hook()
            except Exception as e:
                logger.exception("Error executing pre-mutation hook: %s", e)

    def execute_post_mutation_hooks(self) -> None:
        """
        Execute all registered post-mutation hooks.
        """
        for hook in self._post_mutation_hooks:
            try:
                hook()
            except Exception as e:
                logger.exception("Error executing post-mutation hook: %s", e)

    def query_equilibrium_states(self) -> List[NashEquilibriumState]:
        """
        Query current equilibrium states from all registered hooks and the detector.

        Returns:
            List of detected Nash equilibrium states.
        """
        all_states: List[NashEquilibriumState] = []

        # Query from hooks
        for hook in self._equilibrium_query_hooks:
            try:
                states = hook()
                if states:
                    all_states.extend(states)
            except Exception as e:
                logger.exception("Error querying equilibrium from hook: %s", e)

        # Query from detector directly
        if self._module_pool:
            try:
                detector_states = self.detector.detect_equilibria(self._module_pool)
                all_states.extend(detector_states)
            except Exception as e:
                logger.exception("Error querying equilibrium from detector: %s", e)

        return all_states

    def trigger_multi_module_mutation(
        self,
        modules: List[str],
        strategy: str,
        expected_gain: float,
        risk_level: str = "medium",
    ) -> bool:
        """
        Trigger a coordinated multi-module mutation.

        Args:
            modules: List of module names to mutate together.
            strategy: Description of the coordinated change.
            expected_gain: Estimated fitness improvement.
            risk_level: 'low', 'medium', or 'high'.

        Returns:
            True if the mutation was applied successfully.
        """
        if len(modules) < 2:
            logger.warning("Multi-module mutation requires at least 2 modules, got %d", len(modules))
            return False

        try:
            # Execute pre-mutation hooks
            self.execute_pre_mutation_hooks()

            # Apply coordinated change via detector
            success = self.detector.force_coordinated_change(
                modules=modules,
                strategy=strategy,
                expected_gain=expected_gain,
            )

            if success:
                logger.info(
                    "Successfully triggered multi-module mutation for modules %s",
                    modules,
                )
            else:
                logger.error(
                    "Failed to trigger multi-module mutation for modules %s",
                    modules,
                )

            # Execute post-mutation hooks
            self.execute_post_mutation_hooks()

            return success

        except Exception as e:
            logger.exception(
                "Error triggering multi-module mutation for modules %s: %s",
                modules,
                e,
            )
            return False

    def get_coordinated_mutation_plans(
        self,
        min_coordination_gain: float = 0.05,
        max_modules_per_plan: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Generate coordinated mutation plans based on current equilibrium states.

        Args:
            min_coordination_gain: Minimum expected fitness gain to justify coordination.
            max_modules_per_plan: Maximum number of modules to include in a single plan.

        Returns:
            List of mutation plans.
        """
        return plan_coordinated_mutations(
            detector=self.detector,
            module_pool=self._module_pool,
            min_coordination_gain=min_coordination_gain,
            max_modules_per_plan=max_modules_per_plan,
        )

    def apply_coordinated_plans(
        self,
        plans: List[Dict[str, Any]],
        mutation_engine: Any,
    ) -> List[Dict[str, Any]]:
        """
        Apply a list of coordinated mutation plans.

        Args:
            plans: List of mutation plans.
            mutation_engine: The mutation engine instance.

        Returns:
            List of applied mutation plans with results.
        """
        return apply_coordinated_mutations(
            detector=self.detector,
            mutation_engine=mutation_engine,
            equilibrium_states=self.query_equilibrium_states(),
            module_pool=self._module_pool,
        )

    def get_coordination_candidates(
        self,
        min_interaction_strength: float = 0.3,
    ) -> List[Tuple[str, str, float]]:
        """
        Identify pairs of modules that are strong candidates for coordinated mutation.

        Args:
            min_interaction_strength: Minimum interaction strength to consider.

        Returns:
            List of tuples (module_a, module_b, interaction_strength).
        """
        return get_coordination_candidates(
            detector=self.detector,
            module_pool=self._module_pool,
            min_interaction_strength=min_interaction_strength,
        )


def collect_module_interaction_data(
    orchestrator: Any,
    module_pool: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Collect module interaction data from the orchestrator.
    
    Args:
        orchestrator: The evolution orchestrator instance.
        module_pool: Dictionary mapping module names to their current state/interface.
        
    Returns:
        Dictionary containing interaction data including:
            - 'module_pool': The module pool dictionary
            - 'interaction_matrix': Matrix of module interactions if available
            - 'fitness_history': Recent fitness history if available
            - 'module_dependencies': Module dependency graph if available
    """
    interaction_data = {
        'module_pool': module_pool,
        'interaction_matrix': {},
        'fitness_history': [],
        'module_dependencies': {},
    }
    
    # Collect interaction matrix from orchestrator if available
    if hasattr(orchestrator, 'get_interaction_matrix'):
        interaction_data['interaction_matrix'] = orchestrator.get_interaction_matrix()
    
    # Collect fitness history from orchestrator if available
    if hasattr(orchestrator, 'get_fitness_history'):
        interaction_data['fitness_history'] = orchestrator.get_fitness_history()
    
    # Collect module dependencies from orchestrator if available
    if hasattr(orchestrator, 'get_module_dependencies'):
        interaction_data['module_dependencies'] = orchestrator.get_module_dependencies()
    
    return interaction_data


def feed_to_nash_detector(
    detector: NashDetector,
    interaction_data: Dict[str, Any],
) -> List[NashEquilibriumState]:
    """
    Feed collected interaction data to NashEquilibriumDetector.
    
    Args:
        detector: Initialized NashDetector instance.
        interaction_data: Dictionary containing module interaction data.
        
    Returns:
        List of detected Nash equilibrium states.
    """
    module_pool = interaction_data.get('module_pool', {})
    if not module_pool:
        logger.warning("No module pool found in interaction data")
        return []
    
    # Detect equilibria using the module pool
    equilibrium_states = detector.detect_equilibria(module_pool)
    
    # Optionally update detector with additional interaction data
    if interaction_data.get('interaction_matrix'):
        try:
            detector.update_interaction_matrix(interaction_data['interaction_matrix'])
        except AttributeError:
            logger.debug("Detector does not support update_interaction_matrix")
    
    return equilibrium_states


def apply_coordinated_mutations(
    detector: NashDetector,
    mutation_engine: Any,
    equilibrium_states: List[NashEquilibriumState],
    module_pool: Dict[str, Any],
    min_coordination_gain: float = 0.05,
    max_modules_per_plan: int = 5,
) -> List[Dict[str, Any]]:
    """
    Apply coordinated mutations by calling the mutation engine with a multi-module plan.
    
    Args:
        detector: Initialized NashDetector instance.
        mutation_engine: The mutation engine instance with apply_mutation method.
        equilibrium_states: List of detected Nash equilibrium states.
        module_pool: Dictionary mapping module names to their current state/interface.
        min_coordination_gain: Minimum expected fitness gain to justify coordination.
        max_modules_per_plan: Maximum number of modules to include in a single plan.
        
    Returns:
        List of applied mutation plans with results.
    """
    applied_plans: List[Dict[str, Any]] = []
    
    # Generate coordinated mutation plans
    plans = plan_coordinated_mutations(
        detector=detector,
        module_pool=module_pool,
        min_coordination_gain=min_coordination_gain,
        max_modules_per_plan=max_modules_per_plan,
    )
    
    # Apply each plan using the mutation engine
    for plan in plans:
        try:
            # Call mutation engine with multi-module plan
            result = mutation_engine.apply_mutation(
                modules=plan['modules'],
                strategy=plan['strategy'],
                expected_gain=plan['expected_gain'],
                risk_level=plan['risk_level'],
            )
            
            plan['applied'] = result
            plan['success'] = result is not None
            
            if result:
                logger.info(
                    "Successfully applied coordinated mutation for modules %s",
                    plan['modules'],
                )
            else:
                logger.warning(
                    "Failed to apply coordinated mutation for modules %s",
                    plan['modules'],
                )
            
            applied_plans.append(plan)
            
        except Exception as e:
            logger.exception(
                "Error applying coordinated mutation plan for modules %s: %s",
                plan['modules'],
                e,
            )
            plan['applied'] = False
            plan['success'] = False
            plan['error'] = str(e)
            applied_plans.append(plan)
    
    return applied_plans


def plan_coordinated_mutations(
    detector: NashDetector,
    module_pool: Dict[str, Any],
    min_coordination_gain: float = 0.05,
    max_modules_per_plan: int = 5,
) -> List[Dict[str, Any]]:
    """
    Analyze current module interactions and generate coordinated mutation plans
    for modules stuck in suboptimal Nash equilibria.

    Args:
        detector: Initialized NashDetector instance.
        module_pool: Dictionary mapping module names to their current state/interface.
        min_coordination_gain: Minimum expected fitness gain to justify coordination.
        max_modules_per_plan: Maximum number of modules to include in a single plan.

    Returns:
        List of mutation plans, each being a dict with keys:
            - 'modules': list of module names to mutate together
            - 'strategy': description of the coordinated change
            - 'expected_gain': estimated fitness improvement
            - 'risk_level': 'low', 'medium', or 'high'
    """
    plans: List[Dict[str, Any]] = []

    # Detect current equilibrium states
    equilibrium_states = detector.detect_equilibria(module_pool)

    for eq_state in equilibrium_states:
        if not _is_suboptimal_equilibrium(eq_state):
            continue

        # Identify modules in this equilibrium
        modules_in_eq = list(eq_state.modules_involved)
        if len(modules_in_eq) > max_modules_per_plan:
            modules_in_eq = modules_in_eq[:max_modules_per_plan]

        # Generate coordinated mutation strategy
        plan = _build_coordination_plan(
            detector=detector,
            modules=modules_in_eq,
            equilibrium_state=eq_state,
            module_pool=module_pool,
            min_gain=min_coordination_gain,
        )

        if plan is not None:
            plans.append(plan)
            logger.info(
                "Coordinated mutation plan created for modules %s: %s",
                modules_in_eq,
                plan["strategy"][:80],
            )

    return plans


def _is_suboptimal_equilibrium(eq_state: NashEquilibriumState) -> bool:
    """
    Determine if a Nash equilibrium is suboptimal and worth breaking.
    """
    # If average fitness is below a threshold or there's known stagnation
    if eq_state.average_fitness < 0.5:
        return True
    if eq_state.stagnation_count > 3:
        return True
    if eq_state.defection_opportunity > 0.1:
        return True
    return False


def _build_coordination_plan(
    detector: NashDetector,
    modules: List[str],
    equilibrium_state: NashEquilibriumState,
    module_pool: Dict[str, Any],
    min_gain: float,
) -> Optional[Dict[str, Any]]:
    """
    Build a single coordinated mutation plan for a set of modules.
    Returns None if no viable plan exists.
    """
    if len(modules) < 2:
        return None

    # Estimate gain from coordinated change
    expected_gain = detector.estimate_coordinated_gain(
        modules, equilibrium_state
    )

    if expected_gain < min_gain:
        logger.debug(
            "Expected gain %.3f below threshold %.3f for modules %s",
            expected_gain,
            min_gain,
            modules,
        )
        return None

    # Determine strategy based on interaction type
    strategy = _derive_strategy(modules, equilibrium_state, module_pool)

    # Assess risk
    risk_level = _assess_risk(modules, equilibrium_state, expected_gain)

    return {
        "modules": modules,
        "strategy": strategy,
        "expected_gain": expected_gain,
        "risk_level": risk_level,
    }


def _derive_strategy(
    modules: List[str],
    eq_state: NashEquilibriumState,
    module_pool: Dict[str, Any],
) -> str:
    """
    Derive a human-readable strategy description for the coordinated mutation.
    """
    # Simple heuristic: if modules have conflicting interfaces, suggest alignment
    conflicts = _detect_interface_conflicts(modules, module_pool)
    if conflicts:
        return (
            f"Resolve interface conflicts between {', '.join(conflicts)} "
            f"to align expectations and improve collective fitness."
        )

    # If there's a clear leader-follower dynamic, suggest role reversal
    if eq_state.defection_opportunity > 0.2:
        return (
            f"Swap roles between {modules[0]} and {modules[1]} "
            f"to break the current defection pattern."
        )

    # Default: suggest mutual adaptation
    return (
        f"Coordinate simultaneous adaptation of {', '.join(modules)} "
        f"to escape local optimum (current avg fitness: {eq_state.average_fitness:.3f})."
    )


def _detect_interface_conflicts(
    modules: List[str], module_pool: Dict[str, Any]
) -> List[Tuple[str, str]]:
    """
    Detect interface mismatches between modules.
    Returns list of conflicting module pairs.
    """
    conflicts: List[Tuple[str, str]] = []
    for i in range(len(modules)):
        for j in range(i + 1, len(modules)):
            mod_i = module_pool.get(modules[i])
            mod_j = module_pool.get(modules[j])
            if mod_i is None or mod_j is None:
                continue
            # Simple conflict detection: check if expected outputs don't match inputs
            if hasattr(mod_i, "output_schema") and hasattr(mod_j, "input_schema"):
                if mod_i.output_schema != mod_j.input_schema:
                    conflicts.append((modules[i], modules[j]))
    return conflicts


def _assess_risk(
    modules: List[str],
    eq_state: NashEquilibriumState,
    expected_gain: float,
) -> str:
    """
    Assess risk level of a coordinated mutation plan.
    """
    # More modules = higher risk
    if len(modules) > 3:
        return "high"
    # If gain is very high, risk might be worth it
    if expected_gain > 0.3:
        return "medium"
    # Low module count and moderate gain = low risk
    if len(modules) <= 2 and expected_gain < 0.2:
        return "low"
    return "medium"


def apply_coordinated_mutation_plan(
    plan: Dict[str, Any],
    detector: NashDetector,
    module_pool: Dict[str, Any],
) -> bool:
    """
    Execute a coordinated mutation plan by invoking the detector's
    force_coordinated_change method.

    Args:
        plan: Mutation plan dict as returned by plan_coordinated_mutations.
        detector: Initialized NashDetector instance.
        module_pool: Dictionary mapping module names to their current state.

    Returns:
        True if the coordinated change was applied successfully.
    """
    modules = plan.get("modules", [])
    if len(modules) < 2:
        logger.warning("Coordinated plan requires at least 2 modules, got %d", len(modules))
        return False

    try:
        success = detector.force_coordinated_change(
            modules=modules,
            strategy=plan.get("strategy", ""),
            expected_gain=plan.get("expected_gain", 0.0),
        )
        if success:
            logger.info(
                "Successfully applied coordinated mutation for modules %s",
                modules,
            )
        else:
            logger.error(
                "Failed to apply coordinated mutation for modules %s",
                modules,
            )
        return success
    except Exception as e:
        logger.exception(
            "Error applying coordinated mutation plan for modules %s: %s",
            modules,
            e,
        )
        return False


def get_coordination_candidates(
    detector: NashDetector,
    module_pool: Dict[str, Any],
    min_interaction_strength: float = 0.3,
) -> List[Tuple[str, str, float]]:
    """
    Identify pairs of modules that are strong candidates for coordinated mutation.

    Returns:
        List of tuples (module_a, module_b, interaction_strength).
    """
    candidates: List[Tuple[str, str, float]] = []

    module_names = list(module_pool.keys())
    for i in range(len(module_names)):
        for j in range(i + 1, len(module_names)):
            mod_a = module_names[i]
            mod_b = module_names[j]

            strength = detector.measure_interaction_strength(mod_a, mod_b, module_pool)
            if strength >= min_interaction_strength:
                candidates.append((mod_a, mod_b, strength))

    # Sort by interaction strength descending
    candidates.sort(key=lambda x: x[2], reverse=True)
    return candidates