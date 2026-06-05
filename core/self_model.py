from typing import Dict, List, Optional, Any
from datetime import datetime
import uuid


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