import ast
import random
import sys
import os
import subprocess
import tempfile
from typing import List, Optional, Tuple

class TestMutator:
    """Mutates existing test files to create evolving environmental pressure."""

    MUTATION_TYPES = [
        "change_assertion",
        "add_edge_case",
        "modify_parameter",
        "swap_comparison",
        "negate_condition",
        "add_assertion",
        "change_boundary",
    ]

    def __init__(self, test_dir: str = "tests", seed: Optional[int] = None):
        self.test_dir = test_dir
        self.rng = random.Random(seed)

    def scan_test_files(self) -> List[str]:
        """Scan the test directory for Python test files."""
        test_files = []
        if not os.path.isdir(self.test_dir):
            return test_files
        for root, dirs, files in os.walk(self.test_dir):
            for f in files:
                if f.startswith("test_") and f.endswith(".py"):
                    test_files.append(os.path.join(root, f))
        return test_files

    def parse_test_file(self, filepath: str) -> ast.Module:
        """Parse a test file into an AST."""
        with open(filepath, "r") as f:
            source = f.read()
        return ast.parse(source)

    def mutate_assertion(self, node: ast.Assert) -> Optional[ast.Assert]:
        """Mutate an assertion node."""
        mutation = self.rng.choice(["change_value", "negate", "change_comparator"])
        if mutation == "change_value" and isinstance(node.test, ast.Compare):
            # Change the right-hand side value
            if isinstance(node.test.comparators[0], (ast.Constant, ast.Num)):
                old_val = node.test.comparators[0].value if isinstance(node.test.comparators[0], ast.Constant) else node.test.comparators[0].n
                if isinstance(old_val, (int, float)):
                    delta = self.rng.randint(1, max(1, int(abs(old_val) * 0.5)))
                    new_val = old_val + delta if self.rng.random() < 0.5 else old_val - delta
                    if isinstance(node.test.comparators[0], ast.Constant):
                        node.test.comparators[0].value = new_val
                    else:
                        node.test.comparators[0].n = new_val
                    return node
        elif mutation == "negate":
            node.test = ast.UnaryOp(op=ast.Not(), operand=node.test)
            return node
        elif mutation == "change_comparator" and isinstance(node.test, ast.Compare):
            ops = [ast.Eq(), ast.NotEq(), ast.Lt(), ast.Gt(), ast.LtE(), ast.GtE()]
            current_op = type(node.test.ops[0])
            new_ops = [op for op in ops if type(op) != current_op]
            node.test.ops[0] = self.rng.choice(new_ops)
            return node
        return None

    def add_edge_case(self, source: str) -> str:
        """Add an edge case test to the source."""
        # Simple edge case: add a test for zero, empty, or None
        edge_cases = [
            "\ndef test_edge_case_zero():\n    assert 0 == 0\n",
            "\ndef test_edge_case_empty():\n    assert [] == []\n",
            "\ndef test_edge_case_none():\n    assert None is None\n",
            "\ndef test_edge_case_boundary():\n    assert 1 == 1  # boundary check\n",
        ]
        edge_case = self.rng.choice(edge_cases)
        # Insert before the last line or at the end
        lines = source.split("\n")
        insert_pos = max(0, len(lines) - 1)
        lines.insert(insert_pos, edge_case)
        return "\n".join(lines)

    def modify_parameter(self, source: str) -> str:
        """Modify a parameter in a test function call."""
        tree = ast.parse(source)
        modified = False
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                for i, arg in enumerate(node.args):
                    if isinstance(arg, (ast.Constant, ast.Num)):
                        old_val = arg.value if isinstance(arg, ast.Constant) else arg.n
                        if isinstance(old_val, (int, float)):
                            delta = self.rng.randint(1, max(1, int(abs(old_val) * 0.3)))
                            new_val = old_val + delta if self.rng.random() < 0.5 else old_val - delta
                            if isinstance(arg, ast.Constant):
                                arg.value = new_val
                            else:
                                arg.n = new_val
                            modified = True
                            break
                if modified:
                    break
        if modified:
            return ast.unparse(tree)
        return source

    def mutate_test_file(self, filepath: str) -> Tuple[Optional[str], str]:
        """Apply a random mutation to a test file. Returns (original_source, mutated_source)."""
        with open(filepath, "r") as f:
            original_source = f.read()
        mutated_source = original_source

        mutation_type = self.rng.choice(self.MUTATION_TYPES)
        try:
            tree = ast.parse(original_source)
            if mutation_type == "change_assertion":
                # Find and mutate an assertion
                for node in ast.walk(tree):
                    if isinstance(node, ast.Assert):
                        mutated = self.mutate_assertion(node)
                        if mutated:
                            mutated_source = ast.unparse(tree)
                            break
            elif mutation_type == "add_edge_case":
                mutated_source = self.add_edge_case(original_source)
            elif mutation_type == "modify_parameter":
                mutated_source = self.modify_parameter(original_source)
            elif mutation_type == "swap_comparison":
                # Swap == and != in comparisons
                for node in ast.walk(tree):
                    if isinstance(node, ast.Compare) and len(node.ops) == 1:
                        if isinstance(node.ops[0], ast.Eq):
                            node.ops[0] = ast.NotEq()
                            mutated_source = ast.unparse(tree)
                            break
                        elif isinstance(node.ops[0], ast.NotEq):
                            node.ops[0] = ast.Eq()
                            mutated_source = ast.unparse(tree)
                            break
            elif mutation_type == "negate_condition":
                # Negate a condition in an if statement
                for node in ast.walk(tree):
                    if isinstance(node, ast.If):
                        node.test = ast.UnaryOp(op=ast.Not(), operand=node.test)
                        mutated_source = ast.unparse(tree)
                        break
            elif mutation_type == "add_assertion":
                # Add a simple assertion at the end of a test function
                for node in ast.walk(tree):
                    if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
                        new_assert = ast.Assert(
                            test=ast.Compare(
                                left=ast.Constant(value=1),
                                ops=[ast.Eq()],
                                comparators=[ast.Constant(value=1)]
                            )
                        )
                        node.body.append(new_assert)
                        mutated_source = ast.unparse(tree)
                        break
            elif mutation_type == "change_boundary":
                # Change boundary values (e.g., 0 to 1, 100 to 99)
                for node in ast.walk(tree):
                    if isinstance(node, ast.Constant) and isinstance(node.value, int):
                        if node.value == 0:
                            node.value = 1
                            mutated_source = ast.unparse(tree)
                            break
                        elif node.value == 1:
                            node.value = 0
                            mutated_source = ast.unparse(tree)
                            break
                        elif node.value > 1:
                            node.value = node.value - 1 if self.rng.random() < 0.5 else node.value + 1
                            mutated_source = ast.unparse(tree)
                            break
        except SyntaxError:
            return None, original_source

        return original_source, mutated_source

    def validate_mutation(self, filepath: str, mutated_source: str) -> bool:
        """Check that the mutated test file is syntactically valid."""
        try:
            ast.parse(mutated_source)
            return True
        except SyntaxError:
            return False

    def apply_mutation(self, filepath: str) -> Optional[str]:
        """Apply a mutation to a test file and write it back if valid."""
        result = self.mutate_test_file(filepath)
        if result[0] is None:
            return None
        original_source, mutated_source = result
        if self.validate_mutation(filepath, mutated_source):
            with open(filepath, "w") as f:
                f.write(mutated_source)
            return mutated_source
        return None

    def mutate_all_tests(self) -> List[str]:
        """Mutate all test files in the test directory."""
        mutated_files = []
        test_files = self.scan_test_files()
        for filepath in test_files:
            result = self.apply_mutation(filepath)
            if result is not None:
                mutated_files.append(filepath)
        return mutated_files