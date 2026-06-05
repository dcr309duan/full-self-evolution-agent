import os
import sys
import importlib
import inspect
import json
import shutil
from datetime import datetime
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

# Configuration
ARCHIVE_DIR = "archive"
FAILURE_THRESHOLD = 3
FAILURE_COUNTER_FILE = ".module_failure_counters.json"
REPORT_LOG_FILE = "pruning_report.log"

# Global failure counter dictionary
failure_counters: Dict[str, int] = {}

def load_failure_counters() -> Dict[str, int]:
    """Load persistent failure counters from file."""
    global failure_counters
    if os.path.exists(FAILURE_COUNTER_FILE):
        try:
            with open(FAILURE_COUNTER_FILE, "r") as f:
                failure_counters = json.load(f)
        except (json.JSONDecodeError, IOError):
            failure_counters = {}
    else:
        failure_counters = {}
    return failure_counters

def save_failure_counters() -> None:
    """Save failure counters to persistent file."""
    with open(FAILURE_COUNTER_FILE, "w") as f:
        json.dump(failure_counters, f, indent=2)

def scan_all_modules(base_path: str = ".") -> List[str]:
    """
    Walk the codebase and identify all Python modules (excluding __pycache__ and hidden dirs).
    Returns a list of module file paths relative to base_path.
    """
    modules = []
    base = Path(base_path).resolve()
    for root, dirs, files in os.walk(base):
        # Skip hidden directories and __pycache__
        dirs[:] = [d for d in dirs if not d.startswith('.') and d != '__pycache__']
        for file in files:
            if file.endswith(".py") and file != "__init__.py":
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, base)
                modules.append(rel_path)
    return sorted(modules)

def classify_module(module_path: str, base_path: str = ".") -> Dict:
    """
    Run execution tests on a module and check dependency overlap.
    Returns a dict with keys: 'module', 'import_success', 'function_call_success', 'dependencies', 'overlap_score'.
    """
    result = {
        'module': module_path,
        'import_success': False,
        'function_call_success': False,
        'dependencies': [],
        'overlap_score': 0.0
    }

    # Convert file path to module name
    module_name = module_path.replace(os.sep, '.')[:-3]  # remove .py
    full_path = os.path.join(base_path, module_path)
    if not os.path.exists(full_path):
        return result

    # Attempt import
    try:
        spec = importlib.util.spec_from_file_location(module_name, full_path)
        if spec is None or spec.loader is None:
            return result
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        result['import_success'] = True
    except Exception as e:
        # Import failed
        return result

    # Get dependencies (imports) from the module
    try:
        if hasattr(mod, '__file__') and mod.__file__:
            with open(mod.__file__, 'r') as f:
                source = f.read()
            import ast
            tree = ast.parse(source)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        result['dependencies'].append(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        result['dependencies'].append(node.module)
    except Exception:
        pass

    # Attempt to call a basic function (if any exist)
    functions = [obj for name, obj in inspect.getmembers(mod, inspect.isfunction)
                 if not name.startswith('_')]
    if functions:
        try:
            # Try calling the first public function with no arguments
            func = functions[0]
            sig = inspect.signature(func)
            # Only call if it takes no required arguments
            required_params = [p for p in sig.parameters.values()
                               if p.default is inspect.Parameter.empty and p.kind in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)]
            if not required_params:
                func()
                result['function_call_success'] = True
        except Exception:
            pass

    # Calculate overlap score (simplified: based on number of dependencies)
    # In a more advanced version, you'd compare with other modules' dependencies
    result['overlap_score'] = len(result['dependencies']) * 0.1  # placeholder

    return result

def track_failures(module_path: str, success: bool) -> int:
    """
    Update and return the consecutive failure count for a module.
    Returns the current count after update.
    """
    load_failure_counters()
    if success:
        failure_counters[module_path] = 0
    else:
        failure_counters[module_path] = failure_counters.get(module_path, 0) + 1
    save_failure_counters()
    return failure_counters[module_path]

def prune_module(module_path: str, base_path: str = ".") -> bool:
    """
    Move a broken/redundant module to the archive directory.
    Returns True if successful, False otherwise.
    """
    src = os.path.join(base_path, module_path)
    if not os.path.exists(src):
        return False

    archive_path = os.path.join(base_path, ARCHIVE_DIR)
    os.makedirs(archive_path, exist_ok=True)

    # Create subdirectory structure in archive
    dest_dir = os.path.join(archive_path, os.path.dirname(module_path))
    os.makedirs(dest_dir, exist_ok=True)
    dest = os.path.join(archive_path, module_path)

    try:
        shutil.move(src, dest)
        # Remove the counter entry if exists
        load_failure_counters()
        if module_path in failure_counters:
            del failure_counters[module_path]
            save_failure_counters()
        return True
    except Exception:
        return False

def generate_report(pruned_modules: List[str], failed_modules: List[Tuple[str, int]], timestamp: Optional[str] = None) -> None:
    """
    Output a pruning report log.
    """
    if timestamp is None:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    report_lines = [
        f"=== Pruning Report - {timestamp} ===",
        f"Total modules pruned: {len(pruned_modules)}",
        f"Modules with failures (count):",
    ]
    for mod, count in failed_modules:
        report_lines.append(f"  - {mod}: {count} consecutive failures")

    if pruned_modules:
        report_lines.append("Pruned modules:")
        for mod in pruned_modules:
            report_lines.append(f"  - {mod}")
    else:
        report_lines.append("No modules pruned.")

    report_lines.append("=" * 40)

    report = "\n".join(report_lines)
    print(report)

    # Append to log file
    with open(REPORT_LOG_FILE, "a") as f:
        f.write(report + "\n\n")

def run_triage(base_path: str = ".") -> None:
    """
    Main triage function: scan, classify, track failures, prune if needed, and generate report.
    """
    load_failure_counters()
    modules = scan_all_modules(base_path)
    pruned_modules = []
    failed_modules = []

    for mod_path in modules:
        classification = classify_module(mod_path, base_path)
        success = classification['import_success'] and classification['function_call_success']
        count = track_failures(mod_path, success)

        if not success:
            failed_modules.append((mod_path, count))
            if count >= FAILURE_THRESHOLD:
                if prune_module(mod_path, base_path):
                    pruned_modules.append(mod_path)
                    print(f"Pruned module: {mod_path} (after {count} consecutive failures)")
                else:
                    print(f"Failed to prune module: {mod_path}")

    generate_report(pruned_modules, failed_modules)

if __name__ == "__main__":
    run_triage()