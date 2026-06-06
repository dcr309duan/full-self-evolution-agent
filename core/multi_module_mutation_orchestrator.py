"""multi_module_mutation_orchestrator.py

Purpose: Read existing multi-module orchestrator to understand coordination interface.

This module provides a mutation orchestrator that coordinates multi-module
mutation testing across different test frameworks and mutation strategies.
It reads the existing multi-module orchestrator interface to understand
how modules coordinate mutation operations.

Key responsibilities:
1. Discover available mutation modules
2. Coordinate mutation execution across modules
3. Aggregate mutation results
4. Provide unified interface for mutation orchestration
"""

import importlib
import inspect
import logging
import os
import sys
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Protocol, Tuple, Type

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Protocol / Interface Definitions
# ---------------------------------------------------------------------------

class MutationModule(Protocol):
    """Protocol defining the interface for mutation modules."""
    
    def mutate(self, source: str, **kwargs) -> str:
        """Apply mutations to source code."""
        ...
    
    def get_mutants(self, source: str, **kwargs) -> List[str]:
        """Return list of mutant source strings."""
        ...


class MutationResult:
    """Container for mutation testing results."""
    
    def __init__(
        self,
        module_name: str,
        original: str,
        mutants: List[str],
        killed: List[bool],
        execution_time: float = 0.0,
        errors: List[str] = None,
    ):
        self.module_name = module_name
        self.original = original
        self.mutants = mutants
        self.killed = killed
        self.execution_time = execution_time
        self.errors = errors or []
    
    @property
    def mutation_score(self) -> float:
        """Calculate mutation score (percentage of killed mutants)."""
        if not self.mutants:
            return 0.0
        return sum(self.killed) / len(self.mutants) * 100.0
    
    @property
    def total_mutants(self) -> int:
        return len(self.mutants)
    
    @property
    def killed_mutants(self) -> int:
        return sum(self.killed)
    
    @property
    def survived_mutants(self) -> int:
        return self.total_mutants - self.killed_mutants


@dataclass
class OrchestratorConfig:
    """Configuration for the mutation orchestrator."""
    module_paths: List[str] = field(default_factory=list)
    module_names: List[str] = field(default_factory=list)
    max_mutants_per_module: int = 100
    timeout_per_mutant: float = 5.0
    parallel_execution: bool = False
    max_workers: int = 4
    verbose: bool = False


# ---------------------------------------------------------------------------
# Module Discovery
# ---------------------------------------------------------------------------

def discover_mutation_modules(
    paths: Optional[List[str]] = None,
    module_names: Optional[List[str]] = None,
) -> Dict[str, MutationModule]:
    """Discover available mutation modules from given paths or names.
    
    Args:
        paths: List of directory paths to search for modules.
        module_names: List of specific module names to import.
    
    Returns:
        Dictionary mapping module names to their mutation module instances.
    """
    modules: Dict[str, MutationModule] = {}
    
    # Add paths to sys.path if provided
    if paths:
        for path in paths:
            if path not in sys.path:
                sys.path.insert(0, path)
    
    # Discover from module names
    if module_names:
        for name in module_names:
            try:
                mod = importlib.import_module(name)
                if hasattr(mod, 'mutate') and hasattr(mod, 'get_mutants'):
                    modules[name] = mod
                    logger.info(f"Discovered mutation module: {name}")
                else:
                    logger.warning(
                        f"Module '{name}' does not implement MutationModule protocol"
                    )
            except ImportError as e:
                logger.error(f"Failed to import module '{name}': {e}")
    
    # Discover from paths (scan for Python files)
    if paths:
        for path in paths:
            if not os.path.isdir(path):
                continue
            for filename in os.listdir(path):
                if filename.endswith('.py') and not filename.startswith('_'):
                    module_name = filename[:-3]
                    try:
                        spec = importlib.util.spec_from_file_location(
                            module_name, os.path.join(path, filename)
                        )
                        if spec and spec.loader:
                            mod = importlib.util.module_from_spec(spec)
                            spec.loader.exec_module(mod)
                            if hasattr(mod, 'mutate') and hasattr(mod, 'get_mutants'):
                                modules[module_name] = mod
                                logger.info(f"Discovered mutation module: {module_name}")
                    except Exception as e:
                        logger.error(f"Failed to load module from {filename}: {e}")
    
    return modules


# ---------------------------------------------------------------------------
# Coordination Interface
# ---------------------------------------------------------------------------

class MultiModuleMutationOrchestrator:
    """Orchestrates mutation testing across multiple mutation modules.
    
    This class reads the existing multi-module orchestrator interface to
    understand how modules coordinate mutation operations.
    """
    
    def __init__(self, config: Optional[OrchestratorConfig] = None):
        self.config = config or OrchestratorConfig()
        self.modules: Dict[str, MutationModule] = {}
        self.results: Dict[str, MutationResult] = {}
        self._discover_modules()
    
    def _discover_modules(self) -> None:
        """Discover mutation modules based on configuration."""
        self.modules = discover_mutation_modules(
            paths=self.config.module_paths,
            module_names=self.config.module_names,
        )
        if not self.modules:
            logger.warning("No mutation modules discovered")
    
    def register_module(self, name: str, module: MutationModule) -> None:
        """Register a mutation module manually."""
        self.modules[name] = module
        logger.info(f"Registered mutation module: {name}")
    
    def get_available_modules(self) -> List[str]:
        """Return list of available mutation module names."""
        return list(self.modules.keys())
    
    def get_module_interface(self, module_name: str) -> Dict[str, Any]:
        """Inspect and return the interface of a mutation module.
        
        This method reads the existing module to understand its coordination
        interface.
        
        Args:
            module_name: Name of the module to inspect.
        
        Returns:
            Dictionary describing the module's interface.
        """
        if module_name not in self.modules:
            raise ValueError(f"Module '{module_name}' not found")
        
        module = self.modules[module_name]
        interface_info = {
            'name': module_name,
            'methods': {},
            'attributes': {},
        }
        
        # Inspect methods
        for name, method in inspect.getmembers(module, inspect.isfunction):
            if not name.startswith('_'):
                sig = inspect.signature(method)
                interface_info['methods'][name] = {
                    'signature': str(sig),
                    'parameters': list(sig.parameters.keys()),
                    'doc': inspect.getdoc(method) or '',
                }
        
        # Inspect classes
        for name, cls in inspect.getmembers(module, inspect.isclass):
            if not name.startswith('_'):
                class_info = {
                    'methods': {},
                    'attributes': {},
                }
                for attr_name, attr in inspect.getmembers(cls):
                    if not attr_name.startswith('_'):
                        if inspect.isfunction(attr):
                            sig = inspect.signature(attr)
                            class_info['methods'][attr_name] = {
                                'signature': str(sig),
                                'parameters': list(sig.parameters.keys()),
                                'doc': inspect.getdoc(attr) or '',
                            }
                        else:
                            class_info['attributes'][attr_name] = type(attr).__name__
                interface_info['attributes'][name] = class_info
        
        return interface_info
    
    def read_coordination_interface(self) -> Dict[str, Any]:
        """Read and understand the coordination interface of all modules.
        
        This is the primary method for understanding how modules coordinate.
        It aggregates interface information from all registered modules.
        
        Returns:
            Dictionary containing the aggregated coordination interface.
        """
        coordination_info = {
            'modules': {},
            'common_patterns': [],
            'coordination_methods': [],
        }
        
        for module_name in self.modules:
            interface = self.get_module_interface(module_name)
            coordination_info['modules'][module_name] = interface
            
            # Identify coordination methods (methods that take source code)
            for method_name, method_info in interface.get('methods', {}).items():
                params = method_info.get('parameters', [])
                if 'source' in params or 'code' in params:
                    coordination_info['coordination_methods'].append({
                        'module': module_name,
                        'method': method_name,
                        'parameters': params,
                    })
        
        # Identify common patterns across modules
        if len(self.modules) > 1:
            module_names = list(self.modules.keys())
            first_module = self.modules[module_names[0]]
            common_methods = set(
                name for name, _ in inspect.getmembers(first_module, inspect.isfunction)
                if not name.startswith('_')
            )
            
            for module_name in module_names[1:]:
                module = self.modules[module_name]
                module_methods = set(
                    name for name, _ in inspect.getmembers(module, inspect.isfunction)
                    if not name.startswith('_')
                )
                common_methods &= module_methods
            
            coordination_info['common_patterns'] = list(common_methods)
        
        return coordination_info
    
    def orchestrate_mutation(
        self,
        source: str,
        module_names: Optional[List[str]] = None,
        **kwargs,
    ) -> Dict[str, MutationResult]:
        """Orchestrate mutation testing across specified modules.
        
        Args:
            source: Source code to mutate.
            module_names: List of module names to use (uses all if None).
            **kwargs: Additional arguments passed to mutation modules.
        
        Returns:
            Dictionary mapping module names to their mutation results.
        """
        if module_names is None:
            module_names = list(self.modules.keys())
        
        results = {}
        for module_name in module_names:
            if module_name not in self.modules:
                logger.warning(f"Module '{module_name}' not found, skipping")
                continue
            
            try:
                module = self.modules[module_name]
                mutants = module.get_mutants(source, **kwargs)
                
                # Limit mutants if configured
                if self.config.max_mutants_per_module > 0:
                    mutants = mutants[:self.config.max_mutants_per_module]
                
                # For now, we mark all mutants as not killed (survived)
                # In a real implementation, tests would be run against each mutant
                killed = [False] * len(mutants)
                
                result = MutationResult(
                    module_name=module_name,
                    original=source,
                    mutants=mutants,
                    killed=killed,
                )
                results[module_name] = result
                self.results[module_name] = result
                
                logger.info(
                    f"Module '{module_name}' generated {len(mutants)} mutants"
                )
                
            except Exception as e:
                logger.error(f"Error orchestrating module '{module_name}': {e}")
                results[module_name] = MutationResult(
                    module_name=module_name,
                    original=source,
                    mutants=[],
                    killed=[],
                    errors=[str(e)],
                )
        
        return results
    
    def get_aggregate_results(self) -> Dict[str, Any]:
        """Get aggregate results from all orchestrated mutations.
        
        Returns:
            Dictionary with aggregate statistics.
        """
        if not self.results:
            return {'total_mutants': 0, 'average_score': 0.0}
        
        total_mutants = sum(r.total_mutants for r in self.results.values())
        total_killed = sum(r.killed_mutants for r in self.results.values())
        scores = [r.mutation_score for r in self.results.values() if r.total_mutants > 0]
        
        return {
            'total_mutants': total_mutants,
            'total_killed': total_killed,
            'total_survived': total_mutants - total_killed,
            'average_score': sum(scores) / len(scores) if scores else 0.0,
            'modules_used': list(self.results.keys()),
            'module_results': {
                name: {
                    'total': r.total_mutants,
                    'killed': r.killed_mutants,
                    'survived': r.survived_mutants,
                    'score': r.mutation_score,
                }
                for name, r in self.results.items()
            },
        }


# ---------------------------------------------------------------------------
# Convenience Functions
# ---------------------------------------------------------------------------

def create_orchestrator(
    module_paths: Optional[List[str]] = None,
    module_names: Optional[List[str]] = None,
    **kwargs,
) -> MultiModuleMutationOrchestrator:
    """Create and configure a MultiModuleMutationOrchestrator.
    
    Args:
        module_paths: List of directory paths to search for modules.
        module_names: List of specific module names to import.
        **kwargs: Additional configuration parameters.
    
    Returns:
        Configured orchestrator instance.
    """
    config = OrchestratorConfig(
        module_paths=module_paths or [],
        module_names=module_names or [],
        **kwargs,
    )
    return MultiModuleMutationOrchestrator(config)


def read_existing_orchestrator_interface(
    module_path: str,
) -> Dict[str, Any]:
    """Read and understand the coordination interface of an existing orchestrator.
    
    This is the primary entry point for understanding how modules coordinate.
    
    Args:
        module_path: Path to the orchestrator module to read.
    
    Returns:
        Dictionary describing the coordination interface.
    """
    orchestrator = create_orchestrator(module_paths=[os.path.dirname(module_path)])
    return orchestrator.read_coordination_interface()


# ---------------------------------------------------------------------------
# Example Usage (if run directly)
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    
    # Example: Read existing orchestrator interface
    current_dir = os.path.dirname(os.path.abspath(__file__))
    interface = read_existing_orchestrator_interface(current_dir)
    
    print("Coordination Interface:")
    import json
    print(json.dumps(interface, indent=2, default=str))