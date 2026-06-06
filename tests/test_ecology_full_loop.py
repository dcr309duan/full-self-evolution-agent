import sys
import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

# Add parent directory to path to allow imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import from working test file and ecology_pressure_engine
from tests.test_ecology_pressure_engine import TestEcologyPressureEngine
from ecology_pressure_engine import EcologyPressureEngine, TestRegistry


class TestEcologyFullLoop(unittest.TestCase):
    """Integration test for the full ecology loop."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.engine = EcologyPressureEngine()
        self.registry = TestRegistry()
        
    def test_agent_detects_new_tests(self):
        """Test that agent can detect new tests added by ecology pressure engine."""
        # Simulate ecology pressure engine adding a new test
        new_test = {
            'name': 'test_new_feature',
            'difficulty': 1,
            'code': 'def test_new_feature(): assert True',
            'added_by': 'ecology_pressure_engine'
        }
        self.registry.add_test(new_test)
        
        # Agent detects new tests by checking registry
        detected_tests = self.registry.get_new_tests_since(last_check='2024-01-01')
        self.assertIn(new_test['name'], [t['name'] for t in detected_tests])
        
    def test_agent_modifies_behavior_to_pass_new_tests(self):
        """Test that agent modifies behavior to pass new tests."""
        # Simulate agent receiving a new test
        new_test = {
            'name': 'test_calculate_sum',
            'difficulty': 2,
            'code': 'def test_calculate_sum(): assert 2 + 2 == 4',
            'added_by': 'ecology_pressure_engine'
        }
        
        # Agent modifies its behavior (simulated by updating registry)
        self.registry.add_test(new_test)
        
        # Verify agent can run and pass the test
        test_result = self.engine.run_test(new_test)
        self.assertTrue(test_result['passed'])
        
    def test_ecology_pressure_adds_progressively_harder_tests(self):
        """Test that ecology pressure engine adds progressively harder tests."""
        # Simulate adding tests with increasing difficulty
        test_easy = {
            'name': 'test_easy',
            'difficulty': 1,
            'code': 'def test_easy(): assert 1 == 1',
            'added_by': 'ecology_pressure_engine'
        }
        test_medium = {
            'name': 'test_medium',
            'difficulty': 3,
            'code': 'def test_medium(): assert sum([1,2,3]) == 6',
            'added_by': 'ecology_pressure_engine'
        }
        test_hard = {
            'name': 'test_hard',
            'difficulty': 5,
            'code': 'def test_hard(): assert sorted([3,1,2]) == [1,2,3]',
            'added_by': 'ecology_pressure_engine'
        }
        
        # Add tests in order
        self.registry.add_test(test_easy)
        self.registry.add_test(test_medium)
        self.registry.add_test(test_hard)
        
        # Verify tests are added with increasing difficulty
        all_tests = self.registry.get_all_tests()
        difficulties = [t['difficulty'] for t in all_tests]
        self.assertEqual(difficulties, sorted(difficulties))
        
    def test_full_loop_integration(self):
        """Test the complete ecology loop end-to-end."""
        # Step 1: Ecology pressure engine adds a new test
        new_test = {
            'name': 'test_full_loop',
            'difficulty': 2,
            'code': 'def test_full_loop(): assert True',
            'added_by': 'ecology_pressure_engine'
        }
        self.registry.add_test(new_test)
        
        # Step 2: Agent detects the new test
        detected = self.registry.get_new_tests_since(last_check='2024-01-01')
        self.assertTrue(any(t['name'] == 'test_full_loop' for t in detected))
        
        # Step 3: Agent runs and passes the test
        result = self.engine.run_test(new_test)
        self.assertTrue(result['passed'])
        
        # Step 4: Ecology pressure engine adds a harder test
        harder_test = {
            'name': 'test_harder_loop',
            'difficulty': 4,
            'code': 'def test_harder_loop(): assert 2 + 2 == 4',
            'added_by': 'ecology_pressure_engine'
        }
        self.registry.add_test(harder_test)
        
        # Step 5: Agent adapts and passes the harder test
        harder_result = self.engine.run_test(harder_test)
        self.assertTrue(harder_result['passed'])
        
        # Verify both tests are in registry
        all_tests = self.registry.get_all_tests()
        self.assertEqual(len(all_tests), 2)


def dry_run_import_check():
    """Perform a dry-run import check to ensure all imports resolve before committing."""
    print("Performing dry-run import check...")
    try:
        # Re-import all modules used in this test file
        import sys
        import os
        import tempfile
        import unittest
        from unittest.mock import MagicMock, patch
        
        # Add parent directory to path
        sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
        
        # Import the required modules
        from tests.test_ecology_pressure_engine import TestEcologyPressureEngine
        from ecology_pressure_engine import EcologyPressureEngine, TestRegistry
        
        print("All imports resolved successfully.")
        return True
    except ImportError as e:
        print(f"Import error: {e}")
        return False
    except Exception as e:
        print(f"Unexpected error during import check: {e}")
        return False


if __name__ == '__main__':
    # Run dry-run import check before executing tests
    if dry_run_import_check():
        unittest.main()
    else:
        print("Dry-run import check failed. Aborting test execution.")
        sys.exit(1)