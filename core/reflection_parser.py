from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field, validator
from enum import Enum


class SimulationPrediction(str, Enum):
    PASS = "pass"
    FAIL = "fail"


class SimulationResult(BaseModel):
    """Schema for simulation result fields."""
    simulation_prediction: SimulationPrediction = Field(
        ...,
        description="Prediction result of the simulation: 'pass' or 'fail'."
    )
    simulation_confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence level of the simulation prediction, between 0.0 and 1.0."
    )
    simulation_side_effects: List[str] = Field(
        default_factory=list,
        description="List of module names that may be affected by the simulation."
    )
    simulation_accuracy_trend: List[float] = Field(
        default_factory=list,
        description="Recent accuracy values from simulation runs, ordered chronologically."
    )

    @validator("simulation_confidence")
    def validate_confidence(cls, v: float) -> float:
        if v < 0.0 or v > 1.0:
            raise ValueError("simulation_confidence must be between 0.0 and 1.0")
        return v

    @validator("simulation_accuracy_trend")
    def validate_accuracy_trend(cls, v: List[float]) -> List[float]:
        for val in v:
            if val < 0.0 or val > 1.0:
                raise ValueError("Each accuracy value must be between 0.0 and 1.0")
        return v


class SchemaAlignmentLayer:
    """
    Schema alignment layer that integrates simulation result fields
    into the existing schema structure.
    """

    def __init__(self, base_schema: Optional[Dict[str, Any]] = None):
        self.base_schema = base_schema or {}
        self.simulation_fields = SimulationResult.schema()

    def align_schema(self, schema: Dict[str, Any]) -> Dict[str, Any]:
        """
        Align the given schema by injecting simulation result fields.

        Args:
            schema: The existing schema dictionary to be updated.

        Returns:
            Updated schema dictionary with simulation fields added.
        """
        aligned = schema.copy()
        aligned.setdefault("properties", {}).update(
            {
                "simulation_prediction": self.simulation_fields["properties"]["simulation_prediction"],
                "simulation_confidence": self.simulation_fields["properties"]["simulation_confidence"],
                "simulation_side_effects": self.simulation_fields["properties"]["simulation_side_effects"],
                "simulation_accuracy_trend": self.simulation_fields["properties"]["simulation_accuracy_trend"],
            }
        )
        # Ensure required fields are present
        required = aligned.get("required", [])
        for field in ["simulation_prediction", "simulation_confidence"]:
            if field not in required:
                required.append(field)
        aligned["required"] = required
        return aligned

    def validate_simulation_data(self, data: Dict[str, Any]) -> SimulationResult:
        """
        Validate and return a SimulationResult instance from raw data.

        Args:
            data: Dictionary containing simulation result fields.

        Returns:
            SimulationResult instance if validation passes.

        Raises:
            ValidationError: If data does not conform to the schema.
        """
        return SimulationResult(**data)