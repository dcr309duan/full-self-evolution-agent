"""Helper functions for the self-consistency test suite.

These functions provide utilities for verifying consistency between
mutation definitions, code state, reflection parser assessments, and goals.
"""

import hashlib
import os
import ast
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any


# Default module paths to check (relative to project root)
DEFAULT_MODULE_PATHS = [
    "src/core",
    "src/utils",
    "src/reflection",
    "src/mutations",
    "src/goals",
]


def get_current_code_state(module_paths: Optional[List[str]] = None) -> Dict[str, Any]:
    """Read all relevant module files and compute checksums.

    Args:
        module_paths: List of directory paths to scan. If None, uses defaults.

    Returns:
        Dictionary mapping file paths to their checksums and metadata.
        Structure: {
            "files": {
                "relative/path.py": {
                    "checksum": "sha256hex",
                    "size": 1234,
                    "last_modified": "timestamp",
                    "lines": 50,
                }
            },
            "overall_checksum": "sha256hex",
        }
    """
    if module_paths is None:
        module_paths = DEFAULT_MODULE_PATHS

    project_root = Path.cwd()
    files_info = {}
    all_checksums = []

    for module_path in module_paths:
        full_path = project_root / module_path
        if not full_path.exists():
            continue

        if full_path.is_file() and full_path.suffix == ".py":
            _process_file(full_path, project_root, files_info, all_checksums)
        elif full_path.is_dir():
            for py_file in full_path.rglob("*.py"):
                _process_file(py_file, project_root, files_info, all_checksums)

    # Compute overall checksum from all file checksums
    combined = "".join(sorted(all_checksums))
    overall_checksum = hashlib.sha256(combined.encode()).hexdigest()

    return {
        "files": files_info,
        "overall_checksum": overall_checksum,
    }


def _process_file(
    file_path: Path,
    project_root: Path,
    files_info: Dict[str, Any],
    all_checksums: List[str],
) -> None:
    """Process a single Python file and add its info to the dictionaries."""
    try:
        content = file_path.read_bytes()
        checksum = hashlib.sha256(content).hexdigest()
        relative_path = str(file_path.relative_to(project_root))
        lines = content.decode("utf-8").count("\n")

        files_info[relative_path] = {
            "checksum": checksum,
            "size": len(content),
            "last_modified": str(file_path.stat().st_mtime),
            "lines": lines,
        }
        all_checksums.append(checksum)
    except (OSError, UnicodeDecodeError):
        # Skip files that can't be read
        pass


def compare_mutation_to_state(
    mutation_output: Dict[str, Any],
    actual_state: Dict[str, Any],
) -> Dict[str, Any]:
    """Verify that the mutation's expected output matches actual file changes.

    Args:
        mutation_output: Dictionary describing expected mutation results.
            Expected format: {
                "modified_files": {
                    "relative/path.py": {
                        "expected_checksum": "sha256hex",
                        "expected_lines_added": 5,
                        "expected_lines_removed": 2,
                    }
                },
                "new_files": {
                    "relative/new_file.py": {
                        "expected_checksum": "sha256hex",
                        "expected_lines": 30,
                    }
                },
                "deleted_files": ["relative/old_file.py"],
            }
        actual_state: Current code state from get_current_code_state().

    Returns:
        Dictionary with comparison results:
        {
            "matches": bool,
            "differences": {
                "modified_files": {
                    "relative/path.py": {
                        "checksum_match": True/False,
                        "lines_match": True/False,
                        "actual_checksum": "...",
                        "actual_lines": 50,
                    }
                },
                "new_files": { ... },
                "deleted_files": {
                    "still_exist": ["relative/old_file.py"],
                },
                "unexpected_changes": ["relative/unexpected.py"],
            }
        }
    """
    differences = {
        "modified_files": {},
        "new_files": {},
        "deleted_files": {"still_exist": []},
        "unexpected_changes": [],
    }

    # Check modified files
    for file_path, expected in mutation_output.get("modified_files", {}).items():
        actual_file = actual_state["files"].get(file_path)
        if actual_file is None:
            differences["modified_files"][file_path] = {
                "checksum_match": False,
                "lines_match": False,
                "actual_checksum": None,
                "actual_lines": None,
                "error": "File not found in actual state",
            }
            continue

        checksum_match = actual_file["checksum"] == expected.get("expected_checksum")
        lines_match = actual_file["lines"] == (
            actual_state["files"].get(file_path, {}).get("lines", 0)
        )
        differences["modified_files"][file_path] = {
            "checksum_match": checksum_match,
            "lines_match": lines_match,
            "actual_checksum": actual_file["checksum"],
            "actual_lines": actual_file["lines"],
        }

    # Check new files
    for file_path, expected in mutation_output.get("new_files", {}).items():
        actual_file = actual_state["files"].get(file_path)
        if actual_file is None:
            differences["new_files"][file_path] = {
                "exists": False,
                "checksum_match": False,
                "lines_match": False,
                "error": "File not found",
            }
        else:
            checksum_match = actual_file["checksum"] == expected.get("expected_checksum")
            lines_match = actual_file["lines"] == expected.get("expected_lines")
            differences["new_files"][file_path] = {
                "exists": True,
                "checksum_match": checksum_match,
                "lines_match": lines_match,
                "actual_checksum": actual_file["checksum"],
                "actual_lines": actual_file["lines"],
            }

    # Check deleted files
    for file_path in mutation_output.get("deleted_files", []):
        if file_path in actual_state["files"]:
            differences["deleted_files"]["still_exist"].append(file_path)

    # Check for unexpected changes (files in actual state not in mutation output)
    expected_files = set(mutation_output.get("modified_files", {}).keys())
    expected_files.update(mutation_output.get("new_files", {}).keys())
    # Deleted files should not be in actual state
    for file_path in actual_state["files"]:
        if file_path not in expected_files:
            differences["unexpected_changes"].append(file_path)

    matches = (
        not any(
            diff.get("checksum_match") is False or diff.get("lines_match") is False
            for diff in differences["modified_files"].values()
        )
        and not any(
            diff.get("exists") is False or diff.get("checksum_match") is False
            for diff in differences["new_files"].values()
        )
        and not differences["deleted_files"]["still_exist"]
        and not differences["unexpected_changes"]
    )

    return {
        "matches": matches,
        "differences": differences,
    }


def validate_reflection_accuracy(
    reflection_assessment: Dict[str, Any],
    actual_code_state: Dict[str, Any],
) -> Dict[str, Any]:
    """Check reflection parser's assessment against actual code structure.

    Args:
        reflection_assessment: Dictionary from reflection parser describing code.
            Expected format: {
                "files": {
                    "relative/path.py": {
                        "classes": ["ClassName"],
                        "functions": ["func_name"],
                        "imports": ["module"],
                        "lines_of_code": 50,
                    }
                },
                "overall": {
                    "total_classes": 5,
                    "total_functions": 20,
                    "total_lines": 1000,
                }
            }
        actual_code_state: Current code state from get_current_code_state().

    Returns:
        Dictionary with validation results:
        {
            "accurate": bool,
            "file_errors": {
                "relative/path.py": {
                    "missing_classes": ["ClassName"],
                    "extra_classes": ["ClassName"],
                    "missing_functions": ["func_name"],
                    "extra_functions": ["func_name"],
                    "line_count_mismatch": True/False,
                    "actual_lines": 50,
                    "assessed_lines": 45,
                }
            },
            "overall_errors": {
                "class_count_mismatch": True/False,
                "function_count_mismatch": True/False,
                "line_count_mismatch": True/False,
            }
        }
    """
    file_errors = {}
    overall_errors = {
        "class_count_mismatch": False,
        "function_count_mismatch": False,
        "line_count_mismatch": False,
    }

    # Track actual totals
    actual_total_classes = 0
    actual_total_functions = 0
    actual_total_lines = 0

    for file_path, assessed_info in reflection_assessment.get("files", {}).items():
        actual_file = actual_code_state["files"].get(file_path)
        if actual_file is None:
            file_errors[file_path] = {
                "error": "File not found in actual state",
                "missing_classes": assessed_info.get("classes", []),
                "missing_functions": assessed_info.get("functions", []),
            }
            continue

        # Parse actual file to extract classes, functions, imports
        try:
            actual_file_path = Path.cwd() / file_path
            with open(actual_file_path, "r") as f:
                tree = ast.parse(f.read())
        except (OSError, SyntaxError):
            file_errors[file_path] = {
                "error": "Could not parse actual file",
            }
            continue

        actual_classes = [
            node.name
            for node in ast.walk(tree)
            if isinstance(node, ast.ClassDef)
        ]
        actual_functions = [
            node.name
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]
        actual_imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                actual_imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    actual_imports.append(node.module)

        actual_lines = actual_file.get("lines", 0)

        # Compare
        assessed_classes = set(assessed_info.get("classes", []))
        assessed_functions = set(assessed_info.get("functions", []))
        actual_classes_set = set(actual_classes)
        actual_functions_set = set(actual_functions)

        missing_classes = assessed_classes - actual_classes_set
        extra_classes = actual_classes_set - assessed_classes
        missing_functions = assessed_functions - actual_functions_set
        extra_functions = actual_functions_set - assessed_functions

        line_count_mismatch = actual_lines != assessed_info.get("lines_of_code", 0)

        if missing_classes or extra_classes or missing_functions or extra_functions or line_count_mismatch:
            file_errors[file_path] = {
                "missing_classes": list(missing_classes),
                "extra_classes": list(extra_classes),
                "missing_functions": list(missing_functions),
                "extra_functions": list(extra_functions),
                "line_count_mismatch": line_count_mismatch,
                "actual_lines": actual_lines,
                "assessed_lines": assessed_info.get("lines_of_code", 0),
            }

        actual_total_classes += len(actual_classes)
        actual_total_functions += len(actual_functions)
        actual_total_lines += actual_lines

    # Check overall counts
    assessed_overall = reflection_assessment.get("overall", {})
    if assessed_overall.get("total_classes") != actual_total_classes:
        overall_errors["class_count_mismatch"] = True
    if assessed_overall.get("total_functions") != actual_total_functions:
        overall_errors["function_count_mismatch"] = True
    if assessed_overall.get("total_lines") != actual_total_lines:
        overall_errors["line_count_mismatch"] = True

    accurate = not file_errors and not any(overall_errors.values())

    return {
        "accurate": accurate,
        "file_errors": file_errors,
        "overall_errors": overall_errors,
    }


def check_goal_feasibility(
    goals: List[Dict[str, Any]],
    available_capabilities: Dict[str, Any],
) -> Dict[str, Any]:
    """Verify that goals reference existing capabilities.

    Args:
        goals: List of goal dictionaries. Each goal should have:
            - "name": str
            - "required_capabilities": list of str
            - "description": str (optional)
        available_capabilities: Dictionary mapping capability names to their details.
            Format: {
                "capability_name": {
                    "type": "function|class|module",
                    "location": "module.path",
                    "description": "...",
                }
            }

    Returns:
        Dictionary with feasibility results:
        {
            "all_feasible": bool,
            "goal_results": {
                "goal_name": {
                    "feasible": True/False,
                    "missing_capabilities": ["cap1", "cap2"],
                    "available_capabilities": ["cap3"],
                }
            },
            "unused_capabilities": ["cap4"],
        }
    """
    goal_results = {}
    all_capabilities = set(available_capabilities.keys())
    used_capabilities = set()

    for goal in goals:
        goal_name = goal.get("name", "unnamed_goal")
        required = set(goal.get("required_capabilities", []))
        missing = required - all_capabilities
        available = required & all_capabilities
        used_capabilities.update(available)

        goal_results[goal_name] = {
            "feasible": len(missing) == 0,
            "missing_capabilities": list(missing),
            "available_capabilities": list(available),
        }

    unused_capabilities = list(all_capabilities - used_capabilities)
    all_feasible = all(result["feasible"] for result in goal_results.values())

    return {
        "all_feasible": all_feasible,
        "goal_results": goal_results,
        "unused_capabilities": unused_capabilities,
    }