import unittest
from unittest.mock import patch, mock_open
from core.ecology_engine import generate_new_benchmark, evolve_test_suite, BenchmarkRegistry
import ast
import os
import json
import sys
import tempfile
import importlib.util

class TestEcologyEngineMinimal(unittest.TestCase):
    def test_evolve_test_suite_with_mock_generator(self):
        """Test evolve_test_suite with a mock test generator."""
        mock_generator_calls = []
        
        def mock_generator(difficulty):
            mock_generator_calls.append(difficulty)
            return {
                "code": "def test_add(): assert 1 + 1 == 2",
                "difficulty": difficulty,
                "test_cases": [((1, 2), 3)]
            }
        
        result = evolve_test_suite(
            test_generator=mock_generator,
            num_tests=3,
            difficulty="EASY"
        )
        
        self.assertEqual(len(mock_generator_calls), 3)
        for call in mock_generator_calls:
            self.assertEqual(call, "EASY")
        
        self.assertEqual(len(result), 3)
        for test in result:
            self.assertIn("code", test)
            self.assertIn("difficulty", test)
            self.assertIn("test_cases", test)

    def test_evolve_test_suite_rejects_invalid_tests(self):
        """Verify that invalid tests are rejected."""
        invalid_tests_generated = []
        
        def mock_generator_with_invalid(difficulty):
            invalid_tests_generated.append(difficulty)
            if len(invalid_tests_generated) == 1:
                return None  # Invalid test
            elif len(invalid_tests_generated) == 2:
                return {"code": "", "difficulty": difficulty, "test_cases": []}  # Invalid test
            else:
                return {
                    "code": "def test_valid(): assert 1 + 1 == 2",
                    "difficulty": difficulty,
                    "test_cases": [((1, 2), 3)]
                }
        
        result = evolve_test_suite(
            test_generator=mock_generator_with_invalid,
            num_tests=5,
            difficulty="MEDIUM"
        )
        
        # Should only contain valid tests
        for test in result:
            self.assertIsNotNone(test)
            self.assertIn("code", test)
            self.assertGreater(len(test["code"]), 0)
            self.assertIn("difficulty", test)
            self.assertIn("test_cases", test)

    def test_evolve_test_suite_with_json_output(self):
        """Test that evolve_test_suite can produce JSON output."""
        def mock_generator(difficulty):
            return {
                "code": "def test_mul(): assert 2 * 3 == 6",
                "difficulty": difficulty,
                "test_cases": [((2, 3), 6)]
            }
        
        result = evolve_test_suite(
            test_generator=mock_generator,
            num_tests=2,
            difficulty="HARD",
            output_format="json"
        )
        
        # Verify result is valid JSON
        parsed = json.loads(result)
        self.assertIsInstance(parsed, list)
        self.assertEqual(len(parsed), 2)
        for test in parsed:
            self.assertIn("code", test)
            self.assertIn("difficulty", test)
            self.assertIn("test_cases", test)

    def test_evolve_test_suite_handles_empty_generator(self):
        """Test that evolve_test_suite handles a generator that returns no valid tests."""
        def empty_generator(difficulty):
            return None
        
        result = evolve_test_suite(
            test_generator=empty_generator,
            num_tests=3,
            difficulty="EASY"
        )
        
        self.assertEqual(len(result), 0)

    def test_evolve_test_suite_with_different_difficulties(self):
        """Test evolve_test_suite with various difficulty levels."""
        difficulties = ["EASY", "MEDIUM", "HARD"]
        
        def mock_generator(difficulty):
            return {
                "code": f"def test_{difficulty.lower()}(): pass",
                "difficulty": difficulty,
                "test_cases": [((), None)]
            }
        
        for diff in difficulties:
            result = evolve_test_suite(
                test_generator=mock_generator,
                num_tests=1,
                difficulty=diff
            )
            
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0]["difficulty"], diff)

    @patch('builtins.open', new_callable=mock_open)
    @patch('os.makedirs')
    def test_generate_new_benchmark_creates_valid_test_file(self, mock_makedirs, mock_file):
        """Test that generate_new_benchmark creates a valid Python test file with test_ prefix."""
        # Call the function
        result = generate_new_benchmark()
        
        # Verify os.makedirs was called to create tests directory
        mock_makedirs.assert_called_once_with('tests', exist_ok=True)
        
        # Verify open was called to write a file
        mock_file.assert_called_once()
        call_args = mock_file.call_args
        self.assertTrue(call_args[0][0].startswith('tests/'))
        self.assertTrue(call_args[0][0].endswith('.py'))
        
        # Get the written content
        written_content = ''.join(call[0] for call in mock_file.write.call_args_list)
        
        # Verify the content is valid Python syntax
        try:
            ast.parse(written_content)
        except SyntaxError as e:
            self.fail(f"Generated test file contains invalid Python syntax: {e}")
        
        # Verify the content contains a function with 'test_' prefix
        tree = ast.parse(written_content)
        has_test_function = False
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name.startswith('test_'):
                has_test_function = True
                break
        self.assertTrue(has_test_function, "Generated test file does not contain a function with 'test_' prefix")
        
        # Verify the function is a valid test function (takes no arguments)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name.startswith('test_'):
                self.assertEqual(len(node.args.args), 0, f"Test function {node.name} should take no arguments")
        
        # Verify the result is the file path
        self.assertTrue(isinstance(result, str))
        self.assertTrue(result.startswith('tests/'))
        self.assertTrue(result.endswith('.py'))

    def test_generate_new_benchmark_creates_valid_python(self):
        """Test that generated benchmark is valid Python code."""
        # Create a temporary directory to avoid polluting the real tests directory
        with tempfile.TemporaryDirectory() as tmpdir:
            original_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                os.makedirs('tests', exist_ok=True)
                
                # Generate a benchmark
                result = generate_new_benchmark()
                
                # Read the generated file
                with open(result, 'r') as f:
                    content = f.read()
                
                # Verify it's valid Python
                try:
                    ast.parse(content)
                except SyntaxError as e:
                    self.fail(f"Generated benchmark has invalid Python syntax: {e}")
                
                # Verify it has a test function
                tree = ast.parse(content)
                has_test = any(
                    isinstance(node, ast.FunctionDef) and node.name.startswith('test_')
                    for node in ast.walk(tree)
                )
                self.assertTrue(has_test, "Generated benchmark must contain a test function")
                
            finally:
                os.chdir(original_cwd)

    def test_generate_new_benchmark_no_import_errors(self):
        """Test that generated benchmark has no import errors."""
        with tempfile.TemporaryDirectory() as tmpdir:
            original_cwd = os.getcwd()
            original_sys_path = sys.path.copy()
            try:
                os.chdir(tmpdir)
                os.makedirs('tests', exist_ok=True)
                sys.path.insert(0, tmpdir)
                
                # Generate a benchmark
                result = generate_new_benchmark()
                
                # Try to import the generated module
                module_name = os.path.splitext(os.path.basename(result))[0]
                try:
                    spec = importlib.util.spec_from_file_location(module_name, result)
                    if spec is None:
                        self.fail(f"Could not create spec for {result}")
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                except ImportError as e:
                    self.fail(f"Generated benchmark has import error: {e}")
                except Exception as e:
                    self.fail(f"Generated benchmark raised unexpected error: {e}")
                
            finally:
                sys.path = original_sys_path
                os.chdir(original_cwd)

    def test_benchmark_registry_updated(self):
        """Test that the benchmark registry is properly updated after generation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            original_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                os.makedirs('tests', exist_ok=True)
                
                # Get initial registry state
                initial_registry = BenchmarkRegistry.list_benchmarks()
                initial_count = len(initial_registry)
                
                # Generate a new benchmark
                result = generate_new_benchmark()
                
                # Get updated registry state
                updated_registry = BenchmarkRegistry.list_benchmarks()
                
                # Verify registry has been updated
                self.assertEqual(len(updated_registry), initial_count + 1,
                                 "Benchmark registry should have one more entry after generation")
                
                # Verify the new benchmark is in the registry
                benchmark_names = [b['name'] for b in updated_registry]
                generated_name = os.path.splitext(os.path.basename(result))[0]
                self.assertIn(generated_name, benchmark_names,
                              f"Generated benchmark '{generated_name}' should be in registry")
                
                # Verify the registry entry has required fields
                for benchmark in updated_registry:
                    self.assertIn('name', benchmark)
                    self.assertIn('path', benchmark)
                    self.assertIn('timestamp', benchmark)
                    self.assertIn('difficulty', benchmark)
                    
            finally:
                os.chdir(original_cwd)

    def test_benchmark_registry_persists_across_calls(self):
        """Test that the benchmark registry persists across multiple generate calls."""
        with tempfile.TemporaryDirectory() as tmpdir:
            original_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                os.makedirs('tests', exist_ok=True)
                
                # Generate multiple benchmarks
                num_benchmarks = 3
                generated_files = []
                for _ in range(num_benchmarks):
                    result = generate_new_benchmark()
                    generated_files.append(result)
                
                # Verify registry has all benchmarks
                registry = BenchmarkRegistry.list_benchmarks()
                self.assertEqual(len(registry), num_benchmarks,
                                 f"Registry should contain {num_benchmarks} benchmarks")
                
                # Verify each generated file is in the registry
                for filepath in generated_files:
                    basename = os.path.splitext(os.path.basename(filepath))[0]
                    self.assertIn(basename, [b['name'] for b in registry],
                                  f"Benchmark '{basename}' should be in registry")
                
            finally:
                os.chdir(original_cwd)

    def test_benchmark_registry_metadata(self):
        """Test that benchmark registry entries contain correct metadata."""
        with tempfile.TemporaryDirectory() as tmpdir:
            original_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                os.makedirs('tests', exist_ok=True)
                
                # Generate a benchmark
                result = generate_new_benchmark()
                
                # Get registry entry for the generated benchmark
                registry = BenchmarkRegistry.list_benchmarks()
                generated_name = os.path.splitext(os.path.basename(result))[0]
                
                # Find the entry
                entry = None
                for b in registry:
                    if b['name'] == generated_name:
                        entry = b
                        break
                
                self.assertIsNotNone(entry, f"Registry entry for '{generated_name}' not found")
                
                # Verify metadata fields
                self.assertIn('name', entry)
                self.assertIn('path', entry)
                self.assertIn('timestamp', entry)
                self.assertIn('difficulty', entry)
                self.assertIn('test_count', entry)
                
                # Verify types
                self.assertIsInstance(entry['name'], str)
                self.assertIsInstance(entry['path'], str)
                self.assertIsInstance(entry['timestamp'], (int, float))
                self.assertIsInstance(entry['difficulty'], str)
                self.assertIsInstance(entry['test_count'], int)
                
                # Verify path points to existing file
                self.assertTrue(os.path.exists(entry['path']),
                                f"Registry path '{entry['path']}' should exist")
                
            finally:
                os.chdir(original_cwd)

    def test_benchmark_registry_clear(self):
        """Test that the benchmark registry can be cleared."""
        with tempfile.TemporaryDirectory() as tmpdir:
            original_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                os.makedirs('tests', exist_ok=True)
                
                # Generate a benchmark
                generate_new_benchmark()
                
                # Verify registry is not empty
                registry = BenchmarkRegistry.list_benchmarks()
                self.assertGreater(len(registry), 0)
                
                # Clear the registry
                BenchmarkRegistry.clear_registry()
                
                # Verify registry is empty
                registry = BenchmarkRegistry.list_benchmarks()
                self.assertEqual(len(registry), 0,
                                 "Registry should be empty after clear")
                
            finally:
                os.chdir(original_cwd)

    def test_minimal_evolve_test_suite(self):
        """Minimal test: import ecology_pressure_engine, call evolve_test_suite, assert path exists and is .py."""
        import ecology_pressure_engine
        result = ecology_pressure_engine.evolve_test_suite()
        self.assertTrue(os.path.exists(result))
        self.assertTrue(result.endswith('.py'))

if __name__ == '__main__':
    unittest.main()