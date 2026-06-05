from typing import Any, Dict, Optional, List, Set, Tuple
from agent_core.schema_alignment import SchemaAligner, SchemaValidationError
from datetime import datetime

class SystemModel:
    """
    Represents the system state model with schema validation on all updates.
    """

    def __init__(self, initial_state: Optional[Dict[str, Any]] = None):
        self._state: Dict[str, Any] = {}
        self._aligner = SchemaAligner()
        self._consistency_history: List[Dict[str, Any]] = []
        self._dependency_graph: Dict[str, Set[str]] = {}  # goal -> set of dependencies
        self._dependency_graph_updates: List[Dict[str, Any]] = []  # history of updates
        self._feasibility_scores: Dict[str, float] = {}  # goal -> feasibility score (0.0 to 1.0)
        self._blocked_goals: Dict[str, List[str]] = {}  # goal -> list of blocking reasons
        self._dependency_resolution_events: List[Dict[str, Any]] = []  # log of resolution events
        self._prioritized_backlog: List[Dict[str, Any]] = []  # current prioritized backlog
        if initial_state:
            self.update(initial_state)

    def validate_system_model_input(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate and align incoming state updates using schema_alignment.

        Args:
            data: The raw input data to validate.

        Returns:
            The validated and aligned data dictionary.

        Raises:
            SchemaValidationError: If the data fails schema validation.
        """
        if not isinstance(data, dict):
            raise SchemaValidationError("Input must be a dictionary.")
        return self._aligner.align(data)

    def update(self, updates: Dict[str, Any]) -> None:
        """
        Update the system state with validated input.

        Args:
            updates: Dictionary of state changes to apply.
        """
        validated = self.validate_system_model_input(updates)
        self._state.update(validated)

    def set(self, key: str, value: Any) -> None:
        """
        Set a single state attribute with validation.

        Args:
            key: The attribute name.
            value: The value to set.
        """
        validated = self.validate_system_model_input({key: value})
        self._state.update(validated)

    def get_state(self) -> Dict[str, Any]:
        """Return a copy of the current system state."""
        return self._state.copy()

    def __getitem__(self, key: str) -> Any:
        return self._state[key]

    def __setitem__(self, key: str, value: Any) -> None:
        self.set(key, value)

    def record_consistency_check(self, passed: bool, module: str, details: str) -> None:
        """
        Record a consistency check result for trend analysis and early warning.

        Args:
            passed: Whether the consistency check passed.
            module: The module or component that was checked.
            details: Additional details about the check result.
        """
        check_record = {
            "timestamp": datetime.now().isoformat(),
            "passed": passed,
            "module": module,
            "details": details
        }
        self._consistency_history.append(check_record)

    def get_consistency_history(self) -> List[Dict[str, Any]]:
        """Return the history of consistency checks."""
        return self._consistency_history.copy()

    def get_recent_consistency_checks(self, count: int = 10) -> List[Dict[str, Any]]:
        """Return the most recent consistency checks."""
        return self._consistency_history[-count:] if self._consistency_history else []

    def get_consistency_summary(self) -> Dict[str, Any]:
        """Return a summary of consistency check results."""
        total = len(self._consistency_history)
        if total == 0:
            return {"total_checks": 0, "passed": 0, "failed": 0, "pass_rate": 0.0}
        
        passed = sum(1 for check in self._consistency_history if check["passed"])
        failed = total - passed
        pass_rate = (passed / total) * 100
        
        return {
            "total_checks": total,
            "passed": passed,
            "failed": failed,
            "pass_rate": pass_rate
        }

    def register_dependency_graph_update(self, goal: str, dependencies: Set[str]) -> None:
        """
        Register an update to the dependency graph for a specific goal.

        Args:
            goal: The goal identifier.
            dependencies: Set of dependencies for this goal.
        """
        self._dependency_graph[goal] = dependencies
        update_record = {
            "timestamp": datetime.now().isoformat(),
            "goal": goal,
            "dependencies": list(dependencies),
            "action": "update"
        }
        self._dependency_graph_updates.append(update_record)

    def get_dependency_graph(self) -> Dict[str, Set[str]]:
        """Return the current dependency graph."""
        return self._dependency_graph.copy()

    def get_dependency_graph_updates(self) -> List[Dict[str, Any]]:
        """Return the history of dependency graph updates."""
        return self._dependency_graph_updates.copy()

    def store_feasibility_score(self, goal: str, score: float) -> None:
        """
        Store a feasibility score for a specific goal.

        Args:
            goal: The goal identifier.
            score: Feasibility score between 0.0 and 1.0.
        """
        if not 0.0 <= score <= 1.0:
            raise ValueError("Feasibility score must be between 0.0 and 1.0")
        self._feasibility_scores[goal] = score

    def get_feasibility_score(self, goal: str) -> Optional[float]:
        """
        Get the feasibility score for a specific goal.

        Args:
            goal: The goal identifier.

        Returns:
            The feasibility score, or None if not set.
        """
        return self._feasibility_scores.get(goal)

    def get_all_feasibility_scores(self) -> Dict[str, float]:
        """Return all stored feasibility scores."""
        return self._feasibility_scores.copy()

    def track_blocked_goal(self, goal: str, reason: str) -> None:
        """
        Track a blocked goal with its reason.

        Args:
            goal: The goal identifier that is blocked.
            reason: The reason why the goal is blocked.
        """
        if goal not in self._blocked_goals:
            self._blocked_goals[goal] = []
        self._blocked_goals[goal].append(reason)

    def unblock_goal(self, goal: str) -> None:
        """
        Remove all blocking reasons for a goal.

        Args:
            goal: The goal identifier to unblock.
        """
        if goal in self._blocked_goals:
            del self._blocked_goals[goal]

    def get_blocked_goals(self) -> Dict[str, List[str]]:
        """Return all blocked goals and their reasons."""
        return self._blocked_goals.copy()

    def is_goal_blocked(self, goal: str) -> bool:
        """
        Check if a specific goal is blocked.

        Args:
            goal: The goal identifier to check.

        Returns:
            True if the goal is blocked, False otherwise.
        """
        return goal in self._blocked_goals

    def get_blocked_goal_reasons(self, goal: str) -> List[str]:
        """
        Get the reasons why a specific goal is blocked.

        Args:
            goal: The goal identifier.

        Returns:
            List of blocking reasons, or empty list if not blocked.
        """
        return self._blocked_goals.get(goal, [])

    def get_current_prioritized_backlog(self) -> List[Dict[str, Any]]:
        """
        Expose the current prioritized backlog.

        Returns:
            List of dictionaries representing the prioritized backlog.
            Each dictionary contains goal, feasibility_score, blocked status,
            and dependencies.
        """
        backlog = []
        for goal in self._dependency_graph:
            backlog_item = {
                "goal": goal,
                "feasibility_score": self._feasibility_scores.get(goal, 0.0),
                "blocked": self.is_goal_blocked(goal),
                "blocked_reasons": self.get_blocked_goal_reasons(goal),
                "dependencies": list(self._dependency_graph[goal])
            }
            backlog.append(backlog_item)
        
        # Sort by feasibility score (highest first), then by blocked status (unblocked first)
        backlog.sort(key=lambda x: (-x["feasibility_score"], x["blocked"]))
        self._prioritized_backlog = backlog
        return self._prioritized_backlog.copy()

    def log_dependency_resolution_event(self, event_type: str, goal: str, 
                                       resolution: str, details: Optional[str] = None) -> None:
        """
        Log a dependency resolution event for analysis.

        Args:
            event_type: Type of event (e.g., 'resolved', 'failed', 'blocked', 'unblocked').
            goal: The goal identifier involved in the event.
            resolution: Description of how the dependency was resolved.
            details: Optional additional details about the event.
        """
        event = {
            "timestamp": datetime.now().isoformat(),
            "event_type": event_type,
            "goal": goal,
            "resolution": resolution,
            "details": details or ""
        }
        self._dependency_resolution_events.append(event)

    def get_dependency_resolution_events(self) -> List[Dict[str, Any]]:
        """Return all logged dependency resolution events."""
        return self._dependency_resolution_events.copy()

    def get_recent_dependency_resolution_events(self, count: int = 10) -> List[Dict[str, Any]]:
        """Return the most recent dependency resolution events."""
        return self._dependency_resolution_events[-count:] if self._dependency_resolution_events else []

    def get_dependency_resolution_summary(self) -> Dict[str, Any]:
        """Return a summary of dependency resolution events."""
        total = len(self._dependency_resolution_events)
        if total == 0:
            return {"total_events": 0, "resolved": 0, "failed": 0, "blocked": 0, "unblocked": 0}
        
        resolved = sum(1 for event in self._dependency_resolution_events if event["event_type"] == "resolved")
        failed = sum(1 for event in self._dependency_resolution_events if event["event_type"] == "failed")
        blocked = sum(1 for event in self._dependency_resolution_events if event["event_type"] == "blocked")
        unblocked = sum(1 for event in self._dependency_resolution_events if event["event_type"] == "unblocked")
        
        return {
            "total_events": total,
            "resolved": resolved,
            "failed": failed,
            "blocked": blocked,
            "unblocked": unblocked
        }