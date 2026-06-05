from typing import List, Dict, Tuple, Optional
from collections import defaultdict, deque
import math

class PriorityAssigner:
    """
    Assigns priorities to modules/tasks based on:
    1. Topological sort for base priority (dependencies first)
    2. Critical path adjustments (longest dependency chain)
    3. Module readiness (low-readiness modules get higher priority for foundational work)
    """

    def __init__(self, dependencies: Dict[str, List[str]], readiness: Dict[str, float]):
        """
        Args:
            dependencies: dict mapping module name to list of its dependencies (modules it depends on)
            readiness: dict mapping module name to readiness score (0.0 = not ready, 1.0 = fully ready)
        """
        self.dependencies = dependencies
        self.readiness = readiness
        self.modules = list(dependencies.keys())
        self._validate_inputs()

    def _validate_inputs(self) -> None:
        """Validate that all modules have corresponding readiness scores and no missing dependencies."""
        for module in self.modules:
            if module not in self.readiness:
                raise ValueError(f"Module '{module}' missing readiness score")
            for dep in self.dependencies[module]:
                if dep not in self.modules:
                    raise ValueError(f"Dependency '{dep}' for module '{module}' not in modules list")

    def _topological_sort(self) -> List[str]:
        """
        Perform topological sort using Kahn's algorithm.
        Returns modules in dependency order (dependencies first).
        """
        # Build in-degree count and adjacency list
        in_degree = {m: 0 for m in self.modules}
        adj_list = defaultdict(list)

        for module, deps in self.dependencies.items():
            for dep in deps:
                adj_list[dep].append(module)
                in_degree[module] += 1

        # Start with modules that have no dependencies
        queue = deque([m for m in self.modules if in_degree[m] == 0])
        topo_order = []

        while queue:
            module = queue.popleft()
            topo_order.append(module)
            for neighbor in adj_list[module]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if len(topo_order) != len(self.modules):
            raise ValueError("Circular dependency detected in module dependencies")

        return topo_order

    def _compute_critical_path_lengths(self) -> Dict[str, int]:
        """
        Compute the length of the longest dependency chain (critical path) ending at each module.
        Uses DP on the reversed dependency graph.
        """
        # Build reverse dependency graph (module -> dependents)
        reverse_deps = defaultdict(list)
        for module, deps in self.dependencies.items():
            for dep in deps:
                reverse_deps[dep].append(module)

        # Topological order for DP (dependencies first)
        topo_order = self._topological_sort()
        # DP: longest path ending at this module (including itself)
        longest_path = {m: 1 for m in self.modules}

        for module in topo_order:
            for dep in self.dependencies[module]:
                # The module depends on dep, so path to module includes path to dep + 1
                longest_path[module] = max(longest_path[module], longest_path[dep] + 1)

        return longest_path

    def _compute_base_priority(self, topo_order: List[str]) -> Dict[str, float]:
        """
        Compute base priority from topological order.
        Earlier in topological order = higher priority (lower index = higher priority).
        Returns priority scores where lower is higher priority.
        """
        base_priority = {}
        for idx, module in enumerate(topo_order):
            # Invert so that first in order gets highest priority (lowest score)
            base_priority[module] = idx
        return base_priority

    def _compute_critical_path_adjustment(self, critical_path_lengths: Dict[str, int]) -> Dict[str, float]:
        """
        Compute adjustment factor based on critical path length.
        Modules on longer critical paths get higher priority (lower adjustment score).
        """
        if not critical_path_lengths:
            return {}

        max_length = max(critical_path_lengths.values())
        if max_length == 0:
            return {m: 0.0 for m in self.modules}

        adjustment = {}
        for module, length in critical_path_lengths.items():
            # Normalize: longer path = higher priority = more negative adjustment
            # Scale from 0 (shortest path) to -1 (longest path)
            adjustment[module] = -(length / max_length)
        return adjustment

    def _compute_readiness_adjustment(self) -> Dict[str, float]:
        """
        Compute adjustment based on module readiness.
        Low-readiness modules get higher priority (more negative adjustment) for foundational work.
        """
        if not self.readiness:
            return {}

        readiness_values = list(self.readiness.values())
        min_readiness = min(readiness_values)
        max_readiness = max(readiness_values)
        range_readiness = max_readiness - min_readiness

        adjustment = {}
        for module, readiness in self.readiness.items():
            if range_readiness == 0:
                # All modules have same readiness, no adjustment
                adjustment[module] = 0.0
            else:
                # Normalize: lower readiness = higher priority = more negative adjustment
                # Scale from 0 (max readiness) to -1 (min readiness)
                normalized = (readiness - min_readiness) / range_readiness
                adjustment[module] = -(1 - normalized)  # Invert so low readiness gives -1
        return adjustment

    def assign_priorities(self, 
                          critical_path_weight: float = 1.0, 
                          readiness_weight: float = 1.0) -> List[Tuple[str, float]]:
        """
        Assign priorities to all modules and return ordered list with priority scores.

        Priority score = base_priority + critical_path_adjustment * weight + readiness_adjustment * weight
        Lower score = higher priority.

        Args:
            critical_path_weight: weight for critical path adjustment (default 1.0)
            readiness_weight: weight for readiness adjustment (default 1.0)

        Returns:
            List of (module_name, priority_score) sorted by priority (highest first)
        """
        # Step 1: Topological sort for base priority
        topo_order = self._topological_sort()
        base_priority = self._compute_base_priority(topo_order)

        # Step 2: Critical path lengths
        critical_path_lengths = self._compute_critical_path_lengths()
        critical_adjustment = self._compute_critical_path_adjustment(critical_path_lengths)

        # Step 3: Readiness adjustment
        readiness_adjustment = self._compute_readiness_adjustment()

        # Combine all factors
        priority_scores = {}
        for module in self.modules:
            score = base_priority[module]
            score += critical_adjustment.get(module, 0.0) * critical_path_weight
            score += readiness_adjustment.get(module, 0.0) * readiness_weight
            priority_scores[module] = score

        # Sort by priority score (lower = higher priority)
        sorted_modules = sorted(priority_scores.items(), key=lambda x: x[1])

        return sorted_modules

    def get_ordered_list(self, 
                         critical_path_weight: float = 1.0, 
                         readiness_weight: float = 1.0) -> List[str]:
        """
        Convenience method to get just the ordered list of module names.

        Args:
            critical_path_weight: weight for critical path adjustment
            readiness_weight: weight for readiness adjustment

        Returns:
            List of module names in priority order (highest priority first)
        """
        priorities = self.assign_priorities(critical_path_weight, readiness_weight)
        return [module for module, _ in priorities]