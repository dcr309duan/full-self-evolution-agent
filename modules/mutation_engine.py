from typing import Dict, Any, List, Optional
import json
from dataclasses import dataclass, field, asdict
from datetime import datetime

@dataclass
class MutationRecord:
    """Represents a single mutation event in the history."""
    timestamp: str
    mutation_type: str
    target: str
    details: Dict[str, Any] = field(default_factory=dict)

class MutationEngine:
    """
    Mutation engine that manages mutation operations with configurable parameters
    and full state serialization support for sandboxing.
    """
    
    def __init__(self, 
                 mutation_rate: float = 0.1,
                 allowed_mutation_types: Optional[List[str]] = None,
                 max_history_size: int = 100):
        """
        Initialize the mutation engine.
        
        Args:
            mutation_rate: Probability of mutation per operation (0.0 to 1.0)
            allowed_mutation_types: List of allowed mutation type strings
            max_history_size: Maximum number of recent mutation records to keep
        """
        self.mutation_rate = mutation_rate
        self.allowed_mutation_types = allowed_mutation_types or [
            'point', 'insertion', 'deletion', 'substitution', 'inversion'
        ]
        self.max_history_size = max_history_size
        self.mutation_history: List[MutationRecord] = []
        
    def record_mutation(self, mutation_type: str, target: str, details: Optional[Dict[str, Any]] = None) -> None:
        """
        Record a mutation event in the history.
        
        Args:
            mutation_type: Type of mutation performed
            target: The target that was mutated
            details: Optional additional details about the mutation
        """
        record = MutationRecord(
            timestamp=datetime.utcnow().isoformat(),
            mutation_type=mutation_type,
            target=target,
            details=details or {}
        )
        
        self.mutation_history.append(record)
        
        # Trim history if it exceeds max size
        if len(self.mutation_history) > self.max_history_size:
            self.mutation_history = self.mutation_history[-self.max_history_size:]
    
    def get_serialized_state(self) -> Dict[str, Any]:
        """
        Returns a JSON-serializable dict of the mutation engine's current configuration.
        
        Returns:
            Dict containing mutation rate, allowed mutation types, and recent mutation history
        """
        return {
            'mutation_rate': self.mutation_rate,
            'allowed_mutation_types': self.allowed_mutation_types.copy(),
            'max_history_size': self.max_history_size,
            'mutation_history': [
                asdict(record) for record in self.mutation_history
            ]
        }
    
    @classmethod
    def from_serialized_state(cls, state: Dict[str, Any]) -> 'MutationEngine':
        """
        Reconstruct a MutationEngine instance from a saved state dict.
        
        Args:
            state: Dict containing the serialized engine state (as returned by get_serialized_state())
            
        Returns:
            A new MutationEngine instance with the restored configuration and history
            
        Raises:
            ValueError: If the state dict is missing required keys or contains invalid data
        """
        required_keys = ['mutation_rate', 'allowed_mutation_types', 'max_history_size', 'mutation_history']
        
        # Validate required keys
        missing_keys = [key for key in required_keys if key not in state]
        if missing_keys:
            raise ValueError(f"Missing required state keys: {missing_keys}")
        
        # Validate mutation_rate
        mutation_rate = state['mutation_rate']
        if not isinstance(mutation_rate, (int, float)) or not (0.0 <= mutation_rate <= 1.0):
            raise ValueError(f"Invalid mutation_rate: {mutation_rate}. Must be between 0.0 and 1.0.")
        
        # Validate allowed_mutation_types
        allowed_types = state['allowed_mutation_types']
        if not isinstance(allowed_types, list) or not all(isinstance(t, str) for t in allowed_types):
            raise ValueError("allowed_mutation_types must be a list of strings")
        
        # Validate max_history_size
        max_history_size = state['max_history_size']
        if not isinstance(max_history_size, int) or max_history_size < 1:
            raise ValueError(f"Invalid max_history_size: {max_history_size}. Must be a positive integer.")
        
        # Create engine instance
        engine = cls(
            mutation_rate=mutation_rate,
            allowed_mutation_types=allowed_types,
            max_history_size=max_history_size
        )
        
        # Restore mutation history
        history_data = state['mutation_history']
        if not isinstance(history_data, list):
            raise ValueError("mutation_history must be a list")
        
        for record_data in history_data:
            if not isinstance(record_data, dict):
                raise ValueError("Each mutation history entry must be a dict")
            
            # Validate required fields in each record
            required_record_keys = ['timestamp', 'mutation_type', 'target', 'details']
            missing_record_keys = [key for key in required_record_keys if key not in record_data]
            if missing_record_keys:
                raise ValueError(f"Mutation history entry missing keys: {missing_record_keys}")
            
            record = MutationRecord(
                timestamp=record_data['timestamp'],
                mutation_type=record_data['mutation_type'],
                target=record_data['target'],
                details=record_data.get('details', {})
            )
            engine.mutation_history.append(record)
        
        # Trim history if it exceeds max size (safety check)
        if len(engine.mutation_history) > engine.max_history_size:
            engine.mutation_history = engine.mutation_history[-engine.max_history_size:]
        
        return engine
    
    def to_json(self) -> str:
        """Serialize the engine state to a JSON string."""
        return json.dumps(self.get_serialized_state(), indent=2)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'MutationEngine':
        """
        Reconstruct a MutationEngine from a JSON string.
        
        Args:
            json_str: JSON string containing the serialized engine state
            
        Returns:
            A new MutationEngine instance
        """
        state = json.loads(json_str)
        return cls.from_serialized_state(state)