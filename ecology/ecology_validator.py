"""Ecology system validator: checks module imports, pressure validity, test coverage preservation, and pressure novelty."""

import importlib
import sys
import traceback
from typing import Any, Dict, List, Optional, Set, Tuple, Type


# ---------------------------------------------------------------------------
# 1. Module import validation
# ---------------------------------------------------------------------------

ECOLOGY_MODULES = [
    "ecology.ecology_validator",
    # Add other ecology modules here as they are created:
    # "ecology.ecology_pressure_engine",
    # "ecology.ecology_integrator",
    # "ecology.ecology_goal_generator",
]


def validate_module_imports(
    modules: Optional[List[str]] = None,
) -> Dict[str, Dict[str, Any]]:
    """Check that all ecology modules import correctly.

    Returns a dict mapping module names to import results:
        {"module_name": {"success": bool, "error": str or None, "module": module or None}}
    """
    if modules is None:
        modules = ECOLOGY_MODULES

    results: Dict[str, Dict[str, Any]] = {}
    for mod_name in modules:
        try:
            mod = importlib.import_module(mod_name)
            results[mod_name] = {
                "success": True,
                "error": None,
                "module": mod,
            }
        except Exception as exc:
            tb = traceback.format_exc()
            results[mod_name] = {
                "success": False,
                "error": f"{type(exc).__name__}: {exc}\n{tb}",
                "module": None,
            }
    return results


def report_import_errors(results: Dict[str, Dict[str, Any]]) -> List[str]:
    """Return a list of error messages for modules that failed to import."""
    errors = []
    for mod_name, info in results.items():
        if not info["success"]:
            errors.append(f"Module '{mod_name}' failed to import:\n{info['error']}")
    return errors


# ---------------------------------------------------------------------------
# 2. Pressure validity checking
# ---------------------------------------------------------------------------

# Expected keys for a valid pressure dictionary
PRESSURE_REQUIRED_KEYS: Set[str] = {"name", "description", "severity"}
PRESSURE_OPTIONAL_KEYS: Set[str] = {"category", "tags", "metadata"}

# Valid severity levels
VALID_SEVERITIES: Set[str] = {"low", "medium", "high", "critical"}


def validate_pressure(pressure: Any) -> Tuple[bool, Optional[str]]:
    """Check that a single pressure object is valid.

    Returns (is_valid, error_message).
    """
    if not isinstance(pressure, dict):
        return False, f"Pressure must be a dict, got {type(pressure).__name__}"

    # Check required keys
    missing = PRESSURE_REQUIRED_KEYS - set(pressure.keys())
    if missing:
        return False, f"Missing required keys: {', '.join(sorted(missing))}"

    # Check name is a non-empty string
    name = pressure.get("name")
    if not isinstance(name, str) or not name.strip():
        return False, f"Pressure 'name' must be a non-empty string, got {name!r}"

    # Check description is a non-empty string
    desc = pressure.get("description")
    if not isinstance(desc, str) or not desc.strip():
        return False, f"Pressure 'description' must be a non-empty string, got {desc!r}"

    # Check severity is valid
    severity = pressure.get("severity")
    if severity not in VALID_SEVERITIES:
        return False, (
            f"Pressure 'severity' must be one of {sorted(VALID_SEVERITIES)}, "
            f"got {severity!r}"
        )

    # Check optional keys are valid types if present
    for key in PRESSURE_OPTIONAL_KEYS:
        if key in pressure:
            val = pressure[key]
            if key == "category" and not isinstance(val, str):
                return False, f"Optional key '{key}' must be a string, got {type(val).__name__}"
            if key == "tags" and not isinstance(val, (list, set)):
                return False, f"Optional key '{key}' must be a list or set, got {type(val).__name__}"
            if key == "metadata" and not isinstance(val, dict):
                return False, f"Optional key '{key}' must be a dict, got {type(val).__name__}"

    return True, None


def validate_pressures(pressures: List[Any]) -> Dict[str, Any]:
    """Validate a list of pressures.

    Returns a dict with:
        - valid: list of valid pressures
        - invalid: list of (pressure, error_message) tuples
        - all_valid: bool
    """
    valid: List[Dict] = []
    invalid: List[Tuple[Any, str]] = []

    for p in pressures:
        is_valid, error = validate_pressure(p)
        if is_valid:
            valid.append(p)
        else:
            invalid.append((p, error))

    return {
        "valid": valid,
        "invalid": invalid,
        "all_valid": len(invalid) == 0,
    }


# ---------------------------------------------------------------------------
# 3. Test coverage preservation check
# ---------------------------------------------------------------------------


def check_test_coverage_preserved(
    original_tests: Dict[str, Set[str]],
    mutated_tests: Dict[str, Set[str]],
) -> Dict[str, Any]:
    """Check that test suite mutations preserve existing test coverage.

    Args:
        original_tests: Mapping of test file -> set of test function names.
        mutated_tests: Mapping of test file -> set of test function names after mutation.

    Returns:
        Dict with:
            - preserved: bool (True if all original tests still exist)
            - missing: dict of file -> set of missing test names
            - added: dict of file -> set of new test names
            - details: str summary
    """
    missing: Dict[str, Set[str]] = {}
    added: Dict[str, Set[str]] = {}

    all_files = set(original_tests.keys()) | set(mutated_tests.keys())

    for file in all_files:
        orig = original_tests.get(file, set())
        mut = mutated_tests.get(file, set())

        file_missing = orig - mut
        file_added = mut - orig

        if file_missing:
            missing[file] = file_missing
        if file_added:
            added[file] = file_added

    preserved = len(missing) == 0

    # Build summary
    parts = []
    if preserved:
        parts.append("All original tests are preserved.")
    else:
        for file, tests in missing.items():
            parts.append(f"Missing from {file}: {', '.join(sorted(tests))}")

    if added:
        for file, tests in added.items():
            parts.append(f"Added to {file}: {', '.join(sorted(tests))}")

    return {
        "preserved": preserved,
        "missing": missing,
        "added": added,
        "details": " | ".join(parts),
    }


# ---------------------------------------------------------------------------
# 4. Pressure novelty (duplicate detection)
# ---------------------------------------------------------------------------


def check_pressure_novelty(
    new_pressures: List[Dict],
    existing_pressures: List[Dict],
    *,
    name_key: str = "name",
    description_key: str = "description",
    similarity_threshold: float = 0.8,
) -> Dict[str, Any]:
    """Check that new pressures are novel (not duplicates of existing ones).

    A pressure is considered a duplicate if:
        - It has the same name (case-insensitive) as an existing pressure.
        - OR it has a very similar description (simple overlap check).

    Args:
        new_pressures: List of new pressure dicts to check.
        existing_pressures: List of existing pressure dicts.
        name_key: Key for the pressure name in dicts.
        description_key: Key for the pressure description in dicts.
        similarity_threshold: Fraction of words that must overlap to consider
            descriptions similar (0.0 to 1.0).

    Returns:
        Dict with:
            - novel: list of pressures that are novel
            - duplicates: list of (new_pressure, matched_existing_pressure, reason) tuples
            - all_novel: bool
    """
    novel: List[Dict] = []
    duplicates: List[Tuple[Dict, Dict, str]] = []

    # Build lookup structures for existing pressures
    existing_names_lower: Dict[str, Dict] = {}
    existing_descriptions: List[Tuple[Set[str], Dict]] = []

    for ep in existing_pressures:
        name = ep.get(name_key, "")
        existing_names_lower[name.lower()] = ep

        desc = ep.get(description_key, "")
        words = set(desc.lower().split())
        existing_descriptions.append((words, ep))

    for np_ in new_pressures:
        new_name = np_.get(name_key, "")
        new_desc = np_.get(description_key, "")
        new_words = set(new_desc.lower().split())

        is_duplicate = False

        # Check name match
        if new_name.lower() in existing_names_lower:
            matched = existing_names_lower[new_name.lower()]
            duplicates.append((np_, matched, f"Duplicate name: '{new_name}'"))
            is_duplicate = True
            continue

        # Check description similarity
        for existing_words, ep in existing_descriptions:
            if not new_words or not existing_words:
                continue
            intersection = new_words & existing_words
            union = new_words | existing_words
            if len(union) == 0:
                continue
            overlap = len(intersection) / len(union)
            if overlap >= similarity_threshold:
                duplicates.append(
                    (
                        np_,
                        ep,
                        f"Description overlap {overlap:.2f} >= threshold {similarity_threshold}",
                    )
                )
                is_duplicate = True
                break

        if not is_duplicate:
            novel.append(np_)

    return {
        "novel": novel,
        "duplicates": duplicates,
        "all_novel": len(duplicates) == 0,
    }


# ---------------------------------------------------------------------------
# 5. Convenience runner
# ---------------------------------------------------------------------------


def run_full_validation(
    pressures: Optional[List[Dict]] = None,
    original_tests: Optional[Dict[str, Set[str]]] = None,
    mutated_tests: Optional[Dict[str, Set[str]]] = None,
    new_pressures: Optional[List[Dict]] = None,
    existing_pressures: Optional[List[Dict]] = None,
) -> Dict[str, Any]:
    """Run all validation checks and return a combined report.

    Each check is optional; pass None to skip that check.
    """
    report: Dict[str, Any] = {}

    # 1. Module imports
    import_results = validate_module_imports()
    import_errors = report_import_errors(import_results)
    report["module_imports"] = {
        "all_success": len(import_errors) == 0,
        "results": import_results,
        "errors": import_errors,
    }

    # 2. Pressure validity
    if pressures is not None:
        pressure_results = validate_pressures(pressures)
        report["pressure_validity"] = pressure_results
    else:
        report["pressure_validity"] = None

    # 3. Test coverage preservation
    if original_tests is not None and mutated_tests is not None:
        coverage_results = check_test_coverage_preserved(original_tests, mutated_tests)
        report["test_coverage"] = coverage_results
    else:
        report["test_coverage"] = None

    # 4. Pressure novelty
    if new_pressures is not None and existing_pressures is not None:
        novelty_results = check_pressure_novelty(new_pressures, existing_pressures)
        report["pressure_novelty"] = novelty_results
    else:
        report["pressure_novelty"] = None

    # Overall success
    all_ok = True
    for key, value in report.items():
        if value is None:
            continue
        if isinstance(value, dict):
            if "all_success" in value and not value["all_success"]:
                all_ok = False
            elif "all_valid" in value and not value["all_valid"]:
                all_ok = False
            elif "preserved" in value and not value["preserved"]:
                all_ok = False
            elif "all_novel" in value and not value["all_novel"]:
                all_ok = False

    report["overall_success"] = all_ok
    return report