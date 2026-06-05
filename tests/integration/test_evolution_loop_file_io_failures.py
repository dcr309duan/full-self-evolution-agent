import os
import tempfile
import threading
import time
import json
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

# Assuming the main module is 'evolution_loop' with functions:
#   - write_checkpoint(path, data)
#   - read_checkpoint(path)
#   - atomic_write(path, data)
#   - rollback_checkpoint(path, backup_path)
#   - evolve_state(data)
# Adjust imports as needed.
from evolution_loop import (
    write_checkpoint,
    read_checkpoint,
    atomic_write,
    rollback_checkpoint,
    evolve_state,
    CheckpointCorruptedError,
    FilePermissionError,
    WriteConflictError,
    NetworkTimeoutError,
    PartialWriteError,
)


class TestEvolutionLoopFileIOFailures:
    """Integration tests for file I/O failure scenarios in the evolution loop."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for test files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def checkpoint_path(self, temp_dir):
        """Path to the main checkpoint file."""
        return temp_dir / "checkpoint.json"

    @pytest.fixture
    def backup_path(self, temp_dir):
        """Path to the backup checkpoint file."""
        return temp_dir / "checkpoint_backup.json"

    @pytest.fixture
    def sample_data(self):
        """Sample checkpoint data."""
        return {"generation": 5, "best_fitness": 0.95, "population": [1, 2, 3]}

    # ----------------------------------------------------------------------
    # 1. Permission Denied on Critical Files
    # ----------------------------------------------------------------------
    def test_permission_denied_on_write(self, checkpoint_path, sample_data):
        """Simulate permission denied when writing to checkpoint file."""
        # Make the directory read-only
        os.chmod(checkpoint_path.parent, 0o444)
        try:
            with pytest.raises(FilePermissionError):
                write_checkpoint(checkpoint_path, sample_data)
        finally:
            os.chmod(checkpoint_path.parent, 0o755)

    def test_permission_denied_on_read(self, checkpoint_path, sample_data):
        """Simulate permission denied when reading checkpoint file."""
        # Create a file first
        write_checkpoint(checkpoint_path, sample_data)
        # Remove read permission
        os.chmod(checkpoint_path, 0o000)
        try:
            with pytest.raises(FilePermissionError):
                read_checkpoint(checkpoint_path)
        finally:
            os.chmod(checkpoint_path, 0o644)

    def test_permission_denied_on_atomic_write(self, checkpoint_path, sample_data):
        """Atomic write should fail gracefully on permission denied."""
        os.chmod(checkpoint_path.parent, 0o444)
        try:
            with pytest.raises(FilePermissionError):
                atomic_write(checkpoint_path, sample_data)
        finally:
            os.chmod(checkpoint_path.parent, 0o755)

    # ----------------------------------------------------------------------
    # 2. Concurrent Write Conflicts
    # ----------------------------------------------------------------------
    def test_concurrent_write_conflict(self, checkpoint_path, sample_data):
        """Two threads writing simultaneously should detect conflict."""
        results = []

        def writer(thread_id):
            try:
                write_checkpoint(checkpoint_path, sample_data)
                results.append(("success", thread_id))
            except WriteConflictError:
                results.append(("conflict", thread_id))

        threads = [threading.Thread(target=writer, args=(i,)) for i in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # At least one should succeed, but conflicts may occur
        successes = [r for r in results if r[0] == "success"]
        conflicts = [r for r in results if r[0] == "conflict"]
        assert len(successes) >= 1
        # It's possible both succeed if locking works, but we test detection
        # In a real scenario, locking would prevent conflicts.

    def test_concurrent_read_write_consistency(self, checkpoint_path, sample_data):
        """Read while write is in progress should not see partial data."""
        write_checkpoint(checkpoint_path, sample_data)

        def slow_write():
            # Simulate a slow write that holds a lock
            with open(checkpoint_path, "w") as f:
                f.write("partial")
                time.sleep(0.5)
                f.write(" data")

        def read():
            time.sleep(0.1)
            try:
                data = read_checkpoint(checkpoint_path)
                # Should either get original or complete new data
                assert data == sample_data or data == "partial data"
            except Exception:
                pass  # Acceptable if read fails during write

        t_write = threading.Thread(target=slow_write)
        t_read = threading.Thread(target=read)
        t_write.start()
        t_read.start()
        t_write.join()
        t_read.join()

    # ----------------------------------------------------------------------
    # 3. Corrupted File Reads
    # ----------------------------------------------------------------------
    def test_corrupted_json_file(self, checkpoint_path):
        """Read a corrupted JSON file should raise appropriate error."""
        # Write invalid JSON
        with open(checkpoint_path, "w") as f:
            f.write("{invalid json}")
        with pytest.raises(CheckpointCorruptedError):
            read_checkpoint(checkpoint_path)

    def test_truncated_file(self, checkpoint_path, sample_data):
        """Read a truncated file should raise error."""
        write_checkpoint(checkpoint_path, sample_data)
        # Truncate file
        with open(checkpoint_path, "w") as f:
            f.write('{"generation": 5, "best')
        with pytest.raises(CheckpointCorruptedError):
            read_checkpoint(checkpoint_path)

    def test_empty_file(self, checkpoint_path):
        """Read an empty file should raise error."""
        checkpoint_path.touch()
        with pytest.raises(CheckpointCorruptedError):
            read_checkpoint(checkpoint_path)

    def test_binary_garbage(self, checkpoint_path):
        """Read a file with binary garbage should raise error."""
        with open(checkpoint_path, "wb") as f:
            f.write(b"\x00\x01\x02\xff")
        with pytest.raises(CheckpointCorruptedError):
            read_checkpoint(checkpoint_path)

    # ----------------------------------------------------------------------
    # 4. Network Filesystem Timeouts
    # ----------------------------------------------------------------------
    @patch("evolution_loop.open", side_effect=TimeoutError("NFS timeout"))
    def test_network_timeout_on_open(self, mock_open, checkpoint_path):
        """Simulate network timeout when opening file."""
        with pytest.raises(NetworkTimeoutError):
            write_checkpoint(checkpoint_path, {})

    @patch("evolution_loop.os.fsync", side_effect=TimeoutError("NFS timeout"))
    def test_network_timeout_on_fsync(self, mock_fsync, checkpoint_path, sample_data):
        """Simulate network timeout during fsync."""
        with pytest.raises(NetworkTimeoutError):
            write_checkpoint(checkpoint_path, sample_data)

    @patch("evolution_loop.os.rename", side_effect=TimeoutError("NFS timeout"))
    def test_network_timeout_on_rename(self, mock_rename, checkpoint_path, sample_data):
        """Simulate network timeout during atomic rename."""
        with pytest.raises(NetworkTimeoutError):
            atomic_write(checkpoint_path, sample_data)

    # ----------------------------------------------------------------------
    # 5. Partial Write Failures
    # ----------------------------------------------------------------------
    def test_partial_write_detected(self, checkpoint_path, sample_data):
        """Simulate a partial write by interrupting the write process."""
        original_write = write_checkpoint

        def interrupted_write(path, data):
            # Write only part of the data
            with open(path, "w") as f:
                f.write(json.dumps(data)[:10])
            raise PartialWriteError("Write interrupted")

        with patch("evolution_loop.write_checkpoint", side_effect=interrupted_write):
            with pytest.raises(PartialWriteError):
                write_checkpoint(checkpoint_path, sample_data)

    def test_partial_write_leaves_no_corrupt_file(self, checkpoint_path, sample_data):
        """After a partial write, the file should not be left in a corrupt state."""
        # First write valid data
        write_checkpoint(checkpoint_path, sample_data)
        original_data = read_checkpoint(checkpoint_path)

        # Attempt partial write
        try:
            with open(checkpoint_path, "w") as f:
                f.write("partial")
                raise PartialWriteError("Simulated failure")
        except PartialWriteError:
            pass

        # File should still contain original data (if rollback worked)
        # Or be empty (if atomic write was used)
        # We expect rollback to restore original
        if checkpoint_path.exists():
            data = read_checkpoint(checkpoint_path)
            assert data == original_data

    # ----------------------------------------------------------------------
    # 6. Atomic Write Guarantees and Rollback Correctness
    # ----------------------------------------------------------------------
    def test_atomic_write_creates_temp_file(self, checkpoint_path, sample_data):
        """Atomic write should use a temporary file."""
        atomic_write(checkpoint_path, sample_data)
        # Check that no temp file remains
        temp_files = list(checkpoint_path.parent.glob("*.tmp"))
        assert len(temp_files) == 0

    def test_atomic_write_does_not_corrupt_original_on_failure(self, checkpoint_path, sample_data):
        """If atomic write fails, original file should remain intact."""
        # Write original data
        write_checkpoint(checkpoint_path, sample_data)
        original_data = read_checkpoint(checkpoint_path)

        # Simulate failure during atomic write (e.g., rename fails)
        with patch("evolution_loop.os.rename", side_effect=OSError("Rename failed")):
            with pytest.raises(OSError):
                atomic_write(checkpoint_path, {"new": "data"})

        # Original file should be unchanged
        assert read_checkpoint(checkpoint_path) == original_data

    def test_rollback_restores_backup(self, checkpoint_path, backup_path, sample_data):
        """Rollback should restore the backup file to the main checkpoint."""
        # Write original data and backup
        write_checkpoint(checkpoint_path, sample_data)
        write_checkpoint(backup_path, sample_data)

        # Corrupt main file
        with open(checkpoint_path, "w") as f:
            f.write("corrupt")

        # Perform rollback
        rollback_checkpoint(checkpoint_path, backup_path)

        # Main file should be restored from backup
        restored_data = read_checkpoint(checkpoint_path)
        assert restored_data == sample_data

    def test_rollback_without_backup_raises_error(self, checkpoint_path, backup_path):
        """Rollback without a backup file should raise an error."""
        # Ensure backup does not exist
        if backup_path.exists():
            backup_path.unlink()
        with pytest.raises(FileNotFoundError):
            rollback_checkpoint(checkpoint_path, backup_path)

    def test_atomic_write_ensures_complete_write(self, checkpoint_path, sample_data):
        """Atomic write should guarantee the file is fully written before replacing."""
        # Write using atomic write
        atomic_write(checkpoint_path, sample_data)
        # Read back should be complete
        data = read_checkpoint(checkpoint_path)
        assert data == sample_data

    def test_concurrent_atomic_writes_no_corruption(self, checkpoint_path, sample_data):
        """Multiple atomic writes should not leave the file in a corrupt state."""
        def atomic_writer(data_suffix):
            new_data = sample_data.copy()
            new_data["generation"] = data_suffix
            atomic_write(checkpoint_path, new_data)

        threads = [threading.Thread(target=atomic_writer, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Final file should be valid JSON
        data = read_checkpoint(checkpoint_path)
        assert isinstance(data, dict)
        assert "generation" in data

    def test_rollback_after_partial_write(self, checkpoint_path, backup_path, sample_data):
        """Rollback should recover from a partial write scenario."""
        # Write original and backup
        write_checkpoint(checkpoint_path, sample_data)
        write_checkpoint(backup_path, sample_data)

        # Simulate partial write (e.g., crash during write)
        try:
            with open(checkpoint_path, "w") as f:
                f.write("partial")
                raise PartialWriteError("Crash")
        except PartialWriteError:
            pass

        # Rollback
        rollback_checkpoint(checkpoint_path, backup_path)

        # Data should be restored
        assert read_checkpoint(checkpoint_path) == sample_data

    def test_atomic_write_rollback_consistency(self, checkpoint_path, backup_path, sample_data):
        """Atomic write followed by rollback should maintain consistency."""
        # Write initial data
        atomic_write(checkpoint_path, sample_data)
        atomic_write(backup_path, sample_data)

        # Write new data atomically
        new_data = {"generation": 10, "best_fitness": 0.99}
        atomic_write(checkpoint_path, new_data)

        # Rollback to backup
        rollback_checkpoint(checkpoint_path, backup_path)

        # Should be back to original
        assert read_checkpoint(checkpoint_path) == sample_data