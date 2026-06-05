import pytest
import os
import tempfile
import threading
from unittest.mock import Mock, patch, call
from pathlib import Path
import logging

# Import the module to test - adjust import path as needed
from orchestrator import AtomicFileWriter, Orchestrator

@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)

@pytest.fixture
def snapshot_file(temp_dir):
    """Create a snapshot file with initial content."""
    snap = temp_dir / "snapshot.txt"
    snap.write_text("initial content")
    return snap

@pytest.fixture
def target_file(temp_dir):
    """Define the target file path."""
    return temp_dir / "target.txt"

@pytest.fixture
def orchestrator(temp_dir, snapshot_file):
    """Create an Orchestrator instance with mock logger."""
    logger = Mock(spec=logging.Logger)
    return Orchestrator(
        target_dir=temp_dir,
        snapshot_path=snapshot_file,
        logger=logger
    )

class TestAtomicWriteWithRollback:
    """Test suite for atomic write operations with rollback capability."""

    def test_normal_write_succeeds_and_content_correct(self, orchestrator, target_file, snapshot_file):
        """Test that normal write succeeds and file content is correct."""
        # Arrange
        expected_content = "new content for testing"

        # Act
        orchestrator.atomic_write(target_file, expected_content)

        # Assert
        assert target_file.exists()
        assert target_file.read_text() == expected_content
        # Snapshot should remain unchanged on success
        assert snapshot_file.read_text() == "initial content"

    def test_write_failure_triggers_rollback_from_snapshot(self, orchestrator, target_file, snapshot_file):
        """Test that write failure triggers rollback from snapshot."""
        # Arrange
        # Simulate a write failure by making the target directory unwritable
        original_content = snapshot_file.read_text()
        
        # Make target file read-only to cause write failure
        target_file.touch()
        target_file.chmod(0o444)  # Read-only

        # Act
        with pytest.raises(PermissionError):
            orchestrator.atomic_write(target_file, "new content")

        # Assert
        # After rollback, target should have snapshot content
        assert target_file.exists()
        assert target_file.read_text() == original_content

    def test_failure_logged_as_integration_insight(self, orchestrator, target_file):
        """Test that failure is logged as integration insight."""
        # Arrange
        error_message = "Simulated write error"
        orchestrator.logger.reset_mock()

        # Act
        with patch.object(orchestrator, '_write_content', side_effect=IOError(error_message)):
            with pytest.raises(IOError):
                orchestrator.atomic_write(target_file, "content")

        # Assert
        orchestrator.logger.error.assert_called_once()
        log_call_args = orchestrator.logger.error.call_args
        assert "atomic write failed" in str(log_call_args).lower() or \
               "integration insight" in str(log_call_args).lower() or \
               error_message in str(log_call_args)

    def test_temp_file_cleaned_up_on_success(self, orchestrator, target_file):
        """Test that temp file is cleaned up on success."""
        # Arrange
        temp_files_before = set(orchestrator.temp_dir.glob("*"))

        # Act
        orchestrator.atomic_write(target_file, "success content")

        # Assert
        temp_files_after = set(orchestrator.temp_dir.glob("*"))
        # No new temp files should remain
        assert temp_files_after == temp_files_before

    def test_temp_file_cleaned_up_on_failure(self, orchestrator, target_file):
        """Test that temp file is cleaned up on failure."""
        # Arrange
        temp_files_before = set(orchestrator.temp_dir.glob("*"))

        # Act
        with patch.object(orchestrator, '_write_content', side_effect=IOError("fail")):
            with pytest.raises(IOError):
                orchestrator.atomic_write(target_file, "content")

        # Assert
        temp_files_after = set(orchestrator.temp_dir.glob("*"))
        # No new temp files should remain after failure
        assert temp_files_after == temp_files_before

    def test_concurrent_writes_dont_interfere(self, orchestrator, target_file):
        """Test that concurrent writes don't interfere with each other."""
        # Arrange
        num_threads = 5
        results = {}
        errors = []
        lock = threading.Lock()

        def write_content(thread_id):
            try:
                content = f"content from thread {thread_id}"
                orchestrator.atomic_write(target_file, content)
                with lock:
                    results[thread_id] = content
            except Exception as e:
                with lock:
                    errors.append((thread_id, str(e)))

        # Act
        threads = [threading.Thread(target=write_content, args=(i,)) for i in range(num_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Assert
        assert len(errors) == 0, f"Concurrent writes caused errors: {errors}"
        # At least one write should have succeeded
        assert len(results) > 0
        # The final file content should be from one of the successful threads
        final_content = target_file.read_text()
        assert final_content in results.values()

    def test_concurrent_writes_with_file_locking(self, orchestrator, target_file):
        """Test that concurrent writes use proper file locking."""
        # Arrange
        num_threads = 3
        write_count = 0
        lock = threading.Lock()

        def safe_write(thread_id):
            nonlocal write_count
            try:
                orchestrator.atomic_write(target_file, f"thread {thread_id} data")
                with lock:
                    write_count += 1
            except Exception:
                pass  # Expected for some threads due to locking

        # Act
        threads = [threading.Thread(target=safe_write, args=(i,)) for i in range(num_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Assert
        # Only one write should succeed due to file locking
        assert write_count == 1, f"Expected 1 successful write, got {write_count}"
        # File should exist with content from one thread
        assert target_file.exists()
        assert "thread" in target_file.read_text()

    def test_rollback_preserves_snapshot_integrity(self, orchestrator, target_file, snapshot_file):
        """Test that rollback preserves the snapshot file integrity."""
        # Arrange
        original_snapshot_content = snapshot_file.read_text()
        snapshot_hash_before = hash(original_snapshot_content)

        # Act
        with patch.object(orchestrator, '_write_content', side_effect=IOError("fail")):
            with pytest.raises(IOError):
                orchestrator.atomic_write(target_file, "new content")

        # Assert
        # Snapshot should remain unchanged
        assert snapshot_file.read_text() == original_snapshot_content
        assert hash(snapshot_file.read_text()) == snapshot_hash_before

    def test_multiple_failures_still_rollback_correctly(self, orchestrator, target_file, snapshot_file):
        """Test that multiple consecutive failures still rollback correctly."""
        # Arrange
        original_content = snapshot_file.read_text()

        # Act - simulate multiple failures
        for i in range(3):
            with patch.object(orchestrator, '_write_content', side_effect=IOError(f"fail {i}")):
                with pytest.raises(IOError):
                    orchestrator.atomic_write(target_file, f"attempt {i}")

        # Assert
        # After multiple failures, target should still have snapshot content
        assert target_file.read_text() == original_content

    def test_large_content_write_and_rollback(self, orchestrator, target_file, snapshot_file):
        """Test with large content to ensure no memory issues."""
        # Arrange
        large_content = "A" * 10_000_000  # 10 MB of data
        original_content = snapshot_file.read_text()

        # Act - successful write
        orchestrator.atomic_write(target_file, large_content)
        assert target_file.read_text() == large_content

        # Act - failure and rollback
        with patch.object(orchestrator, '_write_content', side_effect=IOError("fail")):
            with pytest.raises(IOError):
                orchestrator.atomic_write(target_file, "B" * 10_000_000)

        # Assert
        assert target_file.read_text() == original_content

    def test_empty_content_write(self, orchestrator, target_file, snapshot_file):
        """Test writing empty content."""
        # Arrange
        original_content = snapshot_file.read_text()

        # Act
        orchestrator.atomic_write(target_file, "")

        # Assert
        assert target_file.read_text() == ""
        # Snapshot should remain unchanged
        assert snapshot_file.read_text() == original_content

    def test_binary_content_write(self, orchestrator, target_file, snapshot_file):
        """Test writing binary content."""
        # Arrange
        binary_content = b'\x00\x01\x02\x03\xff\xfe'
        original_content = snapshot_file.read_text()

        # Act
        orchestrator.atomic_write(target_file, binary_content)

        # Assert
        with open(target_file, 'rb') as f:
            assert f.read() == binary_content
        assert snapshot_file.read_text() == original_content

    def test_logger_integration_insight_format(self, orchestrator, target_file):
        """Test that integration insight log has proper format."""
        # Arrange
        orchestrator.logger.reset_mock()

        # Act
        with patch.object(orchestrator, '_write_content', side_effect=ValueError("test error")):
            with pytest.raises(ValueError):
                orchestrator.atomic_write(target_file, "content")

        # Assert
        orchestrator.logger.error.assert_called_once()
        log_msg = orchestrator.logger.error.call_args[0][0]
        # Check for key components in the log message
        assert "atomic" in log_msg.lower()
        assert "write" in log_msg.lower()
        assert "fail" in log_msg.lower() or "error" in log_msg.lower()
        assert "rollback" in log_msg.lower()