"""System model extension for integration test coverage, schema alignment, and capability prerequisites.

This module extends the system model/knowledge graph with:
1. Integration test coverage matrix per component pair
2. Schema alignment version/status for each data flow
3. Prerequisite relationships between capabilities

This serves as the data source for the feasibility estimator.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple
from datetime import datetime


class TestCoverageLevel(Enum):
    """Level of integration test coverage between component pairs."""
    NONE = "none"
    PARTIAL = "partial"
    ADEQUATE = "adequate"
    COMPREHENSIVE = "comprehensive"


class SchemaAlignmentStatus(Enum):
    """Status of schema alignment for data flows."""
    UNALIGNED = "unaligned"
    IN_PROGRESS = "in_progress"
    ALIGNED = "aligned"
    VERSION_MISMATCH = "version_mismatch"


class CapabilityStatus(Enum):
    """Status of a capability in the system."""
    PROPOSED = "proposed"
    IN_DEVELOPMENT = "in_development"
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    REMOVED = "removed"


@dataclass
class IntegrationTestCoverage:
    """Coverage matrix entry for integration tests between two components."""
    source_component: str
    target_component: str
    coverage_level: TestCoverageLevel
    test_count: int = 0
    passing_tests: int = 0
    last_test_run: Optional[datetime] = None
    test_suite_path: Optional[str] = None
    
    @property
    def pass_rate(self) -> float:
        """Calculate test pass rate."""
        if self.test_count == 0:
            return 0.0
        return self.passing_tests / self.test_count
    
    @property
    def is_healthy(self) -> bool:
        """Check if integration coverage is healthy."""
        return (self.coverage_level in (TestCoverageLevel.ADEQUATE, TestCoverageLevel.COMPREHENSIVE) 
                and self.pass_rate >= 0.9)


@dataclass
class SchemaAlignment:
    """Schema alignment information for a data flow."""
    data_flow_id: str
    source_schema_version: str
    target_schema_version: str
    alignment_status: SchemaAlignmentStatus
    last_alignment_check: Optional[datetime] = None
    alignment_notes: Optional[str] = None
    breaking_changes_detected: bool = False
    
    @property
    def is_compatible(self) -> bool:
        """Check if schemas are compatible."""
        return (self.alignment_status == SchemaAlignmentStatus.ALIGNED 
                and not self.breaking_changes_detected)


@dataclass
class CapabilityNode:
    """Represents a capability in the system with its prerequisites."""
    capability_id: str
    name: str
    description: str
    status: CapabilityStatus = CapabilityStatus.PROPOSED
    prerequisites: Set[str] = field(default_factory=set)  # Set of capability_ids
    dependents: Set[str] = field(default_factory=set)  # Capabilities that depend on this
    estimated_effort: Optional[float] = None  # Person-days
    implementation_progress: float = 0.0  # 0.0 to 1.0
    
    def add_prerequisite(self, capability_id: str) -> None:
        """Add a prerequisite capability."""
        if capability_id == self.capability_id:
            raise ValueError("A capability cannot be a prerequisite of itself")
        self.prerequisites.add(capability_id)
    
    def add_dependent(self, capability_id: str) -> None:
        """Add a dependent capability."""
        if capability_id == self.capability_id:
            raise ValueError("A capability cannot depend on itself")
        self.dependents.add(capability_id)
    
    @property
    def is_ready(self) -> bool:
        """Check if capability is ready to be implemented (all prerequisites met)."""
        return len(self.prerequisites) == 0  # Simplified; actual check needs graph traversal
    
    @property
    def completion_percentage(self) -> float:
        """Get implementation completion percentage."""
        return min(100.0, self.implementation_progress * 100)


@dataclass
class DataFlow:
    """Represents a data flow between two components."""
    flow_id: str
    source_component: str
    target_component: str
    schema_alignment: Optional[SchemaAlignment] = None
    integration_coverage: Optional[IntegrationTestCoverage] = None
    description: Optional[str] = None
    data_volume_estimate: Optional[str] = None  # e.g., "low", "medium", "high"
    frequency: Optional[str] = None  # e.g., "real-time", "batch", "on-demand"


class SystemModel:
    """Extended system model with integration coverage, schema alignment, and capability prerequisites."""
    
    def __init__(self):
        self.components: Dict[str, Set[str]] = {}  # component -> set of connected components
        self.data_flows: Dict[str, DataFlow] = {}
        self.capabilities: Dict[str, CapabilityNode] = {}
        self.integration_coverage_matrix: Dict[Tuple[str, str], IntegrationTestCoverage] = {}
        self.schema_alignments: Dict[str, SchemaAlignment] = {}
        
    def add_component(self, component_id: str) -> None:
        """Add a component to the system model."""
        if component_id not in self.components:
            self.components[component_id] = set()
    
    def add_data_flow(self, flow: DataFlow) -> None:
        """Add a data flow between components."""
        self.data_flows[flow.flow_id] = flow
        # Update component connections
        if flow.source_component not in self.components:
            self.add_component(flow.source_component)
        if flow.target_component not in self.components:
            self.add_component(flow.target_component)
        self.components[flow.source_component].add(flow.target_component)
        
        # Store integration coverage if present
        if flow.integration_coverage:
            key = (flow.source_component, flow.target_component)
            self.integration_coverage_matrix[key] = flow.integration_coverage
        
        # Store schema alignment if present
        if flow.schema_alignment:
            self.schema_alignments[flow.flow_id] = flow.schema_alignment
    
    def add_capability(self, capability: CapabilityNode) -> None:
        """Add a capability to the system model."""
        self.capabilities[capability.capability_id] = capability
        
        # Update prerequisite relationships
        for prereq_id in capability.prerequisites:
            if prereq_id in self.capabilities:
                self.capabilities[prereq_id].add_dependent(capability.capability_id)
    
    def get_integration_coverage(self, source: str, target: str) -> Optional[IntegrationTestCoverage]:
        """Get integration test coverage between two components."""
        return self.integration_coverage_matrix.get((source, target))
    
    def get_schema_alignment(self, flow_id: str) -> Optional[SchemaAlignment]:
        """Get schema alignment for a data flow."""
        return self.schema_alignments.get(flow_id)
    
    def get_capability_prerequisites(self, capability_id: str) -> Set[str]:
        """Get all prerequisites for a capability (direct and transitive)."""
        if capability_id not in self.capabilities:
            return set()
        
        capability = self.capabilities[capability_id]
        all_prereqs = set(capability.prerequisites)
        
        # Traverse transitive prerequisites
        visited = set()
        to_visit = list(capability.prerequisites)
        
        while to_visit:
            current = to_visit.pop()
            if current in visited or current not in self.capabilities:
                continue
            visited.add(current)
            
            current_cap = self.capabilities[current]
            for prereq in current_cap.prerequisites:
                if prereq not in visited:
                    all_prereqs.add(prereq)
                    to_visit.append(prereq)
        
        return all_prereqs
    
    def get_capability_dependents(self, capability_id: str) -> Set[str]:
        """Get all capabilities that depend on this one (direct and transitive)."""
        if capability_id not in self.capabilities:
            return set()
        
        capability = self.capabilities[capability_id]
        all_dependents = set(capability.dependents)
        
        # Traverse transitive dependents
        visited = set()
        to_visit = list(capability.dependents)
        
        while to_visit:
            current = to_visit.pop()
            if current in visited or current not in self.capabilities:
                continue
            visited.add(current)
            
            current_cap = self.capabilities[current]
            for dep in current_cap.dependents:
                if dep not in visited:
                    all_dependents.add(dep)
                    to_visit.append(dep)
        
        return all_dependents
    
    def get_ready_capabilities(self) -> List[CapabilityNode]:
        """Get capabilities that are ready to be implemented (all prerequisites met)."""
        ready = []
        for cap in self.capabilities.values():
            if cap.is_ready and cap.status == CapabilityStatus.PROPOSED:
                ready.append(cap)
        return ready
    
    def get_uncovered_integrations(self) -> List[Tuple[str, str]]:
        """Get component pairs that lack adequate integration test coverage."""
        uncovered = []
        for source, targets in self.components.items():
            for target in targets:
                coverage = self.get_integration_coverage(source, target)
                if coverage is None or coverage.coverage_level == TestCoverageLevel.NONE:
                    uncovered.append((source, target))
        return uncovered
    
    def get_schema_mismatches(self) -> List[SchemaAlignment]:
        """Get data flows with schema alignment issues."""
        mismatches = []
        for alignment in self.schema_alignments.values():
            if not alignment.is_compatible:
                mismatches.append(alignment)
        return mismatches
    
    def get_critical_path(self) -> List[CapabilityNode]:
        """Get the critical path of capabilities (longest dependency chain)."""
        # Simple topological sort based approach
        visited = set()
        path = []
        
        def dfs(cap_id: str, current_path: List[CapabilityNode]) -> None:
            if cap_id in visited:
                return
            visited.add(cap_id)
            
            cap = self.capabilities.get(cap_id)
            if cap is None:
                return
            
            current_path.append(cap)
            
            if not cap.dependents:
                # Leaf node - check if this path is longer
                if len(current_path) > len(path):
                    path.clear()
                    path.extend(current_path)
            else:
                for dep_id in cap.dependents:
                    dfs(dep_id, current_path)
            
            current_path.pop()
        
        # Start from capabilities with no prerequisites
        for cap in self.capabilities.values():
            if not cap.prerequisites:
                dfs(cap.capability_id, [])
        
        return path
    
    def to_dict(self) -> Dict:
        """Serialize the system model to a dictionary."""
        return {
            "components": list(self.components.keys()),
            "data_flows": {
                fid: {
                    "flow_id": flow.flow_id,
                    "source": flow.source_component,
                    "target": flow.target_component,
                    "description": flow.description,
                    "data_volume": flow.data_volume_estimate,
                    "frequency": flow.frequency
                }
                for fid, flow in self.data_flows.items()
            },
            "capabilities": {
                cid: {
                    "name": cap.name,
                    "description": cap.description,
                    "status": cap.status.value,
                    "prerequisites": list(cap.prerequisites),
                    "dependents": list(cap.dependents),
                    "progress": cap.implementation_progress
                }
                for cid, cap in self.capabilities.items()
            },
            "integration_coverage": {
                f"{src}->{tgt}": {
                    "level": cov.coverage_level.value,
                    "test_count": cov.test_count,
                    "pass_rate": cov.pass_rate
                }
                for (src, tgt), cov in self.integration_coverage_matrix.items()
            },
            "schema_alignments": {
                fid: {
                    "status": align.alignment_status.value,
                    "source_version": align.source_schema_version,
                    "target_version": align.target_schema_version,
                    "compatible": align.is_compatible
                }
                for fid, align in self.schema_alignments.items()
            }
        }