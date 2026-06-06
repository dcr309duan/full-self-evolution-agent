import unittest
import os
import sys
import tempfile
import json

# Ensure the parent directory is on the path so we can import ecology_foundation
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ecology_foundation import TestSuiteManifest, CoverageAnalyzer, PressureRegistry


class TestEcologyFoundation(unittest.TestCase):
    """Test suite for ecology_foundation module."""

    def setUp(self):
        """Create a temporary directory with test files for testing."""
        self.temp_dir = tempfile.mkdtemp()
        self.original_dir = os.getcwd()
        os.chdir(self.temp_dir)

        # Create a known test file with a test purpose
        self.test_file_path = os.path.join(self.temp_dir, "test_example.py")
        with open(self.test_file_path, 'w') as f:
            f.write('''
import unittest

class TestExample(unittest.TestCase):
    """Test the example functionality."""
    
    def test_addition(self):
        """Test that addition works correctly."""
        self.assertEqual(1 + 1, 2)
    
    def test_subtraction(self):
        """Test that subtraction works correctly."""
        self.assertEqual(3 - 1, 2)
''')

        # Create another test file
        self.test_file_path2 = os.path.join(self.temp_dir, "test_another.py")
        with open(self.test_file_path2, 'w') as f:
            f.write('''
import unittest

class TestAnother(unittest.TestCase):
    """Test another functionality."""
    
    def test_multiplication(self):
        """Test that multiplication works correctly."""
        self.assertEqual(2 * 3, 6)
''')

        # Create a non-test file that should be ignored
        self.non_test_file = os.path.join(self.temp_dir, "helper.py")
        with open(self.non_test_file, 'w') as f:
            f.write('# This is not a test file\n')

    def tearDown(self):
        """Clean up temporary directory."""
        os.chdir(self.original_dir)
        import shutil
        shutil.rmtree(self.temp_dir)

    def test_test_suite_manifest_finds_test_files(self):
        """Test that TestSuiteManifest correctly finds test files."""
        manifest = TestSuiteManifest()
        found_files = manifest.find_test_files(self.temp_dir)
        
        # Should find exactly 2 test files
        self.assertEqual(len(found_files), 2)
        
        # Verify the found files are the ones we created
        found_basenames = [os.path.basename(f) for f in found_files]
        self.assertIn("test_example.py", found_basenames)
        self.assertIn("test_another.py", found_basenames)
        self.assertNotIn("helper.py", found_basenames)

    def test_test_suite_manifest_handles_empty_directory(self):
        """Test that TestSuiteManifest handles empty directories."""
        empty_dir = os.path.join(self.temp_dir, "empty")
        os.makedirs(empty_dir)
        
        manifest = TestSuiteManifest()
        found_files = manifest.find_test_files(empty_dir)
        self.assertEqual(len(found_files), 0)

    def test_coverage_analyzer_extracts_test_purposes(self):
        """Test that CoverageAnalyzer extracts at least one test purpose from a known test file."""
        analyzer = CoverageAnalyzer()
        purposes = analyzer.extract_test_purposes(self.test_file_path)
        
        # Should find at least one test purpose
        self.assertGreaterEqual(len(purposes), 1)
        
        # The first test purpose should be from test_addition
        first_purpose = purposes[0]
        self.assertIn("test_addition", first_purpose)
        self.assertIn("Test that addition works correctly", first_purpose)

    def test_coverage_analyzer_handles_file_without_tests(self):
        """Test that CoverageAnalyzer handles files without test methods."""
        analyzer = CoverageAnalyzer()
        purposes = analyzer.extract_test_purposes(self.non_test_file)
        self.assertEqual(len(purposes), 0)

    def test_pressure_registry_add_list_pressures(self):
        """Test that PressureRegistry can add and list pressures."""
        registry = PressureRegistry()
        
        # Initially should be empty
        self.assertEqual(len(registry.list_pressures()), 0)
        
        # Add a pressure
        registry.add_pressure("test_pressure", {"value": 42, "unit": "test"})
        
        # Should now have one pressure
        pressures = registry.list_pressures()
        self.assertEqual(len(pressures), 1)
        self.assertEqual(pressures[0]["name"], "test_pressure")
        self.assertEqual(pressures[0]["data"]["value"], 42)

    def test_pressure_registry_add_multiple_pressures(self):
        """Test that PressureRegistry can add multiple pressures."""
        registry = PressureRegistry()
        
        registry.add_pressure("pressure_1", {"value": 1})
        registry.add_pressure("pressure_2", {"value": 2})
        registry.add_pressure("pressure_3", {"value": 3})
        
        pressures = registry.list_pressures()
        self.assertEqual(len(pressures), 3)
        self.assertEqual(pressures[0]["name"], "pressure_1")
        self.assertEqual(pressures[1]["name"], "pressure_2")
        self.assertEqual(pressures[2]["name"], "pressure_3")

    def test_pressure_registry_clear_pressures(self):
        """Test that PressureRegistry can clear all pressures."""
        registry = PressureRegistry()
        
        registry.add_pressure("test_pressure", {"value": 42})
        self.assertEqual(len(registry.list_pressures()), 1)
        
        registry.clear_pressures()
        self.assertEqual(len(registry.list_pressures()), 0)


if __name__ == '__main__':
    unittest.main()