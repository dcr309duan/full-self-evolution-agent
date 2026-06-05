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
        self.rollback_counter: int = 0  # Tracks consecutive rollbacks

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
            "rollback_counter": self.rollback_counter,
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
        
        # Restore rollback counter
        instance.rollback_counter = state.get("rollback_counter", 0)
        
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

    def generate_ecology_goal(self, test_description: str) -> Goal:
        """
        Generates a new ECOLOGY goal when the Ecology Engine creates a new benchmark or stress test.
        
        Args:
            test_description: Description of the new environmental pressure/test
            
        Returns:
            A new Goal object with ECOLOGY type
        """
        import uuid
        goal = Goal(
            id=str(uuid.uuid4()),
            description=f"Adapt to new environmental pressure: {test_description}",
            template="ECOLOGY",
            created_at=datetime.now().isoformat(),
            parameters={"test_description": test_description, "goal_type": "ECOLOGY"}
        )
        self.pending_goals.append(goal)
        return goal

    def generate_infrastructure_goal(self, rollback_count: int) -> Goal:
        """
        Generates a new INFRASTRUCTURE goal when repeated rollbacks are detected.
        
        Args:
            rollback_count: Number of consecutive rollbacks detected
            
        Returns:
            A new Goal object with INFRASTRUCTURE type and HIGH priority
        """
        import uuid
        goal = Goal(
            id=str(uuid.uuid4()),
            description=f"Improve mutation stability: analyze last {rollback_count} rollbacks and identify common failure patterns",
            template="INFRASTRUCTURE",
            created_at=datetime.now().isoformat(),
            parameters={
                "rollback_count": rollback_count,
                "goal_type": "INFRASTRUCTURE",
                "priority": "HIGH"
            }
        )
        self.pending_goals.append(goal)
        return goal

    def process_rollback(self, is_rollback: bool) -> Optional[Goal]:
        """
        Processes a rollback event and generates an INFRASTRUCTURE goal if needed.
        
        Args:
            is_rollback: Whether the current event is a rollback
            
        Returns:
            A Goal object if a new INFRASTRUCTURE goal was generated, None otherwise
        """
        if is_rollback:
            self.rollback_counter += 1
            if self.rollback_counter > 3:
                # Generate INFRASTRUCTURE goal for repeated rollbacks
                return self.generate_infrastructure_goal(self.rollback_counter)
        else:
            # Reset counter on successful operation
            self.rollback_counter = 0
        
        return None