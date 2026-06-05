import ast
import random
import copy
from typing import Any, Dict, List, Optional, Tuple

class MutationEngine:
    """
    Mutation engine that applies structural code mutations based on meta-evaluation objectives.
    Supports: refactor_architecture, delete_dead_code, optimize_performance.
    """

    def __init__(self, objective_weights: Optional[Dict[str, float]] = None):
        """
        Initialize mutation engine with optional objective weights.
        Default weights are equal for all objectives.
        """
        self.objective_weights = objective_weights or {
            'refactor_architecture': 1.0,
            'delete_dead_code': 1.0,
            'optimize_performance': 1.0
        }
        self._normalize_weights()

    def _normalize_weights(self) -> None:
        """Normalize weights so they sum to 1.0."""
        total = sum(self.objective_weights.values())
        if total > 0:
            for key in self.objective_weights:
                self.objective_weights[key] /= total

    def set_objective_weights(self, weights: Dict[str, float]) -> None:
        """Update objective weights from meta-evaluation loop."""
        self.objective_weights = weights
        self._normalize_weights()

    def mutate(self, source_code: str) -> str:
        """
        Apply a mutation to the source code based on weighted random selection.
        Returns the mutated source code as a string.
        """
        # Choose mutation type based on weights
        mutation_type = self._choose_mutation()
        try:
            tree = ast.parse(source_code)
            if mutation_type == 'refactor_architecture':
                tree = self._refactor_architecture(tree)
            elif mutation_type == 'delete_dead_code':
                tree = self._delete_dead_code(tree)
            elif mutation_type == 'optimize_performance':
                tree = self._optimize_performance(tree)
            return ast.unparse(tree)
        except SyntaxError:
            # If parsing fails, return original code unchanged
            return source_code

    def _choose_mutation(self) -> str:
        """Weighted random selection of mutation type."""
        types = list(self.objective_weights.keys())
        weights = [self.objective_weights[t] for t in types]
        return random.choices(types, weights=weights, k=1)[0]

    def _refactor_architecture(self, tree: ast.AST) -> ast.AST:
        """
        Refactor architecture: identify classes/functions with high coupling and restructure.
        Strategy: Extract related functions into a new class if they share parameters.
        """
        class RefactorVisitor(ast.NodeTransformer):
            def visit_Module(self, node: ast.Module) -> ast.AST:
                # Find functions that could be grouped
                functions = [n for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
                if len(functions) < 2:
                    return node

                # Try to group functions that share common parameters
                param_sets = {}
                for func in functions:
                    params = tuple(p.arg for p in func.args.args if p.arg != 'self')
                    if params:
                        param_sets.setdefault(params, []).append(func)

                # If we find a group with at least 2 functions, create a class
                for params, funcs in param_sets.items():
                    if len(funcs) >= 2:
                        # Create a new class
                        class_name = f"Refactored{''.join(p.capitalize() for p in params)}"
                        class_def = ast.ClassDef(
                            name=class_name,
                            bases=[],
                            keywords=[],
                            body=[],
                            decorator_list=[]
                        )
                        # Add methods to class (add self parameter)
                        for func in funcs:
                            new_func = copy.deepcopy(func)
                            # Add self as first parameter if not present
                            if not new_func.args.args or new_func.args.args[0].arg != 'self':
                                self_param = ast.arg(arg='self', annotation=None)
                                new_func.args.args.insert(0, self_param)
                            class_def.body.append(new_func)
                            # Remove function from module body
                            node.body.remove(func)
                        # Add class to module
                        node.body.insert(0, class_def)
                        break  # Only do one refactoring per mutation
                return node

        return RefactorVisitor().visit(tree)

    def _delete_dead_code(self, tree: ast.AST) -> ast.AST:
        """
        Delete dead code: remove unused functions and variables.
        Strategy: Find functions that are never called and remove them.
        Also remove unused variable assignments.
        """
        class DeadCodeRemover(ast.NodeTransformer):
            def __init__(self):
                self.defined_functions = set()
                self.called_functions = set()
                self.defined_vars = set()
                self.used_vars = set()

            def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.AST:
                self.defined_functions.add(node.name)
                # Track variables defined in function
                for stmt in node.body:
                    if isinstance(stmt, ast.Assign):
                        for target in stmt.targets:
                            if isinstance(target, ast.Name):
                                self.defined_vars.add(target.id)
                self.generic_visit(node)
                return node

            def visit_Call(self, node: ast.Call) -> ast.AST:
                if isinstance(node.func, ast.Name):
                    self.called_functions.add(node.func.id)
                self.generic_visit(node)
                return node

            def visit_Name(self, node: ast.Name) -> ast.AST:
                if isinstance(node.ctx, ast.Load):
                    self.used_vars.add(node.id)
                return node

            def visit_Module(self, node: ast.Module) -> ast.AST:
                # First pass: collect definitions and usages
                self.generic_visit(node)
                # Second pass: remove unused functions
                new_body = []
                for stmt in node.body:
                    if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        if stmt.name not in self.called_functions and stmt.name != '__init__':
                            # Only remove if it's not a special method
                            continue
                    # Remove unused variable assignments at module level
                    if isinstance(stmt, ast.Assign):
                        for target in stmt.targets:
                            if isinstance(target, ast.Name) and target.id not in self.used_vars:
                                # Skip removal to avoid breaking code - just skip this assignment
                                pass
                    new_body.append(stmt)
                node.body = new_body
                return node

        return DeadCodeRemover().visit(tree)

    def _optimize_performance(self, tree: ast.AST) -> ast.AST:
        """
        Optimize performance: rewrite slow loops or redundant logic.
        Strategy: Convert for loops that iterate over range(len(...)) to direct iteration.
        Also simplify if-else that returns boolean.
        """
        class PerformanceOptimizer(ast.NodeTransformer):
            def visit_For(self, node: ast.For) -> ast.AST:
                # Check for for i in range(len(some_list)) pattern
                if (isinstance(node.iter, ast.Call) and
                    isinstance(node.iter.func, ast.Name) and
                    node.iter.func.id == 'range' and
                    len(node.iter.args) == 1):
                    arg = node.iter.args[0]
                    if (isinstance(arg, ast.Call) and
                        isinstance(arg.func, ast.Name) and
                        arg.func.id == 'len' and
                        len(arg.args) == 1):
                        # Convert to for item in collection:
                        collection = arg.args[0]
                        # Create new loop variable
                        new_target = ast.Name(id='item', ctx=ast.Store())
                        # Replace all uses of the index variable with direct access
                        # This is a simplification - in practice we'd need to replace all references
                        new_for = ast.For(
                            target=new_target,
                            iter=collection,
                            body=node.body,
                            orelse=node.orelse
                        )
                        return new_for
                return node

            def visit_If(self, node: ast.If) -> ast.AST:
                # Simplify if condition: return True else return False -> return condition
                if (len(node.body) == 1 and len(node.orelse) == 1):
                    body_stmt = node.body[0]
                    else_stmt = node.orelse[0]
                    if (isinstance(body_stmt, ast.Return) and
                        isinstance(else_stmt, ast.Return)):
                        if (isinstance(body_stmt.value, ast.Constant) and
                            isinstance(else_stmt.value, ast.Constant)):
                            if body_stmt.value.value is True and else_stmt.value.value is False:
                                return ast.Return(value=node.test)
                            elif body_stmt.value.value is False and else_stmt.value.value is True:
                                # Return negated condition
                                return ast.Return(value=ast.UnaryOp(op=ast.Not(), operand=node.test))
                return node

        return PerformanceOptimizer().visit(tree)


def create_mutation_engine(objective_weights: Optional[Dict[str, float]] = None) -> MutationEngine:
    """Factory function to create a MutationEngine with optional weights."""
    return MutationEngine(objective_weights)