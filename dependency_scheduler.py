import json
from typing import List, Dict, Set, Optional, Tuple
from collections import defaultdict, deque


class DependencyScheduler:
    """
    A scheduler that manages module dependencies based on a manifest file.
    Provides methods to determine execution order, identify blocked modules,
    find bottlenecks, and verify prerequisite states.
    """

    def __init__(self, manifest_path: str = "dependency_manifest.json"):
        """
        Initialize the scheduler by loading the dependency manifest.

        Args:
            manifest_path: Path to the JSON manifest file containing dependency definitions.
        """
        self.manifest_path = manifest_path
        self.modules: Dict[str, Dict] = {}
        self.dependencies: Dict[str, List[str]] = {}
        self.dependents: Dict[str, List[str]] = {}
        self._load_manifest()

    def _load_manifest(self) -> None:
        """
        Load and parse the dependency manifest JSON file.
        Expected format:
        {
            "modules": {
                "module_name": {
                    "prerequisites": ["prereq1", "prereq2"],
                    "description": "optional description"
                }
            }
        }
        """
        try:
            with open(self.manifest_path, 'r') as f:
                data = json.load(f)
        except FileNotFoundError:
            raise FileNotFoundError(f"Manifest file '{self.manifest_path}' not found.")
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in manifest file: {e}")

        if "modules" not in data:
            raise ValueError("Manifest must contain a 'modules' key.")

        self.modules = data["modules"]
        self.dependencies = {}
        self.dependents = defaultdict(list)

        for module_name, module_info in self.modules.items():
            prereqs = module_info.get("prerequisites", [])
            self.dependencies[module_name] = prereqs
            for prereq in prereqs:
                self.dependents[prereq].append(module_name)

        # Validate that all referenced prerequisites exist
        all_module_names = set(self.modules.keys())
        for module_name, prereqs in self.dependencies.items():
            for prereq in prereqs:
                if prereq not in all_module_names:
                    raise ValueError(
                        f"Module '{module_name}' has prerequisite '{prereq}' "
                        f"which is not defined in the manifest."
                    )

    def _compute_dependency_depth(self) -> Dict[str, int]:
        """
        Compute the dependency depth for each module using topological sorting.
        Depth is defined as the longest path from a module to any leaf (module with no dependents).

        Returns:
            Dictionary mapping module names to their dependency depth.
        """
        # Build in-degree count for topological sort
        in_degree = {name: 0 for name in self.modules}
        for name, prereqs in self.dependencies.items():
            in_degree[name] = len(prereqs)

        # Initialize queue with modules that have no prerequisites
        queue = deque([name for name, deg in in_degree.items() if deg == 0])
        depth = {name: 0 for name in self.modules}
        topo_order = []

        while queue:
            current = queue.popleft()
            topo_order.append(current)
            for dependent in self.dependents.get(current, []):
                in_degree[dependent] -= 1
                depth[dependent] = max(depth[dependent], depth[current] + 1)
                if in_degree[dependent] == 0:
                    queue.append(dependent)

        # Check for cycles
        if len(topo_order) != len(self.modules):
            raise ValueError("Circular dependency detected in the manifest.")

        return depth

    def get_mutation_queue(self) -> List[str]:
        """
        Return modules sorted by dependency depth (prerequisites first).
        Modules with no prerequisites come first, followed by those that depend on them.

        Returns:
            List of module names in execution order (prerequisites before dependents).
        """
        depth = self._compute_dependency_depth()
        # Sort by depth ascending (prerequisites first)
        sorted_modules = sorted(depth.keys(), key=lambda m: depth[m])
        return sorted_modules

    def get_blocked_modules(self, pending_changes: Set[str]) -> List[str]:
        """
        Identify modules whose prerequisites have pending changes.

        Args:
            pending_changes: Set of module names that have pending changes.

        Returns:
            List of module names that are blocked because at least one prerequisite
            has pending changes.
        """
        blocked = []
        for module_name, prereqs in self.dependencies.items():
            if any(prereq in pending_changes for prereq in prereqs):
                blocked.append(module_name)
        return blocked

    def get_bottleneck(self) -> Optional[str]:
        """
        Find the module with the most dependencies blocking it.
        This is determined by counting how many modules depend on each module
        (i.e., have it as a prerequisite). The module with the most dependents
        is considered the bottleneck.

        Returns:
            The name of the module with the most dependents, or None if no modules exist.
        """
        if not self.modules:
            return None

        max_dependents = -1
        bottleneck = None
        for module_name, dependents_list in self.dependents.items():
            if len(dependents_list) > max_dependents:
                max_dependents = len(dependents_list)
                bottleneck = module_name
        return bottleneck

    def verify_prerequisites(self, module_name: str, state_store: Dict[str, str]) -> bool:
        """
        Check if all prerequisites of a given module are in a 'verified_consistent' state.

        Args:
            module_name: The name of the module to check.
            state_store: A dictionary mapping module names to their current state.
                         Expected states include 'verified_consistent', 'pending', etc.

        Returns:
            True if all prerequisites are in 'verified_consistent' state, False otherwise.
        """
        if module_name not in self.modules:
            raise ValueError(f"Module '{module_name}' not found in manifest.")

        prereqs = self.dependencies.get(module_name, [])
        for prereq in prereqs:
            state = state_store.get(prereq)
            if state != "verified_consistent":
                return False
        return True

    def get_all_modules(self) -> List[str]:
        """Return a list of all module names in the manifest."""
        return list(self.modules.keys())

    def get_prerequisites(self, module_name: str) -> List[str]:
        """Return the list of prerequisites for a given module."""
        if module_name not in self.modules:
            raise ValueError(f"Module '{module_name}' not found in manifest.")
        return self.dependencies.get(module_name, [])

    def get_dependents(self, module_name: str) -> List[str]:
        """Return the list of modules that depend on the given module."""
        if module_name not in self.modules:
            raise ValueError(f"Module '{module_name}' not found in manifest.")
        return self.dependents.get(module_name, [])