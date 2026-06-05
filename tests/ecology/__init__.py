# tests/ecology/__init__.py
"""
Ecology test package.

This package contains dynamically generated test files for the ecology engine.
Tests are created by the mutation and evolution processes to validate system behavior.
"""

import os
import sys

# Ensure the package is importable
__all__ = []

# Package metadata
PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))