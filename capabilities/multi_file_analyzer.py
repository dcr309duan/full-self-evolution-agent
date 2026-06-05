"""Multi-file dependency analyzer for Python projects.

Builds a dependency graph across all Python files, extracting imports,
definitions, and call relationships. Provides analysis for circular
dependencies, unused imports, and orphaned functions.
"""

import ast
import os
import json
from collections import defaultdict
from typing import Dict, List, Set, Tuple, Optional


class MultiFileAnalyzer:
    """Analyzes dependencies across multiple Python files in a project."""

    def __init__(self, project_root: str):
        self.project_root = os.path.abspath(project_root)
        self.file_dependencies: Dict[str, Set[str]] = defaultdict(set)
        self.definitions: Dict[str, List[Dict]] = defaultdict(list)
        self.calls: Dict[str, List[Dict]] = defaultdict(list)
        self.imports: Dict[str, List[Dict]] = defaultdict(list)
        self.all_definitions: Dict[str, Set[str]] = defaultdict(set)
        self.module_map: Dict[str, str] = {}  # module name -> file path

    def _get_python_files(self) -> List[str]:
        """Recursively find all Python files in the project."""
        python_files = []
        for root, _, files in os.walk(self.project_root):
            for f in files:
                if f.endswith('.py'):
                    full_path = os.path.join(root, f)
                    python_files.append(full_path)
        return python_files

    def _module_name_from_path(self, file_path: str) -> str:
        """Convert a file path to a Python module name."""
        rel_path = os.path.relpath(file_path, self.project_root)
        module = rel_path.replace(os.sep, '.')[:-3]  # remove .py
        return module

    def _build_module_map(self):
        """Build mapping from module names to file paths."""
        for file_path in self._get_python_files():
            module_name = self._module_name_from_path(file_path)
            self.module_map[module_name] = file_path

    def _resolve_import(self, module_name: str, file_path: str) -> Optional[str]:
        """Resolve an import to an actual file path in the project."""
        # Try exact match
        if module_name in self.module_map:
            return self.module_map[module_name]

        # Try relative import based on current file's directory
        current_dir = os.path.dirname(file_path)
        rel_path = os.path.join(current_dir, module_name.replace('.', os.sep))
        for ext in ['', '.py']:
            full_path = rel_path + ext
            if os.path.isfile(full_path):
                return os.path.abspath(full_path)

        # Try as package (directory with __init__.py)
        pkg_path = os.path.join(current_dir, module_name.replace('.', os.sep))
        init_path = os.path.join(pkg_path, '__init__.py')
        if os.path.isfile(init_path):
            return os.path.abspath(init_path)

        return None

    def _extract_imports(self, tree: ast.AST, file_path: str):
        """Extract all import statements from an AST."""
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    resolved = self._resolve_import(alias.name, file_path)
                    self.imports[file_path].append({
                        'type': 'import',
                        'module': alias.name,
                        'alias': alias.asname,
                        'resolved_path': resolved
                    })
                    if resolved:
                        self.file_dependencies[file_path].add(resolved)

            elif isinstance(node, ast.ImportFrom):
                module = node.module or ''
                for alias in node.names:
                    full_module = f"{module}.{alias.name}" if module else alias.name
                    resolved = self._resolve_import(full_module, file_path)
                    self.imports[file_path].append({
                        'type': 'import_from',
                        'module': module,
                        'name': alias.name,
                        'alias': alias.asname,
                        'resolved_path': resolved
                    })
                    if resolved:
                        self.file_dependencies[file_path].add(resolved)

    def _extract_definitions(self, tree: ast.AST, file_path: str):
        """Extract function and class definitions from an AST."""
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                def_info = {
                    'type': 'function',
                    'name': node.name,
                    'lineno': node.lineno,
                    'end_lineno': node.end_lineno,
                    'args': [arg.arg for arg in node.args.args],
                    'decorators': [self._get_decorator_name(d) for d in node.decorator_list]
                }
                self.definitions[file_path].append(def_info)
                self.all_definitions[file_path].add(node.name)

            elif isinstance(node, ast.AsyncFunctionDef):
                def_info = {
                    'type': 'async_function',
                    'name': node.name,
                    'lineno': node.lineno,
                    'end_lineno': node.end_lineno,
                    'args': [arg.arg for arg in node.args.args],
                    'decorators': [self._get_decorator_name(d) for d in node.decorator_list]
                }
                self.definitions[file_path].append(def_info)
                self.all_definitions[file_path].add(node.name)

            elif isinstance(node, ast.ClassDef):
                class_info = {
                    'type': 'class',
                    'name': node.name,
                    'lineno': node.lineno,
                    'end_lineno': node.end_lineno,
                    'bases': [self._get_base_name(b) for b in node.bases],
                    'methods': [m.name for m in node.body if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))]
                }
                self.definitions[file_path].append(class_info)
                self.all_definitions[file_path].add(node.name)

    def _get_decorator_name(self, node: ast.AST) -> str:
        """Extract decorator name from AST node."""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return f"{self._get_decorator_name(node.value)}.{node.attr}"
        elif isinstance(node, ast.Call):
            return self._get_decorator_name(node.func)
        return str(node)

    def _get_base_name(self, node: ast.AST) -> str:
        """Extract base class name from AST node."""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return f"{self._get_base_name(node.value)}.{node.attr}"
        return str(node)

    def _extract_calls(self, tree: ast.AST, file_path: str):
        """Extract function/method calls from an AST."""
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                call_info = {
                    'lineno': node.lineno,
                    'col_offset': node.col_offset,
                }
                if isinstance(node.func, ast.Name):
                    call_info['name'] = node.func.id
                    call_info['type'] = 'direct'
                elif isinstance(node.func, ast.Attribute):
                    call_info['name'] = f"{self._get_base_name(node.func.value)}.{node.func.attr}"
                    call_info['type'] = 'attribute'
                elif isinstance(node.func, ast.Call):
                    call_info['name'] = 'complex_call'
                    call_info['type'] = 'complex'
                else:
                    call_info['name'] = 'unknown'
                    call_info['type'] = 'unknown'

                self.calls[file_path].append(call_info)

    def analyze(self) -> Dict:
        """Perform full analysis of all Python files in the project."""
        self._build_module_map()
        python_files = self._get_python_files()

        for file_path in python_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    source = f.read()
                tree = ast.parse(source, filename=file_path)
                self._extract_imports(tree, file_path)
                self._extract_definitions(tree, file_path)
                self._extract_calls(tree, file_path)
            except (SyntaxError, UnicodeDecodeError) as e:
                print(f"Warning: Could not parse {file_path}: {e}")

        return self._build_dependency_map()

    def _build_dependency_map(self) -> Dict:
        """Build the complete dependency map as a JSON-serializable dict."""
        dependency_map = {
            'project_root': self.project_root,
            'files': {},
            'circular_dependencies': self.detect_circular_dependencies(),
            'unused_imports': self.detect_unused_imports(),
            'orphaned_functions': self.detect_orphaned_functions(),
        }

        for file_path in self._get_python_files():
            rel_path = os.path.relpath(file_path, self.project_root)
            file_info = {
                'path': rel_path,
                'module': self._module_name_from_path(file_path),
                'imports': self.imports.get(file_path, []),
                'definitions': self.definitions.get(file_path, []),
                'calls': self.calls.get(file_path, []),
                'dependencies': [
                    os.path.relpath(dep, self.project_root)
                    for dep in self.file_dependencies.get(file_path, set())
                ],
            }
            dependency_map['files'][rel_path] = file_info

        return dependency_map

    def detect_circular_dependencies(self) -> List[List[str]]:
        """Detect circular dependencies using DFS."""
        visited = set()
        recursion_stack = set()
        cycles = []

        def dfs(file_path: str, path: List[str]):
            visited.add(file_path)
            recursion_stack.add(file_path)
            path.append(file_path)

            for dep in self.file_dependencies.get(file_path, set()):
                if dep not in visited:
                    dfs(dep, path)
                elif dep in recursion_stack:
                    # Found a cycle
                    cycle_start = path.index(dep)
                    cycle = path[cycle_start:]
                    cycle.append(dep)  # close the cycle
                    cycles.append([
                        os.path.relpath(f, self.project_root) for f in cycle
                    ])

            path.pop()
            recursion_stack.discard(file_path)

        for file_path in self._get_python_files():
            if file_path not in visited:
                dfs(file_path, [])

        return cycles

    def detect_unused_imports(self) -> Dict[str, List[str]]:
        """Detect imports that are not used in the file."""
        unused = {}
        for file_path in self._get_python_files():
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    source = f.read()
                tree = ast.parse(source, filename=file_path)

                # Collect all names defined/imported in the file
                defined_names = set()
                imported_names = set()
                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                        defined_names.add(node.name)
                    elif isinstance(node, ast.Import):
                        for alias in node.names:
                            name = alias.asname or alias.name.split('.')[0]
                            imported_names.add(name)
                    elif isinstance(node, ast.ImportFrom):
                        for alias in node.names:
                            name = alias.asname or alias.name
                            imported_names.add(name)

                # Collect all name references (excluding definitions)
                referenced_names = set()
                for node in ast.walk(tree):
                    if isinstance(node, ast.Name) and not isinstance(node.ctx, (ast.Store, ast.Del)):
                        referenced_names.add(node.id)
                    elif isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
                        referenced_names.add(node.value.id)

                # Find unused imports
                unused_imports = []
                for imp in self.imports.get(file_path, []):
                    name = imp.get('alias') or imp.get('name', '').split('.')[0]
                    if name and name not in referenced_names and name not in defined_names:
                        unused_imports.append(imp)

                if unused_imports:
                    rel_path = os.path.relpath(file_path, self.project_root)
                    unused[rel_path] = unused_imports

            except (SyntaxError, UnicodeDecodeError):
                continue

        return unused

    def detect_orphaned_functions(self) -> Dict[str, List[str]]:
        """Detect functions/classes defined but never called/used across the project."""
        # Collect all definitions across all files
        all_defs = {}
        for file_path, defs in self.definitions.items():
            for d in defs:
                all_defs[d['name']] = file_path

        # Collect all call references across all files
        all_calls = set()
        for file_path, calls in self.calls.items():
            for call in calls:
                if call['type'] == 'direct':
                    all_calls.add(call['name'])
                elif call['type'] == 'attribute':
                    # Extract the method/function name from attribute calls
                    parts = call['name'].split('.')
                    if parts:
                        all_calls.add(parts[-1])

        # Also collect references from imports (if a function is imported elsewhere)
        imported_defs = set()
        for file_path, imports in self.imports.items():
            for imp in imports:
                if imp['type'] == 'import_from':
                    imported_defs.add(imp['name'])

        # Find orphaned definitions
        orphaned = defaultdict(list)
        for name, file_path in all_defs.items():
            if name not in all_calls and name not in imported_defs:
                # Check if it's a dunder method or special name
                if not (name.startswith('__') and name.endswith('__')):
                    rel_path = os.path.relpath(file_path, self.project_root)
                    orphaned[rel_path].append(name)

        return dict(orphaned)

    def export_json(self, output_path: str):
        """Export the dependency map to a JSON file."""
        dependency_map = self.analyze()
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(dependency_map, f, indent=2, default=str)

    def print_summary(self):
        """Print a human-readable summary of the analysis."""
        dep_map = self.analyze()
        print(f"Project: {dep_map['project_root']}")
        print(f"Files analyzed: {len(dep_map['files'])}")
        print(f"Circular dependencies: {len(dep_map['circular_dependencies'])}")
        print(f"Files with unused imports: {len(dep_map['unused_imports'])}")
        print(f"Files with orphaned functions: {len(dep_map['orphaned_functions'])}")
        print()

        if dep_map['circular_dependencies']:
            print("Circular Dependencies:")
            for cycle in dep_map['circular_dependencies']:
                print(f"  {' -> '.join(cycle)}")
            print()

        if dep_map['unused_imports']:
            print("Unused Imports:")
            for file_path, imports in dep_map['unused_imports'].items():
                print(f"  {file_path}:")
                for imp in imports:
                    print(f"    - {imp.get('module', '')}.{imp.get('name', '')}")
            print()

        if dep_map['orphaned_functions']:
            print("Orphaned Functions:")
            for file_path, funcs in dep_map['orphaned_functions'].items():
                print(f"  {file_path}:")
                for func in funcs:
                    print(f"    - {func}")


def main():
    """CLI entry point for the multi-file analyzer."""
    import argparse
    parser = argparse.ArgumentParser(description='Analyze Python project dependencies')
    parser.add_argument('project_root', help='Root directory of the Python project')
    parser.add_argument('-o', '--output', help='Output JSON file path')
    parser.add_argument('-s', '--summary', action='store_true', help='Print summary to console')
    args = parser.parse_args()

    analyzer = MultiFileAnalyzer(args.project_root)

    if args.output:
        analyzer.export_json(args.output)
        print(f"Dependency map exported to {args.output}")

    if args.summary or not args.output:
        analyzer.print_summary()


if __name__ == '__main__':
    main()