import ast
import json
import os
from typing import Dict, List, Set, Tuple, Optional


class DependencyValidator:
    """Validates Python dependencies by parsing imports and function calls,
    maintaining a dependency map, and checking for circular dependencies
    and non-existent module references."""

    def __init__(self, map_file: str = "dependency_map.json"):
        self.map_file = map_file
        self.dependency_map: Dict[str, Dict[str, List[str]]] = {
            "imports": {},
            "calls": {}
        }
        self._load_map()

    def _load_map(self) -> None:
        """Load the dependency map from JSON file if it exists."""
        if os.path.exists(self.map_file):
            try:
                with open(self.map_file, 'r') as f:
                    self.dependency_map = json.load(f)
            except (json.JSONDecodeError, IOError):
                self.dependency_map = {"imports": {}, "calls": {}}

    def save_map(self) -> None:
        """Save the current dependency map to JSON file."""
        with open(self.map_file, 'w') as f:
            json.dump(self.dependency_map, f, indent=2)

    def parse_file(self, filepath: str) -> Tuple[Dict[str, List[str]], Dict[str, List[str]]]:
        """Parse a Python file and extract imports and function calls.
        
        Returns:
            Tuple of (imports_dict, calls_dict)
            imports_dict: {module_name: [imported_names]}
            calls_dict: {module_name: [called_functions]}
        """
        with open(filepath, 'r') as f:
            code = f.read()
        return self.parse_code(code, filepath)

    def parse_code(self, code: str, source_name: str = "<unknown>") -> Tuple[Dict[str, List[str]], Dict[str, List[str]]]:
        """Parse Python source code and extract imports and function calls.
        
        Args:
            code: Python source code string
            source_name: Identifier for the source (filename or module name)
            
        Returns:
            Tuple of (imports_dict, calls_dict)
        """
        tree = ast.parse(code)
        imports: Dict[str, List[str]] = {}
        calls: Dict[str, List[str]] = {}
        
        # Extract imports
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    module = alias.name
                    asname = alias.asname
                    if module not in imports:
                        imports[module] = []
                    if asname:
                        imports[module].append(asname)
                    else:
                        imports[module].append(module.split('.')[-1])
                        
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ''
                for alias in node.names:
                    name = alias.name
                    asname = alias.asname
                    if module not in imports:
                        imports[module] = []
                    imports[module].append(asname if asname else name)
        
        # Extract function calls (simple detection)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Name):
                    func_name = func.id
                    if source_name not in calls:
                        calls[source_name] = []
                    calls[source_name].append(func_name)
                elif isinstance(func, ast.Attribute):
                    # Handle obj.method() calls
                    if isinstance(func.value, ast.Name):
                        obj_name = func.value.id
                        method_name = func.attr
                        if obj_name not in calls:
                            calls[obj_name] = []
                        calls[obj_name].append(method_name)
        
        return imports, calls

    def update_map(self, source_name: str, imports: Dict[str, List[str]], 
                   calls: Dict[str, List[str]]) -> None:
        """Update the dependency map with new data from parsed code."""
        if source_name not in self.dependency_map["imports"]:
            self.dependency_map["imports"][source_name] = {}
        
        for module, names in imports.items():
            if module not in self.dependency_map["imports"][source_name]:
                self.dependency_map["imports"][source_name][module] = []
            self.dependency_map["imports"][source_name][module].extend(names)
            self.dependency_map["imports"][source_name][module] = list(
                set(self.dependency_map["imports"][source_name][module])
            )
        
        if source_name not in self.dependency_map["calls"]:
            self.dependency_map["calls"][source_name] = {}
        
        for obj, funcs in calls.items():
            if obj not in self.dependency_map["calls"][source_name]:
                self.dependency_map["calls"][source_name][obj] = []
            self.dependency_map["calls"][source_name][obj].extend(funcs)
            self.dependency_map["calls"][source_name][obj] = list(
                set(self.dependency_map["calls"][source_name][obj])
            )
        
        self.save_map()

    def _find_circular_dependencies(self, source_name: str, 
                                     imports: Dict[str, List[str]]) -> List[str]:
        """Check for circular dependencies involving the given source."""
        circular = []
        visited = set()
        path = []
        
        def dfs(current: str, target: str, depth: int = 0) -> bool:
            if current == target and depth > 0:
                return True
            if current in visited:
                return False
            visited.add(current)
            path.append(current)
            
            # Check if current module imports target
            if current in self.dependency_map["imports"]:
                for module in self.dependency_map["imports"][current]:
                    if module == target or module.startswith(target + '.'):
                        path.append(module)
                        return True
                    if dfs(module, target, depth + 1):
                        return True
            path.pop()
            return False
        
        # Check if any new import creates a cycle
        for module in imports:
            visited.clear()
            path.clear()
            if dfs(module, source_name):
                circular.append(f"Circular dependency: {source_name} -> {' -> '.join(path)}")
        
        return circular

    def _check_non_existent_modules(self, imports: Dict[str, List[str]]) -> List[str]:
        """Check if imported modules exist in the dependency map or are standard library modules."""
        non_existent = []
        # Common standard library modules (simplified list)
        stdlib_modules = {
            'os', 'sys', 're', 'json', 'math', 'datetime', 'collections',
            'itertools', 'functools', 'pathlib', 'typing', 'abc', 'io',
            'subprocess', 'argparse', 'logging', 'random', 'string',
            'hashlib', 'base64', 'copy', 'pprint', 'textwrap', 'enum',
            'fractions', 'decimal', 'statistics', 'time', 'calendar',
            'uuid', 'socket', 'http', 'urllib', 'xml', 'html', 'csv',
            'configparser', 'tempfile', 'shutil', 'glob', 'fnmatch',
            'linecache', 'pickle', 'shelve', 'marshal', 'dbm', 'sqlite3',
            'zlib', 'gzip', 'bz2', 'lzma', 'zipfile', 'tarfile',
            'ast', 'inspect', 'dis', 'tokenize', 'keyword', 'token',
            'builtins', '__future__', 'types', 'traceback', 'warnings',
            'dataclasses', 'contextlib', 'importlib', 'pkgutil',
            'unittest', 'doctest', 'profile', 'pstats', 'timeit',
            'venv', 'ensurepip', 'ctypes', 'curses', 'turtle', 'tkinter',
            'webbrowser', 'antigravity'
        }
        
        for module in imports:
            if module == '':
                continue
            # Check if it's a relative import (starts with '.')
            if module.startswith('.'):
                continue
            # Check if it's in the dependency map
            if module in self.dependency_map["imports"]:
                continue
            # Check if it's a standard library module
            base_module = module.split('.')[0]
            if base_module in stdlib_modules:
                continue
            # Check if it's a known third-party package (simplified)
            # In a real implementation, you might check installed packages
            non_existent.append(module)
        
        return non_existent

    def validate_mutation(self, source_name: str, code: str) -> List[str]:
        """Validate new/modified code against the dependency map.
        
        Args:
            source_name: Identifier for the source (filename or module name)
            code: Python source code string to validate
            
        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []
        
        try:
            imports, calls = self.parse_code(code, source_name)
        except SyntaxError as e:
            errors.append(f"Syntax error in code: {e}")
            return errors
        
        # Check for circular dependencies
        circular = self._find_circular_dependencies(source_name, imports)
        errors.extend(circular)
        
        # Check for non-existent module references
        non_existent = self._check_non_existent_modules(imports)
        for module in non_existent:
            errors.append(f"Non-existent module reference: '{module}'")
        
        # Update the map if no errors found
        if not errors:
            self.update_map(source_name, imports, calls)
        
        return errors


def parse_imports(code: str) -> Dict[str, List[str]]:
    """Utility function to parse imports from code string."""
    validator = DependencyValidator()
    imports, _ = validator.parse_code(code)
    return imports


def parse_calls(code: str) -> Dict[str, List[str]]:
    """Utility function to parse function calls from code string."""
    validator = DependencyValidator()
    _, calls = validator.parse_code(code)
    return calls


def validate_mutation(source_name: str, code: str, map_file: str = "dependency_map.json") -> List[str]:
    """Convenience function to validate code mutations.
    
    Args:
        source_name: Identifier for the source
        code: Python source code string
        map_file: Path to dependency map JSON file
        
    Returns:
        List of validation error messages
    """
    validator = DependencyValidator(map_file)
    return validator.validate_mutation(source_name, code)