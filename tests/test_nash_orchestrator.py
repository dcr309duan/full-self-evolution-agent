import unittest
import sys
import os
import json
import tempfile
import threading
import time
from unittest.mock import MagicMock, patch

# Add the project root to the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.nash_orchestrator import NashOrchestrator


class TestNashOrchestratorIntegration(unittest.TestCase):
    """Integration tests for NashOrchestrator with mock modules."""

    def setUp(self):
        """Set up test fixtures."""
        # Create mock modules with configurable metrics
        self.mock_module_a = MagicMock()
        self.mock_module_a.name = "module_a"
        self.mock_module_a.get_metrics.return_value = {
            "accuracy": 0.95,
            "latency": 0.1,
            "throughput": 100
        }

        self.mock_module_b = MagicMock()
        self.mock_module_b.name = "module_b"
        self.mock_module_b.get_metrics.return_value = {
            "accuracy": 0.93,
            "latency": 0.15,
            "throughput": 90
        }

        self.mock_module_c = MagicMock()
        self.mock_module_c.name = "module_c"
        self.mock_module_c.get_metrics.return_value = {
            "accuracy": 0.94,
            "latency": 0.12,
            "throughput": 95
        }

        # Create orchestrator with short check interval for testing
        self.orchestrator = NashOrchestrator(
            check_interval=0.1,  # 100ms for fast testing
            nash_threshold=0.01
        )

        # Register mock modules
        self.orchestrator.register_module(self.mock_module_a)
        self.orchestrator.register_module(self.mock_module_b)
        self.orchestrator.register_module(self.mock_module_c)

    def tearDown(self):
        """Clean up after tests."""
        self.orchestrator.stop()

    def test_detection_to_execution_flow(self):
        """Test the full detection->planning->execution flow."""
        # Configure modules to simulate equilibrium state
        # All modules have similar metrics (within threshold)
        equilibrium_metrics = {
            "accuracy": 0.95,
            "latency": 0.1,
            "throughput": 100
        }
        self.mock_module_a.get_metrics.return_value = equilibrium_metrics
        self.mock_module_b.get_metrics.return_value = equilibrium_metrics
        self.mock_module_c.get_metrics.return_value = equilibrium_metrics

        # Start orchestrator
        self.orchestrator.start()

        # Wait for at least one check cycle
        time.sleep(0.3)

        # Verify that detection occurred
        self.assertTrue(self.orchestrator.nash_detected,
                       "Nash equilibrium should be detected when modules have similar metrics")

        # Verify that a change plan was generated
        self.assertIsNotNone(self.orchestrator.current_plan,
                           "A change plan should be generated after detection")

        # Verify the plan includes at least 2 modules
        plan = self.orchestrator.current_plan
        self.assertGreaterEqual(len(plan['modules']), 2,
                               "Change plan should include at least 2 modules")
        self.assertIn('module_a', plan['modules'],
                     "Module A should be in the change plan")
        self.assertIn('module_b', plan['modules'],
                     "Module B should be in the change plan")

        # Verify that execution was triggered
        self.assertTrue(self.orchestrator.execution_triggered,
                       "Execution should be triggered after planning")

        # Verify that modules were called with new parameters
        self.mock_module_a.update_parameters.assert_called_once()
        self.mock_module_b.update_parameters.assert_called_once()

    def test_no_change_when_not_in_equilibrium(self):
        """Test that no change is triggered when modules are not in equilibrium."""
        # Configure modules with very different metrics
        self.mock_module_a.get_metrics.return_value = {
            "accuracy": 0.99,
            "latency": 0.01,
            "throughput": 200
        }
        self.mock_module_b.get_metrics.return_value = {
            "accuracy": 0.50,
            "latency": 0.5,
            "throughput": 50
        }
        self.mock_module_c.get_metrics.return_value = {
            "accuracy": 0.70,
            "latency": 0.3,
            "throughput": 80
        }

        # Start orchestrator
        self.orchestrator.start()

        # Wait for check cycles
        time.sleep(0.3)

        # Verify that no equilibrium was detected
        self.assertFalse(self.orchestrator.nash_detected,
                        "Nash equilibrium should not be detected with diverse metrics")

        # Verify that no change plan was generated
        self.assertIsNone(self.orchestrator.current_plan,
                         "No change plan should be generated")

        # Verify that no execution was triggered
        self.assertFalse(self.orchestrator.execution_triggered,
                        "No execution should be triggered")

    def test_plan_includes_all_modules_in_equilibrium(self):
        """Test that the change plan includes all modules in equilibrium."""
        # All three modules in equilibrium
        equilibrium_metrics = {
            "accuracy": 0.95,
            "latency": 0.1,
            "throughput": 100
        }
        self.mock_module_a.get_metrics.return_value = equilibrium_metrics
        self.mock_module_b.get_metrics.return_value = equilibrium_metrics
        self.mock_module_c.get_metrics.return_value = equilibrium_metrics

        # Start orchestrator
        self.orchestrator.start()

        # Wait for check cycles
        time.sleep(0.3)

        # Verify plan includes all three modules
        plan = self.orchestrator.current_plan
        self.assertIsNotNone(plan, "A plan should exist")
        self.assertEqual(len(plan['modules']), 3,
                        "Plan should include all 3 modules in equilibrium")
        self.assertIn('module_a', plan['modules'])
        self.assertIn('module_b', plan['modules'])
        self.assertIn('module_c', plan['modules'])

    def test_plan_contains_parameter_changes(self):
        """Test that the change plan contains specific parameter adjustments."""
        # Set up equilibrium state
        equilibrium_metrics = {
            "accuracy": 0.95,
            "latency": 0.1,
            "throughput": 100
        }
        self.mock_module_a.get_metrics.return_value = equilibrium_metrics
        self.mock_module_b.get_metrics.return_value = equilibrium_metrics
        self.mock_module_c.get_metrics.return_value = equilibrium_metrics

        # Start orchestrator
        self.orchestrator.start()

        # Wait for check cycles
        time.sleep(0.3)

        # Verify plan has parameter changes
        plan = self.orchestrator.current_plan
        self.assertIsNotNone(plan, "A plan should exist")
        self.assertIn('changes', plan, "Plan should contain changes")
        self.assertGreater(len(plan['changes']), 0,
                          "Plan should have at least one change")

        # Verify each change has required fields
        for change in plan['changes']:
            self.assertIn('module', change,
                         "Each change should specify a module")
            self.assertIn('parameter', change,
                         "Each change should specify a parameter")
            self.assertIn('new_value', change,
                         "Each change should specify a new value")
            self.assertIn('reason', change,
                         "Each change should include a reason")

    def test_minimal_integration(self):
        """Minimal integration test: import, call detect_nash, verify force_coordinated_change."""
        # Import nash_orchestrator (already imported at top)
        from core.nash_orchestrator import NashOrchestrator

        # Create a minimal orchestrator instance
        orch = NashOrchestrator(check_interval=0.1, nash_threshold=0.01)

        # Create a mock equilibrium state (all modules have same metrics)
        mock_state = {
            "module_a": {"accuracy": 0.95, "latency": 0.1, "throughput": 100},
            "module_b": {"accuracy": 0.95, "latency": 0.1, "throughput": 100},
            "module_c": {"accuracy": 0.95, "latency": 0.1, "throughput": 100}
        }

        # Register mock modules with the equilibrium state
        mock_a = MagicMock()
        mock_a.name = "module_a"
        mock_a.get_metrics.return_value = mock_state["module_a"]
        mock_b = MagicMock()
        mock_b.name = "module_b"
        mock_b.get_metrics.return_value = mock_state["module_b"]
        mock_c = MagicMock()
        mock_c.name = "module_c"
        mock_c.get_metrics.return_value = mock_state["module_c"]

        orch.register_module(mock_a)
        orch.register_module(mock_b)
        orch.register_module(mock_c)

        # Call detect_nash directly (simulating the internal detection)
        orch.detect_nash()

        # Verify force_coordinated_change is triggered
        self.assertTrue(orch.force_coordinated_change,
                       "force_coordinated_change should be True when equilibrium is detected")

        # Clean up
        orch.stop()


if __name__ == '__main__':
    unittest.main()