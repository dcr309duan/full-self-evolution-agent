"""
Multi-Module Forcer: Escapes local optima by coordinating mutations across 2-3 modules.
Imports only from nash_detector (standard library only).
"""

import itertools
import random
from typing import Dict, List, Tuple, Any, Optional, Set
from core.nash_detector import NashEquilibriumDetector


class MultiModuleForcer:
    """
    Detects equilibrium clusters and generates coordinated mutation plans
    to escape local optima by changing multiple modules simultaneously.
    """

    def __init__(self, detector: Optional[NashEquilibriumDetector] = None):
        self.detector = detector or NashEquilibriumDetector()
        self.mutation_history: List[Dict[str, Any]] = []

    def analyze_equilibrium_clusters(self) -> List[Set[str]]:
        """
        Finds groups of modules where coordinated change would escape local optima.
        Returns a list of clusters (sets of module names) that are mutually reinforcing.
        """
        clusters = []
        modules = list(self.detector.module_interactions.keys())

        # Build a graph of mutual dependencies
        mutual_pairs = []
        for m1, m2 in itertools.combinations(modules, 2):
            if self._are_mutually_reinforcing(m1, m2):
                mutual_pairs.append((m1, m2))

        # Cluster using simple union-find on mutual pairs
        parent = {m: m for m in modules}

        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(x, y):
            px, py = find(x), find(y)
            if px != py:
                parent[px] = py

        for m1, m2 in mutual_pairs:
            union(m1, m2)

        # Collect clusters
        cluster_map: Dict[str, Set[str]] = {}
        for m in modules:
            root = find(m)
            if root not in cluster_map:
                cluster_map[root] = set()
            cluster_map[root].add(m)

        # Filter clusters with at least 2 modules (singletons can't coordinate)
        clusters = [c for c in cluster_map.values() if len(c) >= 2]

        # Sort clusters by size (largest first) for priority
        clusters.sort(key=len, reverse=True)
        return clusters

    def _are_mutually_reinforcing(self, module_a: str, module_b: str) -> bool:
        """
        Check if two modules are mutually reinforcing (form a local optimum trap).
        Uses interaction data from the detector.
        """
        # Get interaction data
        a_data = self.detector.module_interactions.get(module_a, {})
        b_data = self.detector.module_interactions.get(module_b, {})

        # Check if they reference each other
        a_refs_b = module_b in a_data.get("references", [])
        b_refs_a = module_a in b_data.get("references", [])

        # Check if they have similar stability (both stable = trapped)
        a_stable = a_data.get("stability", 0.0) > 0.7
        b_stable = b_data.get("stability", 0.0) > 0.7

        # Mutually reinforcing if they reference each other and are both stable
        return a_refs_b and b_refs_a and a_stable and b_stable

    def generate_coordinated_mutation_plan(
        self, cluster: Set[str], max_modules: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Produces a plan to change 2-3 modules simultaneously within a cluster.
        Returns a list of mutation plans, each describing changes for multiple modules.
        """
        plans = []
        modules = list(cluster)

        if len(modules) < 2:
            return plans

        # Generate plans for 2 and 3 module combinations
        for size in range(2, min(max_modules, len(modules)) + 1):
            for combo in itertools.combinations(modules, size):
                plan = self._create_mutation_plan(set(combo))
                if plan:
                    plans.append(plan)

        # Sort plans by estimated impact (descending)
        plans.sort(key=lambda p: p.get("estimated_impact", 0.0), reverse=True)
        return plans

    def _create_mutation_plan(self, modules: Set[str]) -> Optional[Dict[str, Any]]:
        """
        Create a mutation plan for a specific set of modules.
        Returns None if no viable plan exists.
        """
        if not modules or len(modules) < 2:
            return None

        plan = {
            "modules": list(modules),
            "changes": {},
            "estimated_impact": 0.0,
            "risk_score": 0.0,
        }

        total_stability = 0.0
        total_interactions = 0

        for module in modules:
            data = self.detector.module_interactions.get(module, {})
            stability = data.get("stability", 0.5)
            references = data.get("references", [])
            referenced_by = data.get("referenced_by", [])

            # Determine change type based on module characteristics
            change_type = self._determine_change_type(module, stability, references)
            plan["changes"][module] = {
                "type": change_type,
                "current_stability": stability,
                "target_stability": max(0.1, stability - 0.3),  # Reduce stability
                "dependencies": list(set(references + referenced_by)),
            }

            total_stability += stability
            total_interactions += len(references) + len(referenced_by)

        # Estimate impact: higher for modules with many interactions
        avg_stability = total_stability / len(modules) if modules else 0
        plan["estimated_impact"] = (1.0 - avg_stability) * (total_interactions + 1)
        plan["risk_score"] = avg_stability * 0.5 + (1.0 / (total_interactions + 1)) * 0.5

        return plan

    def _determine_change_type(
        self, module: str, stability: float, references: List[str]
    ) -> str:
        """
        Determine the type of change to apply based on module characteristics.
        """
        if stability > 0.9:
            return "restructure"  # Very stable: needs major restructuring
        elif stability > 0.7:
            return "refactor"  # Moderately stable: refactor interfaces
        elif len(references) > 5:
            return "decouple"  # Many references: reduce coupling
        else:
            return "optimize"  # Default: optimize implementation

    def execute_coordinated_mutation(
        self, plan: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Applies the multi-module change and validates it improves the system
        beyond single-module optimization.
        Returns a result dictionary with metrics.
        """
        if not plan or "modules" not in plan:
            return {
                "success": False,
                "error": "Invalid plan: no modules specified",
                "improvement": 0.0,
            }

        modules = plan["modules"]
        changes = plan.get("changes", {})

        # Simulate applying changes
        results = []
        pre_mutation_metrics = self._measure_system_metrics()

        for module in modules:
            if module in changes:
                change_info = changes[module]
                result = self._apply_single_mutation(module, change_info)
                results.append(result)

        post_mutation_metrics = self._measure_system_metrics()

        # Calculate improvement
        improvement = self._calculate_improvement(
            pre_mutation_metrics, post_mutation_metrics
        )

        # Validate against single-module optimization
        single_module_improvements = []
        for module in modules:
            single_improvement = self._simulate_single_module_change(module)
            single_module_improvements.append(single_improvement)

        avg_single_improvement = (
            sum(single_module_improvements) / len(single_module_improvements)
            if single_module_improvements
            else 0
        )

        coordinated_advantage = improvement - avg_single_improvement

        outcome = {
            "success": improvement > 0,
            "modules_changed": modules,
            "pre_metrics": pre_mutation_metrics,
            "post_metrics": post_mutation_metrics,
            "improvement": improvement,
            "avg_single_module_improvement": avg_single_improvement,
            "coordinated_advantage": coordinated_advantage,
            "exceeds_single_optimization": coordinated_advantage > 0,
            "individual_results": results,
        }

        self.mutation_history.append(outcome)
        return outcome

    def _measure_system_metrics(self) -> Dict[str, float]:
        """
        Measure current system metrics based on detector state.
        """
        total_stability = 0.0
        total_modules = len(self.detector.module_interactions)
        total_interactions = 0

        for module, data in self.detector.module_interactions.items():
            total_stability += data.get("stability", 0.5)
            total_interactions += len(data.get("references", []))

        return {
            "avg_stability": total_stability / max(total_modules, 1),
            "total_interactions": total_interactions,
            "module_count": total_modules,
            "diversity_score": self._calculate_diversity(),
        }

    def _calculate_diversity(self) -> float:
        """
        Calculate diversity of module stabilities (higher = more diverse).
        """
        stabilities = [
            data.get("stability", 0.5)
            for data in self.detector.module_interactions.values()
        ]
        if not stabilities:
            return 0.0

        mean = sum(stabilities) / len(stabilities)
        variance = sum((s - mean) ** 2 for s in stabilities) / len(stabilities)
        return variance ** 0.5  # Standard deviation as diversity metric

    def _apply_single_mutation(
        self, module: str, change_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Apply a single mutation to a module and record the result.
        """
        current_stability = change_info.get("current_stability", 0.5)
        target_stability = change_info.get("target_stability", 0.3)

        # Simulate mutation effect
        new_stability = random.uniform(
            target_stability - 0.1, target_stability + 0.1
        )
        new_stability = max(0.0, min(1.0, new_stability))

        # Update detector state
        if module in self.detector.module_interactions:
            self.detector.module_interactions[module]["stability"] = new_stability

        return {
            "module": module,
            "change_type": change_info.get("type", "optimize"),
            "old_stability": current_stability,
            "new_stability": new_stability,
            "stability_reduction": current_stability - new_stability,
        }

    def _calculate_improvement(
        self,
        pre_metrics: Dict[str, float],
        post_metrics: Dict[str, float],
    ) -> float:
        """
        Calculate overall improvement from pre to post mutation.
        Positive values indicate improvement.
        """
        improvement = 0.0

        # Stability reduction is good (escaping local optima)
        stability_change = (
            pre_metrics.get("avg_stability", 0.0)
            - post_metrics.get("avg_stability", 0.0)
        )
        improvement += stability_change * 0.4

        # Diversity increase is good
        diversity_change = (
            post_metrics.get("diversity_score", 0.0)
            - pre_metrics.get("diversity_score", 0.0)
        )
        improvement += diversity_change * 0.3

        # Interaction increase can be good (more exploration)
        interaction_change = (
            post_metrics.get("total_interactions", 0)
            - pre_metrics.get("total_interactions", 0)
        )
        improvement += interaction_change * 0.3

        return improvement

    def _simulate_single_module_change(self, module: str) -> float:
        """
        Simulate what the improvement would be if only this module was changed.
        Returns the estimated improvement value.
        """
        data = self.detector.module_interactions.get(module, {})
        stability = data.get("stability", 0.5)
        references = data.get("references", [])

        # Single module change has limited impact
        impact = (1.0 - stability) * 0.3 + len(references) * 0.05
        return impact

    def get_mutation_history(self) -> List[Dict[str, Any]]:
        """
        Return the history of all executed mutations.
        """
        return self.mutation_history.copy()

    def get_best_coordinated_mutation(self) -> Optional[Dict[str, Any]]:
        """
        Return the best coordinated mutation from history.
        """
        successful = [
            m for m in self.mutation_history if m.get("success", False)
        ]
        if not successful:
            return None
        return max(successful, key=lambda m: m.get("coordinated_advantage", 0.0))

    def force_coalition_change(self) -> List[Dict[str, Any]]:
        """
        Detects Nash equilibria and generates multi-module mutation proposals
        that would escape the equilibrium.
        
        Returns:
            A list of mutation proposals (each a dict) that would escape the equilibrium.
            Each proposal includes the modules to change and the specific changes.
        """
        # Step 1: Detect equilibrium
        equilibrium_result = self.detector.detect_equilibrium()
        
        if not equilibrium_result.get("equilibrium_detected", False):
            return []  # No equilibrium to escape from
        
        # Step 2: Find coalition improvements
        improvements = self.detector.find_coalition_improvements()
        
        if not improvements:
            return []  # No improvements found
        
        # Step 3: Convert improvements to mutation proposals
        proposals = []
        for improvement in improvements:
            modules = improvement.get("modules", [])
            if len(modules) < 2:
                continue
            
            # Create a mutation plan for this coalition
            plan = self._create_mutation_plan(set(modules))
            if plan:
                plan["source"] = "coalition_improvement"
                plan["improvement_value"] = improvement.get("value", 0.0)
                proposals.append(plan)
        
        # Sort proposals by improvement value (descending)
        proposals.sort(key=lambda p: p.get("improvement_value", 0.0), reverse=True)
        
        return proposals

    def propose_coordinated_multi_module_mutations(
        self, equilibrium_state: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Takes the equilibrium state and proposes coordinated multi-module mutations.
        
        Args:
            equilibrium_state: The current equilibrium state from the detector.
            
        Returns:
            A list of proposed mutation plans, each describing coordinated changes
            across multiple modules to escape the equilibrium.
        """
        proposals = []
        
        if not equilibrium_state.get("equilibrium_detected", False):
            return proposals
        
        # Extract module interactions from equilibrium state
        module_interactions = equilibrium_state.get("module_interactions", {})
        if not module_interactions:
            return proposals
        
        # Find clusters of mutually reinforcing modules
        clusters = self.analyze_equilibrium_clusters()
        
        # Generate coordinated mutation plans for each cluster
        for cluster in clusters:
            plans = self.generate_coordinated_mutation_plan(cluster)
            proposals.extend(plans)
        
        # Also consider coalition improvements from the equilibrium state
        improvements = equilibrium_state.get("coalition_improvements", [])
        for improvement in improvements:
            modules = improvement.get("modules", [])
            if len(modules) >= 2:
                plan = self._create_mutation_plan(set(modules))
                if plan:
                    plan["source"] = "equilibrium_coalition"
                    plan["improvement_value"] = improvement.get("value", 0.0)
                    proposals.append(plan)
        
        # Sort proposals by estimated impact (descending)
        proposals.sort(key=lambda p: p.get("estimated_impact", 0.0), reverse=True)
        
        return proposals


class MultiModuleOrchestrator:
    """
    Orchestrator that takes detected Nash equilibria and generates coordinated
    multi-module mutations, with conflict resolution and rollback mechanisms.
    """

    def __init__(self, detector: Optional[NashEquilibriumDetector] = None):
        self.detector = detector or NashEquilibriumDetector()
        self.forcer = MultiModuleForcer(self.detector)
        self.execution_history: List[Dict[str, Any]] = []
        self.snapshot_stack: List[Dict[str, Any]] = []
        self.equilibrium_log: List[Dict[str, Any]] = []
        self.forced_change_log: List[Dict[str, Any]] = []

    def log_equilibrium_event(self, event_type: str, details: Dict[str, Any]) -> None:
        """Log an equilibrium detection event."""
        log_entry = {
            "event_type": event_type,
            "details": details,
            "timestamp": len(self.equilibrium_log)
        }
        self.equilibrium_log.append(log_entry)

    def log_forced_change(self, change_type: str, plan: Dict[str, Any], result: Dict[str, Any]) -> None:
        """Log a forced change event."""
        log_entry = {
            "change_type": change_type,
            "plan": plan,
            "result": result,
            "timestamp": len(self.forced_change_log)
        }
        self.forced_change_log.append(log_entry)

    def orchestrate_from_equilibria(self) -> Dict[str, Any]:
        """
        Takes detected Nash equilibria and generates coordinated multi-module mutations.
        Returns the orchestration result.
        """
        clusters = self.forcer.analyze_equilibrium_clusters()
        if not clusters:
            self.log_equilibrium_event("no_clusters", {"message": "No equilibrium clusters found"})
            return {
                "success": False,
                "error": "No equilibrium clusters found",
                "mutations_executed": 0,
            }

        self.log_equilibrium_event("clusters_found", {"cluster_count": len(clusters), "clusters": [list(c) for c in clusters]})

        results = []
        for cluster in clusters:
            plans = self.forcer.generate_coordinated_mutation_plan(cluster)
            if plans:
                # Resolve conflicts before executing
                resolved_plan = self._resolve_conflicts(plans[0])
                if resolved_plan:
                    # Take snapshot for rollback
                    self._take_snapshot()
                    result = self.forcer.execute_coordinated_mutation(resolved_plan)
                    self.log_forced_change("coordinated_mutation", resolved_plan, result)
                    if not result.get("success", False):
                        self._rollback()
                        self.log_equilibrium_event("rollback", {"cluster": list(cluster), "reason": "Mutation failed"})
                    results.append(result)

        return {
            "success": any(r.get("success", False) for r in results),
            "clusters_found": len(clusters),
            "mutations_executed": len(results),
            "results": results,
        }

    def _resolve_conflicts(self, plan: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Resolves conflicts between changes in a multi-module mutation plan.
        Ensures changes are compatible across modules.
        """
        if not plan or "changes" not in plan:
            return None

        changes = plan["changes"]
        modules = list(changes.keys())

        # Check for conflicting change types
        change_types = [changes[m]["type"] for m in modules]
        if "restructure" in change_types and "optimize" in change_types:
            # Conflict: restructure and optimize on different modules may conflict
            # Resolve by upgrading optimize to refactor for consistency
            for m in modules:
                if changes[m]["type"] == "optimize":
                    changes[m]["type"] = "refactor"

        # Check for dependency conflicts
        all_dependencies = set()
        for m in modules:
            all_dependencies.update(changes[m].get("dependencies", []))

        # If any module depends on another in the plan, ensure compatibility
        for m1, m2 in itertools.combinations(modules, 2):
            if m2 in changes[m1].get("dependencies", []):
                # m1 depends on m2, so m2's change must not break m1
                if changes[m2]["type"] == "restructure":
                    # Downgrade m2's change to refactor to avoid breaking m1
                    changes[m2]["type"] = "refactor"

        plan["changes"] = changes
        return plan

    def _take_snapshot(self) -> None:
        """
        Takes a snapshot of the current system state for potential rollback.
        """
        snapshot = {
            "module_interactions": {
                module: dict(data)
                for module, data in self.detector.module_interactions.items()
            },
            "timestamp": len(self.execution_history),
        }
        self.snapshot_stack.append(snapshot)

    def _rollback(self) -> None:
        """
        Rolls back the system state to the last snapshot.
        """
        if not self.snapshot_stack:
            return

        snapshot = self.snapshot_stack.pop()
        self.detector.module_interactions = {
            module: dict(data)
            for module, data in snapshot["module_interactions"].items()
        }

    def execute_with_rollback(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executes a multi-module mutation with rollback capability.
        Returns the execution result.
        """
        self._take_snapshot()
        result = self.forcer.execute_coordinated_mutation(plan)
        if not result.get("success", False):
            self._rollback()
            result["rolled_back"] = True
            self.log_equilibrium_event("rollback", {"plan": plan, "reason": "Mutation failed"})
        else:
            result["rolled_back"] = False
        self.log_forced_change("executed_mutation", plan, result)
        self.execution_history.append(result)
        return result

    def integrate_with_mutation_pipeline(
        self, plan: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Integrates with the orchestrator's mutation pipeline to apply changes atomically.
        Takes a coordinated mutation plan and applies it through the pipeline,
        ensuring atomic application of all changes.
        
        Args:
            plan: The coordinated mutation plan to apply.
            
        Returns:
            A result dictionary indicating success/failure and details of the atomic operation.
        """
        if not plan or "modules" not in plan:
            return {
                "success": False,
                "error": "Invalid plan: no modules specified",
                "atomic_applied": False,
            }
        
        # Take snapshot before applying changes
        self._take_snapshot()
        
        try:
            # Apply all changes atomically through the pipeline
            result = self.forcer.execute_coordinated_mutation(plan)
            
            if result.get("success", False):
                # Record successful atomic operation
                result["atomic_applied"] = True
                result["rolled_back"] = False
                self.log_forced_change("atomic_mutation_success", plan, result)
            else:
                # Rollback on failure
                self._rollback()
                result["atomic_applied"] = False
                result["rolled_back"] = True
                self.log_equilibrium_event("rollback", {"plan": plan, "reason": "Atomic mutation failed"})
                self.log_forced_change("atomic_mutation_failure", plan, result)
            
            self.execution_history.append(result)
            return result
            
        except Exception as e:
            # Rollback on any exception
            self._rollback()
            error_result = {
                "success": False,
                "error": str(e),
                "atomic_applied": False,
                "rolled_back": True,
                "plan": plan,
            }
            self.log_equilibrium_event("rollback", {"plan": plan, "reason": f"Exception: {str(e)}"})
            self.log_forced_change("atomic_mutation_exception", plan, error_result)
            self.execution_history.append(error_result)
            return error_result

    def get_execution_history(self) -> List[Dict[str, Any]]:
        """
        Returns the history of all orchestrated executions.
        """
        return self.execution_history.copy()

    def get_equilibrium_log(self) -> List[Dict[str, Any]]:
        """Returns the equilibrium event log."""
        return self.equilibrium_log.copy()

    def get_forced_change_log(self) -> List[Dict[str, Any]]:
        """Returns the forced change log."""
        return self.forced_change_log.copy()

    def clear_history(self) -> None:
        """
        Clears the execution history and snapshot stack.
        """
        self.execution_history.clear()
        self.snapshot_stack.clear()
        self.equilibrium_log.clear()
        self.forced_change_log.clear()


def analyze_and_force_coordination(
    detector: Optional[NashEquilibriumDetector] = None,
    max_plans: int = 3,
) -> Dict[str, Any]:
    """
    Convenience function to analyze clusters and execute the best coordinated mutations.
    """
    forcer = MultiModuleForcer(detector)
    clusters = forcer.analyze_equilibrium_clusters()

    if not clusters:
        return {
            "success": False,
            "error": "No equilibrium clusters found",
            "mutations_executed": 0,
        }

    executed_count = 0
    results = []

    for cluster in clusters[:max_plans]:
        plans = forcer.generate_coordinated_mutation_plan(cluster)
        if plans:
            # Execute the best plan for this cluster
            result = forcer.execute_coordinated_mutation(plans[0])
            results.append(result)
            executed_count += 1

    return {
        "success": executed_count > 0,
        "clusters_found": len(clusters),
        "mutations_executed": executed_count,
        "results": results,
        "best_mutation": forcer.get_best_coordinated_mutation(),
    }


def generate_coordinated_multi_module_mutations(
    equilibrium_state: Dict[str, Any],
    detector: Optional[NashEquilibriumDetector] = None
) -> List[Dict[str, Any]]:
    """
    Generates coordinated multi-module mutations based on the equilibrium state.
    This function is designed to be called from the orchestrator's cycle loop.
    
    Args:
        equilibrium_state: The current equilibrium state from the detector.
        detector: Optional NashEquilibriumDetector instance.
        
    Returns:
        A list of coordinated mutation plans.
    """
    forcer = MultiModuleForcer(detector)
    return forcer.propose_coordinated_multi_module_mutations(equilibrium_state)


def execute_multi_module_mutation_with_rollback(
    plan: Dict[str, Any],
    detector: Optional[NashEquilibriumDetector] = None
) -> Dict[str, Any]:
    """
    Executes a multi-module mutation with rollback safety.
    This function is designed to be called from the orchestrator's cycle loop.
    
    Args:
        plan: The coordinated mutation plan to execute.
        detector: Optional NashEquilibriumDetector instance.
        
    Returns:
        A result dictionary with execution details and rollback status.
    """
    orchestrator = MultiModuleOrchestrator(detector)
    return orchestrator.execute_with_rollback(plan)


def integrate_with_orchestrator_cycle(
    equilibrium_state: Dict[str, Any],
    detector: Optional[NashEquilibriumDetector] = None,
    max_mutations: int = 3
) -> Dict[str, Any]:
    """
    Integrates multi-module forcing into the orchestrator's cycle loop.
    This function handles the full pipeline: generate plans, execute with rollback,
    and return results for the cycle loop to process.
    
    Args:
        equilibrium_state: The current equilibrium state from the detector.
        detector: Optional NashEquilibriumDetector instance.
        max_mutations: Maximum number of mutations to execute in this cycle.
        
    Returns:
        A result dictionary with all executed mutations and their outcomes.
    """
    # Step 1: Generate coordinated mutation plans
    plans = generate_coordinated_multi_module_mutations(equilibrium_state, detector)
    
    if not plans:
        return {
            "success": False,
            "error": "No coordinated mutation plans generated",
            "mutations_executed": 0,
            "results": []
        }
    
    # Step 2: Execute up to max_mutations plans with rollback
    executed_results = []
    for plan in plans[:max_mutations]:
        result = execute_multi_module_mutation_with_rollback(plan, detector)
        executed_results.append(result)
    
    # Step 3: Compile results for the cycle loop
    successful = [r for r in executed_results if r.get("success", False)]
    
    return {
        "success": len(successful) > 0,
        "plans_generated": len(plans),
        "mutations_executed": len(executed_results),
        "successful_mutations": len(successful),
        "results": executed_results,
        "cycle_feedback": {
            "improvement": sum(r.get("improvement", 0.0) for r in successful),
            "coordinated_advantage": sum(r.get("coordinated_advantage", 0.0) for r in successful),
            "rolled_back_count": sum(1 for r in executed_results if r.get("rolled_back", False))
        }
    }


def check_and_force_coordinated_mutation(
    detector: Optional[NashEquilibriumDetector] = None
) -> Dict[str, Any]:
    """
    Checks if the system is in a Nash equilibrium and forces a coordinated mutation
    to escape it. This function implements the full pipeline:
    (1) periodically checks for Nash equilibrium,
    (2) when detected, generates a coordinated multi-module mutation plan,
    (3) applies all changes atomically,
    (4) verifies the system escapes the equilibrium.
    
    Args:
        detector: Optional NashEquilibriumDetector instance.
        
    Returns:
        A result dictionary with the outcome of the coordinated mutation attempt.
    """
    forcer = MultiModuleForcer(detector)
    orchestrator = MultiModuleOrchestrator(detector)
    
    # Step 1: Check for Nash equilibrium
    equilibrium_result = forcer.detector.detect_equilibrium()
    
    if not equilibrium_result.get("equilibrium_detected", False):
        orchestrator.log_equilibrium_event("no_equilibrium", {"message": "No Nash equilibrium detected"})
        return {
            "success": False,
            "error": "No Nash equilibrium detected",
            "equilibrium_detected": False,
            "mutation_applied": False,
            "escaped_equilibrium": False
        }
    
    orchestrator.log_equilibrium_event("equilibrium_detected", equilibrium_result)
    
    # Step 2: Generate coordinated multi-module mutation plan
    plans = forcer.force_coalition_change()
    
    if not plans:
        # Fall back to cluster-based planning
        clusters = forcer.analyze_equilibrium_clusters()
        if not clusters:
            orchestrator.log_equilibrium_event("no_plans", {"message": "No viable mutation plans generated"})
            return {
                "success": False,
                "error": "No viable mutation plans generated",
                "equilibrium_detected": True,
                "mutation_applied": False,
                "escaped_equilibrium": False
            }
        
        for cluster in clusters:
            cluster_plans = forcer.generate_coordinated_mutation_plan(cluster)
            plans.extend(cluster_plans)
    
    if not plans:
        orchestrator.log_equilibrium_event("no_plans", {"message": "No viable mutation plans generated"})
        return {
            "success": False,
            "error": "No viable mutation plans generated",
            "equilibrium_detected": True,
            "mutation_applied": False,
            "escaped_equilibrium": False
        }
    
    # Step 3: Apply all changes atomically
    best_plan = plans[0]  # Plans are sorted by impact
    result = orchestrator.integrate_with_mutation_pipeline(best_plan)
    
    if not result.get("success", False):
        orchestrator.log_forced_change("failed_mutation", best_plan, result)
        return {
            "success": False,
            "error": "Atomic mutation application failed",
            "equilibrium_detected": True,
            "mutation_applied": False,
            "escaped_equilibrium": False,
            "mutation_result": result
        }
    
    # Step 4: Verify the system escapes the equilibrium
    post_equilibrium = forcer.detector.detect_equilibrium()
    escaped = not post_equilibrium.get("equilibrium_detected", True)
    
    orchestrator.log_forced_change("successful_mutation", best_plan, result)
    orchestrator.log_equilibrium_event("post_mutation_check", {"escaped": escaped, "post_equilibrium": post_equilibrium})
    
    return {
        "success": escaped,
        "equilibrium_detected": True,
        "mutation_applied": True,
        "escaped_equilibrium": escaped,
        "plan_applied": best_plan,
        "mutation_result": result,
        "post_equilibrium_state": post_equilibrium,
        "verification": {
            "pre_equilibrium": equilibrium_result,
            "post_equilibrium": post_equilibrium,
            "escaped": escaped
        }
    }


def _vote_on_modules(modules: List[str], detector: NashEquilibriumDetector) -> List[str]:
    """
    Simple voting mechanism to select which modules to change together.
    Each module gets a vote based on its stability and interaction count.
    Returns the top 2-3 modules with the most votes.
    """
    votes = {}
    for module in modules:
        data = detector.module_interactions.get(module, {})
        stability = data.get("stability", 0.5)
        references = len(data.get("references", []))
        referenced_by = len(data.get("referenced_by", []))
        
        # Vote score: higher stability and more interactions = more votes
        vote_score = stability * 2.0 + references * 0.5 + referenced_by * 0.5
        votes[module] = vote_score
    
    # Sort by vote score descending
    sorted_modules = sorted(votes.items(), key=lambda x: x[1], reverse=True)
    
    # Select top 2-3 modules (randomly choose between 2 or 3)
    num_to_select = random.choice([2, 3])
    selected = [m[0] for m in sorted_modules[:num_to_select]]
    
    return selected


def generate_coordinated_change_plan(detector: NashEquilibriumDetector) -> Optional[Dict[str, Any]]:
    """
    When nash_detector signals equilibrium, generate a coordinated change plan
    affecting 2-3 modules simultaneously using a voting mechanism.
    
    Args:
        detector: The NashEquilibriumDetector instance.
        
    Returns:
        A coordinated change plan, or None if no equilibrium detected.
    """
    # Check for equilibrium
    equilibrium_result = detector.detect_equilibrium()
    if not equilibrium_result.get("equilibrium_detected", False):
        return None
    
    # Get all modules
    modules = list(detector.module_interactions.keys())
    if len(modules) < 2:
        return None
    
    # Use voting to select which modules to change together
    selected_modules = _vote_on_modules(modules, detector)
    
    # Create a coordinated change plan
    forcer = MultiModuleForcer(detector)
    plan = forcer._create_mutation_plan(set(selected_modules))
    
    if plan:
        plan["source"] = "voting_mechanism"
        plan["voting_results"] = {m: detector.module_interactions.get(m, {}).get("stability", 0.5) for m in selected_modules}
    
    return plan


def execute_atomic_coordinated_change(
    plan: Dict[str, Any],
    detector: NashEquilibriumDetector
) -> Dict[str, Any]:
    """
    Implement the changes in a single atomic operation.
    Roll back all changes if any single change fails.
    
    Args:
        plan: The coordinated change plan to execute.
        detector: The NashEquilibriumDetector instance.
        
    Returns:
        A result dictionary indicating success/failure and rollback status.
    """
    orchestrator = MultiModuleOrchestrator(detector)
    return orchestrator.integrate_with_mutation_pipeline(plan)