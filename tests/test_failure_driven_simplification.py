import pytest
import logging
from unittest.mock import Mock, patch, call
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

# Assuming the module is named 'failure_driven_simplification' and contains:
# - FailureDrivenSimplificationManager (or similar class)
# - DeprecationEvent (dataclass or namedtuple)
# - CapabilityRegistry (singleton or class with register/remove methods)
# - _deprecation_logger (module-level logger)

from failure_driven_simplification import (
    FailureDrivenSimplificationManager,
    DeprecationEvent,
    CapabilityRegistry,
    _deprecation_logger,
    MAX_CONSECUTIVE_FAILURES,
)


@pytest.fixture
def manager():
    """Fixture to create a fresh manager instance for each test."""
    return FailureDrivenSimplificationManager()


@pytest.fixture
def capability_registry():
    """Fixture to reset the capability registry before each test."""
    registry = CapabilityRegistry()
    registry.clear()  # Assuming clear() method exists
    return registry


@pytest.fixture
def mock_logger():
    """Fixture to mock the deprecation logger."""
    with patch.object(_deprecation_logger, 'warning') as mock_warning:
        yield mock_warning


class TestFailureDrivenSimplification:
    """Comprehensive tests for failure-driven simplification mechanism."""

    def test_three_consecutive_failures_trigger_deprecation(self, manager, mock_logger):
        """Test that 3 consecutive failures trigger deprecation."""
        # Arrange: Register a capability
        capability_id = "test_capability_1"
        manager.register_capability(capability_id, lambda: "result")

        # Act: Record 3 consecutive failures
        for _ in range(3):
            manager.record_failure(capability_id)

        # Assert: Deprecation should be triggered
        assert manager.is_deprecated(capability_id), "Capability should be deprecated after 3 failures"
        mock_logger.assert_called_once_with(
            f"Capability '{capability_id}' deprecated after 3 consecutive failures"
        )

    def test_two_failures_do_not_trigger_deprecation(self, manager, mock_logger):
        """Test that 2 failures do NOT trigger deprecation."""
        # Arrange: Register a capability
        capability_id = "test_capability_2"
        manager.register_capability(capability_id, lambda: "result")

        # Act: Record 2 consecutive failures
        for _ in range(2):
            manager.record_failure(capability_id)

        # Assert: Deprecation should NOT be triggered
        assert not manager.is_deprecated(capability_id), "Capability should NOT be deprecated after 2 failures"
        mock_logger.assert_not_called()

    def test_success_resets_failure_counter(self, manager, mock_logger):
        """Test that a successful execution between failures resets the counter."""
        # Arrange: Register a capability
        capability_id = "test_capability_3"
        manager.register_capability(capability_id, lambda: "result")

        # Act: Record 2 failures, then a success, then another failure
        manager.record_failure(capability_id)
        manager.record_failure(capability_id)
        manager.record_success(capability_id)  # This should reset the counter
        manager.record_failure(capability_id)

        # Assert: Only 1 failure counted after success, so deprecation should NOT trigger
        assert not manager.is_deprecated(capability_id), "Capability should NOT be deprecated after success resets counter"
        mock_logger.assert_not_called()

    def test_deprecated_module_removed_from_registry(self, manager, capability_registry):
        """Test that deprecated module is removed from capability registry."""
        # Arrange: Register a capability in both manager and registry
        capability_id = "test_capability_4"
        manager.register_capability(capability_id, lambda: "result")
        capability_registry.register(capability_id, "some_module")

        # Act: Trigger deprecation by recording 3 failures
        for _ in range(3):
            manager.record_failure(capability_id)

        # Assert: Capability should be removed from registry
        assert not capability_registry.has_capability(capability_id), (
            "Deprecated capability should be removed from registry"
        )

    def test_deprecation_logs_created_with_proper_metadata(self, manager, mock_logger):
        """Test that deprecation logs are created with proper metadata."""
        # Arrange: Register a capability
        capability_id = "test_capability_5"
        manager.register_capability(capability_id, lambda: "result")

        # Act: Trigger deprecation
        for _ in range(3):
            manager.record_failure(capability_id)

        # Assert: Check log call arguments for metadata
        expected_message = f"Capability '{capability_id}' deprecated after 3 consecutive failures"
        mock_logger.assert_called_once_with(expected_message)
        
        # If logger supports extra metadata, we can check that too
        # Assuming the logger call includes extra kwargs like extra={'capability_id': capability_id, 'failures': 3}
        # Uncomment the following if applicable:
        # call_args = mock_logger.call_args
        # assert call_args[0][0] == expected_message
        # assert call_args[1].get('extra', {}).get('capability_id') == capability_id
        # assert call_args[1].get('extra', {}).get('failures') == 3

    def test_manual_restore_functionality(self, manager, mock_logger):
        """Test manual restore functionality for deprecated capabilities."""
        # Arrange: Register and deprecate a capability
        capability_id = "test_capability_6"
        manager.register_capability(capability_id, lambda: "result")
        for _ in range(3):
            manager.record_failure(capability_id)
        assert manager.is_deprecated(capability_id), "Capability should be deprecated before restore"

        # Act: Manually restore the capability
        manager.restore_capability(capability_id)

        # Assert: Capability should no longer be deprecated
        assert not manager.is_deprecated(capability_id), "Capability should be restored after manual restore"
        # The failure counter should be reset
        assert manager.get_failure_count(capability_id) == 0, "Failure count should be reset after restore"
        # The capability should be re-registered in the registry (if applicable)
        # Assuming restore also re-registers in capability_registry
        # assert capability_registry.has_capability(capability_id)

    def test_restore_non_deprecated_capability(self, manager):
        """Test that restoring a non-deprecated capability does nothing or raises appropriate error."""
        # Arrange: Register a capability but don't deprecate it
        capability_id = "test_capability_7"
        manager.register_capability(capability_id, lambda: "result")

        # Act & Assert: Restoring a non-deprecated capability should not raise an error
        # but should also not change state
        try:
            manager.restore_capability(capability_id)
        except Exception as e:
            pytest.fail(f"Restoring non-deprecated capability raised an exception: {e}")

        # Assert: Capability should still not be deprecated
        assert not manager.is_deprecated(capability_id), "Capability should remain non-deprecated"

    def test_deprecation_with_multiple_capabilities(self, manager, mock_logger):
        """Test that deprecation of one capability doesn't affect others."""
        # Arrange: Register two capabilities
        cap1 = "capability_A"
        cap2 = "capability_B"
        manager.register_capability(cap1, lambda: "result_A")
        manager.register_capability(cap2, lambda: "result_B")

        # Act: Deprecate cap1 only
        for _ in range(3):
            manager.record_failure(cap1)
        # Record only 1 failure for cap2
        manager.record_failure(cap2)

        # Assert: Only cap1 should be deprecated
        assert manager.is_deprecated(cap1), "cap1 should be deprecated"
        assert not manager.is_deprecated(cap2), "cap2 should NOT be deprecated"
        # Logger should have been called only once for cap1
        assert mock_logger.call_count == 1

    def test_failure_count_accuracy(self, manager):
        """Test that failure count is accurately tracked."""
        # Arrange: Register a capability
        capability_id = "test_capability_8"
        manager.register_capability(capability_id, lambda: "result")

        # Act: Record various numbers of failures and successes
        manager.record_failure(capability_id)
        manager.record_failure(capability_id)
        manager.record_success(capability_id)
        manager.record_failure(capability_id)
        manager.record_failure(capability_id)
        manager.record_failure(capability_id)

        # Assert: After success, counter reset, then 3 failures should trigger deprecation
        assert manager.is_deprecated(capability_id), "Capability should be deprecated after 3 failures post-success"
        assert manager.get_failure_count(capability_id) == 3, "Failure count should be 3 after reset and 3 failures"

    def test_deprecation_event_creation(self, manager):
        """Test that deprecation events are created with correct metadata."""
        # Arrange: Register a capability
        capability_id = "test_capability_9"
        manager.register_capability(capability_id, lambda: "result")

        # Act: Trigger deprecation
        for _ in range(3):
            manager.record_failure(capability_id)

        # Assert: Check that a DeprecationEvent was created
        events = manager.get_deprecation_events()  # Assuming this method exists
        assert len(events) == 1, "Should be exactly one deprecation event"
        event = events[0]
        assert event.capability_id == capability_id
        assert event.failure_count == 3
        assert isinstance(event.timestamp, datetime)
        # Check that timestamp is recent (within last minute)
        assert datetime.now() - event.timestamp < timedelta(minutes=1)

    def test_restore_after_multiple_deprecations(self, manager):
        """Test restoring after multiple deprecations of the same capability."""
        # Arrange: Register and deprecate a capability
        capability_id = "test_capability_10"
        manager.register_capability(capability_id, lambda: "result")
        for _ in range(3):
            manager.record_failure(capability_id)
        assert manager.is_deprecated(capability_id)

        # Act: Restore and then deprecate again
        manager.restore_capability(capability_id)
        for _ in range(3):
            manager.record_failure(capability_id)

        # Assert: Capability should be deprecated again
        assert manager.is_deprecated(capability_id), "Capability should be deprecated again after restore and failures"
        # Check that there are now two deprecation events
        events = manager.get_deprecation_events()
        assert len(events) == 2, "Should be two deprecation events after restore and re-deprecation"

    def test_deprecation_logger_metadata(self, manager, mock_logger):
        """Test that deprecation logger includes proper metadata in log records."""
        # Arrange: Register a capability
        capability_id = "test_capability_11"
        manager.register_capability(capability_id, lambda: "result")

        # Act: Trigger deprecation
        for _ in range(3):
            manager.record_failure(capability_id)

        # Assert: Check that the logger was called with the correct message
        # and any additional metadata (if the logger supports it)
        expected_message = f"Capability '{capability_id}' deprecated after 3 consecutive failures"
        mock_logger.assert_called_once_with(expected_message)
        
        # If the logger uses structured logging or extra kwargs, verify them
        # For example, if the logger is called as:
        # _deprecation_logger.warning(msg, extra={'capability_id': cap_id, 'failures': count})
        # Uncomment and adjust as needed:
        # call_args = mock_logger.call_args
        # assert call_args[0][0] == expected_message
        # extra = call_args[1].get('extra', {})
        # assert extra.get('capability_id') == capability_id
        # assert extra.get('failures') == 3
        # assert 'timestamp' in extra