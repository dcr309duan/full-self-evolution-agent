#!/usr/bin/env python3
"""Minimal integration test for Nash detector/forcer within the same process."""

import unittest
from unittest.mock import Mock, patch
import json
import os

# Import the core modules directly (same process)
from core.nash_detector import NashDetector
from core.nash_forcer import NashForcer


class TestNashIntegration(unittest.TestCase):
    """Integration tests for Nash detector and forcer working together."""

    def setUp(self):
        """Set up mock data for testing."""
        self.detector = NashDetector()
        self.forcer = NashForcer()
        # Mock dependency graph: module -> list of dependents
        self.mock_graph = {
            "module_a": ["module_b", "module_c"],
            "module_b": ["module_c"],
            "module_c": [],
            "module_d": ["module_e"],
            "module_e": [],
        }
        # Mock module states: module -> (healthy, version)
        self.mock_states = {
            "module_a": (True, "1.0"),
            "module_b": (True, "1.0"),
            "module_c": (True, "1.0"),
            "module_d": (False, "0.9"),  # Unhealthy
            "module_e": (True, "1.0"),
        }

    def test_detect_equilibrium(self):
        """Test that NashDetector correctly identifies equilibrium state."""
        # All modules healthy -> should be equilibrium
        healthy_states = {k: (True, v) for k, v in self.mock_states.items()}
        is_eq, details = self.detector.detect_equilibrium(
            self.mock_graph, healthy_states
        )
        self.assertTrue(is_eq)
        self.assertIn("equilibrium", details)

    def test_detect_no_equilibrium(self):
        """Test that NashDetector detects non-equilibrium."""
        is_eq, details = self.detector.detect_equilibrium(
            self.mock_graph, self.mock_states
        )
        self.assertFalse(is_eq)
        self.assertIn("unhealthy", details)

    def test_force_equilibrium(self):
        """Test that NashForcer can force modules to equilibrium."""
        # Force all modules to healthy state
        result = self.forcer.force_equilibrium(
            self.mock_graph, self.mock_states
        )
        self.assertTrue(result["success"])
        # Check that all modules are now healthy
        for module, (healthy, _) in result["states"].items():
            self.assertTrue(healthy, f"Module {module} not forced to healthy")

    def test_integrated_detect_and_force(self):
        """Test full pipeline: detect non-equilibrium, then force it."""
        # 1. Detect non-equilibrium
        is_eq, details = self.detector.detect_equilibrium(
            self.mock_graph, self.mock_states
        )
        self.assertFalse(is_eq)

        # 2. Force equilibrium
        force_result = self.forcer.force_equilibrium(
            self.mock_graph, self.mock_states
        )
        self.assertTrue(force_result["success"])

        # 3. Verify equilibrium after forcing
        is_eq_after, details_after = self.detector.detect_equilibrium(
            self.mock_graph, force_result["states"]
        )
        self.assertTrue(is_eq_after)

    def test_multi_module_force(self):
        """Test forcing multiple unhealthy modules to equilibrium."""
        # Add more unhealthy modules
        extended_states = {
            "module_a": (False, "0.5"),
            "module_b": (False, "0.5"),
            "module_c": (True, "1.0"),
            "module_d": (False, "0.9"),
            "module_e": (False, "0.8"),
        }
        result = self.forcer.force_equilibrium(
            self.mock_graph, extended_states
        )
        self.assertTrue(result["success"])
        # All should be healthy after force
        for module, (healthy, _) in result["states"].items():
            self.assertTrue(healthy, f"Module {module} not forced to healthy")

    def test_empty_graph(self):
        """Test edge case: empty dependency graph."""
        empty_graph = {}
        states = {}
        is_eq, details = self.detector.detect_equilibrium(empty_graph, states)
        self.assertTrue(is_eq)
        result = self.forcer.force_equilibrium(empty_graph, states)
        self.assertTrue(result["success"])


if __name__ == "__main__":
    unittest.main()