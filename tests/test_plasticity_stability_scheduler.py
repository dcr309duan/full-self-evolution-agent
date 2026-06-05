import unittest
from unittest.mock import Mock, patch
import logging
from plasticity_stability_scheduler import PlasticityStabilityScheduler
from system_state import SystemState

class TestPlasticityStabilityScheduler(unittest.TestCase):
    def setUp(self):
        self.scheduler = PlasticityStabilityScheduler()
        self.system_state = SystemState()
        self.logger = logging.getLogger('test_logger')
        self.logger.setLevel(logging.DEBUG)
        self.logger.addHandler(logging.NullHandler())

    def test_three_consecutive_failures_trigger_adjustment(self):
        """Test that 3 consecutive failures trigger a plasticity adjustment."""
        initial_plasticity = self.scheduler.plasticity
        for _ in range(3):
            self.scheduler.record_failure()
        self.assertGreater(self.scheduler.plasticity, initial_plasticity,
                          "Plasticity should increase after 3 consecutive failures")

    def test_three_consecutive_successes_trigger_reverse_adjustment(self):
        """Test that 3 consecutive successes trigger a stability adjustment."""
        # First set a high plasticity to ensure we have room to decrease
        self.scheduler.plasticity = 0.8
        initial_plasticity = self.scheduler.plasticity
        for _ in range(3):
            self.scheduler.record_success()
        self.assertLess(self.scheduler.plasticity, initial_plasticity,
                       "Plasticity should decrease after 3 consecutive successes")

    def test_clamping_behavior(self):
        """Test that plasticity and stability values are properly clamped."""
        # Test lower bound clamping
        self.scheduler.plasticity = -0.1
        self.scheduler._clamp_values()
        self.assertGreaterEqual(self.scheduler.plasticity, 0.0,
                               "Plasticity should be clamped to minimum of 0.0")
        
        # Test upper bound clamping
        self.scheduler.plasticity = 1.5
        self.scheduler._clamp_values()
        self.assertLessEqual(self.scheduler.plasticity, 1.0,
                            "Plasticity should be clamped to maximum of 1.0")
        
        # Test stability clamping
        self.scheduler.stability = -0.2
        self.scheduler._clamp_values()
        self.assertGreaterEqual(self.scheduler.stability, 0.0,
                               "Stability should be clamped to minimum of 0.0")
        
        self.scheduler.stability = 2.0
        self.scheduler._clamp_values()
        self.assertLessEqual(self.scheduler.stability, 1.0,
                            "Stability should be clamped to maximum of 1.0")

    def test_logging_works_correctly(self):
        """Test that logging messages are generated correctly."""
        with self.assertLogs('test_logger', level='INFO') as log:
            self.scheduler.logger = self.logger
            self.scheduler.record_failure()
            self.scheduler.record_success()
            self.assertTrue(any("failure" in message.lower() for message in log.output),
                           "Log should contain failure-related messages")
            self.assertTrue(any("success" in message.lower() for message in log.output),
                           "Log should contain success-related messages")

    def test_integration_with_system_state(self):
        """Test integration with system state."""
        # Simulate system state changes
        self.system_state.performance = 0.3  # Low performance
        self.system_state.error_rate = 0.8   # High error rate
        
        # Update scheduler based on system state
        self.scheduler.update_from_system_state(self.system_state)
        
        # Verify that system state influences scheduler decisions
        self.assertGreater(self.scheduler.plasticity, 0.5,
                          "Plasticity should be higher when system has high error rate")
        
        # Simulate improved system state
        self.system_state.performance = 0.9
        self.system_state.error_rate = 0.1
        self.scheduler.update_from_system_state(self.system_state)
        
        # Verify scheduler adjusts to improved state
        self.assertLess(self.scheduler.plasticity, 0.5,
                       "Plasticity should be lower when system has low error rate")

    def test_mixed_success_failure_pattern(self):
        """Test that mixed patterns don't trigger adjustments."""
        initial_plasticity = self.scheduler.plasticity
        self.scheduler.record_failure()
        self.scheduler.record_success()
        self.scheduler.record_failure()
        self.assertEqual(self.scheduler.plasticity, initial_plasticity,
                        "Mixed success/failure pattern should not trigger adjustment")

    def test_counter_reset_on_opposite_event(self):
        """Test that counters reset when opposite event occurs."""
        # Build up failure count
        self.scheduler.record_failure()
        self.scheduler.record_failure()
        self.assertEqual(self.scheduler.failure_count, 2)
        
        # Record success should reset failure count
        self.scheduler.record_success()
        self.assertEqual(self.scheduler.failure_count, 0,
                        "Failure count should reset after a success")
        
        # Build up success count
        self.scheduler.record_success()
        self.scheduler.record_success()
        self.assertEqual(self.scheduler.success_count, 2)
        
        # Record failure should reset success count
        self.scheduler.record_failure()
        self.assertEqual(self.scheduler.success_count, 0,
                        "Success count should reset after a failure")

if __name__ == '__main__':
    unittest.main()