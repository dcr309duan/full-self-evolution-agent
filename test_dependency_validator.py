import unittest
from unittest.mock import patch, mock_open, MagicMock
import sys
import os
import ast
from dependency_validator import DependencyValidator, ImportGraph, ImportError

class TestDependencyValidator(unittest.TestCase):
    """Comprehensive tests for the dependency validator."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.validator = DependencyValidator()
        self.test_dir = '/tmp/test_project'
        
    def create_mock_module(self, module_path, imports=None, functions=None):
        """Helper to create mock module content."""
        content = []
        if imports:
            content.extend(imports)
        if functions:
            content.extend(functions)
        return '\n'.join(content) if content else ''
    
    # 1) Test detection of circular imports
    def test_circular_import_direct(self):
        """Test detection of direct circular import A->B->A."""
        modules = {
            'module_a': ['import module_b'],
            'module_b': ['import module_a']
        }
        with patch.object(self.validator, 'get_module_content', side_effect=lambda x: modules.get(x, '')):
            with self.assertRaises(ImportError) as context:
                self.validator.validate('module_a')
            self.assertIn('circular', str(context.exception).lower())
    
    def test_circular_import_indirect(self):
        """Test detection of indirect circular import A->B->C->A."""
        modules = {
            'module_a': ['import module_b'],
            'module_b': ['import module_c'],
            'module_c': ['import module_a']
        }
        with patch.object(self.validator, 'get_module_content', side_effect=lambda x: modules.get(x, '')):
            with self.assertRaises(ImportError) as context:
                self.validator.validate('module_a')
            self.assertIn('circular', str(context.exception).lower())
    
    def test_circular_import_self(self):
        """Test detection of self-import circular dependency."""
        modules = {
            'module_a': ['import module_a']
        }
        with patch.object(self.validator, 'get_module_content', side_effect=lambda x: modules.get(x, '')):
            with self.assertRaises(ImportError) as context:
                self.validator.validate('module_a')
            self.assertIn('circular', str(context.exception).lower())
    
    def test_no_circular_import(self):
        """Test that acyclic imports pass validation."""
        modules = {
            'module_a': ['import module_b'],
            'module_b': ['import module_c'],
            'module_c': []
        }
        with patch.object(self.validator, 'get_module_content', side_effect=lambda x: modules.get(x, '')):
            try:
                self.validator.validate('module_a')
            except ImportError:
                self.fail("validate() raised ImportError unexpectedly!")
    
    # 2) Test detection of non-existent module references
    def test_non_existent_module_absolute(self):
        """Test detection of non-existent module in absolute import."""
        modules = {
            'module_a': ['import non_existent_module']
        }
        with patch.object(self.validator, 'get_module_content', side_effect=lambda x: modules.get(x, '')):
            with self.assertRaises(ImportError) as context:
                self.validator.validate('module_a')
            self.assertIn('non_existent_module', str(context.exception))
    
    def test_non_existent_module_from_import(self):
        """Test detection of non-existent module in from-import."""
        modules = {
            'module_a': ['from non_existent_package import some_module']
        }
        with patch.object(self.validator, 'get_module_content', side_effect=lambda x: modules.get(x, '')):
            with self.assertRaises(ImportError) as context:
                self.validator.validate('module_a')
            self.assertIn('non_existent_package', str(context.exception))
    
    def test_non_existent_relative_import(self):
        """Test detection of non-existent module in relative import."""
        modules = {
            'package.module_a': ['from . import non_existent_module']
        }
        with patch.object(self.validator, 'get_module_content', side_effect=lambda x: modules.get(x, '')):
            with self.assertRaises(ImportError) as context:
                self.validator.validate('package.module_a')
            self.assertIn('non_existent_module', str(context.exception))
    
    def test_non_existent_submodule(self):
        """Test detection of non-existent submodule."""
        modules = {
            'module_a': ['from os import non_existent_function']
        }
        with patch.object(self.validator, 'get_module_content', side_effect=lambda x: modules.get(x, '')):
            with self.assertRaises(ImportError) as context:
                self.validator.validate('module_a')
            self.assertIn('non_existent_function', str(context.exception))
    
    # 3) Test that valid imports pass validation
    def test_valid_standard_library_import(self):
        """Test that standard library imports pass validation."""
        modules = {
            'module_a': ['import os', 'import sys', 'from collections import defaultdict']
        }
        with patch.object(self.validator, 'get_module_content', side_effect=lambda x: modules.get(x, '')):
            try:
                self.validator.validate('module_a')
            except ImportError:
                self.fail("validate() raised ImportError for valid standard library imports!")
    
    def test_valid_project_import(self):
        """Test that valid project imports pass validation."""
        modules = {
            'module_a': ['import module_b', 'from module_c import function_d'],
            'module_b': [],
            'module_c': ['def function_d(): pass']
        }
        with patch.object(self.validator, 'get_module_content', side_effect=lambda x: modules.get(x, '')):
            try:
                self.validator.validate('module_a')
            except ImportError:
                self.fail("validate() raised ImportError for valid project imports!")
    
    def test_valid_third_party_import(self):
        """Test that valid third-party imports pass validation."""
        modules = {
            'module_a': ['import requests', 'from flask import Flask']
        }
        with patch.object(self.validator, 'get_module_content', side_effect=lambda x: modules.get(x, '')):
            try:
                self.validator.validate('module_a')
            except ImportError:
                self.fail("validate() raised ImportError for valid third-party imports!")
    
    # 4) Test parsing of various import styles
    def test_absolute_import_parsing(self):
        """Test parsing of absolute imports."""
        code = 'import os\nimport sys\nimport package.module'
        expected_imports = ['os', 'sys', 'package.module']
        result = self.validator.parse_imports(code)
        self.assertEqual(result, expected_imports)
    
    def test_relative_import_parsing(self):
        """Test parsing of relative imports."""
        code = 'from . import module\nfrom .. import parent_module\nfrom .subpackage import something'
        expected_imports = ['.module', '..parent_module', '.subpackage.something']
        result = self.validator.parse_imports(code)
        self.assertEqual(result, expected_imports)
    
    def test_from_import_parsing(self):
        """Test parsing of from-imports."""
        code = 'from os import path\nfrom collections import defaultdict, OrderedDict'
        expected_imports = ['os.path', 'collections.defaultdict', 'collections.OrderedDict']
        result = self.validator.parse_imports(code)
        self.assertEqual(result, expected_imports)
    
    def test_mixed_import_styles(self):
        """Test parsing of mixed import styles."""
        code = '''
import os
from sys import argv
from . import local_module
import external_package
from ..parent import sibling
'''
        expected_imports = ['os', 'sys.argv', '.local_module', 'external_package', '..parent.sibling']
        result = self.validator.parse_imports(code)
        self.assertEqual(result, expected_imports)
    
    def test_import_with_alias(self):
        """Test parsing of imports with aliases."""
        code = 'import numpy as np\nfrom pandas import DataFrame as df'
        expected_imports = ['numpy', 'pandas.DataFrame']
        result = self.validator.parse_imports(code)
        self.assertEqual(result, expected_imports)
    
    # 5) Test function call resolution
    def test_function_call_in_same_module(self):
        """Test resolution of function calls within same module."""
        code = '''
def helper():
    pass

def main():
    helper()
'''
        with patch.object(self.validator, 'get_module_content', return_value=code):
            result = self.validator.resolve_function_calls('test_module', 'main')
            self.assertIn('helper', result)
    
    def test_function_call_from_imported_module(self):
        """Test resolution of function calls from imported modules."""
        modules = {
            'module_a': '''
from module_b import helper

def main():
    helper()
''',
            'module_b': '''
def helper():
    pass
'''
        }
        with patch.object(self.validator, 'get_module_content', side_effect=lambda x: modules.get(x, '')):
            result = self.validator.resolve_function_calls('module_a', 'main')
            self.assertIn('module_b.helper', result)
    
    def test_chained_function_calls(self):
        """Test resolution of chained function calls."""
        modules = {
            'module_a': '''
from module_b import get_data

def process():
    data = get_data()
    analyze(data)
''',
            'module_b': '''
def get_data():
    return [1, 2, 3]
'''
        }
        with patch.object(self.validator, 'get_module_content', side_effect=lambda x: modules.get(x, '')):
            result = self.validator.resolve_function_calls('module_a', 'process')
            self.assertIn('module_b.get_data', result)
    
    def test_function_call_with_nested_imports(self):
        """Test resolution of function calls with nested imports."""
        modules = {
            'module_a': '''
from module_b import outer

def main():
    outer()
''',
            'module_b': '''
from module_c import inner

def outer():
    inner()
''',
            'module_c': '''
def inner():
    pass
'''
        }
        with patch.object(self.validator, 'get_module_content', side_effect=lambda x: modules.get(x, '')):
            result = self.validator.resolve_function_calls('module_a', 'main')
            self.assertIn('module_c.inner', result)
    
    def test_function_call_with_standard_library(self):
        """Test resolution of function calls to standard library."""
        code = '''
import os

def main():
    os.path.join('a', 'b')
'''
        with patch.object(self.validator, 'get_module_content', return_value=code):
            result = self.validator.resolve_function_calls('test_module', 'main')
            self.assertIn('os.path.join', result)
    
    def test_function_call_not_found(self):
        """Test behavior when function call cannot be resolved."""
        code = '''
def main():
    unknown_function()
'''
        with patch.object(self.validator, 'get_module_content', return_value=code):
            result = self.validator.resolve_function_calls('test_module', 'main')
            self.assertEqual(result, [])  # Should return empty list for unresolved calls
    
    # 6) Integration tests for pre-mutation validation hook
    def test_pre_mutation_hook_rejects_circular_dependency(self):
        """Test that pre-mutation hook rejects mutations introducing circular dependencies."""
        # Simulate a mutation that would introduce a circular dependency
        modules = {
            'module_a': ['import module_b'],
            'module_b': ['import module_c'],
            'module_c': ['import module_a']  # This creates the cycle
        }
        with patch.object(self.validator, 'get_module_content', side_effect=lambda x: modules.get(x, '')):
            with patch.object(self.validator, 'validate_mutation', return_value=False):
                result = self.validator.pre_mutation_hook('module_a', 'add_import', {'import': 'module_c'})
                self.assertFalse(result)
    
    def test_pre_mutation_hook_rejects_non_existent_module(self):
        """Test that pre-mutation hook rejects mutations referencing non-existent modules."""
        modules = {
            'module_a': ['import module_b']
        }
        with patch.object(self.validator, 'get_module_content', side_effect=lambda x: modules.get(x, '')):
            with patch.object(self.validator, 'validate_mutation', return_value=False):
                result = self.validator.pre_mutation_hook('module_a', 'add_import', {'import': 'non_existent_module'})
                self.assertFalse(result)
    
    def test_pre_mutation_hook_accepts_valid_mutation(self):
        """Test that pre-mutation hook accepts valid mutations."""
        modules = {
            'module_a': ['import module_b'],
            'module_b': ['import module_c'],
            'module_c': []
        }
        with patch.object(self.validator, 'get_module_content', side_effect=lambda x: modules.get(x, '')):
            with patch.object(self.validator, 'validate_mutation', return_value=True):
                result = self.validator.pre_mutation_hook('module_a', 'add_import', {'import': 'module_c'})
                self.assertTrue(result)
    
    def test_pre_mutation_hook_rejects_self_referencing_import(self):
        """Test that pre-mutation hook rejects self-referencing imports."""
        modules = {
            'module_a': ['import module_b']
        }
        with patch.object(self.validator, 'get_module_content', side_effect=lambda x: modules.get(x, '')):
            with patch.object(self.validator, 'validate_mutation', return_value=False):
                result = self.validator.pre_mutation_hook('module_a', 'add_import', {'import': 'module_a'})
                self.assertFalse(result)
    
    def test_pre_mutation_hook_rejects_nested_circular_dependency(self):
        """Test that pre-mutation hook rejects complex nested circular dependencies."""
        modules = {
            'module_a': ['import module_b'],
            'module_b': ['import module_c'],
            'module_c': ['import module_d'],
            'module_d': ['import module_e'],
            'module_e': ['import module_a']  # Creates cycle A->B->C->D->E->A
        }
        with patch.object(self.validator, 'get_module_content', side_effect=lambda x: modules.get(x, '')):
            with patch.object(self.validator, 'validate_mutation', return_value=False):
                result = self.validator.pre_mutation_hook('module_a', 'add_import', {'import': 'module_e'})
                self.assertFalse(result)
    
    def test_pre_mutation_hook_accepts_acyclic_imports(self):
        """Test that pre-mutation hook accepts acyclic import chains."""
        modules = {
            'module_a': ['import module_b'],
            'module_b': ['import module_c'],
            'module_c': ['import module_d'],
            'module_d': []
        }
        with patch.object(self.validator, 'get_module_content', side_effect=lambda x: modules.get(x, '')):
            with patch.object(self.validator, 'validate_mutation', return_value=True):
                result = self.validator.pre_mutation_hook('module_a', 'add_import', {'import': 'module_d'})
                self.assertTrue(result)
    
    def test_pre_mutation_hook_rejects_mutation_with_multiple_issues(self):
        """Test that pre-mutation hook rejects mutations with multiple issues."""
        modules = {
            'module_a': ['import module_b'],
            'module_b': ['import module_c'],
            'module_c': ['import module_a', 'import non_existent_module']  # Both circular and non-existent
        }
        with patch.object(self.validator, 'get_module_content', side_effect=lambda x: modules.get(x, '')):
            with patch.object(self.validator, 'validate_mutation', return_value=False):
                result = self.validator.pre_mutation_hook('module_c', 'add_import', {'import': 'non_existent_module'})
                self.assertFalse(result)
    
    def test_pre_mutation_hook_handles_empty_imports(self):
        """Test that pre-mutation hook handles modules with no imports."""
        modules = {
            'module_a': [],
            'module_b': ['import module_a']
        }
        with patch.object(self.validator, 'get_module_content', side_effect=lambda x: modules.get(x, '')):
            with patch.object(self.validator, 'validate_mutation', return_value=True):
                result = self.validator.pre_mutation_hook('module_b', 'add_import', {'import': 'module_a'})
                self.assertTrue(result)
    
    def test_pre_mutation_hook_rejects_import_from_non_existent_package(self):
        """Test that pre-mutation hook rejects imports from non-existent packages."""
        modules = {
            'module_a': ['import module_b']
        }
        with patch.object(self.validator, 'get_module_content', side_effect=lambda x: modules.get(x, '')):
            with patch.object(self.validator, 'validate_mutation', return_value=False):
                result = self.validator.pre_mutation_hook('module_a', 'add_from_import', {'package': 'non_existent_package', 'module': 'some_module'})
                self.assertFalse(result)
    
    def test_pre_mutation_hook_accepts_standard_library_imports(self):
        """Test that pre-mutation hook accepts standard library imports."""
        modules = {
            'module_a': ['import os']
        }
        with patch.object(self.validator, 'get_module_content', side_effect=lambda x: modules.get(x, '')):
            with patch.object(self.validator, 'validate_mutation', return_value=True):
                result = self.validator.pre_mutation_hook('module_a', 'add_import', {'import': 'sys'})
                self.assertTrue(result)

if __name__ == '__main__':
    unittest.main()