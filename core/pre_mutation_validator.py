import ast
import sys
import os
import importlib.util
from typing import List, Dict, Any, Tuple, Optional


class PreMutationValidator:
    """
    Validates proposed mutations before they are applied to the codebase.
    Provides clean implementation with syntax validation, import resolution,
    and structured error reporting.
    """

    def __init__(self):
        self.validation_errors: List[Dict[str, Any]] = []

    def validate_mutation_proposal(self, code_string: str, target_file: str) -> Dict[str, Any]:
        """
        Validate a mutation proposal (code string + target file).
        
        Args:
            code_string: The proposed new code as a string
            target_file: The file path where the code will be applied
            
        Returns:
            Dict with 'valid' (bool), 'errors' (list of dicts with 'error_type', 'file', 'line', 'message')
        """
        self.validation_errors = []
        
        # Step 1: Syntax validation using ast.parse()
        syntax_valid, syntax_errors = self._validate_syntax(code_string, target_file)
        if not syntax_valid:
            return {
                'valid': False,
                'errors': syntax_errors
            }
        
        # Step 2: Parse the AST for import analysis
        try:
            tree = ast.parse(code_string)
        except SyntaxError as e:
            return {
                'valid': False,
                'errors': [{
                    'error_type': 'syntax_error',
                    'file': target_file,
                    'line': e.lineno or 0,
                    'message': str(e)
                }]
            }
        
        # Step 3: Resolve imports and check module availability
        import_errors = self._validate_imports(tree, target_file)
        if import_errors:
            return {
                'valid': False,
                'errors': import_errors
            }
        
        # Step 4: Check required standard modules
        module_errors = self._check_required_modules(tree)
        if module_errors:
            return {
                'valid': False,
                'errors': module_errors
            }
        
        return {
            'valid': True,
            'errors': []
        }

    def _validate_syntax(self, code_string: str, target_file: str) -> Tuple[bool, List[Dict[str, Any]]]:
        """
        Validate Python syntax using ast.parse().
        
        Returns:
            Tuple of (is_valid, list of error dicts)
        """
        errors = []
        try:
            ast.parse(code_string)
            return True, errors
        except SyntaxError as e:
            errors.append({
                'error_type': 'syntax_error',
                'file': target_file,
                'line': e.lineno or 0,
                'message': f"Syntax error: {e.msg}"
            })
            return False, errors

    def _validate_imports(self, tree: ast.AST, target_file: str) -> List[Dict[str, Any]]:
        """
        Validate all import statements in the AST against the filesystem.
        
        Args:
            tree: The parsed AST
            target_file: The file path for error reporting
            
        Returns:
            List of error dicts for invalid imports
        """
        errors = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if not self._resolve_import(alias.name):
                        errors.append({
                            'error_type': 'import_error',
                            'file': target_file,
                            'line': node.lineno,
                            'message': f"Cannot resolve import '{alias.name}'"
                        })
            
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    if not self._resolve_import(node.module):
                        errors.append({
                            'error_type': 'import_error',
                            'file': target_file,
                            'line': node.lineno,
                            'message': f"Cannot resolve import '{node.module}'"
                        })
        
        return errors

    def _resolve_import(self, module_name: str) -> bool:
        """
        Resolve an import statement against the current filesystem.
        
        Uses sys.path and os.path.exists to check if the module can be found.
        Also checks for built-in modules and standard library modules.
        
        Args:
            module_name: The module name to resolve
            
        Returns:
            True if the module can be resolved, False otherwise
        """
        # Check if it's a built-in or standard library module
        if module_name in sys.builtin_module_names:
            return True
        
        # Check using importlib.util.find_spec for installed packages
        spec = importlib.util.find_spec(module_name)
        if spec is not None:
            return True
        
        # Check against sys.path for local modules
        for path in sys.path:
            # Check for module as a file
            module_path = os.path.join(path, module_name.replace('.', os.sep) + '.py')
            if os.path.exists(module_path):
                return True
            
            # Check for module as a package (directory with __init__.py)
            package_path = os.path.join(path, module_name.replace('.', os.sep))
            init_path = os.path.join(package_path, '__init__.py')
            if os.path.exists(init_path):
                return True
        
        return False

    def _check_required_modules(self, tree: ast.AST) -> List[Dict[str, Any]]:
        """
        Check that required modules (numpy, random, etc.) are available.
        
        Args:
            tree: The parsed AST
            
        Returns:
            List of error dicts for missing required modules
        """
        errors = []
        required_modules = {'numpy', 'random', 'math', 'os', 'sys', 'json', 'collections', 'itertools', 'functools'}
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    base_module = alias.name.split('.')[0]
                    if base_module in required_modules:
                        spec = importlib.util.find_spec(base_module)
                        if spec is None:
                            errors.append({
                                'error_type': 'module_not_found',
                                'file': '',
                                'line': node.lineno,
                                'message': f"Required module '{base_module}' is not available"
                            })
            
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    base_module = node.module.split('.')[0]
                    if base_module in required_modules:
                        spec = importlib.util.find_spec(base_module)
                        if spec is None:
                            errors.append({
                                'error_type': 'module_not_found',
                                'file': '',
                                'line': node.lineno,
                                'message': f"Required module '{base_module}' is not available"
                            })
        
        return errors

    def validate_mutation(self, mutation: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate a proposed mutation (backward compatibility method).
        
        Args:
            mutation: Dict with keys 'files' (list of file paths) and 'changes' (dict mapping file path to new code)
            
        Returns:
            Dict with 'passed' (bool), 'errors' (list of str), and optionally 'fallback_mutation'
        """
        self.validation_errors = []
        
        files = mutation.get('files', [])
        changes = mutation.get('changes', {})
        
        if not files or not changes:
            return {
                'passed': False,
                'errors': ['No files or changes provided'],
                'warnings': []
            }
        
        all_errors = []
        for file_path in files:
            code_string = changes.get(file_path, '')
            if not code_string:
                all_errors.append(f"No code provided for {file_path}")
                continue
            
            result = self.validate_mutation_proposal(code_string, file_path)
            if not result['valid']:
                for error in result['errors']:
                    all_errors.append(f"{error['file']}:{error['line']} - {error['message']}")
        
        if all_errors:
            return {
                'passed': False,
                'errors': all_errors,
                'warnings': [],
                'fallback_mutation': self._generate_fallback(mutation)
            }
        
        return {
            'passed': True,
            'errors': [],
            'warnings': []
        }

    def _generate_fallback(self, original_mutation: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate a simplified fallback mutation that modifies only a single file with minimal changes.
        """
        files = original_mutation.get('files', [])
        changes = original_mutation.get('changes', {})

        if not files or not changes:
            return {'files': [], 'changes': {}}

        # Pick the first file that has changes
        target_file = files[0]
        original_code = changes.get(target_file, '')

        # Generate minimal change: add a comment
        fallback_code = original_code + '\n# Fallback mutation: minimal change\n'

        return {
            'files': [target_file],
            'changes': {target_file: fallback_code}
        }


def validate_mutation(mutation: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convenience function to validate a mutation using the PreMutationValidator.
    """
    validator = PreMutationValidator()
    return validator.validate_mutation(mutation)


def validate_mutation_proposal(code_string: str, target_file: str) -> Dict[str, Any]:
    """
    Convenience function to validate a mutation proposal using the PreMutationValidator.
    """
    validator = PreMutationValidator()
    return validator.validate_mutation_proposal(code_string, target_file)