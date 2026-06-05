import pytest
from unittest.mock import MagicMock, patch
from dead_module_detector import DeadModuleDetector

class TestDeadModuleDetector:
    """Comprehensive tests for DeadModuleDetector."""

    @pytest.fixture
    def detector(self):
        """Fixture providing a fresh DeadModuleDetector instance."""
        return DeadModuleDetector()

    def test_usage_counter_increments(self, detector):
        """Test that usage counter increments correctly."""
        module_name = "test_module"
        assert detector.get_usage_count(module_name) == 0
        detector.record_usage(module_name)
        assert detector.get_usage_count(module_name) == 1
        detector.record_usage(module_name)
        assert detector.get_usage_count(module_name) == 2

    def test_module_with_zero_uses_in_20_cycles_flagged(self, detector):
        """Test that modules with 0 uses in 20 cycles are flagged."""
        module_name = "unused_module"
        # Simulate 20 cycles without usage
        for _ in range(20):
            detector.cycle()
        assert detector.is_flagged(module_name) == True

    def test_module_with_one_use_flagged(self, detector):
        """Test that modules with 1 use are flagged."""
        module_name = "single_use_module"
        detector.record_usage(module_name)
        # Simulate 20 cycles after the single use
        for _ in range(20):
            detector.cycle()
        assert detector.is_flagged(module_name) == True

    def test_module_with_two_or_more_uses_not_flagged(self, detector):
        """Test that modules with 2+ uses are not flagged."""
        module_name = "frequently_used_module"
        for _ in range(5):  # 5 uses
            detector.record_usage(module_name)
        # Simulate 20 cycles
        for _ in range(20):
            detector.cycle()
        assert detector.is_flagged(module_name) == False

    def test_removal_sandbox_correctly_removes_module_and_runs_tests(self, detector):
        """Test that removal sandbox correctly removes a module and runs tests."""
        module_name = "module_to_remove"
        test_command = "python -m pytest tests/"

        # Mock the subprocess to simulate successful test run
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            result = detector.sandbox_remove(module_name, test_command)
            assert result == True
            mock_run.assert_called_once_with(test_command, shell=True, capture_output=True, text=True)

    def test_rollback_when_removal_breaks_functionality(self, detector):
        """Test rollback when removal breaks functionality."""
        module_name = "critical_module"
        test_command = "python -m pytest tests/"

        # Mock the subprocess to simulate test failure
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(returncode=1)
            result = detector.sandbox_remove(module_name, test_command)
            assert result == False
            # Verify rollback was called
            assert detector.is_module_restored(module_name) == True

    def test_multiple_modules_tracking(self, detector):
        """Test tracking multiple modules simultaneously."""
        modules = ["mod_a", "mod_b", "mod_c"]
        for mod in modules:
            detector.record_usage(mod)
        # Only mod_a and mod_b get additional uses
        detector.record_usage("mod_a")
        detector.record_usage("mod_b")
        # Simulate 20 cycles
        for _ in range(20):
            detector.cycle()
        # mod_c should be flagged (only 1 use), mod_a and mod_b should not (2+ uses)
        assert detector.is_flagged("mod_c") == True
        assert detector.is_flagged("mod_a") == False
        assert detector.is_flagged("mod_b") == False

    def test_usage_counter_reset_after_cycle(self, detector):
        """Test that usage counter resets after each cycle."""
        detector.record_usage("temp_module")
        assert detector.get_usage_count("temp_module") == 1
        detector.cycle()
        # After cycle, usage count should reset to 0 for new cycle
        assert detector.get_usage_count("temp_module") == 0

    def test_flagged_modules_list(self, detector):
        """Test that flagged modules are properly listed."""
        modules = ["dead_mod1", "dead_mod2", "active_mod"]
        detector.record_usage("active_mod")
        detector.record_usage("active_mod")
        # Simulate 20 cycles
        for _ in range(20):
            detector.cycle()
        flagged = detector.get_flagged_modules()
        assert "dead_mod1" in flagged
        assert "dead_mod2" in flagged
        assert "active_mod" not in flagged