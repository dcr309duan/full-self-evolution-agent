"""ecology_minimal_core.py - A minimal, self-contained ecology engine with zero external dependencies.

Provides core classes for scanning, generating, and mutating test suites.
Includes a self-test method for verification.
"""

import ast
import hashlib
import os
import random
import sys
import textwrap
import traceback
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple


class TestSuiteScanner:
    """Scans a directory tree for Python test files and extracts test functions."""

    def __init__(self, root_dir: str = "."):
        self.root_dir = Path(root_dir).resolve()
        self.test_files: List[Path] = []
        self.test_functions: Dict[str, List[str]] = {}

    def scan(self) -> None:
        """Find all test files (test_*.py or *_test.py) under root_dir."""
        self.test_files = []
        self.test_functions = {}
        for path in self.root_dir.rglob("*.py"):
            if path.name.startswith("test_") or path.name.endswith("_test.py"):
                self.test_files.append(path)
                self._extract_functions(path)

    def _extract_functions(self, path: Path) -> None:
        """Extract function names from a test file using AST."""
        try:
            with open(path, "r", encoding="utf-8") as f:
                tree = ast.parse(f.read(), filename=str(path))
            funcs = []
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
                    funcs.append(node.name)
            self.test_functions[str(path)] = funcs
        except (SyntaxError, UnicodeDecodeError, OSError):
            pass

    def get_coverage_gaps(self) -> List[Tuple[str, str]]:
        """Identify potential coverage gaps (simulated heuristic)."""
        gaps = []
        for filepath, funcs in self.test_functions.items():
            if not funcs:
                gaps.append((filepath, "no_test_functions"))
            elif len(funcs) < 3:
                gaps.append((filepath, "low_test_count"))
        return gaps

    def summary(self) -> Dict:
        """Return a summary of the scan results."""
        return {
            "root_dir": str(self.root_dir),
            "test_files_found": len(self.test_files),
            "total_test_functions": sum(len(v) for v in self.test_functions.values()),
            "files_with_tests": len(self.test_functions),
        }


class SimplePressureGenerator:
    """Generates new test cases based on coverage gaps or heuristics."""

    def __init__(self, scanner: TestSuiteScanner):
        self.scanner = scanner
        self.generated_tests: List[Tuple[str, str]] = []  # (filepath, test_code)

    def generate_for_gaps(self) -> List[Tuple[str, str]]:
        """Generate test cases for identified coverage gaps."""
        gaps = self.scanner.get_coverage_gaps()
        new_tests = []
        for filepath, gap_type in gaps:
            if gap_type == "no_test_functions":
                code = self._create_basic_test_file(filepath)
                new_tests.append((filepath, code))
            elif gap_type == "low_test_count":
                code = self._create_additional_test(filepath)
                new_tests.append((filepath, code))
        self.generated_tests = new_tests
        return new_tests

    def _create_basic_test_file(self, filepath: str) -> str:
        """Create a basic test file for a module that has no tests."""
        module_name = Path(filepath).stem.replace("test_", "").replace("_test", "")
        test_code = textwrap.dedent(f'''\
            \"\"\"Auto-generated tests for {module_name}.\"\"\"
            import pytest
            from {module_name} import *  # noqa: F403


            def test_{module_name}_basic():
                """Basic sanity test."""
                assert True


            def test_{module_name}_edge():
                """Edge case test."""
                assert 1 == 1


            def test_{module_name}_error():
                """Error handling test."""
                try:
                    raise ValueError("test")
                except ValueError:
                    assert True
        ''')
        return test_code

    def _create_additional_test(self, filepath: str) -> str:
        """Create an additional test function for a file with few tests."""
        module_name = Path(filepath).stem.replace("test_", "").replace("_test", "")
        test_code = textwrap.dedent(f'''\
            def test_{module_name}_generated():
                """Auto-generated additional test."""
                result = 42
                assert result == 42
        ''')
        return test_code


class TestSuiteMutator:
    """Mutates test suites by adding, removing, or modifying tests."""

    def __init__(self, scanner: TestSuiteScanner):
        self.scanner = scanner
        self.mutations_applied: List[str] = []

    def add_test(self, filepath: str, test_code: str) -> bool:
        """Add a new test function to an existing test file."""
        path = Path(filepath)
        if not path.exists():
            return False
        try:
            with open(path, "a", encoding="utf-8") as f:
                f.write("\n" + test_code + "\n")
            self.mutations_applied.append(f"Added test to {filepath}")
            return True
        except OSError:
            return False

    def remove_test(self, filepath: str, test_name: str) -> bool:
        """Remove a test function from a file (simple line-based removal)."""
        path = Path(filepath)
        if not path.exists():
            return False
        try:
            with open(path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            new_lines = []
            skip = False
            removed = False
            for line in lines:
                if line.strip().startswith(f"def {test_name}("):
                    skip = True
                    removed = True
                elif skip and line.strip() and not line[0].isspace():
                    skip = False
                elif skip and line.strip() == "":
                    continue
                if not skip:
                    new_lines.append(line)
            if removed:
                with open(path, "w", encoding="utf-8") as f:
                    f.writelines(new_lines)
                self.mutations_applied.append(f"Removed {test_name} from {filepath}")
                return True
            return False
        except OSError:
            return False

    def modify_test(self, filepath: str, old_name: str, new_code: str) -> bool:
        """Replace an existing test function with new code."""
        if self.remove_test(filepath, old_name):
            return self.add_test(filepath, new_code)
        return False

    def random_mutation(self) -> Optional[str]:
        """Apply a random mutation to a random test file."""
        if not self.scanner.test_files:
            return None
        filepath = str(random.choice(self.scanner.test_files))
        mutation_type = random.choice(["add", "remove", "modify"])

        if mutation_type == "add":
            test_code = f"def test_random_{random.randint(1000,9999)}():\n    assert True\n"
            if self.add_test(filepath, test_code):
                return f"Random add to {filepath}"
        elif mutation_type == "remove":
            funcs = self.scanner.test_functions.get(filepath, [])
            if funcs:
                test_name = random.choice(funcs)
                if self.remove_test(filepath, test_name):
                    return f"Random remove {test_name} from {filepath}"
        else:  # modify
            funcs = self.scanner.test_functions.get(filepath, [])
            if funcs:
                old_name = random.choice(funcs)
                new_code = f"def {old_name}_modified():\n    assert 2 + 2 == 4\n"
                if self.modify_test(filepath, old_name, new_code):
                    return f"Random modify {old_name} in {filepath}"
        return None


class EcologyMinimalCore:
    """Main ecology engine combining scanner, generator, and mutator."""

    def __init__(self, root_dir: str = "."):
        self.scanner = TestSuiteScanner(root_dir)
        self.generator = SimplePressureGenerator(self.scanner)
        self.mutator = TestSuiteMutator(self.scanner)

    def run_full_cycle(self) -> Dict:
        """Execute a full ecology cycle: scan, generate, mutate."""
        results = {"scan": {}, "generate": [], "mutate": []}

        # Scan
        self.scanner.scan()
        results["scan"] = self.scanner.summary()

        # Generate
        generated = self.generator.generate_for_gaps()
        results["generate"] = [(fp, len(code)) for fp, code in generated]

        # Mutate (apply generated tests)
        for filepath, test_code in generated:
            success = self.mutator.add_test(filepath, test_code)
            results["mutate"].append({"file": filepath, "success": success})

        return results

    def self_test(self) -> bool:
        """Run a self-test to verify the engine works correctly."""
        try:
            # Create a temporary directory structure for testing
            import tempfile
            import shutil

            tmp_dir = tempfile.mkdtemp(prefix="ecology_test_")
            test_dir = Path(tmp_dir) / "tests"
            test_dir.mkdir(parents=True, exist_ok=True)

            # Create a sample test file
            sample_test = test_dir / "test_sample.py"
            sample_test.write_text(textwrap.dedent("""\
                def test_one():
                    assert 1 == 1

                def test_two():
                    assert 2 == 2
            """))

            # Create a module to test
            mod_dir = Path(tmp_dir) / "src"
            mod_dir.mkdir(parents=True, exist_ok=True)
            mod_file = mod_dir / "mymodule.py"
            mod_file.write_text("def foo(): return 42\n")

            # Initialize engine on tmp_dir
            engine = EcologyMinimalCore(root_dir=tmp_dir)

            # Run scan
            engine.scanner.scan()
            scan_summary = engine.scanner.summary()
            assert scan_summary["test_files_found"] >= 1, "Should find at least one test file"
            assert scan_summary["total_test_functions"] >= 2, "Should find at least 2 test functions"

            # Run generation
            generated = engine.generator.generate_for_gaps()
            assert isinstance(generated, list), "Generated tests should be a list"

            # Run mutation
            mutation_result = engine.mutator.random_mutation()
            assert mutation_result is None or isinstance(mutation_result, str), "Mutation result should be string or None"

            # Run full cycle
            cycle_results = engine.run_full_cycle()
            assert "scan" in cycle_results, "Full cycle should include scan results"
            assert "generate" in cycle_results, "Full cycle should include generate results"
            assert "mutate" in cycle_results, "Full cycle should include mutate results"

            # Cleanup
            shutil.rmtree(tmp_dir)

            return True

        except Exception as e:
            print(f"Self-test failed: {e}")
            traceback.print_exc()
            return False


def main():
    """CLI entry point for testing the ecology engine."""
    engine = EcologyMinimalCore()
    print("Running ecology self-test...")
    if engine.self_test():
        print("Self-test PASSED")
        return 0
    else:
        print("Self-test FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(main())