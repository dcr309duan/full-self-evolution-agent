from datetime import datetime
from typing import Dict, List, Tuple, Optional
import json
import os

class KnowledgeBase:
    """
    A knowledge base that tracks blocking dependencies between goals and their prerequisites.
    Enables identification of recurring blockers for prioritization.
    """
    
    def __init__(self, storage_path: str = "knowledge_base.json"):
        """
        Initialize the knowledge base.
        
        Args:
            storage_path: Path to the JSON file for persistent storage
        """
        self.storage_path = storage_path
        self.blocking_dependencies: Dict[str, Dict] = {}  # key: "goal_id:prerequisite"
        self._load()
    
    def _load(self) -> None:
        """Load existing data from storage file."""
        if os.path.exists(self.storage_path):
            try:
                with open(self.storage_path, 'r') as f:
                    data = json.load(f)
                    self.blocking_dependencies = data.get('blocking_dependencies', {})
            except (json.JSONDecodeError, IOError):
                self.blocking_dependencies = {}
    
    def _save(self) -> None:
        """Save current state to storage file."""
        data = {
            'blocking_dependencies': self.blocking_dependencies
        }
        try:
            with open(self.storage_path, 'w') as f:
                json.dump(data, f, indent=2)
        except IOError:
            pass  # Silently fail if unable to write
    
    def log_blocking_dependency(self, goal_id: str, prerequisite: str, timestamp: Optional[str] = None) -> Dict:
        """
        Record a blocking dependency in the knowledge base.
        
        Args:
            goal_id: Identifier of the goal that is blocked
            prerequisite: The unmet prerequisite causing the block
            timestamp: Optional timestamp string; defaults to current UTC time
            
        Returns:
            Dict containing the updated dependency record with:
                - goal_id: The blocked goal
                - prerequisite: The unmet prerequisite
                - timestamp: When the block was recorded
                - block_count: How many times this specific dependency has blocked goals
                - first_seen: When this dependency was first recorded
        """
        if timestamp is None:
            timestamp = datetime.utcnow().isoformat()
        
        # Create a unique key for this dependency pair
        dependency_key = f"{goal_id}:{prerequisite}"
        
        if dependency_key in self.blocking_dependencies:
            # Update existing record
            record = self.blocking_dependencies[dependency_key]
            record['block_count'] += 1
            record['last_seen'] = timestamp
            record['timestamps'].append(timestamp)
        else:
            # Create new record
            record = {
                'goal_id': goal_id,
                'prerequisite': prerequisite,
                'block_count': 1,
                'first_seen': timestamp,
                'last_seen': timestamp,
                'timestamps': [timestamp]
            }
            self.blocking_dependencies[dependency_key] = record
        
        self._save()
        return record
    
    def get_blocking_dependencies(self, 
                                   goal_id: Optional[str] = None,
                                   prerequisite: Optional[str] = None,
                                   min_block_count: int = 1) -> List[Dict]:
        """
        Retrieve blocking dependencies with optional filtering.
        
        Args:
            goal_id: Filter by specific goal ID
            prerequisite: Filter by specific prerequisite
            min_block_count: Minimum number of times a dependency has blocked goals
            
        Returns:
            List of dependency records matching the filters
        """
        results = []
        for key, record in self.blocking_dependencies.items():
            if goal_id and record['goal_id'] != goal_id:
                continue
            if prerequisite and record['prerequisite'] != prerequisite:
                continue
            if record['block_count'] < min_block_count:
                continue
            results.append(record)
        
        return results
    
    def get_recurring_blockers(self, min_block_count: int = 2) -> List[Dict]:
        """
        Identify recurring blockers that have blocked goals multiple times.
        
        Args:
            min_block_count: Minimum number of blocks to consider recurring (default: 2)
            
        Returns:
            List of dependency records sorted by block_count (highest first)
        """
        recurring = [
            record for record in self.blocking_dependencies.values()
            if record['block_count'] >= min_block_count
        ]
        return sorted(recurring, key=lambda x: x['block_count'], reverse=True)
    
    def get_most_blocked_prerequisites(self, top_n: int = 10) -> List[Tuple[str, int]]:
        """
        Get the most frequently blocking prerequisites across all goals.
        
        Args:
            top_n: Number of top blockers to return
            
        Returns:
            List of (prerequisite, total_block_count) tuples sorted by block count
        """
        prerequisite_counts: Dict[str, int] = {}
        for record in self.blocking_dependencies.values():
            prereq = record['prerequisite']
            prerequisite_counts[prereq] = prerequisite_counts.get(prereq, 0) + record['block_count']
        
        sorted_prereqs = sorted(prerequisite_counts.items(), key=lambda x: x[1], reverse=True)
        return sorted_prereqs[:top_n]
    
    def clear(self) -> None:
        """Clear all recorded blocking dependencies."""
        self.blocking_dependencies = {}
        self._save()
    
    def get_statistics(self) -> Dict:
        """
        Get summary statistics about the knowledge base.
        
        Returns:
            Dict with statistics about recorded dependencies
        """
        if not self.blocking_dependencies:
            return {
                'total_dependencies': 0,
                'total_blocks': 0,
                'unique_goals': 0,
                'unique_prerequisites': 0,
                'recurring_blockers': 0
            }
        
        unique_goals = set(record['goal_id'] for record in self.blocking_dependencies.values())
        unique_prerequisites = set(record['prerequisite'] for record in self.blocking_dependencies.values())
        total_blocks = sum(record['block_count'] for record in self.blocking_dependencies.values())
        recurring_count = sum(1 for record in self.blocking_dependencies.values() if record['block_count'] >= 2)
        
        return {
            'total_dependencies': len(self.blocking_dependencies),
            'total_blocks': total_blocks,
            'unique_goals': len(unique_goals),
            'unique_prerequisites': len(unique_prerequisites),
            'recurring_blockers': recurring_count
        }