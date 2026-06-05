from typing import Dict, List, Optional, Any
from datetime import datetime
import uuid
import copy


class SimulationNode:
    """Represents a module node in the self-model knowledge graph with simulation data."""

    def __init__(self, module_id: str, module_name: str, accuracy: float = 0.0):
        self.id = module_id
        self.name = module_name
        self.accuracy = accuracy  # Accuracy metric for this module's simulation
        self.simulation_history: List[Dict[str, Any]] = []  # History of simulation runs
        self.cross_references: List[Dict[str, Any]] = []  # Cross-ref predictions vs actuals
        self.failure_clusters: List[str] = []  # IDs of failure clusters affecting this module

    def add_simulation_entry(self, prediction: Any, actual: Any, timestamp: Optional[datetime] = None):
        """Record a simulation run and its outcome for this module."""
        entry = {
            "id": str(uuid.uuid4()),
            "timestamp": timestamp or datetime.utcnow(),
            "prediction": prediction,
            "actual": actual,
            "match": prediction == actual
        }
        self.simulation_history.append(entry)
        # Update accuracy based on history
        if self.simulation_history:
            matches = sum(1 for e in self.simulation_history if e["match"])
            self.accuracy = matches / len(self.simulation_history)

    def add_cross_reference(self, prediction: Any, actual: Any, context: Optional[str] = None):
        """Store a cross-reference between a simulation prediction and actual mutation outcome."""
        ref = {
            "id": str(uuid.uuid4()),
            "timestamp": datetime.utcnow(),
            "prediction": prediction,
            "actual": actual,
            "context": context,
            "match": prediction == actual
        }
        self.cross_references.append(ref)

    def add_failure_cluster(self, cluster_id: str):
        """Associate a failure cluster with this module."""
        if cluster_id not in self.failure_clusters:
            self.failure_clusters.append(cluster_id)

    def remove_failure_cluster(self, cluster_id: str):
        """Remove a failure cluster association from this module."""
        if cluster_id in self.failure_clusters:
            self.failure_clusters.remove(cluster_id)


class DependencyEdge:
    """Represents a dependency edge used by the simulation engine between two modules."""

    def __init__(self, source_id: str, target_id: str, weight: float = 1.0):
        self.id = str(uuid.uuid4())
        self.source_id = source_id
        self.target_id = target_id
        self.weight = weight  # Influence weight for simulation propagation


class FailureClusterNode:
    """Represents a failure cluster node in the self-model knowledge graph."""

    def __init__(self, cluster_id: str, description: str = ""):
        self.id = cluster_id
        self.description = description
        self.affected_modules: List[str] = []  # Module IDs affected by this cluster
        self.active: bool = True  # Whether the cluster is currently active

    def add_affected_module(self, module_id: str):
        """Add a module to the list of affected modules."""
        if module_id not in self.affected_modules:
            self.affected_modules.append(module_id)

    def remove_affected_module(self, module_id: str):
        """Remove a module from the list of affected modules."""
        if module_id in self.affected_modules:
            self.affected_modules.remove(module_id)

    def set_active(self, active: bool):
        """Set the active status of the failure cluster."""
        self.active = active


class SelfModelKnowledgeGraph:
    """Manages the self-model knowledge graph with simulation nodes, dependencies, and history."""

    def __init__(self):
        self.nodes: Dict[str, SimulationNode] = {}
        self.edges: List[DependencyEdge] = []
        self.failure_clusters: Dict[str, FailureClusterNode] = {}  # Cluster ID -> FailureClusterNode
        self.module_interfaces: Dict[str, Dict[str, Dict[str, Any]]] = {}  # Module ID -> {function_name: {signature, docstring}}
        self.meta_parameters: Dict[str, Any] = {
            "mutation_rate": 0.1,  # Default value within 0.01-0.5
            "goal_selection_weights": {
                "novelty": 0.4,
                "feasibility": 0.3,
                "impact": 0.3
            },
            "reflection_depth": 3,  # Default value within 1-5
            "parameter_change_history": []  # History of parameter changes with timestamps and fitness outcomes
        }

    def set_mutation_rate(self, rate: float):
        """Set the mutation rate, clamped to valid range 0.01-0.5."""
        self.meta_parameters["mutation_rate"] = max(0.01, min(0.5, rate))

    def get_mutation_rate(self) -> float:
        """Get the current mutation rate."""
        return self.meta_parameters["mutation_rate"]

    def set_goal_selection_weights(self, weights: Dict[str, float]):
        """Set the goal selection weights, ensuring all required keys exist."""
        required_keys = {"novelty", "feasibility", "impact"}
        if not required_keys.issubset(weights.keys()):
            raise ValueError(f"Goal selection weights must contain keys: {required_keys}")
        # Normalize weights to sum to 1.0
        total = sum(weights.values())
        if total > 0:
            normalized = {k: v / total for k, v in weights.items()}
        else:
            normalized = {k: 1.0 / len(weights) for k in weights}
        self.meta_parameters["goal_selection_weights"] = normalized

    def get_goal_selection_weights(self) -> Dict[str, float]:
        """Get the current goal selection weights."""
        return self.meta_parameters["goal_selection_weights"]

    def set_reflection_depth(self, depth: int):
        """Set the reflection depth, clamped to valid range 1-5."""
        self.meta_parameters["reflection_depth"] = max(1, min(5, depth))

    def get_reflection_depth(self) -> int:
        """Get the current reflection depth."""
        return self.meta_parameters["reflection_depth"]

    def record_parameter_change(self, parameter_name: str, old_value: Any, new_value: Any, fitness_outcome: Optional[float] = None):
        """Record a parameter change with timestamp and optional fitness outcome."""
        change_entry = {
            "timestamp": datetime.utcnow(),
            "parameter": parameter_name,
            "old_value": old_value,
            "new_value": new_value,
            "fitness_outcome": fitness_outcome
        }
        self.meta_parameters["parameter_change_history"].append(change_entry)

    def get_parameter_change_history(self) -> List[Dict[str, Any]]:
        """Get the history of parameter changes."""
        return self.meta_parameters["parameter_change_history"]

    def register_module_interface(self, module_id: str, function_name: str, signature: str, docstring: str):
        """Register a function's signature and docstring for a module, enabling the scanner to access this data without re-parsing."""
        if module_id not in self.module_interfaces:
            self.module_interfaces[module_id] = {}
        self.module_interfaces[module_id][function_name] = {
            "signature": signature,
            "docstring": docstring
        }

    def get_module_interface(self, module_id: str) -> Dict[str, Dict[str, Any]]:
        """Retrieve all registered function interfaces for a given module."""
        return self.module_interfaces.get(module_id, {})

    def add_module_node(self, module_id: str, module_name: str, accuracy: float = 0.0) -> SimulationNode:
        """Add a simulation node for a module."""
        if module_id in self.nodes:
            raise ValueError(f"Module node '{module_id}' already exists.")
        node = SimulationNode(module_id, module_name, accuracy)
        self.nodes[module_id] = node
        return node

    def add_dependency_edge(self, source_id: str, target_id: str, weight: float = 1.0) -> DependencyEdge:
        """Add a dependency edge used by the simulation engine."""
        if source_id not in self.nodes:
            raise ValueError(f"Source module '{source_id}' not found.")
        if target_id not in self.nodes:
            raise ValueError(f"Target module '{target_id}' not found.")
        edge = DependencyEdge(source_id, target_id, weight)
        self.edges.append(edge)
        return edge

    def add_failure_cluster(self, cluster_id: str, description: str = "") -> FailureClusterNode:
        """Add a failure cluster node to the knowledge graph."""
        if cluster_id in self.failure_clusters:
            raise ValueError(f"Failure cluster '{cluster_id}' already exists.")
        cluster = FailureClusterNode(cluster_id, description)
        self.failure_clusters[cluster_id] = cluster
        return cluster

    def link_failure_cluster_to_module(self, cluster_id: str, module_id: str):
        """Create a bidirectional link between a failure cluster and a module."""
        if cluster_id not in self.failure_clusters:
            raise ValueError(f"Failure cluster '{cluster_id}' not found.")
        if module_id not in self.nodes:
            raise ValueError(f"Module '{module_id}' not found.")
        cluster = self.failure_clusters[cluster_id]
        module = self.nodes[module_id]
        cluster.add_affected_module(module_id)
        module.add_failure_cluster(cluster_id)

    def unlink_failure_cluster_from_module(self, cluster_id: str, module_id: str):
        """Remove the bidirectional link between a failure cluster and a module."""
        if cluster_id in self.failure_clusters:
            cluster = self.failure_clusters[cluster_id]
            cluster.remove_affected_module(module_id)
        if module_id in self.nodes:
            module = self.nodes[module_id]
            module.remove_failure_cluster(cluster_id)

    def set_failure_cluster_active(self, cluster_id: str, active: bool):
        """Set the active status of a failure cluster."""
        if cluster_id not in self.failure_clusters:
            raise ValueError(f"Failure cluster '{cluster_id}' not found.")
        self.failure_clusters[cluster_id].set_active(active)

    def get_active_failure_clusters_for_module(self, module_id: str) -> List[FailureClusterNode]:
        """Get all active failure clusters affecting a given module."""
        if module_id not in self.nodes:
            raise ValueError(f"Module '{module_id}' not found.")
        module = self.nodes[module_id]
        active_clusters = []
        for cluster_id in module.failure_clusters:
            if cluster_id in self.failure_clusters and self.failure_clusters[cluster_id].active:
                active_clusters.append(self.failure_clusters[cluster_id])
        return active_clusters

    def get_modules_with_active_clusters(self) -> List[str]:
        """Get all module IDs that have at least one active failure cluster."""
        modules_with_clusters = []
        for module_id, module in self.nodes.items():
            if any(cluster_id in self.failure_clusters and self.failure_clusters[cluster_id].active
                   for cluster_id in module.failure_clusters):
                modules_with_clusters.append(module_id)
        return modules_with_clusters

    def get_module_simulation_history(self, module_id: str) -> List[Dict[str, Any]]:
        """Retrieve simulation history for a given module."""
        if module_id not in self.nodes:
            raise ValueError(f"Module '{module_id}' not found.")
        return self.nodes[module_id].simulation_history

    def get_module_cross_references(self, module_id: str) -> List[Dict[str, Any]]:
        """Retrieve cross-references between predictions and actual outcomes for a module."""
        if module_id not in self.nodes:
            raise ValueError(f"Module '{module_id}' not found.")
        return self.nodes[module_id].cross_references

    def get_all_accuracy_metrics(self) -> Dict[str, float]:
        """Return accuracy metrics for all modules."""
        return {mid: node.accuracy for mid, node in self.nodes.items()}

    def get_dependencies_for_module(self, module_id: str) -> List[DependencyEdge]:
        """Get all dependency edges where the module is the source."""
        return [edge for edge in self.edges if edge.source_id == module_id]

    def update_accuracy_from_history(self, module_id: str):
        """Recalculate accuracy for a module based on its simulation history."""
        if module_id not in self.nodes:
            raise ValueError(f"Module '{module_id}' not found.")
        node = self.nodes[module_id]
        if node.simulation_history:
            matches = sum(1 for entry in node.simulation_history if entry["match"])
            node.accuracy = matches / len(node.simulation_history)
        else:
            node.accuracy = 0.0

    def record_simulation_and_cross_reference(self, module_id: str, prediction: Any, actual: Any,
                                              context: Optional[str] = None):
        """Convenience method to record both simulation history and cross-reference."""
        if module_id not in self.nodes:
            raise ValueError(f"Module '{module_id}' not found.")
        node = self.nodes[module_id]
        node.add_simulation_entry(prediction, actual)
        node.add_cross_reference(prediction, actual, context)

    def remove_deleted_capabilities(self, removed_list: List[str]):
        """Remove capabilities (modules) that have been pruned from the knowledge graph."""
        for module_id in removed_list:
            if module_id in self.nodes:
                # Remove all edges associated with this module
                self.edges = [edge for edge in self.edges if edge.source_id != module_id and edge.target_id != module_id]
                # Remove failure cluster links
                module = self.nodes[module_id]
                for cluster_id in module.failure_clusters[:]:
                    self.unlink_failure_cluster_from_module(cluster_id, module_id)
                # Remove the node itself
                del self.nodes[module_id]
                # Remove module interface data
                if module_id in self.module_interfaces:
                    del self.module_interfaces[module_id]

    def update_dependency_counts(self, merged_pairs: List[tuple]):
        """Update dependency counts after merging capabilities, adjusting edges to reflect new capability set."""
        for old_id, new_id in merged_pairs:
            if old_id in self.nodes and new_id in self.nodes:
                # Redirect edges from old_id to new_id
                for edge in self.edges:
                    if edge.source_id == old_id:
                        edge.source_id = new_id
                    if edge.target_id == old_id:
                        edge.target_id = new_id
                # Merge failure clusters from old module to new module
                old_module = self.nodes[old_id]
                new_module = self.nodes[new_id]
                for cluster_id in old_module.failure_clusters:
                    if cluster_id not in new_module.failure_clusters:
                        new_module.add_failure_cluster(cluster_id)
                        if cluster_id in self.failure_clusters:
                            self.failure_clusters[cluster_id].add_affected_module(new_id)
                # Merge module interfaces from old module to new module
                if old_id in self.module_interfaces:
                    if new_id not in self.module_interfaces:
                        self.module_interfaces[new_id] = {}
                    self.module_interfaces[new_id].update(self.module_interfaces[old_id])
                    del self.module_interfaces[old_id]
                # Remove old module
                self.remove_deleted_capabilities([old_id])

    def snapshot_state(self) -> Dict[str, Any]:
        """Serialize the entire self-model state for integration testing."""
        snapshot = {
            "nodes": {},
            "edges": [],
            "failure_clusters": {},
            "module_interfaces": {},
            "meta_parameters": copy.deepcopy(self.meta_parameters)
        }
        # Deep copy nodes to avoid mutation of original data
        for node_id, node in self.nodes.items():
            snapshot["nodes"][node_id] = {
                "id": node.id,
                "name": node.name,
                "accuracy": node.accuracy,
                "simulation_history": copy.deepcopy(node.simulation_history),
                "cross_references": copy.deepcopy(node.cross_references),
                "failure_clusters": copy.deepcopy(node.failure_clusters)
            }
        # Deep copy edges
        for edge in self.edges:
            snapshot["edges"].append({
                "id": edge.id,
                "source_id": edge.source_id,
                "target_id": edge.target_id,
                "weight": edge.weight
            })
        # Deep copy failure clusters
        for cluster_id, cluster in self.failure_clusters.items():
            snapshot["failure_clusters"][cluster_id] = {
                "id": cluster.id,
                "description": cluster.description,
                "affected_modules": copy.deepcopy(cluster.affected_modules),
                "active": cluster.active
            }
        # Deep copy module interfaces
        for module_id, interfaces in self.module_interfaces.items():
            snapshot["module_interfaces"][module_id] = copy.deepcopy(interfaces)
        return snapshot

    def restore_state(self, snapshot: Dict[str, Any]):
        """Reset the self-model state from a snapshot for test cycle reset."""
        # Clear current state
        self.nodes.clear()
        self.edges.clear()
        self.failure_clusters.clear()
        self.module_interfaces.clear()
        self.meta_parameters.clear()
        # Restore meta_parameters
        if "meta_parameters" in snapshot:
            self.meta_parameters = copy.deepcopy(snapshot["meta_parameters"])
        else:
            self.meta_parameters = {
                "mutation_rate": 0.1,
                "goal_selection_weights": {
                    "novelty": 0.4,
                    "feasibility": 0.3,
                    "impact": 0.3
                },
                "reflection_depth": 3,
                "parameter_change_history": []
            }
        # Restore nodes
        for node_id, node_data in snapshot["nodes"].items():
            node = SimulationNode(node_data["id"], node_data["name"], node_data["accuracy"])
            node.simulation_history = copy.deepcopy(node_data["simulation_history"])
            node.cross_references = copy.deepcopy(node_data["cross_references"])
            node.failure_clusters = copy.deepcopy(node_data["failure_clusters"])
            self.nodes[node_id] = node
        # Restore edges
        for edge_data in snapshot["edges"]:
            edge = DependencyEdge(edge_data["source_id"], edge_data["target_id"], edge_data["weight"])
            edge.id = edge_data["id"]
            self.edges.append(edge)
        # Restore failure clusters
        for cluster_id, cluster_data in snapshot["failure_clusters"].items():
            cluster = FailureClusterNode(cluster_data["id"], cluster_data["description"])
            cluster.affected_modules = copy.deepcopy(cluster_data["affected_modules"])
            cluster.active = cluster_data["active"]
            self.failure_clusters[cluster_id] = cluster
        # Restore module interfaces
        if "module_interfaces" in snapshot:
            for module_id, interfaces in snapshot["module_interfaces"].items():
                self.module_interfaces[module_id] = copy.deepcopy(interfaces)

    def validate_consistency(self) -> List[str]:
        """Check for orphaned modules, circular dependencies, and missing schema references.
        Returns a list of inconsistency descriptions."""
        inconsistencies = []
        # Check for orphaned modules (modules not referenced by any edge and not in any failure cluster)
        all_module_ids = set(self.nodes.keys())
        referenced_modules = set()
        for edge in self.edges:
            referenced_modules.add(edge.source_id)
            referenced_modules.add(edge.target_id)
        for cluster in self.failure_clusters.values():
            for mod_id in cluster.affected_modules:
                referenced_modules.add(mod_id)
        orphaned = all_module_ids - referenced_modules
        if orphaned:
            inconsistencies.append(f"Orphaned modules (not referenced by any edge or failure cluster): {sorted(orphaned)}")
        # Check for circular dependencies using DFS
        visited = set()
        rec_stack = set()
        def dfs(node_id, path):
            visited.add(node_id)
            rec_stack.add(node_id)
            for edge in self.edges:
                if edge.source_id == node_id:
                    neighbor = edge.target_id
                    if neighbor not in visited:
                        if dfs(neighbor, path + [neighbor]):
                            return True
                    elif neighbor in rec_stack:
                        # Found a cycle
                        cycle_path = path[path.index(neighbor):] + [neighbor]
                        inconsistencies.append(f"Circular dependency detected: {' -> '.join(cycle_path)}")
                        return True
            rec_stack.discard(node_id)
            return False
        for node_id in self.nodes:
            if node_id not in visited:
                dfs(node_id, [node_id])
        # Check for missing schema references (edges referencing non-existent nodes)
        for edge in self.edges:
            if edge.source_id not in self.nodes:
                inconsistencies.append(f"Edge {edge.id} references non-existent source module '{edge.source_id}'")
            if edge.target_id not in self.nodes:
                inconsistencies.append(f"Edge {edge.id} references non-existent target module '{edge.target_id}'")
        # Check for failure clusters referencing non-existent modules
        for cluster_id, cluster in self.failure_clusters.items():
            for mod_id in cluster.affected_modules:
                if mod_id not in self.nodes:
                    inconsistencies.append(f"Failure cluster '{cluster_id}' references non-existent module '{mod_id}'")
        # Check for modules referencing non-existent failure clusters
        for node_id, node in self.nodes.items():
            for cluster_id in node.failure_clusters:
                if cluster_id not in self.failure_clusters:
                    inconsistencies.append(f"Module '{node_id}' references non-existent failure cluster '{cluster_id}'")
        # Validate meta_parameters consistency
        if "mutation_rate" in self.meta_parameters:
            rate = self.meta_parameters["mutation_rate"]
            if not (0.01 <= rate <= 0.5):
                inconsistencies.append(f"Mutation rate {rate} is outside valid range [0.01, 0.5]")
        if "reflection_depth" in self.meta_parameters:
            depth = self.meta_parameters["reflection_depth"]
            if not (1 <= depth <= 5):
                inconsistencies.append(f"Reflection depth {depth} is outside valid range [1, 5]")
        if "goal_selection_weights" in self.meta_parameters:
            weights = self.meta_parameters["goal_selection_weights"]
            required_keys = {"novelty", "feasibility", "impact"}
            if not required_keys.issubset(weights.keys()):
                inconsistencies.append(f"Goal selection weights missing required keys: {required_keys - set(weights.keys())}")
        return inconsistencies