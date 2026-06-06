import unittest
import os
import sys
import tempfile
import shutil
import importlib.util

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.ecology_pressure_engine import evolve_fitness_landscape, initialize_ecology_engine

class TestEcologyIntegration(unittest.TestCase):
    def setUp(self):
        # Create a temporary directory for test files
        self.test_dir = tempfile.mkdtemp()
        self.original_dir = os.getcwd()
        os.chdir(self.test_dir)
        
        # Create a minimal test file to simulate existing tests
        test_file_path = os.path.join(self.test_dir, 'test_sample.py')
        with open(test_file_path, 'w') as f:
            f.write("""
import unittest

class TestSample(unittest.TestCase):
    def test_sample(self):
        self.assertEqual(1 + 1, 2)

if __name__ == '__main__':
    unittest.main()
""")
        
        # Create a minimal test suite file
        suite_file_path = os.path.join(self.test_dir, 'test_suite.py')
        with open(suite_file_path, 'w') as f:
            f.write("""
import unittest

def load_tests(loader, tests, pattern):
    suite = unittest.TestSuite()
    suite.addTest(TestSample('test_sample'))
    return suite
""")

    def tearDown(self):
        os.chdir(self.original_dir)
        shutil.rmtree(self.test_dir)

    def test_full_ecology_cycle(self):
        # Step 1: Initialize the ecology engine
        engine_state = initialize_ecology_engine()
        
        # Verify engine initialization
        self.assertIsInstance(engine_state, dict)
        self.assertIn('initialized', engine_state)
        self.assertTrue(engine_state['initialized'])
        self.assertIn('config', engine_state)
        self.assertIn('test_directory', engine_state)
        self.assertEqual(engine_state['test_directory'], self.test_dir)
        
        # Step 2: Run test suite evolution
        result = evolve_fitness_landscape()
        
        # Verify pressure generation output
        self.assertIsInstance(result, dict)
        self.assertIn('fitness_scores', result)
        self.assertIn('population', result)
        self.assertIn('generation', result)
        self.assertIn('test_suite', result)
        
        # Step 3: Verify new tests are created and runnable
        test_suite = result['test_suite']
        self.assertIsInstance(test_suite, list)
        self.assertGreater(len(test_suite), 0)
        
        # Verify test suite contains valid test files
        for test_file in test_suite:
            self.assertTrue(os.path.exists(test_file))
            self.assertTrue(test_file.endswith('.py'))
            
            # Verify the test file is runnable
            try:
                spec = importlib.util.spec_from_file_location(
                    os.path.basename(test_file).replace('.py', ''),
                    test_file
                )
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                
                # Check that the module contains test classes
                has_test = False
                for name in dir(module):
                    obj = getattr(module, name)
                    if isinstance(obj, type) and issubclass(obj, unittest.TestCase):
                        has_test = True
                        break
                self.assertTrue(has_test, f"Test file {test_file} does not contain any test classes")
            except Exception as e:
                self.fail(f"Failed to load test file {test_file}: {e}")
        
        # Step 4: Check that the fitness landscape has changed
        # Get initial fitness landscape
        initial_fitness = result['fitness_scores']
        self.assertIsInstance(initial_fitness, dict)
        self.assertGreater(len(initial_fitness), 0)
        
        # Run evolution again to see if landscape changes
        result2 = evolve_fitness_landscape()
        new_fitness = result2['fitness_scores']
        
        # Verify fitness landscape has changed
        self.assertIsInstance(new_fitness, dict)
        self.assertGreater(len(new_fitness), 0)
        
        # Check that fitness values are different (landscape changed)
        fitness_changed = False
        for key in initial_fitness:
            if key in new_fitness:
                if initial_fitness[key] != new_fitness[key]:
                    fitness_changed = True
                    break
            else:
                fitness_changed = True
                break
        
        if not fitness_changed:
            # Check if new keys appeared
            for key in new_fitness:
                if key not in initial_fitness:
                    fitness_changed = True
                    break
        
        self.assertTrue(fitness_changed, "Fitness landscape did not change between generations")
        
        # Verify generation counter increases
        self.assertGreater(result2['generation'], result['generation'])
        
        # Step 5: Test execution - run the generated test suite
        test_loader = unittest.TestLoader()
        test_suite_obj = unittest.TestSuite()
        
        for test_file in test_suite:
            try:
                # Load the test module
                spec = importlib.util.spec_from_file_location(
                    os.path.basename(test_file).replace('.py', ''),
                    test_file
                )
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                
                # Load tests from module
                tests = test_loader.loadTestsFromModule(module)
                test_suite_obj.addTests(tests)
            except Exception as e:
                self.fail(f"Failed to load test file {test_file}: {e}")
        
        # Step 6: Result collection - run tests and collect results
        test_runner = unittest.TextTestRunner(verbosity=0)
        test_result = test_runner.run(test_suite_obj)
        
        # Verify test execution results
        self.assertIsNotNone(test_result)
        self.assertIsInstance(test_result, unittest.TestResult)
        
        # Check that tests were actually executed
        total_tests = test_result.testsRun
        self.assertGreater(total_tests, 0, "No tests were executed")
        
        # Verify result collection contains expected attributes
        self.assertTrue(hasattr(test_result, 'wasSuccessful'))
        self.assertTrue(hasattr(test_result, 'errors'))
        self.assertTrue(hasattr(test_result, 'failures'))
        
        # Step 7: Verify the ecology loop produces consistent results
        initial_count = len(test_suite)
        result3 = evolve_fitness_landscape()
        test_suite3 = result3['test_suite']
        
        # Test suite should maintain or grow (allow for one removal)
        self.assertGreaterEqual(len(test_suite3), initial_count - 1)
        
        # Verify generation counter increases
        self.assertGreater(result3['generation'], result2['generation'])

if __name__ == '__main__':
    unittest.main()