from typing import Dict, Any, List, Optional
import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
import os
import tempfile
import logging

logger = logging.getLogger(__name__)

def atomic_write(filepath: str, content: str) -> None:
    """
    Atomically write content to a file using a temporary file and os.rename().
    
    Args:
        filepath: Path to the target file
        content: Content to write to the file
    """
    # Log git status before write
    logger.info(f"Git status before atomic write to {filepath}")
    os.system("git status")
    
    # Get directory of target file
    directory = os.path.dirname(filepath) or "."
    
    # Create temporary file in the same directory
    with tempfile.NamedTemporaryFile(
        mode='w',
        dir=directory,
        delete=False,
        suffix='.tmp'
    ) as tmp_file:
        tmp_path = tmp_file.name
        tmp_file.write(content)
    
    # Atomic rename
    os.replace(tmp_path, filepath)
    
    # Log git status after write
    logger.info(f"Git status after atomic write to {filepath}")
    os.system("git status")

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
            'point', 'insertion', 'deletion', 'substitution', 'inversion', 'trivial_mutation'
        ]
        self.max_history_size = max_history_size
        self.mutation_history: List[MutationRecord] = []
        self._operator_weights: Dict[str, float] = {
            mutation_type: 1.0 / len(self.allowed_mutation_types)
            for mutation_type in self.allowed_mutation_types
        }
        self._failure_records: List[Dict[str, Any]] = []
        
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
    
    def register_failure(self, mutation_type: str, error_type: str, details: Optional[Dict[str, Any]] = None) -> None:
        """
        Register a failure with error type classification from the failure pattern learner.
        
        Args:
            mutation_type: The type of mutation that caused the failure
            error_type: The classified error type (e.g., 'syntax_error', 'runtime_error', 'logic_error')
            details: Optional additional details about the failure
        """
        failure_record = {
            'timestamp': datetime.utcnow().isoformat(),
            'mutation_type': mutation_type,
            'error_type': error_type,
            'details': details or {}
        }
        self._failure_records.append(failure_record)
    
    @property
    def operator_weights(self) -> Dict[str, float]:
        """
        Get the current operator weights as a mutable dict.
        
        Returns:
            Dict mapping mutation types to their current weights
        """
        return self._operator_weights
    
    @operator_weights.setter
    def operator_weights(self, weights: Dict[str, float]) -> None:
        """
        Set the operator weights directly.
        
        Args:
            weights: Dict mapping mutation types to their weights
        """
        self._operator_weights = weights
    
    def get_adjusted_operator_weights(self) -> Dict[str, float]:
        """
        Returns current operator probabilities after failure-based adjustments.
        
        Returns:
            Dict mapping mutation types to their adjusted probabilities (normalized to sum to 1.0)
        """
        if not self._operator_weights:
            return {}
        
        total_weight = sum(self._operator_weights.values())
        if total_weight == 0:
            return {key: 0.0 for key in self._operator_weights}
        
        return {key: value / total_weight for key, value in self._operator_weights.items()}
    
    def set_operator_weights(self, weights_dict: Dict[str, float]) -> None:
        """
        Allows the failure pattern learner to update operator probabilities.
        
        Args:
            weights_dict: Dict mapping mutation types to their new weights
        """
        self._operator_weights = weights_dict
    
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
            ],
            'operator_weights': self._operator_weights.copy(),
            'failure_records': self._failure_records.copy()
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
        
        # Restore operator weights if present
        if 'operator_weights' in state:
            engine._operator_weights = state['operator_weights']
        
        # Restore failure records if present
        if 'failure_records' in state:
            engine._failure_records = state['failure_records']
        
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
    
    def trivial_mutation(self, filepath: str) -> None:
        """
        Perform a trivial mutation that only adds a comment to a file.
        This provides a minimal mutation that should never fail.
        Implemented with simple file read/write (no atomic operations initially to isolate issues).
        
        Args:
            filepath: Path to the file to mutate
        """
        try:
            # Read the file content
            with open(filepath, 'r') as f:
                content = f.read()
            
            # Add a trivial comment at the end of the file
            comment = "\n# Trivial mutation comment added at " + datetime.utcnow().isoformat() + "\n"
            content += comment
            
            # Write the modified content back to the file (simple write, no atomic operations)
            with open(filepath, 'w') as f:
                f.write(content)
            
            # Record the mutation
            self.record_mutation(
                mutation_type='trivial_mutation',
                target=filepath,
                details={'comment_added': comment.strip()}
            )
        except FileNotFoundError:
            logger.error(f"File not found: {filepath}")
            raise
        except PermissionError:
            logger.error(f"Permission denied when accessing file: {filepath}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error during trivial mutation: {e}")
            raise

    def quality_gate(self, filepath: str) -> Dict[str, Any]:
        """
        Perform a quality gate check on the mutated file.
        This is a placeholder that should be replaced with actual quality checks.
        
        Args:
            filepath: Path to the file to check
            
        Returns:
            Dict with keys 'passed' (bool) and 'errors' (list of error dicts)
        """
        # Placeholder: always pass for now
        # In a real implementation, this would check syntax, style, etc.
        return {'passed': True, 'errors': []}

    def apply_mutation(self, filepath: str, mutation_type: str, mutation_params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Main mutation application method. Applies a mutation, runs quality gate,
        and handles retries on failure.
        
        Args:
            filepath: Path to the file to mutate
            mutation_type: Type of mutation to apply
            mutation_params: Optional parameters for the mutation
            
        Returns:
            Dict with keys:
                - 'success': bool
                - 'error_details': list of error dicts (if failed)
                - 'retry_count': int (number of retries attempted)
                - 'discarded': bool (True if mutation was discarded after max retries)
        """
        max_retries = 3
        retry_count = 0
        error_details = []
        
        while retry_count < max_retries:
            try:
                # Apply the mutation based on type
                if mutation_type == 'trivial_mutation':
                    self.trivial_mutation(filepath)
                else:
                    # For other mutation types, we would implement specific logic
                    # For now, just record the mutation attempt
                    self.record_mutation(
                        mutation_type=mutation_type,
                        target=filepath,
                        details=mutation_params or {}
                    )
                
                # Run quality gate
                gate_result = self.quality_gate(filepath)
                
                if gate_result['passed']:
                    # Save the mutation (atomic write is handled by mutation methods)
                    return {
                        'success': True,
                        'error_details': [],
                        'retry_count': retry_count,
                        'discarded': False
                    }
                else:
                    # Gate failed
                    error_details = gate_result.get('errors', [{'message': 'Quality gate failed'}])
                    logger.error(f"Quality gate failed for {mutation_type} on {filepath}: {error_details}")
                    
                    # Register failure
                    self.register_failure(
                        mutation_type=mutation_type,
                        error_type='quality_gate_failure',
                        details={'errors': error_details, 'retry_count': retry_count}
                    )
                    
                    retry_count += 1
                    
                    if retry_count >= max_retries:
                        # Discard mutation entirely
                        logger.error(f"Mutation {mutation_type} on {filepath} discarded after {max_retries} failures")
                        return {
                            'success': False,
                            'error_details': error_details,
                            'retry_count': retry_count,
                            'discarded': True
                        }
                    
                    # Return structured failure response for LLM to fix
                    return {
                        'success': False,
                        'error_details': error_details,
                        'retry_count': retry_count,
                        'discarded': False
                    }
                    
            except Exception as e:
                error_msg = str(e)
                logger.error(f"Error during mutation {mutation_type} on {filepath}: {error_msg}")
                
                error_details = [{'message': error_msg, 'exception': type(e).__name__}]
                
                # Register failure
                self.register_failure(
                    mutation_type=mutation_type,
                    error_type='mutation_error',
                    details={'error': error_msg, 'retry_count': retry_count}
                )
                
                retry_count += 1
                
                if retry_count >= max_retries:
                    logger.error(f"Mutation {mutation_type} on {filepath} discarded after {max_retries} failures")
                    return {
                        'success': False,
                        'error_details': error_details,
                        'retry_count': retry_count,
                        'discarded': True
                    }
                
                return {
                    'success': False,
                    'error_details': error_details,
                    'retry_count': retry_count,
                    'discarded': False
                }
        
        # Should not reach here, but just in case
        return {
            'success': False,
            'error_details': error_details,
            'retry_count': retry_count,
            'discarded': True
        }