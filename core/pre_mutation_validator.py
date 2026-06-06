import ast
import sys
import importlib.util
from typing import List, Dict, Any, Tuple, Optional

# Import the new robust implementation
from core.pre_mutation_guard import PreMutationGuard

class PreMutationValidator:
    """
    Validates proposed mutations before they are applied to the codebase.
    This is now a thin wrapper around PreMutationGuard for backward compatibility.
    """

    def __init__(self):
        self.validation_errors: List[str] = []
        self._guard = PreMutationGuard()

    def validate_mutation(self, mutation: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate a proposed mutation.
        
        Args:
            mutation: Dict with keys 'files' (list of file paths) and 'changes' (dict mapping file path to new code)
            
        Returns:
            Dict with 'passed' (bool), 'errors' (list of str), and optionally 'fallback_mutation'
        """
        self.validation_errors = []
        
        # Delegate to PreMutationGuard
        guard_result = self._guard.validate_mutation(mutation)
        
        # Convert guard result to legacy format if needed
        if guard_result.get('passed'):
            return {
                'passed': True,
                'errors': [],
                'warnings': []
            }
        else:
            self.validation_errors = guard_result.get('errors', [])
            return {
                'passed': False,
                'errors': self.validation_errors,
                'warnings': guard_result.get('warnings', []),
                'fallback_mutation': self._generate_fallback(mutation)
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
        # Delegate to PreMutationGuard
        return self._guard.validate_mutation_proposal(code_string, target_file)


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