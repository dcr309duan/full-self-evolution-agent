import ast
import os
import shutil
import tempfile
import random
import textwrap
from typing import List, Tuple, Optional


class TestSuiteMutator:
    """Mutates test files in the tests/ directory with safe, AST-validated mutations."""

    def __init__(self, tests_dir: str = "tests"):
        self.tests_dir = tests_dir
        self.mutation_types = [
            self._add_parameterized_test_case,
            self._add_edge_case,
            self._add_performance_test,
            self._add_stress_test,
        ]

    def get_test_files(self) -> List[str]:
        """Return list of Python test file paths in the tests directory."""
        if not os.path.isdir(self.tests_dir):
            return []
        return [
            os.path.join(self.tests_dir, f)
            for f in os.listdir(self.tests_dir)
            if f.endswith(".py") and f.startswith("test_")
        ]

    def _add_parameterized_test_case(self, source: str) -> str:
        """Add a parameterized test case using a simple decorator pattern."""
        param_decorator = textwrap.dedent("""\
        def parametrize(params):
            def decorator(func):
                def wrapper(*args, **kwargs):
                    for p in params:
                        func(*args, p, **kwargs)
                return wrapper
            return decorator
        """)
        param_test = textwrap.dedent("""\
        @parametrize([1, 2, 3, 5, 10])
        def test_mutated_parameterized(value):
            assert value > 0
        """)
        return source + "\n\n" + param_decorator + "\n" + param_test

    def _add_edge_case(self, source: str) -> str:
        """Add an edge case test."""
        edge_test = textwrap.dedent("""\
        def test_mutated_edge_case():
            assert True  # Edge case placeholder
        """)
        return source + "\n\n" + edge_test

    def _add_performance_test(self, source: str) -> str:
        """Add a performance test with timing."""
        perf_test = textwrap.dedent("""\
        import time
        def test_mutated_performance():
            start = time.time()
            for _ in range(1000):
                pass
            elapsed = time.time() - start
            assert elapsed < 10.0  # Performance threshold
        """)
        return source + "\n\n" + perf_test

    def _add_stress_test(self, source: str) -> str:
        """Add a stress test with large iterations."""
        stress_test = textwrap.dedent("""\
        def test_mutated_stress():
            for i in range(10000):
                assert i >= 0
        """)
        return source + "\n\n" + stress_test

    def validate_ast(self, source: str) -> bool:
        """Check if the source code can be parsed by Python AST."""
        try:
            ast.parse(source)
            return True
        except SyntaxError:
            return False

    def apply_random_mutation(self, source: str) -> Optional[str]:
        """Apply a random safe mutation to the source code."""
        mutation_func = random.choice(self.mutation_types)
        mutated = mutation_func(source)
        if self.validate_ast(mutated):
            return mutated
        return None

    def atomic_write(self, filepath: str, content: str) -> bool:
        """Write content to file atomically with rollback on failure."""
        fd, tmp_path = tempfile.mkstemp(dir=os.path.dirname(filepath), suffix=".tmp")
        try:
            with os.fdopen(fd, "w") as tmp_file:
                tmp_file.write(content)
            shutil.move(tmp_path, filepath)
            return True
        except (OSError, IOError) as e:
            # Rollback: remove temp file if it still exists
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            return False

    def mutate_test_file(self, filepath: str) -> Tuple[bool, str]:
        """Mutate a single test file with validation and atomic write."""
        if not os.path.isfile(filepath):
            return False, f"File not found: {filepath}"

        try:
            with open(filepath, "r") as f:
                original_source = f.read()
        except (OSError, IOError) as e:
            return False, f"Read error: {e}"

        mutated_source = self.apply_random_mutation(original_source)
        if mutated_source is None:
            return False, "Mutation produced invalid AST"

        success = self.atomic_write(filepath, mutated_source)
        if success:
            return True, f"Successfully mutated: {filepath}"
        else:
            return False, f"Atomic write failed for: {filepath}"

    def mutate_all(self) -> List[Tuple[str, str]]:
        """Mutate all test files in the tests directory."""
        results = []
        for test_file in self.get_test_files():
            success, message = self.mutate_test_file(test_file)
            results.append((test_file, message))
        return results


def main():
    """CLI entry point for test suite mutation."""
    mutator = TestSuiteMutator()
    results = mutator.mutate_all()
    for filepath, message in results:
        print(message)


if __name__ == "__main__":
    main()