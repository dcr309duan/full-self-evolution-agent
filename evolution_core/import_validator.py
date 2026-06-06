"""Module for validating that imports in a proposed new file would resolve correctly.

This module provides a pre-creation validation function that parses import
statements from a proposed file and verifies each module exists in sys.path
before allowing file creation. It helps prevent runtime import errors by
catching missing dependencies early.
"""

import ast
import sys
import importlib
import importlib.util
from pathlib import Path
from typing import List, Tuple, Set, Optional


def _extract_imports(source_code: str) -> List[Tuple[str, Optional[str]]]:
    """Parse Python source code and extract all import statements.
    
    Args:
        source_code: The Python source code to parse.
        
    Returns:
        A list of tuples, each containing (module_name, alias) where alias
        is None for direct imports or the 'as' name for aliased imports.
    """
    imports = []
    try:
        tree = ast.parse(source_code)
    except SyntaxError:
        # If we can't parse, we can't validate imports
        return imports
    
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append((alias.name, alias.asname))
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ''
            for alias in node.names:
                full_module = f"{module}.{alias.name}" if module else alias.name
                imports.append((full_module, alias.asname))
    
    return imports


def _check_module_exists(module_name: str) -> bool:
    """Check if a module can be imported from sys.path.
    
    Args:
        module_name: The fully qualified module name to check.
        
    Returns:
        True if the module exists and can be imported, False otherwise.
    """
    # Handle relative imports - we can't validate these without knowing
    # the package context, so we assume they're valid
    if module_name.startswith('.'):
        return True
    
    # Check if it's a built-in module
    if module_name in sys.builtin_module_names:
        return True
    
    # Try to find the module spec
    try:
        spec = importlib.util.find_spec(module_name)
        return spec is not None
    except (ModuleNotFoundError, ValueError, ImportError):
        return False


def validate_imports(source_code: str, additional_paths: Optional[List[str]] = None) -> Tuple[bool, List[str]]:
    """Validate that all imports in the given source code would resolve.
    
    Parses the source code, extracts all import statements, and checks if
    each imported module exists in sys.path (or additional paths).
    
    Args:
        source_code: The Python source code to validate.
        additional_paths: Optional list of additional paths to add to sys.path
            temporarily for validation.
            
    Returns:
        A tuple of (is_valid, errors) where is_valid is True if all imports
        resolve, and errors is a list of error messages for failed imports.
    """
    errors = []
    
    # Temporarily add additional paths if provided
    original_paths = None
    if additional_paths:
        original_paths = sys.path.copy()
        for path in additional_paths:
            if path not in sys.path:
                sys.path.insert(0, path)
    
    try:
        imports = _extract_imports(source_code)
        
        for module_name, alias in imports:
            if not _check_module_exists(module_name):
                alias_info = f" as {alias}" if alias else ""
                errors.append(
                    f"Import '{module_name}{alias_info}' could not be resolved. "
                    f"Module not found in sys.path."
                )
    finally:
        # Restore original sys.path if we modified it
        if original_paths is not None:
            sys.path = original_paths
    
    return len(errors) == 0, errors


def validate_file_creation(file_path: str, source_code: str, 
                          additional_paths: Optional[List[str]] = None) -> Tuple[bool, List[str]]:
    """Validate that a proposed new file can be created with resolvable imports.
    
    This is the main entry point for pre-creation validation. It checks that
    all imports in the source code would resolve correctly before the file
    is actually created.
    
    Args:
        file_path: The proposed file path (used for error reporting).
        source_code: The Python source code to validate.
        additional_paths: Optional list of additional paths to search for modules.
        
    Returns:
        A tuple of (can_create, errors) where can_create is True if the file
        can be safely created, and errors is a list of error messages.
    """
    is_valid, import_errors = validate_imports(source_code, additional_paths)
    
    if not is_valid:
        errors = [
            f"Cannot create file '{file_path}': unresolved imports detected.",
            *import_errors
        ]
        return False, errors
    
    return True, []


def get_resolvable_modules() -> Set[str]:
    """Get a set of all module names that are currently resolvable.
    
    Useful for debugging and understanding what's available in the
    current Python environment.
    
    Returns:
        A set of module names that can be imported.
    """
    modules = set(sys.builtin_module_names)
    
    for path in sys.path:
        path_obj = Path(path)
        if not path_obj.exists():
            continue
        
        # Add top-level modules/packages
        for item in path_obj.iterdir():
            if item.suffix == '.py' and item.stem != '__init__':
                modules.add(item.stem)
            elif item.is_dir() and (item / '__init__.py').exists():
                modules.add(item.stem)
    
    return modules


# Convenience function for quick validation
def quick_validate(source_code: str) -> bool:
    """Quick validation that returns True if all imports resolve.
    
    Args:
        source_code: The Python source code to validate.
        
    Returns:
        True if all imports resolve, False otherwise.
    """
    is_valid, _ = validate_imports(source_code)
    return is_valid