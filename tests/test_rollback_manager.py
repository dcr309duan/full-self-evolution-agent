import pytest
import os
import tempfile
import json
import threading
from pathlib import Path
from unittest.mock import patch, MagicMock

# Assuming the rollback manager is in a module named 'rollback_manager'
from rollback_manager import RollbackManager, AtomicFileWrite, RollbackLog

class TestRollbackManager:

    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def rollback_manager(self, temp_dir):
        return RollbackManager(log_dir=temp_dir / "logs")

    def test_atomic_file_write_with_rollback(self, temp_dir, rollback_manager):
        """Test that atomic file write can be rolled back successfully."""
        target_file = temp_dir / "test_file.txt"
        original_content = "original content"
        new_content = "new content"

        # Write original content
        target_file.write_text(original_content)

        # Perform atomic write
        atomic_write = AtomicFileWrite(target_file, new_content)
        rollback_manager.register_operation(atomic_write)
        atomic_write.execute()

        # Verify new content is written
        assert target_file.read_text() == new_content

        # Rollback
        rollback_manager.rollback()

        # Verify original content is restored
        assert target_file.read_text() == original_content

    def test_partial_failure_recovery(self, temp_dir, rollback_manager):
        """Test recovery from partial failure during multiple operations."""
        files = []
        for i in range(5):
            file_path = temp_dir / f"file_{i}.txt"
            file_path.write_text(f"original_{i}")
            files.append(file_path)

        # Register operations but simulate failure on the third operation
        operations = []
        for i, file_path in enumerate(files):
            atomic_write = AtomicFileWrite(file_path, f"new_content_{i}")
            rollback_manager.register_operation(atomic_write)
            operations.append(atomic_write)

        # Execute operations with simulated failure
        with patch.object(operations[2], 'execute', side_effect=Exception("Simulated failure")):
            with pytest.raises(Exception):
                for op in operations:
                    op.execute()

        # Verify rollback was triggered
        for i, file_path in enumerate(files):
            assert file_path.read_text() == f"original_{i}"

    def test_log_integrity(self, temp_dir, rollback_manager):
        """Test that rollback log maintains integrity after operations."""
        # Create multiple operations
        for i in range(3):
            file_path = temp_dir / f"log_test_{i}.txt"
            file_path.write_text(f"original_{i}")
            atomic_write = AtomicFileWrite(file_path, f"new_{i}")
            rollback_manager.register_operation(atomic_write)
            atomic_write.execute()

        # Check log file exists and is valid JSON
        log_file = rollback_manager.log_dir / "rollback_log.json"
        assert log_file.exists()

        with open(log_file, 'r') as f:
            log_data = json.load(f)

        # Verify log structure
        assert isinstance(log_data, list)
        assert len(log_data) == 3

        for i, entry in enumerate(log_data):
            assert "operation_type" in entry
            assert "target_path" in entry
            assert "original_content" in entry
            assert "new_content" in entry
            assert entry["operation_type"] == "atomic_file_write"
            assert Path(entry["target_path"]).name == f"log_test_{i}.txt"
            assert entry["original_content"] == f"original_{i}"
            assert entry["new_content"] == f"new_{i}"

    def test_concurrent_mutation_rollback(self, temp_dir):
        """Test rollback with concurrent file mutations."""
        rollback_manager = RollbackManager(log_dir=temp_dir / "logs")
        test_file = temp_dir / "concurrent_test.txt"
        test_file.write_text("initial")

        errors = []
        lock = threading.Lock()

        def mutate_file(thread_id):
            try:
                with lock:
                    content = test_file.read_text()
                    new_content = f"{content}_thread_{thread_id}"
                    atomic_write = AtomicFileWrite(test_file, new_content)
                    rollback_manager.register_operation(atomic_write)
                    atomic_write.execute()
            except Exception as e:
                errors.append(e)

        # Create multiple threads that mutate the same file
        threads = []
        for i in range(5):
            t = threading.Thread(target=mutate_file, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        # Rollback all operations
        rollback_manager.rollback()

        # Verify file returned to initial state
        assert test_file.read_text() == "initial"
        assert len(errors) == 0, f"Errors occurred: {errors}"

    def test_rollback_with_non_existent_backup(self, temp_dir, rollback_manager):
        """Test rollback when backup file doesn't exist."""
        test_file = temp_dir / "new_file.txt"
        new_content = "new file content"

        atomic_write = AtomicFileWrite(test_file, new_content)
        rollback_manager.register_operation(atomic_write)
        atomic_write.execute()

        # Delete the backup file
        backup_file = rollback_manager.log_dir / f"{test_file.name}.backup"
        if backup_file.exists():
            backup_file.unlink()

        # Rollback should handle missing backup gracefully
        rollback_manager.rollback()

        # File should be deleted since it didn't exist before
        assert not test_file.exists()

    def test_multiple_rollbacks(self, temp_dir, rollback_manager):
        """Test that multiple rollbacks don't cause issues."""
        test_file = temp_dir / "multi_rollback.txt"
        test_file.write_text("version_0")

        # Perform multiple operations
        for i in range(1, 4):
            atomic_write = AtomicFileWrite(test_file, f"version_{i}")
            rollback_manager.register_operation(atomic_write)
            atomic_write.execute()

        # Rollback multiple times
        rollback_manager.rollback()
        assert test_file.read_text() == "version_0"

        # Second rollback should be idempotent
        rollback_manager.rollback()
        assert test_file.read_text() == "version_0"