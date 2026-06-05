"""Interface discovery for self-modeling components.

This module provides the InterfaceDiscovery class which is responsible for
identifying and cataloging public APIs of each component in the system.
It distinguishes between internal and external interfaces and supports
decorator-based route discovery.
"""

import ast
import inspect
import logging
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Set,
    Tuple,
    Union,
)

logger = logging.getLogger(__name__)


class InterfaceDiscovery:
    """Discovers and catalogs public interfaces of components.

    Identifies exported functions, class methods, and decorator-based routes.
    Distinguishes between internal (prefixed with _) and external interfaces.
    """

    def __init__(self, component: Any, name: Optional[str] = None):
        """Initialize with a component to analyze.

        Args:
            component: The component object to discover interfaces from.
            name: Optional name for the component (defaults to class/module name).
        """
        self.component = component
        self.name = name or self._derive_name()
        self._interfaces: Dict[str, Dict[str, Any]] = {}
        self._routes: List[Dict[str, Any]] = []
        self._external_interfaces: Dict[str, Dict[str, Any]] = {}
        self._internal_interfaces: Dict[str, Dict[str, Any]] = {}

    def _derive_name(self) -> str:
        """Derive component name from its type."""
        if inspect.isclass(self.component):
            return self.component.__name__
        elif inspect.ismodule(self.component):
            return self.component.__name__
        elif hasattr(self.component, '__name__'):
            return self.component.__name__
        return type(self.component).__name__

    def discover_all(self) -> Dict[str, Any]:
        """Perform full interface discovery on the component.

        Returns:
            Dictionary containing all discovered interfaces, routes, and metadata.
        """
        self._interfaces = {}
        self._routes = []
        self._external_interfaces = {}
        self._internal_interfaces = {}

        if inspect.isclass(self.component):
            self._discover_class_interfaces()
        elif inspect.ismodule(self.component):
            self._discover_module_interfaces()
        elif callable(self.component):
            self._discover_callable_interface()
        else:
            self._discover_object_interfaces()

        self._categorize_interfaces()

        return {
            'name': self.name,
            'type': self._get_component_type(),
            'interfaces': self._interfaces,
            'external_interfaces': self._external_interfaces,
            'internal_interfaces': self._internal_interfaces,
            'routes': self._routes,
            'interface_count': len(self._interfaces),
            'external_count': len(self._external_interfaces),
            'internal_count': len(self._internal_interfaces),
            'route_count': len(self._routes),
        }

    def _get_component_type(self) -> str:
        """Get the type description of the component."""
        if inspect.isclass(self.component):
            return 'class'
        elif inspect.ismodule(self.component):
            return 'module'
        elif inspect.isfunction(self.component):
            return 'function'
        elif inspect.ismethod(self.component):
            return 'method'
        else:
            return 'object'

    def _discover_class_interfaces(self) -> None:
        """Discover interfaces from a class component."""
        for name, member in inspect.getmembers(self.component):
            if inspect.isfunction(member) or inspect.ismethod(member):
                self._add_interface(name, member, 'method')
            elif isinstance(member, (staticmethod, classmethod)):
                self._add_interface(name, member, 'method')

        # Discover decorator-based routes (e.g., Flask, FastAPI, custom)
        self._discover_routes_from_class()

    def _discover_module_interfaces(self) -> None:
        """Discover interfaces from a module component."""
        for name, member in inspect.getmembers(self.component):
            if name.startswith('_'):
                continue  # Skip private members
            if inspect.isfunction(member):
                self._add_interface(name, member, 'function')
            elif inspect.isclass(member):
                self._add_interface(name, member, 'class')

        # Discover decorator-based routes at module level
        self._discover_routes_from_module()

    def _discover_callable_interface(self) -> None:
        """Discover interface from a callable (function/method)."""
        name = getattr(self.component, '__name__', 'anonymous')
        self._add_interface(name, self.component, 'callable')

    def _discover_object_interfaces(self) -> None:
        """Discover interfaces from a generic object."""
        for name in dir(self.component):
            if name.startswith('_'):
                continue
            try:
                member = getattr(self.component, name)
                if callable(member):
                    self._add_interface(name, member, 'method')
            except Exception as e:
                logger.debug(f"Could not access member {name}: {e}")

    def _add_interface(
        self,
        name: str,
        member: Any,
        interface_type: str,
    ) -> None:
        """Add an interface to the discovery results.

        Args:
            name: Name of the interface.
            member: The actual function/method/class.
            interface_type: Type of interface (method, function, class, callable).
        """
        interface_info = {
            'name': name,
            'type': interface_type,
            'is_internal': name.startswith('_'),
            'signature': self._get_signature(member),
            'docstring': inspect.getdoc(member) or '',
            'module': getattr(member, '__module__', ''),
            'qualname': getattr(member, '__qualname__', name),
        }

        self._interfaces[name] = interface_info

    def _get_signature(self, obj: Any) -> Optional[str]:
        """Get string representation of a callable's signature.

        Args:
            obj: The callable to inspect.

        Returns:
            String representation of the signature, or None if not available.
        """
        try:
            sig = inspect.signature(obj)
            return str(sig)
        except (ValueError, TypeError):
            return None

    def _categorize_interfaces(self) -> None:
        """Categorize interfaces into internal and external."""
        for name, info in self._interfaces.items():
            if info['is_internal']:
                self._internal_interfaces[name] = info
            else:
                self._external_interfaces[name] = info

    def _discover_routes_from_class(self) -> None:
        """Discover decorator-based routes from class methods.

        Looks for common web framework route decorators and custom route markers.
        """
        for name, method in inspect.getmembers(self.component, inspect.isfunction):
            route_info = self._extract_route_info(method)
            if route_info:
                route_info['method_name'] = name
                self._routes.append(route_info)

    def _discover_routes_from_module(self) -> None:
        """Discover decorator-based routes from module-level functions."""
        for name, func in inspect.getmembers(self.component, inspect.isfunction):
            if not name.startswith('_'):
                route_info = self._extract_route_info(func)
                if route_info:
                    route_info['function_name'] = name
                    self._routes.append(route_info)

    def _extract_route_info(self, func: Callable) -> Optional[Dict[str, Any]]:
        """Extract route information from a function's decorators.

        Attempts to parse the source code to find route decorators.
        Supports common patterns like @app.route(), @router.get(), etc.

        Args:
            func: The function to inspect for route decorators.

        Returns:
            Dictionary with route info or None if no route decorator found.
        """
        try:
            source_file = inspect.getsourcefile(func)
            if not source_file:
                return None

            source_lines, start_line = inspect.getsourcelines(func)
            source = ''.join(source_lines)

            tree = ast.parse(source)
            if not tree.body:
                return None

            node = tree.body[0]
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                return None

            # Look for decorators that might be route decorators
            for decorator in node.decorator_list:
                route_info = self._parse_route_decorator(decorator)
                if route_info:
                    return route_info

        except (OSError, SyntaxError, Exception) as e:
            logger.debug(f"Could not extract route info from {func}: {e}")

        return None

    def _parse_route_decorator(self, decorator: ast.expr) -> Optional[Dict[str, Any]]:
        """Parse an AST decorator node to extract route information.

        Args:
            decorator: AST node representing a decorator.

        Returns:
            Dictionary with route path, methods, and framework if recognized.
        """
        # Pattern: @app.route('/path') or @router.get('/path')
        if isinstance(decorator, ast.Call):
            func = decorator.func
            if isinstance(func, ast.Attribute):
                # Get the method name (e.g., 'route', 'get', 'post', etc.)
                method_name = func.attr.lower()

                # Common HTTP methods and route decorators
                route_methods = {
                    'route': ['GET', 'POST', 'PUT', 'DELETE', 'PATCH'],
                    'get': ['GET'],
                    'post': ['POST'],
                    'put': ['PUT'],
                    'delete': ['DELETE'],
                    'patch': ['PATCH'],
                    'head': ['HEAD'],
                    'options': ['OPTIONS'],
                }

                if method_name in route_methods:
                    # Extract path from first argument
                    path = ''
                    if decorator.args:
                        if isinstance(decorator.args[0], ast.Constant):
                            path = decorator.args[0].value
                        elif isinstance(decorator.args[0], ast.Str):
                            path = decorator.args[0].s

                    # Try to determine the framework from the object name
                    framework = self._guess_framework(func)

                    return {
                        'path': path,
                        'methods': route_methods[method_name],
                        'framework': framework,
                        'decorator': method_name,
                    }

        return None

    def _guess_framework(self, func: ast.Attribute) -> str:
        """Try to guess the web framework from the decorator's object.

        Args:
            func: The attribute node representing the decorator call.

        Returns:
            String identifying the likely framework ('flask', 'fastapi', 'unknown').
        """
        if isinstance(func.value, ast.Name):
            name = func.value.id.lower()
            if name in ('app', 'bp', 'blueprint'):
                return 'flask'
            elif name in ('router', 'api', 'app'):
                return 'fastapi'
        elif isinstance(func.value, ast.Attribute):
            # Handle cases like app.api.route()
            if hasattr(func.value, 'attr'):
                attr = func.value.attr.lower()
                if attr in ('app', 'router', 'api'):
                    return 'fastapi'
        return 'unknown'

    def get_external_interfaces(self) -> Dict[str, Dict[str, Any]]:
        """Get only external (public) interfaces.

        Returns:
            Dictionary of external interface names to their metadata.
        """
        if not self._external_interfaces:
            self.discover_all()
        return self._external_interfaces

    def get_internal_interfaces(self) -> Dict[str, Dict[str, Any]]:
        """Get only internal (private) interfaces.

        Returns:
            Dictionary of internal interface names to their metadata.
        """
        if not self._internal_interfaces:
            self.discover_all()
        return self._internal_interfaces

    def get_routes(self) -> List[Dict[str, Any]]:
        """Get discovered routes.

        Returns:
            List of route dictionaries with path, methods, and framework info.
        """
        if not self._routes:
            self.discover_all()
        return self._routes

    def has_interface(self, name: str) -> bool:
        """Check if a specific interface exists.

        Args:
            name: Name of the interface to check.

        Returns:
            True if the interface exists, False otherwise.
        """
        if not self._interfaces:
            self.discover_all()
        return name in self._interfaces

    def get_interface(self, name: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a specific interface.

        Args:
            name: Name of the interface.

        Returns:
            Interface metadata dictionary or None if not found.
        """
        if not self._interfaces:
            self.discover_all()
        return self._interfaces.get(name)

    def refresh(self) -> Dict[str, Any]:
        """Force re-discovery of interfaces.

        Returns:
            Fresh discovery results.
        """
        self._interfaces = {}
        self._routes = []
        self._external_interfaces = {}
        self._internal_interfaces = {}
        return self.discover_all()


def discover_component_interfaces(
    component: Any,
    name: Optional[str] = None,
) -> Dict[str, Any]:
    """Convenience function to discover interfaces of a component.

    Args:
        component: The component to analyze.
        name: Optional name for the component.

    Returns:
        Dictionary of discovery results.
    """
    discoverer = InterfaceDiscovery(component, name)
    return discoverer.discover_all()


def get_public_apis(
    component: Any,
    name: Optional[str] = None,
) -> Dict[str, Dict[str, Any]]:
    """Get only public (external) APIs of a component.

    Args:
        component: The component to analyze.
        name: Optional name for the component.

    Returns:
        Dictionary of public interface names to their metadata.
    """
    discoverer = InterfaceDiscovery(component, name)
    return discoverer.get_external_interfaces()


def get_internal_apis(
    component: Any,
    name: Optional[str] = None,
) -> Dict[str, Dict[str, Any]]:
    """Get only internal (private) APIs of a component.

    Args:
        component: The component to analyze.
        name: Optional name for the component.

    Returns:
        Dictionary of internal interface names to their metadata.
    """
    discoverer = InterfaceDiscovery(component, name)
    return discoverer.get_internal_interfaces()