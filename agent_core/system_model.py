from typing import Any, Dict, Optional
from agent_core.schema_alignment import SchemaAligner, SchemaValidationError

class SystemModel:
    """
    Represents the system state model with schema validation on all updates.
    """

    def __init__(self, initial_state: Optional[Dict[str, Any]] = None):
        self._state: Dict[str, Any] = {}
        self._aligner = SchemaAligner()
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