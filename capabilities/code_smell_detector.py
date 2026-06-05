import ast
import os
import re
from collections import defaultdict
from typing import List, Dict, Tuple, Optional

class CodeSmellDetector:
    """Detects common code smells in a Python codebase."""

    # Thresholds for code smells
    LARGE_CLASS_LINES = 200
    LONG_METHOD_LINES = 50
    TOO_MANY_PARAMETERS = 5
    DUPLICATE_CODE_MIN_LINES = 10  # Minimum lines for a duplicate block
    DUPLICATE_CODE_SIMILARITY = 0.8  # Fraction of lines that must match

    def __init__(self, root_dir: str):
        self.root_dir = os.path.abspath(root_dir)
        self.report = []

    def analyze(self) -> List[Dict]:
        """Run all code smell analyses and return a structured report."""
        self.report = []
        python_files = self._get_python_files()

        # Parse all files into ASTs
        file_asts = {}
        for filepath in python_files:
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    source = f.read()
                tree = ast.parse(source, filename=filepath)
                file_asts[filepath] = (source, tree)
            except (SyntaxError, UnicodeDecodeError) as e:
                self.report.append({
                    'type': 'parse_error',
                    'file': filepath,
                    'severity': 'low',
                    'message': f'Could not parse file: {e}',
                    'suggestion': 'Fix syntax errors or encoding issues.'
                })

        # Run each detector
        self._detect_large_classes(file_asts)
        self._detect_long_methods(file_asts)
        self._detect_too_many_parameters(file_asts)
        self._detect_duplicate_code(file_asts)
        self._detect_god_objects(file_asts)
        self._detect_feature_envy(file_asts)

        return self.report

    def _get_python_files(self) -> List[str]:
        """Recursively find all .py files in the root directory."""
        python_files = []
        for root, dirs, files in os.walk(self.root_dir):
            # Skip common non-source directories
            dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ('__pycache__', 'venv', 'env', 'node_modules')]
            for file in files:
                if file.endswith('.py'):
                    python_files.append(os.path.join(root, file))
        return python_files

    def _detect_large_classes(self, file_asts: Dict[str, Tuple[str, ast.AST]]):
        """Detect classes with more than LARGE_CLASS_LINES lines."""
        for filepath, (source, tree) in file_asts.items():
            lines = source.splitlines()
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    # Count lines from class definition to end of class body
                    if hasattr(node, 'lineno') and hasattr(node, 'end_lineno'):
                        class_lines = node.end_lineno - node.lineno + 1
                        if class_lines > self.LARGE_CLASS_LINES:
                            self.report.append({
                                'type': 'large_class',
                                'file': filepath,
                                'line': node.lineno,
                                'class_name': node.name,
                                'severity': 'high' if class_lines > 400 else 'medium',
                                'message': f'Class "{node.name}" has {class_lines} lines (threshold: {self.LARGE_CLASS_LINES})',
                                'suggestion': 'Consider splitting the class into smaller, focused classes using composition or inheritance.'
                            })

    def _detect_long_methods(self, file_asts: Dict[str, Tuple[str, ast.AST]]):
        """Detect functions/methods with more than LONG_METHOD_LINES lines."""
        for filepath, (source, tree) in file_asts.items():
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if hasattr(node, 'lineno') and hasattr(node, 'end_lineno'):
                        method_lines = node.end_lineno - node.lineno + 1
                        if method_lines > self.LONG_METHOD_LINES:
                            self.report.append({
                                'type': 'long_method',
                                'file': filepath,
                                'line': node.lineno,
                                'method_name': node.name,
                                'severity': 'high' if method_lines > 100 else 'medium',
                                'message': f'Method "{node.name}" has {method_lines} lines (threshold: {self.LONG_METHOD_LINES})',
                                'suggestion': 'Extract smaller helper methods and break down the logic into cohesive units.'
                            })

    def _detect_too_many_parameters(self, file_asts: Dict[str, Tuple[str, ast.AST]]):
        """Detect functions with more than TOO_MANY_PARAMETERS parameters."""
        for filepath, (source, tree) in file_asts.items():
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    # Count only positional and keyword parameters (not *args, **kwargs)
                    param_count = len(node.args.args) + len(node.args.kwonlyargs)
                    if node.args.vararg:
                        param_count += 1  # *args counts as one
                    if node.args.kwarg:
                        param_count += 1  # **kwargs counts as one
                    if param_count > self.TOO_MANY_PARAMETERS:
                        self.report.append({
                            'type': 'too_many_parameters',
                            'file': filepath,
                            'line': node.lineno,
                            'method_name': node.name,
                            'severity': 'medium',
                            'message': f'Method "{node.name}" has {param_count} parameters (threshold: {self.TOO_MANY_PARAMETERS})',
                            'suggestion': 'Consider using a configuration object, *args, **kwargs, or splitting the method.'
                        })

    def _detect_duplicate_code(self, file_asts: Dict[str, Tuple[str, ast.AST]]):
        """Detect duplicate code blocks across files using line-by-line comparison."""
        # Collect all function/class bodies as lists of stripped lines
        code_blocks = []  # List of (filepath, start_line, end_line, lines)
        for filepath, (source, tree) in file_asts.items():
            source_lines = source.splitlines()
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    if hasattr(node, 'lineno') and hasattr(node, 'end_lineno'):
                        # Extract lines of the body (excluding decorators and signature)
                        body_start = node.body[0].lineno if node.body else node.lineno
                        body_end = node.end_lineno
                        block_lines = source_lines[body_start-1:body_end]
                        # Filter out blank lines and comments for comparison
                        cleaned = [line.strip() for line in block_lines if line.strip() and not line.strip().startswith('#')]
                        if len(cleaned) >= self.DUPLICATE_CODE_MIN_LINES:
                            code_blocks.append((filepath, body_start, body_end, cleaned))

        # Compare blocks pairwise (O(n^2) but acceptable for moderate codebases)
        for i in range(len(code_blocks)):
            for j in range(i+1, len(code_blocks)):
                file1, start1, end1, lines1 = code_blocks[i]
                file2, start2, end2, lines2 = code_blocks[j]
                # Skip if same file and overlapping
                if file1 == file2 and not (end1 < start2 or end2 < start1):
                    continue
                # Compute similarity as fraction of matching lines
                min_len = min(len(lines1), len(lines2))
                if min_len < self.DUPLICATE_CODE_MIN_LINES:
                    continue
                matches = sum(1 for a, b in zip(lines1, lines2) if a == b)
                similarity = matches / min_len
                if similarity >= self.DUPLICATE_CODE_SIMILARITY:
                    self.report.append({
                        'type': 'duplicate_code',
                        'file': file1,
                        'line': start1,
                        'severity': 'medium',
                        'message': f'Duplicate code block (similarity {similarity:.0%}) with {file2}:{start2}',
                        'suggestion': 'Extract the common code into a shared function or module.'
                    })

    def _detect_god_objects(self, file_asts: Dict[str, Tuple[str, ast.AST]]):
        """Detect classes that have too many methods and fields (god objects)."""
        for filepath, (source, tree) in file_asts.items():
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    method_count = 0
                    field_count = 0
                    for child in ast.walk(node):
                        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            method_count += 1
                        elif isinstance(child, ast.Assign):
                            for target in child.targets:
                                if isinstance(target, ast.Name):
                                    field_count += 1
                    # Heuristic: god object if >20 methods and >10 fields
                    if method_count > 20 and field_count > 10:
                        self.report.append({
                            'type': 'god_object',
                            'file': filepath,
                            'line': node.lineno,
                            'class_name': node.name,
                            'severity': 'high',
                            'message': f'Class "{node.name}" has {method_count} methods and {field_count} fields (potential god object)',
                            'suggestion': 'Decompose the class into smaller classes with single responsibilities.'
                        })

    def _detect_feature_envy(self, file_asts: Dict[str, Tuple[str, ast.AST]]):
        """Detect methods that use more attributes/methods of another class than their own."""
        # Build a mapping of class names to their defined attributes and methods
        class_defs = {}  # class_name -> set of own attributes/methods
        for filepath, (source, tree) in file_asts.items():
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    own_members = set()
                    for child in ast.walk(node):
                        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            own_members.add(child.name)
                        elif isinstance(child, ast.Assign):
                            for target in child.targets:
                                if isinstance(target, ast.Name):
                                    own_members.add(target.id)
                    class_defs[node.name] = own_members

        # Now analyze each method in each class
        for filepath, (source, tree) in file_asts.items():
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    # Find enclosing class
                    enclosing_class = None
                    for parent in ast.walk(tree):
                        if isinstance(parent, ast.ClassDef):
                            if node in ast.walk(parent):
                                enclosing_class = parent
                                break
                    if not enclosing_class:
                        continue

                    # Count attribute accesses on 'self' vs other objects
                    self_accesses = 0
                    other_accesses = 0
                    other_class_names = set()
                    for child in ast.walk(node):
                        if isinstance(child, ast.Attribute):
                            if isinstance(child.value, ast.Name):
                                if child.value.id == 'self':
                                    self_accesses += 1
                                else:
                                    other_accesses += 1
                                    # Try to infer the class name from variable name (heuristic)
                                    other_class_names.add(child.value.id)

                    # Heuristic: if other accesses > 2 * self accesses, feature envy
                    if self_accesses > 0 and other_accesses > 2 * self_accesses:
                        self.report.append({
                            'type': 'feature_envy',
                            'file': filepath,
                            'line': node.lineno,
                            'method_name': node.name,
                            'severity': 'medium',
                            'message': f'Method "{node.name}" accesses other objects {other_accesses} times vs self {self_accesses} times',
                            'suggestion': 'Consider moving this method to the class it envies, or pass the needed data as parameters.'
                        })


def generate_report(report: List[Dict], output_format: str = 'text') -> str:
    """Generate a formatted report from the analysis results."""
    if output_format == 'text':
        lines = []
        lines.append("=" * 60)
        lines.append("CODE SMELL ANALYSIS REPORT")
        lines.append("=" * 60)
        if not report:
            lines.append("No code smells detected.")
        else:
            # Group by severity
            severity_order = {'high': 0, 'medium': 1, 'low': 2}
            sorted_report = sorted(report, key=lambda x: (severity_order.get(x['severity'], 3), x['file'], x.get('line', 0)))
            for item in sorted_report:
                lines.append(f"\n[{item['severity'].upper()}] {item['type'].replace('_', ' ').title()}")
                lines.append(f"  File: {item['file']}")
                if 'line' in item:
                    lines.append(f"  Line: {item['line']}")
                if 'class_name' in item:
                    lines.append(f"  Class: {item['class_name']}")
                if 'method_name' in item:
                    lines.append(f"  Method: {item['method_name']}")
                lines.append(f"  Message: {item['message']}")
                lines.append(f"  Suggestion: {item['suggestion']}")
        lines.append("\n" + "=" * 60)
        return "\n".join(lines)
    elif output_format == 'json':
        import json
        return json.dumps(report, indent=2)
    else:
        raise ValueError(f"Unsupported output format: {output_format}")


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python code_smell_detector.py <directory> [--format text|json]")
        sys.exit(1)
    root_dir = sys.argv[1]
    output_format = 'text'
    if len(sys.argv) >= 3 and sys.argv[2] == '--format':
        if len(sys.argv) >= 4:
            output_format = sys.argv[3]
    detector = CodeSmellDetector(root_dir)
    report = detector.analyze()
    print(generate_report(report, output_format))