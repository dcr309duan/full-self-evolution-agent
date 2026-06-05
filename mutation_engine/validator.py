"""Multi-phase mutation validator.

Performs validation of mutations across three phases:
1. Static AST-level checks (syntax, structure, imports)
2. Dependency graph analysis (critical interface impact) with side effect simulation
3. Sandboxed execution with test suite

Returns structured results with pass/fail per phase.
"""

import ast
import copy
import importlib
import importlib.util
import os
import sys
import tempfile
import traceback
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# Phase 2 integration
try:
    from self_model.builder import get_dependency_graph
except ImportError:
    get_dependency_graph = None

# Side effect simulator integration
try:
    from side_effect_simulator import simulate_side_effects
except ImportError:
    simulate_side_effects = None

# Phase 3 integration
try:
    from testing_framework import run_tests
except ImportError:
    run_tests = None


class ValidationResult:
    """Structured result from the mutation validator."""

    def __init__(self):
        self.phase1: Dict[str, Any] = {"passed": False, "details": []}
        self.phase2: Dict[str, Any] = {"passed": False, "details": [], "side_effects": None}
        self.phase3: Dict[str, Any] = {"passed": False, "details": []}
        self.overall_passed: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "phase1": self.phase1,
            "phase2": self.phase2,
            "phase3": self.phase3,
            "overall_passed": self.overall_passed,
        }


# ---------------------------------------------------------------------------
# Phase 1: Static AST-level checks
# ---------------------------------------------------------------------------

def _check_syntax_validity(source_code: str) -> Tuple[bool, Optional[str]]:
    """Check if the source code is syntactically valid Python."""
    try:
        ast.parse(source_code)
        return True, None
    except SyntaxError as e:
        return False, f"Syntax error: {e.msg} at line {e.lineno}, offset {e.offset}"


def _check_structural_integrity(tree: ast.AST) -> Tuple[bool, List[str]]:
    """Check for structural issues like missing required nodes, unbalanced structures."""
    issues = []
    # Ensure there is at least one statement
    if not isinstance(tree, ast.Module) or not tree.body:
        issues.append("Module body is empty")
    # Check for any obvious structural anomalies (e.g., break/continue outside loop)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Break, ast.Continue)):
            # Walk up to find enclosing loop
            for parent in ast.walk(tree):
                if isinstance(parent, (ast.For, ast.While)):
                    break
            else:
                issues.append(f"{type(node).__name__} outside loop at line {getattr(node, 'lineno', '?')}")
    return len(issues) == 0, issues


def _check_import_consistency(source_code: str, original_source: str) -> Tuple[bool, List[str]]:
    """Check that imports in the mutated code are consistent with the original."""
    issues = []
    try:
        mutated_tree = ast.parse(source_code)
        original_tree = ast.parse(original_source)
    except SyntaxError:
        issues.append("Cannot parse source for import consistency check")
        return False, issues

    def get_imports(tree: ast.AST) -> Set[str]:
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.add(alias.name)
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                for alias in node.names:
                    imports.add(f"{module}.{alias.name}" if module else alias.name)
        return imports

    original_imports = get_imports(original_tree)
    mutated_imports = get_imports(mutated_tree)

    # Mutations should not add new imports (unless they are stdlib or already present)
    new_imports = mutated_imports - original_imports
    if new_imports:
        issues.append(f"Mutation introduces new imports: {new_imports}")

    # Mutations should not remove imports that are still used
    removed_imports = original_imports - mutated_imports
    if removed_imports:
        # Check if any removed import is still referenced in the mutated code
        for imp in removed_imports:
            # Simple check: see if the import name appears in the source
            if imp.split(".")[0] in source_code:
                issues.append(f"Import '{imp}' removed but still referenced in code")

    return len(issues) == 0, issues


def validate_phase1(source_code: str, original_source: str) -> Dict[str, Any]:
    """Run Phase 1 validation: syntax, structure, import consistency."""
    details = []
    passed = True

    # Syntax validity
    syntax_ok, syntax_err = _check_syntax_validity(source_code)
    if not syntax_ok:
        passed = False
        details.append({"check": "syntax_validity", "passed": False, "message": syntax_err})
    else:
        details.append({"check": "syntax_validity", "passed": True, "message": "Syntax is valid"})

    # Structural integrity
    try:
        tree = ast.parse(source_code)
        struct_ok, struct_issues = _check_structural_integrity(tree)
        if not struct_ok:
            passed = False
            for issue in struct_issues:
                details.append({"check": "structural_integrity", "passed": False, "message": issue})
        else:
            details.append({"check": "structural_integrity", "passed": True, "message": "Structure is sound"})
    except SyntaxError:
        # Already reported above
        pass

    # Import consistency
    import_ok, import_issues = _check_import_consistency(source_code, original_source)
    if not import_ok:
        passed = False
        for issue in import_issues:
            details.append({"check": "import_consistency", "passed": False, "message": issue})
    else:
        details.append({"check": "import_consistency", "passed": True, "message": "Imports are consistent"})

    return {"passed": passed, "details": details}


# ---------------------------------------------------------------------------
# Phase 2: Dependency graph analysis with side effect simulation
# ---------------------------------------------------------------------------

def _get_critical_interfaces(dep_graph: Dict[str, Any]) -> Set[str]:
    """Extract critical interfaces from the dependency graph.

    Critical interfaces are functions, classes, or modules that are depended upon
    by other components.
    """
    critical = set()
    # dep_graph is expected to be a dict with module names as keys and
    # their dependencies as values (or a more complex structure)
    if not dep_graph:
        return critical

    # Collect all entities that are depended upon
    depended_upon = set()
    for module_name, deps in dep_graph.items():
        if isinstance(deps, dict):
            for dep_type, dep_list in deps.items():
                if dep_type in ("functions", "classes", "modules"):
                    for dep in dep_list:
                        depended_upon.add(dep)
        elif isinstance(deps, (list, set)):
            for dep in deps:
                depended_upon.add(dep)

    # Also consider the module itself if it's depended upon
    for module_name in dep_graph:
        depended_upon.add(module_name)

    return depended_upon


def _get_mutated_interfaces(source_code: str, module_name: str) -> Set[str]:
    """Extract interfaces (functions, classes) defined in the mutated source."""
    interfaces = set()
    try:
        tree = ast.parse(source_code)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                interfaces.add(f"{module_name}.{node.name}")
            elif isinstance(node, ast.AsyncFunctionDef):
                interfaces.add(f"{module_name}.{node.name}")
            elif isinstance(node, ast.ClassDef):
                interfaces.add(f"{module_name}.{node.name}")
    except SyntaxError:
        pass
    return interfaces


def validate_phase2(source_code: str, module_name: str, original_source: str) -> Dict[str, Any]:
    """Run Phase 2 validation: dependency graph analysis and side effect simulation.

    Checks if the mutation affects any critical interfaces and simulates side effects.
    """
    details = []
    passed = True
    side_effects = None

    if get_dependency_graph is None:
        details.append({"check": "dependency_graph", "passed": False,
                        "message": "self_model.builder.get_dependency_graph not available"})
        return {"passed": False, "details": details, "side_effects": None}

    try:
        dep_graph = get_dependency_graph()
        critical_interfaces = _get_critical_interfaces(dep_graph)

        mutated_interfaces = _get_mutated_interfaces(source_code, module_name)
        original_interfaces = _get_mutated_interfaces(original_source, module_name)

        # Check if any critical interface is modified or removed
        removed_interfaces = original_interfaces - mutated_interfaces
        affected_critical = removed_interfaces & critical_interfaces

        if affected_critical:
            passed = False
            details.append({"check": "critical_interfaces", "passed": False,
                            "message": f"Mutation removes/modifies critical interfaces: {affected_critical}"})
        else:
            details.append({"check": "critical_interfaces", "passed": True,
                            "message": "No critical interfaces affected"})

        # Check if any new interface is introduced that might conflict
        new_interfaces = mutated_interfaces - original_interfaces
        if new_interfaces:
            details.append({"check": "new_interfaces", "passed": True,
                            "message": f"New interfaces introduced: {new_interfaces}"})

        # Run side effect simulator after critical interface check
        if simulate_side_effects is not None:
            try:
                # Prepare the simulation context
                simulation_context = {
                    "source_code": source_code,
                    "original_source": original_source,
                    "module_name": module_name,
                    "dep_graph": dep_graph,
                    "critical_interfaces": critical_interfaces,
                    "mutated_interfaces": mutated_interfaces,
                    "original_interfaces": original_interfaces,
                    "affected_critical": affected_critical,
                    "new_interfaces": new_interfaces,
                }
                
                simulation_result = simulate_side_effects(simulation_context)
                
                if isinstance(simulation_result, dict):
                    side_effects = {
                        "affected_modules": simulation_result.get("affected_modules", []),
                        "risk_score": simulation_result.get("risk_score", 0),
                        "recommended_compensations": simulation_result.get("recommended_compensations", [])
                    }
                    
                    # If risk_score > 70, mark Phase 2 as failed with a warning
                    if side_effects["risk_score"] > 70:
                        passed = False
                        details.append({
                            "check": "side_effect_risk",
                            "passed": False,
                            "message": f"Side effect risk score {side_effects['risk_score']} exceeds threshold of 70. "
                                      f"Affected modules: {side_effects['affected_modules']}. "
                                      f"Recommended compensations: {side_effects['recommended_compensations']}"
                        })
                    else:
                        details.append({
                            "check": "side_effect_risk",
                            "passed": True,
                            "message": f"Side effect risk score {side_effects['risk_score']} is within acceptable range"
                        })
                else:
                    details.append({
                        "check": "side_effect_simulation",
                        "passed": False,
                        "message": "Side effect simulator returned invalid result format"
                    })
            except Exception as e:
                details.append({
                    "check": "side_effect_simulation",
                    "passed": False,
                    "message": f"Error running side effect simulator: {str(e)}"
                })
        else:
            details.append({
                "check": "side_effect_simulation",
                "passed": False,
                "message": "side_effect_simulator module not available"
            })

    except Exception as e:
        passed = False
        details.append({"check": "dependency_graph", "passed": False,
                        "message": f"Error analyzing dependency graph: {str(e)}"})

    return {"passed": passed, "details": details, "side_effects": side_effects}


# ---------------------------------------------------------------------------
# Phase 3: Sandboxed execution
# ---------------------------------------------------------------------------

def _create_sandboxed_module(source_code: str, module_name: str) -> Optional[Path]:
    """Create a temporary file with the mutated source code for sandboxed execution."""
    try:
        tmp_dir = tempfile.mkdtemp(prefix="mutation_sandbox_")
        # Create package structure if needed
        parts = module_name.split(".")
        if len(parts) > 1:
            pkg_dir = tmp_dir
            for part in parts[:-1]:
                pkg_dir = os.path.join(pkg_dir, part)
                os.makedirs(pkg_dir, exist_ok=True)
                init_file = os.path.join(pkg_dir, "__init__.py")
                if not os.path.exists(init_file):
                    Path(init_file).write_text("")
            module_path = os.path.join(pkg_dir, f"{parts[-1]}.py")
        else:
            module_path = os.path.join(tmp_dir, f"{module_name}.py")

        Path(module_path).write_text(source_code)
        return Path(tmp_dir)
    except Exception:
        return None


def _run_tests_in_sandbox(sandbox_path: Path, test_target: Optional[str] = None) -> Dict[str, Any]:
    """Run the test suite in the sandboxed environment.

    If run_tests from testing_framework is available, use it.
    Otherwise, attempt a basic test discovery and execution.
    """
    result = {"passed": False, "output": "", "errors": []}

    if run_tests is not None:
        try:
            # Use the testing_framework's run_tests function
            test_result = run_tests(sandbox_path, test_target)
            if isinstance(test_result, dict):
                result = test_result
            else:
                result["passed"] = test_result
                result["output"] = str(test_result)
        except Exception as e:
            result["errors"].append(f"Error running tests via testing_framework: {str(e)}")
        return result

    # Fallback: basic test discovery using unittest
    try:
        original_sys_path = sys.path.copy()
        sys.path.insert(0, str(sandbox_path))

        import unittest
        loader = unittest.TestLoader()
        suite = loader.discover(str(sandbox_path), pattern="test_*.py")
        runner = unittest.TextTestRunner(verbosity=0)
        test_result = runner.run(suite)

        result["passed"] = test_result.wasSuccessful()
        result["output"] = f"Tests run: {test_result.testsRun}, Failures: {len(test_result.failures)}, Errors: {len(test_result.errors)}"
        for failure in test_result.failures:
            result["errors"].append(f"FAIL: {failure[0]}\n{failure[1]}")
        for error in test_result.errors:
            result["errors"].append(f"ERROR: {error[0]}\n{error[1]}")

        sys.path = original_sys_path
    except Exception as e:
        result["errors"].append(f"Error during test execution: {str(e)}")
        sys.path = original_sys_path

    return result


def validate_phase3(source_code: str, module_name: str, test_target: Optional[str] = None) -> Dict[str, Any]:
    """Run Phase 3 validation: sandboxed execution with test suite."""
    details = []
    passed = False

    sandbox_path = _create_sandboxed_module(source_code, module_name)
    if sandbox_path is None:
        details.append({"check": "sandbox_creation", "passed": False,
                        "message": "Failed to create sandboxed module"})
        return {"passed": False, "details": details}

    try:
        test_result = _run_tests_in_sandbox(sandbox_path, test_target)
        passed = test_result.get("passed", False)
        output = test_result.get("output", "")
        errors = test_result.get("errors", [])

        details.append({"check": "sandbox_execution", "passed": passed,
                        "message": output if output else "No output"})
        for err in errors:
            details.append({"check": "test_error", "passed": False, "message": str(err)})
    except Exception as e:
        details.append({"check": "sandbox_execution", "passed": False,
                        "message": f"Exception during sandbox execution: {str(e)}"})
    finally:
        # Clean up sandbox
        import shutil
        try:
            shutil.rmtree(sandbox_path)
        except Exception:
            pass

    return {"passed": passed, "details": details}


# ---------------------------------------------------------------------------
# Main validation orchestrator
# ---------------------------------------------------------------------------

def validate_mutation(source_code: str,
                      original_source: str,
                      module_name: str,
                      test_target: Optional[str] = None,
                      run_phase1: bool = True,
                      run_phase2: bool = True,
                      run_phase3: bool = True) -> ValidationResult:
    """Run multi-phase validation on a mutation.

    Args:
        source_code: The mutated source code as a string.
        original_source: The original source code as a string.
        module_name: The fully qualified module name (e.g., 'my_package.my_module').
        test_target: Optional specific test target for Phase 3.
        run_phase1: Whether to run Phase 1 checks.
        run_phase2: Whether to run Phase 2 checks.
        run_phase3: Whether to run Phase 3 checks.

    Returns:
        A ValidationResult object with per-phase results.
    """
    result = ValidationResult()

    if run_phase1:
        result.phase1 = validate_phase1(source_code, original_source)

    if run_phase2:
        result.phase2 = validate_phase2(source_code, module_name, original_source)

    if run_phase3:
        result.phase3 = validate_phase3(source_code, module_name, test_target)

    # Overall pass if all executed phases passed
    phases = []
    if run_phase1:
        phases.append(result.phase1["passed"])
    if run_phase2:
        phases.append(result.phase2["passed"])
    if run_phase3:
        phases.append(result.phase3["passed"])

    result.overall_passed = all(phases) if phases else False

    return result