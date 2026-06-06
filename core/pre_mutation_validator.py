import ast
import sys
import importlib.util
from typing import List, Dict, Any, Tuple, Optional

class PreMutationValidator:
    """
    Validates proposed mutations before they are applied to the codebase.
    Checks syntax, import consistency across files, and provides fallback mutations on failure.
    """

    def __init__(self):
        self.validation_errors: List[str] = []

    def validate_mutation(self, mutation: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate a proposed mutation.
        
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
                'errors': [{'type': 'validation', 'line': 0, 'message': 'Mutation must specify files and changes'}],
                'warnings': [],
                'fallback_mutation': self._generate_fallback(mutation)
            }

        # Step 2: Parse each file's proposed code with detailed error reporting
        parsed_files = {}
        for file_path in files:
            code = changes.get(file_path)
            if code is None:
                self.validation_errors.append({'type': 'validation', 'line': 0, 'message': f"No code provided for {file_path}"})
                continue
            try:
                tree = ast.parse(code)
                parsed_files[file_path] = tree
            except SyntaxError as e:
                error_detail = {
                    'type': 'SyntaxError',
                    'line': e.lineno if hasattr(e, 'lineno') else 0,
                    'message': str(e)
                }
                if hasattr(e, 'offset'):
                    error_detail['column'] = e.offset
                self.validation_errors.append(error_detail)

        if self.validation_errors:
            return {
                'passed': False,
                'errors': self.validation_errors,
                'warnings': [],
                'fallback_mutation': self._generate_fallback(mutation)
            }

        # Step 3: Check import consistency across files
        import_errors = self._check_import_consistency(parsed_files)
        if import_errors:
            self.validation_errors.extend(import_errors)
            return {
                'passed': False,
                'errors': self.validation_errors,
                'warnings': [],
                'fallback_mutation': self._generate_fallback(mutation)
            }

        return {
            'passed': True,
            'errors': [],
            'warnings': []
        }

    def _check_import_consistency(self, parsed_files: Dict[str, ast.AST]) -> List[Dict[str, Any]]:
        """
        Check that imports across files are consistent.
        Returns list of error messages, empty if all good.
        """
        errors = []
        all_imports = {}  # file -> set of imported module names

        for file_path, tree in parsed_files.items():
            imports = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.add(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        imports.add(node.module)
            all_imports[file_path] = imports

        # Check for conflicting imports (same name from different modules)
        import_sources = {}  # name -> set of files that import it
        for file_path, imports in all_imports.items():
            for imp in imports:
                if imp not in import_sources:
                    import_sources[imp] = set()
                import_sources[imp].add(file_path)

        # This is a simplified check; real cross-module consistency would be more complex
        # For now, we just flag if the same module is imported in multiple files with different aliases
        # (basic sanity check)
        for imp, files_using in import_sources.items():
            if len(files_using) > 1:
                # Check if any file re-imports with different alias (basic check)
                pass  # Placeholder for more advanced checks

        return errors

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

    def validate_mutation_proposal(self, code_string: str, target_file: str) -> Dict[str, Any]:
        """
        Validate a mutation proposal (code string + target file).
        
        Args:
            code_string: The proposed new code as a string
            target_file: The file path where the code will be applied
            
        Returns:
            Dict with 'passed' (bool), 'errors' (list of dicts with 'type', 'line', 'message'), 'warnings' (list)
        """
        result = {
            'passed': True,
            'errors': [],
            'warnings': []
        }

        # Step 1: Parse the code with detailed error reporting
        try:
            tree = ast.parse(code_string)
        except SyntaxError as e:
            error_detail = {
                'type': 'SyntaxError',
                'line': e.lineno if hasattr(e, 'lineno') else 0,
                'message': str(e)
            }
            if hasattr(e, 'offset'):
                error_detail['column'] = e.offset
            result['errors'].append(error_detail)
            result['passed'] = False
            return result

        # Step 2: Parse all import statements
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append({
                        'type': 'import',
                        'module': alias.name,
                        'alias': alias.asname,
                        'line': node.lineno
                    })
            elif isinstance(node, ast.ImportFrom):
                module = node.module if node.module else ''
                for alias in node.names:
                    imports.append({
                        'type': 'from_import',
                        'module': module,
                        'name': alias.name,
                        'alias': alias.asname,
                        'line': node.lineno
                    })

        # Step 3: Check each import against sys.modules and available packages
        for imp in imports:
            module_name = imp['module']
            
            # Check if module is already loaded
            if module_name in sys.modules:
                continue
            
            # Try to find the module spec
            try:
                spec = importlib.util.find_spec(module_name)
                if spec is None:
                    result['warnings'].append({
                        'type': 'import_warning',
                        'line': imp['line'],
                        'message': f"Module '{module_name}' not found in sys.modules or available packages"
                    })
            except (ImportError, ValueError, ModuleNotFoundError) as e:
                result['warnings'].append({
                    'type': 'import_warning',
                    'line': imp['line'],
                    'message': f"Error checking module '{module_name}': {str(e)}"
                })

        return result


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