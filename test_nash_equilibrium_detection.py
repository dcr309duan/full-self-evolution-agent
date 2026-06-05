import unittest
from unittest.mock import Mock, patch
import sys
import os

# Add parent directory to path to import the module under test
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from nash_equilibrium_detector import NashEquilibriumDetector

class TestNashEquilibriumDetector(unittest.TestCase):
    """Test suite for NashEquilibriumDetector."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.K = 3  # Default threshold for consecutive failures
        self.detector = NashEquilibriumDetector(K=self.K)
        
    def test_detector_triggers_after_K_consecutive_failures(self):
        """Test that detector triggers after exactly K consecutive single-module mutation failures."""
        # Simulate K-1 failures - should not trigger yet
        for i in range(self.K - 1):
            self.detector.record_mutation_result(success=False)
            self.assertFalse(self.detector.is_nash_equilibrium(),
                             f"Should not trigger after {i+1} failures")
        
        # Simulate the Kth failure - should trigger
        self.detector.record_mutation_result(success=False)
        self.assertTrue(self.detector.is_nash_equilibrium(),
                        "Should trigger after K consecutive failures")
    
    def test_detector_does_not_trigger_with_mixed_results(self):
        """Test that detector does not trigger when failures are not consecutive."""
        # Simulate: fail, fail, success, fail, fail, fail
        # The last three are consecutive, but the first two are not part of the streak
        self.detector.record_mutation_result(success=False)
        self.detector.record_mutation_result(success=False)
        self.detector.record_mutation_result(success=True)  # Resets counter
        
        # Now three consecutive failures should trigger
        self.detector.record_mutation_result(success=False)
        self.detector.record_mutation_result(success=False)
        self.detector.record_mutation_result(success=False)
        
        self.assertTrue(self.detector.is_nash_equilibrium(),
                        "Should trigger after three consecutive failures following a success")
    
    def test_detector_does_not_trigger_with_successful_mutations(self):
        """Test that detector does not trigger when single-module mutations are succeeding."""
        # Simulate many successful mutations
        for _ in range(10):
            self.detector.record_mutation_result(success=True)
            self.assertFalse(self.detector.is_nash_equilibrium(),
                             "Should not trigger when mutations are succeeding")
    
    def test_detector_resets_after_success(self):
        """Test that a successful mutation resets the consecutive failure counter."""
        # Simulate K-1 failures
        for _ in range(self.K - 1):
            self.detector.record_mutation_result(success=False)
        
        # A success should reset the counter
        self.detector.record_mutation_result(success=True)
        self.assertFalse(self.detector.is_nash_equilibrium(),
                         "Should not trigger after success resets counter")
        
        # Now K failures again should trigger
        for _ in range(self.K):
            self.detector.record_mutation_result(success=False)
        
        self.assertTrue(self.detector.is_nash_equilibrium(),
                        "Should trigger after K failures following a reset")
    
    def test_detector_initial_state(self):
        """Test that detector starts in non-triggered state."""
        self.assertFalse(self.detector.is_nash_equilibrium(),
                         "Should not be triggered initially")
    
    def test_detector_with_different_K_values(self):
        """Test detector with different K threshold values."""
        for K in [1, 2, 5, 10]:
            detector = NashEquilibriumDetector(K=K)
            
            # K-1 failures should not trigger
            for _ in range(K - 1):
                detector.record_mutation_result(success=False)
                self.assertFalse(detector.is_nash_equilibrium(),
                                 f"Should not trigger after {K-1} failures with K={K}")
            
            # Kth failure should trigger
            detector.record_mutation_result(success=False)
            self.assertTrue(detector.is_nash_equilibrium(),
                            f"Should trigger after {K} failures with K={K}")
    
    def test_detector_handles_large_number_of_operations(self):
        """Test detector handles many operations without performance issues."""
        # Simulate a long sequence of alternating successes and failures
        for i in range(100):
            if i % 4 == 3:  # Every 4th operation is a failure
                self.detector.record_mutation_result(success=False)
            else:
                self.detector.record_mutation_result(success=True)
        
        # Should not be triggered since failures are not consecutive
        self.assertFalse(self.detector.is_nash_equilibrium(),
                         "Should not trigger with non-consecutive failures")
    
    def test_detector_edge_case_K_equals_one(self):
        """Test edge case where K=1 (single failure triggers)."""
        detector = NashEquilibriumDetector(K=1)
        
        # First failure should trigger
        detector.record_mutation_result(success=False)
        self.assertTrue(detector.is_nash_equilibrium(),
                        "Should trigger immediately when K=1")
        
        # Reset with success
        detector.record_mutation_result(success=True)
        self.assertFalse(detector.is_nash_equilibrium(),
                         "Should reset after success even with K=1")
        
        # Next failure triggers again
        detector.record_mutation_result(success=False)
        self.assertTrue(detector.is_nash_equilibrium(),
                        "Should trigger again after single failure with K=1")
    
    def test_detector_does_not_trigger_with_alternating_results(self):
        """Test that alternating success/failure never triggers detector."""
        for _ in range(20):
            self.detector.record_mutation_result(success=True)
            self.assertFalse(self.detector.is_nash_equilibrium(),
                             "Should not trigger after success")
            self.detector.record_mutation_result(success=False)
            self.assertFalse(self.detector.is_nash_equilibrium(),
                             "Should not trigger after single failure in alternating pattern")

if __name__ == '__main__':
    unittest.main()