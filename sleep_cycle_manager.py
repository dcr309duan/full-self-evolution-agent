import ast
import os
import glob
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Set, Tuple, Optional

class DeadCodeScanner:
    """Scans all .py files to identify modules with zero test coverage and no imports from active code."""
    
    def __init__(self, project_root: str = "."):
        self.project_root = Path(project_root)
        self.test_dir = self.project_root / "tests"
        self.all_py_files = self._find_all_py_files()
        self.import_map = self._build_import_map()
    
    def _find_all_py_files(self) -> List[Path]:
        """Find all .py files in the project (excluding tests directory)."""
        py_files = []
        for root, dirs, files in os.walk(self.project_root):
            # Skip tests directory and virtual environments
            if 'tests' in dirs:
                dirs.remove('tests')
            if '.venv' in dirs:
                dirs.remove('.venv')
            if '__pycache__' in dirs:
                dirs.remove('__pycache__')
            for file in files:
                if file.endswith('.py'):
                    py_files.append(Path(root) / file)
        return py_files
    
    def _build_import_map(self) -> Dict[str, Set[str]]:
        """Build a map of module names to the modules that import them."""
        import_map: Dict[str, Set[str]] = {}
        for py_file in self.all_py_files:
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    tree = ast.parse(f.read(), filename=str(py_file))
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            module_name = alias.name.split('.')[0]
                            if module_name not in import_map:
                                import_map[module_name] = set()
                            import_map[module_name].add(str(py_file))
                    elif isinstance(node, ast.ImportFrom):
                        if node.module:
                            module_name = node.module.split('.')[0]
                            if module_name not in import_map:
                                import_map[module_name] = set()
                            import_map[module_name].add(str(py_file))
            except (SyntaxError, UnicodeDecodeError):
                continue
        return import_map
    
    def _has_test_file(self, module_path: Path) -> bool:
        """Check if a corresponding test file exists in the tests directory."""
        # Convert module path to test file path
        relative_path = module_path.relative_to(self.project_root)
        test_file_name = f"test_{relative_path.name}"
        test_file_path = self.test_dir / test_file_name
        return test_file_path.exists()
    
    def _is_imported(self, module_path: Path) -> bool:
        """Check if the module is imported by any other active code."""
        module_name = module_path.stem  # Get module name without .py
        return module_name in self.import_map and len(self.import_map[module_name]) > 0
    
    def scan(self) -> List[Path]:
        """Identify modules with zero test coverage and no imports from active code."""
        dead_modules = []
        for py_file in self.all_py_files:
            if not self._has_test_file(py_file) and not self._is_imported(py_file):
                dead_modules.append(py_file)
        return dead_modules


class DuplicateConsolidator:
    """Compares utility functions across modules using AST signature matching and suggests merges."""
    
    def __init__(self, project_root: str = "."):
        self.project_root = Path(project_root)
        self.all_py_files = self._find_all_py_files()
    
    def _find_all_py_files(self) -> List[Path]:
        """Find all .py files in the project."""
        py_files = []
        for root, dirs, files in os.walk(self.project_root):
            if '__pycache__' in dirs:
                dirs.remove('__pycache__')
            if '.venv' in dirs:
                dirs.remove('.venv')
            for file in files:
                if file.endswith('.py'):
                    py_files.append(Path(root) / file)
        return py_files
    
    def _get_function_signature(self, func_node: ast.FunctionDef) -> Tuple[str, str, str]:
        """Extract a signature from a function definition node."""
        # Get function name
        name = func_node.name
        
        # Get parameter signature (parameter names and default values)
        params = []
        defaults = [None] * (len(func_node.args.args) - len(func_node.args.defaults)) + func_node.args.defaults
        for arg, default in zip(func_node.args.args, defaults):
            param_str = arg.arg
            if default is not None:
                param_str += f"={ast.dump(default)}"
            params.append(param_str)
        param_signature = ",".join(params)
        
        # Get return type annotation if present
        return_annotation = ""
        if func_node.returns:
            return_annotation = ast.dump(func_node.returns)
        
        return (name, param_signature, return_annotation)
    
    def _extract_functions(self, file_path: Path) -> List[Tuple[str, str, str, str]]:
        """Extract all function definitions from a Python file."""
        functions = []
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                tree = ast.parse(f.read(), filename=str(file_path))
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    name, param_sig, return_ann = self._get_function_signature(node)
                    functions.append((name, param_sig, return_ann, str(file_path)))
        except (SyntaxError, UnicodeDecodeError):
            pass
        return functions
    
    def find_duplicates(self) -> List[Dict]:
        """Find functions with identical signatures across different modules."""
        all_functions = []
        for py_file in self.all_py_files:
            all_functions.extend(self._extract_functions(py_file))
        
        # Group functions by signature (name, param_signature, return_annotation)
        signature_groups: Dict[Tuple[str, str, str], List[Tuple[str, str, str, str]]] = {}
        for func in all_functions:
            key = (func[0], func[1], func[2])  # name, param_sig, return_ann
            if key not in signature_groups:
                signature_groups[key] = []
            signature_groups[key].append(func)
        
        # Find duplicates (functions with same signature in different files)
        duplicates = []
        for signature, funcs in signature_groups.items():
            if len(funcs) > 1:
                # Check if they are in different files
                files = set(f[3] for f in funcs)
                if len(files) > 1:
                    duplicates.append({
                        'signature': {
                            'name': signature[0],
                            'parameters': signature[1],
                            'return_type': signature[2]
                        },
                        'locations': [{'file': f[3], 'name': f[0]} for f in funcs]
                    })
        return duplicates
    
    def suggest_merges(self) -> List[Dict]:
        """Suggest merges for duplicate utility functions."""
        duplicates = self.find_duplicates()
        suggestions = []
        for dup in duplicates:
            suggestion = {
                'function_name': dup['signature']['name'],
                'locations': dup['locations'],
                'recommendation': f"Merge {dup['signature']['name']} into a single utility module"
            }
            suggestions.append(suggestion)
        return suggestions


class CleanupLogger:
    """Records all deletions/consolidations with timestamps and freed capacity."""
    
    def __init__(self, log_file: str = "cleanup_log.txt"):
        self.log_file = log_file
        self.log_entries: List[Dict] = []
    
    def log_deletion(self, file_path: str, lines_removed: int, reason: str = "Dead code removal"):
        """Log a file deletion event."""
        entry = {
            'timestamp': datetime.now().isoformat(),
            'action': 'deletion',
            'file': file_path,
            'lines_removed': lines_removed,
            'reason': reason
        }
        self.log_entries.append(entry)
        self._write_entry(entry)
    
    def log_consolidation(self, source_files: List[str], target_file: str, lines_removed: int):
        """Log a consolidation event where multiple files are merged into one."""
        entry = {
            'timestamp': datetime.now().isoformat(),
            'action': 'consolidation',
            'source_files': source_files,
            'target_file': target_file,
            'lines_removed': lines_removed,
            'reason': 'Duplicate function consolidation'
        }
        self.log_entries.append(entry)
        self._write_entry(entry)
    
    def _write_entry(self, entry: Dict):
        """Write a log entry to the log file."""
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(f"[{entry['timestamp']}] {entry['action'].upper()}: ")
            if entry['action'] == 'deletion':
                f.write(f"Deleted {entry['file']} ({entry['lines_removed']} lines) - {entry['reason']}\n")
            elif entry['action'] == 'consolidation':
                f.write(f"Consolidated {', '.join(entry['source_files'])} into {entry['target_file']} "
                       f"({entry['lines_removed']} lines removed) - {entry['reason']}\n")
    
    def get_total_freed_capacity(self) -> int:
        """Get total lines of code removed across all logged actions."""
        total = 0
        for entry in self.log_entries:
            total += entry.get('lines_removed', 0)
        return total
    
    def get_log_summary(self) -> str:
        """Get a summary of all logged actions."""
        summary = f"Cleanup Log Summary ({len(self.log_entries)} actions)\n"
        summary += f"Total lines freed: {self.get_total_freed_capacity()}\n"
        for entry in self.log_entries:
            summary += f"  [{entry['timestamp']}] {entry['action']}: {entry.get('file', entry.get('target_file', ''))}\n"
        return summary


class ConfirmationPrompt:
    """Requires explicit 'yes' before deletion."""
    
    @staticmethod
    def confirm(message: str = "Are you sure you want to proceed?") -> bool:
        """Prompt user for confirmation. Returns True only if user types 'yes'."""
        response = input(f"{message} (type 'yes' to confirm): ").strip().lower()
        return response == 'yes'
    
    @staticmethod
    def confirm_deletion(file_path: str, lines: int = 0) -> bool:
        """Specific confirmation for file deletion."""
        message = f"Delete {file_path} ({lines} lines)?"
        return ConfirmationPrompt.confirm(message)
    
    @staticmethod
    def confirm_consolidation(source_files: List[str], target_file: str) -> bool:
        """Specific confirmation for consolidation."""
        message = f"Consolidate {', '.join(source_files)} into {target_file}?"
        return ConfirmationPrompt.confirm(message)


# Example usage (commented out to avoid accidental execution)
"""
if __name__ == "__main__":
    # Example: Scan for dead code
    scanner = DeadCodeScanner()
    dead_modules = scanner.scan()
    print(f"Found {len(dead_modules)} dead modules:")
    for module in dead_modules:
        print(f"  {module}")
    
    # Example: Find duplicate functions
    consolidator = DuplicateConsolidator()
    duplicates = consolidator.find_duplicates()
    print(f"Found {len(duplicates)} duplicate function groups")
    
    # Example: Log a deletion
    logger = CleanupLogger()
    logger.log_deletion("dead_module.py", 50, "No test coverage and no imports")
    
    # Example: Confirm before deletion
    if ConfirmationPrompt.confirm_deletion("dead_module.py", 50):
        print("Deletion confirmed")
    else:
        print("Deletion cancelled")
"""