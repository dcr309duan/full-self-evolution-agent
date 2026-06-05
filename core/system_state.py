from typing import List, Dict, Any, Optional
from datetime import datetime
import json
import os

class SystemState:
    """
    Manages system state including fitness history, capability count history, and pruning history.
    Supports serialization/deserialization for persistence.
    """
    
    def __init__(self, state_file: Optional[str] = None):
        self.fitness_history: List[Dict[str, Any]] = []
        self.capability_count_history: List[Dict[str, Any]] = []
        self.pruning_history: List[Dict[str, Any]] = []
        self._state_file = state_file
        
        if state_file and os.path.exists(state_file):
            self.load(state_file)
    
    def add_fitness_entry(self, cycle: int, fitness_score: float) -> None:
        """Add a fitness history entry."""
        self.fitness_history.append({
            'cycle': cycle,
            'fitness_score': fitness_score,
            'timestamp': datetime.now().isoformat()
        })
    
    def add_capability_count_entry(self, cycle: int, count: int) -> None:
        """Add a capability count history entry."""
        self.capability_count_history.append({
            'cycle': cycle,
            'count': count,
            'timestamp': datetime.now().isoformat()
        })
    
    def add_pruning_entry(self, module_name: str, reason: str = "") -> None:
        """Add a pruning history entry."""
        self.pruning_history.append({
            'module': module_name,
            'timestamp': datetime.now().isoformat(),
            'reason': reason
        })
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize system state to dictionary."""
        return {
            'fitness_history': self.fitness_history,
            'capability_count_history': self.capability_count_history,
            'pruning_history': self.pruning_history
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SystemState':
        """Deserialize system state from dictionary."""
        state = cls()
        state.fitness_history = data.get('fitness_history', [])
        state.capability_count_history = data.get('capability_count_history', [])
        state.pruning_history = data.get('pruning_history', [])
        return state
    
    def save(self, filepath: str) -> None:
        """Save system state to a JSON file."""
        with open(filepath, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)
    
    def load(self, filepath: str) -> None:
        """Load system state from a JSON file."""
        with open(filepath, 'r') as f:
            data = json.load(f)
            self.fitness_history = data.get('fitness_history', [])
            self.capability_count_history = data.get('capability_count_history', [])
            self.pruning_history = data.get('pruning_history', [])
    
    def get_fitness_history(self) -> List[Dict[str, Any]]:
        """Return the fitness history list."""
        return self.fitness_history
    
    def get_capability_count_history(self) -> List[Dict[str, Any]]:
        """Return the capability count history list."""
        return self.capability_count_history
    
    def get_pruning_history(self) -> List[Dict[str, Any]]:
        """Return the pruning history list."""
        return self.pruning_history
    
    def clear(self) -> None:
        """Clear all history data."""
        self.fitness_history.clear()
        self.capability_count_history.clear()
        self.pruning_history.clear()
    
    def __repr__(self) -> str:
        return (f"SystemState(fitness_entries={len(self.fitness_history)}, "
                f"capability_entries={len(self.capability_count_history)}, "
                f"pruning_entries={len(self.pruning_history)})")