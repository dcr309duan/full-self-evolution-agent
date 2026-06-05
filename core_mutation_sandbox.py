"""
core_mutation_sandbox.py

Main sandbox module for intercepting and filtering mutations targeting core files.
Provides dependency impact analysis, mutation filtering, and integration hooks.
"""

import ast
import os
import sys
from pathlib import Path
from typing import Dict, List, Set, Optional, Tuple, Any
from collections import defaultdict
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Core files that are protected from direct mutation
CORE_FILES = {
    "evolution_orchestrator.py",
    "goal_generator.py"
}

# Threshold for maximum allowed dependencies affected by a mutation
MAX_DEPENDENCIES_AFFECTED = 2


class DependencyGraph:
    """
    Represents the dependency graph of all modules in the project.
    Parses import statements to build edges between modules.
    """
    
    def __init__(self, project_root: Optional[Path] = None):
        """
        Initialize the dependency graph.
        
        Args:
            project_root: Root directory of the project. If None, uses current working directory.
        """
        self.project_root = project_root or Path.cwd()
        self.graph: Dict[str, Set[str]] = defaultdict(set)  # module -> set of imported modules
        self.reverse_graph: Dict[str, Set[str]] = defaultdict(set)  # module -> set of modules that import it
        self._built = False
    
    def build(self) -> None:
        """
        Parse all Python files in the project to build the dependency graph.
        """
        logger.info(f"Building dependency graph from {self.project_root}")
        self.graph.clear()
        self.reverse_graph.clear()
        
        for py_file in self.project_root.rglob("*.py"):
            module_path = self._file_to_module(py_file)
            if module_path is None:
                continue
            
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    tree = ast.parse(f.read(), filename=str(py_file))
                
                imports = self._extract_imports(tree)
                for imported_module in imports:
                    self.graph[module_path].add(imported_module)
                    self.reverse_graph[imported_module].add(module_path)
                    
            except (SyntaxError, UnicodeDecodeError) as e:
                logger.warning(f"Could not parse {py_file}: {e}")
                continue
        
        self._built = True
        logger.info(f"Dependency graph built with {len(self.graph)} modules")
    
    def _file_to_module(self, file_path: Path) -> Optional[str]:
        """
        Convert a file path to a module name.
        
        Args:
            file_path: Path to a Python file.
            
        Returns:
            Module name relative to project root, or None if not under project root.
        """
        try:
            relative = file_path.relative_to(self.project_root)
            # Remove .py extension and convert path separators to dots
            module = str(relative.with_suffix('')).replace(os.sep, '.')
            # Handle __init__.py files
            if module.endswith('.__init__'):
                module = module[:-9]  # Remove '.__init__'
            return module
        except ValueError:
            return None
    
    def _extract_imports(self, tree: ast.AST) -> Set[str]:
        """
        Extract all module imports from an AST.
        
        Args:
            tree: AST of a Python file.
            
        Returns:
            Set of imported module names.
        """
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.add(alias.name.split('.')[0])  # Top-level module only
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.add(node.module.split('.')[0])
        return imports
    
    def get_dependents(self, module: str) -> Set[str]:
        """
        Get all modules that directly depend on the given module.
        
        Args:
            module: Module name to query.
            
        Returns:
            Set of module names that import the given module.
        """
        if not self._built:
            self.build()
        return self.reverse_graph.get(module, set())
    
    def get_dependencies(self, module: str) -> Set[str]:
        """
        Get all modules that the given module directly depends on.
        
        Args:
            module: Module name to query.
            
        Returns:
            Set of module names imported by the given module.
        """
        if not self._built:
            self.build()
        return self.graph.get(module, set())
    
    def get_all_affected_modules(self, target_module: str) -> Set[str]:
        """
        Get all modules that would be affected by a change to the target module,
        including transitive dependencies.
        
        Args:
            target_module: The module being mutated.
            
        Returns:
            Set of all modules that depend on the target module (directly or transitively).
        """
        affected = set()
        to_visit = {target_module}
        visited = set()
        
        while to_visit:
            current = to_visit.pop()
            if current in visited:
                continue
            visited.add(current)
            
            dependents = self.get_dependents(current)
            affected.update(dependents)
            to_visit.update(dependents - visited)
        
        return affected


class MutationFilter:
    """
    Filters mutation requests based on dependency impact analysis.
    Rejects mutations that would affect too many dependencies.
    """
    
    def __init__(self, dependency_graph: DependencyGraph):
        """
        Initialize the mutation filter.
        
        Args:
            dependency_graph: The dependency graph to use for analysis.
        """
        self.dependency_graph = dependency_graph
        self.rejected_mutations: List[Dict[str, Any]] = []
    
    def evaluate_mutation(self, target_file: str, mutation_details: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """
        Evaluate whether a mutation should be allowed.
        
        Args:
            target_file: The file being mutated (e.g., 'evolution_orchestrator.py').
            mutation_details: Details about the mutation (e.g., {'type': 'add_function', 'name': 'new_func'}).
            
        Returns:
            Tuple of (allowed: bool, suggestion: Optional[str]).
            If allowed is False, suggestion contains a safer alternative.
        """
        module = target_file.replace('.py', '')
        affected_modules = self.dependency_graph.get_all_affected_modules(module)
        num_affected = len(affected_modules)
        
        if num_affected >= 3:
            suggestion = self._generate_suggestion(target_file, mutation_details, affected_modules)
            rejection_record = {
                'target_file': target_file,
                'mutation_details': mutation_details,
                'num_affected': num_affected,
                'affected_modules': list(affected_modules),
                'suggestion': suggestion
            }
            self.rejected_mutations.append(rejection_record)
            logger.warning(
                f"Mutation to {target_file} rejected: affects {num_affected} dependencies "
                f"(threshold: {MAX_DEPENDENCIES_AFFECTED}). Suggestion: {suggestion}"
            )
            return False, suggestion
        
        logger.info(
            f"Mutation to {target_file} approved: affects {num_affected} dependencies "
            f"(threshold: {MAX_DEPENDENCIES_AFFECTED})"
        )
        return True, None
    
    def _generate_suggestion(self, target_file: str, mutation_details: Dict[str, Any],
                             affected_modules: Set[str]) -> str:
        """
        Generate a suggestion for a safer alternative mutation.
        
        Args:
            target_file: The file being mutated.
            mutation_details: Details about the mutation.
            affected_modules: Set of modules that would be affected.
            
        Returns:
            A string describing the suggested alternative.
        """
        # Suggest creating a new module or adding to a less-impacted module
        suggestion_parts = [
            f"Mutation to {target_file} affects {len(affected_modules)} modules: "
            f"{', '.join(sorted(affected_modules)[:5])}{'...' if len(affected_modules) > 5 else ''}."
        ]
        
        # Suggest creating a new module
        new_module_name = f"{target_file.replace('.py', '')}_extension"
        suggestion_parts.append(
            f"Consider creating a new module '{new_module_name}.py' to isolate the change, "
            f"or modify a module with fewer dependents."
        )
        
        # Suggest specific safer targets based on mutation type
        mutation_type = mutation_details.get('type', 'unknown')
        if mutation_type == 'add_function':
            suggestion_parts.append(
                f"Alternatively, add the function to a utility module that has fewer dependents."
            )
        elif mutation_type == 'modify_function':
            suggestion_parts.append(
                f"Consider adding a new function instead of modifying an existing one to maintain backward compatibility."
            )
        
        return ' '.join(suggestion_parts)


def intercept_mutation_request(target_file: str, mutation_details: Dict[str, Any],
                                dependency_graph: Optional[DependencyGraph] = None,
                                mutation_filter: Optional[MutationFilter] = None) -> Tuple[bool, Optional[str]]:
    """
    Intercept a mutation request targeting a core file.
    
    Args:
        target_file: The file being mutated.
        mutation_details: Details about the mutation.
        dependency_graph: Optional pre-built dependency graph. If None, builds one.
        mutation_filter: Optional pre-built mutation filter. If None, creates one.
        
    Returns:
        Tuple of (allowed: bool, suggestion: Optional[str]).
    """
    # Check if target is a core file
    if target_file not in CORE_FILES:
        logger.info(f"Target {target_file} is not a core file, allowing mutation")
        return True, None
    
    logger.info(f"Intercepting mutation request for core file: {target_file}")
    
    # Build dependency graph if not provided
    if dependency_graph is None:
        dependency_graph = DependencyGraph()
        dependency_graph.build()
    
    # Create mutation filter if not provided
    if mutation_filter is None:
        mutation_filter = MutationFilter(dependency_graph)
    
    # Evaluate the mutation
    return mutation_filter.evaluate_mutation(target_file, mutation_details)


class EvolutionOrchestratorHook:
    """
    Integration hooks for the evolution orchestrator to call before applying any mutation.
    """
    
    def __init__(self, dependency_graph: Optional[DependencyGraph] = None):
        """
        Initialize the hook.
        
        Args:
            dependency_graph: Optional pre-built dependency graph.
        """
        self.dependency_graph = dependency_graph or DependencyGraph()
        self.mutation_filter = MutationFilter(self.dependency_graph)
        self.mutation_history: List[Dict[str, Any]] = []
    
    def before_mutation(self, target_file: str, mutation_details: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """
        Hook to be called by the evolution orchestrator before applying a mutation.
        
        Args:
            target_file: The file being mutated.
            mutation_details: Details about the mutation.
            
        Returns:
            Tuple of (allowed: bool, suggestion: Optional[str]).
        """
        logger.info(f"Evolution orchestrator hook: before mutation to {target_file}")
        
        # Record the mutation attempt
        record = {
            'target_file': target_file,
            'mutation_details': mutation_details,
            'timestamp': __import__('datetime').datetime.now().isoformat()
        }
        self.mutation_history.append(record)
        
        # Use the main interception function
        return intercept_mutation_request(
            target_file, mutation_details,
            dependency_graph=self.dependency_graph,
            mutation_filter=self.mutation_filter
        )
    
    def get_mutation_history(self) -> List[Dict[str, Any]]:
        """
        Get the history of all mutation attempts.
        
        Returns:
            List of mutation records.
        """
        return self.mutation_history.copy()
    
    def get_rejected_mutations(self) -> List[Dict[str, Any]]:
        """
        Get all mutations that were rejected by the filter.
        
        Returns:
            List of rejected mutation records.
        """
        return self.mutation_filter.rejected_mutations.copy()


# Convenience function for quick integration
def create_sandbox_hook(project_root: Optional[Path] = None) -> EvolutionOrchestratorHook:
    """
    Create a sandbox hook for the evolution orchestrator.
    
    Args:
        project_root: Root directory of the project.
        
    Returns:
        An EvolutionOrchestratorHook instance ready to use.
    """
    dependency_graph = DependencyGraph(project_root)
    dependency_graph.build()
    return EvolutionOrchestratorHook(dependency_graph)


# Example usage (commented out)
if __name__ == "__main__":
    # Quick test
    hook = create_sandbox_hook()
    
    # Simulate a mutation attempt
    allowed, suggestion = hook.before_mutation(
        "evolution_orchestrator.py",
        {"type": "add_function", "name": "new_evolution_method"}
    )
    
    if allowed:
        print("Mutation allowed")
    else:
        print(f"Mutation rejected: {suggestion}")
    
    print(f"Mutation history: {hook.get_mutation_history()}")