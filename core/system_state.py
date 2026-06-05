from typing import List, Dict, Any, Optional
from datetime import datetime
import json
import os

class SystemState:
    """
    Manages system state including fitness history, capability count history, pruning history,
    mutation rate, goal acceptance threshold, mutation outcomes, and meta parameter history.
    Supports serialization/deserialization for persistence.
    """
    
    def __init__(self, state_file: Optional[str] = None):
        self.fitness_history: List[Dict[str, Any]] = []
        self.capability_count_history: List[Dict[str, Any]] = []
        self.pruning_history: List[Dict[str, Any]] = []
        self.mutation_rate: float = 0.5
        self.goal_acceptance_threshold: float = 0.5
        self.mutation_outcomes: List[str] = []
        self.meta_parameter_history: List[Dict[str, Any]] = []
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
    
    def add_mutation_outcome(self, outcome: str) -> None:
        """Add a mutation outcome ('success' or 'failure'), keeping max 10 entries."""
        if outcome not in ('success', 'failure'):
            raise ValueError("Mutation outcome must be 'success' or 'failure'")
        self.mutation_outcomes.append(outcome)
        if len(self.mutation_outcomes) > 10:
            self.mutation_outcomes.pop(0)
    
    def add_meta_parameter_adjustment(self, parameter: str, old_value: Any, new_value: Any, reason: str = "") -> None:
        """Add a meta-parameter adjustment record."""
        self.meta_parameter_history.append({
            'parameter': parameter,
            'old_value': old_value,
            'new_value': new_value,
            'timestamp': datetime.now().isoformat(),
            'reason': reason
        })
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize system state to dictionary."""
        return {
            'fitness_history': self.fitness_history,
            'capability_count_history': self.capability_count_history,
            'pruning_history': self.pruning_history,
            'mutation_rate': self.mutation_rate,
            'goal_acceptance_threshold': self.goal_acceptance_threshold,
            'mutation_outcomes': self.mutation_outcomes,
            'meta_parameter_history': self.meta_parameter_history
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SystemState':
        """Deserialize system state from dictionary."""
        state = cls()
        state.fitness_history = data.get('fitness_history', [])
        state.capability_count_history = data.get('capability_count_history', [])
        state.pruning_history = data.get('pruning_history', [])
        state.mutation_rate = data.get('mutation_rate', 0.5)
        state.goal_acceptance_threshold = data.get('goal_acceptance_threshold', 0.5)
        state.mutation_outcomes = data.get('mutation_outcomes', [])
        state.meta_parameter_history = data.get('meta_parameter_history', [])
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
            self.mutation_rate = data.get('mutation_rate', 0.5)
            self.goal_acceptance_threshold = data.get('goal_acceptance_threshold', 0.5)
            self.mutation_outcomes = data.get('mutation_outcomes', [])
            self.meta_parameter_history = data.get('meta_parameter_history', [])
    
    def get_fitness_history(self) -> List[Dict[str, Any]]:
        """Return the fitness history list."""
        return self.fitness_history
    
    def get_capability_count_history(self) -> List[Dict[str, Any]]:
        """Return the capability count history list."""
        return self.capability_count_history
    
    def get_pruning_history(self) -> List[Dict[str, Any]]:
        """Return the pruning history list."""
        return self.pruning_history
    
    def get_mutation_rate(self) -> float:
        """Return the current mutation rate."""
        return self.mutation_rate
    
    def set_mutation_rate(self, rate: float) -> None:
        """Set the mutation rate and record the adjustment."""
        old_value = self.mutation_rate
        self.mutation_rate = rate
        self.add_meta_parameter_adjustment('mutation_rate', old_value, rate, 'Manual update')
    
    def get_goal_acceptance_threshold(self) -> float:
        """Return the current goal acceptance threshold."""
        return self.goal_acceptance_threshold
    
    def set_goal_acceptance_threshold(self, threshold: float) -> None:
        """Set the goal acceptance threshold and record the adjustment."""
        old_value = self.goal_acceptance_threshold
        self.goal_acceptance_threshold = threshold
        self.add_meta_parameter_adjustment('goal_acceptance_threshold', old_value, threshold, 'Manual update')
    
    def get_mutation_outcomes(self) -> List[str]:
        """Return the mutation outcomes list."""
        return self.mutation_outcomes
    
    def get_meta_parameter_history(self) -> List[Dict[str, Any]]:
        """Return the meta parameter history list."""
        return self.meta_parameter_history
    
    def clear(self) -> None:
        """Clear all history data and reset parameters to defaults."""
        self.fitness_history.clear()
        self.capability_count_history.clear()
        self.pruning_history.clear()
        self.mutation_rate = 0.5
        self.goal_acceptance_threshold = 0.5
        self.mutation_outcomes.clear()
        self.meta_parameter_history.clear()
    
    def __repr__(self) -> str:
        return (f"SystemState(fitness_entries={len(self.fitness_history)}, "
                f"capability_entries={len(self.capability_count_history)}, "
                f"pruning_entries={len(self.pruning_history)}, "
                f"mutation_rate={self.mutation_rate}, "
                f"goal_acceptance_threshold={self.goal_acceptance_threshold}, "
                f"mutation_outcomes={len(self.mutation_outcomes)}, "
                f"meta_parameter_history={len(self.meta_parameter_history)})")