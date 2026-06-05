import os
import sys
import tempfile
import shutil
import stat
import time
import threading
import pytest
from unittest.mock import patch, MagicMock, call

# Add the parent directory to sys.path to import the module
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from fs_abstraction import (
    atomic_write,
    safe_delete,
    ensure_directory,
    set_file_permissions,
    MAX_RETRIES,
    RETRY_DELAY,
    PermissionError as FsPermissionError,
    FileSystemError
)

# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def temp_dir():
    """Create a temporary directory for testing."""
    dir_path = tempfile.mkdtemp()
    yield dir_path
    shutil.rmtree(dir_path, ignore_errors=True)

@pytest.fixture
def test_file_path(temp_dir):
    """Create a path to a test file inside temp_dir."""
    return os.path.join(temp_dir, "test_file.txt")

@pytest.fixture
def read_only_dir(temp_dir):
    """Create a read-only directory for permission tests."""
    dir_path = os.path.join(temp_dir, "read_only")
    os.makedirs(dir_path, mode=0o444)
    yield dir_path

# =============================================================================
# Test 1: Atomic write creates file correctly
# =============================================================================

class TestAtomicWriteCreatesFile:
    def test_basic_atomic_write(self, test_file_path):
        """Test that atomic_write creates a file with correct content."""
        content = b"Hello, World!"
        atomic_write(test_file_path, content)
        
        assert os.path.exists(test_file_path)
        with open(test_file_path, 'rb') as f:
            assert f.read() == content

    def test_atomic_write_with_text(self, test_file_path):
        """Test atomic_write with string content."""
        content = "Hello, World!"
        atomic_write(test_file_path, content)
        
        assert os.path.exists(test_file_path)
        with open(test_file_path, 'r') as f:
            assert f.read() == content

    def test_atomic_write_empty_content(self, test_file_path):
        """Test atomic_write with empty content."""
        atomic_write(test_file_path, b"")
        
        assert os.path.exists(test_file_path)
        assert os.path.getsize(test_file_path) == 0

    def test_atomic_write_binary_data(self, test_file_path):
        """Test atomic_write with binary data including null bytes."""
        content = bytes(range(256))
        atomic_write(test_file_path, content)
        
        with open(test_file_path, 'rb') as f:
            assert f.read() == content

# =============================================================================
# Test 2: Atomic write leaves no temp file on success
# =============================================================================

class TestAtomicWriteNoTempFile:
    def test_no_temp_file_after_success(self, test_file_path):
        """Test that no temporary file remains after successful atomic write."""
        temp_dir_path = os.path.dirname(test_file_path)
        temp_files_before = set(os.listdir(temp_dir_path))
        
        atomic_write(test_file_path, b"test content")
        
        temp_files_after = set(os.listdir(temp_dir_path))
        # Only the target file should exist (no .tmp files)
        assert temp_files_after == temp_files_before | {os.path.basename(test_file_path)}

    def test_temp_file_removed_on_exception(self, test_file_path):
        """Test that temp file is removed if an exception occurs during write."""
        with patch('builtins.open', side_effect=IOError("Write failed")):
            with pytest.raises(IOError):
                atomic_write(test_file_path, b"test")
        
        # Verify no temp file remains
        temp_dir = os.path.dirname(test_file_path)
        temp_files = [f for f in os.listdir(temp_dir) if f.endswith('.tmp')]
        assert len(temp_files) == 0

    def test_multiple_atomic_writes_no_temp(self, test_file_path):
        """Test that multiple atomic writes don't leave temp files."""
        for i in range(10):
            atomic_write(test_file_path, f"content {i}".encode())
        
        temp_dir = os.path.dirname(test_file_path)
        temp_files = [f for f in os.listdir(temp_dir) if f.endswith('.tmp')]
        assert len(temp_files) == 0

# =============================================================================
# Test 3: Retry logic succeeds after temporary failures
# =============================================================================

class TestRetryLogicSuccess:
    def test_retry_after_temporary_failure(self, test_file_path):
        """Test that retry logic succeeds after temporary failures."""
        original_open = open
        call_count = [0]
        
        def mock_open(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] <= 2:  # Fail first two attempts
                raise IOError("Temporary failure")
            return original_open(*args, **kwargs)
        
        with patch('builtins.open', mock_open):
            atomic_write(test_file_path, b"success after retry")
        
        assert os.path.exists(test_file_path)
        with open(test_file_path, 'rb') as f:
            assert f.read() == b"success after retry"

    def test_retry_success_on_third_attempt(self, test_file_path):
        """Test that retry succeeds on the third attempt."""
        original_open = open
        call_count = [0]
        
        def mock_open(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] <= 3:  # Fail first three attempts
                raise IOError("Temporary failure")
            return original_open(*args, **kwargs)
        
        with patch('builtins.open', mock_open):
            atomic_write(test_file_path, b"success after retry")
        
        assert call_count[0] == 4  # 3 failures + 1 success
        assert os.path.exists(test_file_path)

    def test_retry_delays_between_attempts(self, test_file_path):
        """Test that there are proper delays between retry attempts."""
        original_sleep = time.sleep
        sleep_times = []
        
        def mock_sleep(seconds):
            sleep_times.append(seconds)
            return original_sleep(seconds)
        
        original_open = open
        call_count = [0]
        
        def mock_open(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] <= 2:
                raise IOError("Temporary failure")
            return original_open(*args, **kwargs)
        
        with patch('time.sleep', mock_sleep), patch('builtins.open', mock_open):
            atomic_write(test_file_path, b"test")
        
        assert len(sleep_times) == 2  # Two delays for two failures
        assert all(delay > 0 for delay in sleep_times)

# =============================================================================
# Test 4: Retry logic fails after max retries
# =============================================================================

class TestRetryLogicFailure:
    def test_fails_after_max_retries(self, test_file_path):
        """Test that atomic write fails after max retries."""
        with patch('builtins.open', side_effect=IOError("Persistent failure")):
            with pytest.raises(IOError):
                atomic_write(test_file_path, b"test")
        
        assert not os.path.exists(test_file_path)

    def test_max_retries_constant(self):
        """Test that MAX_RETRIES is defined and has a reasonable value."""
        assert hasattr(sys.modules['fs_abstraction'], 'MAX_RETRIES')
        assert MAX_RETRIES >= 3  # Should have at least 3 retries

    def test_retry_count_matches_max(self, test_file_path):
        """Test that retry count matches MAX_RETRIES."""
        call_count = [0]
        
        def mock_open(*args, **kwargs):
            call_count[0] += 1
            raise IOError("Persistent failure")
        
        with patch('builtins.open', mock_open):
            with pytest.raises(IOError):
                atomic_write(test_file_path, b"test")
        
        # Should have attempted MAX_RETRIES + 1 times (initial + retries)
        assert call_count[0] == MAX_RETRIES + 1

# =============================================================================
# Test 5: Permission check prevents writes to read-only locations
# =============================================================================

class TestPermissionCheck:
    def test_write_to_read_only_directory(self, read_only_dir):
        """Test that writing to a read-only directory raises PermissionError."""
        file_path = os.path.join(read_only_dir, "test.txt")
        
        with pytest.raises(FsPermissionError):
            atomic_write(file_path, b"test")

    def test_write_to_read_only_file(self, test_file_path):
        """Test that writing to a read-only file raises PermissionError."""
        # Create a file and make it read-only
        with open(test_file_path, 'w') as f:
            f.write("original")
        os.chmod(test_file_path, stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
        
        with pytest.raises(FsPermissionError):
            atomic_write(test_file_path, b"new content")

    def test_write_to_non_existent_directory(self, temp_dir):
        """Test that writing to a non-existent directory raises appropriate error."""
        file_path = os.path.join(temp_dir, "nonexistent", "test.txt")
        
        with pytest.raises(FileNotFoundError):
            atomic_write(file_path, b"test")

    def test_permission_error_message(self, read_only_dir):
        """Test that permission error has a descriptive message."""
        file_path = os.path.join(read_only_dir, "test.txt")
        
        try:
            atomic_write(file_path, b"test")
        except FsPermissionError as e:
            assert "permission" in str(e).lower()
            assert file_path in str(e)

# =============================================================================
# Test 6: Safe deletion of existing files
# =============================================================================

class TestSafeDeletion:
    def test_safe_delete_existing_file(self, test_file_path):
        """Test that safe_delete removes an existing file."""
        # Create a file first
        with open(test_file_path, 'w') as f:
            f.write("test content")
        
        assert os.path.exists(test_file_path)
        safe_delete(test_file_path)
        assert not os.path.exists(test_file_path)

    def test_safe_delete_returns_true(self, test_file_path):
        """Test that safe_delete returns True for existing files."""
        with open(test_file_path, 'w') as f:
            f.write("test")
        
        result = safe_delete(test_file_path)
        assert result is True

    def test_safe_delete_removes_content(self, test_file_path):
        """Test that safe_delete completely removes file content."""
        with open(test_file_path, 'w') as f:
            f.write("sensitive data")
        
        safe_delete(test_file_path)
        assert not os.path.isfile(test_file_path)

# =============================================================================
# Test 7: Safe deletion fails for non-existent files
# =============================================================================

class TestSafeDeleteNonExistent:
    def test_safe_delete_non_existent(self, test_file_path):
        """Test that safe_delete returns False for non-existent files."""
        assert not os.path.exists(test_file_path)
        result = safe_delete(test_file_path)
        assert result is False

    def test_safe_delete_non_existent_no_error(self, test_file_path):
        """Test that safe_delete doesn't raise error for non-existent files."""
        # Should not raise any exception
        safe_delete(test_file_path)

    def test_safe_delete_already_deleted(self, test_file_path):
        """Test that safe_delete handles already deleted files gracefully."""
        with open(test_file_path, 'w') as f:
            f.write("test")
        
        safe_delete(test_file_path)
        # Delete again - should return False
        result = safe_delete(test_file_path)
        assert result is False

# =============================================================================
# Test 8: Directory creation with permissions
# =============================================================================

class TestDirectoryCreation:
    def test_create_directory(self, temp_dir):
        """Test that ensure_directory creates a new directory."""
        new_dir = os.path.join(temp_dir, "new_directory")
        assert not os.path.exists(new_dir)
        
        ensure_directory(new_dir)
        assert os.path.isdir(new_dir)

    def test_create_directory_with_permissions(self, temp_dir):
        """Test that ensure_directory creates directory with specified permissions."""
        new_dir = os.path.join(temp_dir, "custom_perms")
        custom_mode = 0o755
        
        ensure_directory(new_dir, mode=custom_mode)
        assert os.path.isdir(new_dir)
        
        # Check permissions (mask with 0o777 to ignore umask)
        actual_mode = stat.S_IMODE(os.stat(new_dir).st_mode)
        assert actual_mode == custom_mode

    def test_create_nested_directories(self, temp_dir):
        """Test that ensure_directory creates nested directories."""
        nested_dir = os.path.join(temp_dir, "level1", "level2", "level3")
        assert not os.path.exists(nested_dir)
        
        ensure_directory(nested_dir)
        assert os.path.isdir(nested_dir)

    def test_directory_already_exists(self, temp_dir):
        """Test that ensure_directory doesn't fail if directory already exists."""
        ensure_directory(temp_dir)  # Should not raise error
        assert os.path.isdir(temp_dir)

    def test_create_directory_with_restrictive_permissions(self, temp_dir):
        """Test creating directory with restrictive permissions."""
        new_dir = os.path.join(temp_dir, "restricted")
        ensure_directory(new_dir, mode=0o700)
        
        actual_mode = stat.S_IMODE(os.stat(new_dir).st_mode)
        assert actual_mode == 0o700

# =============================================================================
# Test 9: Concurrent write safety
# =============================================================================

class TestConcurrentWriteSafety:
    def test_concurrent_atomic_writes(self, test_file_path):
        """Test that concurrent atomic writes don't corrupt the file."""
        num_threads = 10
        errors = []
        results = []
        
        def write_content(content):
            try:
                atomic_write(test_file_path, content)
                results.append(content)
            except Exception as e:
                errors.append(e)
        
        threads = []
        for i in range(num_threads):
            content = f"Thread {i} content".encode()
            t = threading.Thread(target=write_content, args=(content,))
            threads.append(t)
            t.start()
        
        for t in threads:
            t.join()
        
        # No errors should have occurred
        assert len(errors) == 0
        
        # File should exist and contain valid content
        assert os.path.exists(test_file_path)
        with open(test_file_path, 'rb') as f:
            final_content = f.read()
        
        # Final content should be one of the thread's contents
        assert final_content in [f"Thread {i} content".encode() for i in range(num_threads)]

    def test_concurrent_read_write(self, test_file_path):
        """Test concurrent reads and writes to the same file."""
        # Create initial file
        atomic_write(test_file_path, b"initial")
        
        errors = []
        
        def writer():
            for i in range(5):
                try:
                    atomic_write(test_file_path, f"write {i}".encode())
                except Exception as e:
                    errors.append(e)
        
        def reader():
            for i in range(5):
                try:
                    if os.path.exists(test_file_path):
                        with open(test_file_path, 'rb') as f:
                            f.read()
                except Exception as e:
                    errors.append(e)
        
        threads = []
        for _ in range(3):
            threads.append(threading.Thread(target=writer))
            threads.append(threading.Thread(target=reader))
        
        for t in threads:
            t.start()
        
        for t in threads:
            t.join()
        
        assert len(errors) == 0

    def test_concurrent_directory_creation(self, temp_dir):
        """Test concurrent directory creation."""
        num_threads = 5
        errors = []
        dir_path = os.path.join(temp_dir, "concurrent_dir")
        
        def create_dir():
            try:
                ensure_directory(dir_path)
            except Exception as e:
                errors.append(e)
        
        threads = [threading.Thread(target=create_dir) for _ in range(num_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        assert len(errors) == 0
        assert os.path.isdir(dir_path)

# =============================================================================
# Test 10: File modification scenarios (create->modify->delete cycle)
# =============================================================================

class TestFileModificationCycle:
    def test_create_modify_delete_cycle(self, test_file_path):
        """Test complete file lifecycle: create, modify, then delete."""
        # Create
        atomic_write(test_file_path, b"initial content")
        assert os.path.exists(test_file_path)
        with open(test_file_path, 'rb') as f:
            assert f.read() == b"initial content"
        
        # Modify
        atomic_write(test_file_path, b"modified content")
        assert os.path.exists(test_file_path)
        with open(test_file_path, 'rb') as f:
            assert f.read() == b"modified content"
        
        # Delete
        safe_delete(test_file_path)
        assert not os.path.exists(test_file_path)

    def test_multiple_modifications(self, test_file_path):
        """Test multiple file modifications in sequence."""
        contents = [f"Version {i}".encode() for i in range(5)]
        
        for content in contents:
            atomic_write(test_file_path, content)
            with open(test_file_path, 'rb') as f:
                assert f.read() == content
        
        # Final state should be last version
        with open(test_file_path, 'rb') as f:
            assert f.read() == contents[-1]

    def test_modify_and_delete_with_permissions(self, test_file_path):
        """Test modify and delete cycle with permission changes."""
        # Create file
        atomic_write(test_file_path, b"original")
        
        # Make file read-only
        os.chmod(test_file_path, stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
        
        # Attempt to modify should fail
        with pytest.raises(FsPermissionError):
            atomic_write(test_file_path, b"modified")
        
        # Make file writable again
        os.chmod(test_file_path, stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH)
        
        # Now modification should succeed
        atomic