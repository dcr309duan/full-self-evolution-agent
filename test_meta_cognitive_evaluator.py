import unittest
from unittest.mock import Mock, patch, MagicMock
from collections import deque
import math

# Import the modules to test (assuming they are in the same package)
from meta_cognitive_evaluator import MetaCognitiveEvaluator
from parameter_controller import ParameterController
from orchestrator import Orchestrator

class TestMetaCognitiveEvaluator(unittest.TestCase):
    """Test suite for MetaCognitiveEvaluator and related components."""

    def setUp(self):
        """Set up test fixtures."""
        self.evaluator = MetaCognitiveEvaluator(window_size=30)
        self.controller = ParameterController()
        self.orchestrator = Orchestrator()

    def test_rolling_window_tracking(self):
        """Test that evaluator correctly tracks 30-cycle rolling window."""
        # Add 30 successful outcomes
        for i in range(30):
            self.evaluator.record_outcome(success=True, cycle=i)
        
        # Verify window has exactly 30 entries
        self.assertEqual(len(self.evaluator.success_window), 30)
        self.assertEqual(self.evaluator.success_rate, 1.0)
        
        # Add 10 more successful outcomes (window should still be 30)
        for i in range(30, 40):
            self.evaluator.record_outcome(success=True, cycle=i)
        
        self.assertEqual(len(self.evaluator.success_window), 30)
        
        # Add 15 failures, then check success rate
        for i in range(40, 55):
            self.evaluator.record_outcome(success=False, cycle=i)
        
        # Window should contain 15 successes and 15 failures
        self.assertEqual(len(self.evaluator.success_window), 30)
        expected_rate = 15 / 30
        self.assertAlmostEqual(self.evaluator.success_rate, expected_rate, places=5)
        
        # Verify oldest entries are being removed (FIFO behavior)
        self.assertEqual(self.evaluator.success_window[0], True)  # First success from cycle 25
        self.assertEqual(self.evaluator.success_window[-1], False)  # Last failure from cycle 54

    def test_brittleness_detection_on_core_success_rate_drop(self):
        """Test brittleness detection when core success rate drops."""
        # Initially, set high success rate
        for i in range(20):
            self.evaluator.record_outcome(success=True, cycle=i)
        
        self.assertFalse(self.evaluator.is_brittle)
        
        # Now introduce failures to drop success rate below threshold
        for i in range(20, 30):
            self.evaluator.record_outcome(success=False, cycle=i)
        
        # Success rate should be 20/30 = 0.667 (below typical 0.7 threshold)
        self.assertLess(self.evaluator.success_rate, 0.7)
        self.assertTrue(self.evaluator.is_brittle)
        
        # Test with custom threshold
        custom_evaluator = MetaCognitiveEvaluator(window_size=30, brittleness_threshold=0.5)
        for i in range(15):
            custom_evaluator.record_outcome(success=True, cycle=i)
        for i in range(15, 30):
            custom_evaluator.record_outcome(success=False, cycle=i)
        
        # Success rate = 0.5, which is not below 0.5 threshold
        self.assertAlmostEqual(custom_evaluator.success_rate, 0.5, places=5)
        self.assertFalse(custom_evaluator.is_brittle)
        
        # Add one more failure to drop below threshold
        custom_evaluator.record_outcome(success=False, cycle=30)
        self.assertLess(custom_evaluator.success_rate, 0.5)
        self.assertTrue(custom_evaluator.is_brittle)

    def test_parameter_controller_reduces_mutation_rate_on_brittleness(self):
        """Test that parameter controller reduces mutation rate on brittleness."""
        # Set initial mutation rate
        initial_mutation_rate = 0.1
        self.controller.set_mutation_rate(initial_mutation_rate)
        
        # Simulate brittleness detection
        self.controller.on_brittleness_detected()
        
        # Mutation rate should be reduced (e.g., by factor of 2)
        expected_reduced_rate = initial_mutation_rate / 2
        self.assertAlmostEqual(self.controller.mutation_rate, expected_reduced_rate, places=5)
        
        # Test with multiple brittleness events
        self.controller.on_brittleness_detected()
        expected_reduced_rate /= 2
        self.assertAlmostEqual(self.controller.mutation_rate, expected_reduced_rate, places=5)
        
        # Test that mutation rate doesn't go below minimum
        min_mutation_rate = 0.001
        self.controller.set_min_mutation_rate(min_mutation_rate)
        for _ in range(20):
            self.controller.on_brittleness_detected()
        
        self.assertGreaterEqual(self.controller.mutation_rate, min_mutation_rate)

    def test_parameters_gradually_return_to_baseline_after_stability(self):
        """Test that parameters gradually return to baseline after stability."""
        # Set baseline and reduce mutation rate due to brittleness
        baseline_rate = 0.1
        self.controller.set_baseline_mutation_rate(baseline_rate)
        self.controller.set_mutation_rate(baseline_rate)
        
        # Trigger brittleness
        self.controller.on_brittleness_detected()
        reduced_rate = self.controller.mutation_rate
        self.assertLess(reduced_rate, baseline_rate)
        
        # Simulate stability (no brittleness for several cycles)
        for _ in range(5):
            self.controller.on_stability_maintained()
        
        # Mutation rate should have increased but not yet reached baseline
        self.assertGreater(self.controller.mutation_rate, reduced_rate)
        self.assertLess(self.controller.mutation_rate, baseline_rate)
        
        # Continue stability until baseline is restored
        for _ in range(20):
            self.controller.on_stability_maintained()
        
        self.assertAlmostEqual(self.controller.mutation_rate, baseline_rate, places=5)
        
        # Test that it doesn't exceed baseline
        for _ in range(10):
            self.controller.on_stability_maintained()
        
        self.assertAlmostEqual(self.controller.mutation_rate, baseline_rate, places=5)

    def test_integration_with_orchestrator_using_mock_mutations(self):
        """Test integration with orchestrator using mock mutations."""
        # Create mock for mutation operations
        mock_mutation = MagicMock()
        mock_mutation.apply.return_value = "mutated_genome"
        
        # Set up orchestrator with evaluator and controller
        self.orchestrator.set_evaluator(self.evaluator)
        self.orchestrator.set_controller(self.controller)
        self.orchestrator.set_mutation_function(mock_mutation)
        
        # Simulate a successful mutation cycle
        initial_mutation_rate = self.controller.mutation_rate
        result = self.orchestrator.execute_mutation_cycle(genome="original_genome")
        
        # Verify mutation was called with correct parameters
        mock_mutation.apply.assert_called_once()
        call_args = mock_mutation.apply.call_args[0]
        self.assertEqual(call_args[0], "original_genome")
        self.assertEqual(call_args[1], initial_mutation_rate)
        
        # Verify result
        self.assertEqual(result, "mutated_genome")
        
        # Simulate multiple cycles with failures to trigger brittleness
        mock_mutation.reset_mock()
        for i in range(15):
            self.orchestrator.execute_mutation_cycle(genome=f"genome_{i}")
            self.evaluator.record_outcome(success=False, cycle=i)
        
        # After 15 failures, brittleness should be detected
        self.assertTrue(self.evaluator.is_brittle)
        
        # Verify controller reduced mutation rate
        self.assertLess(self.controller.mutation_rate, initial_mutation_rate)
        
        # Verify orchestrator uses reduced rate for subsequent mutations
        mock_mutation.reset_mock()
        self.orchestrator.execute_mutation_cycle(genome="new_genome")
        call_args = mock_mutation.apply.call_args[0]
        self.assertEqual(call_args[1], self.controller.mutation_rate)
        
        # Simulate recovery with successes
        for i in range(20):
            self.orchestrator.execute_mutation_cycle(genome=f"recovery_genome_{i}")
            self.evaluator.record_outcome(success=True, cycle=30 + i)
        
        # After recovery, mutation rate should start returning to baseline
        self.assertGreater(self.controller.mutation_rate, 0)
        self.assertLessEqual(self.controller.mutation_rate, initial_mutation_rate)

    def test_edge_cases(self):
        """Test edge cases for the evaluator and controller."""
        # Empty window
        empty_evaluator = MetaCognitiveEvaluator(window_size=30)
        self.assertEqual(empty_evaluator.success_rate, 0.0)
        self.assertFalse(empty_evaluator.is_brittle)
        
        # Single entry window
        single_evaluator = MetaCognitiveEvaluator(window_size=1)
        single_evaluator.record_outcome(success=True, cycle=0)
        self.assertEqual(single_evaluator.success_rate, 1.0)
        
        single_evaluator.record_outcome(success=False, cycle=1)
        self.assertEqual(single_evaluator.success_rate, 0.0)
        self.assertTrue(single_evaluator.is_brittle)
        
        # Controller with extreme values
        extreme_controller = ParameterController()
        extreme_controller.set_mutation_rate(1.0)
        extreme_controller.on_brittleness_detected()
        self.assertLess(extreme_controller.mutation_rate, 1.0)
        
        extreme_controller.set_mutation_rate(0.0)
        extreme_controller.on_stability_maintained()
        self.assertGreaterEqual(extreme_controller.mutation_rate, 0.0)


if __name__ == '__main__':
    unittest.main()