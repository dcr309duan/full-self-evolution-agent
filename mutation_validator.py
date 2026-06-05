import ast
import sys
from typing import Tuple, Dict, Any, List, Set

class TypeValidator(ast.NodeVisitor):
    """AST visitor that validates types, variable references, and function calls."""
    
    def __init__(self, known_variables: Dict[str, Any]):
        self.symbol_table = dict(known_variables)
        self.errors: List[str] = []
        self.defined_functions: Set[str] = set()
        self.current_function = None
        
    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Visit function definitions and add them to defined functions."""
        self.defined_functions.add(node.name)
        old_function = self.current_function
        self.current_function = node.name
        
        # Add function parameters to symbol table
        for arg in node.args.args:
            self.symbol_table[arg.arg] = 'any'
        
        # Visit function body
        self.generic_visit(node)
        
        self.current_function = old_function
        
    def visit_Name(self, node: ast.Name) -> None:
        """Check for undefined variable references."""
        if isinstance(node.ctx, ast.Load):
            if node.id not in self.symbol_table and node.id not in self.defined_functions:
                self.errors.append(f"Undefined variable '{node.id}' at line {node.lineno}")
        self.generic_visit(node)
        
    def visit_Call(self, node: ast.Call) -> None:
        """Check for calls to undefined functions."""
        if isinstance(node.func, ast.Name):
            if node.func.id not in self.defined_functions:
                self.errors.append(f"Call to undefined function '{node.func.id}' at line {node.lineno}")
        self.generic_visit(node)
        
    def visit_BinOp(self, node: ast.BinOp) -> None:
        """Check for type mismatches in binary operations."""
        left_type = self._get_type(node.left)
        right_type = self._get_type(node.right)
        
        if left_type and right_type and left_type != right_type:
            op_name = self._get_op_name(node.op)
            self.errors.append(
                f"Type mismatch in '{op_name}' operation at line {node.lineno}: "
                f"cannot operate on {left_type} and {right_type}"
            )
        self.generic_visit(node)
        
    def visit_UnaryOp(self, node: ast.UnaryOp) -> None:
        """Check for type mismatches in unary operations."""
        operand_type = self._get_type(node.operand)
        op_name = self._get_op_name(node.op)
        
        if operand_type and operand_type not in ('int', 'float', 'complex'):
            self.errors.append(
                f"Type mismatch in '{op_name}' operation at line {node.lineno}: "
                f"cannot apply to {operand_type}"
            )
        self.generic_visit(node)
        
    def visit_Assign(self, node: ast.Assign) -> None:
        """Add assigned variables to symbol table."""
        for target in node.targets:
            if isinstance(target, ast.Name):
                value_type = self._get_type(node.value)
                if target.id in self.symbol_table:
                    existing_type = self.symbol_table[target.id]
                    if existing_type != value_type and value_type:
                        self.errors.append(
                            f"Type mismatch at line {node.lineno}: "
                            f"variable '{target.id}' was {existing_type}, now assigned {value_type}"
                        )
                self.symbol_table[target.id] = value_type or 'any'
        self.generic_visit(node)
        
    def _get_type(self, node: ast.AST) -> str:
        """Infer the type of an AST node."""
        if isinstance(node, ast.Constant):
            if isinstance(node.value, int):
                return 'int'
            elif isinstance(node.value, float):
                return 'float'
            elif isinstance(node.value, str):
                return 'str'
            elif isinstance(node.value, bool):
                return 'bool'
            elif node.value is None:
                return 'NoneType'
            elif isinstance(node.value, complex):
                return 'complex'
            elif isinstance(node.value, bytes):
                return 'bytes'
        elif isinstance(node, ast.Name):
            if node.id in self.symbol_table:
                return self.symbol_table[node.id]
            return None
        elif isinstance(node, ast.List):
            return 'list'
        elif isinstance(node, ast.Tuple):
            return 'tuple'
        elif isinstance(node, ast.Dict):
            return 'dict'
        elif isinstance(node, ast.Set):
            return 'set'
        elif isinstance(node, ast.BinOp):
            left_type = self._get_type(node.left)
            right_type = self._get_type(node.right)
            if left_type and right_type:
                if left_type == right_type:
                    return left_type
                # Numeric type promotion
                if left_type in ('int', 'float', 'complex') and right_type in ('int', 'float', 'complex'):
                    if 'complex' in (left_type, right_type):
                        return 'complex'
                    if 'float' in (left_type, right_type):
                        return 'float'
                    return 'int'
            return None
        elif isinstance(node, ast.UnaryOp):
            return self._get_type(node.operand)
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                if node.func.id in self.defined_functions:
                    return 'any'  # We don't know return type of user functions
            return None
        return None
        
    def _get_op_name(self, op: ast.operator) -> str:
        """Get string representation of an operator."""
        op_map = {
            ast.Add: '+',
            ast.Sub: '-',
            ast.Mult: '*',
            ast.Div: '/',
            ast.FloorDiv: '//',
            ast.Mod: '%',
            ast.Pow: '**',
            ast.LShift: '<<',
            ast.RShift: '>>',
            ast.BitOr: '|',
            ast.BitXor: '^',
            ast.BitAnd: '&',
            ast.UAdd: '+',
            ast.USub: '-',
            ast.Not: 'not',
            ast.Invert: '~',
        }
        return op_map.get(type(op), str(op))


def validate_types(code_string: str, known_variables: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Validates types, variable references, and function calls in Python code.
    
    Args:
        code_string: A string containing Python code to validate.
        known_variables: A dictionary of variable names to their types.
        
    Returns:
        A tuple (is_valid, errors) where:
            - is_valid: True if no errors found, False otherwise.
            - errors: A list of error messages (empty if valid).
    """
    if not code_string or not code_string.strip():
        return True, []
    
    try:
        tree = ast.parse(code_string)
    except SyntaxError as e:
        return False, [f"SyntaxError: {e.msg}"]
    
    validator = TypeValidator(known_variables)
    validator.visit(tree)
    
    return len(validator.errors) == 0, validator.errors


def validate_syntax(code_string: str) -> Tuple[bool, str]:
    """
    Validates the syntax of a given Python code string using ast.parse().
    
    Args:
        code_string: A string containing Python code to validate.
        
    Returns:
        A tuple (is_valid, error_message) where:
            - is_valid: True if the code has no syntax errors, False otherwise.
            - error_message: An empty string if valid, or a descriptive error message if invalid.
    """
    # Handle empty or whitespace-only strings (valid Python is empty code)
    if not code_string or not code_string.strip():
        return True, ""
    
    # Handle non-string input gracefully (though type hint suggests str)
    if not isinstance(code_string, str):
        try:
            code_string = str(code_string)
        except Exception as e:
            return False, f"Input cannot be converted to string: {e}"
    
    try:
        # Attempt to parse the code
        ast.parse(code_string)
        return True, ""
    except SyntaxError as e:
        # Extract meaningful error details from SyntaxError
        error_msg = f"SyntaxError: {e.msg}"
        if e.lineno is not None:
            error_msg += f" at line {e.lineno}"
        if e.offset is not None:
            error_msg += f", column {e.offset}"
        if e.text:
            # Clean up the text (remove trailing newlines, limit length)
            text = e.text.rstrip('\n\r')
            if len(text) > 80:
                text = text[:77] + "..."
            error_msg += f": '{text}'"
        return False, error_msg
    except ValueError as e:
        # ast.parse can raise ValueError for some encoding issues in older Python versions
        return False, f"ValueError: {e}"
    except MemoryError:
        # Handle extremely large code strings that cause memory issues
        return False, "MemoryError: Code string too large to parse"
    except Exception as e:
        # Catch any other unexpected exceptions
        return False, f"Unexpected error: {type(e).__name__}: {e}"


class ValidationError(Exception):
    """Base error for mutation validation failures."""
    pass


class InterfaceError(ValidationError):
    """Raised when a mutation breaks a module interface."""
    pass


class TestError(ValidationError):
    """Raised when a mutation fails test execution."""
    pass


class MutationValidator:
    """Validates proposed mutations before they are applied.

    Combines syntax checking, type validation, and structural checks.
    """

    def __init__(self, known_variables=None):
        self.known_variables = known_variables or {}

    def validate(self, code: str) -> Tuple[bool, List[str]]:
        """Run all validation checks on a code string.

        Returns (is_valid, list_of_errors).
        """
        errors = []

        syntax_ok, syntax_err = validate_syntax(code)
        if not syntax_ok:
            errors.append(syntax_err)
            return False, errors

        types_ok, type_errors = validate_types(code, self.known_variables)
        if not types_ok:
            errors.extend(type_errors)

        return len(errors) == 0, errors

    def validate_mutation(self, original: str, mutated: str) -> Tuple[bool, List[str]]:
        """Validate a mutation by checking the mutated code is valid
        and structurally different from the original."""
        is_valid, errors = self.validate(mutated)
        if not is_valid:
            return False, errors

        if original.strip() == mutated.strip():
            return False, ["Mutation produced no change"]

        try:
            orig_tree = ast.parse(original)
            mut_tree = ast.parse(mutated)
            if ast.dump(orig_tree) == ast.dump(mut_tree):
                return False, ["AST is identical to original"]
        except SyntaxError:
            pass

        return True, []


def _test_validate_syntax():
    """Simple test function to demonstrate usage (not exported)."""
    test_cases = [
        ("", True, ""),
        ("   ", True, ""),
        ("x = 1", True, ""),
        ("def foo(): pass", True, ""),
        ("if True:", False, "SyntaxError"),
        ("x = 1\n", True, ""),
        ("import os\nprint(os.name)", True, ""),
        ("\x80abc", False, "SyntaxError"),  # Invalid UTF-8 byte sequence
        (None, False, "cannot be converted"),  # Non-string input
        (123, True, ""),  # Integer converted to string "123" is valid Python
        ("a = 1\nb = 2\nc = 3", True, ""),
        ("a = 1\n\nb = 2", True, ""),
        ("a = 1\n  indented", False, "SyntaxError"),
    ]
    
    for code, expected_valid, expected_error_substr in test_cases:
        is_valid, error_msg = validate_syntax(code)
        assert is_valid == expected_valid, f"Failed for {code!r}: expected valid={expected_valid}, got {is_valid}"
        if expected_error_substr:
            assert expected_error_substr in error_msg, f"Failed for {code!r}: expected error containing {expected_error_substr!r}, got {error_msg!r}"
        else:
            assert error_msg == "", f"Failed for {code!r}: expected empty error, got {error_msg!r}"
    print("All syntax tests passed.")


def _test_validate_types():
    """Test function for validate_types."""
    test_cases = [
        # (code, known_variables, expected_valid, expected_errors_substrings)
        ("x = 1", {}, True, []),
        ("x = y", {}, False, ["Undefined variable 'y'"]),
        ("x = 1 + 2", {}, True, []),
        ("x = 1 + 'hello'", {}, False, ["Type mismatch"]),
        ("def foo(): pass\nfoo()", {}, True, []),
        ("def foo(): pass\nbar()", {}, False, ["undefined function 'bar'"]),
        ("x = 1\nx = 'hello'", {}, False, ["Type mismatch"]),
        ("x = 1\nx + 'hello'", {}, False, ["Type mismatch"]),
        ("x = 1\n-x", {}, True, []),
        ("x = 'hello'\n-x", {}, False, ["Type mismatch"]),
        ("x = 1\nx = 2", {}, True, []),
        ("def foo(x): return x\nfoo(1)", {}, True, []),
        ("x = 1\ny = x + 2", {}, True, []),
        ("x = 1\ny = x + 'hello'", {}, False, ["Type mismatch"]),
    ]
    
    for code, known_vars, expected_valid, expected_errors in test_cases:
        is_valid, errors = validate_types(code, known_vars)
        assert is_valid == expected_valid, f"Failed for {code!r}: expected valid={expected_valid}, got {is_valid}"
        if expected_errors:
            for expected_error in expected_errors:
                found = any(expected_error in error for error in errors)
                assert found, f"Failed for {code!r}: expected error containing '{expected_error}', got {errors}"
        else:
            assert errors == [], f"Failed for {code!r}: expected no errors, got {errors}"
    print("All type validation tests passed.")


if __name__ == "__main__":
    _test_validate_syntax()
    _test_validate_types()