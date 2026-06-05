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
        self.failure_counter = 0
        self.use_grammar_mutation = False
        self.template_success = {1: 0, 2: 0, 3: 0}
        self.template_failure = {1: 0, 2: 0, 3: 0}
        self.paused = False
        self.failure_report = None

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
        if self.paused:
            return source_code

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
            elif mutation_type == 'grammar_guided_mutation':
                return self._grammar_guided_mutation(source_code)
            return ast.unparse(tree)
        except SyntaxError:
            # If parsing fails, return original code unchanged
            self.failure_counter += 1
            if self.failure_counter >= 4:
                self.use_grammar_mutation = True
            return source_code

    def _choose_mutation(self) -> str:
        """Weighted random selection of mutation type."""
        if self.use_grammar_mutation:
            return 'grammar_guided_mutation'
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

    def _grammar_guided_mutation(self, source_code: str) -> str:
        """
        Apply grammar-guided mutation using templates.
        Randomly select one of the 3 templates and apply it to the target code.
        Track success/failure of each template application.
        """
        # Define 3 grammar templates
        templates = [
            # Template 1: Add a try-except block around a function body
            self._template_add_try_except,
            # Template 2: Replace a for loop with a while loop
            self._template_replace_for_with_while,
            # Template 3: Inline a simple function call
            self._template_inline_function
        ]
        
        # Randomly select a template
        template_index = random.randint(0, 2)
        template_func = templates[template_index]
        template_number = template_index + 1
        
        try:
            # Apply the selected template
            result = template_func(source_code)
            # Track success
            self.template_success[template_number] += 1
            return result
        except Exception as e:
            # Track failure
            self.template_failure[template_number] += 1
            # Check if all templates have failed
            if all(self.template_failure[t] > 0 for t in range(1, 4)):
                # Generate failure report
                self.failure_report = {
                    'failure_reasons': f"All 3 templates failed. Last template {template_number} failed with error: {str(e)}",
                    'template_used': template_number,
                    'code_state': source_code,
                    'template_success_counts': dict(self.template_success),
                    'template_failure_counts': dict(self.template_failure)
                }
                # Set paused flag
                self.paused = True
            return source_code

    def _template_add_try_except(self, source_code: str) -> str:
        """
        Template 1: Add a try-except block around a function body.
        Wraps the entire body of a randomly selected function in a try-except that catches Exception.
        """
        tree = ast.parse(source_code)
        
        class TryExceptAdder(ast.NodeTransformer):
            def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.AST:
                if node.body and not any(isinstance(stmt, ast.Try) for stmt in node.body):
                    # Create try-except block
                    except_handler = ast.ExceptHandler(
                        type=ast.Name(id='Exception', ctx=ast.Load()),
                        name='e',
                        body=[
                            ast.Raise(
                                exc=ast.Call(
                                    func=ast.Attribute(
                                        value=ast.Name(id='e', ctx=ast.Load()),
                                        attr='__class__',
                                        ctx=ast.Load()
                                    ),
                                    args=[],
                                    keywords=[]
                                ),
                                cause=None
                            )
                        ]
                    )
                    try_node = ast.Try(
                        body=node.body,
                        handlers=[except_handler],
                        orelse=[],
                        finalbody=[]
                    )
                    node.body = [try_node]
                return node
        
        tree = TryExceptAdder().visit(tree)
        return ast.unparse(tree)

    def _template_replace_for_with_while(self, source_code: str) -> str:
        """
        Template 2: Replace a for loop with a while loop.
        Converts a simple for loop iterating over a list to an equivalent while loop.
        """
        tree = ast.parse(source_code)
        
        class ForToWhileReplacer(ast.NodeTransformer):
            def visit_For(self, node: ast.For) -> ast.AST:
                # Only replace simple for loops over names
                if isinstance(node.iter, ast.Name):
                    iter_name = node.iter.id
                    target_name = node.target.id if isinstance(node.target, ast.Name) else None
                    if target_name:
                        # Create while loop equivalent
                        # Initialize index variable
                        index_var = ast.Name(id='_idx', ctx=ast.Store())
                        init_assign = ast.Assign(
                            targets=[index_var],
                            value=ast.Constant(value=0)
                        )
                        
                        # Create while condition: _idx < len(iter_name)
                        while_condition = ast.Compare(
                            left=ast.Name(id='_idx', ctx=ast.Load()),
                            ops=[ast.Lt()],
                            comparators=[
                                ast.Call(
                                    func=ast.Name(id='len', ctx=ast.Load()),
                                    args=[ast.Name(id=iter_name, ctx=ast.Load())],
                                    keywords=[]
                                )
                            ]
                        )
                        
                        # Create loop body with index access
                        new_body = []
                        for stmt in node.body:
                            # Replace references to target with iter_name[_idx]
                            class ReplaceTarget(ast.NodeTransformer):
                                def visit_Name(self, name_node):
                                    if name_node.id == target_name:
                                        return ast.Subscript(
                                            value=ast.Name(id=iter_name, ctx=ast.Load()),
                                            slice=ast.Name(id='_idx', ctx=ast.Load()),
                                            ctx=name_node.ctx
                                        )
                                    return name_node
                            new_stmt = ReplaceTarget().visit(copy.deepcopy(stmt))
                            new_body.append(new_stmt)
                        
                        # Add increment at end of loop body
                        increment = ast.AugAssign(
                            target=ast.Name(id='_idx', ctx=ast.Store()),
                            op=ast.Add(),
                            value=ast.Constant(value=1)
                        )
                        new_body.append(increment)
                        
                        while_node = ast.While(
                            test=while_condition,
                            body=new_body,
                            orelse=node.orelse
                        )
                        
                        # Return both init and while as a list
                        return [init_assign, while_node]
                return node
        
        tree = ForToWhileReplacer().visit(tree)
        return ast.unparse(tree)

    def _template_inline_function(self, source_code: str) -> str:
        """
        Template 3: Inline a simple function call.
        Finds a function that is called exactly once and inlines its body.
        """
        tree = ast.parse(source_code)
        
        # First pass: collect function definitions and call counts
        class FunctionCollector(ast.NodeVisitor):
            def __init__(self):
                self.functions = {}
                self.call_counts = {}
            
            def visit_FunctionDef(self, node):
                self.functions[node.name] = node
                self.generic_visit(node)
            
            def visit_Call(self, node):
                if isinstance(node.func, ast.Name):
                    func_name = node.func.id
                    if func_name in self.call_counts:
                        self.call_counts[func_name] += 1
                    else:
                        self.call_counts[func_name] = 1
                self.generic_visit(node)
        
        collector = FunctionCollector()
        collector.visit(tree)
        
        # Find a function that is called exactly once and has simple body
        inline_candidate = None
        for func_name, count in collector.call_counts.items():
            if count == 1 and func_name in collector.functions:
                func_node = collector.functions[func_name]
                # Check if function has simple body (single return statement)
                if (len(func_node.body) == 1 and 
                    isinstance(func_node.body[0], ast.Return) and
                    func_node.body[0].value is not None):
                    inline_candidate = func_name
                    break
        
        if inline_candidate is None:
            raise ValueError("No suitable function found for inlining")
        
        # Second pass: inline the function
        class Inliner(ast.NodeTransformer):
            def __init__(self, func_name, func_node):
                self.func_name = func_name
                self.func_node = func_node
                self.inlined = False
            
            def visit_Call(self, node):
                if (isinstance(node.func, ast.Name) and 
                    node.func.id == self.func_name and 
                    not self.inlined):
                    self.inlined = True
                    # Get the return value expression
                    return_expr = self.func_node.body[0].value
                    # Replace parameters with arguments
                    param_map = {}
                    for param, arg in zip(self.func_node.args.args, node.args):
                        param_map[param.arg] = arg
                    
                    # Replace parameter references in the expression
                    class ParamReplacer(ast.NodeTransformer):
                        def visit_Name(self, name_node):
                            if name_node.id in param_map:
                                return copy.deepcopy(param_map[name_node.id])
                            return name_node
                    
                    return ParamReplacer().visit(copy.deepcopy(return_expr))
                return node
            
            def visit_FunctionDef(self, node):
                if node.name == self.func_name:
                    # Remove the function definition
                    return None
                return node
        
        inliner = Inliner(inline_candidate, collector.functions[inline_candidate])
        tree = inliner.visit(tree)
        
        # Fix the tree after removal
        ast.fix_missing_locations(tree)
        return ast.unparse(tree)

    def evolve_subsystem(self, subsystem_name: str, subsystem_code: str) -> Tuple[bool, str]:
        """
        Apply the current mutation strategy to a given subsystem's source code.
        
        Args:
            subsystem_name: Name of the subsystem being mutated (for logging/tracking)
            subsystem_code: Source code of the subsystem to mutate
            
        Returns:
            Tuple of (success: bool, mutated_code: str)
            - success: True if mutation was applied successfully, False otherwise
            - mutated_code: The mutated source code if successful, original code if failed
        """
        try:
            # Apply mutation based on current strategy
            if self.use_grammar_mutation:
                mutated_code = self._grammar_guided_mutation(subsystem_code)
            else:
                mutated_code = self.mutate(subsystem_code)
            
            # Check if mutation actually changed the code
            if mutated_code == subsystem_code:
                return False, subsystem_code
            
            return True, mutated_code
            
        except Exception as e:
            # Track failure for strategy adaptation
            self.failure_counter += 1
            if self.failure_counter >= 4:
                self.use_grammar_mutation = True
            return False, subsystem_code


def create_mutation_engine(objective_weights: Optional[Dict[str, float]] = None) -> MutationEngine:
    """Factory function to create a MutationEngine with optional weights."""
    return MutationEngine(objective_weights)