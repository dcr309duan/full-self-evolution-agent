"""Coordinated Mutation Planner for Nash equilibrium detection and atomic multi-module changes."""

from typing import List, Dict, Tuple, Any, Set
from collections import defaultdict


class CoordinatedMutationPlanner:
    """
    Planner that, upon Nash equilibrium detection, generates coordinated multi-module mutations.
    Uses dependency graph to identify tightly coupled clusters and proposes simultaneous changes.
    """

    def __init__(self, dependency_graph: Dict[str, Set[str]]):
        """
        Initialize planner with a dependency graph.

        Args:
            dependency_graph: Dict mapping module names to sets of modules they depend on.
        """
        self.dependency_graph = dependency_graph
        self.clusters = self._identify_clusters()

    def _identify_clusters(self) -> List[Set[str]]:
        """
        Identify clusters of tightly coupled modules using strongly connected components (SCCs)
        and transitive dependency analysis.

        Returns:
            List of sets, each set containing module names in a cluster.
        """
        # Build adjacency list for both directions
        forward = self.dependency_graph
        reverse = defaultdict(set)
        for module, deps in forward.items():
            for dep in deps:
                reverse[dep].add(module)

        # Kosaraju's algorithm for SCCs
        visited = set()
        stack = []

        def dfs(node, graph, collect):
            visited.add(node)
            for neighbor in graph.get(node, set()):
                if neighbor not in visited:
                    dfs(neighbor, graph, collect)
            if collect is not None:
                stack.append(node)

        # First pass: order by finish time
        for node in list(forward.keys()) + list(reverse.keys()):
            if node not in visited:
                dfs(node, forward, stack)

        # Second pass: collect SCCs
        visited.clear()
        sccs = []
        while stack:
            node = stack.pop()
            if node not in visited:
                component = []
                dfs(node, reverse, component)
                sccs.append(set(component))

        # Filter out single-node SCCs that are not tightly coupled
        # Tight coupling: mutual dependency or shared callers/callees
        clusters = []
        for scc in sccs:
            if len(scc) > 1:
                clusters.append(scc)
            else:
                # Check for tight coupling via shared dependencies
                node = next(iter(scc))
                deps = forward.get(node, set())
                callers = reverse.get(node, set())
                # If node has both callers and callees that form a cycle with it
                for dep in deps:
                    if dep in callers:
                        clusters.append({node, dep})
                        break
                else:
                    # Check if node is part of a larger implicit cluster
                    # (e.g., reflection_parser + goal_generator + mutation_engine)
                    if len(deps & callers) > 0:
                        clusters.append({node} | deps | callers)

        # Merge overlapping clusters
        merged = []
        for cluster in clusters:
            for existing in merged:
                if cluster & existing:
                    existing.update(cluster)
                    break
            else:
                merged.append(cluster)

        return merged

    def generate_mutation_plan(self, equilibrium_state: Dict[str, Any]) -> List[Tuple[str, Dict]]:
        """
        Generate a coordinated mutation plan based on detected Nash equilibrium.

        Args:
            equilibrium_state: Current state of the system at Nash equilibrium.

        Returns:
            List of (module, change_spec) pairs to apply atomically.
        """
        plan = []

        for cluster in self.clusters:
            # Generate coordinated changes for this cluster
            cluster_changes = self._plan_cluster_mutations(cluster, equilibrium_state)
            plan.extend(cluster_changes)

        return plan

    def _plan_cluster_mutations(self, cluster: Set[str], state: Dict[str, Any]) -> List[Tuple[str, Dict]]:
        """
        Plan mutations for a single cluster of tightly coupled modules.

        Args:
            cluster: Set of module names in the cluster.
            state: Current equilibrium state.

        Returns:
            List of (module, change_spec) for this cluster.
        """
        changes = []

        # Determine the interface module (the one most depended upon)
        interface_module = self._find_interface_module(cluster)

        # Change the interface and all callers simultaneously
        if interface_module:
            # Change interface signature
            interface_change = {
                "type": "interface_change",
                "new_signature": self._generate_new_signature(interface_module, state),
                "reason": "Nash equilibrium detected - coordinated interface update"
            }
            changes.append((interface_module, interface_change))

            # Change all callers to match new interface
            for module in cluster:
                if module != interface_module and self._is_caller(module, interface_module):
                    caller_change = {
                        "type": "caller_update",
                        "target_interface": interface_module,
                        "new_call_signature": interface_change["new_signature"],
                        "reason": "Simultaneous update to match new interface"
                    }
                    changes.append((module, caller_change))

        # If no clear interface, change all modules in cluster with complementary changes
        if not changes:
            for module in cluster:
                change = {
                    "type": "coordinated_mutation",
                    "cluster_id": hash(frozenset(cluster)),
                    "complementary_changes": self._get_complementary_changes(module, cluster, state),
                    "reason": "Part of coordinated cluster mutation"
                }
                changes.append((module, change))

        return changes

    def _find_interface_module(self, cluster: Set[str]) -> str:
        """
        Find the module that serves as an interface (most depended upon) within a cluster.

        Args:
            cluster: Set of module names.

        Returns:
            Name of the interface module, or None if not found.
        """
        dependency_count = {}
        for module in cluster:
            count = 0
            for other in cluster:
                if other != module and module in self.dependency_graph.get(other, set()):
                    count += 1
            dependency_count[module] = count

        if dependency_count:
            return max(dependency_count, key=dependency_count.get)
        return None

    def _is_caller(self, module: str, target: str) -> bool:
        """Check if module calls (depends on) target."""
        return target in self.dependency_graph.get(module, set())

    def _generate_new_signature(self, module: str, state: Dict[str, Any]) -> Dict:
        """
        Generate a new interface signature for a module based on equilibrium state.

        Args:
            module: Module name.
            state: Current equilibrium state.

        Returns:
            Dictionary representing new signature.
        """
        # Placeholder: In real implementation, this would analyze state and generate
        # a new signature that breaks the Nash equilibrium
        return {
            "module": module,
            "parameters": ["new_param_1", "new_param_2"],
            "return_type": "new_return_type",
            "state_hash": hash(str(state.get(module, {})))
        }

    def _get_complementary_changes(self, module: str, cluster: Set[str], state: Dict[str, Any]) -> List[Dict]:
        """
        Get complementary changes for a module that are invalid individually but valid together.

        Args:
            module: The module to generate changes for.
            cluster: The cluster this module belongs to.
            state: Current equilibrium state.

        Returns:
            List of change specifications.
        """
        complementary = []
        for other in cluster:
            if other != module:
                # Each change depends on the other module's change
                change = {
                    "module": other,
                    "required_change": f"simultaneous_update_{module}_{other}",
                    "dependency": module,
                    "state": state.get(other, {})
                }
                complementary.append(change)
        return complementary

    def detect_nash_equilibrium(self, state: Dict[str, Any]) -> bool:
        """
        Detect if the current state represents a Nash equilibrium.

        Args:
            state: Current system state.

        Returns:
            True if Nash equilibrium detected, False otherwise.
        """
        # Placeholder: In real implementation, this would check if no module can
        # unilaterally improve its payoff given others' strategies
        # For now, return True if there are clusters (indicating tight coupling)
        return len(self.clusters) > 0

    def get_plan_summary(self, plan: List[Tuple[str, Dict]]) -> str:
        """
        Get a human-readable summary of the mutation plan.

        Args:
            plan: The mutation plan to summarize.

        Returns:
            String summary.
        """
        if not plan:
            return "No mutations planned."

        summary_lines = ["Coordinated Mutation Plan:"]
        cluster_groups = defaultdict(list)
        for module, change in plan:
            cluster_id = change.get("cluster_id", hash(module))
            cluster_groups[cluster_id].append((module, change))

        for cluster_id, changes in cluster_groups.items():
            summary_lines.append(f"\nCluster {cluster_id}:")
            for module, change in changes:
                change_type = change.get("type", "unknown")
                summary_lines.append(f"  - {module}: {change_type} ({change.get('reason', '')})")

        return "\n".join(summary_lines)


# Example usage
if __name__ == "__main__":
    # Example dependency graph for tightly coupled modules
    dep_graph = {
        "reflection_parser": {"goal_generator"},
        "goal_generator": {"mutation_engine"},
        "mutation_engine": {"reflection_parser"},
        "module_a": {"module_b"},
        "module_b": {"module_a"},
        "standalone": set()
    }

    planner = CoordinatedMutationPlanner(dep_graph)
    print("Identified clusters:", planner.clusters)

    # Simulate equilibrium state
    equilibrium = {
        "reflection_parser": {"state": "stable"},
        "goal_generator": {"state": "stable"},
        "mutation_engine": {"state": "stable"}
    }

    if planner.detect_nash_equilibrium(equilibrium):
        plan = planner.generate_mutation_plan(equilibrium)
        print(planner.get_plan_summary(plan))