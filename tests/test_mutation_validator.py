import unittest
from unittest.mock import patch, MagicMock
import sys
import os

# Add parent directory to path to import the module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mutation_validator import MutationValidator, ValidationError, SyntaxError, InterfaceError, TestError

class TestMutationValidator(unittest.TestCase):
    """Comprehensive test suite for MutationValidator."""

    def setUp(self):
        """Set up test fixtures."""
        self.validator = MutationValidator()
        
        # Sample valid mutation for testing
        self.valid_mutation = {
            'module': 'example_module',
            'code': 'def new_function():\n    return "valid"',
            'dependencies': ['dependency1', 'dependency2']
        }
        
        # Sample mutation with syntax error
        self.syntax_error_mutation = {
            'module': 'example_module',
            'code': 'def broken_function(:\n    return "invalid"',
            'dependencies': []
        }
        
        # Sample mutation that breaks interface
        self.interface_break_mutation = {
            'module': 'example_module',
            'code': 'def existing_function(param1, param2):\n    return param1 + param2',
            'dependencies': ['dependency1']
        }
        
        # Sample mutation that fails tests
        self.test_fail_mutation = {
            'module': 'example_module',
            'code': 'def testable_function():\n    return False',
            'dependencies': []
        }

    def test_valid_mutation_passes_all_phases(self):
        """Test that a valid mutation passes all validation phases."""
        result = self.validator.validate(self.valid_mutation)
        self.assertTrue(result.is_valid)
        self.assertEqual(result.phase, 3)
        self.assertEqual(len(result.errors), 0)

    def test_syntax_error_fails_phase_one(self):
        """Test that a mutation with syntax error fails phase 1."""
        with self.assertRaises(SyntaxError) as context:
            self.validator.validate(self.syntax_error_mutation)
        self.assertIn('Syntax error', str(context.exception))
        self.assertEqual(context.exception.phase, 1)

    def test_interface_break_fails_phase_two(self):
        """Test that a mutation breaking critical interface fails phase 2."""
        with self.assertRaises(InterfaceError) as context:
            self.validator.validate(self.interface_break_mutation)
        self.assertIn('Interface violation', str(context.exception))
        self.assertEqual(context.exception.phase, 2)

    def test_test_failure_fails_phase_three(self):
        """Test that a mutation passing phases 1-2 but failing tests fails phase 3."""
        with self.assertRaises(TestError) as context:
            self.validator.validate(self.test_fail_mutation)
        self.assertIn('Test failure', str(context.exception))
        self.assertEqual(context.exception.phase, 3)

    def test_empty_mutation_raises_error(self):
        """Test that an empty mutation raises appropriate error."""
        empty_mutation = {}
        with self.assertRaises(ValidationError) as context:
            self.validator.validate(empty_mutation)
        self.assertIn('Invalid mutation', str(context.exception))

    def test_mutation_on_non_existent_module(self):
        """Test that mutation on non-existent module fails."""
        non_existent_mutation = {
            'module': 'non_existent_module',
            'code': 'def test():\n    pass',
            'dependencies': []
        }
        with self.assertRaises(ValidationError) as context:
            self.validator.validate(non_existent_mutation)
        self.assertIn('Module not found', str(context.exception))

    def test_circular_dependency_detection(self):
        """Test that circular dependencies are detected."""
        circular_mutation = {
            'module': 'module_a',
            'code': 'from module_b import something',
            'dependencies': ['module_b']
        }
        # Mock to simulate circular dependency
        with patch.object(self.validator, '_check_circular_dependencies', return_value=True):
            with self.assertRaises(ValidationError) as context:
                self.validator.validate(circular_mutation)
            self.assertIn('Circular dependency', str(context.exception))

    def test_mutation_with_missing_required_fields(self):
        """Test that mutation missing required fields fails."""
        incomplete_mutation = {
            'module': 'test_module'
            # Missing 'code' and 'dependencies'
        }
        with self.assertRaises(ValidationError) as context:
            self.validator.validate(incomplete_mutation)
        self.assertIn('Missing required fields', str(context.exception))

    def test_mutation_with_invalid_dependency_format(self):
        """Test that invalid dependency format is caught."""
        invalid_dep_mutation = {
            'module': 'test_module',
            'code': 'def test():\n    pass',
            'dependencies': ['valid_dep', 123]  # Invalid type
        }
        with self.assertRaises(ValidationError) as context:
            self.validator.validate(invalid_dep_mutation)
        self.assertIn('Invalid dependency', str(context.exception))

    def test_phase_one_syntax_validation(self):
        """Test phase 1 syntax validation specifically."""
        # Test valid syntax
        valid_code = 'def valid_function():\n    return True'
        self.assertTrue(self.validator._validate_syntax(valid_code))
        
        # Test invalid syntax
        invalid_code = 'def invalid_function(:\n    return True'
        self.assertFalse(self.validator._validate_syntax(invalid_code))

    def test_phase_two_interface_validation(self):
        """Test phase 2 interface validation specifically."""
        # Test with valid interface
        valid_interface = {
            'function_name': 'existing_function',
            'parameters': ['param1', 'param2']
        }
        self.assertTrue(self.validator._validate_interface(valid_interface))
        
        # Test with invalid interface
        invalid_interface = {
            'function_name': 'non_existing_function',
            'parameters': ['param1']
        }
        self.assertFalse(self.validator._validate_interface(invalid_interface))

    def test_phase_three_test_validation(self):
        """Test phase 3 test validation specifically."""
        # Test with passing tests
        passing_test_code = 'def test_function():\n    assert True'
        self.assertTrue(self.validator._validate_tests(passing_test_code))
        
        # Test with failing tests
        failing_test_code = 'def test_function():\n    assert False'
        self.assertFalse(self.validator._validate_tests(failing_test_code))

    def test_validation_result_object(self):
        """Test that validation returns proper result object."""
        result = self.validator.validate(self.valid_mutation)
        self.assertIsNotNone(result)
        self.assertTrue(hasattr(result, 'is_valid'))
        self.assertTrue(hasattr(result, 'phase'))
        self.assertTrue(hasattr(result, 'errors'))
        self.assertTrue(hasattr(result, 'warnings'))

    def test_mutation_with_warnings(self):
        """Test that warnings are properly captured."""
        warning_mutation = {
            'module': 'example_module',
            'code': 'def deprecated_function():\n    return "warning"',
            'dependencies': ['deprecated_dependency']
        }
        result = self.validator.validate(warning_mutation)
        self.assertTrue(result.is_valid)
        self.assertTrue(len(result.warnings) > 0)

    def test_concurrent_mutation_validation(self):
        """Test validation of multiple mutations concurrently."""
        mutations = [
            self.valid_mutation,
            self.syntax_error_mutation,
            self.interface_break_mutation,
            self.test_fail_mutation
        ]
        
        results = []
        for mutation in mutations:
            try:
                result = self.validator.validate(mutation)
                results.append(result)
            except (SyntaxError, InterfaceError, TestError, ValidationError) as e:
                results.append(e)
        
        self.assertEqual(len(results), 4)
        self.assertTrue(any(r.is_valid if hasattr(r, 'is_valid') else False for r in results))
        self.assertTrue(any(isinstance(r, (SyntaxError, InterfaceError, TestError, ValidationError)) for r in results))

    def test_large_mutation_code(self):
        """Test validation with large code block."""
        large_code = '\n'.join([f'def function_{i}():\n    return {i}' for i in range(100)])
        large_mutation = {
            'module': 'example_module',
            'code': large_code,
            'dependencies': []
        }
        result = self.validator.validate(large_mutation)
        self.assertTrue(result.is_valid)

    def test_mutation_with_special_characters(self):
        """Test mutation with special characters in code."""
        special_mutation = {
            'module': 'example_module',
            'code': 'def special_func():\n    return "!@#$%^&*()"',
            'dependencies': []
        }
        result = self.validator.validate(special_mutation)
        self.assertTrue(result.is_valid)

    def test_validation_error_message_format(self):
        """Test that error messages are properly formatted."""
        try:
            self.validator.validate(self.syntax_error_mutation)
        except SyntaxError as e:
            self.assertIn('phase', str(e))
            self.assertIn('message', str(e))
            self.assertIn('details', str(e))

    def test_validation_phases_execution_order(self):
        """Test that validation phases execute in correct order."""
        with patch.object(self.validator, '_phase_one_validation') as mock_phase1, \
             patch.object(self.validator, '_phase_two_validation') as mock_phase2, \
             patch.object(self.validator, '_phase_three_validation') as mock_phase3:
            
            self.validator.validate(self.valid_mutation)
            
            # Verify execution order
            mock_phase1.assert_called_once()
            mock_phase2.assert_called_once()
            mock_phase3.assert_called_once()

    def test_mutation_with_unicode_characters(self):
        """Test validation with unicode characters."""
        unicode_mutation = {
            'module': 'example_module',
            'code': 'def unicode_func():\n    return "ñóñ éñglísh"',
            'dependencies': []
        }
        result = self.validator.validate(unicode_mutation)
        self.assertTrue(result.is_valid)

    def test_mutation_validation_timeout(self):
        """Test that validation times out for long-running mutations."""
        long_running_mutation = {
            'module': 'example_module',
            'code': 'import time\ndef long_running():\n    time.sleep(10)',
            'dependencies': []
        }
        with self.assertRaises(TimeoutError):
            self.validator.validate(long_running_mutation, timeout=1)

    def test_mutation_with_invalid_imports(self):
        """Test that mutations with invalid imports are caught."""
        invalid_import_mutation = {
            'module': 'example_module',
            'code': 'import non_existent_module_xyz',
            'dependencies': []
        }
        with self.assertRaises(ValidationError) as context:
            self.validator.validate(invalid_import_mutation)
        self.assertIn('Invalid import', str(context.exception))

    def test_mutation_with_side_effects(self):
        """Test that mutations with side effects are detected."""
        side_effect_mutation = {
            'module': 'example_module',
            'code': 'import os\ndef side_effect():\n    os.remove("/important/file")',
            'dependencies': []
        }
        with self.assertRaises(ValidationError) as context:
            self.validator.validate(side_effect_mutation)
        self.assertIn('Side effect detected', str(context.exception))

    def test_validation_statistics(self):
        """Test that validation statistics are properly tracked."""
        initial_stats = self.validator.get_statistics()
        
        # Perform some validations
        self.validator.validate(self.valid_mutation)
        try:
            self.validator.validate(self.syntax_error_mutation)
        except SyntaxError:
            pass
        
        updated_stats = self.validator.get_statistics()
        self.assertEqual(updated_stats['total_validations'], initial_stats['total_validations'] + 2)
        self.assertEqual(updated_stats['successful_validations'], initial_stats['successful_validations'] + 1)
        self.assertEqual(updated_stats['failed_validations'], initial_stats['failed_validations'] + 1)

if __name__ == '__main__':
    unittest.main()