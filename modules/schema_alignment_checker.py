"""Schema alignment checker for predicting conflicts without modifying files.

This module provides a method to simulate schema alignment checks and return
a conflict score based on how many data contracts would be violated.
"""

import ast
import os
from typing import Dict, List, Any, Optional, Tuple


def predict_conflicts(
    module_path: str,
    proposed_changes: Dict[str, Any],
    contract_definitions: Optional[Dict[str, Any]] = None,
) -> float:
    """Simulate schema alignment checks and return a conflict score.

    Analyzes proposed changes to a module and predicts how many data contracts
    would be violated without actually modifying any files. Returns a score
    between 0.0 (no conflicts) and 1.0 (all contracts violated).

    Args:
        module_path: Path to the Python module file to analyze.
        proposed_changes: Dictionary describing proposed changes. Expected keys:
            - 'additions': List of dicts with 'name', 'type', 'nullable' keys
            - 'removals': List of dicts with 'name' key
            - 'modifications': List of dicts with 'name', 'old_type', 'new_type'
        contract_definitions: Optional dictionary of existing data contracts.
            If None, attempts to extract from module source.

    Returns:
        Float between 0.0 and 1.0 representing conflict severity.
    """
    if not os.path.exists(module_path):
        return 1.0  # Missing module is a complete conflict

    # Extract existing contracts if not provided
    if contract_definitions is None:
        contract_definitions = _extract_contracts_from_module(module_path)

    if not contract_definitions:
        return 0.0  # No contracts to violate

    # Normalize proposed changes
    additions = proposed_changes.get("additions", [])
    removals = proposed_changes.get("removals", [])
    modifications = proposed_changes.get("modifications", [])

    total_contracts = len(contract_definitions)
    violated_contracts = 0

    # Check removals against contracts
    for removal in removals:
        field_name = removal.get("name", "")
        if field_name in contract_definitions:
            violated_contracts += 1

    # Check modifications against contracts
    for modification in modifications:
        field_name = modification.get("name", "")
        if field_name in contract_definitions:
            old_type = modification.get("old_type", "")
            new_type = modification.get("new_type", "")
            contract_type = contract_definitions[field_name].get("type", "")

            # Type change is a violation
            if old_type != new_type:
                violated_contracts += 1

    # Check additions for potential conflicts (e.g., name collisions)
    for addition in additions:
        field_name = addition.get("name", "")
        if field_name in contract_definitions:
            violated_contracts += 1

    # Calculate score
    if total_contracts == 0:
        return 0.0

    score = violated_contracts / total_contracts
    return min(score, 1.0)


def _extract_contracts_from_module(module_path: str) -> Dict[str, Any]:
    """Extract data contracts from a Python module by parsing its AST.

    Looks for class definitions and function signatures that might represent
    data contracts (e.g., dataclasses, TypedDicts, or classes with type annotations).

    Args:
        module_path: Path to the Python module file.

    Returns:
        Dictionary mapping field names to their type information.
    """
    try:
        with open(module_path, "r") as f:
            source = f.read()
    except (IOError, OSError):
        return {}

    try:
        tree = ast.parse(source)
    except SyntaxError:
        return {}

    contracts: Dict[str, Any] = {}

    for node in ast.walk(tree):
        # Look for class definitions with type annotations
        if isinstance(node, ast.ClassDef):
            for item in node.body:
                if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                    field_name = item.target.id
                    field_type = _get_type_name(item.annotation)
                    contracts[field_name] = {
                        "type": field_type,
                        "nullable": _is_nullable(item.annotation),
                    }

        # Look for function signatures (e.g., __init__ parameters)
        if isinstance(node, ast.FunctionDef):
            if node.name == "__init__":
                for arg in node.args.args:
                    if arg.arg == "self":
                        continue
                    field_name = arg.arg
                    if arg.annotation:
                        field_type = _get_type_name(arg.annotation)
                        contracts[field_name] = {
                            "type": field_type,
                            "nullable": _is_nullable(arg.annotation),
                        }

    return contracts


def _get_type_name(annotation_node: Optional[ast.AST]) -> str:
    """Extract a type name from an AST annotation node.

    Args:
        annotation_node: AST node representing a type annotation.

    Returns:
        String representation of the type.
    """
    if annotation_node is None:
        return "Any"

    if isinstance(annotation_node, ast.Name):
        return annotation_node.id

    if isinstance(annotation_node, ast.Subscript):
        # Handle generic types like List[str], Optional[int]
        base_type = _get_type_name(annotation_node.value)
        sub_type = _get_type_name(annotation_node.slice)
        return f"{base_type}[{sub_type}]"

    if isinstance(annotation_node, ast.Attribute):
        # Handle fully qualified names like typing.Optional
        return f"{_get_type_name(annotation_node.value)}.{annotation_node.attr}"

    if isinstance(annotation_node, ast.Constant):
        return str(annotation_node.value)

    return "Unknown"


def _is_nullable(annotation_node: Optional[ast.AST]) -> bool:
    """Check if a type annotation indicates a nullable field.

    Args:
        annotation_node: AST node representing a type annotation.

    Returns:
        True if the type is Optional or has a None default.
    """
    if annotation_node is None:
        return True  # Missing annotation implies Any, which could be None

    if isinstance(annotation_node, ast.Subscript):
        base_type = _get_type_name(annotation_node.value)
        if base_type in ("Optional", "Union"):
            return True

    if isinstance(annotation_node, ast.Attribute):
        if annotation_node.attr == "Optional":
            return True

    return False


def get_contract_summary(module_path: str) -> Dict[str, Any]:
    """Get a summary of all data contracts found in a module.

    Args:
        module_path: Path to the Python module file.

    Returns:
        Dictionary with contract count and list of field names.
    """
    contracts = _extract_contracts_from_module(module_path)
    return {
        "total_contracts": len(contracts),
        "fields": list(contracts.keys()),
        "contracts": contracts,
    }