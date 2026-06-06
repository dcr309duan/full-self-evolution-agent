"""test_suite_mutator.py

A self-modifying module for mutating test cases to generate new variants.
Supports parameterization of inputs, edge case injection, scenario combination,
and introduction of failure modes. Tracks mutation effectiveness and can
rewrite its own mutation strategies based on learning signals.
"""

import inspect
import random
import copy
import ast
import types
import sys
import os
import tempfile
import subprocess
import importlib.util
from typing import Any, Callable, Dict, List, Optional, Tuple, Union
from collections import defaultdict, Counter
from dataclasses import dataclass, field
import itertools
import re

# ---------------------------------------------------------------------------
# Data structures for mutation tracking
# ---------------------------------------------------------------------------

@dataclass
class MutationRecord:
    """Record of a single mutation application."""
    mutation_id: str
    mutation_type: str
    original_test: str
    mutated_test: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    learning_signal: float = 0.0  # e.g., coverage increase, bug detection rate
    times_applied: int = 0
    times_useful: int = 0

    @property
    def effectiveness(self) -> float:
        """Ratio of useful applications to total applications."""
        if self.times_applied == 0:
            return 0.0
        return self.times_useful / self.times_applied


class MutationTracker:
    """Tracks mutation records and computes learning signals."""

    def __init__(self):
        self.records: Dict[str, MutationRecord] = {}
        self.history: List[MutationRecord] = []

    def register_mutation(self, mutation_type: str, original: str, mutated: str,
                          params: Dict[str, Any] = None) -> str:
        """Register a new mutation and return its ID."""
        mutation_id = f"{mutation_type}_{len(self.history)}_{random.randint(0, 10000)}"
        record = MutationRecord(
            mutation_id=mutation_id,
            mutation_type=mutation_type,
            original_test=original,
            mutated_test=mutated,
            parameters=params or {}
        )
        self.records[mutation_id] = record
        self.history.append(record)
        return mutation_id

    def record_application(self, mutation_id: str, useful: bool):
        """Update usage statistics for a mutation."""
        if mutation_id in self.records:
            self.records[mutation_id].times_applied += 1
            if useful:
                self.records[mutation_id].times_useful += 1

    def set_learning_signal(self, mutation_id: str, signal: float):
        """Set the learning signal for a mutation."""
        if mutation_id in self.records:
            self.records[mutation_id].learning_signal = signal

    def get_best_mutations(self, top_n: int = 5) -> List[MutationRecord]:
        """Return the top N mutations by effectiveness."""
        sorted_records = sorted(
            self.records.values(),
            key=lambda r: (r.effectiveness, r.learning_signal),
            reverse=True
        )
        return sorted_records[:top_n]

    def get_mutation_stats(self) -> Dict[str, Any]:
        """Return aggregate statistics."""
        if not self.records:
            return {}
        total = len(self.records)
        useful = sum(1 for r in self.records.values() if r.times_useful > 0)
        avg_effectiveness = sum(r.effectiveness for r in self.records.values()) / total
        return {
            "total_mutations": total,
            "useful_mutations": useful,
            "avg_effectiveness": avg_effectiveness,
            "best_mutation": self.get_best_mutations(1)[0] if self.records else None
        }


# ---------------------------------------------------------------------------
# Mutation strategies (can be self-modified)
# ---------------------------------------------------------------------------

class MutationStrategy:
    """Base class for mutation strategies."""

    def __init__(self, name: str, mutator: 'TestSuiteMutator'):
        self.name = name
        self.mutator = mutator

    def mutate(self, test_code: str) -> str:
        """Apply mutation to test code. Override in subclasses."""
        raise NotImplementedError

    def __repr__(self):
        return f"MutationStrategy({self.name})"


class ParameterizeInputs(MutationStrategy):
    """Replace hardcoded inputs with parameterized versions."""

    def __init__(self, mutator: 'TestSuiteMutator'):
        super().__init__("parameterize_inputs", mutator)

    def mutate(self, test_code: str) -> str:
        # Simple heuristic: find function calls with literal arguments and replace
        # with parameterized versions.
        lines = test_code.split('\n')
        mutated_lines = []
        for line in lines:
            # Look for patterns like func(5) or func("hello")
            if '(' in line and ')' in line and 'def ' not in line and 'assert' not in line:
                # Replace literal arguments with parameterized versions
                # This is a simplified version; real implementation would use AST
                # Replace integer literals
                line = re.sub(r'\((\d+)\)', r'(param_\1)', line)
                # Replace string literals
                line = re.sub(r'\("([^"]+)"\)', r'("param_\1")', line)
            mutated_lines.append(line)
        return '\n'.join(mutated_lines)


class AddEdgeCases(MutationStrategy):
    """Add edge case test scenarios."""

    EDGE_CASES = [
        ("empty_input", "assert func('') == expected_empty"),
        ("zero_input", "assert func(0) == expected_zero"),
        ("negative_input", "assert func(-1) == expected_negative"),
        ("large_input", "assert func(10**6) == expected_large"),
        ("none_input", "assert func(None) == expected_none"),
        ("boundary_input", "assert func(sys.maxsize) == expected_boundary"),
    ]

    def __init__(self, mutator: 'TestSuiteMutator'):
        super().__init__("add_edge_cases", mutator)

    def mutate(self, test_code: str) -> str:
        # Add edge case assertions after the last assertion in the test
        lines = test_code.split('\n')
        # Find the last assert line
        last_assert_idx = -1
        for i, line in enumerate(lines):
            if line.strip().startswith('assert'):
                last_assert_idx = i

        if last_assert_idx >= 0:
            # Insert edge cases after the last assert
            edge_case = random.choice(self.EDGE_CASES)
            indent = '    '  # Assume 4-space indent
            edge_line = f"{indent}# Edge case: {edge_case[0]}\n{indent}{edge_case[1]}"
            lines.insert(last_assert_idx + 1, edge_line)
            return '\n'.join(lines)
        return test_code


class CombineScenarios(MutationStrategy):
    """Combine multiple test scenarios into one."""

    def __init__(self, mutator: 'TestSuiteMutator'):
        super().__init__("combine_scenarios", mutator)

    def mutate(self, test_code: str) -> str:
        # Combine multiple assert statements into a single test with multiple scenarios
        lines = test_code.split('\n')
        assert_lines = [i for i, line in enumerate(lines) if line.strip().startswith('assert')]
        if len(assert_lines) < 2:
            return test_code

        # Pick two assert lines to combine
        idx1, idx2 = random.sample(assert_lines, 2)
        # Create a combined scenario
        combined = f"# Combined scenario\nfor input_val in [input1, input2]:\n    assert func(input_val) == expected"
        # Replace the two assert lines with the combined version
        # This is a simplified approach
        lines[idx1] = combined
        lines[idx2] = f"    # (combined from line {idx2})"
        return '\n'.join(lines)


class IntroduceFailureModes(MutationStrategy):
    """Introduce new failure modes by modifying assertions."""

    FAILURE_MODES = [
        ("off_by_one", lambda x: f"assert func({x}) == expected_{x} + 1"),
        ("type_error", lambda x: f"assert func('{x}') == expected_string"),
        ("negation", lambda x: f"assert not func({x}) == expected_{x}"),
        ("boundary_flip", lambda x: f"assert func({x}) < expected_{x}"),
    ]

    def __init__(self, mutator: 'TestSuiteMutator'):
        super().__init__("introduce_failure_modes", mutator)

    def mutate(self, test_code: str) -> str:
        lines = test_code.split('\n')
        for i, line in enumerate(lines):
            if line.strip().startswith('assert') and 'func(' in line:
                # Extract the argument
                match = re.search(r'func\(([^)]+)\)', line)
                if match:
                    arg = match.group(1)
                    failure_mode = random.choice(self.FAILURE_MODES)
                    new_assert = failure_mode[1](arg)
                    lines[i] = f"    # Failure mode: {failure_mode[0]}\n    {new_assert}"
                    break
        return '\n'.join(lines)


# ---------------------------------------------------------------------------
# Self-modification engine
# ---------------------------------------------------------------------------

class SelfModificationEngine:
    """Allows the module to rewrite its own mutation strategies."""

    def __init__(self, mutator: 'TestSuiteMutator'):
        self.mutator = mutator
        self.source_file = __file__ if '__file__' in globals() else 'test_suite_mutator.py'

    def add_strategy(self, strategy_code: str, strategy_name: str = None):
        """Add a new mutation strategy dynamically."""
        # Parse the strategy code
        try:
            tree = ast.parse(strategy_code)
            # Find class definitions
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    strategy_name = node.name
                    break
            if not strategy_name:
                raise ValueError("No class found in strategy code")
            # Compile and execute the new class
            compiled = compile(tree, '<string>', 'exec')
            local_scope = {}
            exec(compiled, globals(), local_scope)
            # Instantiate and register
            new_class = local_scope.get(strategy_name)
            if new_class and issubclass(new_class, MutationStrategy):
                instance = new_class(self.mutator)
                self.mutator.strategies[strategy_name] = instance
                return instance
        except Exception as e:
            raise RuntimeError(f"Failed to add strategy: {e}")

    def remove_strategy(self, strategy_name: str):
        """Remove a mutation strategy."""
        if strategy_name in self.mutator.strategies:
            del self.mutator.strategies[strategy_name]

    def modify_strategy(self, strategy_name: str, new_code: str):
        """Replace an existing strategy with new code."""
        self.remove_strategy(strategy_name)
        return self.add_strategy(new_code)

    def get_strategy_source(self, strategy_name: str) -> str:
        """Get the source code of a strategy."""
        strategy = self.mutator.strategies.get(strategy_name)
        if strategy:
            return inspect.getsource(strategy.__class__)
        return ""

    def rewrite_self(self, new_strategies: Dict[str, str]):
        """Rewrite the module file with new strategies."""
        # Read current source
        with open(self.source_file, 'r') as f:
            source = f.read()

        # Find the mutation strategies section and replace
        # This is a simplified approach; real implementation would use AST
        for name, code in new_strategies.items():
            # Find the class definition and replace
            pattern = rf"class {name}\(MutationStrategy\):.*?(?=\nclass |\n#|\Z)"
            replacement = code.strip()
            source = re.sub(pattern, replacement, source, flags=re.DOTALL)

        # Write back
        with open(self.source_file, 'w') as f:
            f.write(source)

        # Reload the module
        import importlib
        importlib.reload(sys.modules[__name__])


# ---------------------------------------------------------------------------
# Main mutator class
# ---------------------------------------------------------------------------

class TestSuiteMutator:
    """Main class for mutating test suites."""

    def __init__(self, test_dir: str = "tests", source_dir: str = "src"):
        self.tracker = MutationTracker()
        self.self_mod = SelfModificationEngine(self)
        self.strategies: Dict[str, MutationStrategy] = {
            "parameterize_inputs": ParameterizeInputs(self),
            "add_edge_cases": AddEdgeCases(self),
            "combine_scenarios": CombineScenarios(self),
            "introduce_failure_modes": IntroduceFailureModes(self),
        }
        self.mutation_history: List[Tuple[str, str, str]] = []  # (original, mutated, strategy)
        self.test_dir = test_dir
        self.source_dir = source_dir

    def mutate(self, test_code: str, strategy_name: str = None) -> str:
        """Apply a mutation to test code."""
        if strategy_name:
            strategy = self.strategies.get(strategy_name)
            if not strategy:
                raise ValueError(f"Unknown strategy: {strategy_name}")
        else:
            # Pick a random strategy
            strategy = random.choice(list(self.strategies.values()))

        mutated = strategy.mutate(test_code)
        mutation_id = self.tracker.register_mutation(
            strategy.name, test_code, mutated
        )
        self.mutation_history.append((test_code, mutated, strategy.name))
        return mutated

    def mutate_multiple(self, test_cases: List[str], num_mutations: int = 5) -> List[str]:
        """Generate multiple mutated versions of test cases."""
        results = []
        for _ in range(num_mutations):
            test = random.choice(test_cases)
            mutated = self.mutate(test)
            results.append(mutated)
        return results

    def evaluate_mutation(self, mutation_id: str, test_results: Dict[str, bool]) -> float:
        """Evaluate a mutation based on test results and compute learning signal."""
        record = self.tracker.records.get(mutation_id)
        if not record:
            return 0.0

        # Compute learning signal based on:
        # - How many new failures were detected
        # - How much coverage increased
        # - Diversity of inputs
        signal = 0.0
        if test_results:
            failures = sum(1 for v in test_results.values() if not v)
            signal = failures / len(test_results)

        self.tracker.set_learning_signal(mutation_id, signal)
        return signal

    def get_best_strategies(self, top_n: int = 2) -> List[str]:
        """Return the names of the best performing strategies."""
        best_mutations = self.tracker.get_best_mutations(top_n)
        strategy_counts = Counter(r.mutation_type for r in best_mutations)
        return [s for s, _ in strategy_counts.most_common(top_n)]

    def adapt_strategies(self):
        """Adapt mutation strategies based on learning signals."""
        best = self.get_best_strategies(2)
        # Strengthen best strategies by modifying their behavior
        for strategy_name in best:
            strategy = self.strategies.get(strategy_name)
            if strategy:
                # Example adaptation: increase aggressiveness
                if hasattr(strategy, 'EDGE_CASES'):
                    # Add more edge cases
                    new_edge = ("random_edge", "assert func(random.random()) == expected_random")
                    if new_edge not in strategy.EDGE_CASES:
                        strategy.EDGE_CASES.append(new_edge)

    def generate_report(self) -> Dict[str, Any]:
        """Generate a report of mutation activities."""
        stats = self.tracker.get_mutation_stats()
        return {
            "statistics": stats,
            "best_strategies": self.get_best_strategies(),
            "total_mutations_applied": len(self.mutation_history),
            "active_strategies": list(self.strategies.keys()),
        }

    # -----------------------------------------------------------------------
    # New methods for test suite evolution
    # -----------------------------------------------------------------------

    def scan_coverage(self) -> Dict[str, List[str]]:
        """Use AST to find all test files and their imports.

        Returns:
            Dict mapping test file paths to lists of imported module names.
        """
        coverage_map = {}
        if not os.path.isdir(self.test_dir):
            return coverage_map

        for root, dirs, files in os.walk(self.test_dir):
            for file in files:
                if file.endswith('.py') and file.startswith('test_'):
                    filepath = os.path.join(root, file)
                    try:
                        with open(filepath, 'r') as f:
                            source = f.read()
                        tree = ast.parse(source)
                        imports = []
                        for node in ast.walk(tree):
                            if isinstance(node, ast.Import):
                                for alias in node.names:
                                    imports.append(alias.name)
                            elif isinstance(node, ast.ImportFrom):
                                if node.module:
                                    imports.append(node.module)
                        coverage_map[filepath] = imports
                    except Exception as e:
                        print(f"Warning: Could not parse {filepath}: {e}")
        return coverage_map

    def identify_gaps(self) -> List[Dict[str, Any]]:
        """Compare module exports vs test coverage.

        Returns:
            List of dicts with 'module', 'uncovered_exports', and 'test_files'.
        """
        gaps = []
        if not os.path.isdir(self.source_dir):
            return gaps

        # Get all source modules
        source_modules = {}
        for root, dirs, files in os.walk(self.source_dir):
            for file in files:
                if file.endswith('.py') and not file.startswith('_'):
                    filepath = os.path.join(root, file)
                    module_name = filepath.replace(os.sep, '.').replace('.py', '')
                    try:
                        with open(filepath, 'r') as f:
                            source = f.read()
                        tree = ast.parse(source)
                        exports = []
                        for node in ast.walk(tree):
                            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                                exports.append(node.name)
                            elif isinstance(node, ast.Assign):
                                for target in node.targets:
                                    if isinstance(target, ast.Name):
                                        if not target.id.startswith('_'):
                                            exports.append(target.id)
                        source_modules[module_name] = {
                            'filepath': filepath,
                            'exports': exports
                        }
                    except Exception as e:
                        print(f"Warning: Could not parse {filepath}: {e}")

        # Get test coverage
        coverage_map = self.scan_coverage()

        # Compare
        for module_name, module_info in source_modules.items():
            uncovered = []
            test_files = []
            for test_file, imports in coverage_map.items():
                if module_name in imports:
                    test_files.append(test_file)
            for export in module_info['exports']:
                covered = False
                for test_file in test_files:
                    try:
                        with open(test_file, 'r') as f:
                            test_source = f.read()
                        if export in test_source:
                            covered = True
                            break
                    except:
                        pass
                if not covered:
                    uncovered.append(export)
            if uncovered:
                gaps.append({
                    'module': module_name,
                    'uncovered_exports': uncovered,
                    'test_files': test_files
                })
        return gaps

    def generate_test_stub(self, module_path: str) -> str:
        """Create a minimal pytest test file that imports the module and runs basic smoke tests.

        Args:
            module_path: Path to the module to generate tests for.

        Returns:
            String containing the generated test code.
        """
        # Convert module path to importable name
        module_name = module_path.replace(os.sep, '.').replace('.py', '')
        if module_name.endswith('.'):
            module_name = module_name[:-1]

        # Get module exports
        exports = []
        try:
            with open(module_path, 'r') as f:
                source = f.read()
            tree = ast.parse(source)
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    exports.append(node.name)
        except Exception as e:
            print(f"Warning: Could not parse {module_path}: {e}")

        # Generate test code
        test_code = f'''"""Auto-generated test stub for {module_name}."""
import pytest
import sys
import os

# Add source to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from {module_name} import {', '.join(exports) if exports else '*'}


class Test{module_name.replace('.', '_').title().replace('_', '')}:
    """Smoke tests for {module_name}."""

    def test_import(self):
        """Test that the module can be imported."""
        import {module_name}
        assert {module_name} is not None

'''

        # Add smoke tests for each export
        for export in exports:
            test_code += f'''    def test_{export}_smoke(self):
        """Basic smoke test for {export}."""
        # This is a stub - replace with actual test logic
        assert {export} is not None
        # TODO: Add actual test assertions

'''

        return test_code

    def validate_and_add(self, test_code: str, test_path: str) -> bool:
        """Write to temp dir, run pytest on it, only move to real test dir if tests pass.

        Args:
            test_code: The test code to validate.
            test_path: The intended path for the test file.

        Returns:
            True if tests passed and file was written, False otherwise.
        """
        # Create temp directory
        with tempfile.TemporaryDirectory() as tmpdir:
            # Write test to temp dir
            tmp_test_path = os.path.join(tmpdir, os.path.basename(test_path))
            os.makedirs(os.path.dirname(tmp_test_path), exist_ok=True)
            with open(tmp_test_path, 'w') as f:
                f.write(test_code)

            # Run pytest on the temp test
            try:
                result = subprocess.run(
                    [sys.executable, '-m', 'pytest', tmp_test_path, '-v', '--tb=short'],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                if result.returncode == 0:
                    # Tests passed, move to real test dir
                    os.makedirs(os.path.dirname(test_path), exist_ok=True)
                    with open(test_path, 'w') as f:
                        f.write(test_code)
                    print(f"Test file written to {test_path}")
                    return True
                else:
                    print(f"Tests failed for {test_path}:")
                    print(result.stdout)
                    print(result.stderr)
                    return False
            except subprocess.TimeoutExpired:
                print(f"Test execution timed out for {test_path}")
                return False
            except Exception as e:
                print(f"Error running tests for {test_path}: {e}")
                return False

    def evolve(self) -> Dict[str, Any]:
        """Orchestrate the full cycle: scan, identify gaps, generate stubs, validate, and add.

        Returns:
            Dict with 'new_tests', 'failed_tests', 'gaps_found', and 'coverage_stats'.
        """
        results = {
            'new_tests': [],
            'failed_tests': [],
            'gaps_found': [],
            'coverage_stats': {}
        }

        # Step 1: Scan coverage
        coverage_map = self.scan_coverage()
        results['coverage_stats'] = {
            'test_files_found': len(coverage_map),
            'total_imports': sum(len(imports) for imports in coverage_map.values())
        }

        # Step 2: Identify gaps
        gaps = self.identify_gaps()
        results['gaps_found'] = gaps

        # Step 3: Generate and validate test stubs for gaps
        for gap in gaps:
            module_path = gap['module'].replace('.', os.sep) + '.py'
            full_module_path = os.path.join(self.source_dir, module_path)
            if not os.path.exists(full_module_path):
                # Try to find the module file
                for root, dirs, files in os.walk(self.source_dir):
                    for file in files:
                        if file.endswith('.py') and file.replace('.py', '') == gap['module'].split('.')[-1]:
                            full_module_path = os.path.join(root, file)
                            break

            if os.path.exists(full_module_path):
                # Generate test stub
                test_code = self.generate_test_stub(full_module_path)

                # Determine test file path
                test_filename = f"test_{gap['module'].replace('.', '_')}.py"
                test_path = os.path.join(self.test_dir, test_filename)

                # Validate and add
                success = self.validate_and_add(test_code, test_path)
                if success:
                    results['new_tests'].append(test_path)
                else:
                    results['failed_tests'].append(test_path)

        # Step 4: Adapt strategies based on results
        if results['new_tests']:
            self.adapt_strategies()

        return results


# ---------------------------------------------------------------------------
# Utility functions for external use
# ---------------------------------------------------------------------------

def create_mutator(test_dir: str = "tests", source_dir: str = "src") -> TestSuiteMutator:
    """Factory function to create a configured mutator."""
    return TestSuiteMutator(test_dir=test_dir, source_dir=source_dir)


def mutate_test_file(filepath: str, output_path: str = None, num_mutations: int = 10):
    """Mutate all test cases in a file and write to output."""
    mutator = create_mutator()
    with open(filepath, 'r') as f:
        content = f.read()

    # Split into individual test functions (simple heuristic)
    test_cases = []
    current_test = []
    for line in content.split('\n'):
        if line.strip().startswith('def test_'):
            if current_test:
                test_cases.append('\n'.join(current_test))
            current_test = [line]
        else:
            current_test.append(line)
    if current_test:
        test_cases.append('\n'.join(current_test))

    # Mutate
    mutated_tests = mutator.mutate_multiple(test_cases, num_mutations)

    # Write output
    output = output_path or filepath.replace('.py', '_mutated.py')
    with open(output, 'w') as f:
        f.write("# Auto-generated mutated test cases\n")
        f.write(f"# Original source: {filepath}\n\n")
        for test in mutated_tests:
            f.write(test + '\n\n')

    return mutator.generate_report()


# ---------------------------------------------------------------------------
# Self-test / demo
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Demo the mutator
    sample_test = """
def test_addition():
    assert add(2, 3) == 5
    assert add(-1, 1) == 0
    assert add(0, 0) == 0
"""

    mutator = create_mutator()
    print("Original test:")
    print(sample_test)
    print("\nMutated versions:")
    for i in range(3):
        mutated = mutator.mutate(sample_test)
        print(f"\n--- Mutation {i+1} ---")
        print(mutated)

    print("\nReport:")
    print(mutator.generate_report())

    # Demo evolution cycle
    print("\n--- Evolution Cycle Demo ---")
    print("Scanning coverage...")
    coverage = mutator.scan_coverage()
    print(f"Found {len(coverage)} test files")

    print("\nIdentifying gaps...")
    gaps = mutator.identify_gaps()
    print(f"Found {len(gaps)} gaps")

    if gaps:
        print("\nGenerating test stub for first gap...")
        module_path = gaps[0]['module'].replace('.', os.sep) + '.py'
        full_path = os.path.join(mutator.source_dir, module_path)
        if os.path.exists(full_path):
            stub = mutator.generate_test_stub(full_path)
            print(stub[:500] + "...")
        else:
            print(f"Module file not found: {full_path}")

    print("\nEvolve cycle completed.")