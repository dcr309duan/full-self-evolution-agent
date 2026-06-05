"""Dependency analyzer for self-modeling codebase.

Reads import statements and function calls to build dependency edges
between components and detect external dependencies.
"""

import ast
import sys
import os
from typing import Dict, List, Set, Tuple, Optional
from dataclasses import dataclass, field, asdict


@dataclass
class DependencyRecord:
    """Structured record of a single dependency."""
    source: str  # component/module that depends
    target: str  # component/module depended upon
    dep_type: str  # 'internal', 'stdlib', 'third_party'
    line_number: int
    kind: str  # 'import', 'call', 'attribute'
    details: Optional[str] = None


@dataclass
class ComponentDependencies:
    """All dependencies for a single component."""
    component: str
    imports: List[DependencyRecord] = field(default_factory=list)
    calls: List[DependencyRecord] = field(default_factory=list)
    attributes: List[DependencyRecord] = field(default_factory=list)


class DependencyAnalyzer:
    """Analyzes Python source files to extract dependency relationships."""

    # Known standard library modules (Python 3.8+)
    STDLIB_MODULES = {
        'abc', 'ast', 'asyncio', 'base64', 'collections', 'contextlib',
        'copy', 'csv', 'dataclasses', 'datetime', 'decimal', 'enum',
        'functools', 'glob', 'hashlib', 'html', 'http', 'importlib',
        'inspect', 'io', 'itertools', 'json', 'logging', 'math', 'os',
        'pathlib', 'pickle', 'platform', 'pprint', 'random', 're',
        'shutil', 'signal', 'socket', 'sqlite3', 'string', 'struct',
        'subprocess', 'sys', 'tempfile', 'textwrap', 'threading',
        'time', 'traceback', 'types', 'typing', 'unittest', 'urllib',
        'uuid', 'warnings', 'weakref', 'xml', 'zipfile',
    }

    def __init__(self, project_root: str = '.'):
        self.project_root = os.path.abspath(project_root)
        self._stdlib_modules = self._get_stdlib_modules()
        self._project_modules: Set[str] = set()
        self._third_party_modules: Set[str] = set()

    def _get_stdlib_modules(self) -> Set[str]:
        """Get the set of standard library module names."""
        stdlib = set(self.STDLIB_MODULES)
        # Add modules from sys.stdlib_module_names if available (Python 3.10+)
        if hasattr(sys, 'stdlib_module_names'):
            stdlib.update(sys.stdlib_module_names)
        return stdlib

    def _is_stdlib(self, module_name: str) -> bool:
        """Check if a module is part of the Python standard library."""
        base = module_name.split('.')[0]
        return base in self._stdlib_modules

    def _is_project_module(self, module_name: str) -> bool:
        """Check if a module belongs to the current project."""
        base = module_name.split('.')[0]
        return base in self._project_modules

    def _classify_module(self, module_name: str) -> str:
        """Classify a module as 'stdlib', 'third_party', or 'internal'."""
        if self._is_stdlib(module_name):
            return 'stdlib'
        if self._is_project_module(module_name):
            return 'internal'
        return 'third_party'

    def scan_project(self) -> List[ComponentDependencies]:
        """Scan all Python files in the project and extract dependencies."""
        self._discover_project_modules()
        results: List[ComponentDependencies] = []

        for root, dirs, files in os.walk(self.project_root):
            # Skip hidden directories and common non-source dirs
            dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ('__pycache__', 'venv', 'env', '.git')]

            for file in files:
                if file.endswith('.py'):
                    filepath = os.path.join(root, file)
                    component = self._file_to_component(filepath)
                    deps = self.analyze_file(filepath, component)
                    if deps:
                        results.append(deps)

        return results

    def _discover_project_modules(self) -> None:
        """Build set of module names that belong to this project."""
        self._project_modules = set()
        for root, dirs, files in os.walk(self.project_root):
            dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ('__pycache__', 'venv', 'env', '.git')]

            # Add directory as package
            rel_path = os.path.relpath(root, self.project_root)
            if rel_path != '.':
                parts = rel_path.replace(os.sep, '.').split('.')
                for i in range(len(parts)):
                    self._project_modules.add('.'.join(parts[:i+1]))

            # Add module files
            for file in files:
                if file.endswith('.py') and file != '__init__.py':
                    module_name = file[:-3]
                    if rel_path != '.':
                        module_name = f"{rel_path.replace(os.sep, '.')}.{module_name}"
                    self._project_modules.add(module_name)

    def _file_to_component(self, filepath: str) -> str:
        """Convert a file path to a component/module name."""
        rel_path = os.path.relpath(filepath, self.project_root)
        component = rel_path.replace(os.sep, '.')
        if component.endswith('.py'):
            component = component[:-3]
        if component.endswith('.__init__'):
            component = component[:-9]
        return component

    def analyze_file(self, filepath: str, component: str = None) -> Optional[ComponentDependencies]:
        """Analyze a single Python file for dependencies."""
        if component is None:
            component = self._file_to_component(filepath)

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                source = f.read()
        except (IOError, UnicodeDecodeError):
            return None

        try:
            tree = ast.parse(source, filename=filepath)
        except SyntaxError:
            return None

        result = ComponentDependencies(component=component)
        self._extract_imports(tree, component, result)
        self._extract_calls(tree, component, result)

        return result

    def _extract_imports(self, tree: ast.AST, source_component: str, result: ComponentDependencies) -> None:
        """Extract import dependencies from AST."""
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    module_name = alias.name
                    dep_type = self._classify_module(module_name)
                    record = DependencyRecord(
                        source=source_component,
                        target=module_name,
                        dep_type=dep_type,
                        line_number=node.lineno,
                        kind='import',
                        details=f"import {module_name}"
                    )
                    result.imports.append(record)

            elif isinstance(node, ast.ImportFrom):
                module_name = node.module or ''
                dep_type = self._classify_module(module_name)
                for alias in node.names:
                    target = f"{module_name}.{alias.name}" if module_name else alias.name
                    record = DependencyRecord(
                        source=source_component,
                        target=target,
                        dep_type=dep_type,
                        line_number=node.lineno,
                        kind='import',
                        details=f"from {module_name} import {alias.name}"
                    )
                    result.imports.append(record)

    def _extract_calls(self, tree: ast.AST, source_component: str, result: ComponentDependencies) -> None:
        """Extract function call dependencies from AST."""
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Name):
                    # Simple function call: func()
                    target = func.id
                    dep_type = self._classify_module(target)
                    record = DependencyRecord(
                        source=source_component,
                        target=target,
                        dep_type=dep_type,
                        line_number=node.lineno,
                        kind='call',
                        details=f"call {target}()"
                    )
                    result.calls.append(record)

                elif isinstance(func, ast.Attribute):
                    # Method/attribute call: obj.method()
                    obj = func.value
                    attr = func.attr

                    if isinstance(obj, ast.Name):
                        target = f"{obj.id}.{attr}"
                        dep_type = self._classify_module(obj.id)
                        record = DependencyRecord(
                            source=source_component,
                            target=target,
                            dep_type=dep_type,
                            line_number=node.lineno,
                            kind='call',
                            details=f"call {target}()"
                        )
                        result.calls.append(record)

                    elif isinstance(obj, ast.Attribute):
                        # Chained attribute: a.b.c()
                        parts = []
                        current = obj
                        while isinstance(current, ast.Attribute):
                            parts.append(current.attr)
                            current = current.value
                        if isinstance(current, ast.Name):
                            parts.append(current.id)
                        parts.reverse()
                        parts.append(attr)
                        target = '.'.join(parts)
                        dep_type = self._classify_module(parts[0])
                        record = DependencyRecord(
                            source=source_component,
                            target=target,
                            dep_type=dep_type,
                            line_number=node.lineno,
                            kind='call',
                            details=f"call {target}()"
                        )
                        result.calls.append(record)

    def get_dependency_graph(self) -> Dict[str, List[DependencyRecord]]:
        """Get a complete dependency graph as a dictionary."""
        all_deps = self.scan_project()
        graph: Dict[str, List[DependencyRecord]] = {}

        for comp_deps in all_deps:
            component = comp_deps.component
            if component not in graph:
                graph[component] = []

            for dep_list in [comp_deps.imports, comp_deps.calls, comp_deps.attributes]:
                graph[component].extend(dep_list)

        return graph

    def get_external_dependencies(self) -> Dict[str, Set[str]]:
        """Get all external (non-project) dependencies grouped by type."""
        all_deps = self.scan_project()
        external: Dict[str, Set[str]] = {
            'stdlib': set(),
            'third_party': set()
        }

        for comp_deps in all_deps:
            for dep_list in [comp_deps.imports, comp_deps.calls, comp_deps.attributes]:
                for dep in dep_list:
                    if dep.dep_type == 'stdlib':
                        external['stdlib'].add(dep.target.split('.')[0])
                    elif dep.dep_type == 'third_party':
                        external['third_party'].add(dep.target.split('.')[0])

        return external

    def to_dict(self, deps: ComponentDependencies) -> dict:
        """Convert ComponentDependencies to a dictionary."""
        return {
            'component': deps.component,
            'imports': [asdict(r) for r in deps.imports],
            'calls': [asdict(r) for r in deps.calls],
            'attributes': [asdict(r) for r in deps.attributes]
        }

    def to_json_serializable(self) -> List[dict]:
        """Get all dependencies in JSON-serializable format."""
        all_deps = self.scan_project()
        return [self.to_dict(d) for d in all_deps]