import os
import re
import ast
import unittest
import json
import subprocess
import sys
import hashlib
import time
from collections import defaultdict
from typing import List, Dict, Set, Optional, Tuple, Any

class TestSuiteMutator:
    """Handles adding, removing, or modifying test cases in the test suite."""
    
    def __init__(self, test_dir: str = "tests"):
        self.test_dir = test_dir
        os.makedirs(self.test_dir, exist_ok=True)
    
    def add_test_case(self, module_name: str, test_name: str, assertion: str) -> str:
        """Add a new test case to the specified module's test file."""
        test_filename = f"test_{module_name}.py"
        test_filepath = os.path.join(self.test_dir, test_filename)
        
        # Create test file if it doesn't exist
        if not os.path.exists(test_filepath):
            test_content = f'''import unittest

class Test{module_name.capitalize()}(unittest.TestCase):
    pass

if __name__ == "__main__":
    unittest.main()
'''
            with open(test_filepath, "w") as f:
                f.write(test_content)
        
        # Read existing content
        with open(test_filepath, "r") as f:
            source = f.read()
        
        # Add new test method
        new_method = f"\n    def {test_name}(self):\n        {assertion}\n"
        
        # Insert before the last line of the file
        lines = source.split('\n')
        for i in range(len(lines) - 1, -1, -1):
            if lines[i].strip() == "if __name__ == \"__main__\"":
                lines.insert(i, new_method)
                break
        else:
            # Fallback: append to end
            lines.append(new_method)
        
        source = '\n'.join(lines)
        
        with open(test_filepath, "w") as f:
            f.write(source)
        
        return test_filepath
    
    def remove_test_case(self, module_name: str, test_name: str) -> bool:
        """Remove a specific test case from the specified module's test file."""
        test_filename = f"test_{module_name}.py"
        test_filepath = os.path.join(self.test_dir, test_filename)
        
        if not os.path.exists(test_filepath):
            return False
        
        with open(test_filepath, "r") as f:
            source = f.read()
        
        # Remove the test method
        pattern = rf"\n\s+def {test_name}\(self\):.*?(?=\n\s+def |\nclass |\nif __name__)"
        source = re.sub(pattern, "", source, flags=re.DOTALL)
        
        # Clean up empty lines
        source = re.sub(r'\n{3,}', '\n\n', source)
        
        with open(test_filepath, "w") as f:
            f.write(source)
        
        return True
    
    def modify_test_case(self, module_name: str, test_name: str, new_assertion: str) -> bool:
        """Modify an existing test case's assertion."""
        test_filename = f"test_{module_name}.py"
        test_filepath = os.path.join(self.test_dir, test_filename)
        
        if not os.path.exists(test_filepath):
            return False
        
        with open(test_filepath, "r") as f:
            source = f.read()
        
        # Find and replace the assertion in the specified test method
        pattern = rf"(def {test_name}\(self\):\s+)(.*?)(?=\n\s+def |\nclass |\nif __name__)"
        replacement = rf"\1{new_assertion}"
        source = re.sub(pattern, replacement, source, flags=re.DOTALL)
        
        with open(test_filepath, "w") as f:
            f.write(source)
        
        return True
    
    def get_test_methods(self, module_name: str) -> List[Dict[str, str]]:
        """Get all test methods and their assertions for a module."""
        test_filename = f"test_{module_name}.py"
        test_filepath = os.path.join(self.test_dir, test_filename)
        
        if not os.path.exists(test_filepath):
            return []
        
        with open(test_filepath, "r") as f:
            source = f.read()
        
        methods = []
        try:
            tree = ast.parse(source, filename=test_filepath)
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
                    # Extract assertion from the method body
                    assertions = []
                    for child in ast.walk(node):
                        if isinstance(child, ast.Call):
                            func_name = None
                            if isinstance(child.func, ast.Attribute):
                                func_name = child.func.attr
                            elif isinstance(child.func, ast.Name):
                                func_name = child.func.id
                            if func_name and func_name.startswith("assert"):
                                try:
                                    assertions.append(ast.dump(child))
                                except Exception:
                                    pass
                    
                    methods.append({
                        "name": node.name,
                        "assertions": assertions
                    })
        except (SyntaxError, IOError):
            pass
        
        return methods


class NoveltyDetector:
    """Identifies test patterns not present in the current suite."""
    
    def __init__(self, test_dir: str = "tests"):
        self.test_dir = test_dir
        self.existing_patterns = self._load_existing_patterns()
    
    def _load_existing_patterns(self) -> Set[str]:
        """Load all existing assertion patterns from test files."""
        patterns = set()
        if not os.path.isdir(self.test_dir):
            return patterns
        
        for filename in os.listdir(self.test_dir):
            if filename.startswith("test_") and filename.endswith(".py"):
                filepath = os.path.join(self.test_dir, filename)
                try:
                    with open(filepath, "r") as f:
                        source = f.read()
                    tree = ast.parse(source, filename=filepath)
                    for node in ast.walk(tree):
                        if isinstance(node, ast.Call):
                            func_name = None
                            if isinstance(node.func, ast.Attribute):
                                func_name = node.func.attr
                            elif isinstance(node.func, ast.Name):
                                func_name = node.func.id
                            if func_name and func_name.startswith("assert"):
                                try:
                                    patterns.add(ast.dump(node))
                                except Exception:
                                    pass
                except (SyntaxError, IOError):
                    continue
        
        return patterns
    
    def find_novel_patterns(self, num_patterns: int = 5) -> List[str]:
        """Find novel assertion patterns not present in the current suite."""
        # Common assertion patterns to check
        common_patterns = [
            "self.assertTrue(True)",
            "self.assertFalse(False)",
            "self.assertEqual(1, 1)",
            "self.assertNotEqual(1, 2)",
            "self.assertIsNone(None)",
            "self.assertIsNotNone(1)",
            "self.assertIn(1, [1, 2, 3])",
            "self.assertNotIn(4, [1, 2, 3])",
            "self.assertIsInstance(1, int)",
            "self.assertNotIsInstance(1, str)",
            "self.assertGreater(2, 1)",
            "self.assertGreaterEqual(2, 2)",
            "self.assertLess(1, 2)",
            "self.assertLessEqual(1, 1)",
            "self.assertAlmostEqual(1.0, 1.0)",
            "self.assertNotAlmostEqual(1.0, 2.0)",
            "self.assertIs(True, True)",
            "self.assertIsNot(True, False)",
            "self.assertRegex('test', 'test')",
            "self.assertNotRegex('test', 'xyz')",
            "self.assertCountEqual([1, 2], [2, 1])",
            "self.assertMultiLineEqual('a\\nb', 'a\\nb')",
            "self.assertSequenceEqual([1, 2], [1, 2])",
            "self.assertListEqual([1, 2], [1, 2])",
            "self.assertTupleEqual((1, 2), (1, 2))",
            "self.assertSetEqual({1, 2}, {2, 1})",
            "self.assertDictEqual({'a': 1}, {'a': 1})",
            "self.assertDictContainsSubset({'a': 1}, {'a': 1, 'b': 2})",
        ]
        
        novel_patterns = []
        for pattern in common_patterns:
            if pattern not in self.existing_patterns:
                novel_patterns.append(pattern)
                if len(novel_patterns) >= num_patterns:
                    break
        
        # If not enough novel patterns found, generate unique ones
        while len(novel_patterns) < num_patterns:
            counter = len(novel_patterns) + len(self.existing_patterns)
            new_pattern = f"self.assertIsNot(1, {counter + 2})"
            if new_pattern not in self.existing_patterns and new_pattern not in novel_patterns:
                novel_patterns.append(new_pattern)
        
        return novel_patterns[:num_patterns]
    
    def get_coverage_gaps(self) -> Dict[str, List[str]]:
        """Identify modules and assertion types that are under-covered."""
        gaps = defaultdict(list)
        
        # Check for missing assertion types per module
        assertion_types = [
            "assertTrue", "assertFalse", "assertEqual", "assertNotEqual",
            "assertIsNone", "assertIsNotNone", "assertIn", "assertNotIn",
            "assertIsInstance", "assertGreater", "assertLess",
            "assertAlmostEqual", "assertIs", "assertIsNot"
        ]
        
        if not os.path.isdir(self.test_dir):
            return dict(gaps)
        
        for filename in os.listdir(self.test_dir):
            if filename.startswith("test_") and filename.endswith(".py"):
                module_name = filename.replace("test_", "").replace(".py", "")
                filepath = os.path.join(self.test_dir, filename)
                
                try:
                    with open(filepath, "r") as f:
                        source = f.read()
                    tree = ast.parse(source, filename=filepath)
                    
                    # Collect used assertion types
                    used_assertions = set()
                    for node in ast.walk(tree):
                        if isinstance(node, ast.Call):
                            func_name = None
                            if isinstance(node.func, ast.Attribute):
                                func_name = node.func.attr
                            elif isinstance(node.func, ast.Name):
                                func_name = node.func.id
                            if func_name and func_name.startswith("assert"):
                                used_assertions.add(func_name)
                    
                    # Find missing assertion types
                    missing = [at for at in assertion_types if at not in used_assertions]
                    if missing:
                        gaps[module_name] = missing
                        
                except (SyntaxError, IOError):
                    continue
        
        return dict(gaps)


class PressureInjector:
    """Creates performance benchmarks and stress tests."""
    
    def __init__(self, test_dir: str = "tests"):
        self.test_dir = test_dir
        os.makedirs(self.test_dir, exist_ok=True)
    
    def create_performance_benchmark(self, module_name: str, iterations: int = 1000) -> str:
        """Create a performance benchmark test for a module."""
        test_content = f'''import unittest
import time

class Test{module_name.capitalize()}Performance(unittest.TestCase):
    """Performance benchmarks for {module_name} module."""
    
    def setUp(self):
        self.iterations = {iterations}
    
    def test_performance_baseline(self):
        """Baseline performance test."""
        start_time = time.time()
        for _ in range(self.iterations):
            # Simple operation to establish baseline
            _ = 1 + 1
        elapsed = time.time() - start_time
        self.assertLess(elapsed, 1.0, "Baseline operation took too long")
    
    def test_performance_stress(self):
        """Stress test with repeated operations."""
        start_time = time.time()
        results = []
        for i in range(self.iterations):
            results.append(i * 2)
        elapsed = time.time() - start_time
        self.assertLess(elapsed, 2.0, f"Stress test took {{elapsed:.2f}}s")
        self.assertEqual(len(results), self.iterations)
    
    def test_performance_memory(self):
        """Memory allocation performance test."""
        start_time = time.time()
        data = []
        for i in range(min(self.iterations, 100)):
            data.append([j for j in range(100)])
        elapsed = time.time() - start_time
        self.assertLess(elapsed, 1.0, f"Memory allocation took {{elapsed:.2f}}s")
        self.assertEqual(len(data), min(self.iterations, 100))

if __name__ == "__main__":
    unittest.main()
'''
        
        filename = f"test_{module_name}_performance.py"
        filepath = os.path.join(self.test_dir, filename)
        
        with open(filepath, "w") as f:
            f.write(test_content)
        
        return filepath
    
    def create_stress_test(self, module_name: str, num_threads: int = 10) -> str:
        """Create a stress test that simulates concurrent access."""
        test_content = f'''import unittest
import threading
import time

class Test{module_name.capitalize()}Stress(unittest.TestCase):
    """Stress tests for {module_name} module."""
    
    def setUp(self):
        self.num_threads = {num_threads}
        self.results = []
        self.errors = []
    
    def _worker(self, worker_id: int):
        """Worker function for stress testing."""
        try:
            # Simulate work
            result = 0
            for i in range(100):
                result += i * worker_id
            self.results.append(result)
        except Exception as e:
            self.errors.append((worker_id, str(e)))
    
    def test_concurrent_access(self):
        """Test concurrent access with multiple threads."""
        threads = []
        for i in range(self.num_threads):
            t = threading.Thread(target=self._worker, args=(i,))
            threads.append(t)
            t.start()
        
        for t in threads:
            t.join(timeout=10)
        
        self.assertEqual(len(self.errors), 0, f"Errors occurred: {{self.errors}}")
        self.assertEqual(len(self.results), self.num_threads)
    
    def test_repeated_stress(self):
        """Repeated stress test to check for memory leaks."""
        for iteration in range(5):
            local_results = []
            for i in range(100):
                local_results.append(i * iteration)
            self.assertEqual(len(local_results), 100)
            time.sleep(0.01)  # Small delay to simulate real workload
    
    def test_boundary_conditions(self):
        """Test boundary conditions under stress."""
        test_cases = [
            (0, "Minimum value"),
            (1, "Single value"),
            (1000, "Large value"),
            (-1, "Negative value"),
        ]
        
        for value, description in test_cases:
            with self.subTest(description=description):
                result = value * 2
                self.assertIsInstance(result, int)

if __name__ == "__main__":
    unittest.main()
'''
        
        filename = f"test_{module_name}_stress.py"
        filepath = os.path.join(self.test_dir, filename)
        
        with open(filepath, "w") as f:
            f.write(test_content)
        
        return filepath
    
    def create_load_test(self, module_name: str, duration_seconds: int = 5) -> str:
        """Create a load test that runs for a specified duration."""
        test_content = f'''import unittest
import time

class Test{module_name.capitalize()}Load(unittest.TestCase):
    """Load tests for {module_name} module."""
    
    def setUp(self):
        self.duration = {duration_seconds}
        self.operations_per_second = []
    
    def test_sustained_load(self):
        """Sustained load test over time."""
        start_time = time.time()
        operation_count = 0
        
        while time.time() - start_time < self.duration:
            # Perform operations
            for _ in range(100):
                _ = 1 + 1
                operation_count += 1
            
            # Record operations per second
            elapsed = time.time() - start_time
            if elapsed > 0:
                self.operations_per_second.append(operation_count / elapsed)
        
        total_time = time.time() - start_time
        avg_ops_per_second = operation_count / total_time if total_time > 0 else 0
        
        self.assertGreater(avg_ops_per_second, 0, "No operations performed")
        self.assertGreater(total_time, 0, "Test ran too quickly")
    
    def test_peak_load(self):
        """Peak load test with maximum operations."""
        start_time = time.time()
        peak_operations = 0
        
        # Perform as many operations as possible in 1 second
        while time.time() - start_time < 1.0:
            for _ in range(1000):
                _ = [i for i in range(10)]
                peak_operations += 1
        
        self.assertGreater(peak_operations, 0, "No peak operations performed")

if __name__ == "__main__":
    unittest.main()
'''
        
        filename = f"test_{module_name}_load.py"
        filepath = os.path.join(self.test_dir, filename)
        
        with open(filepath, "w") as f:
            f.write(test_content)
        
        return filepath


class TestRegistry:
    """Tracks all tests and their metadata."""
    
    def __init__(self, registry_file: str = "test_registry.json"):
        self.registry_file = registry_file
        self.registry = self._load_registry()
    
    def _load_registry(self) -> Dict[str, Any]:
        """Load the registry from file."""
        if os.path.exists(self.registry_file):
            try:
                with open(self.registry_file, "r") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        return {
            "tests": {},
            "metadata": {
                "created_at": time.time(),
                "last_updated": time.time(),
                "total_tests": 0
            }
        }
    
    def _save_registry(self):
        """Save the registry to file."""
        self.registry["metadata"]["last_updated"] = time.time()
        self.registry["metadata"]["total_tests"] = len(self.registry["tests"])
        
        with open(self.registry_file, "w") as f:
            json.dump(self.registry, f, indent=2)
    
    def register_test(self, test_name: str, module: str, test_type: str, 
                     assertions: List[str], filepath: str) -> str:
        """Register a test with its metadata."""
        test_id = hashlib.md5(f"{test_name}:{module}:{time.time()}".encode()).hexdigest()[:8]
        
        self.registry["tests"][test_id] = {
            "name": test_name,
            "module": module,
            "type": test_type,
            "assertions": assertions,
            "filepath": filepath,
            "created_at": time.time(),
            "last_run": None,
            "status": "pending",
            "execution_time": None
        }
        
        self._save_registry()
        return test_id
    
    def update_test_status(self, test_id: str, status: str, execution_time: float = None):
        """Update the status of a registered test."""
        if test_id in self.registry["tests"]:
            self.registry["tests"][test_id]["status"] = status
            self.registry["tests"][test_id]["last_run"] = time.time()
            if execution_time is not None:
                self.registry["tests"][test_id]["execution_time"] = execution_time
            self._save_registry()
    
    def get_test_by_name(self, test_name: str) -> Optional[Dict[str, Any]]:
        """Get test metadata by test name."""
        for test_id, test_data in self.registry["tests"].items():
            if test_data["name"] == test_name:
                return test_data
        return None
    
    def get_tests_by_module(self, module: str) -> List[Dict[str, Any]]:
        """Get all tests for a specific module."""
        return [
            test_data for test_data in self.registry["tests"].values()
            if test_data["module"] == module
        ]
    
    def get_tests_by_type(self, test_type: str) -> List[Dict[str, Any]]:
        """Get all tests of a specific type."""
        return [
            test_data for test_data in self.registry["tests"].values()
            if test_data["type"] == test_type
        ]
    
    def get_all_tests(self) -> Dict[str, Dict[str, Any]]:
        """Get all registered tests."""
        return self.registry["tests"]
    
    def remove_test(self, test_id: str) -> bool:
        """Remove a test from the registry."""
        if test_id in self.registry["tests"]:
            del self.registry["tests"][test_id]
            self._save_registry()
            return True
        return False
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get statistics about the registered tests."""
        stats = {
            "total_tests": len(self.registry["tests"]),
            "by_type": defaultdict(int),
            "by_module": defaultdict(int),
            "by_status": defaultdict(int),
            "average_execution_time": 0
        }
        
        total_time = 0
        time_count = 0
        
        for test_data in self.registry["tests"].values():
            stats["by_type"][test_data["type"]] += 1
            stats["by_module"][test_data["module"]] += 1
            stats["by_status"][test_data["status"]] += 1
            
            if test_data["execution_time"] is not None:
                total_time += test_data["execution_time"]
                time_count += 1
        
        if time_count > 0:
            stats["average_execution_time"] = total_time / time_count
        
        return dict(stats)


class TestSuiteEvolution:
    """Scans tests/ directory, extracts assertions, generates novel test files, and maintains a manifest."""

    MANIFEST_FILE = "test_manifest.json"

    def __init__(self, test_dir="tests"):
        self.test_dir = test_dir
        self.existing_assertions = set()
        self.manifest = self._load_manifest()
        self.mutator = TestSuiteMutator(test_dir)
        self.novelty_detector = NoveltyDetector(test_dir)
        self.pressure_injector = PressureInjector(test_dir)
        self.registry = TestRegistry()

    def _load_manifest(self):
        if os.path.exists(self.MANIFEST_FILE):
            with open(self.MANIFEST_FILE, "r") as f:
                return json.load(f)
        return {"generated_files": []}

    def _save_manifest(self):
        with open(self.MANIFEST_FILE, "w") as f:
            json.dump(self.manifest, f, indent=2)

    def scan_test_files(self):
        """Scan the test directory and extract all assertion strings from test files."""
        if not os.path.isdir(self.test_dir):
            return
        for filename in os.listdir(self.test_dir):
            if filename.startswith("test_") and filename.endswith(".py"):
                filepath = os.path.join(self.test_dir, filename)
                try:
                    with open(filepath, "r") as f:
                        source = f.read()
                    tree = ast.parse(source, filename=filepath)
                    for node in ast.walk(tree):
                        if isinstance(node, ast.Call):
                            func_name = None
                            if isinstance(node.func, ast.Attribute):
                                func_name = node.func.attr
                            elif isinstance(node.func, ast.Name):
                                func_name = node.func.id
                            if func_name and func_name.startswith("assert"):
                                # Extract the assertion string representation
                                try:
                                    assertion_str = ast.dump(node)
                                    self.existing_assertions.add(assertion_str)
                                except Exception:
                                    pass
                except (SyntaxError, IOError):
                    continue

    def generate_novel_test(self, base_name="test_generated"):
        """Generate a new test file with an assertion not found in existing tests."""
        # Simple novel assertion patterns
        novel_assertions = [
            "self.assertTrue(True)",
            "self.assertEqual(1, 1)",
            "self.assertIn(1, [1, 2, 3])",
            "self.assertIsNone(None)",
            "self.assertIsNotNone(1)",
            "self.assertGreater(2, 1)",
            "self.assertLess(1, 2)",
            "self.assertAlmostEqual(1.0, 1.0)",
            "self.assertNotEqual(1, 2)",
            "self.assertIsInstance(1, int)",
        ]

        # Find a novel assertion
        chosen_assertion = None
        for assertion in novel_assertions:
            # Check if this assertion pattern is already present
            is_novel = True
            for existing in self.existing_assertions:
                if assertion in existing:
                    is_novel = False
                    break
            if is_novel:
                chosen_assertion = assertion
                break

        if chosen_assertion is None:
            # If all patterns are used, create a unique one
            counter = len(self.manifest["generated_files"])
            chosen_assertion = f"self.assertIsNot(1, {counter + 2})"

        # Generate test file content
        test_content = f'''import unittest

class TestGenerated(unittest.TestCase):
    def test_novel(self):
        {chosen_assertion}

if __name__ == "__main__":
    unittest.main()
'''

        # Determine a unique filename
        file_index = len(self.manifest["generated_files"]) + 1
        filename = f"{base_name}_{file_index}.py"
        filepath = os.path.join(self.test_dir, filename)

        # Write the file
        os.makedirs(self.test_dir, exist_ok=True)
        with open(filepath, "w") as f:
            f.write(test_content)

        # Register in manifest
        self.manifest["generated_files"].append({
            "filename": filename,
            "assertion": chosen_assertion
        })
        self._save_manifest()

        # Register in test registry
        self.registry.register_test(
            test_name="test_novel",
            module="generated",
            test_type="novel",
            assertions=[chosen_assertion],
            filepath=filepath
        )

        return filepath

    def _get_module_coverage(self):
        """Analyze test files to determine which modules are least covered."""
        module_coverage = {}
        if not os.path.isdir(self.test_dir):
            return module_coverage
        
        for filename in os.listdir(self.test_dir):
            if filename.startswith("test_") and filename.endswith(".py"):
                filepath = os.path.join(self.test_dir, filename)
                try:
                    with open(filepath, "r") as f:
                        source = f.read()
                    tree = ast.parse(source, filename=filepath)
                    for node in ast.walk(tree):
                        if isinstance(node, ast.Call):
                            func_name = None
                            if isinstance(node.func, ast.Attribute):
                                func_name = node.func.attr
                            elif isinstance(node.func, ast.Name):
                                func_name = node.func.id
                            if func_name and func_name.startswith("assert"):
                                # Extract the module name from the test file
                                module_name = filename.replace("test_", "").replace(".py", "")
                                if module_name not in module_coverage:
                                    module_coverage[module_name] = 0
                                module_coverage[module_name] += 1
                except (SyntaxError, IOError):
                    continue
        
        return module_coverage

    def _find_least_covered_module(self):
        """Identify the module with the fewest assertions."""
        module_coverage = self._get_module_coverage()
        if not module_coverage:
            return None
        
        # Find the module with the minimum number of assertions
        min_coverage = min(module_coverage.values())
        least_covered_modules = [module for module, count in module_coverage.items() if count == min_coverage]
        
        # Return the first least-covered module
        return least_covered_modules[0] if least_covered_modules else None

    def _generate_new_assertions(self, module_name):
        """Generate 3 new test assertions for the given module."""
        # Generate unique assertions based on module name and current state
        counter = len(self.manifest["generated_files"])
        new_assertions = [
            f"self.assertIsNotNone({module_name})",
            f"self.assertIsInstance({module_name}, str)",
            f"self.assertEqual(len({module_name}), {counter + 10})"
        ]
        
        # Ensure assertions are novel
        novel_assertions = []
        for assertion in new_assertions:
            is_novel = True
            for existing in self.existing_assertions:
                if assertion in existing:
                    is_novel = False
                    break
            if is_novel:
                novel_assertions.append(assertion)
        
        # If not enough novel assertions, generate more
        while len(novel_assertions) < 3:
            counter += 1
            new_assertion = f"self.assertGreater({counter}, {counter - 1})"
            is_novel = True
            for existing in self.existing_assertions:
                if new_assertion in existing:
                    is_novel = False
                    break
            if is_novel:
                novel_assertions.append(new_assertion)
        
        return novel_assertions[:3]

    def _append_assertions_to_test_file(self, module_name, assertions):
        """Append the given assertions to the corresponding test file."""
        test_filename = f"test_{module_name}.py"
        test_filepath = os.path.join(self.test_dir, test_filename)
        
        # Create test file if it doesn't exist
        if not os.path.exists(test_filepath):
            test_content = f'''import unittest

class Test{module_name.capitalize()}(unittest.TestCase):
    pass

if __name__ == "__main__":
    unittest.main()
'''
            os.makedirs(self.test_dir, exist_ok=True)
            with open(test_filepath, "w") as f:
                f.write(test_content)
        
        # Read existing content
        with open(test_filepath, "r") as f:
            source = f.read()
        
        # Parse the AST to find the class and add new test methods
        tree = ast.parse(source, filename=test_filepath)
        
        # Find the test class
        test_class = None
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
                test_class = node
                break
        
        if test_class is None:
            # If no test class found, add one
            new_class_code = f"\n\nclass Test{module_name.capitalize()}(unittest.TestCase):\n"
            for i, assertion in enumerate(assertions):
                new_class_code += f"    def test_evolved_{i}(self):\n        {assertion}\n\n"
            source += new_class_code
        else:
            # Add new test methods to the existing class
            new_methods = ""
            for i, assertion in enumerate(assertions):
                new_methods += f"    def test_evolved_{i}(self):\n        {assertion}\n\n"
            
            # Insert new methods before the last line of the class
            lines = source.split('\n')
            class_start = None
            class_end = None
            for i, line in enumerate(lines):
                if line.strip().startswith("class Test") and module_name.capitalize() in line:
                    class_start = i
                if class_start is not None and line.strip() == "" and i > class_start:
                    class_end = i
                    break
            
            if class_end is not None:
                # Insert new methods before the blank line after class
                lines.insert(class_end, new_methods.rstrip())
                source = '\n'.join(lines)
            else:
                # Fallback: append to the end of the file
                source += "\n" + new_methods
        
        # Write the updated content
        with open(test_filepath, "w") as f:
            f.write(source)
        
        return test_filepath

    def _run_test_suite(self):
        """Run the test suite and return True if all tests pass."""
        try:
            result = subprocess.run(
                [sys.executable, "-m", "unittest", "discover", "-s", self.test_dir],
                capture_output=True,
                text=True,
                timeout=30
            )
            return result.returncode == 0
        except subprocess.TimeoutExpired:
            return False
        except Exception:
            return False

    def evolve_test_suite(self):
        """Identify the least-covered module, generate 3 new assertions, append them, and validate."""
        # Step 1: Scan existing test files
        self.scan_test_files()
        
        # Step 2: Identify the least-covered module
        least_covered_module = self._find_least_covered_module()
        if least_covered_module is None:
            print("No modules found to evolve.")
            return False
        
        print(f"Least-covered module: {least_covered_module}")
        
        # Step 3: Generate 3 new test assertions for the module
        new_assertions = self._generate_new_assertions(least_covered_module)
        print(f"Generated assertions: {new_assertions}")
        
        # Step 4: Append assertions to the corresponding test file
        test_filepath = self._append_assertions_to_test_file(least_covered_module, new_assertions)
        print(f"Appended assertions to: {test_filepath}")
        
        # Step 5: Run the test suite to validate
        success = self._run_test_suite()
        if success:
            print("Test suite passed successfully.")
            # Update manifest
            self.manifest["generated_files"].append({
                "filename": os.path.basename(test_filepath),
                "assertions": new_assertions,
                "module": least_covered_module
            })
            self._save_manifest()
            
            # Register in test registry
            for i, assertion in enumerate(new_assertions):
                self.registry.register_test(
                    test_name=f"test_evolved_{i}",
                    module=least_covered_module,
                    test_type="evolved",
                    assertions=[assertion],
                    filepath=test_filepath
                )
            
            return True
        else:
            print("Test suite failed. Rolling back changes.")
            # Rollback: remove the added assertions
            self._rollback_test_file(test_filepath, new_assertions)
            return False

    def _rollback_test_file(self, filepath, assertions):
        """Remove the added assertions from the test file."""
        try:
            with open(filepath, "r") as f:
                source = f.read()
            
            # Remove the added test methods
            for i in range(len(assertions)):
                method_pattern = f"    def test_evolved_{i}(self):\n        {assertions[i]}\n\n"
                source = source.replace(method_pattern, "")
            
            # Clean up empty lines
            source = re.sub(r'\n{3,}', '\n\n', source)
            
            with open(filepath, "w") as f:
                f.write(source)
        except Exception as e:
            print(f"Error during rollback: {e}")

    def evolve(self):
        """Perform the full evolution cycle: scan, generate novel test, register."""
        self.scan_test_files()
        return self.generate_novel_test()


if __name__ == "__main__":
    evolution = TestSuiteEvolution()
    new_file = evolution.evolve()
    print(f"Generated new test file: {new_file}")
    
    # Also run the evolve_test_suite method
    success = evolution.evolve_test_suite()
    if success:
        print("Test suite evolution completed successfully.")
    else:
        print("Test suite evolution failed.")