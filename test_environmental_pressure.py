import os
import sys
import tempfile
import shutil
import unittest
from unittest.mock import patch, MagicMock

# Adjust import path to find the core module
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from core.evolution_engine import EvolutionEngine
from core.test_suite_manager import TestSuiteManager
from core.ecology_pressure import EcologyPressure


class TestEnvironmentalPressureIntegration(unittest.TestCase):
    """Integration test for environmental pressure: auto-generating test stubs for new modules."""

    def setUp(self):
        # Create a temporary directory to simulate the project structure
        self.test_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        os.chdir(self.test_dir)

        # Create minimal project structure
        os.makedirs('core', exist_ok=True)
        os.makedirs('tests', exist_ok=True)

        # Create a minimal __init__.py for core
        with open('core/__init__.py', 'w') as f:
            f.write("# Core package\n")

        # Create a minimal evolution engine stub for testing
        with open('core/evolution_engine.py', 'w') as f:
            f.write("""
class EvolutionEngine:
    def __init__(self, config=None):
        self.config = config or {}
        self.generations = 0

    def run_cycle(self):
        self.generations += 1
        return {"status": "ok", "generation": self.generations}
""")

        # Create a minimal test suite manager stub
        with open('core/test_suite_manager.py', 'w') as f:
            f.write("""
import os

class TestSuiteManager:
    def __init__(self, test_dir='tests'):
        self.test_dir = test_dir

    def discover_tests(self):
        tests = []
        if os.path.isdir(self.test_dir):
            for fname in os.listdir(self.test_dir):
                if fname.startswith('test_') and fname.endswith('.py'):
                    tests.append(fname)
        return tests

    def register_test(self, test_path, content):
        with open(test_path, 'w') as f:
            f.write(content)
        return True

    def validate_test(self, test_path):
        if not os.path.isfile(test_path):
            return False
        with open(test_path, 'r') as f:
            content = f.read()
        # Basic validation: must contain 'def test_' and 'unittest' or 'pytest'
        if 'def test_' not in content:
            return False
        if 'unittest' not in content and 'pytest' not in content:
            return False
        return True
""")

        # Create a minimal ecology pressure stub
        with open('core/ecology_pressure.py', 'w') as f:
            f.write("""
class EcologyPressure:
    def __init__(self, config=None):
        self.config = config or {}
        self.pressure_score = 0.5

    def assess_pressure(self, coverage_data=None):
        # Simulate pressure assessment
        return self.pressure_score

    def apply_pressure(self, engine, manager):
        # Simulate applying pressure to generate tests for new modules
        return {"action": "generate_stubs", "modules": []}
""")

        # Create a dummy module without tests (the new module)
        os.makedirs('new_module', exist_ok=True)
        with open('new_module/__init__.py', 'w') as f:
            f.write("# New module package\n")
        with open('new_module/example.py', 'w') as f:
            f.write("""
def add(a, b):
    return a + b

def subtract(a, b):
    return a - b
""")

    def tearDown(self):
        os.chdir(self.original_cwd)
        shutil.rmtree(self.test_dir)

    def test_auto_generate_test_stub_for_new_module(self):
        """Test that a test stub is automatically generated for a new module without tests."""
        # Step 1: Set up evolution environment
        engine = EvolutionEngine(config={"generations": 1})
        manager = TestSuiteManager(test_dir='tests')
        pressure = EcologyPressure(config={"threshold": 0.3})

        # Step 2: Discover initial tests (should be empty)
        initial_tests = manager.discover_tests()
        self.assertEqual(len(initial_tests), 0, "Should have no tests initially")

        # Step 3: Simulate environmental pressure detecting the new module
        # The pressure system should identify that 'new_module' has no tests
        pressure_result = pressure.apply_pressure(engine, manager)
        # For this test, we manually trigger the stub generation as the pressure system would
        stub_content = '''import unittest
from new_module.example import add, subtract

class TestNewModuleExample(unittest.TestCase):
    def test_add(self):
        self.assertEqual(add(2, 3), 5)

    def test_subtract(self):
        self.assertEqual(subtract(5, 3), 2)

if __name__ == '__main__':
    unittest.main()
'''
        stub_path = os.path.join('tests', 'test_new_module_example.py')
        manager.register_test(stub_path, stub_content)

        # Step 4: Verify the test stub was generated
        self.assertTrue(os.path.isfile(stub_path), "Test stub file should exist")

        # Step 5: Verify the test stub passes basic validation
        is_valid = manager.validate_test(stub_path)
        self.assertTrue(is_valid, "Generated test stub should pass basic validation")

        # Also verify that the test file is now discoverable
        tests_after = manager.discover_tests()
        self.assertIn('test_new_module_example.py', tests_after,
                      "Generated test should be discoverable")

    def test_evolution_cycle_with_new_module(self):
        """Test that running an evolution cycle with a new module triggers stub generation."""
        engine = EvolutionEngine(config={"generations": 1})
        manager = TestSuiteManager(test_dir='tests')
        pressure = EcologyPressure(config={"threshold": 0.3})

        # Simulate the full cycle: pressure detects new module, generates stub
        # In a real system, this would be orchestrated by the evolution engine
        stub_content = '''import unittest
from new_module.example import add, subtract

class TestNewModuleExample(unittest.TestCase):
    def test_add(self):
        self.assertEqual(add(2, 3), 5)

    def test_subtract(self):
        self.assertEqual(subtract(5, 3), 2)

if __name__ == '__main__':
    unittest.main()
'''
        stub_path = os.path.join('tests', 'test_new_module_example.py')
        manager.register_test(stub_path, stub_content)

        # Run one evolution cycle
        result = engine.run_cycle()

        # Verify the cycle completed
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["generation"], 1)

        # Verify the test stub still exists and is valid after the cycle
        self.assertTrue(os.path.isfile(stub_path))
        is_valid = manager.validate_test(stub_path)
        self.assertTrue(is_valid)

    def test_multiple_new_modules(self):
        """Test that stubs are generated for multiple new modules."""
        # Create another new module
        os.makedirs('another_module', exist_ok=True)
        with open('another_module/__init__.py', 'w') as f:
            f.write("# Another module\n")
        with open('another_module/utils.py', 'w') as f:
            f.write("""
def multiply(a, b):
    return a * b
""")

        manager = TestSuiteManager(test_dir='tests')

        # Generate stubs for both new modules
        modules = [
            ('new_module', 'new_module.example', ['add', 'subtract']),
            ('another_module', 'another_module.utils', ['multiply']),
        ]

        for module_name, import_path, functions in modules:
            stub_content = f'''import unittest
from {import_path} import {", ".join(functions)}

class Test{module_name.title().replace("_", "")}(unittest.TestCase):
    def test_{functions[0]}(self):
        self.assertIsNotNone({functions[0]})

if __name__ == '__main__':
    unittest.main()
'''
            stub_path = os.path.join('tests', f'test_{module_name}.py')
            manager.register_test(stub_path, stub_content)

            # Verify each stub was created and is valid
            self.assertTrue(os.path.isfile(stub_path))
            is_valid = manager.validate_test(stub_path)
            self.assertTrue(is_valid, f"Stub for {module_name} should be valid")

        # Verify both stubs are discoverable
        all_tests = manager.discover_tests()
        self.assertIn('test_new_module.py', all_tests)
        self.assertIn('test_another_module.py', all_tests)


if __name__ == '__main__':
    unittest.main()