from typing import Any, Dict, List, Optional
from datetime import datetime
import json

from agent_core.schema_alignment import SchemaAlignment, GoalSchema
from agent_core.reflection_engine import ReflectionOutput
from agent_core.system_model import SystemModelState


class GoalGenerator:
    """
    Generates, validates, and normalizes goals for the agent system.
    Ensures all goals conform to the canonical schema before storage or execution.
    """

    def __init__(self, schema_alignment: SchemaAlignment, system_model: SystemModelState):
        self.schema_alignment = schema_alignment
        self.system_model = system_model
        self.goal_history: List[Dict[str, Any]] = []

    def generate_goal(self, reflection_output: ReflectionOutput) -> Optional[Dict[str, Any]]:
        """
        Generate a goal from reflection output, normalizing and validating it.
        Returns the validated goal dict or None if validation fails.
        """
        raw_goal = self._extract_goal_from_reflection(reflection_output)
        if not raw_goal:
            return None

        normalized_goal = self._normalize_goal(raw_goal)
        if not normalized_goal:
            return None

        validated_goal = self._validate_goal(normalized_goal)
        if not validated_goal:
            return None

        self.goal_history.append(validated_goal)
        return validated_goal

    def _extract_goal_from_reflection(self, reflection_output: ReflectionOutput) -> Optional[Dict[str, Any]]:
        """
        Extract a raw goal definition from reflection output.
        Returns a dict with at least 'description' and 'priority' keys, or None.
        """
        if not reflection_output or not reflection_output.content:
            return None

        # Attempt to parse JSON goal from reflection content
        try:
            goal_data = json.loads(reflection_output.content) if isinstance(reflection_output.content, str) else reflection_output.content
        except (json.JSONDecodeError, TypeError):
            goal_data = None

        if isinstance(goal_data, dict) and 'description' in goal_data:
            return goal_data
        elif isinstance(reflection_output.content, str):
            # Fallback: treat entire content as description
            return {
                'description': reflection_output.content,
                'priority': 'medium',
                'source': 'reflection'
            }
        return None

    def _normalize_goal(self, raw_goal: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Normalize a raw goal definition to the canonical format.
        Ensures consistency with reflection outputs and system model state.
        """
        if not isinstance(raw_goal, dict):
            return None

        # Define canonical structure
        canonical_goal = {
            'id': raw_goal.get('id', f"goal_{datetime.utcnow().timestamp()}"),
            'description': raw_goal.get('description', '').strip(),
            'priority': self._normalize_priority(raw_goal.get('priority', 'medium')),
            'status': 'pending',
            'created_at': datetime.utcnow().isoformat(),
            'source': raw_goal.get('source', 'generated'),
            'constraints': raw_goal.get('constraints', []),
            'dependencies': raw_goal.get('dependencies', []),
            'metadata': raw_goal.get('metadata', {})
        }

        # Validate required fields
        if not canonical_goal['description']:
            return None

        # Merge with system model context if available
        system_context = self.system_model.get_current_state() if self.system_model else {}
        if system_context:
            canonical_goal['system_context'] = system_context

        return canonical_goal

    def _normalize_priority(self, priority: Any) -> str:
        """Normalize priority to one of: low, medium, high, critical."""
        valid_priorities = {'low', 'medium', 'high', 'critical'}
        if isinstance(priority, str) and priority.lower() in valid_priorities:
            return priority.lower()
        return 'medium'

    def _validate_goal(self, goal: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Validate a normalized goal through schema_alignment.
        Returns the validated goal or None if validation fails.
        """
        if not self.schema_alignment:
            # If no schema alignment available, accept as-is
            return goal

        try:
            # Convert to GoalSchema for validation
            goal_schema = GoalSchema(
                description=goal['description'],
                priority=goal['priority'],
                constraints=goal.get('constraints', []),
                dependencies=goal.get('dependencies', [])
            )

            # Validate through schema alignment
            validation_result = self.schema_alignment.validate_goal(goal_schema)
            if validation_result.is_valid:
                return goal
            else:
                # Log validation failure details
                print(f"Goal validation failed: {validation_result.errors}")
                return None
        except Exception as e:
            print(f"Error during goal validation: {e}")
            return None

    def store_goal(self, goal: Dict[str, Any]) -> bool:
        """
        Store a validated goal (e.g., to database or memory).
        Returns True if stored successfully.
        """
        if not goal or 'id' not in goal:
            return False

        # Placeholder for actual storage logic
        # In production, this would write to a persistent store
        self.goal_history.append(goal)
        return True

    def execute_goal(self, goal: Dict[str, Any]) -> bool:
        """
        Execute a validated goal.
        Returns True if execution started successfully.
        """
        if not goal or 'id' not in goal:
            return False

        # Placeholder for actual execution logic
        # In production, this would trigger the goal execution pipeline
        goal['status'] = 'executing'
        goal['executed_at'] = datetime.utcnow().isoformat()
        return True

    def get_goal_history(self) -> List[Dict[str, Any]]:
        """Return the list of all generated and stored goals."""
        return self.goal_history.copy()