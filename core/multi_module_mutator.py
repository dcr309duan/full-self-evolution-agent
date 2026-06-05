import ast
import builtins
import sys
from typing import List, Tuple, Optional, Dict, Any

# Standard library modules that are always safe to import
SAFE_STDLIB_MODULES = {
    'abc', 'ast', 'asyncio', 'base64', 'binascii', 'bisect', 'builtins',
    'calendar', 'collections', 'colorsys', 'contextlib', 'copy', 'csv',
    'datetime', 'decimal', 'difflib', 'dis', 'enum', 'errno', 'fcntl',
    'filecmp', 'fnmatch', 'fractions', 'functools', 'gc', 'getopt',
    'getpass', 'gettext', 'glob', 'grp', 'gzip', 'hashlib', 'heapq',
    'hmac', 'html', 'http', 'importlib', 'inspect', 'io', 'itertools',
    'json', 'keyword', 'linecache', 'locale', 'logging', 'lzma',
    'mailbox', 'markupbase', 'marshal', 'math', 'mimetypes', 'mmap',
    'modulefinder', 'multiprocessing', 'netrc', 'nis', 'nntplib',
    'numbers', 'operator', 'optparse', 'os', 'pathlib', 'pdb', 'pickle',
    'pickletools', 'pipes', 'pkgutil', 'platform', 'plistlib', 'poplib',
    'posix', 'posixpath', 'pprint', 'profile', 'pstats', 'pty', 'pwd',
    'py_compile', 'pyclbr', 'pydoc', 'queue', 'quopri', 'random',
    're', 'readline', 'reprlib', 'resource', 'rlcompleter', 'runpy',
    'sched', 'secrets', 'select', 'selectors', 'shelve', 'shlex',
    'shutil', 'signal', 'site', 'smtpd', 'smtplib', 'sndhdr', 'socket',
    'socketserver', 'sqlite3', 'ssl', 'stat', 'statistics', 'string',
    'stringprep', 'struct', 'subprocess', 'sunau', 'symtable', 'sys',
    'sysconfig', 'syslog', 'tabnanny', 'tarfile', 'telnetlib', 'tempfile',
    'termios', 'test', 'textwrap', 'threading', 'time', 'timeit',
    'tkinter', 'token', 'tokenize', 'trace', 'traceback', 'tracemalloc',
    'tty', 'turtle', 'types', 'typing', 'unicodedata', 'unittest',
    'urllib', 'uu', 'uuid', 'venv', 'warnings', 'wave', 'weakref',
    'webbrowser', 'winreg', 'winsound', 'wsgiref', 'xdrlib', 'xml',
    'xmlrpc', 'zipapp', 'zipfile', 'zipimport', 'zlib'
}


class CrossModuleImportValidator:
    """Simplified import checker that only validates standard library imports."""
    
    @staticmethod
    def validate_imports(source_code: str) -> Tuple[bool, Optional[str]]:
        """
        Validate that all imports in the source code are from the standard library.
        Returns (True, None) if valid, (False, error_message) if invalid.
        """
        try:
            tree = ast.parse(source_code)
        except SyntaxError as e:
            return False, f"Syntax error: {e}"
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    module_name = alias.name.split('.')[0]
                    if module_name not in SAFE_STDLIB_MODULES and module_name != '__future__':
                        return False, f"Import '{alias.name}' is not from standard library"
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    module_name = node.module.split('.')[0]
                    if module_name not in SAFE_STDLIB_MODULES and module_name != '__future__':
                        return False, f"Import from '{node.module}' is not from standard library"
        
        return True, None


class MultiModuleMutator:
    """
    A specialized mutator for coordinated changes across multiple modules.
    Generates mutations that modify all targets in a single atomic operation.
    """
    
    def __init__(self, max_targets: int = 3):
        self.max_targets = max_targets
        self.validator = CrossModuleImportValidator()
    
    def generate_mutation_plan(self, target_modules: List[str]) -> Optional[Dict[str, Any]]:
        """
        Generate a mutation plan for a list of target modules.
        Returns a dict with 'modules' (list of module names) and 'mutations' (list of mutation dicts).
        """
        if not target_modules:
            return None
        
        if len(target_modules) > self.max_targets:
            target_modules = target_modules[:self.max_targets]
        
        # Generate a simple mutation plan that adds a helper function to each module
        mutations = []
        for i, module_name in enumerate(target_modules):
            mutation = {
                'module': module_name,
                'type': 'add_function',
                'function_name': f'_coordinated_helper_{i}',
                'function_body': f'def _coordinated_helper_{i}():\n    """Helper function for coordinated mutation."""\n    pass\n'
            }
            mutations.append(mutation)
        
        return {
            'modules': target_modules,
            'mutations': mutations
        }
    
    def validate_mutation_consistency(self, mutation_plan: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """
        Validate that the mutation plan maintains cross-module consistency.
        Checks that function names don't conflict and that the plan is well-formed.
        """
        if 'modules' not in mutation_plan or 'mutations' not in mutation_plan:
            return False, "Mutation plan must contain 'modules' and 'mutations' keys"
        
        modules = mutation_plan['modules']
        mutations = mutation_plan['mutations']
        
        if len(modules) != len(mutations):
            return False, "Number of modules must match number of mutations"
        
        # Check for duplicate function names across mutations
        function_names = set()
        for mutation in mutations:
            if mutation.get('type') == 'add_function':
                func_name = mutation.get('function_name')
                if func_name in function_names:
                    return False, f"Duplicate function name '{func_name}' across mutations"
                function_names.add(func_name)
        
        return True, None
    
    def apply_atomic_mutation(self, mutation_plan: Dict[str, Any], module_sources: Dict[str, str]) -> Tuple[bool, Optional[str], Dict[str, str]]:
        """
        Apply the mutation plan atomically to all modules.
        Returns (success, error_message, updated_sources).
        """
        # Validate the plan first
        valid, error = self.validate_mutation_consistency(mutation_plan)
        if not valid:
            return False, error, {}
        
        updated_sources = {}
        
        for mutation in mutation_plan['mutations']:
            module_name = mutation['module']
            if module_name not in module_sources:
                return False, f"Module '{module_name}' not found in provided sources", {}
            
            source = module_sources[module_name]
            
            if mutation['type'] == 'add_function':
                # Add the function to the module source
                new_source = source.rstrip() + '\n\n' + mutation['function_body']
                
                # Validate imports in the new source
                valid_imports, import_error = self.validator.validate_imports(new_source)
                if not valid_imports:
                    return False, f"Import validation failed for {module_name}: {import_error}", {}
                
                updated_sources[module_name] = new_source
            else:
                return False, f"Unknown mutation type: {mutation['type']}", {}
        
        return True, None, updated_sources
    
    def create_coordinated_mutation(self, target_modules: List[str], module_sources: Dict[str, str]) -> Tuple[bool, Optional[str], Dict[str, str]]:
        """
        High-level method to create and apply a coordinated mutation.
        Returns (success, error_message, updated_sources).
        """
        plan = self.generate_mutation_plan(target_modules)
        if plan is None:
            return False, "Failed to generate mutation plan", {}
        
        return self.apply_atomic_mutation(plan, module_sources)


def create_multi_module_mutator(max_targets: int = 3) -> MultiModuleMutator:
    """Factory function to create a MultiModuleMutator instance."""
    return MultiModuleMutator(max_targets=max_targets)