import unittest
from unittest.mock import Mock, patch, PropertyMock
import logging
from pathlib import Path
import sys
import os

# Add the parent directory to sys.path to allow imports from the core module
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from core.mutation_sandbox import MutationSandbox, DependencyGraph, ImportParser

class TestCoreMutationSandbox(unittest.TestCase):
    """Test suite for core mutation sandbox functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.sandbox = MutationSandbox()
        self.logger = logging.getLogger('test_mutation_sandbox')
        self.logger.setLevel(logging.DEBUG)
        
        # Capture log output for verification
        self.log_capture = []
        self.handler = logging.StreamHandler()
        self.handler.setLevel(logging.DEBUG)
        self.logger.addHandler(self.handler)

    def create_mock_dependency_graph(self, dependency_count):
        """Helper to create a mock dependency graph with specified number of dependencies."""
        mock_graph = Mock(spec=DependencyGraph)
        mock_dependencies = [Mock() for _ in range(dependency_count)]
        
        # Configure the mock to return the specified number of dependencies
        type(mock_graph).dependencies = PropertyMock(return_value=mock_dependencies)
        mock_graph.dependency_count = dependency_count
        mock_graph.__len__ = Mock(return_value=dependency_count)
        
        return mock_graph

    def test_mutation_with_zero_dependencies_allowed(self):
        """Test that mutations with 0 dependencies are allowed."""
        mock_graph = self.create_mock_dependency_graph(0)
        result = self.sandbox.validate_mutation(mock_graph)
        self.assertTrue(result, "Mutation with 0 dependencies should be allowed")

    def test_mutation_with_one_dependency_allowed(self):
        """Test that mutations with 1 dependency are allowed."""
        mock_graph = self.create_mock_dependency_graph(1)
        result = self.sandbox.validate_mutation(mock_graph)
        self.assertTrue(result, "Mutation with 1 dependency should be allowed")

    def test_mutation_with_two_dependencies_allowed(self):
        """Test that mutations with 2 dependencies are allowed."""
        mock_graph = self.create_mock_dependency_graph(2)
        result = self.sandbox.validate_mutation(mock_graph)
        self.assertTrue(result, "Mutation with 2 dependencies should be allowed")

    def test_mutation_with_three_dependencies_rejected(self):
        """Test that mutations with 3+ dependencies are rejected."""
        mock_graph = self.create_mock_dependency_graph(3)
        
        with self.assertLogs(level='INFO') as log:
            result = self.sandbox.validate_mutation(mock_graph)
            self.assertFalse(result, "Mutation with 3 dependencies should be rejected")
            self.assertTrue(any("suggestion" in message.lower() for message in log.output),
                          "Log should contain a suggestion message")

    def test_mutation_with_four_dependencies_rejected(self):
        """Test that mutations with 4 dependencies are rejected."""
        mock_graph = self.create_mock_dependency_graph(4)
        
        with self.assertLogs(level='INFO') as log:
            result = self.sandbox.validate_mutation(mock_graph)
            self.assertFalse(result, "Mutation with 4 dependencies should be rejected")
            self.assertTrue(any("suggestion" in message.lower() for message in log.output),
                          "Log should contain a suggestion message")

    def test_mutation_with_multiple_dependencies_rejected(self):
        """Test that mutations with many dependencies are rejected."""
        mock_graph = self.create_mock_dependency_graph(10)
        
        with self.assertLogs(level='INFO') as log:
            result = self.sandbox.validate_mutation(mock_graph)
            self.assertFalse(result, "Mutation with 10 dependencies should be rejected")
            self.assertTrue(any("suggestion" in message.lower() for message in log.output),
                          "Log should contain a suggestion message")

    def test_import_parser_on_core_files(self):
        """Test that the import parser accurately detects dependencies in sample core files."""
        # Create a sample core file with various import patterns
        sample_core_content = """
import os
import sys
from pathlib import Path
from collections import defaultdict
import numpy as np
from typing import List, Dict, Optional
import json
import re
from datetime import datetime
import math
"""
        
        # Create a temporary file to parse
        temp_file = Path('temp_test_core_file.py')
        try:
            temp_file.write_text(sample_core_content)
            
            parser = ImportParser()
            dependencies = parser.parse_file(temp_file)
            
            # Verify all expected imports are detected
            expected_imports = [
                'os', 'sys', 'pathlib.Path', 'collections.defaultdict',
                'numpy', 'typing.List', 'typing.Dict', 'typing.Optional',
                'json', 're', 'datetime.datetime', 'math'
            ]
            
            for expected in expected_imports:
                self.assertIn(expected, dependencies,
                            f"Import '{expected}' should be detected by parser")
            
            # Verify no extra imports are detected
            self.assertEqual(len(dependencies), len(expected_imports),
                           "Parser should detect exactly the expected number of imports")
            
        finally:
            # Clean up temporary file
            if temp_file.exists():
                temp_file.unlink()

    def test_import_parser_on_complex_core_files(self):
        """Test import parser with more complex import patterns."""
        sample_complex_content = """
# Conditional imports
try:
    import pandas as pd
    import matplotlib.pyplot as plt
except ImportError:
    pass

# Relative imports
from . import utils
from ..config import settings
from .submodule import helper_function

# Import with aliases
import numpy as np
import pandas as pd

# Import from packages
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, precision_score

# Standard library imports
import os, sys, json
from collections import OrderedDict, Counter
from pathlib import Path, PurePath
"""
        
        temp_file = Path('temp_complex_core_file.py')
        try:
            temp_file.write_text(sample_complex_content)
            
            parser = ImportParser()
            dependencies = parser.parse_file(temp_file)
            
            # Verify key imports are detected
            expected_imports = [
                'pandas', 'matplotlib.pyplot', 'utils', 'config.settings',
                'submodule.helper_function', 'numpy', 'sklearn.model_selection.train_test_split',
                'sklearn.metrics.accuracy_score', 'sklearn.metrics.precision_score',
                'os', 'sys', 'json', 'collections.OrderedDict', 'collections.Counter',
                'pathlib.Path', 'pathlib.PurePath'
            ]
            
            for expected in expected_imports:
                self.assertIn(expected, dependencies,
                            f"Complex import '{expected}' should be detected by parser")
            
            # Verify no duplicate imports
            self.assertEqual(len(dependencies), len(set(dependencies)),
                           "Parser should not detect duplicate imports")
            
        finally:
            if temp_file.exists():
                temp_file.unlink()

    def test_import_parser_edge_cases(self):
        """Test import parser with edge cases and special patterns."""
        sample_edge_content = """
# Import with comments
import os  # system operations
import sys  # command line arguments

# Multi-line imports
from typing import (
    List,
    Dict,
    Tuple,
    Optional
)

# Import with underscores
import my_custom_module
from my_package import my_function

# Import with numbers
import module2
from package3 import function4

# Dynamic imports (should be ignored or handled)
import importlib
module = importlib.import_module('some_module')
"""
        
        temp_file = Path('temp_edge_core_file.py')
        try:
            temp_file.write_text(sample_edge_content)
            
            parser = ImportParser()
            dependencies = parser.parse_file(temp_file)
            
            # Verify edge case imports are detected
            expected_imports = [
                'os', 'sys', 'typing.List', 'typing.Dict', 'typing.Tuple',
                'typing.Optional', 'my_custom_module', 'my_package.my_function',
                'module2', 'package3.function4', 'importlib'
            ]
            
            for expected in expected_imports:
                self.assertIn(expected, dependencies,
                            f"Edge case import '{expected}' should be detected by parser")
            
            # Verify dynamic imports are not included
            self.assertNotIn('some_module', dependencies,
                           "Dynamic imports should not be detected as dependencies")
            
        finally:
            if temp_file.exists():
                temp_file.unlink()

    def test_dependency_graph_mocking(self):
        """Test that dependency graph mocking works correctly for all test cases."""
        # Test with various dependency counts
        for count in [0, 1, 2, 3, 5, 10]:
            mock_graph = self.create_mock_dependency_graph(count)
            self.assertEqual(len(mock_graph), count,
                           f"Mock graph should have {count} dependencies")
            self.assertEqual(mock_graph.dependency_count, count,
                           f"Mock graph dependency_count should be {count}")

    def tearDown(self):
        """Clean up after tests."""
        self.logger.removeHandler(self.handler)
        # Clean up any remaining temp files
        for temp_file in Path('.').glob('temp_*_core_file.py'):
            temp_file.unlink()


if __name__ == '__main__':
    unittest.main()