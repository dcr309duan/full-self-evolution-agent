"""
self_model_knowledge_graph.py

Extends the knowledge graph to include 'coordination_potential' edges between modules
that are tightly coupled based on shared interfaces, data formats, or call graphs.
This provides the coordinated planner with a pre-computed map of which modules are
good candidates for simultaneous mutation.
"""

import ast
import os
from typing import Dict, List, Set, Tuple, Optional
from dataclasses import dataclass, field
from collections import defaultdict


@dataclass
class ModuleInfo:
    """Represents information about a module in the knowledge graph."""
    name: str
    file_path: str
    imports: Set[str] = field(default_factory=set)
    exported_names: Set[str] = field(default_factory=set)
    used_names: Set[str] = field(default_factory=set)
    function_calls: Set[str] = field(default_factory=set)
    class_definitions: Set[str] = field(default_factory=set)
    data_format_refs: Set[str] = field(default_factory=set)


class KnowledgeGraphExtender:
    """
    Extends the knowledge graph by analyzing Python modules for tight coupling
    and adding 'coordination_potential' edges between tightly coupled modules.
    """

    def __init__(self, source_dir: str):
        self.source_dir = source_dir
        self.modules: Dict[str, ModuleInfo] = {}
        self.coordination_edges: List[Tuple[str, str, float]] = []
        self._discover_modules()

    def _discover_modules(self) -> None:
        """Walk through source directory and discover all Python modules."""
        for root, dirs, files in os.walk(self.source_dir):
            for file in files:
                if file.endswith('.py') and not file.startswith('__'):
                    file_path = os.path.join(root, file)
                    module_name = self._path_to_module_name(file_path)
                    self.modules[module_name] = ModuleInfo(
                        name=module_name,
                        file_path=file_path
                    )

    def _path_to_module_name(self, file_path: str) -> str:
        """Convert a file path to a Python module name."""
        relative_path = os.path.relpath(file_path, self.source_dir)
        module_name = relative_path.replace(os.sep, '.')
        if module_name.endswith('.py'):
            module_name = module_name[:-3]
        return module_name

    def analyze_modules(self) -> None:
        """Analyze all discovered modules for coupling information."""
        for module_name, module_info in self.modules.items():
            self._analyze_single_module(module_info)

    def _analyze_single_module(self, module_info: ModuleInfo) -> None:
        """Parse a single module and extract coupling information."""
        try:
            with open(module_info.file_path, 'r', encoding='utf-8') as f:
                tree = ast.parse(f.read(), filename=module_info.file_path)
        except (SyntaxError, FileNotFoundError, UnicodeDecodeError):
            return

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    module_info.imports.add(alias.name.split('.')[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    module_info.imports.add(node.module.split('.')[0])
                    for alias in node.names:
                        module_info.used_names.add(alias.name)
            elif isinstance(node, ast.FunctionDef):
                module_info.exported_names.add(node.name)
                self._extract_function_calls(node, module_info)
            elif isinstance(node, ast.ClassDef):
                module_info.class_definitions.add(node.name)
                module_info.exported_names.add(node.name)
                for item in node.body:
                    if isinstance(item, ast.FunctionDef):
                        self._extract_function_calls(item, module_info)
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Attribute):
                    module_info.function_calls.add(node.func.attr)
                elif isinstance(node.func, ast.Name):
                    module_info.function_calls.add(node.func.id)

    def _extract_function_calls(self, func_node: ast.FunctionDef, module_info: ModuleInfo) -> None:
        """Extract function calls from a function definition."""
        for node in ast.walk(func_node):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Attribute):
                    module_info.function_calls.add(node.func.attr)
                elif isinstance(node.func, ast.Name):
                    module_info.function_calls.add(node.func.id)

    def _calculate_interface_overlap(self, mod_a: ModuleInfo, mod_b: ModuleInfo) -> float:
        """Calculate the overlap of exported/used interfaces between two modules."""
        if not mod_a.exported_names or not mod_b.used_names:
            return 0.0

        common = mod_a.exported_names & mod_b.used_names
        total = mod_a.exported_names | mod_b.used_names
        return len(common) / len(total) if total else 0.0

    def _calculate_data_format_overlap(self, mod_a: ModuleInfo, mod_b: ModuleInfo) -> float:
        """Calculate overlap in data format references (class definitions and type hints)."""
        if not mod_a.class_definitions or not mod_b.class_definitions:
            return 0.0

        common = mod_a.class_definitions & mod_b.class_definitions
        total = mod_a.class_definitions | mod_b.class_definitions
        return len(common) / len(total) if total else 0.0

    def _calculate_call_graph_overlap(self, mod_a: ModuleInfo, mod_b: ModuleInfo) -> float:
        """Calculate overlap in function call patterns between two modules."""
        if not mod_a.function_calls or not mod_b.function_calls:
            return 0.0

        common = mod_a.function_calls & mod_b.function_calls
        total = mod_a.function_calls | mod_b.function_calls
        return len(common) / len(total) if total else 0.0

    def _calculate_import_coupling(self, mod_a: ModuleInfo, mod_b: ModuleInfo) -> float:
        """Calculate coupling based on import relationships."""
        a_imports_b = mod_b.name.split('.')[0] in mod_a.imports
        b_imports_a = mod_a.name.split('.')[0] in mod_b.imports
        return 1.0 if a_imports_b or b_imports_a else 0.0

    def compute_coordination_potential(self, threshold: float = 0.3) -> List[Tuple[str, str, float]]:
        """
        Compute coordination potential between all module pairs.
        
        Args:
            threshold: Minimum coordination potential score to create an edge
            
        Returns:
            List of (module_a, module_b, score) tuples representing coordination edges
        """
        self.coordination_edges = []
        module_names = list(self.modules.keys())

        for i in range(len(module_names)):
            for j in range(i + 1, len(module_names)):
                mod_a = self.modules[module_names[i]]
                mod_b = self.modules[module_names[j]]

                # Calculate individual coupling scores
                interface_score = self._calculate_interface_overlap(mod_a, mod_b)
                data_format_score = self._calculate_data_format_overlap(mod_a, mod_b)
                call_graph_score = self._calculate_call_graph_overlap(mod_a, mod_b)
                import_score = self._calculate_import_coupling(mod_a, mod_b)

                # Weighted combination of coupling metrics
                total_score = (
                    0.35 * interface_score +
                    0.25 * data_format_score +
                    0.25 * call_graph_score +
                    0.15 * import_score
                )

                if total_score >= threshold:
                    self.coordination_edges.append(
                        (module_names[i], module_names[j], total_score)
                    )

        return self.coordination_edges

    def get_coordination_graph(self) -> Dict[str, List[Tuple[str, float]]]:
        """
        Get the coordination potential graph as an adjacency list.
        
        Returns:
            Dictionary mapping module names to list of (neighbor, score) tuples
        """
        graph: Dict[str, List[Tuple[str, float]]] = defaultdict(list)
        for mod_a, mod_b, score in self.coordination_edges:
            graph[mod_a].append((mod_b, score))
            graph[mod_b].append((mod_a, score))
        return dict(graph)

    def get_high_coordination_clusters(self, min_score: float = 0.5) -> List[Set[str]]:
        """
        Identify clusters of modules with high coordination potential.
        
        Args:
            min_score: Minimum score to consider for cluster formation
            
        Returns:
            List of sets, each containing module names in a cluster
        """
        # Build adjacency list for modules above threshold
        adjacency: Dict[str, Set[str]] = defaultdict(set)
        for mod_a, mod_b, score in self.coordination_edges:
            if score >= min_score:
                adjacency[mod_a].add(mod_b)
                adjacency[mod_b].add(mod_a)

        # Find connected components (clusters)
        visited: Set[str] = set()
        clusters: List[Set[str]] = []

        for module in adjacency:
            if module not in visited:
                cluster = set()
                stack = [module]
                while stack:
                    current = stack.pop()
                    if current not in visited:
                        visited.add(current)
                        cluster.add(current)
                        stack.extend(adjacency[current] - visited)
                if len(cluster) > 1:
                    clusters.append(cluster)

        return clusters

    def export_edges(self, file_path: str) -> None:
        """Export coordination edges to a file for use by the coordinated planner."""
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write("# coordination_potential edges: module_a, module_b, score\n")
            for mod_a, mod_b, score in sorted(self.coordination_edges, key=lambda x: -x[2]):
                f.write(f"{mod_a},{mod_b},{score:.4f}\n")


def extend_knowledge_graph(source_dir: str, threshold: float = 0.3) -> Dict[str, List[Tuple[str, float]]]:
    """
    Main entry point: extend the knowledge graph with coordination potential edges.
    
    Args:
        source_dir: Directory containing Python source files
        threshold: Minimum coordination potential score for creating edges
        
    Returns:
        Coordination graph as adjacency list
    """
    extender = KnowledgeGraphExtender(source_dir)
    extender.analyze_modules()
    extender.compute_coordination_potential(threshold)
    return extender.get_coordination_graph()


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        source_directory = sys.argv[1]
    else:
        source_directory = os.getcwd()
    
    threshold = float(sys.argv[2]) if len(sys.argv) > 2 else 0.3
    
    print(f"Analyzing modules in: {source_directory}")
    print(f"Using threshold: {threshold}")
    
    graph = extend_knowledge_graph(source_directory, threshold)
    
    print(f"\nFound {sum(len(v) for v in graph.values()) // 2} coordination edges")
    print("\nHigh coordination clusters:")
    extender = KnowledgeGraphExtender(source_directory)
    extender.analyze_modules()
    extender.compute_coordination_potential(threshold)
    clusters = extender.get_high_coordination_clusters()
    
    for i, cluster in enumerate(clusters, 1):
        print(f"  Cluster {i}: {', '.join(sorted(cluster))}")
    
    # Export edges for coordinated planner
    output_file = "coordination_edges.csv"
    extender.export_edges(output_file)
    print(f"\nCoordination edges exported to: {output_file}")