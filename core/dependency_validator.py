"""Pre-import validation script that checks all module imports before execution.
Prevents 'failed import' errors by validating dependencies upfront.
Runs before any nash-related code executes."""

import importlib
import sys
import logging
import ast
import os
from typing import List, Tuple, Set, Optional, Dict
from importlib.metadata import distribution, PackageNotFoundError

logger = logging.getLogger(__name__)

# Core modules that must be importable for the system to function
CORE_DEPENDENCIES = [
    "core.nash_detector_and_forcer",
    "core.nash_integration_hook",
    "core.coordinated_mutation_engine",
    "core.evolution_orchestrator",
    "core.import_validator",
]

# Optional dependencies that enhance functionality but aren't critical
OPTIONAL_DEPENDENCIES = [
    "core.mutation_analyzer",
    "core.pattern_detector",
    "core.performance_tracker",
]

# Third-party dependencies
THIRD_PARTY_DEPENDENCIES = [
    "numpy",
    "scipy",
    "networkx",
]

# Local cache of known available packages
_known_available_packages: Set[str] = set()

# Cache for requirements files
_requirements_cache: Optional[Dict[str, str]] = None
_setup_py_cache: Optional[Dict[str, str]] = None


def _update_known_available_packages():
    """Update the local cache of known available packages."""
    global _known_available_packages
    try:
        # Get all installed packages from importlib.metadata
        import importlib.metadata as metadata
        for dist in metadata.distributions():
            _known_available_packages.add(dist.metadata['Name'].lower())
    except Exception as e:
        logger.warning(f"Failed to update known available packages: {e}")


def _check_package_installed(package_name: str) -> bool:
    """Check if a package is installed using importlib.metadata.
    
    Args:
        package_name: Name of the package to check
        
    Returns:
        True if the package is installed, False otherwise
    """
    try:
        distribution(package_name)
        return True
    except PackageNotFoundError:
        return False
    except Exception:
        return False


def _load_requirements_file() -> Dict[str, str]:
    """Load and parse requirements.txt if it exists.
    
    Returns:
        Dictionary mapping package names to version specifiers
    """
    global _requirements_cache
    if _requirements_cache is not None:
        return _requirements_cache
    
    _requirements_cache = {}
    requirements_paths = [
        "requirements.txt",
        "requirements/requirements.txt",
        "../requirements.txt",
    ]
    
    for path in requirements_paths:
        if os.path.exists(path):
            try:
                with open(path, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#') and not line.startswith('-'):
                            # Parse package name and version
                            parts = line.split('==')
                            if len(parts) >= 2:
                                _requirements_cache[parts[0].strip().lower()] = parts[1].strip()
                            elif line:
                                _requirements_cache[line.lower()] = ""
                break
            except Exception as e:
                logger.warning(f"Failed to load requirements file {path}: {e}")
    
    return _requirements_cache


def _load_setup_py() -> Dict[str, str]:
    """Load and parse setup.py if it exists.
    
    Returns:
        Dictionary mapping package names to version specifiers
    """
    global _setup_py_cache
    if _setup_py_cache is not None:
        return _setup_py_cache
    
    _setup_py_cache = {}
    setup_paths = [
        "setup.py",
        "../setup.py",
    ]
    
    for path in setup_paths:
        if os.path.exists(path):
            try:
                with open(path, 'r') as f:
                    content = f.read()
                # Simple parsing for install_requires
                if 'install_requires' in content:
                    # Extract the list between brackets
                    start = content.find('install_requires=[')
                    if start != -1:
                        start = content.find('[', start) + 1
                        end = content.find(']', start)
                        if end != -1:
                            requires_str = content[start:end]
                            for req in requires_str.split(','):
                                req = req.strip().strip("'").strip('"')
                                if req:
                                    parts = req.split('==')
                                    if len(parts) >= 2:
                                        _setup_py_cache[parts[0].strip().lower()] = parts[1].strip()
                                    else:
                                        _setup_py_cache[req.lower()] = ""
                break
            except Exception as e:
                logger.warning(f"Failed to load setup.py {path}: {e}")
    
    return _setup_py_cache


def _get_suggested_fix(module_name: str) -> str:
    """Generate a suggested fix for a failed import.
    
    Args:
        module_name: Name of the module that failed to import
        
    Returns:
        Suggested fix command
    """
    # Check if it's a known package
    package_name = module_name.split('.')[0].lower()
    
    # Check requirements files for version info
    requirements = _load_requirements_file()
    setup_py = _load_setup_py()
    
    version = None
    if package_name in requirements:
        version = requirements[package_name]
    elif package_name in setup_py:
        version = setup_py[package_name]
    
    if version:
        return f"pip install {package_name}=={version}"
    else:
        return f"pip install {package_name}"


def validate_import(module_name: str) -> Tuple[bool, Optional[str], Optional[str]]:
    """Validate that a module can be imported without errors.
    
    Args:
        module_name: Fully qualified module name to validate
        
    Returns:
        Tuple of (success, error_message, suggested_fix)
    """
    # Update known available packages cache periodically
    _update_known_available_packages()
    
    # Check if the package is known to be available
    package_name = module_name.split('.')[0].lower()
    if package_name in _known_available_packages:
        try:
            importlib.import_module(module_name)
            return True, None, None
        except ImportError as e:
            return False, f"ImportError: {str(e)}", _get_suggested_fix(module_name)
        except SyntaxError as e:
            return False, f"SyntaxError in {module_name}: {str(e)}", None
        except Exception as e:
            return False, f"Unexpected error importing {module_name}: {str(e)}", None
    
    # Check using importlib.metadata
    if _check_package_installed(package_name):
        try:
            importlib.import_module(module_name)
            _known_available_packages.add(package_name)
            return True, None, None
        except ImportError as e:
            return False, f"ImportError: {str(e)}", _get_suggested_fix(module_name)
        except SyntaxError as e:
            return False, f"SyntaxError in {module_name}: {str(e)}", None
        except Exception as e:
            return False, f"Unexpected error importing {module_name}: {str(e)}", None
    
    # Package not found
    return False, f"Package '{package_name}' is not installed", _get_suggested_fix(module_name)


def validate_dependencies(dependencies: List[str]) -> List[Tuple[str, bool, Optional[str], Optional[str]]]:
    """Validate a list of module dependencies.
    
    Args:
        dependencies: List of module names to validate
        
    Returns:
        List of (module_name, success, error_message, suggested_fix) tuples
    """
    results = []
    for module_name in dependencies:
        success, error, suggested_fix = validate_import(module_name)
        results.append((module_name, success, error, suggested_fix))
        if success:
            logger.debug(f"✓ {module_name} validated successfully")
        else:
            logger.error(f"✗ {module_name} validation failed: {error}")
            if suggested_fix:
                logger.info(f"  Suggested fix: {suggested_fix}")
    return results


def get_failed_imports(results: List[Tuple[str, bool, Optional[str], Optional[str]]]) -> List[Tuple[str, str, Optional[str]]]:
    """Extract failed imports from validation results.
    
    Args:
        results: List of validation result tuples
        
    Returns:
        List of (module_name, error_message, suggested_fix) for failed imports
    """
    return [(module, error, suggested_fix) for module, success, error, suggested_fix in results if not success]


def run_pre_import_validation() -> bool:
    """Run comprehensive pre-import validation.
    
    Returns:
        True if all core dependencies pass validation, False otherwise
    """
    logger.info("Running pre-import dependency validation...")
    
    # Update known available packages
    _update_known_available_packages()
    
    all_results = []
    
    # Validate core dependencies (required)
    logger.info("Validating core dependencies...")
    core_results = validate_dependencies(CORE_DEPENDENCIES)
    all_results.extend(core_results)
    
    # Validate optional dependencies
    logger.info("Validating optional dependencies...")
    optional_results = validate_dependencies(OPTIONAL_DEPENDENCIES)
    all_results.extend(optional_results)
    
    # Validate third-party dependencies
    logger.info("Validating third-party dependencies...")
    third_party_results = validate_dependencies(THIRD_PARTY_DEPENDENCIES)
    all_results.extend(third_party_results)
    
    # Check for failures
    failed_core = get_failed_imports(core_results)
    failed_optional = get_failed_imports(optional_results)
    failed_third_party = get_failed_imports(third_party_results)
    
    if failed_core:
        logger.error(f"CRITICAL: {len(failed_core)} core dependency/ies failed validation:")
        for module, error, suggested_fix in failed_core:
            logger.error(f"  - {module}: {error}")
            if suggested_fix:
                logger.error(f"    Suggested fix: {suggested_fix}")
        return False
    
    if failed_optional:
        logger.warning(f"WARNING: {len(failed_optional)} optional dependency/ies failed validation:")
        for module, error, suggested_fix in failed_optional:
            logger.warning(f"  - {module}: {error}")
            if suggested_fix:
                logger.warning(f"    Suggested fix: {suggested_fix}")
    
    if failed_third_party:
        logger.warning(f"WARNING: {len(failed_third_party)} third-party dependency/ies failed validation:")
        for module, error, suggested_fix in failed_third_party:
            logger.warning(f"  - {module}: {error}")
            if suggested_fix:
                logger.warning(f"    Suggested fix: {suggested_fix}")
    
    logger.info("Pre-import validation completed successfully")
    return True


def validate_module_file(file_path: str) -> Tuple[bool, Optional[str]]:
    """Validate a Python file by attempting to compile it.
    
    Args:
        file_path: Path to the Python file to validate
        
    Returns:
        Tuple of (success, error_message)
    """
    try:
        with open(file_path, 'r') as f:
            source = f.read()
        compile(source, file_path, 'exec')
        return True, None
    except SyntaxError as e:
        return False, f"SyntaxError in {file_path}: {str(e)}"
    except Exception as e:
        return False, f"Error validating {file_path}: {str(e)}"


def validate_all_module_files(module_paths: List[str]) -> bool:
    """Validate multiple Python files by attempting to compile them.
    
    Args:
        module_paths: List of file paths to validate
        
    Returns:
        True if all files compile successfully, False otherwise
    """
    all_passed = True
    for file_path in module_paths:
        success, error = validate_module_file(file_path)
        if success:
            logger.debug(f"✓ {file_path} compiles successfully")
        else:
            logger.error(f"✗ {file_path} compilation failed: {error}")
            all_passed = False
    return all_passed


def get_system_dependency_report() -> dict:
    """Generate a comprehensive dependency report for the system.
    
    Returns:
        Dictionary with dependency validation results
    """
    report = {
        "core": {},
        "optional": {},
        "third_party": {},
        "overall_status": "unknown"
    }
    
    # Validate all dependency categories
    for module in CORE_DEPENDENCIES:
        success, error, suggested_fix = validate_import(module)
        report["core"][module] = {"success": success, "error": error, "suggested_fix": suggested_fix}
    
    for module in OPTIONAL_DEPENDENCIES:
        success, error, suggested_fix = validate_import(module)
        report["optional"][module] = {"success": success, "error": error, "suggested_fix": suggested_fix}
    
    for module in THIRD_PARTY_DEPENDENCIES:
        success, error, suggested_fix = validate_import(module)
        report["third_party"][module] = {"success": success, "error": error, "suggested_fix": suggested_fix}
    
    # Determine overall status
    core_failures = any(not v["success"] for v in report["core"].values())
    report["overall_status"] = "failed" if core_failures else "passed"
    
    return report


def _extract_imports_from_source(source: str, filename: str) -> List[Tuple[str, str]]:
    """Extract import statements from Python source code.
    
    Args:
        source: Python source code string
        filename: Name of the file (for error reporting)
        
    Returns:
        List of (module_name, imported_name) tuples
    """
    imports = []
    try:
        tree = ast.parse(source, filename=filename)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append((alias.name, alias.asname or alias.name))
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                for alias in node.names:
                    full_name = f"{module}.{alias.name}" if module else alias.name
                    imports.append((full_name, alias.asname or alias.name))
            elif isinstance(node, ast.Call):
                # Handle dynamic imports like importlib.import_module('module_name')
                if isinstance(node.func, ast.Attribute):
                    if node.func.attr == 'import_module' and isinstance(node.func.value, ast.Name):
                        if node.func.value.id == 'importlib':
                            if node.args and isinstance(node.args[0], ast.Constant):
                                imports.append((node.args[0].value, node.args[0].value))
    except SyntaxError:
        pass  # Will be caught by other validation
    return imports


def _extract_exports_from_source(source: str, filename: str) -> Set[str]:
    """Extract exported names from Python source code.
    
    Args:
        source: Python source code string
        filename: Name of the file (for error reporting)
        
    Returns:
        Set of exported names
    """
    exports = set()
    try:
        tree = ast.parse(source, filename=filename)
        # Add all top-level function and class definitions
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                exports.add(node.name)
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        exports.add(target.id)
            elif isinstance(node, ast.AnnAssign):
                if isinstance(node.target, ast.Name):
                    exports.add(node.target.id)
        
        # Check for __all__ definition
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == "__all__":
                        if isinstance(node.value, (ast.List, ast.Tuple)):
                            for elt in node.value.elts:
                                if isinstance(elt, ast.Constant):
                                    exports.add(elt.value)
    except SyntaxError:
        pass
    return exports


def validate_imports_across_files(file_changes_dict: Dict[str, str]) -> List[str]:
    """Validate cross-file import consistency across proposed file changes.
    
    Checks that if module A imports from module B, module B actually exports
    the symbol being imported.
    
    Args:
        file_changes_dict: Dictionary mapping filenames to their proposed code
        
    Returns:
        List of issue descriptions (strings) for any inconsistencies found
    """
    issues = []
    
    # First pass: extract all imports and exports from each file
    file_imports: Dict[str, List[Tuple[str, str]]] = {}
    file_exports: Dict[str, Set[str]] = {}
    
    for filename, source in file_changes_dict.items():
        file_imports[filename] = _extract_imports_from_source(source, filename)
        file_exports[filename] = _extract_exports_from_source(source, filename)
    
    # Second pass: check each import against the corresponding file's exports
    for importing_file, imports in file_imports.items():
        for full_name, imported_name in imports:
            # Split the import to find the source module and symbol
            parts = full_name.split(".")
            if len(parts) >= 2:
                # This is a from-import like "module.submodule.symbol"
                # The source module is everything except the last part
                source_module = ".".join(parts[:-1])
                symbol = parts[-1]
                
                # Check if the source module is in our file changes
                if source_module in file_changes_dict:
                    source_file = source_module.replace(".", "/") + ".py"
                    # Try to find the actual file key (might be different format)
                    matching_files = [f for f in file_changes_dict.keys() if f.endswith(source_file) or f == source_module]
                    if matching_files:
                        source_file_key = matching_files[0]
                        if symbol not in file_exports.get(source_file_key, set()):
                            issues.append(
                                f"File '{importing_file}' imports '{symbol}' from '{source_module}', "
                                f"but '{source_module}' does not export '{symbol}'"
                            )
                    else:
                        issues.append(
                            f"File '{importing_file}' imports from '{source_module}', "
                            f"but '{source_module}' is not in the proposed changes"
                        )
            elif len(parts) == 1:
                # This is a simple import like "module"
                # Check if the module is in our file changes
                source_file = parts[0].replace(".", "/") + ".py"
                matching_files = [f for f in file_changes_dict.keys() if f.endswith(source_file) or f == parts[0]]
                if not matching_files:
                    issues.append(
                        f"File '{importing_file}' imports module '{parts[0]}', "
                        f"but '{parts[0]}' is not in the proposed changes"
                    )
    
    return issues


# Run validation when module is imported
if __name__ != "__main__":
    # Configure logging if not already configured
    if not logger.handlers:
        logging.basicConfig(level=logging.INFO)
    
    # Initialize known available packages cache
    _update_known_available_packages()
    
    # Automatically run validation on import
    validation_passed = run_pre_import_validation()
    if not validation_passed:
        logger.critical("Pre-import validation failed! System may not function correctly.")
        # Don't raise an exception here - let the importing code decide how to handle
else:
    # When run directly, perform comprehensive validation
    logging.basicConfig(level=logging.INFO)
    print("Running comprehensive dependency validation...")
    report = get_system_dependency_report()
    
    print(f"\nOverall Status: {report['overall_status'].upper()}")
    
    print("\nCore Dependencies:")
    for module, info in report["core"].items():
        status = "✓" if info["success"] else "✗"
        print(f"  {status} {module}")
        if info["error"]:
            print(f"    Error: {info['error']}")
        if info["suggested_fix"]:
            print(f"    Suggested fix: {info['suggested_fix']}")
    
    print("\nOptional Dependencies:")
    for module, info in report["optional"].items():
        status = "✓" if info["success"] else "✗"
        print(f"  {status} {module}")
        if info["error"]:
            print(f"    Error: {info['error']}")
        if info["suggested_fix"]:
            print(f"    Suggested fix: {info['suggested_fix']}")
    
    print("\nThird-Party Dependencies:")
    for module, info in report["third_party"].items():
        status = "✓" if info["success"] else "✗"
        print(f"  {status} {module}")
        if info["error"]:
            print(f"    Error: {info['error']}")
        if info["suggested_fix"]:
            print(f"    Suggested fix: {info['suggested_fix']}")
    
    sys.exit(0 if report["overall_status"] == "passed" else 1)