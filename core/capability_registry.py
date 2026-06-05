from typing import Dict, Optional, Any
import json
from datetime import datetime
from pathlib import Path


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
        return self._capabilities.get(name)

    def get_all(self) -> Dict[str, Dict[str, Any]]:
        """
        Get all registered capabilities.
        
        Returns:
            Dict of all capabilities with their metadata
        """
        return dict(self._capabilities)

    def get_enabled(self) -> Dict[str, Dict[str, Any]]:
        """
        Get all enabled capabilities.
        
        Returns:
            Dict of enabled capabilities with their metadata
        """
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
        if name not in self._capabilities:
            return False
        
        del self._capabilities[name]
        self._save()
        return True

    def clear(self) -> None:
        """Remove all capabilities from the registry."""
        self._capabilities.clear()
        self._save()

    def count(self) -> int:
        """Get the number of registered capabilities."""
        return len(self._capabilities)

    def __contains__(self, name: str) -> bool:
        """Check if a capability exists in the registry."""
        return name in self._capabilities

    def __len__(self) -> int:
        """Get the number of registered capabilities."""
        return len(self._capabilities)

    def __repr__(self) -> str:
        return f"CapabilityRegistry({len(self._capabilities)} capabilities)"