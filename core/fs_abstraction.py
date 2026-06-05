import os
import tempfile
import shutil
import time
import random
from pathlib import Path
from typing import Optional, Callable, Union
from contextlib import contextmanager


class FileSystemError(Exception):
    """Base exception for file system operations."""
    pass


class PermissionError(FileSystemError):
    """Raised when insufficient permissions for an operation."""
    pass


class RetryExhaustedError(FileSystemError):
    """Raised when all retry attempts are exhausted."""
    pass


class FileSystemAbstraction:
    """
    A robust file system abstraction with atomic writes, retry logic,
    permission checking, context manager support, and safe operations.
    """

    def __init__(self, base_path: Optional[Union[str, Path]] = None,
                 max_retries: int = 3,
                 base_delay: float = 0.5,
                 max_delay: float = 10.0,
                 jitter: bool = True):
        """
        Initialize the file system abstraction.

        Args:
            base_path: Optional base path for relative operations.
            max_retries: Maximum number of retry attempts.
            base_delay: Initial delay in seconds for exponential backoff.
            max_delay: Maximum delay in seconds.
            jitter: Whether to add random jitter to delays.
        """
        self.base_path = Path(base_path).resolve() if base_path else None
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.jitter = jitter

    def _resolve_path(self, path: Union[str, Path]) -> Path:
        """Resolve a path relative to base_path if set."""
        p = Path(path)
        if self.base_path and not p.is_absolute():
            return (self.base_path / p).resolve()
        return p.resolve()

    def _check_permissions(self, path: Path, mode: str = 'r') -> None:
        """
        Check if the current process has the required permissions.

        Args:
            path: Path to check permissions for.
            mode: 'r' for read, 'w' for write, 'x' for execute.

        Raises:
            PermissionError: If permissions are insufficient.
        """
        if not path.exists():
            # For non-existent paths, check parent directory
            parent = path.parent
            if not parent.exists():
                raise FileNotFoundError(f"Parent directory does not exist: {parent}")
            if mode == 'w' and not os.access(parent, os.W_OK):
                raise PermissionError(f"No write permission for parent directory: {parent}")
            return

        if mode == 'r' and not os.access(path, os.R_OK):
            raise PermissionError(f"No read permission: {path}")
        elif mode == 'w' and not os.access(path, os.W_OK):
            raise PermissionError(f"No write permission: {path}")
        elif mode == 'x' and not os.access(path, os.X_OK):
            raise PermissionError(f"No execute permission: {path}")

    def _retry_operation(self, operation: Callable, *args, **kwargs):
        """
        Execute an operation with exponential backoff retry logic.

        Args:
            operation: Callable to execute.
            *args: Arguments for the operation.
            **kwargs: Keyword arguments for the operation.

        Returns:
            Result of the operation.

        Raises:
            RetryExhaustedError: If all retry attempts fail.
        """
        last_exception = None
        for attempt in range(self.max_retries + 1):
            try:
                return operation(*args, **kwargs)
            except (OSError, PermissionError, FileNotFoundError) as e:
                last_exception = e
                if attempt < self.max_retries:
                    delay = min(self.base_delay * (2 ** attempt), self.max_delay)
                    if self.jitter:
                        delay += random.uniform(0, delay * 0.1)
                    time.sleep(delay)
                else:
                    raise RetryExhaustedError(
                        f"Operation failed after {self.max_retries} retries: {e}"
                    ) from e

    def atomic_write(self, path: Union[str, Path], content: Union[str, bytes],
                     encoding: str = 'utf-8', mode: str = 'w') -> None:
        """
        Write content to a file atomically using a temporary file and rename.

        Args:
            path: Target file path.
            content: Content to write (string or bytes).
            encoding: Encoding for string content.
            mode: File mode ('w' for text, 'wb' for binary).

        Raises:
            PermissionError: If write permission is denied.
            RetryExhaustedError: If all retry attempts fail.
        """
        target_path = self._resolve_path(path)
        self._check_permissions(target_path, 'w')

        def _write():
            # Create temporary file in the same directory
            temp_dir = target_path.parent
            with tempfile.NamedTemporaryFile(
                mode=mode,
                encoding=encoding if 'b' not in mode else None,
                dir=temp_dir,
                delete=False,
                prefix=f'.{target_path.name}.tmp_'
            ) as tmp_file:
                tmp_path = tmp_file.name
                if isinstance(content, str) and 'b' not in mode:
                    tmp_file.write(content)
                elif isinstance(content, bytes) and 'b' in mode:
                    tmp_file.write(content)
                else:
                    raise ValueError("Content type does not match file mode")

            # Rename temporary file to target (atomic on most file systems)
            os.replace(tmp_path, str(target_path))

        self._retry_operation(_write)

    def safe_read(self, path: Union[str, Path], encoding: str = 'utf-8',
                  mode: str = 'r') -> Union[str, bytes]:
        """
        Safely read a file with permission checking and retry logic.

        Args:
            path: File path to read.
            encoding: Encoding for text mode.
            mode: File mode ('r' for text, 'rb' for binary).

        Returns:
            File contents as string or bytes.

        Raises:
            PermissionError: If read permission is denied.
            RetryExhaustedError: If all retry attempts fail.
        """
        target_path = self._resolve_path(path)
        self._check_permissions(target_path, 'r')

        def _read():
            with open(target_path, mode=mode, encoding=encoding if 'b' not in mode else None) as f:
                return f.read()

        return self._retry_operation(_read)

    def create_directory(self, path: Union[str, Path],
                         mode: int = 0o755,
                         exist_ok: bool = True) -> None:
        """
        Create a directory with permission validation.

        Args:
            path: Directory path to create.
            mode: Permission mode for the new directory.
            exist_ok: If True, no error if directory already exists.

        Raises:
            PermissionError: If write permission is denied for parent.
            FileSystemError: If directory creation fails.
        """
        target_path = self._resolve_path(path)
        parent = target_path.parent

        if target_path.exists():
            if not target_path.is_dir():
                raise FileSystemError(f"Path exists but is not a directory: {target_path}")
            if not exist_ok:
                raise FileExistsError(f"Directory already exists: {target_path}")
            return

        self._check_permissions(parent, 'w')

        def _create():
            target_path.mkdir(mode=mode, parents=True, exist_ok=exist_ok)
            # Validate permissions after creation
            if not os.access(target_path, os.R_OK | os.X_OK):
                raise PermissionError(f"Created directory lacks read/execute permissions: {target_path}")

        self._retry_operation(_create)

    def safe_delete(self, path: Union[str, Path],
                    confirm: bool = True,
                    recursive: bool = False) -> bool:
        """
        Safely delete a file or directory with confirmation checks.

        Args:
            path: Path to delete.
            confirm: If True, verify the path exists and is the intended target.
            recursive: If True, recursively delete directories.

        Returns:
            True if deletion was successful, False otherwise.

        Raises:
            PermissionError: If write permission is denied.
            FileSystemError: If deletion fails.
        """
        target_path = self._resolve_path(path)

        if not target_path.exists():
            return False

        if confirm:
            # Double-check the path is what we expect
            resolved = target_path.resolve()
            if str(resolved) != str(target_path):
                raise FileSystemError(f"Path resolution mismatch: {target_path} -> {resolved}")

        self._check_permissions(target_path, 'w')

        def _delete():
            if target_path.is_file() or target_path.is_symlink():
                target_path.unlink()
            elif target_path.is_dir():
                if recursive:
                    shutil.rmtree(target_path)
                else:
                    target_path.rmdir()
            else:
                raise FileSystemError(f"Unknown file type: {target_path}")

        try:
            self._retry_operation(_delete)
            return True
        except (RetryExhaustedError, OSError, PermissionError):
            return False

    @contextmanager
    def safe_open(self, path: Union[str, Path], mode: str = 'r',
                  encoding: str = 'utf-8', **kwargs):
        """
        Context manager for safe file handling with permission checks.

        Args:
            path: File path to open.
            mode: File open mode.
            encoding: Encoding for text mode.
            **kwargs: Additional arguments for open().

        Yields:
            File object.

        Raises:
            PermissionError: If permissions are insufficient.
        """
        target_path = self._resolve_path(path)

        # Check permissions based on mode
        if 'r' in mode:
            self._check_permissions(target_path, 'r')
        if 'w' in mode or 'a' in mode or '+' in mode:
            self._check_permissions(target_path, 'w')

        file_obj = None
        try:
            file_obj = open(
                target_path,
                mode=mode,
                encoding=encoding if 'b' not in mode else None,
                **kwargs
            )
            yield file_obj
        finally:
            if file_obj:
                file_obj.close()

    def copy_file(self, src: Union[str, Path], dst: Union[str, Path],
                  overwrite: bool = False) -> None:
        """
        Copy a file with permission checking and retry logic.

        Args:
            src: Source file path.
            dst: Destination file path.
            overwrite: If True, overwrite existing destination.

        Raises:
            PermissionError: If permissions are insufficient.
            FileNotFoundError: If source does not exist.
        """
        src_path = self._resolve_path(src)
        dst_path = self._resolve_path(dst)

        if not src_path.exists():
            raise FileNotFoundError(f"Source file does not exist: {src_path}")

        if dst_path.exists() and not overwrite:
            raise FileExistsError(f"Destination already exists: {dst_path}")

        self._check_permissions(src_path, 'r')
        self._check_permissions(dst_path.parent, 'w')

        def _copy():
            shutil.copy2(src_path, dst_path)

        self._retry_operation(_copy)

    def move_file(self, src: Union[str, Path], dst: Union[str, Path],
                  overwrite: bool = False) -> None:
        """
        Move a file with permission checking and retry logic.

        Args:
            src: Source file path.
            dst: Destination file path.
            overwrite: If True, overwrite existing destination.

        Raises:
            PermissionError: If permissions are insufficient.
            FileNotFoundError: If source does not exist.
        """
        src_path = self._resolve_path(src)
        dst_path = self._resolve_path(dst)

        if not src_path.exists():
            raise FileNotFoundError(f"Source file does not exist: {src_path}")

        if dst_path.exists() and not overwrite:
            raise FileExistsError(f"Destination already exists: {dst_path}")

        self._check_permissions(src_path, 'w')
        self._check_permissions(dst_path.parent, 'w')

        def _move():
            shutil.move(str(src_path), str(dst_path))

        self._retry_operation(_move)

    def file_exists(self, path: Union[str, Path]) -> bool:
        """Check if a file exists with permission validation."""
        target_path = self._resolve_path(path)
        try:
            self._check_permissions(target_path, 'r')
            return target_path.exists()
        except (PermissionError, FileNotFoundError):
            return False

    def get_file_info(self, path: Union[str, Path]) -> dict:
        """
        Get file metadata with permission checking.

        Returns:
            Dictionary with file information (size, modified time, etc.).
        """
        target_path = self._resolve_path(path)
        self._check_permissions(target_path, 'r')

        stat = target_path.stat()
        return {
            'size': stat.st_size,
            'modified': stat.st_mtime,
            'created': stat.st_ctime,
            'permissions': stat.st_mode,
            'is_file': target_path.is_file(),
            'is_dir': target_path.is_dir(),
            'is_symlink': target_path.is_symlink(),
            'absolute_path': str(target_path.resolve())
        }


_fs_instance = None


def get_fs() -> FileSystemAbstraction:
    """Get the singleton FileSystemAbstraction instance."""
    global _fs_instance
    if _fs_instance is None:
        _fs_instance = FileSystemAbstraction()
    return _fs_instance