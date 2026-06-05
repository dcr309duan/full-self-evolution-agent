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
        
        # Extract function calls (comprehensive detection)
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
                    elif isinstance(func.value, ast.Call):
                        # Handle chained calls like func().method()
                        inner_func = func.value.func
                        if isinstance(inner_func, ast.Name):
                            inner_name = inner_func.id
                            method_name = func.attr
                            if inner_name not in calls:
                                calls[inner_name] = []
                            calls[inner_name].append(method_name)
                elif isinstance(func, ast.Subscript):
                    # Handle array access like obj[key]()
                    if isinstance(func.value, ast.Name):
                        obj_name = func.value.id
                        if obj_name not in calls:
                            calls[obj_name] = []
                        calls[obj_name].append("__getitem__")
        
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
        """Check for circular dependencies involving the given source using DFS."""
        circular = []
        
        def dfs(current: str, target: str, visited: Set[str], path: List[str]) -> bool:
            if current == target and len(path) > 0:
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
                    if dfs(module, target, visited, path):
                        return True
            path.pop()
            visited.discard(current)
            return False
        
        # Check if any new import creates a cycle
        for module in imports:
            visited: Set[str] = set()
            path: List[str] = []
            if dfs(module, source_name, visited, path):
                circular.append(f"Circular dependency: {source_name} -> {' -> '.join(path)}")
        
        # Also check for cycles within the existing dependency map
        for module in self.dependency_map["imports"]:
            visited = set()
            path = []
            if dfs(module, module, visited, path):
                cycle_str = " -> ".join(path)
                if cycle_str not in [str(c) for c in circular]:
                    circular.append(f"Circular dependency: {cycle_str}")
        
        return circular

    def _check_non_existent_modules(self, imports: Dict[str, List[str]]) -> List[str]:
        """Check if imported modules exist in the dependency map or are standard library modules."""
        non_existent = []
        # Common standard library modules (comprehensive list)
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
            'webbrowser', 'antigravity', 'array', 'bisect', 'calendar',
            'cmath', 'collections.abc', 'concurrent', 'contextvars',
            'copyreg', 'cProfile', 'crypt', 'csv', 'ctypes', 'curses',
            'dataclasses', 'datetime', 'dbm', 'decimal', 'difflib',
            'dis', 'distutils', 'doctest', 'email', 'encodings',
            'enum', 'errno', 'faulthandler', 'fcntl', 'filecmp',
            'fileinput', 'fnmatch', 'fractions', 'ftplib', 'functools',
            'gc', 'getopt', 'getpass', 'gettext', 'glob', 'grp',
            'gzip', 'hashlib', 'heapq', 'hmac', 'html', 'http',
            'idlelib', 'imaplib', 'imghdr', 'imp', 'importlib',
            'inspect', 'io', 'ipaddress', 'itertools', 'json',
            'keyword', 'lib2to3', 'linecache', 'locale', 'logging',
            'lzma', 'mailbox', 'mailcap', 'marshal', 'math', 'mimetypes',
            'mmap', 'modulefinder', 'multiprocessing', 'netrc', 'nis',
            'nntplib', 'numbers', 'operator', 'optparse', 'os',
            'ossaudiodev', 'parser', 'pathlib', 'pdb', 'pickle',
            'pickletools', 'pipes', 'pkgutil', 'platform', 'plistlib',
            'poplib', 'posix', 'posixpath', 'pprint', 'profile',
            'pstats', 'pty', 'pwd', 'py_compile', 'pyclbr', 'pydoc',
            'queue', 'quopri', 'random', 're', 'readline', 'reprlib',
            'resource', 'rlcompleter', 'runpy', 'sched', 'secrets',
            'select', 'selectors', 'shelve', 'shlex', 'shutil',
            'signal', 'site', 'smtpd', 'smtplib', 'sndhdr', 'socket',
            'socketserver', 'sqlite3', 'ssl', 'stat', 'statistics',
            'string', 'stringprep', 'struct', 'subprocess', 'sunau',
            'symtable', 'sys', 'sysconfig', 'syslog', 'tabnanny',
            'tarfile', 'telnetlib', 'tempfile', 'termios', 'test',
            'textwrap', 'threading', 'time', 'timeit', 'tkinter',
            'token', 'tokenize', 'trace', 'traceback', 'tracemalloc',
            'tty', 'turtle', 'types', 'typing', 'unicodedata',
            'unittest', 'urllib', 'uu', 'uuid', 'venv', 'warnings',
            'wave', 'weakref', 'webbrowser', 'winreg', 'winsound',
            'wsgiref', 'xdrlib', 'xml', 'xmlrpc', 'zipapp', 'zipfile',
            'zipimport', 'zlib'
        }
        
        # Build a set of known modules from the dependency map
        known_modules = set(self.dependency_map["imports"].keys())
        # Also include modules that are imported by others
        for source, imports_dict in self.dependency_map["imports"].items():
            for module in imports_dict:
                known_modules.add(module)
        
        for module in imports:
            if module == '':
                continue
            # Check if it's a relative import (starts with '.')
            if module.startswith('.'):
                continue
            # Check if it's in the dependency map
            if module in known_modules:
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

    def validate_mutation_safety(self, mutation_diff: str, dependency_map: Dict[str, Dict[str, List[str]]]) -> Dict[str, object]:
        """Validate a proposed mutation diff against the current dependency map.
        
        Args:
            mutation_diff: A string representing the diff of the proposed code change
            dependency_map: The current dependency map to validate against
            
        Returns:
            A dictionary with 'passed' (bool) and 'errors' (list of str) keys
        """
        result = {
            "passed": True,
            "errors": []
        }
        
        # Parse the mutation diff to extract new imports and function calls
        new_imports = {}
        new_calls = {}
        
        # Simple diff parsing: extract lines starting with '+' (added lines)
        added_lines = []
        for line in mutation_diff.split('\n'):
            if line.startswith('+') and not line.startswith('+++'):
                added_lines.append(line[1:].strip())
        
        # Combine added lines into a pseudo-code block for parsing
        pseudo_code = '\n'.join(added_lines)
        if pseudo_code.strip():
            try:
                parsed_imports, parsed_calls = self.parse_code(pseudo_code, "<mutation>")
                new_imports = parsed_imports
                new_calls = parsed_calls
            except SyntaxError:
                # If parsing fails, try to extract imports manually
                for line in added_lines:
                    if line.startswith('import ') or line.startswith('from '):
                        try:
                            imp_imports, _ = self.parse_code(line, "<mutation>")
                            for mod, names in imp_imports.items():
                                if mod not in new_imports:
                                    new_imports[mod] = []
                                new_imports[mod].extend(names)
                        except SyntaxError:
                            pass
        
        # Build a set of known modules from the dependency map
        known_modules = set(dependency_map.get("imports", {}).keys())
        for source, imports_dict in dependency_map.get("imports", {}).items():
            for module in imports_dict:
                known_modules.add(module)
        
        # Validate new imports against dependency map
        for module, names in new_imports.items():
            if module == '' or module.startswith('.'):
                continue
            
            # Check if module exists in dependency map
            if module not in known_modules:
                # Check if it's a standard library module
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
                base_module = module.split('.')[0]
                if base_module not in stdlib_modules:
                    result["passed"] = False
                    result["errors"].append(f"Non-existent module reference: '{module}'")
        
        # Check for circular dependencies using DFS
        for module in new_imports:
            visited = set()
            path = []
            
            def dfs(current: str, target: str, depth: int = 0) -> bool:
                if current == target and depth > 0:
                    return True
                if current in visited:
                    return False
                visited.add(current)
                path.append(current)
                
                # Check if current module imports target in dependency map
                if current in dependency_map.get("imports", {}):
                    for dep_module in dependency_map["imports"][current]:
                        if dep_module == target or dep_module.startswith(target + '.'):
                            path.append(dep_module)
                            return True
                        if dfs(dep_module, target, depth + 1):
                            return True
                path.pop()
                visited.discard(current)
                return False
            
            # We need a source name for the mutation; use a placeholder
            source_name = "<mutation>"
            if dfs(module, source_name):
                result["passed"] = False
                result["errors"].append(f"Circular dependency detected: {source_name} -> {' -> '.join(path)}")
        
        # Validate function calls (check if called functions exist in dependency map)
        for obj, funcs in new_calls.items():
            if obj in dependency_map.get("calls", {}):
                for func in funcs:
                    if func not in dependency_map["calls"][obj]:
                        result["passed"] = False
                        result["errors"].append(f"Non-existent function call: '{func}' in module '{obj}'")
            elif obj != "<mutation>":
                # If the object is not in the calls map, it might be a new module
                # Check if it exists in imports
                if obj not in known_modules:
                    result["passed"] = False
                    result["errors"].append(f"Non-existent module for function call: '{obj}'")
        
        return result

    def get_dependency_map(self) -> Dict[str, Dict[str, List[str]]]:
        """Scan all modules in the system, extract their imports and function calls,
        and build a comprehensive directed graph of dependencies.
        
        This method scans Python files in the current directory and subdirectories,
        parses each file to extract imports and function calls, and builds a
        comprehensive dependency map. The map is stored persistently as a JSON file
        and updated after each successful mutation.
        
        Returns:
            The comprehensive dependency map with structure:
            {
                "imports": {module_name: {imported_module: [imported_names]}},
                "calls": {module_name: {called_object: [called_functions]}}
            }
        """
        # Reset the dependency map to start fresh
        self.dependency_map = {"imports": {}, "calls": {}}
        
        # Walk through all Python files in the current directory and subdirectories
        for root, dirs, files in os.walk('.'):
            # Skip hidden directories and common non-source directories
            dirs[:] = [d for d in dirs if not d.startswith('.') and d not in {'__pycache__', 'venv', 'env', '.git'}]
            
            for file in files:
                if file.endswith('.py'):
                    filepath = os.path.join(root, file)
                    # Create a module name from the filepath (relative to current directory)
                    module_name = os.path.splitext(filepath)[0].replace(os.sep, '.')
                    if module_name.startswith('.'):
                        module_name = module_name[1:]
                    
                    try:
                        imports, calls = self.parse_file(filepath)
                        
                        # Update the dependency map with parsed data
                        if imports:
                            if module_name not in self.dependency_map["imports"]:
                                self.dependency_map["imports"][module_name] = {}
                            for mod, names in imports.items():
                                if mod not in self.dependency_map["imports"][module_name]:
                                    self.dependency_map["imports"][module_name][mod] = []
                                self.dependency_map["imports"][module_name][mod].extend(names)
                                self.dependency_map["imports"][module_name][mod] = list(
                                    set(self.dependency_map["imports"][module_name][mod])
                                )
                        
                        if calls:
                            if module_name not in self.dependency_map["calls"]:
                                self.dependency_map["calls"][module_name] = {}
                            for obj, funcs in calls.items():
                                if obj not in self.dependency_map["calls"][module_name]:
                                    self.dependency_map["calls"][module_name][obj] = []
                                self.dependency_map["calls"][module_name][obj].extend(funcs)
                                self.dependency_map["calls"][module_name][obj] = list(
                                    set(self.dependency_map["calls"][module_name][obj])
                                )
                    except (SyntaxError, IOError) as e:
                        # Skip files that can't be parsed
                        continue
        
        # Save the comprehensive map to the JSON file
        self.save_map()
        
        return self.dependency_map


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


def validate_mutation_safety(mutation_diff: str, dependency_map: Dict[str, Dict[str, List[str]]]) -> Dict[str, object]:
    """Convenience function to validate mutation safety.
    
    Args:
        mutation_diff: A string representing the diff of the proposed code change
        dependency_map: The current dependency map to validate against
        
    Returns:
        A dictionary with 'passed' (bool) and 'errors' (list of str) keys
    """
    validator = DependencyValidator()
    return validator.validate_mutation_safety(mutation_diff, dependency_map)


def get_dependency_map(map_file: str = "dependency_map.json") -> Dict[str, Dict[str, List[str]]]:
    """Convenience function to get the comprehensive dependency map.
    
    This function scans all Python modules in the system, extracts their imports
    and function calls, and builds a comprehensive directed graph of dependencies.
    The map is stored persistently as a JSON file and updated after each successful mutation.
    
    Args:
        map_file: Path to dependency map JSON file
        
    Returns:
        The comprehensive dependency map
    """
    validator = DependencyValidator(map_file)
    return validator.get_dependency_map()