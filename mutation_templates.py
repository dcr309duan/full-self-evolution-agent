import ast
import astor

def wrap_in_try_except(source: str) -> str:
    """
    Template 1: Wrap the entire function body in a try-except block.
    The except clause catches Exception and re-raises it after logging.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return source  # Return unchanged if parsing fails

    class TryExceptWrapper(ast.NodeTransformer):
        def visit_FunctionDef(self, node):
            # Wrap the existing body in a try-except
            try_body = node.body
            except_handler = ast.ExceptHandler(
                type=ast.Name(id='Exception', ctx=ast.Load()),
                name='e',
                body=[
                    ast.Expr(
                        value=ast.Call(
                            func=ast.Attribute(
                                value=ast.Name(id='print', ctx=ast.Load()),
                                attr='__call__'
                            ),
                            args=[ast.Constant(value='Exception caught in function')],
                            keywords=[]
                        )
                    ),
                    ast.Raise(
                        exc=ast.Call(
                            func=ast.Name(id='e', ctx=ast.Load()),
                            args=[],
                            keywords=[]
                        ),
                        cause=None
                    )
                ]
            )
            node.body = [
                ast.Try(
                    body=try_body,
                    handlers=[except_handler],
                    orelse=[],
                    finalbody=[]
                )
            ]
            return node

    transformer = TryExceptWrapper()
    new_tree = transformer.visit(tree)
    return astor.to_source(new_tree)


def add_entry_logging(source: str) -> str:
    """
    Template 2: Add a logging call at the beginning of the function body.
    Uses print for simplicity; can be replaced with logging module.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return source

    class LoggingAdder(ast.NodeTransformer):
        def visit_FunctionDef(self, node):
            # Prepend a print statement with function name
            log_stmt = ast.Expr(
                value=ast.Call(
                    func=ast.Name(id='print', ctx=ast.Load()),
                    args=[ast.Constant(value=f"Entering function: {node.name}")],
                    keywords=[]
                )
            )
            node.body.insert(0, log_stmt)
            return node

    transformer = LoggingAdder()
    new_tree = transformer.visit(tree)
    return astor.to_source(new_tree)


def replace_constant_with_parameter(source: str, constant_value: object = None) -> str:
    """
    Template 3: Replace the first occurrence of a constant (e.g., a numeric literal)
    in the function body with a new parameter. The constant_value can be specified;
    if None, the first numeric constant found is used.
    Returns modified source with the constant replaced by a parameter named 'param'.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return source

    class ConstantReplacer(ast.NodeTransformer):
        def __init__(self, target_value):
            self.target_value = target_value
            self.found = False

        def visit_FunctionDef(self, node):
            # Add a new parameter 'param' to the function
            new_arg = ast.arg(arg='param', annotation=None)
            node.args.args.append(new_arg)
            # Now visit the body to replace the constant
            self.generic_visit(node)
            return node

        def visit_Constant(self, node):
            if not self.found and node.value == self.target_value:
                self.found = True
                return ast.Name(id='param', ctx=ast.Load())
            return node

    # Find the first numeric constant in the source to use as target
    # This is a simplistic approach; for production, more robust detection needed.
    # For now, we assume the user provides constant_value or we use a default.
    if constant_value is None:
        # Try to extract first numeric constant from source
        temp_tree = ast.parse(source)
        for node in ast.walk(temp_tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
                constant_value = node.value
                break
        if constant_value is None:
            return source  # No numeric constant found

    transformer = ConstantReplacer(constant_value)
    new_tree = transformer.visit(tree)
    return astor.to_source(new_tree)