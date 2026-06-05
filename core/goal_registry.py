from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class TriageAction(BaseModel):
    """Represents a single triage action recorded in the goal's history."""
    action: str = Field(..., description="Type of triage action: 'flagged', 'decomposed', or 'archived'")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="When the action was taken")
    reason: str = Field(..., description="Explanation for why the action was taken")
    previous_state: Optional[Dict[str, Any]] = Field(None, description="Snapshot of goal state before this action, for rollback")
    actor: Optional[str] = Field(None, description="User or system component that performed the action")


class GoalSchema(BaseModel):
    """Schema for a goal with triage history for traceability and rollback."""
    id: str = Field(..., description="Unique identifier for the goal")
    title: str = Field(..., description="Short description of the goal")
    description: Optional[str] = Field(None, description="Detailed goal description")
    status: str = Field("active", description="Current status: 'active', 'flagged', 'decomposed', 'archived'")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="When the goal was created")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="When the goal was last modified")
    triage_history: List[TriageAction] = Field(default_factory=list, description="Chronological record of all triage actions")

    def record_triage_action(self, action: str, reason: str, previous_state: Optional[Dict[str, Any]] = None, actor: Optional[str] = None) -> None:
        """Record a triage action in the goal's history and update status accordingly.

        Args:
            action: The triage action ('flagged', 'decomposed', 'archived').
            reason: Explanation for the action.
            previous_state: Snapshot of goal state before the action (for rollback).
            actor: Who or what performed the action.
        """
        if action not in {"flagged", "decomposed", "archived"}:
            raise ValueError(f"Invalid triage action: {action}. Must be one of 'flagged', 'decomposed', 'archived'.")

        triage_entry = TriageAction(
            action=action,
            timestamp=datetime.utcnow(),
            reason=reason,
            previous_state=previous_state,
            actor=actor
        )
        self.triage_history.append(triage_entry)
        self.status = action
        self.updated_at = datetime.utcnow()

    def rollback_last_triage(self) -> Optional[Dict[str, Any]]:
        """Rollback the most recent triage action if a previous state snapshot exists.

        Returns:
            The previous state dictionary if rollback was successful, None otherwise.
        """
        if not self.triage_history:
            return None

        last_action = self.triage_history[-1]
        if last_action.previous_state is None:
            return None

        # Restore previous state (excluding triage_history to avoid duplication)
        previous_state = last_action.previous_state.copy()
        previous_state.pop("triage_history", None)
        for key, value in previous_state.items():
            setattr(self, key, value)

        # Remove the rolled-back action from history
        self.triage_history.pop()
        self.updated_at = datetime.utcnow()
        return previous_state

    def get_triage_history(self) -> List[Dict[str, Any]]:
        """Return triage history as a list of dictionaries for easy serialization."""
        return [action.dict() for action in self.triage_history]