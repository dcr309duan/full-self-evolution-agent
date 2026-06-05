import ast
import os
import sys
from typing import Dict, List, Set, Tuple, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
import json
import hashlib


class Severity(Enum):
    """Severity levels for conflicts."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class Conflict:
    """Represents a single conflict detected."""
    type: str
    description: str
    severity: Severity
    file1: str
    file2: str
    location1: Optional[Tuple[int, int]] = None  # (line, col)
    location2: Optional[Tuple[int, int]] = None
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ConflictReport:
    """Structured conflict report."""
    conflicts: List[Conflict] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def add_conflict(self, conflict: Conflict) -> None:
        self.conflicts.append(conflict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "metadata": self.metadata,
            "conflicts": [
                {
                    "type": c.type,
                    "description": c.description,
                    "severity": c.severity.value,
                    "file1": c.file1,
                    "file2": c.file2,
                    "location1": c.location1,
                    "location2": c.location2,
                    "details": c.details
                }
                for c in self.conflicts
            ]
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    def __len__(self) -> int:
        return len(self.conflicts)


class ASTAnalyzer(ast.NodeVisitor):
    """Parses AST to extract definitions, dependencies, and interface info."""

    def __init__(self, filepath: str):
        self.filepath = filepath
        self.functions: Dict[str, ast.FunctionDef] = {}
        self.classes: Dict[str, ast.ClassDef] = {}
        self.global_vars: Set[str] = set()
        self.file_io: bool = False
        self.database_tables: Set[str] = set()
        self.imports: List[ast.Import | ast.ImportFrom] = []
        self.function_signatures: Dict[str, Dict[str, Any]] = {}
        self.class_methods: Dict[str, Dict[str, Dict[str, Any]]] = {}
        self.ast_tree: Optional[ast.AST] = None

    def analyze(self) -> None:
        """Parse and analyze the file."""
        if not os.path.exists(self.filepath):
            return
        try:
            with open(self.filepath, 'r', encoding='utf-8') as f:
                source = f.read()
            self.ast_tree = ast.parse(source, filename=self.filepath)
            self.visit(self.ast_tree)
        except SyntaxError as e:
            # Could log or store syntax error as conflict
            pass

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.functions[node.name] = node
        self._extract_function_signature(node)
        self._check_for_shared_state(node)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.functions[node.name] = node
        self._extract_function_signature(node)
        self._check_for_shared_state(node)
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.classes[node.name] = node
        methods = {}
        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                methods[item.name] = self._extract_method_signature(item)
        self.class_methods[node.name] = methods
        self._check_for_shared_state(node)
        self.generic_visit(node)

    def visit_Global(self, node: ast.Global) -> None:
        for name in node.names:
            self.global_vars.add(name)

    def visit_Import(self, node: ast.Import) -> None:
        self.imports.append(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        self.imports.append(node)

    def visit_Call(self, node: ast.Call) -> None:
        # Detect file I/O and database calls
        if isinstance(node.func, ast.Attribute):
            if isinstance(node.func.value, ast.Name):
                if node.func.value.id == 'open' and node.func.attr in ('read', 'write', 'append'):
                    self.file_io = True
                elif node.func.attr in ('execute', 'executemany', 'fetchall', 'fetchone'):
                    self.database_tables.add('*')  # generic DB call
                elif node.func.attr in ('insert', 'update', 'delete', 'select'):
                    # Could extract table name from args
                    for arg in node.args:
                        if isinstance(arg, ast.Str):
                            self.database_tables.add(arg.s)
        self.generic_visit(node)

    def _extract_function_signature(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> Dict[str, Any]:
        sig = {
            'name': node.name,
            'args': [arg.arg for arg in node.args.args],
            'defaults': len(node.args.defaults),
            'vararg': node.args.vararg.arg if node.args.vararg else None,
            'kwonlyargs': [arg.arg for arg in node.args.kwonlyargs],
            'kw_defaults': len(node.args.kw_defaults),
            'kwarg': node.args.kwarg.arg if node.args.kwarg else None,
            'returns': ast.dump(node.returns) if node.returns else None,
            'decorator_list': [ast.dump(d) for d in node.decorator_list],
        }
        self.function_signatures[node.name] = sig
        return sig

    def _extract_method_signature(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> Dict[str, Any]:
        return self._extract_function_signature(node)

    def _check_for_shared_state(self, node: ast.AST) -> None:
        """Walk node to find global variable assignments and file I/O."""
        for child in ast.walk(node):
            if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Store):
                if child.id in self.global_vars:
                    pass  # already tracked
            elif isinstance(child, ast.Call):
                if isinstance(child.func, ast.Attribute):
                    if isinstance(child.func.value, ast.Name):
                        if child.func.value.id == 'open':
                            self.file_io = True
                        elif child.func.attr in ('execute', 'executemany'):
                            self.database_tables.add('*')


class ConflictDetector:
    """Main conflict detection engine."""

    def __init__(self, files: List[str]):
        self.files = files
        self.analyzers: Dict[str, ASTAnalyzer] = {}
        self.report = ConflictReport()
        self._analyze_all()

    def _analyze_all(self) -> None:
        for filepath in self.files:
            analyzer = ASTAnalyzer(filepath)
            analyzer.analyze()
            self.analyzers[filepath] = analyzer

    def detect_all(self) -> ConflictReport:
        """Run all conflict detection checks."""
        self._detect_overlapping_definitions()
        self._detect_shared_state_dependencies()
        self._check_interface_compatibility()
        self._check_import_changes()
        self.report.metadata = {
            "files_analyzed": len(self.files),
            "total_conflicts": len(self.report)
        }
        return self.report

    def _detect_overlapping_definitions(self) -> None:
        """Detect overlapping function and class definitions across files."""
        all_functions: Dict[str, List[Tuple[str, ast.FunctionDef]]] = {}
        all_classes: Dict[str, List[Tuple[str, ast.ClassDef]]] = {}

        for filepath, analyzer in self.analyzers.items():
            for name, node in analyzer.functions.items():
                all_functions.setdefault(name, []).append((filepath, node))
            for name, node in analyzer.classes.items():
                all_classes.setdefault(name, []).append((filepath, node))

        for name, occurrences in all_functions.items():
            if len(occurrences) > 1:
                for i in range(len(occurrences)):
                    for j in range(i+1, len(occurrences)):
                        file1, node1 = occurrences[i]
                        file2, node2 = occurrences[j]
                        conflict = Conflict(
                            type="overlapping_function",
                            description=f"Function '{name}' defined in multiple files.",
                            severity=Severity.HIGH,
                            file1=file1,
                            file2=file2,
                            location1=(node1.lineno, node1.col_offset),
                            location2=(node2.lineno, node2.col_offset),
                            details={"function_name": name}
                        )
                        self.report.add_conflict(conflict)

        for name, occurrences in all_classes.items():
            if len(occurrences) > 1:
                for i in range(len(occurrences)):
                    for j in range(i+1, len(occurrences)):
                        file1, node1 = occurrences[i]
                        file2, node2 = occurrences[j]
                        conflict = Conflict(
                            type="overlapping_class",
                            description=f"Class '{name}' defined in multiple files.",
                            severity=Severity.HIGH,
                            file1=file1,
                            file2=file2,
                            location1=(node1.lineno, node1.col_offset),
                            location2=(node2.lineno, node2.col_offset),
                            details={"class_name": name}
                        )
                        self.report.add_conflict(conflict)

    def _detect_shared_state_dependencies(self) -> None:
        """Detect shared global variables, file I/O, and database tables."""
        # Global variables
        global_vars_per_file: Dict[str, Set[str]] = {}
        for filepath, analyzer in self.analyzers.items():
            global_vars_per_file[filepath] = analyzer.global_vars

        # Find global variables defined in multiple files
        all_globals: Dict[str, List[str]] = {}
        for filepath, vars_set in global_vars_per_file.items():
            for var in vars_set:
                all_globals.setdefault(var, []).append(filepath)

        for var, files in all_globals.items():
            if len(files) > 1:
                for i in range(len(files)):
                    for j in range(i+1, len(files)):
                        conflict = Conflict(
                            type="shared_global_variable",
                            description=f"Global variable '{var}' used in multiple files.",
                            severity=Severity.MEDIUM,
                            file1=files[i],
                            file2=files[j],
                            details={"variable": var}
                        )
                        self.report.add_conflict(conflict)

        # File I/O
        file_io_files = [f for f, a in self.analyzers.items() if a.file_io]
        if len(file_io_files) > 1:
            for i in range(len(file_io_files)):
                for j in range(i+1, len(file_io_files)):
                    conflict = Conflict(
                        type="shared_file_io",
                        description="Multiple files perform file I/O operations.",
                        severity=Severity.MEDIUM,
                        file1=file_io_files[i],
                        file2=file_io_files[j],
                        details={"file_io_files": file_io_files}
                    )
                    self.report.add_conflict(conflict)

        # Database tables
        all_tables: Dict[str, List[str]] = {}
        for filepath, analyzer in self.analyzers.items():
            for table in analyzer.database_tables:
                all_tables.setdefault(table, []).append(filepath)

        for table, files in all_tables.items():
            if len(files) > 1:
                for i in range(len(files)):
                    for j in range(i+1, len(files)):
                        conflict = Conflict(
                            type="shared_database_table",
                            description=f"Database table '{table}' accessed in multiple files.",
                            severity=Severity.HIGH,
                            file1=files[i],
                            file2=files[j],
                            details={"table": table}
                        )
                        self.report.add_conflict(conflict)

    def _check_interface_compatibility(self) -> None:
        """Check function signature and class method compatibility."""
        # Compare function signatures across files
        all_signatures: Dict[str, List[Tuple[str, Dict[str, Any]]]] = {}
        for filepath, analyzer in self.analyzers.items():
            for name, sig in analyzer.function_signatures.items():
                all_signatures.setdefault(name, []).append((filepath, sig))

        for name, sigs in all_signatures.items():
            if len(sigs) > 1:
                base_sig = sigs[0][1]
                for filepath, sig in sigs[1:]:
                    if sig != base_sig:
                        conflict = Conflict(
                            type="incompatible_function_signature",
                            description=f"Function '{name}' has different signatures across files.",
                            severity=Severity.CRITICAL,
                            file1=sigs[0][0],
                            file2=filepath,
                            details={
                                "function_name": name,
                                "signature1": base_sig,
                                "signature2": sig
                            }
                        )
                        self.report.add_conflict(conflict)

        # Compare class methods
        all_class_methods: Dict[str, Dict[str, List[Tuple[str, Dict[str, Any]]]]] = {}
        for filepath, analyzer in self.analyzers.items():
            for class_name, methods in analyzer.class_methods.items():
                if class_name not in all_class_methods:
                    all_class_methods[class_name] = {}
                for method_name, sig in methods.items():
                    all_class_methods[class_name].setdefault(method_name, []).append((filepath, sig))

        for class_name, methods in all_class_methods.items():
            for method_name, sigs in methods.items():
                if len(sigs) > 1:
                    base_sig = sigs[0][1]
                    for filepath, sig in sigs[1:]:
                        if sig != base_sig:
                            conflict = Conflict(
                                type="incompatible_class_method",
                                description=f"Method '{class_name}.{method_name}' has different signatures across files.",
                                severity=Severity.CRITICAL,
                                file1=sigs[0][0],
                                file2=filepath,
                                details={
                                    "class_name": class_name,
                                    "method_name": method_name,
                                    "signature1": base_sig,
                                    "signature2": sig
                                }
                            )
                            self.report.add_conflict(conflict)

    def _check_import_changes(self) -> None:
        """Detect import changes that may cause conflicts."""
        # Compare imports across files
        all_imports: Dict[str, Set[str]] = {}
        for filepath, analyzer in self.analyzers.items():
            imports = set()
            for imp in analyzer.imports:
                if isinstance(imp, ast.Import):
                    for alias in imp.names:
                        imports.add(alias.name)
                elif isinstance(imp, ast.ImportFrom):
                    module = imp.module or ''
                    for alias in imp.names:
                        imports.add(f"{module}.{alias.name}")
            all_imports[filepath] = imports

        # Find imports that are defined in one file and used in another
        # This is a simplified check; a full implementation would resolve imports
        for filepath1, imports1 in all_imports.items():
            for filepath2, imports2 in all_imports.items():
                if filepath1 < filepath2:
                    common = imports1 & imports2
                    if common:
                        conflict = Conflict(
                            type="shared_import",
                            description=f"Files share imports: {', '.join(common)}",
                            severity=Severity.LOW,
                            file1=filepath1,
                            file2=filepath2,
                            details={"shared_imports": list(common)}
                        )
                        self.report.add_conflict(conflict)


def detect_conflicts(files: List[str]) -> ConflictReport:
    """Convenience function to run conflict detection on a list of files."""
    detector = ConflictDetector(files)
    return detector.detect_all()


def generate_report(files: List[str], output_path: Optional[str] = None) -> str:
    """Generate a conflict report and optionally write to a file."""
    report = detect_conflicts(files)
    json_report = report.to_json()
    if output_path:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(json_report)
    return json_report


if __name__ == "__main__":
    # Example usage
    if len(sys.argv) > 1:
        files = sys.argv[1:]
        report = detect_conflicts(files)
        print(report.to_json())
    else:
        print("Usage: python conflict_detector.py <file1.py> <file2.py> ...")