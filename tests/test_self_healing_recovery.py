import unittest
from unittest.mock import Mock, patch, MagicMock, call
import logging
from datetime import datetime, timedelta
import json

# Import the module to test (assuming it exists)
# from self_healing_recovery import SelfHealingRecovery, FailureTracker, RecoveryManager

# For testing purposes, we'll define the classes here if they don't exist yet
class FailureTracker:
    def __init__(self, threshold=2, window_minutes=60):
        self.threshold = threshold
        self.window_minutes = window_minutes
        self.failures = []
        self.logger = logging.getLogger(__name__)
    
    def record_failure(self, failure_type="generic"):
        now = datetime.now()
        self.failures.append({"time": now, "type": failure_type})
        self._cleanup_old_failures()
        return self._check_recovery_needed()
    
    def _cleanup_old_failures(self):
        cutoff = datetime.now() - timedelta(minutes=self.window_minutes)
        self.failures = [f for f in self.failures if f["time"] > cutoff]
    
    def _check_recovery_needed(self):
        return len(self.failures) >= self.threshold
    
    def get_failure_count(self):
        self._cleanup_old_failures()
        return len(self.failures)

class RecoveryManager:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.recovery_attempts = 0
        self.simplified_module = None
        self.full_restored = False
        self.git_reverted = False
    
    def create_simplified_module(self, module_name):
        """Creates a simplified version of the module"""
        self.simplified_module = {
            "name": module_name,
            "version": "simplified",
            "created_at": datetime.now().isoformat(),
            "original_module": module_name
        }
        self.recovery_attempts += 1
        self.logger.info(f"Created simplified module for {module_name}")
        return self.simplified_module
    
    def restore_full_functionality(self, module_name):
        """Restores full functionality after successful simplified cycle"""
        self.full_restored = True
        self.simplified_module = None
        self.logger.info(f"Restored full functionality for {module_name}")
        return True
    
    def simulate_git_revert(self, commit_hash):
        """Simulates git revert operation"""
        self.git_reverted = True
        self.logger.info(f"Reverted git commit {commit_hash}")
        return {"status": "success", "reverted_commit": commit_hash}

class SelfHealingRecovery:
    def __init__(self, failure_threshold=2, recovery_window_minutes=60):
        self.failure_tracker = FailureTracker(threshold=failure_threshold, 
                                              window_minutes=recovery_window_minutes)
        self.recovery_manager = RecoveryManager()
        self.logger = logging.getLogger(__name__)
        self.recovery_active = False
        self.current_module = None
    
    def process_failure(self, failure_type="generic"):
        """Process a failure and determine if recovery is needed"""
        self.logger.info(f"Processing failure: {failure_type}")
        recovery_needed = self.failure_tracker.record_failure(failure_type)
        
        if recovery_needed and not self.recovery_active:
            self.recovery_active = True
            self.logger.warning(f"Recovery triggered after {self.failure_tracker.get_failure_count()} failures")
            return self._initiate_recovery()
        return {"recovery_needed": False}
    
    def _initiate_recovery(self):
        """Initiate the recovery process"""
        if self.current_module:
            simplified = self.recovery_manager.create_simplified_module(self.current_module)
            return {"recovery_needed": True, "simplified_module": simplified}
        return {"recovery_needed": True, "error": "No module to recover"}
    
    def complete_recovery_cycle(self):
        """Complete the recovery cycle and restore full functionality"""
        if self.recovery_active and self.current_module:
            self.recovery_manager.restore_full_functionality(self.current_module)
            self.recovery_active = False
            return True
        return False


class TestSelfHealingRecovery(unittest.TestCase):
    """Comprehensive tests for self-healing recovery system"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.recovery = SelfHealingRecovery(failure_threshold=2, recovery_window_minutes=60)
        self.recovery.current_module = "test_module"
        
        # Set up logging capture
        self.logger = logging.getLogger()
        self.logger.setLevel(logging.DEBUG)
        self.log_handler = logging.handlers.MemoryHandler(capacity=1000)
        self.logger.addHandler(self.log_handler)
    
    def tearDown(self):
        """Clean up after tests"""
        self.logger.removeHandler(self.log_handler)
        self.log_handler.close()
    
    def test_two_consecutive_failures_trigger_recovery(self):
        """Test that 2 consecutive failures trigger recovery"""
        # First failure should not trigger recovery
        result1 = self.recovery.process_failure("connection_error")
        self.assertFalse(result1["recovery_needed"])
        self.assertFalse(self.recovery.recovery_active)
        
        # Second failure should trigger recovery
        result2 = self.recovery.process_failure("connection_error")
        self.assertTrue(result2["recovery_needed"])
        self.assertTrue(self.recovery.recovery_active)
        self.assertIn("simplified_module", result2)
    
    def test_single_failure_does_not_trigger_recovery(self):
        """Test that single failure does not trigger recovery"""
        result = self.recovery.process_failure("timeout_error")
        self.assertFalse(result["recovery_needed"])
        self.assertFalse(self.recovery.recovery_active)
        self.assertEqual(self.recovery.failure_tracker.get_failure_count(), 1)
    
    def test_recovery_creates_simplified_module_version(self):
        """Test that recovery creates simplified module version"""
        # Trigger two failures to initiate recovery
        self.recovery.process_failure("error_1")
        result = self.recovery.process_failure("error_2")
        
        # Verify simplified module was created
        self.assertTrue(result["recovery_needed"])
        simplified = result.get("simplified_module")
        self.assertIsNotNone(simplified)
        self.assertEqual(simplified["name"], "test_module")
        self.assertEqual(simplified["version"], "simplified")
        self.assertEqual(simplified["original_module"], "test_module")
        self.assertEqual(self.recovery.recovery_manager.recovery_attempts, 1)
    
    def test_failure_patterns_logged_correctly(self):
        """Test that failure patterns are logged correctly"""
        # Clear any existing logs
        self.log_handler.buffer.clear()
        
        # Simulate different failure types
        failure_types = ["connection_error", "timeout_error", "memory_error"]
        for failure_type in failure_types:
            self.recovery.process_failure(failure_type)
        
        # Check that failures were logged
        log_messages = [record.getMessage() for record in self.log_handler.buffer]
        
        # Verify failure logging
        self.assertTrue(any("connection_error" in msg for msg in log_messages))
        self.assertTrue(any("timeout_error" in msg for msg in log_messages))
        self.assertTrue(any("memory_error" in msg for msg in log_messages))
        
        # Verify recovery trigger was logged
        self.assertTrue(any("Recovery triggered" in msg for msg in log_messages))
        
        # Verify failure count logging
        failure_count = self.recovery.failure_tracker.get_failure_count()
        self.assertEqual(failure_count, 3)  # All three failures within window
    
    def test_full_functionality_restoration_after_simplified_cycle(self):
        """Test that full functionality restoration works after one successful simplified cycle"""
        # Trigger recovery
        self.recovery.process_failure("error_1")
        self.recovery.process_failure("error_2")
        
        # Verify we're in recovery mode with simplified module
        self.assertTrue(self.recovery.recovery_active)
        self.assertIsNotNone(self.recovery.recovery_manager.simplified_module)
        
        # Complete the recovery cycle
        result = self.recovery.complete_recovery_cycle()
        self.assertTrue(result)
        
        # Verify full restoration
        self.assertFalse(self.recovery.recovery_active)
        self.assertTrue(self.recovery.recovery_manager.full_restored)
        self.assertIsNone(self.recovery.recovery_manager.simplified_module)
        
        # Verify subsequent failures start fresh
        result = self.recovery.process_failure("new_error")
        self.assertFalse(result["recovery_needed"])
    
    def test_git_revert_simulation_with_mock(self):
        """Test git revert simulation with mock"""
        # Create a mock for git operations
        with patch.object(self.recovery.recovery_manager, 'simulate_git_revert') as mock_git_revert:
            # Configure the mock
            mock_git_revert.return_value = {
                "status": "success", 
                "reverted_commit": "abc123def456"
            }
            
            # Simulate git revert
            commit_hash = "abc123def456"
            result = self.recovery.recovery_manager.simulate_git_revert(commit_hash)
            
            # Verify mock was called correctly
            mock_git_revert.assert_called_once_with(commit_hash)
            
            # Verify the result
            self.assertEqual(result["status"], "success")
            self.assertEqual(result["reverted_commit"], commit_hash)
            
            # Verify git reverted flag
            self.assertTrue(self.recovery.recovery_manager.git_reverted)
    
    def test_failure_tracking_with_window_expiry(self):
        """Test that old failures are not counted after window expiry"""
        recovery = SelfHealingRecovery(failure_threshold=2, recovery_window_minutes=1)
        recovery.current_module = "test_module"
        
        # Record first failure
        recovery.process_failure("error_1")
        self.assertEqual(recovery.failure_tracker.get_failure_count(), 1)
        
        # Simulate time passing beyond window (mock datetime)
        with patch('tests.test_self_healing_recovery.datetime') as mock_datetime:
            # Set current time to 2 minutes later
            future_time = datetime.now() + timedelta(minutes=2)
            mock_datetime.now.return_value = future_time
            
            # Record second failure - should not trigger recovery because first expired
            result = recovery.process_failure("error_2")
            self.assertFalse(result["recovery_needed"])
            self.assertEqual(recovery.failure_tracker.get_failure_count(), 1)
    
    def test_multiple_failure_types_handling(self):
        """Test handling of multiple different failure types"""
        failure_types = ["connection_error", "timeout_error", "memory_error", "disk_error"]
        
        for i, failure_type in enumerate(failure_types):
            result = self.recovery.process_failure(failure_type)
            
            # Recovery should trigger after 2nd failure
            if i >= 1:  # 0-indexed, so i=1 is the 2nd failure
                self.assertTrue(result["recovery_needed"])
                self.assertTrue(self.recovery.recovery_active)
                break
            else:
                self.assertFalse(result["recovery_needed"])
    
    def test_recovery_not_triggered_with_different_failure_types(self):
        """Test that recovery is not triggered with different failure types if threshold is type-specific"""
        # This test assumes threshold is per failure type
        recovery = SelfHealingRecovery(failure_threshold=2, recovery_window_minutes=60)
        recovery.current_module = "test_module"
        
        # Record different types of failures
        recovery.process_failure("type_a")
        recovery.process_failure("type_b")
        
        # Should not trigger recovery if threshold is per type
        self.assertFalse(recovery.recovery_active)
        self.assertEqual(recovery.failure_tracker.get_failure_count(), 2)


if __name__ == '__main__':
    unittest.main()