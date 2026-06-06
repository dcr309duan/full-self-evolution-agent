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
            from core.ecology_foundation import TestSuiteEvolver, PressureGenerator, FitnessLandscapeModifier
            self.TestSuiteEvolver = TestSuiteEvolver
            self.PressureGenerator = PressureGenerator
            self.FitnessLandscapeModifier = FitnessLandscapeModifier
            self.evolver = TestSuiteEvolver()
            self.pressure_gen = PressureGenerator()
            self.landscape_modifier = FitnessLandscapeModifier()
            self.foundation_available = True
        except (ImportError, Exception) as e:
            self.foundation_available = False
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
        
        # Create a manifest file for testing
        os.makedirs('manifest', exist_ok=True)
        with open('manifest/test_requirements.json', 'w') as f:
            json.dump({
                "requirements": [
                    {"id": "REQ-001", "description": "Basic functionality test", "priority": "high"},
                    {"id": "REQ-002", "description": "Performance benchmark", "priority": "medium"}
                ]
            }, f)

    def test_foundation_import(self):
        """Test that the foundation module can be imported."""
        if not self.foundation_available:
            self.skipTest(f"Foundation not available: {self.import_error}")
        self.assertIsNotNone(self.TestSuiteEvolver)
        self.assertIsNotNone(self.PressureGenerator)
        self.assertIsNotNone(self.FitnessLandscapeModifier)

    def test_evolver_initialization(self):
        """Test that TestSuiteEvolver initializes without crashing."""
        if not self.foundation_available:
            self.skipTest(f"Foundation not available: {self.import_error}")
        self.assertIsNotNone(self.evolver)

    def test_pressure_generator_initialization(self):
        """Test that PressureGenerator initializes without crashing."""
        if not self.foundation_available:
            self.skipTest(f"Foundation not available: {self.import_error}")
        self.assertIsNotNone(self.pressure_gen)

    def test_landscape_modifier_initialization(self):
        """Test that FitnessLandscapeModifier initializes without crashing."""
        if not self.foundation_available:
            self.skipTest(f"Foundation not available: {self.import_error}")
        self.assertIsNotNone(self.landscape_modifier)

    def test_evolver_list_test_files(self):
        """Test that TestSuiteEvolver can list test files."""
        if not self.foundation_available:
            self.skipTest(f"Foundation not available: {self.import_error}")
        
        test_files = self.evolver.list_test_files()
        self.assertIsNotNone(test_files)
        self.assertIsInstance(test_files, list)
        self.assertGreater(len(test_files), 0)
        # Should find our mock test files
        self.assertIn('tests/test_sample.py', test_files)
        self.assertIn('tests/test_large.py', test_files)
        self.assertIn('tests/test_performance.py', test_files)

    def test_evolver_list_test_files_empty(self):
        """Test that TestSuiteEvolver handles empty directory."""
        if not self.foundation_available:
            self.skipTest(f"Foundation not available: {self.import_error}")
        
        # Remove test files
        import shutil
        shutil.rmtree('tests', ignore_errors=True)
        
        test_files = self.evolver.list_test_files()
        self.assertIsNotNone(test_files)
        self.assertIsInstance(test_files, list)
        self.assertEqual(len(test_files), 0)

    def test_evolver_list_test_files_with_pattern(self):
        """Test that TestSuiteEvolver can filter test files by pattern."""
        if not self.foundation_available:
            self.skipTest(f"Foundation not available: {self.import_error}")
        
        test_files = self.evolver.list_test_files(pattern="*sample*")
        self.assertIsNotNone(test_files)
        self.assertIsInstance(test_files, list)
        self.assertIn('tests/test_sample.py', test_files)
        self.assertNotIn('tests/test_large.py', test_files)
        self.assertNotIn('tests/test_performance.py', test_files)

    def test_pressure_generator_create_scenario_template(self):
        """Test that PressureGenerator can create a new test scenario template."""
        if not self.foundation_available:
            self.skipTest(f"Foundation not available: {self.import_error}")
        
        template = self.pressure_gen.create_test_scenario_template(
            name="performance_regression",
            description="Test for performance regression under load",
            pressure_type="performance",
            intensity=0.7
        )
        self.assertIsNotNone(template)
        self.assertIsInstance(template, dict)
        self.assertIn('name', template)
        self.assertIn('description', template)
        self.assertIn('pressure_type', template)
        self.assertIn('intensity', template)
        self.assertEqual(template['name'], "performance_regression")
        self.assertEqual(template['description'], "Test for performance regression under load")
        self.assertEqual(template['pressure_type'], "performance")
        self.assertEqual(template['intensity'], 0.7)

    def test_pressure_generator_create_scenario_template_with_metrics(self):
        """Test that PressureGenerator creates template with metrics configuration."""
        if not self.foundation_available:
            self.skipTest(f"Foundation not available: {self.import_error}")
        
        template = self.pressure_gen.create_test_scenario_template(
            name="coverage_analysis",
            description="Analyze code coverage under different conditions",
            pressure_type="coverage",
            intensity=0.5,
            metrics=["line_coverage", "branch_coverage", "function_coverage"]
        )
        self.assertIsNotNone(template)
        self.assertIn('metrics', template)
        self.assertEqual(template['metrics'], ["line_coverage", "branch_coverage", "function_coverage"])

    def test_pressure_generator_create_scenario_template_defaults(self):
        """Test that PressureGenerator creates template with sensible defaults."""
        if not self.foundation_available:
            self.skipTest(f"Foundation not available: {self.import_error}")
        
        template = self.pressure_gen.create_test_scenario_template(
            name="basic_test",
            description="Basic test scenario"
        )
        self.assertIsNotNone(template)
        self.assertIn('pressure_type', template)
        self.assertIn('intensity', template)
        # Should have default values
        self.assertIsNotNone(template['pressure_type'])
        self.assertIsNotNone(template['intensity'])

    def test_pressure_generator_create_scenario_template_invalid_name(self):
        """Test that PressureGenerator handles invalid template names."""
        if not self.foundation_available:
            self.skipTest(f"Foundation not available: {self.import_error}")
        
        with self.assertRaises((ValueError, TypeError)):
            self.pressure_gen.create_test_scenario_template(
                name="",
                description="Invalid name"
            )

    def test_landscape_modifier_add_test_requirement(self):
        """Test that FitnessLandscapeModifier can add a new test requirement to the manifest."""
        if not self.foundation_available:
            self.skipTest(f"Foundation not available: {self.import_error}")
        
        new_requirement = {
            "id": "REQ-003",
            "description": "New integration test requirement",
            "priority": "high"
        }
        
        result = self.landscape_modifier.add_test_requirement(
            manifest_path="manifest/test_requirements.json",
            requirement=new_requirement
        )
        self.assertTrue(result)
        
        # Verify the requirement was added
        with open("manifest/test_requirements.json", 'r') as f:
            manifest = json.load(f)
        
        self.assertIn("requirements", manifest)
        requirements = manifest["requirements"]
        self.assertEqual(len(requirements), 3)
        self.assertIn(new_requirement, requirements)

    def test_landscape_modifier_add_test_requirement_multiple(self):
        """Test that FitnessLandscapeModifier can add multiple requirements."""
        if not self.foundation_available:
            self.skipTest(f"Foundation not available: {self.import_error}")
        
        requirements_to_add = [
            {"id": "REQ-003", "description": "Requirement three", "priority": "high"},
            {"id": "REQ-004", "description": "Requirement four", "priority": "low"}
        ]
        
        for req in requirements_to_add:
            result = self.landscape_modifier.add_test_requirement(
                manifest_path="manifest/test_requirements.json",
                requirement=req
            )
            self.assertTrue(result)
        
        # Verify all requirements were added
        with open("manifest/test_requirements.json", 'r') as f:
            manifest = json.load(f)
        
        self.assertEqual(len(manifest["requirements"]), 4)

    def test_landscape_modifier_add_test_requirement_duplicate(self):
        """Test that FitnessLandscapeModifier handles duplicate requirements."""
        if not self.foundation_available:
            self.skipTest(f"Foundation not available: {self.import_error}")
        
        requirement = {"id": "REQ-001", "description": "Duplicate", "priority": "high"}
        
        # Adding a duplicate should either fail or update
        try:
            result = self.landscape_modifier.add_test_requirement(
                manifest_path="manifest/test_requirements.json",
                requirement=requirement
            )
            # If it succeeds, check that it was handled appropriately
            with open("manifest/test_requirements.json", 'r') as f:
                manifest = json.load(f)
            # Should still have 2 requirements (no duplicate added)
            self.assertEqual(len(manifest["requirements"]), 2)
        except (ValueError, KeyError):
            # Duplicate rejection is also acceptable
            pass

    def test_landscape_modifier_add_test_requirement_invalid(self):
        """Test that FitnessLandscapeModifier handles invalid requirements."""
        if not self.foundation_available:
            self.skipTest(f"Foundation not available: {self.import_error}")
        
        with self.assertRaises((ValueError, TypeError, KeyError)):
            self.landscape_modifier.add_test_requirement(
                manifest_path="manifest/test_requirements.json",
                requirement={"invalid": "data"}
            )

    def test_landscape_modifier_add_test_requirement_missing_manifest(self):
        """Test that FitnessLandscapeModifier handles missing manifest file."""
        if not self.foundation_available:
            self.skipTest(f"Foundation not available: {self.import_error}")
        
        requirement = {"id": "REQ-005", "description": "New requirement", "priority": "medium"}
        
        # Should create the manifest if it doesn't exist
        result = self.landscape_modifier.add_test_requirement(
            manifest_path="manifest/new_manifest.json",
            requirement=requirement
        )
        self.assertTrue(result)
        
        # Verify the new manifest was created
        self.assertTrue(os.path.exists("manifest/new_manifest.json"))
        with open("manifest/new_manifest.json", 'r') as f:
            manifest = json.load(f)
        self.assertIn("requirements", manifest)
        self.assertEqual(len(manifest["requirements"]), 1)

    def test_evolver_list_test_files_with_manifest(self):
        """Test that TestSuiteEvolver can list test files and consider manifest."""
        if not self.foundation_available:
            self.skipTest(f"Foundation not available: {self.import_error}")
        
        test_files = self.evolver.list_test_files(manifest_path="manifest/test_requirements.json")
        self.assertIsNotNone(test_files)
        self.assertIsInstance(test_files, list)
        # Should still find our test files
        self.assertGreater(len(test_files), 0)

    def test_pressure_generator_create_scenario_template_with_manifest(self):
        """Test that PressureGenerator creates template that can be added to manifest."""
        if not self.foundation_available:
            self.skipTest(f"Foundation not available: {self.import_error}")
        
        template = self.pressure_gen.create_test_scenario_template(
            name="manifest_integration",
            description="Test that integrates with manifest",
            pressure_type="complexity",
            intensity=0.8
        )
        
        # Add the template as a requirement to the manifest
        requirement = {
            "id": "REQ-INTEGRATION",
            "description": template['description'],
            "priority": "high",
            "template": template
        }
        
        result = self.landscape_modifier.add_test_requirement(
            manifest_path="manifest/test_requirements.json",
            requirement=requirement
        )
        self.assertTrue(result)
        
        # Verify the integration
        with open("manifest/test_requirements.json", 'r') as f:
            manifest = json.load(f)
        
        self.assertEqual(len(manifest["requirements"]), 3)
        self.assertIn(requirement, manifest["requirements"])

    def test_evolver_list_test_files_with_custom_directory(self):
        """Test that TestSuiteEvolver can list test files from custom directory."""
        if not self.foundation_available:
            self.skipTest(f"Foundation not available: {self.import_error}")
        
        # Create additional test directory
        os.makedirs('custom_tests', exist_ok=True)
        with open('custom_tests/test_custom.py', 'w') as f:
            f.write("""
import unittest

class TestCustom(unittest.TestCase):
    def test_custom(self):
        self.assertTrue(True)
""")
        
        test_files = self.evolver.list_test_files(directory='custom_tests')
        self.assertIsNotNone(test_files)
        self.assertIn('custom_tests/test_custom.py', test_files)
        self.assertNotIn('tests/test_sample.py', test_files)

    def test_pressure_generator_create_scenario_template_with_parameters(self):
        """Test that PressureGenerator creates template with custom parameters."""
        if not self.foundation_available:
            self.skipTest(f"Foundation not available: {self.import_error}")
        
        template = self.pressure_gen.create_test_scenario_template(
            name="parameterized_test",
            description="Test with custom parameters",
            pressure_type="coverage",
            intensity=0.6,
            parameters={
                "threshold": 0.8,
                "iterations": 100,
                "mode": "aggressive"
            }
        )
        self.assertIsNotNone(template)
        self.assertIn('parameters', template)
        self.assertEqual(template['parameters']['threshold'], 0.8)
        self.assertEqual(template['parameters']['iterations'], 100)
        self.assertEqual(template['parameters']['mode'], "aggressive")

    def test_landscape_modifier_add_test_requirement_with_priority(self):
        """Test that FitnessLandscapeModifier handles priority correctly."""
        if not self.foundation_available:
            self.skipTest(f"Foundation not available: {self.import_error}")
        
        requirements = [
            {"id": "REQ-HIGH", "description": "High priority", "priority": "high"},
            {"id": "REQ-MED", "description": "Medium priority", "priority": "medium"},
            {"id": "REQ-LOW", "description": "Low priority", "priority": "low"}
        ]
        
        for req in requirements:
            result = self.landscape_modifier.add_test_requirement(
                manifest_path="manifest/test_requirements.json",
                requirement=req
            )
            self.assertTrue(result)
        
        # Verify all requirements were added
        with open("manifest/test_requirements.json", 'r') as f:
            manifest = json.load(f)
        
        self.assertEqual(len(manifest["requirements"]), 5)

    def test_evolver_list_test_files_after_modification(self):
        """Test that TestSuiteEvolver can list test files after manifest modification."""
        if not self.foundation_available:
            self.skipTest(f"Foundation not available: {self.import_error}")
        
        # First, list test files
        initial_files = self.evolver.list_test_files()
        
        # Add a new test file
        with open('tests/test_new.py', 'w') as f:
            f.write("""
import unittest

class TestNew(unittest.TestCase):
    def test_new(self):
        self.assertTrue(True)
""")
        
        # List test files again
        updated_files = self.evolver.list_test_files()
        
        # Should have one more file
        self.assertEqual(len(updated_files), len(initial_files) + 1)
        self.assertIn('tests/test_new.py', updated_files)

    def test_pressure_generator_create_scenario_template_validation(self):
        """Test that PressureGenerator validates template parameters."""
        if not self.foundation_available:
            self.skipTest(f"Foundation not available: {self.import_error}")
        
        # Test with invalid intensity
        with self.assertRaises((ValueError, AssertionError)):
            self.pressure_gen.create_test_scenario_template(
                name="invalid",
                description="Invalid intensity",
                pressure_type="performance",
                intensity=1.5
            )
        
        # Test with negative intensity
        with self.assertRaises((ValueError, AssertionError)):
            self.pressure_gen.create_test_scenario_template(
                name="negative",
                description="Negative intensity",
                pressure_type="performance",
                intensity=-0.1
            )

    def test_landscape_modifier_add_test_requirement_manifest_update(self):
        """Test that FitnessLandscapeModifier updates manifest correctly."""
        if not self.foundation_available:
            self.skipTest(f"Foundation not available: {self.import_error}")
        
        # Add multiple requirements
        for i in range(3, 6):
            req = {
                "id": f"REQ-{i:03d}",
                "description": f"Requirement {i}",
                "priority": "medium"
            }
            self.landscape_modifier.add_test_requirement(
                manifest_path="manifest/test_requirements.json",
                requirement=req
            )
        
        # Verify the manifest structure
        with open("manifest/test_requirements.json", 'r') as f:
            manifest = json.load(f)
        
        self.assertIn("requirements", manifest)
        self.assertEqual(len(manifest["requirements"]), 5)
        
        # Verify all IDs are unique
        ids = [req["id"] for req in manifest["requirements"]]
        self.assertEqual(len(ids), len(set(ids)))

    def test_integration_workflow(self):
        """Test the complete workflow: list files, create template, add requirement."""
        if not self.foundation_available:
            self.skipTest(f"Foundation not available: {self.import_error}")
        
        # Step 1: List test files
        test_files = self.evolver.list_test_files()
        self.assertGreater(len(test_files), 0)
        
        # Step 2: Create a test scenario template
        template = self.pressure_gen.create_test_scenario_template(
            name="integration_test",
            description="Integration test scenario",
            pressure_type="complexity",
            intensity=0.5
        )
        self.assertIsNotNone(template)
        
        # Step 3: Add a new test requirement to the manifest
        requirement = {
            "id": "REQ-INTEGRATION",
            "description": template['description'],
            "priority": "high",
            "template_name": template['name']
        }
        
        result = self.landscape_modifier.add_test_requirement(
            manifest_path="manifest/test_requirements.json",
            requirement=requirement
        )
        self.assertTrue(result)
        
        # Verify the complete workflow
        with open("manifest/test_requirements.json", 'r') as f:
            manifest = json.load(f)
        
        self.assertEqual(len(manifest["requirements"]), 3)
        self.assertIn(requirement, manifest["requirements"])

    def test_foundation_handles_missing_directories(self):
        """Test that foundation classes handle missing directories gracefully."""
        if not self.foundation_available:
            self.skipTest(f"Foundation not available: {self.import_error}")
        
        # Test with non-existent directory
        test_files = self.evolver.list_test_files(directory="nonexistent")
        self.assertIsNotNone(test_files)
        self.assertEqual(len(test_files), 0)
        
        # Test with non-existent manifest
        with self.assertRaises((FileNotFoundError, IOError)):
            self.landscape_modifier.add_test_requirement(
                manifest_path="nonexistent/manifest.json",
                requirement={"id": "REQ-001", "description": "Test", "priority": "high"}
            )

    def test_foundation_consistency(self):
        """Test that foundation classes maintain consistency across operations."""
        if not self.foundation_available:
            self.skipTest(f"Foundation not available: {self.import_error}")
        
        # Get initial state
        initial_files = self.evolver.list_test_files()
        
        # Create template and add requirement
        template = self.pressure_gen.create_test_scenario_template(
            name="consistency_test",
            description="Consistency test",
            pressure_type="coverage",
            intensity=0.4
        )
        
        requirement = {
            "id": "REQ-CONSISTENCY",
            "description": template['description'],
            "priority": "medium"
        }
        
        self.landscape_modifier.add_test_requirement(
            manifest_path="manifest/test_requirements.json",
            requirement=requirement
        )
        
        # Verify test files are unchanged
        updated_files = self.evolver.list_test_files()
        self.assertEqual(initial_files, updated_files)
        
        # Verify manifest was updated
        with open("manifest/test_requirements.json", 'r') as f:
            manifest = json.load(f)
        self.assertEqual(len(manifest["requirements"]), 3)

    def test_foundation_error_handling(self):
        """Test that foundation classes handle errors gracefully."""
        if not self.foundation_available:
            self.skipTest(f"Foundation not available: {self.import_error}")
        
        # Test with invalid pattern
        test_files = self.evolver.list_test_files(pattern="[invalid")
        self.assertIsNotNone(test_files)
        self.assertIsInstance(test_files, list)
        
        # Test with invalid manifest path
        with self.assertRaises((FileNotFoundError, IOError, ValueError)):
            self.landscape_modifier.add_test_requirement(
                manifest_path="",
                requirement={"id": "REQ-001", "description": "Test", "priority": "high"}
            )

if __name__ == '__main__':
    unittest.main()