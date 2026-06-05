from pathlib import Path
import ast
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)


@dataclass
class Component:
    """Represents a code component extracted from the codebase."""
    name: str
    type: str  # 'module', 'class', 'function', 'import'
    file_path: str
    line_number: int
    docstring: Optional[str] = None
    parameters: List[Dict[str, str]] = field(default_factory=list)
    return_type: Optional[str] = None
    base_classes: List[str] = field(default_factory=list)
    decorators: List[str] = field(default_factory=list)
    imports: List[Dict[str, str]] = field(default_factory=list)
    body_summary: Optional[str] = None


class ComponentScanner:
    """Walks the codebase directory, parses Python files, and extracts components."""

    def __init__(self, root_dir: str, exclude_dirs: Optional[List[str]] = None):
        self.root_dir = Path(root_dir).resolve()
        self.exclude_dirs = exclude_dirs or ['__pycache__', '.git', 'venv', 'env', '.mypy_cache', '.pytest_cache']
        self.components: List[Component] = []

    def scan(self) -> List[Component]:
        """Main entry point: walk directory and extract all components."""
        self.components = []
        for py_file in self.root_dir.rglob("*.py"):
            if any(excluded in py_file.parts for excluded in self.exclude_dirs):
                continue
            try:
                self._process_file(py_file)
            except SyntaxError as e:
                logger.warning(f"Syntax error in {py_file}: {e}")
            except Exception as e:
                logger.error(f"Error processing {py_file}: {e}")
        return self.components

    def _process_file(self, file_path: Path) -> None:
        """Parse a single Python file and extract components."""
        try:
            source = file_path.read_text(encoding='utf-8', errors='ignore')
        except Exception as e:
            logger.warning(f"Cannot read {file_path}: {e}")
            return

        try:
            tree = ast.parse(source, filename=str(file_path))
        except SyntaxError:
            raise

        # Extract module-level docstring
        module_docstring = ast.get_docstring(tree)
        module_imports = self._extract_imports(tree)

        # Create module component
        module_component = Component(
            name=file_path.stem,
            type='module',
            file_path=str(file_path),
            line_number=1,
            docstring=module_docstring,
            imports=module_imports
        )
        self.components.append(module_component)

        # Extract classes and functions
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.ClassDef):
                self._extract_class(node, file_path)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self._extract_function(node, file_path)

    def _extract_imports(self, tree: ast.AST) -> List[Dict[str, str]]:
        """Extract import statements from AST."""
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append({
                        'module': alias.name,
                        'alias': alias.asname or '',
                        'type': 'import'
                    })
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ''
                for alias in node.names:
                    imports.append({
                        'module': module,
                        'name': alias.name,
                        'alias': alias.asname or '',
                        'type': 'from_import'
                    })
        return imports

    def _extract_class(self, node: ast.ClassDef, file_path: Path) -> None:
        """Extract class definition details."""
        docstring = ast.get_docstring(node)
        base_classes = [self._get_name(base) for base in node.bases]
        decorators = [self._get_name(dec) for dec in node.decorator_list]

        class_component = Component(
            name=node.name,
            type='class',
            file_path=str(file_path),
            line_number=node.lineno,
            docstring=docstring,
            base_classes=base_classes,
            decorators=decorators
        )
        self.components.append(class_component)

        # Extract methods within the class
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self._extract_function(child, file_path, parent_class=node.name)

    def _extract_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef, file_path: Path, parent_class: Optional[str] = None) -> None:
        """Extract function/method definition details."""
        docstring = ast.get_docstring(node)
        parameters = self._extract_parameters(node)
        return_type = self._get_annotation(node.returns) if node.returns else None
        decorators = [self._get_name(dec) for dec in node.decorator_list]

        func_type = 'method' if parent_class else 'function'
        func_name = f"{parent_class}.{node.name}" if parent_class else node.name

        func_component = Component(
            name=func_name,
            type=func_type,
            file_path=str(file_path),
            line_number=node.lineno,
            docstring=docstring,
            parameters=parameters,
            return_type=return_type,
            decorators=decorators
        )
        self.components.append(func_component)

    def _extract_parameters(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> List[Dict[str, str]]:
        """Extract function parameters with type hints."""
        params = []
        for arg in node.args.args:
            param_info = {
                'name': arg.arg,
                'type': self._get_annotation(arg.annotation) if arg.annotation else 'Any'
            }
            params.append(param_info)

        # Handle *args
        if node.args.vararg:
            params.append({
                'name': f"*{node.args.vararg.arg}",
                'type': self._get_annotation(node.args.vararg.annotation) if node.args.vararg.annotation else 'Tuple[Any, ...]'
            })

        # Handle **kwargs
        if node.args.kwarg:
            params.append({
                'name': f"**{node.args.kwarg.arg}",
                'type': self._get_annotation(node.args.kwarg.annotation) if node.args.kwarg.annotation else 'Dict[str, Any]'
            })

        # Handle keyword-only args
        for arg in node.args.kwonlyargs:
            params.append({
                'name': arg.arg,
                'type': self._get_annotation(arg.annotation) if arg.annotation else 'Any',
                'keyword_only': True
            })

        return params

    def _get_annotation(self, node: Optional[ast.AST]) -> Optional[str]:
        """Convert AST annotation node to string representation."""
        if node is None:
            return None
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return f"{self._get_annotation(node.value)}.{node.attr}"
        elif isinstance(node, ast.Subscript):
            return f"{self._get_annotation(node.value)}[{self._get_annotation(node.slice)}]"
        elif isinstance(node, ast.Constant):
            return str(node.value)
        elif isinstance(node, ast.Tuple):
            elements = [self._get_annotation(el) for el in node.elts]
            return f"Tuple[{', '.join(elements)}]"
        elif isinstance(node, ast.List):
            elements = [self._get_annotation(el) for el in node.elts]
            return f"List[{', '.join(elements)}]"
        elif isinstance(node, ast.BinOp):
            left = self._get_annotation(node.left)
            right = self._get_annotation(node.right)
            op = ast.dump(node.op)
            return f"{left} {op} {right}"
        elif isinstance(node, ast.Call):
            func_name = self._get_annotation(node.func)
            args = [self._get_annotation(arg) for arg in node.args]
            return f"{func_name}({', '.join(args)})"
        else:
            return ast.dump(node)

    def _get_name(self, node: ast.AST) -> str:
        """Extract name from a decorator or base class node."""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return f"{self._get_name(node.value)}.{node.attr}"
        elif isinstance(node, ast.Call):
            return self._get_name(node.func)
        else:
            return ast.dump(node)