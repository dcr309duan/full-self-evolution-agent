import ast
import sys
from typing import Any, Dict, List, Optional, Set, Tuple

class SymbolTable:
    """Simple symbol table tracking variable and function definitions."""
    
    def __init__(self):
        self.variables: Dict[str, Set[str]] = {}  # name -> set of scopes
        self.functions: Dict[str, ast.FunctionDef] = {}
        self.classes: Dict[str, ast.ClassDef] = {}
        self.scope_stack: List[str] = []
    
    def enter_scope(self, scope_name: str) -> None:
        self.scope_stack.append(scope_name)
    
    def exit_scope(self) -> None:
        if self.scope_stack:
            self.scope_stack.pop()
    
    def current_scope(self) -> str:
        return '.'.join(self.scope_stack) if self.scope_stack else 'global'
    
    def add_variable(self, name: str) -> None:
        scope = self.current_scope()
        if name not in self.variables:
            self.variables[name] = set()
        self.variables[name].add(scope)
    
    def add_function(self, func_def: ast.FunctionDef) -> None:
        self.functions[func_def.name] = func_def
    
    def add_class(self, class_def: ast.ClassDef) -> None:
        self.classes[class_def.name] = class_def
    
    def is_variable_defined(self, name: str) -> bool:
        return name in self.variables
    
    def is_function_defined(self, name: str) -> bool:
        return name in self.functions
    
    def is_class_defined(self, name: str) -> bool:
        return name in self.classes


def validate_syntax(ast_tree: ast.AST) -> bool:
    """
    Validate that the AST tree is syntactically correct.
    Returns True if valid, False otherwise.
    """
    try:
        # If it's already an AST, we can check basic structure
        if not isinstance(ast_tree, ast.AST):
            return False
        
        # Verify it's a valid module or expression
        if not isinstance(ast_tree, (ast.Module, ast.Expression)):
            return False
        
        # Try to compile the AST to verify syntactic correctness
        try:
            compile(ast_tree, '<ast>', 'exec')
            return True
        except SyntaxError:
            return False
        except TypeError:
            # Some AST nodes might not be compilable directly
            return False
    except Exception:
        return False


def _build_symbol_table(ast_tree: ast.AST) -> SymbolTable:
    """Build a symbol table from the AST tree."""
    symbol_table = SymbolTable()
    
    class SymbolTableBuilder(ast.NodeVisitor):
        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            symbol_table.add_function(node)
            symbol_table.enter_scope(node.name)
            
            # Add function parameters as variables
            for arg in node.args.args:
                symbol_table.add_variable(arg.arg)
            
            # Visit function body
            self.generic_visit(node)
            symbol_table.exit_scope()
        
        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
            symbol_table.add_function(node)
            symbol_table.enter_scope(node.name)
            
            for arg in node.args.args:
                symbol_table.add_variable(arg.arg)
            
            self.generic_visit(node)
            symbol_table.exit_scope()
        
        def visit_ClassDef(self, node: ast.ClassDef) -> None:
            symbol_table.add_class(node)
            symbol_table.enter_scope(node.name)
            self.generic_visit(node)
            symbol_table.exit_scope()
        
        def visit_Name(self, node: ast.Name) -> None:
            if isinstance(node.ctx, ast.Store):
                symbol_table.add_variable(node.id)
            self.generic_visit(node)
        
        def visit_Assign(self, node: ast.Assign) -> None:
            for target in node.targets:
                if isinstance(target, ast.Name):
                    symbol_table.add_variable(target.id)
                elif isinstance(target, (ast.Tuple, ast.List)):
                    for elt in target.elts:
                        if isinstance(elt, ast.Name):
                            symbol_table.add_variable(elt.id)
            self.generic_visit(node)
        
        def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
            if isinstance(node.target, ast.Name):
                symbol_table.add_variable(node.target.id)
            self.generic_visit(node)
        
        def visit_For(self, node: ast.For) -> None:
            if isinstance(node.target, ast.Name):
                symbol_table.add_variable(node.target.id)
            elif isinstance(node.target, (ast.Tuple, ast.List)):
                for elt in node.target.elts:
                    if isinstance(elt, ast.Name):
                        symbol_table.add_variable(elt.id)
            self.generic_visit(node)
        
        def visit_With(self, node: ast.With) -> None:
            for item in node.items:
                if item.optional_vars and isinstance(item.optional_vars, ast.Name):
                    symbol_table.add_variable(item.optional_vars.id)
            self.generic_visit(node)
    
    builder = SymbolTableBuilder()
    builder.visit(ast_tree)
    return symbol_table


def check_type_consistency(ast_tree: ast.AST, symbol_table: Optional[SymbolTable] = None) -> bool:
    """
    Check type consistency by verifying variable/function usage matches definitions.
    Returns True if consistent, False otherwise.
    """
    if symbol_table is None:
        symbol_table = _build_symbol_table(ast_tree)
    
    class TypeConsistencyChecker(ast.NodeVisitor):
        def __init__(self):
            self.errors: List[str] = []
        
        def visit_Name(self, node: ast.Name) -> None:
            if isinstance(node.ctx, ast.Load):
                # Check if variable is defined
                if not symbol_table.is_variable_defined(node.id):
                    # Allow built-in names and common exceptions
                    builtins = {'True', 'False', 'None', 'print', 'len', 'range', 
                               'int', 'str', 'float', 'list', 'dict', 'set', 'tuple',
                               'type', 'isinstance', 'hasattr', 'getattr', 'setattr',
                               'open', 'input', 'super', 'object', 'property',
                               'staticmethod', 'classmethod', 'Exception', 'BaseException',
                               'ValueError', 'TypeError', 'KeyError', 'IndexError',
                               'AttributeError', 'ImportError', 'StopIteration',
                               'ArithmeticError', 'LookupError', 'OSError'}
                    if node.id not in builtins:
                        self.errors.append(f"Undefined variable '{node.id}' at line {node.lineno}")
            self.generic_visit(node)
        
        def visit_Call(self, node: ast.Call) -> None:
            if isinstance(node.func, ast.Name):
                func_name = node.func.id
                # Check if function is defined (allow built-ins)
                builtins = {'print', 'len', 'range', 'int', 'str', 'float', 'list', 
                           'dict', 'set', 'tuple', 'type', 'isinstance', 'hasattr',
                           'getattr', 'setattr', 'open', 'input', 'super', 'object',
                           'property', 'staticmethod', 'classmethod'}
                if func_name not in builtins and not symbol_table.is_function_defined(func_name):
                    # Could be a class or method call
                    if not symbol_table.is_class_defined(func_name):
                        self.errors.append(f"Undefined function '{func_name}' at line {node.lineno}")
            self.generic_visit(node)
        
        def visit_Attribute(self, node: ast.Attribute) -> None:
            # Allow attribute access (method calls, property access)
            self.generic_visit(node)
    
    checker = TypeConsistencyChecker()
    checker.visit(ast_tree)
    return len(checker.errors) == 0


def _compute_cyclomatic_complexity(ast_tree: ast.AST) -> int:
    """
    Compute cyclomatic complexity of the AST tree.
    M = E - N + 2P where:
    - E = number of edges
    - N = number of nodes
    - P = number of connected components (usually 1 for a single function/module)
    
    Simplified: Count decision points + 1
    """
    complexity = 1  # Base complexity
    
    class ComplexityVisitor(ast.NodeVisitor):
        def __init__(self):
            self.complexity = 1
        
        def visit_If(self, node: ast.If) -> None:
            self.complexity += 1
            self.generic_visit(node)
        
        def visit_While(self, node: ast.While) -> None:
            self.complexity += 1
            self.generic_visit(node)
        
        def visit_For(self, node: ast.For) -> None:
            self.complexity += 1
            self.generic_visit(node)
        
        def visit_AsyncFor(self, node: ast.AsyncFor) -> None:
            self.complexity += 1
            self.generic_visit(node)
        
        def visit_And(self, node: ast.And) -> None:
            self.complexity += len(node.values) - 1 if node.values else 0
            self.generic_visit(node)
        
        def visit_Or(self, node: ast.Or) -> None:
            self.complexity += len(node.values) - 1 if node.values else 0
            self.generic_visit(node)
        
        def visit_Try(self, node: ast.Try) -> None:
            # Each except handler adds complexity
            self.complexity += len(node.handlers)
            self.generic_visit(node)
        
        def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
            self.generic_visit(node)
        
        def visit_BoolOp(self, node: ast.BoolOp) -> None:
            # Boolean operators add complexity
            if isinstance(node.op, (ast.And, ast.Or)):
                self.complexity += len(node.values) - 1
            self.generic_visit(node)
        
        def visit_With(self, node: ast.With) -> None:
            # Context managers don't add complexity
            self.generic_visit(node)
        
        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            # Each function has its own complexity, but we're measuring the whole module
            self.generic_visit(node)
        
        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
            self.generic_visit(node)
        
        def visit_ClassDef(self, node: ast.ClassDef) -> None:
            self.generic_visit(node)
    
    visitor = ComplexityVisitor()
    visitor.visit(ast_tree)
    return visitor.complexity


def check_complexity(ast_tree: ast.AST, max_complexity: int = 10) -> bool:
    """
    Check if the cyclomatic complexity of the AST tree is within limits.
    Returns True if complexity <= max_complexity, False otherwise.
    """
    try:
        complexity = _compute_cyclomatic_complexity(ast_tree)
        return complexity <= max_complexity
    except Exception:
        return False


def validate_mutation(ast_tree: ast.AST, max_complexity: int = 10) -> bool:
    """
    Unified validation function that runs all checks:
    - Syntax validation
    - Type consistency
    - Complexity check
    
    Returns True if all checks pass, False otherwise.
    """
    try:
        # Check 1: Syntax validation
        if not validate_syntax(ast_tree):
            return False
        
        # Check 2: Type consistency
        if not check_type_consistency(ast_tree):
            return False
        
        # Check 3: Complexity check
        if not check_complexity(ast_tree, max_complexity):
            return False
        
        return True
    except Exception:
        return False


# Export public API
__all__ = [
    'validate_syntax',
    'check_type_consistency',
    'check_complexity',
    'validate_mutation',
    'SymbolTable',
]