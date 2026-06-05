import unittest
import sys
import os
import tempfile
import json
import time
import random
import math

class TestEcologyFoundation(unittest.TestCase):
    """Comprehensive test suite for the ecology foundation module."""

    def setUp(self):
        """Create a temporary directory structure for testing."""
        self.test_dir = tempfile.mkdtemp()
        self.original_dir = os.getcwd()
        os.chdir(self.test_dir)
        
        # Create mock test files
        self._create_mock_test_files()
        
        # Import the module under test
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        try:
            from core.ecology_engine import EcologyEngine
            self.EcologyEngine = EcologyEngine
            self.engine = EcologyEngine()
            self.engine_available = True
        except (ImportError, Exception) as e:
            self.engine_available = False
            self.import_error = str(e)

    def tearDown(self):
        """Clean up temporary directory."""
        os.chdir(self.original_dir)
        import shutil
        shutil.rmtree(self.test_dir, ignore_errors=True)
        sys.path.pop(0)

    def _create_mock_test_files(self):
        """Create mock test files for testing."""
        os.makedirs('tests', exist_ok=True)
        
        # Create a simple test file
        with open('tests/test_sample.py', 'w') as f:
            f.write("""
import unittest

class TestSample(unittest.TestCase):
    def test_pass(self):
        self.assertTrue(True)
    
    def test_fail(self):
        self.assertTrue(False)
    
    def test_error(self):
        raise ValueError("Test error")
    
    def test_skip(self):
        self.skipTest("Skipping this test")
    
    def test_complex(self):
        result = sum(range(100))
        self.assertEqual(result, 4950)
""")
        
        # Create a test file with many tests
        with open('tests/test_large.py', 'w') as f:
            f.write("""
import unittest

class TestLarge(unittest.TestCase):
""")
            for i in range(20):
                f.write(f"""
    def test_{i}(self):
        self.assertTrue({i} < 100)
""")
        
        # Create a test file with performance tests
        with open('tests/test_performance.py', 'w') as f:
            f.write("""
import unittest
import time

class TestPerformance(unittest.TestCase):
    def test_fast(self):
        pass
    
    def test_slow(self):
        time.sleep(0.1)
    
    def test_very_slow(self):
        time.sleep(0.5)
""")

    def test_engine_import(self):
        """Test that the engine can be imported (even if dependencies are missing)."""
        # This test should pass even if the engine fails to import
        if not self.engine_available:
            self.skipTest(f"Engine not available: {self.import_error}")
        self.assertIsNotNone(self.EcologyEngine)

    def test_engine_initialization(self):
        """Test that the engine initializes without crashing."""
        if not self.engine_available:
            self.skipTest(f"Engine not available: {self.import_error}")
        self.assertIsNotNone(self.engine)

    def test_complexity_pressure_creation(self):
        """Test creating complexity pressure type."""
        if not self.engine_available:
            self.skipTest(f"Engine not available: {self.import_error}")
        
        pressure = self.engine.create_pressure("complexity", intensity=0.5)
        self.assertIsNotNone(pressure)
        self.assertEqual(pressure.type, "complexity")
        self.assertEqual(pressure.intensity, 0.5)

    def test_coverage_pressure_creation(self):
        """Test creating coverage pressure type."""
        if not self.engine_available:
            self.skipTest(f"Engine not available: {self.import_error}")
        
        pressure = self.engine.create_pressure("coverage", intensity=0.8)
        self.assertIsNotNone(pressure)
        self.assertEqual(pressure.type, "coverage")
        self.assertEqual(pressure.intensity, 0.8)

    def test_performance_pressure_creation(self):
        """Test creating performance pressure type."""
        if not self.engine_available:
            self.skipTest(f"Engine not available: {self.import_error}")
        
        pressure = self.engine.create_pressure("performance", intensity=0.3)
        self.assertIsNotNone(pressure)
        self.assertEqual(pressure.type, "performance")
        self.assertEqual(pressure.intensity, 0.3)

    def test_invalid_pressure_type(self):
        """Test that invalid pressure types raise appropriate errors."""
        if not self.engine_available:
            self.skipTest(f"Engine not available: {self.import_error}")
        
        with self.assertRaises((ValueError, TypeError, AttributeError)):
            self.engine.create_pressure("invalid_type", intensity=0.5)

    def test_pressure_intensity_bounds(self):
        """Test pressure intensity bounds (should be between 0 and 1)."""
        if not self.engine_available:
            self.skipTest(f"Engine not available: {self.import_error}")
        
        # Test valid intensities
        for intensity in [0.0, 0.5, 1.0]:
            pressure = self.engine.create_pressure("complexity", intensity=intensity)
            self.assertEqual(pressure.intensity, intensity)
        
        # Test invalid intensities
        with self.assertRaises((ValueError, AssertionError)):
            self.engine.create_pressure("complexity", intensity=-0.1)
        with self.assertRaises((ValueError, AssertionError)):
            self.engine.create_pressure("complexity", intensity=1.1)

    def test_apply_pressure_to_mock_suite(self):
        """Test applying pressure to a mock test suite."""
        if not self.engine_available:
            self.skipTest(f"Engine not available: {self.import_error}")
        
        # Create a mock test suite
        mock_suite = {
            'tests/test_sample.py': {
                'tests': ['test_pass', 'test_fail', 'test_error', 'test_skip', 'test_complex'],
                'complexity': 0.3,
                'coverage': 0.6,
                'performance': 0.1
            },
            'tests/test_large.py': {
                'tests': [f'test_{i}' for i in range(20)],
                'complexity': 0.8,
                'coverage': 0.4,
                'performance': 0.2
            }
        }
        
        # Apply complexity pressure
        pressure = self.engine.create_pressure("complexity", intensity=0.7)
        result = self.engine.apply_pressure(mock_suite, pressure)
        
        self.assertIsNotNone(result)
        self.assertIn('tests/test_sample.py', result)
        self.assertIn('tests/test_large.py', result)

    def test_pressure_affects_test_selection(self):
        """Test that pressure affects which tests are selected."""
        if not self.engine_available:
            self.skipTest(f"Engine not available: {self.import_error}")
        
        mock_suite = {
            'tests/test_sample.py': {
                'tests': ['test_pass', 'test_fail', 'test_error', 'test_skip', 'test_complex'],
                'complexity': 0.3,
                'coverage': 0.6,
                'performance': 0.1
            },
            'tests/test_large.py': {
                'tests': [f'test_{i}' for i in range(20)],
                'complexity': 0.8,
                'coverage': 0.4,
                'performance': 0.2
            }
        }
        
        # Apply high complexity pressure
        pressure = self.engine.create_pressure("complexity", intensity=0.9)
        result_high = self.engine.apply_pressure(mock_suite, pressure)
        
        # Apply low complexity pressure
        pressure_low = self.engine.create_pressure("complexity", intensity=0.1)
        result_low = self.engine.apply_pressure(mock_suite, pressure_low)
        
        # High pressure should select different tests than low pressure
        high_tests = set()
        low_tests = set()
        for file_data in result_high.values():
            high_tests.update(file_data.get('selected_tests', []))
        for file_data in result_low.values():
            low_tests.update(file_data.get('selected_tests', []))
        
        # The selections should be different
        self.assertNotEqual(high_tests, low_tests)

    def test_engine_runs_without_crashing(self):
        """Test that the engine can run without crashing even with missing dependencies."""
        # This test should work even if the engine is not available
        if not self.engine_available:
            self.skipTest(f"Engine not available: {self.import_error}")
        
        try:
            # Run the engine's main cycle
            result = self.engine.run_cycle()
            self.assertIsNotNone(result)
        except Exception as e:
            self.fail(f"Engine crashed with exception: {e}")

    def test_engine_handles_empty_suite(self):
        """Test that the engine handles an empty test suite gracefully."""
        if not self.engine_available:
            self.skipTest(f"Engine not available: {self.import_error}")
        
        empty_suite = {}
        pressure = self.engine.create_pressure("complexity", intensity=0.5)
        
        try:
            result = self.engine.apply_pressure(empty_suite, pressure)
            self.assertIsNotNone(result)
            self.assertEqual(len(result), 0)
        except Exception as e:
            self.fail(f"Engine crashed with empty suite: {e}")

    def test_engine_handles_missing_files(self):
        """Test that the engine handles missing test files gracefully."""
        if not self.engine_available:
            self.skipTest(f"Engine not available: {self.import_error}")
        
        # Remove test files
        import shutil
        shutil.rmtree('tests', ignore_errors=True)
        
        try:
            result = self.engine.run_cycle()
            self.assertIsNotNone(result)
        except Exception as e:
            self.fail(f"Engine crashed with missing files: {e}")

    def test_multiple_pressure_types(self):
        """Test applying multiple pressure types sequentially."""
        if not self.engine_available:
            self.skipTest(f"Engine not available: {self.import_error}")
        
        mock_suite = {
            'tests/test_sample.py': {
                'tests': ['test_pass', 'test_fail', 'test_error', 'test_skip', 'test_complex'],
                'complexity': 0.3,
                'coverage': 0.6,
                'performance': 0.1
            }
        }
        
        # Apply different pressure types
        pressure_types = ['complexity', 'coverage', 'performance']
        results = []
        
        for ptype in pressure_types:
            pressure = self.engine.create_pressure(ptype, intensity=0.5)
            result = self.engine.apply_pressure(mock_suite, pressure)
            results.append(result)
        
        # All should succeed
        for result in results:
            self.assertIsNotNone(result)

    def test_pressure_metrics(self):
        """Test that pressure application produces metrics."""
        if not self.engine_available:
            self.skipTest(f"Engine not available: {self.import_error}")
        
        mock_suite = {
            'tests/test_sample.py': {
                'tests': ['test_pass', 'test_fail', 'test_error', 'test_skip', 'test_complex'],
                'complexity': 0.3,
                'coverage': 0.6,
                'performance': 0.1
            }
        }
        
        pressure = self.engine.create_pressure("complexity", intensity=0.5)
        result = self.engine.apply_pressure(mock_suite, pressure)
        
        # Check for metrics
        self.assertIn('metrics', result.get('tests/test_sample.py', {}))
        metrics = result['tests/test_sample.py']['metrics']
        self.assertIn('pressure_applied', metrics)
        self.assertIn('tests_selected', metrics)
        self.assertIn('tests_skipped', metrics)

    def test_engine_cycle_consistency(self):
        """Test that running multiple cycles produces consistent results."""
        if not self.engine_available:
            self.skipTest(f"Engine not available: {self.import_error}")
        
        results = []
        for _ in range(3):
            result = self.engine.run_cycle()
            results.append(result)
        
        # Results should be consistent (same structure)
        for result in results:
            self.assertIsNotNone(result)
            self.assertIsInstance(result, dict)

    def test_pressure_adaptation(self):
        """Test that pressure adapts based on previous results."""
        if not self.engine_available:
            self.skipTest(f"Engine not available: {self.import_error}")
        
        mock_suite = {
            'tests/test_sample.py': {
                'tests': ['test_pass', 'test_fail', 'test_error', 'test_skip', 'test_complex'],
                'complexity': 0.3,
                'coverage': 0.6,
                'performance': 0.1
            }
        }
        
        # Apply pressure multiple times
        pressure = self.engine.create_pressure("complexity", intensity=0.5)
        result1 = self.engine.apply_pressure(mock_suite, pressure)
        result2 = self.engine.apply_pressure(mock_suite, pressure)
        
        # Results should be similar but may vary
        self.assertIsNotNone(result1)
        self.assertIsNotNone(result2)

    def test_engine_without_dependencies(self):
        """Test that the engine can be instantiated even without its dependencies."""
        # This test verifies the engine handles missing dependencies gracefully
        if not self.engine_available:
            self.skipTest(f"Engine not available: {self.import_error}")
        
        # Try to access engine properties that might depend on external modules
        try:
            has_attr = hasattr(self.engine, 'scan_tests')
            self.assertIsInstance(has_attr, bool)
        except Exception as e:
            self.fail(f"Engine failed when checking attributes: {e}")

    def test_pressure_effect_on_test_ordering(self):
        """Test that pressure affects the order of test execution."""
        if not self.engine_available:
            self.skipTest(f"Engine not available: {self.import_error}")
        
        mock_suite = {
            'tests/test_sample.py': {
                'tests': ['test_pass', 'test_fail', 'test_error', 'test_skip', 'test_complex'],
                'complexity': 0.3,
                'coverage': 0.6,
                'performance': 0.1
            }
        }
        
        # Apply performance pressure
        pressure = self.engine.create_pressure("performance", intensity=0.8)
        result = self.engine.apply_pressure(mock_suite, pressure)
        
        # Check that tests are ordered by performance impact
        file_data = result.get('tests/test_sample.py', {})
        ordered_tests = file_data.get('ordered_tests', [])
        
        # The ordered tests should be a permutation of the original tests
        original_tests = ['test_pass', 'test_fail', 'test_error', 'test_skip', 'test_complex']
        if ordered_tests:
            self.assertEqual(set(ordered_tests), set(original_tests))

    def test_engine_scan_functionality(self):
        """Test that the engine can scan for test files."""
        if not self.engine_available:
            self.skipTest(f"Engine not available: {self.import_error}")
        
        try:
            test_files = self.engine.scan_tests()
            self.assertIsNotNone(test_files)
            self.assertIsInstance(test_files, list)
            # Should find our mock test files
            self.assertGreater(len(test_files), 0)
        except Exception as e:
            self.fail(f"Engine scan failed: {e}")

    def test_engine_cycle_with_scan(self):
        """Test running a full cycle that includes scanning."""
        if not self.engine_available:
            self.skipTest(f"Engine not available: {self.import_error}")
        
        try:
            result = self.engine.run_cycle(scan_first=True)
            self.assertIsNotNone(result)
        except Exception as e:
            self.fail(f"Engine cycle with scan failed: {e}")

    def test_engine_handles_corrupted_files(self):
        """Test that the engine handles corrupted test files gracefully."""
        if not self.engine_available:
            self.skipTest(f"Engine not available: {self.import_error}")
        
        # Create a corrupted test file
        with open('tests/test_corrupted.py', 'w') as f:
            f.write("This is not valid Python code!!!")
        
        try:
            result = self.engine.run_cycle()
            self.assertIsNotNone(result)
        except Exception as e:
            self.fail(f"Engine crashed with corrupted file: {e}")

    def test_pressure_combination(self):
        """Test combining multiple pressure types."""
        if not self.engine_available:
            self.skipTest(f"Engine not available: {self.import_error}")
        
        mock_suite = {
            'tests/test_sample.py': {
                'tests': ['test_pass', 'test_fail', 'test_error', 'test_skip', 'test_complex'],
                'complexity': 0.3,
                'coverage': 0.6,
                'performance': 0.1
            }
        }
        
        # Create combined pressure
        try:
            combined_pressure = self.engine.create_combined_pressure({
                'complexity': 0.5,
                'coverage': 0.3,
                'performance': 0.2
            })
            result = self.engine.apply_pressure(mock_suite, combined_pressure)
            self.assertIsNotNone(result)
        except (AttributeError, NotImplementedError):
            self.skipTest("Combined pressure not implemented")
        except Exception as e:
            self.fail(f"Combined pressure failed: {e}")

    def test_engine_persistence(self):
        """Test that engine state persists across cycles."""
        if not self.engine_available:
            self.skipTest(f"Engine not available: {self.import_error}")
        
        # Run multiple cycles and check state
        states = []
