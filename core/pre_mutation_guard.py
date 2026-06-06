import ast
import sys
import os
import json
from pathlib import Path
from typing import List, Dict, Optional, Tuple

# Ensure logs directory exists
LOGS_DIR = Path("logs")
LOGS_DIR.mkdir(exist_ok=True)
FAILURE_LOG_PATH = LOGS_DIR / "failure_log.jsonl"


def _create_error_record(
    error_type: str,
    file: str,
    line: int,
    message: str,
) -> Dict[str, object]:
    """Create a structured error record dictionary."""
    return {
        "error_type": error_type,
        "file": file,
        "line": line,
        "message": message,
    }


def _append_failure_log(record: Dict[str, object]) -> None:
    """Append a single JSON record to the failure log file."""
    try:
        with open(FAILURE_LOG_PATH, "a") as f:
            f.write(json.dumps(record) + "\n")
    except OSError as e:
        # If we cannot write to the log, print a warning (do not crash)
        print(f"Warning: Could not write to failure log: {e}", file=sys.stderr)


def validate_syntax(code: str, filename: str = "<unknown>") -> List[Dict[str, object]]:
    """
    Validate Python syntax using ast.parse().
    Returns a list of error records. If the list is empty, syntax is valid.
    """
    errors: List[Dict[str, object]] = []
    try:
        ast.parse(code, filename=filename)
    except SyntaxError as e:
        line_no = e.lineno if e.lineno is not None else 0
        error_type = type(e).__name__
        msg = e.msg if e.msg else str(e)
        record = _create_error_record(
            error_type=error_type,
            file=filename,
            line=line_no,
            message=msg,
        )
        errors.append(record)
        _append_failure_log(record)
    return errors


def resolve_import_path(import_name: str, base_path: Optional[str] = None) -> Optional[str]:
    """
    Resolve a single import name against the filesystem.
    Returns the resolved file path if found, None otherwise.
    Checks standard library paths and the provided base_path (or current directory).
    """
    # Check if it's a built-in / standard library module (quick check via sys.modules)
    if import_name in sys.builtin_module_names:
        return import_name

    # Check if already imported (module is available)
    if import_name in sys.modules:
        return import_name

    # Attempt to find the module using the filesystem
    search_paths = sys.path[:]
    if base_path:
        # Add the base path to the search list (if not already present)
        base_abs = os.path.abspath(base_path)
        if base_abs not in search_paths:
            search_paths.insert(0, base_abs)

    # Convert import name to file path candidates
    # e.g., 'os.path' -> 'os/path.py' or 'os/path/__init__.py'
    parts = import_name.split(".")
    for sp in search_paths:
        # Try as a single file
        file_candidate = os.path.join(sp, *parts) + ".py"
        if os.path.isfile(file_candidate):
            return file_candidate
        # Try as a package (directory with __init__.py)
        dir_candidate = os.path.join(sp, *parts)
        init_candidate = os.path.join(dir_candidate, "__init__.py")
        if os.path.isdir(dir_candidate) and os.path.isfile(init_candidate):
            return init_candidate
    return None


def validate_imports(
    code: str,
    filename: str = "<unknown>",
    base_path: Optional[str] = None,
) -> List[Dict[str, object]]:
    """
    Parse the code and validate all import statements.
    Returns a list of error records for unresolved imports.
    """
    errors: List[Dict[str, object]] = []
    try:
        tree = ast.parse(code, filename=filename)
    except SyntaxError:
        # If syntax is invalid, we cannot reliably check imports; skip.
        return errors

    for node in ast.walk(tree):
        # Handle 'import X' and 'import X.Y'
        if isinstance(node, ast.Import):
            for alias in node.names:
                import_name = alias.name
                resolved = resolve_import_path(import_name, base_path)
                if resolved is None:
                    record = _create_error_record(
                        error_type="ImportError",
                        file=filename,
                        line=node.lineno,
                        message=f"Cannot resolve import '{import_name}'",
                    )
                    errors.append(record)
                    _append_failure_log(record)
        # Handle 'from X import Y'
        elif isinstance(node, ast.ImportFrom):
            if node.module is None:
                # Relative import (e.g., 'from . import something')
                # We skip relative imports for simplicity; they are harder to resolve.
                continue
            import_name = node.module
            resolved = resolve_import_path(import_name, base_path)
            if resolved is None:
                record = _create_error_record(
                    error_type="ImportError",
                    file=filename,
                    line=node.lineno,
                    message=f"Cannot resolve import '{import_name}'",
                )
                errors.append(record)
                _append_failure_log(record)
    return errors


def check_module_availability(
    module_names: List[str],
    filename: str = "<unknown>",
    line: int = 0,
) -> List[Dict[str, object]]:
    """
    Verify that a list of module names can be imported (e.g., numpy, random).
    Returns a list of error records for modules that cannot be imported.
    """
    errors: List[Dict[str, object]] = []
    for mod_name in module_names:
        try:
            __import__(mod_name)
        except ImportError as e:
            record = _create_error_record(
                error_type="ModuleNotFoundError",
                file=filename,
                line=line,
                message=f"Module '{mod_name}' is not available: {e}",
            )
            errors.append(record)
            _append_failure_log(record)
    return errors


def pre_mutation_guard(
    code: str,
    filename: str = "<unknown>",
    base_path: Optional[str] = None,
    required_modules: Optional[List[str]] = None,
) -> Tuple[bool, List[Dict[str, object]]]:
    """
    Main entry point for pre-mutation validation guard.
    Performs:
      1. Syntax validation via ast.parse()
      2. Import path resolution
      3. Module availability verification (if required_modules provided)

    Returns:
        (is_valid: bool, errors: List[Dict[str, object]])
    """
    all_errors: List[Dict[str, object]] = []

    # Step 1: Syntax validation
    syntax_errors = validate_syntax(code, filename)
    all_errors.extend(syntax_errors)

    # If syntax is invalid, we cannot proceed with import checks (they may be misleading)
    if not syntax_errors:
        # Step 2: Import path resolution
        import_errors = validate_imports(code, filename, base_path)
        all_errors.extend(import_errors)

        # Step 3: Module availability verification
        if required_modules:
            module_errors = check_module_availability(required_modules, filename)
            all_errors.extend(module_errors)

    is_valid = len(all_errors) == 0
    return is_valid, all_errors