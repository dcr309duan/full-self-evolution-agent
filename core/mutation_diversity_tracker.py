from collections import deque
import random
import time
from typing import List, Optional, Tuple

class MutationRecord:
    """Stores a single mutation attempt with its feature vector, timestamp, and outcome."""
    
    def __init__(self, feature_vector: List[float], goal_type: str, outcome: Optional[str] = None):
        """
        Initialize a mutation record.
        
        Args:
            feature_vector: List of [complexity, import_count, file_count, goal_type_encoded]
            goal_type: String identifier for the goal type
            outcome: Optional outcome string (e.g., 'success', 'failure', 'pending')
        """
        self.feature_vector = feature_vector
        self.goal_type = goal_type
        self.timestamp = time.time()
        self.outcome = outcome
    
    def to_dict(self) -> dict:
        """Convert record to dictionary for serialization."""
        return {
            'feature_vector': self.feature_vector,
            'goal_type': self.goal_type,
            'timestamp': self.timestamp,
            'outcome': self.outcome
        }


class DiversityTracker:
    """Tracks mutation diversity using a circular buffer of recent mutation records."""
    
    def __init__(self, buffer_size: int = 20):
        """
        Initialize the diversity tracker.
        
        Args:
            buffer_size: Maximum number of recent mutation records to maintain
        """
        self.buffer_size = buffer_size
        self.records = deque(maxlen=buffer_size)
        self.available_goal_types = ['feature_addition', 'bug_fix', 'refactoring', 
                                     'optimization', 'documentation', 'test_addition']
    
    def add_record(self, feature_vector: List[float], goal_type: str, 
                   outcome: Optional[str] = None) -> None:
        """
        Add a new mutation record to the circular buffer.
        
        Args:
            feature_vector: Feature vector for the mutation
            goal_type: Goal type string
            outcome: Optional outcome string
        """
        record = MutationRecord(feature_vector, goal_type, outcome)
        self.records.append(record)
    
    def compute_cosine_similarity(self, feature_vector: List[float]) -> List[float]:
        """
        Compute cosine similarity between current feature vector and each stored record.
        
        Args:
            feature_vector: Current feature vector to compare against stored records
            
        Returns:
            List of cosine similarity values (one per stored record)
        """
        similarities = []
        current_norm = self._compute_norm(feature_vector)
        
        for record in self.records:
            stored_norm = self._compute_norm(record.feature_vector)
            
            # Handle zero vectors
            if current_norm == 0 or stored_norm == 0:
                similarities.append(0.0)
                continue
            
            # Compute dot product
            dot_product = sum(a * b for a, b in zip(feature_vector, record.feature_vector))
            similarity = dot_product / (current_norm * stored_norm)
            similarities.append(similarity)
        
        return similarities
    
    def should_force_diversity(self, feature_vector: List[float]) -> bool:
        """
        Check if forced diversity is needed based on similarity threshold.
        
        Args:
            feature_vector: Current feature vector to check
            
        Returns:
            True if any similarity exceeds 0.8 threshold
        """
        if len(self.records) < 2:  # Need at least 2 records for meaningful comparison
            return False
        
        similarities = self.compute_cosine_similarity(feature_vector)
        return any(sim > 0.8 for sim in similarities)
    
    def inject_noise(self, feature_vector: List[float]) -> List[float]:
        """
        Randomly perturb the feature vector by ±10% when forced diversity is triggered.
        
        Args:
            feature_vector: Original feature vector to perturb
            
        Returns:
            Noisy feature vector with each component perturbed by ±10%
        """
        noisy_vector = []
        for value in feature_vector:
            # Apply ±10% random perturbation
            noise_factor = 1.0 + random.uniform(-0.1, 0.1)
            noisy_value = value * noise_factor
            noisy_vector.append(noisy_value)
        
        return noisy_vector
    
    def force_goal_type_change(self, current_goal_type: str) -> str:
        """
        Select a different goal type from the available pool.
        
        Args:
            current_goal_type: Current goal type to avoid
            
        Returns:
            A different goal type from available pool
        """
        available_types = [gt for gt in self.available_goal_types if gt != current_goal_type]
        
        if not available_types:
            # Fallback if no other types available
            return current_goal_type
        
        return random.choice(available_types)
    
    def get_diversity_stats(self) -> dict:
        """
        Get statistics about current diversity state.
        
        Returns:
            Dictionary with diversity statistics
        """
        if not self.records:
            return {
                'total_records': 0,
                'unique_goal_types': 0,
                'avg_similarity': 0.0,
                'max_similarity': 0.0
            }
        
        goal_types = set(record.goal_type for record in self.records)
        
        # Compute average similarity between consecutive records
        similarities = []
        for i in range(1, len(self.records)):
            sim = self._compute_pairwise_similarity(
                self.records[i-1].feature_vector, 
                self.records[i].feature_vector
            )
            similarities.append(sim)
        
        avg_similarity = sum(similarities) / len(similarities) if similarities else 0.0
        max_similarity = max(similarities) if similarities else 0.0
        
        return {
            'total_records': len(self.records),
            'unique_goal_types': len(goal_types),
            'avg_similarity': avg_similarity,
            'max_similarity': max_similarity
        }
    
    def clear_records(self) -> None:
        """Clear all stored records."""
        self.records.clear()
    
    def _compute_norm(self, vector: List[float]) -> float:
        """Compute Euclidean norm of a vector."""
        return sum(v ** 2 for v in vector) ** 0.5
    
    def _compute_pairwise_similarity(self, vector1: List[float], vector2: List[float]) -> float:
        """Compute cosine similarity between two vectors."""
        norm1 = self._compute_norm(vector1)
        norm2 = self._compute_norm(vector2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        dot_product = sum(a * b for a, b in zip(vector1, vector2))
        return dot_product / (norm1 * norm2)