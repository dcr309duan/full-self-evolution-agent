"""Static AST-based validation module for Python agent modules.

Provides functions to validate Python source files by analyzing their AST
for syntax validity, type consistency, unresolved references, and structural invariants.
"""

import ast
import sys
import importlib.util
import os
from typing import Dict, List, Optional, Set, Tuple, Any
from pathlib import Path


def _get_imported_modules(tree: ast.AST) -> Dict[str, str]:
    """Extract imported module names and their aliases from an AST."""
    imports: Dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports[alias.asname or alias.name] = alias.name
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ''
            for alias in node.names:
                full_name = f"{module}.{alias.name}" if module else alias.name
                imports[alias.asname or alias.name] = full_name
    return imports


def _get_defined_names(tree: ast.AST) -> Set[str]:
    """Get all names defined in the module (functions, classes, variables at module level)."""
    defined: Set[str] = set()
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
            defined.add(node.name)
        elif isinstance(node, ast.ClassDef):
            defined.add(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    defined.add(target.id)
                elif isinstance(target, ast.Tuple) or isinstance(target, ast.List):
                    for elt in target.elts:
                        if isinstance(elt, ast.Name):
                            defined.add(elt.id)
        elif isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name):
                defined.add(node.target.id)
        elif isinstance(node, ast.Import) or isinstance(node, ast.ImportFrom):
            for alias in node.names:
                defined.add(alias.asname or alias.name)
    return defined


def _check_type_annotations(tree: ast.AST) -> List[str]:
    """Check basic type annotation consistency (e.g., annotated return types match actual returns)."""
    errors: List[str] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.returns is not None:
                # Check that return statements exist if annotated with non-None type
                has_return = False
                has_none_return = False
                for child in ast.walk(node):
                    if isinstance(child, ast.Return):
                        has_return = True
                        if child.value is None:
                            has_none_return = True
                        break
                # Simple heuristic: if annotated with something other than None, expect a return
                if not isinstance(node.returns, ast.Constant) or node.returns.value is not None:
                    if not has_return:
                        errors.append(
                            f"Function '{node.name}' annotated with return type but has no return statement"
                        )
            # Check parameter annotations
            for arg in node.args.args:
                if arg.arg == 'self' or arg.arg == 'cls':
                    continue
                if arg.annotation is None:
                    errors.append(
                        f"Parameter '{arg.arg}' in function '{node.name}' missing type annotation"
                    )
    return errors


def _check_unresolved_references(tree: ast.AST, module_path: str) -> List[str]:
    """Check for unresolved references (names used but not defined or imported)."""
    errors: List[str] = []
    defined_names = _get_defined_names(tree)
    imported_modules = _get_imported_modules(tree)

    # Add built-in names
    builtins = dir(__builtins__) if hasattr(__builtins__, '__dict__') else dir(__builtins__)
    defined_names.update(builtins)

    # Walk through all Name nodes and check if they are defined
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            # Skip function/class definitions and import targets
            if isinstance(node.ctx, (ast.Store, ast.Del)):
                continue
            # Skip names used in imports
            parent = getattr(node, 'parent', None)
            if parent is None:
                # Find parent manually
                for potential_parent in ast.walk(tree):
                    for child in ast.iter_child_nodes(potential_parent):
                        if child is node:
                            parent = potential_parent
                            break
                    if parent:
                        break
            if isinstance(parent, (ast.Import, ast.ImportFrom, ast.alias)):
                continue
            if node.id not in defined_names and node.id not in imported_modules:
                # Check if it's a module-level name that might be defined later
                errors.append(f"Unresolved reference: '{node.id}' at line {node.lineno}")

    return errors


def _check_structural_invariants(tree: ast.AST, config: Optional[Dict] = None) -> List[str]:
    """Check structural invariants like required function signatures."""
    errors: List[str] = []
    if config is None:
        return errors

    required_functions = config.get('required_functions', {})
    for func_name, expected_sig in required_functions.items():
        found = False
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == func_name:
                found = True
                # Check signature
                if expected_sig:
                    actual_args = [arg.arg for arg in node.args.args]
                    expected_args = expected_sig.get('args', [])
                    if actual_args != expected_args:
                        errors.append(
                            f"Function '{func_name}' has args {actual_args}, expected {expected_args}"
                        )
                    if 'returns' in expected_sig:
                        if node.returns is None:
                            errors.append(
                                f"Function '{func_name}' missing return annotation, expected {expected_sig['returns']}"
                            )
                break
        if not found:
            errors.append(f"Required function '{func_name}' not found in module")

    return errors


def validate_module_ast(module_path: str, config: Optional[Dict] = None) -> bool:
    """Parse and validate a Python module's AST.

    Checks:
    1. Syntax validity
    2. Type consistency (basic type annotations match usage)
    3. Unresolved references (imports exist, names defined before use)
    4. Structural invariants (required function signatures if specified in config)

    Args:
        module_path: Path to the Python module file.
        config: Optional dictionary with validation rules, e.g.:
            {'required_functions': {'my_func': {'args': ['x', 'y'], 'returns': 'int'}}}

    Returns:
        True if all checks pass, False otherwise.
    """
    if not os.path.exists(module_path):
        print(f"Error: Module file not found: {module_path}")
        return False

    # Read the source file
    try:
        with open(module_path, 'r', encoding='utf-8') as f:
            source = f.read()
    except IOError as e:
        print(f"Error reading file {module_path}: {e}")
        return False

    # 1. Syntax validity
    try:
        tree = ast.parse(source, filename=module_path)
    except SyntaxError as e:
        print(f"Syntax error in {module_path}: {e}")
        return False

    # Set parent references for AST nodes (needed for some checks)
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            child.parent = node

    all_errors: List[str] = []

    # 2. Type consistency
    type_errors = _check_type_annotations(tree)
    all_errors.extend(type_errors)

    # 3. Unresolved references
    ref_errors = _check_unresolved_references(tree, module_path)
    all_errors.extend(ref_errors)

    # 4. Structural invariants
    struct_errors = _check_structural_invariants(tree, config)
    all_errors.extend(struct_errors)

    if all_errors:
        print(f"Validation errors in {module_path}:")
        for error in all_errors:
            print(f"  - {error}")
        return False

    return True


def validate_module_importable(module_path: str) -> bool:
    """Check if a module can be imported without errors.

    This is a secondary check that actually tries to import the module
    to catch runtime import errors that AST analysis might miss.

    Args:
        module_path: Path to the Python module file.

    Returns:
        True if the module imports successfully, False otherwise.
    """
    try:
        module_name = Path(module_path).stem
        spec = importlib.util.spec_from_file_location(module_name, module_path)
        if spec is None:
            print(f"Could not create spec for {module_path}")
            return False
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return True
    except Exception as e:
        print(f"Import error for {module_path}: {e}")
        return False


if __name__ == "__main__":
    # Simple CLI usage
    if len(sys.argv) < 2:
        print("Usage: python static_validator.py <module_path> [config_path]")
        sys.exit(1)

    module_path = sys.argv[1]
    config = None
    if len(sys.argv) > 2:
        import json
        try:
            with open(sys.argv[2], 'r') as f:
                config = json.load(f)
        except (IOError, json.JSONDecodeError) as e:
            print(f"Error loading config: {e}")
            sys.exit(1)

    result = validate_module_ast(module_path, config)
    sys.exit(0 if result else 1)