"""Snapshot Manager for managing stable snapshots of mutated modules.

This module provides functionality to capture, store, and retrieve snapshots
of module states after successful mutation promotions. It maintains an index
of snapshots per module path and supports pruning old snapshots to manage storage.
"""

import json
import os
import shutil
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
import hashlib


class SnapshotManager:
    """Manages stable snapshots of module states after successful mutation promotions."""

    def __init__(self, snapshots_dir: str = "snapshots", max_snapshots_per_module: int = 10):
        """Initialize the snapshot manager.

        Args:
            snapshots_dir: Directory to store snapshot files
            max_snapshots_per_module: Maximum number of snapshots to keep per module
        """
        self.snapshots_dir = Path(snapshots_dir)
        self.index_path = self.snapshots_dir / "index.json"
        self.max_snapshots_per_module = max_snapshots_per_module
        self._index: Dict[str, List[Dict[str, Any]]] = {}
        self._ensure_directories()
        self._load_index()

    def _ensure_directories(self) -> None:
        """Create snapshots directory if it doesn't exist."""
        self.snapshots_dir.mkdir(parents=True, exist_ok=True)

    def _load_index(self) -> None:
        """Load the snapshot index from disk."""
        if self.index_path.exists():
            try:
                with open(self.index_path, 'r') as f:
                    self._index = json.load(f)
            except (json.JSONDecodeError, IOError):
                self._index = {}
        else:
            self._index = {}

    def _save_index(self) -> None:
        """Save the snapshot index to disk."""
        with open(self.index_path, 'w') as f:
            json.dump(self._index, f, indent=2)

    def _compute_source_hash(self, source: str) -> str:
        """Compute a hash of the source code for deduplication.

        Args:
            source: Source code string

        Returns:
            SHA256 hash of the source
        """
        return hashlib.sha256(source.encode('utf-8')).hexdigest()

    def _get_snapshot_filename(self, module_path: str, timestamp: float) -> str:
        """Generate a filename for a snapshot.

        Args:
            module_path: Path to the module
            timestamp: Unix timestamp of the snapshot

        Returns:
            Filename for the snapshot
        """
        safe_path = module_path.replace('/', '_').replace('\\', '_').replace('.', '_')
        return f"{safe_path}_{timestamp}.json"

    def capture_snapshot(self, module_path: str, ast_data: Dict[str, Any], source: str) -> None:
        """Capture a snapshot of a module after successful mutation promotion.

        Args:
            module_path: Path to the module being snapshotted
            ast_data: Full AST representation of the module
            source: Source code of the module
        """
        timestamp = time.time()
        source_hash = self._compute_source_hash(source)

        snapshot = {
            "module_path": module_path,
            "timestamp": timestamp,
            "datetime": datetime.fromtimestamp(timestamp).isoformat(),
            "source_hash": source_hash,
            "ast": ast_data
        }

        # Save snapshot file
        filename = self._get_snapshot_filename(module_path, timestamp)
        filepath = self.snapshots_dir / filename
        with open(filepath, 'w') as f:
            json.dump(snapshot, f, indent=2)

        # Update index
        if module_path not in self._index:
            self._index[module_path] = []
        
        self._index[module_path].append({
            "timestamp": timestamp,
            "filename": filename,
            "source_hash": source_hash
        })

        # Prune old snapshots
        self._prune_snapshots(module_path)
        self._save_index()

    def get_latest_stable(self, module_path: str) -> Optional[Dict[str, Any]]:
        """Get the latest stable snapshot for a module.

        Args:
            module_path: Path to the module

        Returns:
            Latest snapshot data or None if no snapshots exist
        """
        if module_path not in self._index or not self._index[module_path]:
            return None

        latest = self._index[module_path][-1]
        return self._load_snapshot_file(latest["filename"])

    def get_snapshot_at(self, module_path: str, timestamp: float) -> Optional[Dict[str, Any]]:
        """Get the snapshot closest to and not after the given timestamp.

        Args:
            module_path: Path to the module
            timestamp: Unix timestamp to find snapshot for

        Returns:
            Snapshot data at or before the timestamp, or None if not found
        """
        if module_path not in self._index:
            return None

        snapshots = self._index[module_path]
        # Find the latest snapshot that is not after the given timestamp
        for snapshot in reversed(snapshots):
            if snapshot["timestamp"] <= timestamp:
                return self._load_snapshot_file(snapshot["filename"])
        
        return None

    def _load_snapshot_file(self, filename: str) -> Optional[Dict[str, Any]]:
        """Load a snapshot from file.

        Args:
            filename: Name of the snapshot file

        Returns:
            Snapshot data or None if file doesn't exist
        """
        filepath = self.snapshots_dir / filename
        if not filepath.exists():
            return None
        
        try:
            with open(filepath, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return None

    def _prune_snapshots(self, module_path: str) -> None:
        """Remove old snapshots for a module, keeping only the most recent ones.

        Args:
            module_path: Path to the module to prune snapshots for
        """
        if module_path not in self._index:
            return

        snapshots = self._index[module_path]
        if len(snapshots) <= self.max_snapshots_per_module:
            return

        # Sort by timestamp (should already be sorted, but ensure)
        snapshots.sort(key=lambda x: x["timestamp"])
        
        # Keep only the most recent ones
        to_remove = snapshots[:-self.max_snapshots_per_module]
        self._index[module_path] = snapshots[-self.max_snapshots_per_module:]

        # Delete snapshot files
        for snapshot in to_remove:
            filepath = self.snapshots_dir / snapshot["filename"]
            if filepath.exists():
                filepath.unlink()

    def get_snapshot_for_merge(self, module_path: str, timestamp: Optional[float] = None) -> Optional[Dict[str, Any]]:
        """Get a snapshot suitable for use as a base in three-way merge.

        This method integrates with conflict_resolver to provide base snapshots.

        Args:
            module_path: Path to the module
            timestamp: Optional timestamp to find snapshot at (uses latest if None)

        Returns:
            Snapshot data for use as merge base, or None if not available
        """
        if timestamp is not None:
            return self.get_snapshot_at(module_path, timestamp)
        return self.get_latest_stable(module_path)

    def list_snapshots(self, module_path: Optional[str] = None) -> Dict[str, List[Dict[str, Any]]]:
        """List all snapshots, optionally filtered by module path.

        Args:
            module_path: Optional module path to filter by

        Returns:
            Dictionary mapping module paths to lists of snapshot metadata
        """
        if module_path:
            return {module_path: self._index.get(module_path, [])}
        return dict(self._index)

    def clear_snapshots(self, module_path: Optional[str] = None) -> None:
        """Clear snapshots for a specific module or all modules.

        Args:
            module_path: Optional module path to clear snapshots for
        """
        if module_path:
            if module_path in self._index:
                for snapshot in self._index[module_path]:
                    filepath = self.snapshots_dir / snapshot["filename"]
                    if filepath.exists():
                        filepath.unlink()
                del self._index[module_path]
        else:
            # Clear all snapshots
            shutil.rmtree(self.snapshots_dir)
            self._ensure_directories()
            self._index = {}
        
        self._save_index()

    def get_snapshot_count(self, module_path: str) -> int:
        """Get the number of snapshots for a module.

        Args:
            module_path: Path to the module

        Returns:
            Number of snapshots for the module
        """
        return len(self._index.get(module_path, []))

    def get_total_snapshot_count(self) -> int:
        """Get the total number of snapshots across all modules.

        Returns:
            Total number of snapshots
        """
        return sum(len(snapshots) for snapshots in self._index.values())