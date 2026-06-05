import ast
import sys
from typing import List, Dict, Tuple, Optional, Set
from dataclasses import dataclass, field
from pathlib import Path

# Import the interface usage map (assumed to be available)
try:
    from self_model.interface_usage_map import interface_usage_map
except ImportError:
    # Fallback: define a minimal type for the map
    interface_usage_map: Dict[str, List[Dict]] = {}

@dataclass
class AffectedModule:
    module_path: str
    affected_functions: List[str] = field(default_factory=list)

@dataclass
class MutationInfo:
    file_path: str
    old_code: str
    new_code: str

@dataclass
class SideEffectResult:
    affected_modules: List[AffectedModule] = field(default_factory=list)
    risk_score: int = 0

def _extract_interface_names(code: str) -> Set[str]:
    """Extract function/class names defined in the given code."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return set()
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            names.add(node.name)
        elif isinstance(node, ast.AsyncFunctionDef):
            names.add(node.name)
        elif isinstance(node, ast.ClassDef):
            names.add(node.name)
    return names

def _extract_imported_names(code: str) -> Set[str]:
    """Extract names that are imported or used from other modules."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return set()
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                names.add(alias.name)
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute):
                names.add(node.func.attr)
            elif isinstance(node.func, ast.Name):
                names.add(node.func.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
    return names

def _detect_signature_change(old_code: str, new_code: str) -> bool:
    """Detect if any function/class signature changed between old and new code."""
    try:
        old_tree = ast.parse(old_code)
        new_tree = ast.parse(new_code)
    except SyntaxError:
        return False

    old_funcs = {}
    new_funcs = {}

    for node in ast.walk(old_tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            old_funcs[node.name] = node.args

    for node in ast.walk(new_tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            new_funcs[node.name] = node.args

    for func_name in set(old_funcs.keys()) & set(new_funcs.keys()):
        old_args = old_funcs[func_name]
        new_args = new_funcs[func_name]
        # Compare argument lists (excluding self/cls for methods)
        if ast.dump(old_args) != ast.dump(new_args):
            return True

    return False

def _trace_callers(interface_name: str, depth: int = 2) -> List[Tuple[str, str]]:
    """Trace callers of a given interface up to specified depth."""
    callers = []
    visited = set()

    def _trace(name: str, current_depth: int):
        if current_depth > depth or name in visited:
            return
        visited.add(name)
        # Look up callers in the interface usage map
        callers_info = interface_usage_map.get(name, [])
        for caller in callers_info:
            module = caller.get('module', '')
            function = caller.get('function', '')
            if module and function:
                callers.append((module, function))
                # Recurse to trace deeper
                _trace(function, current_depth + 1)

    _trace(interface_name, 0)
    return callers

def _calculate_risk_score(num_callers: int, depth: int, signature_changed: bool) -> int:
    """Calculate risk score based on callers count, depth, and signature change."""
    score = 0
    # Base score from number of callers (max 40 points)
    score += min(num_callers * 10, 40)
    # Depth factor (max 30 points)
    score += min(depth * 15, 30)
    # Signature change penalty (30 points if changed)
    if signature_changed:
        score += 30
    return min(score, 100)

def simulate_side_effects(mutation: MutationInfo) -> SideEffectResult:
    """
    Simulate side effects of a proposed mutation.

    Args:
        mutation: A MutationInfo object containing file path, old code, and new code.

    Returns:
        A SideEffectResult containing affected modules and risk score.
    """
    result = SideEffectResult()

    # Extract interfaces from old and new code
    old_interfaces = _extract_interface_names(mutation.old_code)
    new_interfaces = _extract_interface_names(mutation.new_code)

    # Determine which interfaces are changed (removed, added, or modified)
    changed_interfaces = old_interfaces | new_interfaces

    # Detect signature changes
    signature_changed = _detect_signature_change(mutation.old_code, mutation.new_code)

    # Collect all callers for changed interfaces
    all_callers: List[Tuple[str, str]] = []
    for interface in changed_interfaces:
        callers = _trace_callers(interface, depth=2)
        all_callers.extend(callers)

    # Deduplicate callers
    unique_callers = list(set(all_callers))

    # Group callers by module
    module_to_functions: Dict[str, Set[str]] = {}
    for module, function in unique_callers:
        if module not in module_to_functions:
            module_to_functions[module] = set()
        module_to_functions[module].add(function)

    # Build affected modules list
    for module_path, functions in module_to_functions.items():
        affected_module = AffectedModule(
            module_path=module_path,
            affected_functions=list(functions)
        )
        result.affected_modules.append(affected_module)

    # Calculate risk score
    num_callers = len(unique_callers)
    max_depth = 0
    for interface in changed_interfaces:
        # Re-trace to find max depth (simplified: use number of unique callers as proxy)
        pass
    # Use number of callers and depth from tracing
    # For simplicity, depth is approximated by the number of unique callers per interface
    depth_factor = min(len(changed_interfaces), 2)  # Max depth 2 as per requirement
    result.risk_score = _calculate_risk_score(num_callers, depth_factor, signature_changed)

    return result

def simulate_side_effects_from_file(file_path: str, old_code: str, new_code: str) -> SideEffectResult:
    """
    Convenience function to simulate side effects from file path and code strings.

    Args:
        file_path: Path to the file being mutated.
        old_code: Original code content.
        new_code: New code content.

    Returns:
        A SideEffectResult.
    """
    mutation = MutationInfo(file_path=file_path, old_code=old_code, new_code=new_code)
    return simulate_side_effects(mutation)