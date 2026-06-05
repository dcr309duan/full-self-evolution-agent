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

    def orchestrate_from_equilibria(self) -> Dict[str, Any]:
        """
        Takes detected Nash equilibria and generates coordinated multi-module mutations.
        Returns the orchestration result.
        """
        clusters = self.forcer.analyze_equilibrium_clusters()
        if not clusters:
            return {
                "success": False,
                "error": "No equilibrium clusters found",
                "mutations_executed": 0,
            }

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
                    if not result.get("success", False):
                        self._rollback()
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
        else:
            result["rolled_back"] = False
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
            else:
                # Rollback on failure
                self._rollback()
                result["atomic_applied"] = False
                result["rolled_back"] = True
            
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
            self.execution_history.append(error_result)
            return error_result

    def get_execution_history(self) -> List[Dict[str, Any]]:
        """
        Returns the history of all orchestrated executions.
        """
        return self.execution_history.copy()

    def clear_history(self) -> None:
        """
        Clears the execution history and snapshot stack.
        """
        self.execution_history.clear()
        self.snapshot_stack.clear()


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