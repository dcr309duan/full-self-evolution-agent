from typing import List, Optional, Dict, Any
import ast
import random

class SimplerMutationGenerator:
    """Fallback mutation generator that produces simpler alternatives when mutations are rejected.
    
    Generates mutations that:
    - Modify only single files
    - Keep cyclomatic complexity < 5
    - Avoid import-heavy patterns
    - Prefer [ECOLOGY] pattern mutations (test expectation changes over implementation)
    """
    
    def __init__(self, max_cyclomatic_complexity: int = 5):
        self.max_cyclomatic_complexity = max_cyclomatic_complexity
        self._ecolocy_patterns = [
            self._modify_test_assertion,
            self._modify_test_expected_value,
            self._modify_test_condition,
            self._swap_comparison_operator,
            self._negate_boolean_literal,
        ]
        self._implementation_patterns = [
            self._simplify_arithmetic,
            self._simplify_condition,
            self._remove_unused_variable,
            self._inline_simple_function,
        ]
    
    def generate_mutations(self, source_code: str, file_path: str) -> List[Dict[str, Any]]:
        """Generate simpler mutations for the given source code.
        
        Args:
            source_code: The source code to mutate
            file_path: Path to the source file
            
        Returns:
            List of mutation dictionaries with 'code' and 'type' keys
        """
        mutations = []
        
        # Try ECOLOGY patterns first (test expectation changes)
        ecology_mutations = self._apply_ecology_patterns(source_code, file_path)
        mutations.extend(ecology_mutations)
        
        # If no ecology mutations found, fall back to implementation patterns
        if not ecology_mutations:
            impl_mutations = self._apply_implementation_patterns(source_code, file_path)
            mutations.extend(impl_mutations)
        
        return mutations
    
    def _apply_ecology_patterns(self, source_code: str, file_path: str) -> List[Dict[str, Any]]:
        """Apply ECOLOGY pattern mutations that modify test expectations."""
        mutations = []
        
        try:
            tree = ast.parse(source_code)
        except SyntaxError:
            return mutations
        
        for node in ast.walk(tree):
            for pattern in self._ecolocy_patterns:
                try:
                    result = pattern(node, source_code, file_path)
                    if result and self._is_simple_mutation(result):
                        mutations.append(result)
                except Exception:
                    continue
        
        return mutations
    
    def _apply_implementation_patterns(self, source_code: str, file_path: str) -> List[Dict[str, Any]]:
        """Apply implementation pattern mutations as fallback."""
        mutations = []
        
        try:
            tree = ast.parse(source_code)
        except SyntaxError:
            return mutations
        
        for node in ast.walk(tree):
            for pattern in self._implementation_patterns:
                try:
                    result = pattern(node, source_code, file_path)
                    if result and self._is_simple_mutation(result):
                        mutations.append(result)
                except Exception:
                    continue
        
        return mutations
    
    def _modify_test_assertion(self, node: ast.AST, source_code: str, file_path: str) -> Optional[Dict[str, Any]]:
        """Modify a test assertion (e.g., assertEqual -> assertNotEqual)."""
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            func_name = node.func.attr.lower()
            if 'assert' in func_name and 'equal' in func_name:
                # Swap assertEqual with assertNotEqual or vice versa
                if 'not' in func_name:
                    new_func_name = func_name.replace('not', '')
                else:
                    new_func_name = func_name.replace('equal', 'notequal')
                
                new_code = source_code[:node.col_offset] + \
                           f"self.{new_func_name}(" + \
                           source_code[node.col_offset + len(func_name) + 5:]
                
                return {
                    'code': new_code,
                    'type': 'assertion_modification',
                    'file': file_path,
                    'complexity': 1
                }
        return None
    
    def _modify_test_expected_value(self, node: ast.AST, source_code: str, file_path: str) -> Optional[Dict[str, Any]]:
        """Modify expected value in test assertions."""
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            func_name = node.func.attr.lower()
            if 'assert' in func_name and len(node.args) >= 2:
                # Modify the expected value (second argument)
                expected_arg = node.args[1]
                if isinstance(expected_arg, ast.Constant):
                    if isinstance(expected_arg.value, (int, float)):
                        new_value = expected_arg.value + 1
                        new_code = source_code[:expected_arg.col_offset] + \
                                   str(new_value) + \
                                   source_code[expected_arg.end_col_offset:]
                        return {
                            'code': new_code,
                            'type': 'expected_value_modification',
                            'file': file_path,
                            'complexity': 1
                        }
                    elif isinstance(expected_arg.value, bool):
                        new_value = not expected_arg.value
                        new_code = source_code[:expected_arg.col_offset] + \
                                   str(new_value) + \
                                   source_code[expected_arg.end_col_offset:]
                        return {
                            'code': new_code,
                            'type': 'expected_value_modification',
                            'file': file_path,
                            'complexity': 1
                        }
        return None
    
    def _modify_test_condition(self, node: ast.AST, source_code: str, file_path: str) -> Optional[Dict[str, Any]]:
        """Modify condition in test assertions."""
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            func_name = node.func.attr.lower()
            if 'assert' in func_name and 'true' in func_name:
                new_code = source_code[:node.col_offset] + \
                           source_code[node.col_offset:].replace('assertTrue', 'assertFalse', 1)
                return {
                    'code': new_code,
                    'type': 'condition_modification',
                    'file': file_path,
                    'complexity': 1
                }
            elif 'assert' in func_name and 'false' in func_name:
                new_code = source_code[:node.col_offset] + \
                           source_code[node.col_offset:].replace('assertFalse', 'assertTrue', 1)
                return {
                    'code': new_code,
                    'type': 'condition_modification',
                    'file': file_path,
                    'complexity': 1
                }
        return None
    
    def _swap_comparison_operator(self, node: ast.AST, source_code: str, file_path: str) -> Optional[Dict[str, Any]]:
        """Swap comparison operators (e.g., == -> !=, < -> >)."""
        if isinstance(node, ast.Compare):
            if len(node.ops) == 1:
                op = node.ops[0]
                if isinstance(op, ast.Eq):
                    new_op = '!='
                elif isinstance(op, ast.NotEq):
                    new_op = '=='
                elif isinstance(op, ast.Lt):
                    new_op = '>'
                elif isinstance(op, ast.Gt):
                    new_op = '<'
                elif isinstance(op, ast.LtE):
                    new_op = '>='
                elif isinstance(op, ast.GtE):
                    new_op = '<='
                else:
                    return None
                
                # Find the operator position in source
                op_start = node.ops[0].col_offset
                op_end = node.ops[0].end_col_offset
                new_code = source_code[:op_start] + new_op + source_code[op_end:]
                return {
                    'code': new_code,
                    'type': 'comparison_swap',
                    'file': file_path,
                    'complexity': 1
                }
        return None
    
    def _negate_boolean_literal(self, node: ast.AST, source_code: str, file_path: str) -> Optional[Dict[str, Any]]:
        """Negate boolean literals (True -> False, False -> True)."""
        if isinstance(node, ast.Constant) and isinstance(node.value, bool):
            new_value = not node.value
            new_code = source_code[:node.col_offset] + \
                       str(new_value) + \
                       source_code[node.end_col_offset:]
            return {
                'code': new_code,
                'type': 'boolean_negation',
                'file': file_path,
                'complexity': 1
            }
        return None
    
    def _simplify_arithmetic(self, node: ast.AST, source_code: str, file_path: str) -> Optional[Dict[str, Any]]:
        """Simplify arithmetic expressions."""
        if isinstance(node, ast.BinOp):
            if isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)):
                if isinstance(node.left, ast.Constant) and isinstance(node.right, ast.Constant):
                    try:
                        if isinstance(node.op, ast.Add):
                            result = node.left.value + node.right.value
                        elif isinstance(node.op, ast.Sub):
                            result = node.left.value - node.right.value
                        elif isinstance(node.op, ast.Mult):
                            result = node.left.value * node.right.value
                        elif isinstance(node.op, ast.Div):
                            result = node.left.value / node.right.value
                        else:
                            return None
                        
                        new_code = source_code[:node.col_offset] + \
                                   str(result) + \
                                   source_code[node.end_col_offset:]
                        return {
                            'code': new_code,
                            'type': 'arithmetic_simplification',
                            'file': file_path,
                            'complexity': 1
                        }
                    except (ZeroDivisionError, TypeError):
                        return None
        return None
    
    def _simplify_condition(self, node: ast.AST, source_code: str, file_path: str) -> Optional[Dict[str, Any]]:
        """Simplify boolean conditions."""
        if isinstance(node, ast.BoolOp):
            if len(node.values) == 2:
                left = node.values[0]
                right = node.values[1]
                if isinstance(left, ast.Constant) and isinstance(left.value, bool):
                    if isinstance(node.op, ast.And):
                        if left.value:
                            new_code = source_code[:right.col_offset] + \
                                       source_code[right.col_offset:right.end_col_offset] + \
                                       source_code[right.end_col_offset:]
                            return {
                                'code': new_code,
                                'type': 'condition_simplification',
                                'file': file_path,
                                'complexity': 1
                            }
                        else:
                            new_code = source_code[:left.col_offset] + \
                                       'False' + \
                                       source_code[left.end_col_offset:]
                            return {
                                'code': new_code,
                                'type': 'condition_simplification',
                                'file': file_path,
                                'complexity': 1
                            }
                    elif isinstance(node.op, ast.Or):
                        if left.value:
                            new_code = source_code[:left.col_offset] + \
                                       'True' + \
                                       source_code[left.end_col_offset:]
                            return {
                                'code': new_code,
                                'type': 'condition_simplification',
                                'file': file_path,
                                'complexity': 1
                            }
                        else:
                            new_code = source_code[:right.col_offset] + \
                                       source_code[right.col_offset:right.end_col_offset] + \
                                       source_code[right.end_col_offset:]
                            return {
                                'code': new_code,
                                'type': 'condition_simplification',
                                'file': file_path,
                                'complexity': 1
                            }
        return None
    
    def _remove_unused_variable(self, node: ast.AST, source_code: str, file_path: str) -> Optional[Dict[str, Any]]:
        """Remove unused variable assignments."""
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            if isinstance(target, ast.Name):
                # Check if variable is used elsewhere (simple check)
                var_name = target.id
                if not var_name.startswith('_') and not var_name.startswith('self.'):
                    # Simple heuristic: remove assignment if value is simple
                    if isinstance(node.value, (ast.Constant, ast.Name)):
                        new_code = source_code[:node.col_offset] + \
                                   source_code[node.end_col_offset:]
                        return {
                            'code': new_code,
                            'type': 'variable_removal',
                            'file': file_path,
                            'complexity': 1
                        }
        return None
    
    def _inline_simple_function(self, node: ast.AST, source_code: str, file_path: str) -> Optional[Dict[str, Any]]:
        """Inline simple function calls."""
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            # Only inline functions with simple names (no attribute access)
            if len(node.args) == 1:
                arg = node.args[0]
                if isinstance(arg, ast.Constant):
                    # Simple inlining: replace call with argument
                    new_code = source_code[:node.col_offset] + \
                               source_code[arg.col_offset:arg.end_col_offset] + \
                               source_code[node.end_col_offset:]
                    return {
                        'code': new_code,
                        'type': 'function_inlining',
                        'file': file_path,
                        'complexity': 1
                    }
        return None
    
    def _is_simple_mutation(self, mutation: Dict[str, Any]) -> bool:
        """Check if mutation is simple enough (low complexity, single file)."""
        if mutation.get('complexity', 0) >= self.max_cyclomatic_complexity:
            return False
        if mutation.get('file') is None:
            return False
        return True
    
    def get_available_patterns(self) -> List[str]:
        """Return list of available mutation patterns."""
        return [
            'modify_test_assertion',
            'modify_test_expected_value',
            'modify_test_condition',
            'swap_comparison_operator',
            'negate_boolean_literal',
            'simplify_arithmetic',
            'simplify_condition',
            'remove_unused_variable',
            'inline_simple_function',
        ]