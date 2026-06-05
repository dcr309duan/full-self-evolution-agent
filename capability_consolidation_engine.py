from collections import defaultdict
import os
import shutil
import json
from datetime import datetime
from typing import Dict, List, Tuple, Optional

class CapabilityConsolidationEngine:
    """
    Core consolidation engine that manages capability lifecycle, merging low-impact
    capabilities into abstract capabilities to optimize the capability registry.
    """

    def __init__(self, registry_path: str = "capability_registry.json",
                 archive_dir: str = "archive",
                 dependency_graph_path: str = "dependency_graph.json",
                 max_capabilities: int = 20):
        self.registry_path = registry_path
        self.archive_dir = archive_dir
        self.dependency_graph_path = dependency_graph_path
        self.max_capabilities = max_capabilities
        self.registry: Dict[str, Dict] = {}
        self.dependency_graph: Dict[str, List[str]] = defaultdict(list)
        self._load_registry()
        self._load_dependency_graph()

    def _load_registry(self):
        """Load capability registry from file if exists."""
        if os.path.exists(self.registry_path):
            with open(self.registry_path, 'r') as f:
                self.registry = json.load(f)
        else:
            self.registry = {}

    def _save_registry(self):
        """Persist capability registry to file."""
        with open(self.registry_path, 'w') as f:
            json.dump(self.registry, f, indent=2)

    def _load_dependency_graph(self):
        """Load dependency graph from file if exists."""
        if os.path.exists(self.dependency_graph_path):
            with open(self.dependency_graph_path, 'r') as f:
                self.dependency_graph = defaultdict(list, json.load(f))
        else:
            self.dependency_graph = defaultdict(list)

    def _save_dependency_graph(self):
        """Persist dependency graph to file."""
        with open(self.dependency_graph_path, 'w') as f:
            json.dump(dict(self.dependency_graph), f, indent=2)

    def register_capability(self, name: str, implementation_path: str,
                            usage_frequency: float = 0.0,
                            failure_rate: float = 0.0,
                            dependencies: List[str] = None):
        """
        Register a new capability with initial metrics.
        
        Args:
            name: Unique capability identifier
            implementation_path: Path to the capability implementation file
            usage_frequency: How often the capability is used (0.0 to 1.0)
            failure_rate: Rate of failures (0.0 to 1.0)
            dependencies: List of capability names this depends on
        """
        if name in self.registry:
            raise ValueError(f"Capability '{name}' already exists in registry")
        
        self.registry[name] = {
            "name": name,
            "implementation_path": implementation_path,
            "usage_frequency": usage_frequency,
            "failure_rate": failure_rate,
            "created_at": datetime.now().isoformat(),
            "is_abstract": False,
            "merged_from": []
        }
        
        if dependencies:
            self.dependency_graph[name] = dependencies
            for dep in dependencies:
                if dep not in self.registry:
                    raise ValueError(f"Dependency '{dep}' not found in registry")
        
        self._save_registry()
        self._save_dependency_graph()

    def update_metrics(self, name: str, usage_frequency: float = None,
                       failure_rate: float = None):
        """Update usage frequency and/or failure rate for a capability."""
        if name not in self.registry:
            raise ValueError(f"Capability '{name}' not found in registry")
        
        if usage_frequency is not None:
            self.registry[name]["usage_frequency"] = max(0.0, min(1.0, usage_frequency))
        if failure_rate is not None:
            self.registry[name]["failure_rate"] = max(0.0, min(1.0, failure_rate))
        
        self._save_registry()

    def _calculate_weighted_score(self, capability_name: str) -> float:
        """Calculate weighted score for a capability."""
        cap = self.registry[capability_name]
        return cap["usage_frequency"] * 0.3 + cap["failure_rate"] * 0.7

    def _select_low_impact_capabilities(self) -> Optional[Tuple[str, str]]:
        """
        Select 2 low-impact capabilities based on weighted score.
        Returns tuple of capability names or None if insufficient candidates.
        """
        # Filter out abstract capabilities and those already merged
        candidates = [
            name for name, cap in self.registry.items()
            if not cap.get("is_abstract", False) and not cap.get("merged_from")
        ]
        
        if len(candidates) < 2:
            return None
        
        # Sort by weighted score (ascending) and take lowest 2
        candidates.sort(key=lambda name: self._calculate_weighted_score(name))
        return candidates[0], candidates[1]

    def _generate_merged_abstract_capability(self, cap1_name: str,
                                              cap2_name: str) -> str:
        """
        Generate a merged abstract capability name combining core functionality.
        """
        cap1 = self.registry[cap1_name]
        cap2 = self.registry[cap2_name]
        
        # Extract core names (remove path and extension)
        core1 = os.path.splitext(os.path.basename(cap1["implementation_path"]))[0]
        core2 = os.path.splitext(os.path.basename(cap2["implementation_path"]))[0]
        
        # Create abstract name
        abstract_name = f"abstract_{core1}_{core2}"
        
        # Ensure uniqueness
        counter = 1
        while abstract_name in self.registry:
            abstract_name = f"abstract_{core1}_{core2}_{counter}"
            counter += 1
        
        return abstract_name

    def _archive_original_implementations(self, cap1_name: str, cap2_name: str):
        """Move original implementation files to archive directory."""
        os.makedirs(self.archive_dir, exist_ok=True)
        
        for cap_name in [cap1_name, cap2_name]:
            impl_path = self.registry[cap_name]["implementation_path"]
            if os.path.exists(impl_path):
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                archive_name = f"{cap_name}_{timestamp}{os.path.splitext(impl_path)[1]}"
                archive_path = os.path.join(self.archive_dir, archive_name)
                shutil.move(impl_path, archive_path)
                self.registry[cap_name]["archived_path"] = archive_path

    def _update_registry_and_graph(self, abstract_name: str,
                                    cap1_name: str, cap2_name: str):
        """Update registry and dependency graph after consolidation."""
        # Mark original capabilities as merged
        for cap_name in [cap1_name, cap2_name]:
            self.registry[cap_name]["merged_into"] = abstract_name
        
        # Create abstract capability entry
        abstract_impl_path = f"implementations/{abstract_name}.py"
        os.makedirs("implementations", exist_ok=True)
        
        # Create abstract implementation file
        with open(abstract_impl_path, 'w') as f:
            f.write(f"# Abstract capability: {abstract_name}\n")
            f.write(f"# Merged from: {cap1_name}, {cap2_name}\n")
            f.write(f"# Created: {datetime.now().isoformat()}\n")
            f.write("\ndef execute(input_data=None):\n")
            f.write('    """Execute the abstract capability.\n')
            f.write("    This is a placeholder for the merged functionality.\n")
            f.write("    \"\"\"\n")
            f.write("    # TODO: Implement merged logic\n")
            f.write("    pass\n")
        
        # Calculate abstract metrics (average of merged capabilities)
        avg_frequency = (self.registry[cap1_name]["usage_frequency"] +
                         self.registry[cap2_name]["usage_frequency"]) / 2
        avg_failure = (self.registry[cap1_name]["failure_rate"] +
                       self.registry[cap2_name]["failure_rate"]) / 2
        
        self.registry[abstract_name] = {
            "name": abstract_name,
            "implementation_path": abstract_impl_path,
            "usage_frequency": avg_frequency,
            "failure_rate": avg_failure,
            "created_at": datetime.now().isoformat(),
            "is_abstract": True,
            "merged_from": [cap1_name, cap2_name]
        }
        
        # Update dependency graph
        combined_deps = set()
        for cap_name in [cap1_name, cap2_name]:
            combined_deps.update(self.dependency_graph.get(cap_name, []))
        # Remove self-references
        combined_deps.discard(cap1_name)
        combined_deps.discard(cap2_name)
        self.dependency_graph[abstract_name] = list(combined_deps)
        
        # Update dependents to point to abstract capability
        for dependent, deps in self.dependency_graph.items():
            updated_deps = []
            for dep in deps:
                if dep in [cap1_name, cap2_name]:
                    updated_deps.append(abstract_name)
                else:
                    updated_deps.append(dep)
            self.dependency_graph[dependent] = updated_deps
        
        self._save_registry()
        self._save_dependency_graph()

    def run_consolidation_cycle(self) -> Optional[str]:
        """
        Run one consolidation cycle if conditions are met.
        Returns the name of the created abstract capability or None.
        """
        # Check if consolidation is needed
        active_capabilities = [
            name for name, cap in self.registry.items()
            if not cap.get("merged_into")
        ]
        
        if len(active_capabilities) <= self.max_capabilities:
            return None
        
        # Select low-impact capabilities
        selected = self._select_low_impact_capabilities()
        if selected is None:
            return None
        
        cap1_name, cap2_name = selected
        
        # Generate abstract capability
        abstract_name = self._generate_merged_abstract_capability(cap1_name, cap2_name)
        
        # Archive original implementations
        self._archive_original_implementations(cap1_name, cap2_name)
        
        # Update registry and graph
        self._update_registry_and_graph(abstract_name, cap1_name, cap2_name)
        
        return abstract_name

    def get_registry_summary(self) -> Dict:
        """Get a summary of the current capability registry."""
        active = [name for name, cap in self.registry.items()
                  if not cap.get("merged_into")]
        archived = [name for name, cap in self.registry.items()
                    if cap.get("merged_into")]
        
        return {
            "total_capabilities": len(self.registry),
            "active_capabilities": len(active),
            "archived_capabilities": len(archived),
            "abstract_capabilities": len([c for c in self.registry.values()
                                          if c.get("is_abstract")]),
            "active_list": active,
            "archived_list": archived
        }

    def get_low_impact_candidates(self, count: int = 2) -> List[str]:
        """Get the lowest impact capabilities based on weighted score."""
        candidates = [
            name for name, cap in self.registry.items()
            if not cap.get("is_abstract", False) and not cap.get("merged_into")
        ]
        candidates.sort(key=lambda name: self._calculate_weighted_score(name))
        return candidates[:count]