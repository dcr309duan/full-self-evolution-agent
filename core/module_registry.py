"""Module Registry - Central registry for module discovery and dependency resolution.

This module provides a registry for tracking available modules and their
dependencies. It is used by the dependency resolver to understand module
relationships and resolve dependency chains.
"""

import importlib
import inspect
import logging
import os
import sys
from typing import Any, Dict, List, Optional, Set, Tuple, Type

logger = logging.getLogger(__name__)


class ModuleRegistry:
    """Central registry for module discovery and dependency tracking.
    
    Maintains a registry of all known modules, their metadata, and their
    dependencies. Supports dynamic module loading and dependency resolution.
    """
    
    def __init__(self):
        self._modules: Dict[str, Dict[str, Any]] = {}
        self._loaded: Set[str] = set()
        self._initialized = False
    
    def register(self, module_name: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Register a module in the registry.
        
        Args:
            module_name: Fully qualified module name (e.g., 'core.evolution_orchestrator')
            metadata: Optional dictionary of module metadata including dependencies
        """
        if metadata is None:
            metadata = {}
        
        if module_name not in self._modules:
            self._modules[module_name] = {
                'name': module_name,
                'dependencies': metadata.get('dependencies', []),
                'description': metadata.get('description', ''),
                'version': metadata.get('version', '0.1.0'),
                'loaded': False,
                'path': None
            }
            logger.debug(f"Registered module: {module_name}")
        else:
            # Update existing registration
            self._modules[module_name].update(metadata)
            logger.debug(f"Updated module registration: {module_name}")
    
    def load_module(self, module_name: str) -> Optional[Any]:
        """Load a module by name, resolving dependencies first.
        
        Args:
            module_name: Name of the module to load
            
        Returns:
            The loaded module object, or None if loading failed
        """
        if module_name in self._loaded:
            return sys.modules.get(module_name)
        
        # Check if module is registered
        if module_name not in self._modules:
            logger.warning(f"Module '{module_name}' not registered. Attempting direct import.")
            try:
                module = importlib.import_module(module_name)
                self._loaded.add(module_name)
                self.register(module_name, {'loaded': True})
                return module
            except ImportError as e:
                logger.error(f"Failed to import module '{module_name}': {e}")
                return None
        
        # Resolve and load dependencies first
        deps = self._modules[module_name].get('dependencies', [])
        for dep in deps:
            if dep not in self._loaded:
                self.load_module(dep)
        
        # Load the module
        try:
            module = importlib.import_module(module_name)
            self._loaded.add(module_name)
            self._modules[module_name]['loaded'] = True
            self._modules[module_name]['path'] = getattr(module, '__file__', None)
            logger.info(f"Loaded module: {module_name}")
            return module
        except ImportError as e:
            logger.error(f"Failed to load module '{module_name}': {e}")
            return None
    
    def get_dependencies(self, module_name: str) -> List[str]:
        """Get the dependencies for a registered module.
        
        Args:
            module_name: Name of the module
            
        Returns:
            List of dependency module names
        """
        if module_name in self._modules:
            return self._modules[module_name].get('dependencies', [])
        return []
    
    def get_dependents(self, module_name: str) -> List[str]:
        """Get all modules that depend on the given module.
        
        Args:
            module_name: Name of the module to find dependents for
            
        Returns:
            List of module names that depend on the given module
        """
        dependents = []
        for name, info in self._modules.items():
            if module_name in info.get('dependencies', []):
                dependents.append(name)
        return dependents
    
    def resolve_dependency_chain(self, module_name: str) -> List[str]:
        """Resolve the full dependency chain for a module (topological order).
        
        Args:
            module_name: Name of the module to resolve dependencies for
            
        Returns:
            List of module names in dependency order (dependencies first)
        """
        resolved = []
        visited = set()
        
        def _resolve(name: str, chain: Set[str]) -> bool:
            """Recursive dependency resolution with cycle detection."""
            if name in chain:
                logger.error(f"Circular dependency detected involving '{name}'")
                return False
            
            if name in visited:
                return True
            
            chain.add(name)
            deps = self.get_dependencies(name)
            
            for dep in deps:
                if not _resolve(dep, chain):
                    return False
            
            chain.remove(name)
            visited.add(name)
            
            if name not in resolved:
                resolved.append(name)
            
            return True
        
        if _resolve(module_name, set()):
            return resolved
        return []
    
    def discover_modules(self, package_path: Optional[str] = None) -> List[str]:
        """Discover and register modules from a package path.
        
        Args:
            package_path: Path to discover modules from (defaults to current directory)
            
        Returns:
            List of discovered module names
        """
        if package_path is None:
            package_path = os.path.dirname(os.path.abspath(__file__))
        
        discovered = []
        package_name = os.path.basename(package_path)
        
        for root, dirs, files in os.walk(package_path):
            for file in files:
                if file.endswith('.py') and not file.startswith('__'):
                    # Convert file path to module name
                    rel_path = os.path.relpath(os.path.join(root, file), package_path)
                    module_name = rel_path.replace(os.sep, '.')[:-3]  # Remove .py
                    full_name = f"{package_name}.{module_name}" if package_name else module_name
                    
                    # Extract docstring for description
                    description = ""
                    try:
                        with open(os.path.join(root, file), 'r') as f:
                            content = f.read()
                            if '"""' in content:
                                start = content.index('"""') + 3
                                end = content.index('"""', start)
                                description = content[start:end].strip()
                    except (IOError, ValueError):
                        pass
                    
                    self.register(full_name, {'description': description})
                    discovered.append(full_name)
        
        logger.info(f"Discovered {len(discovered)} modules in '{package_path}'")
        return discovered
    
    def is_registered(self, module_name: str) -> bool:
        """Check if a module is registered.
        
        Args:
            module_name: Name of the module to check
            
        Returns:
            True if the module is registered, False otherwise
        """
        return module_name in self._modules
    
    def is_loaded(self, module_name: str) -> bool:
        """Check if a module has been loaded.
        
        Args:
            module_name: Name of the module to check
            
        Returns:
            True if the module is loaded, False otherwise
        """
        return module_name in self._loaded
    
    def get_registered_modules(self) -> Dict[str, Dict[str, Any]]:
        """Get all registered modules and their metadata.
        
        Returns:
            Dictionary of module names to their metadata
        """
        return dict(self._modules)
    
    def clear(self) -> None:
        """Clear the registry (for testing or reset)."""
        self._modules.clear()
        self._loaded.clear()
        self._initialized = False


# Global registry instance
_registry: Optional[ModuleRegistry] = None


def get_registry() -> ModuleRegistry:
    """Get or create the global module registry instance.
    
    Returns:
        The global ModuleRegistry instance
    """
    global _registry
    if _registry is None:
        _registry = ModuleRegistry()
    return _registry


def register_module(module_name: str, metadata: Optional[Dict[str, Any]] = None) -> None:
    """Convenience function to register a module in the global registry.
    
    Args:
        module_name: Fully qualified module name
        metadata: Optional module metadata
    """
    registry = get_registry()
    registry.register(module_name, metadata)


def load_module(module_name: str) -> Optional[Any]:
    """Convenience function to load a module via the global registry.
    
    Args:
        module_name: Name of the module to load
        
    Returns:
        The loaded module object, or None if loading failed
    """
    registry = get_registry()
    return registry.load_module(module_name)


def resolve_dependencies(module_name: str) -> List[str]:
    """Convenience function to resolve dependencies via the global registry.
    
    Args:
        module_name: Name of the module to resolve dependencies for
        
    Returns:
        List of module names in dependency order
    """
    registry = get_registry()
    return registry.resolve_dependency_chain(module_name)


def discover_modules(package_path: Optional[str] = None) -> List[str]:
    """Convenience function to discover modules via the global registry.
    
    Args:
        package_path: Path to discover modules from
        
    Returns:
        List of discovered module names
    """
    registry = get_registry()
    return registry.discover_modules(package_path)