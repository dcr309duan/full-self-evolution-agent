from typing import Dict, List, Optional, Tuple
from collections import defaultdict
import math

class AccumulatedKnowledge:
    """
    Manages capability tracking with usage statistics and lifecycle management.
    
    Each capability entry tracks:
    - times_called: Counter for how many times the capability has been invoked
    - last_active_cycle: The cycle number when the capability was last used
    - dependency_count: Number of other capabilities that depend on this one
    """
    
    def __init__(self):
        self._capabilities: Dict[str, Dict] = {}
        self._current_cycle: int = 0
        
    def add_capability(self, name: str, initial_dependencies: int = 0) -> None:
        """
        Add a new capability entry with default tracking fields.
        
        Args:
            name: Unique identifier for the capability
            initial_dependencies: Starting dependency count (default 0)
        """
        if name in self._capabilities:
            raise ValueError(f"Capability '{name}' already exists")
        
        self._capabilities[name] = {
            'times_called': 0,
            'last_active_cycle': 0,
            'dependency_count': initial_dependencies,
            'created_cycle': self._current_cycle
        }
    
    def record_call(self, name: str, cycle: Optional[int] = None) -> None:
        """
        Record that a capability was called, updating its tracking fields.
        
        Args:
            name: Capability to record call for
            cycle: Current cycle number (uses internal counter if None)
        """
        if name not in self._capabilities:
            raise KeyError(f"Capability '{name}' not found")
        
        if cycle is not None:
            self._current_cycle = max(self._current_cycle, cycle)
        else:
            cycle = self._current_cycle
        
        self._capabilities[name]['times_called'] += 1
        self._capabilities[name]['last_active_cycle'] = cycle
    
    def update_dependency_count(self, name: str, delta: int = 1) -> None:
        """
        Increment or decrement the dependency count for a capability.
        
        Args:
            name: Capability to update
            delta: Amount to change dependency count (positive or negative)
        """
        if name not in self._capabilities:
            raise KeyError(f"Capability '{name}' not found")
        
        new_count = self._capabilities[name]['dependency_count'] + delta
        if new_count < 0:
            raise ValueError(f"Dependency count for '{name}' would become negative")
        
        self._capabilities[name]['dependency_count'] = new_count
    
    def get_usage_stats(self, cycle: int, window: int = 20) -> Dict[str, float]:
        """
        Calculate and return usage scores for all capabilities.
        
        The score is based on:
        - Recency: How recently the capability was used (within the window)
        - Frequency: How many times it was called (within the window)
        - Dependency importance: How many other capabilities depend on it
        
        Args:
            cycle: Current cycle number for recency calculation
            window: Number of cycles to consider for the usage window (default 20)
            
        Returns:
            Dictionary mapping capability names to their usage scores (0.0 to 1.0)
        """
        if window <= 0:
            raise ValueError("Window must be positive")
        
        scores = {}
        
        for name, data in self._capabilities.items():
            # Calculate recency factor (1.0 if used in current cycle, decreasing to 0.0 outside window)
            cycles_since_active = cycle - data['last_active_cycle']
            if cycles_since_active < 0:
                recency_factor = 0.0  # Future cycle? Treat as not used
            elif cycles_since_active <= window:
                recency_factor = 1.0 - (cycles_since_active / window)
            else:
                recency_factor = 0.0
            
            # Calculate frequency factor (normalized by window size)
            # Assuming max reasonable calls per cycle is 1 for normalization
            max_possible_calls = window
            frequency_factor = min(data['times_called'] / max_possible_calls, 1.0)
            
            # Calculate dependency factor (normalized, assuming max dependencies is arbitrary)
            # Using a logarithmic scale to prevent domination by high dependency counts
            dependency_factor = 0.0
            if data['dependency_count'] > 0:
                dependency_factor = math.log2(data['dependency_count'] + 1) / 10.0
                dependency_factor = min(dependency_factor, 1.0)
            
            # Combine factors with weights
            # Recency: 40%, Frequency: 30%, Dependency: 30%
            score = (recency_factor * 0.4 + 
                    frequency_factor * 0.3 + 
                    dependency_factor * 0.3)
            
            scores[name] = round(score, 4)
        
        return scores
    
    def remove_capability(self, name: str) -> None:
        """
        Safely delete a capability entry.
        
        Checks for:
        - Existence of the capability
        - No other capabilities depend on it (dependency_count == 0)
        
        Args:
            name: Capability to remove
            
        Raises:
            KeyError: If capability doesn't exist
            ValueError: If other capabilities depend on this one
        """
        if name not in self._capabilities:
            raise KeyError(f"Capability '{name}' not found")
        
        if self._capabilities[name]['dependency_count'] > 0:
            raise ValueError(
                f"Cannot remove capability '{name}': {self._capabilities[name]['dependency_count']} "
                f"other capabilities depend on it"
            )
        
        del self._capabilities[name]
    
    def get_capability(self, name: str) -> Optional[Dict]:
        """
        Get the tracking data for a specific capability.
        
        Args:
            name: Capability to retrieve
            
        Returns:
            Dictionary with tracking fields, or None if not found
        """
        return self._capabilities.get(name)
    
    def list_capabilities(self) -> List[str]:
        """Return sorted list of all capability names."""
        return sorted(self._capabilities.keys())
    
    def advance_cycle(self) -> int:
        """Advance the internal cycle counter and return the new cycle number."""
        self._current_cycle += 1
        return self._current_cycle
    
    @property
    def current_cycle(self) -> int:
        """Get the current cycle number."""
        return self._current_cycle
    
    def __len__(self) -> int:
        """Return the number of tracked capabilities."""
        return len(self._capabilities)
    
    def __contains__(self, name: str) -> bool:
        """Check if a capability is being tracked."""
        return name in self._capabilities