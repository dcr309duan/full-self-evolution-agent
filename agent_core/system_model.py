from typing import Any, Dict, Optional, List
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