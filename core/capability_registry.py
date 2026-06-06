from typing import Dict, Optional, Any, List
import json
from datetime import datetime
from pathlib import Path
import threading


class CapabilityRegistry:
    """
    A centralized registry for managing capabilities with metadata.
    
    Each capability entry contains:
        - name: str
        - enabled: bool
        - last_benchmarked: Optional[str] (ISO format datetime)
        - benchmark_score: Optional[float]
        - age: Optional[float] (in days since creation)
    """

    def __init__(self, storage_path: Optional[str] = None):
        self._capabilities: Dict[str, Dict[str, Any]] = {}
        self._storage_path = Path(storage_path) if storage_path else None
        self._lock = threading.Lock()
        self._load()

    def _load(self) -> None:
        """Load capabilities from file if storage path is set."""
        if self._storage_path and self._storage_path.exists():
            try:
                with open(self._storage_path, 'r') as f:
                    self._capabilities = json.load(f)
            except (json.JSONDecodeError, IOError):
                self._capabilities = {}

    def _save(self) -> None:
        """Save capabilities to file if storage path is set."""
        if self._storage_path:
            self._storage_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._storage_path, 'w') as f:
                json.dump(self._capabilities, f, indent=2)

    def register(self, name: str, enabled: bool = True) -> bool:
        """
        Register a new capability.
        
        Args:
            name: The name of the capability
            enabled: Whether the capability is initially enabled
            
        Returns:
            True if registered successfully, False if already exists
        """
        with self._lock:
            if name in self._capabilities:
                return False
            
            self._capabilities[name] = {
                "name": name,
                "enabled": enabled,
                "last_benchmarked": None,
                "benchmark_score": None,
                "age": 0.0
            }
            self._save()
            return True

    def enable(self, name: str) -> bool:
        """
        Enable a capability.
        
        Args:
            name: The name of the capability
            
        Returns:
            True if enabled, False if capability not found
        """
        with self._lock:
            if name not in self._capabilities:
                return False
            
            self._capabilities[name]["enabled"] = True
            self._save()
            return True

    def disable(self, name: str) -> bool:
        """
        Disable a capability.
        
        Args:
            name: The name of the capability
            
        Returns:
            True if disabled, False if capability not found
        """
        with self._lock:
            if name not in self._capabilities:
                return False
            
            self._capabilities[name]["enabled"] = False
            self._save()
            return True

    def is_enabled(self, name: str) -> Optional[bool]:
        """
        Check if a capability is enabled.
        
        Args:
            name: The name of the capability
            
        Returns:
            True if enabled, False if disabled, None if not found
        """
        with self._lock:
            if name not in self._capabilities:
                return None
            return self._capabilities[name]["enabled"]

    def get(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Get the full metadata for a capability.
        
        Args:
            name: The name of the capability
            
        Returns:
            Capability metadata dict or None if not found
        """
        with self._lock:
            return self._capabilities.get(name)

    def get_all(self) -> Dict[str, Dict[str, Any]]:
        """
        Get all registered capabilities.
        
        Returns:
            Dict of all capabilities with their metadata
        """
        with self._lock:
            return dict(self._capabilities)

    def get_enabled(self) -> Dict[str, Dict[str, Any]]:
        """
        Get all enabled capabilities.
        
        Returns:
            Dict of enabled capabilities with their metadata
        """
        with self._lock:
            return {
                name: meta for name, meta in self._capabilities.items()
                if meta["enabled"]
            }

    def get_disabled(self) -> Dict[str, Dict[str, Any]]:
        """
        Get all disabled capabilities.
        
        Returns:
            Dict of disabled capabilities with their metadata
        """
        with self._lock:
            return {
                name: meta for name, meta in self._capabilities.items()
                if not meta["enabled"]
            }

    def set_benchmark_score(self, name: str, score: float) -> bool:
        """
        Set the benchmark score for a capability and update last_benchmarked.
        
        Args:
            name: The name of the capability
            score: The benchmark score
            
        Returns:
            True if set, False if capability not found
        """
        with self._lock:
            if name not in self._capabilities:
                return False
            
            self._capabilities[name]["benchmark_score"] = score
            self._capabilities[name]["last_benchmarked"] = datetime.now().isoformat()
            self._save()
            return True

    def get_benchmark_score(self, name: str) -> Optional[float]:
        """
        Get the benchmark score for a capability.
        
        Args:
            name: The name of the capability
            
        Returns:
            Benchmark score or None if not found/not benchmarked
        """
        with self._lock:
            cap = self._capabilities.get(name)
            if cap:
                return cap.get("benchmark_score")
            return None

    def has_been_benchmarked(self, name: str) -> bool:
        """
        Check if a capability has been benchmarked.
        
        Args:
            name: The name of the capability
            
        Returns:
            True if benchmarked, False otherwise
        """
        with self._lock:
            cap = self._capabilities.get(name)
            if cap:
                return cap.get("last_benchmarked") is not None
            return False

    def get_benchmarked_capabilities(self) -> Dict[str, Dict[str, Any]]:
        """
        Get all capabilities that have been benchmarked.
        
        Returns:
            Dict of benchmarked capabilities with their metadata
        """
        with self._lock:
            return {
                name: meta for name, meta in self._capabilities.items()
                if meta["last_benchmarked"] is not None
            }

    def get_unbenchmarked_capabilities(self) -> Dict[str, Dict[str, Any]]:
        """
        Get all capabilities that have not been benchmarked.
        
        Returns:
            Dict of unbenchmarked capabilities with their metadata
        """
        with self._lock:
            return {
                name: meta for name, meta in self._capabilities.items()
                if meta["last_benchmarked"] is None
            }

    def update_age(self, name: str, age_days: float) -> bool:
        """
        Update the age of a capability.
        
        Args:
            name: The name of the capability
            age_days: Age in days
            
        Returns:
            True if updated, False if capability not found
        """
        with self._lock:
            if name not in self._capabilities:
                return False
            
            self._capabilities[name]["age"] = age_days
            self._save()
            return True

    def remove(self, name: str) -> bool:
        """
        Remove a capability from the registry.
        
        Args:
            name: The name of the capability
            
        Returns:
            True if removed, False if not found
        """
        with self._lock:
            if name not in self._capabilities:
                return False
            
            del self._capabilities[name]
            self._save()
            return True

    def clear(self) -> None:
        """Remove all capabilities from the registry."""
        with self._lock:
            self._capabilities.clear()
            self._save()

    def count(self) -> int:
        """Get the number of registered capabilities."""
        with self._lock:
            return len(self._capabilities)

    def consolidate_duplicates(self, base_name: str, status: str = "enabled") -> int:
        """
        Consolidate duplicate entries with a common base name into a single tracked capability.
        
        This method scans all registered capabilities for entries whose names start with
        the given base_name (case-insensitive), removes all duplicates, and registers a single
        consolidated entry with the specified status.
        
        Args:
            base_name: The base name to match (e.g., '[GAME_THEORY]').
            status: The status for the consolidated entry ('enabled' or 'disabled').
            
        Returns:
            The number of duplicate entries removed.
        """
        with self._lock:
            base_lower = base_name.lower()
            duplicates: List[str] = []
            
            for name in list(self._capabilities.keys()):
                if name.lower().startswith(base_lower):
                    duplicates.append(name)
            
            if not duplicates:
                return 0
            
            removed_count = 0
            for dup_name in duplicates:
                del self._capabilities[dup_name]
                removed_count += 1
            
            enabled = status.lower() == "enabled"
            self._capabilities[base_name] = {
                "name": base_name,
                "enabled": enabled,
                "last_benchmarked": None,
                "benchmark_score": None,
                "age": 0.0
            }
            
            self._save()
            return removed_count

    def get_failure_count(self, capability_id: str) -> int:
        """
        Count consecutive failures for a capability from evolution.log.
        
        Args:
            capability_id: The ID of the capability to check
            
        Returns:
            Number of consecutive failures, or 0 if no failures found
        """
        with self._lock:
            log_path = Path("evolution.log")
            if not log_path.exists():
                return 0
            
            consecutive_failures = 0
            try:
                with open(log_path, 'r') as f:
                    lines = f.readlines()
                
                for line in reversed(lines):
                    if capability_id in line:
                        if "FAILURE" in line.upper() or "failure" in line.lower():
                            consecutive_failures += 1
                        else:
                            break
            except (IOError, OSError):
                return 0
            
            return consecutive_failures

    def archive_capability(self, capability_id: str) -> bool:
        """
        Move a capability out of the active registry into an archive.
        
        Args:
            capability_id: The ID of the capability to archive
            
        Returns:
            True if archived successfully, False if capability not found
        """
        with self._lock:
            if capability_id not in self._capabilities:
                return False
            
            archive_path = Path("archive")
            archive_path.mkdir(parents=True, exist_ok=True)
            
            archive_file = archive_path / f"{capability_id}.json"
            capability_data = self._capabilities[capability_id]
            
            try:
                with open(archive_file, 'w') as f:
                    json.dump(capability_data, f, indent=2)
                
                del self._capabilities[capability_id]
                self._save()
                return True
            except (IOError, OSError):
                return False

    def __contains__(self, name: str) -> bool:
        """Check if a capability exists in the registry."""
        with self._lock:
            return name in self._capabilities

    def __len__(self) -> int:
        """Get the number of registered capabilities."""
        with self._lock:
            return len(self._capabilities)

    def __repr__(self) -> str:
        with self._lock:
            return f"CapabilityRegistry({len(self._capabilities)} capabilities)"