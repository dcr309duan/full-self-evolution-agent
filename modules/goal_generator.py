from typing import Dict, Any, Optional, List
import json
from dataclasses import dataclass, field, asdict
from datetime import datetime


@dataclass
class Goal:
    """Represents a single goal with its metadata."""
    id: str
    description: str
    template: str
    created_at: str
    completed_at: Optional[str] = None
    parameters: Dict[str, Any] = field(default_factory=dict)


class GoalGenerator:
    """Generates and manages goals based on templates and parameters."""

    def __init__(self, templates: Optional[Dict[str, Any]] = None):
        self.pending_goals: List[Goal] = []
        self.completed_goals: List[Goal] = []
        self.goal_templates: Dict[str, Any] = templates or {}
        self.generation_parameters: Dict[str, Any] = {
            "max_pending": 10,
            "auto_generate": True,
            "priority_mode": "balanced"
        }

    def get_serialized_state(self) -> Dict[str, Any]:
        """
        Returns a JSON-serializable dictionary of the current state.
        
        Returns:
            Dict containing all state information for serialization
        """
        return {
            "pending_goals": [asdict(goal) for goal in self.pending_goals],
            "completed_goals": [asdict(goal) for goal in self.completed_goals],
            "goal_templates": self.goal_templates,
            "generation_parameters": self.generation_parameters.copy(),
            "version": 1  # For future compatibility
        }

    @classmethod
    def from_serialized_state(cls, state: Dict[str, Any]) -> 'GoalGenerator':
        """
        Reconstructs a GoalGenerator instance from a serialized state.
        
        Args:
            state: Dictionary containing the serialized state
            
        Returns:
            A new GoalGenerator instance with the restored state
            
        Raises:
            ValueError: If the state dictionary is invalid or missing required keys
        """
        required_keys = ["pending_goals", "completed_goals", "goal_templates", "generation_parameters"]
        
        # Validate required keys exist
        for key in required_keys:
            if key not in state:
                raise ValueError(f"Missing required key '{key}' in serialized state")
        
        # Create new instance
        instance = cls(templates=state.get("goal_templates", {}))
        
        # Restore generation parameters
        instance.generation_parameters = state.get("generation_parameters", {}).copy()
        
        # Restore pending goals
        instance.pending_goals = []
        for goal_dict in state.get("pending_goals", []):
            instance.pending_goals.append(Goal(
                id=goal_dict["id"],
                description=goal_dict["description"],
                template=goal_dict["template"],
                created_at=goal_dict["created_at"],
                completed_at=goal_dict.get("completed_at"),
                parameters=goal_dict.get("parameters", {})
            ))
        
        # Restore completed goals
        instance.completed_goals = []
        for goal_dict in state.get("completed_goals", []):
            instance.completed_goals.append(Goal(
                id=goal_dict["id"],
                description=goal_dict["description"],
                template=goal_dict["template"],
                created_at=goal_dict["created_at"],
                completed_at=goal_dict.get("completed_at"),
                parameters=goal_dict.get("parameters", {})
            ))
        
        return instance

    def to_json(self) -> str:
        """Converts the current state to a JSON string."""
        return json.dumps(self.get_serialized_state(), indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> 'GoalGenerator':
        """Creates a GoalGenerator instance from a JSON string."""
        state = json.loads(json_str)
        return cls.from_serialized_state(state)