from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict, Callable, Any
from datetime import datetime

class CycleReport(BaseModel):
    schema_version: int = Field(..., ge=1, description="Schema version number")
    timestamp: float = Field(..., description="Unix timestamp of report generation")
    component: str = Field(..., min_length=1, description="Component identifier")
    cycle_id: str = Field(..., min_length=1, description="Unique cycle identifier")
    reflection_summary: str = Field(..., min_length=1, description="Summary of reflection output")
    metrics: Optional[dict] = Field(default=None, description="Optional performance metrics")

    @field_validator('timestamp')
    def validate_timestamp(cls, v):
        if v < 0:
            raise ValueError('Timestamp must be non-negative')
        return v

    @field_validator('component')
    def validate_component(cls, v):
        allowed_components = ['reflection_parser', 'goal_generator', 'failure_analysis']
        if v not in allowed_components:
            raise ValueError(f'Component must be one of {allowed_components}')
        return v

class GoalSpec(BaseModel):
    schema_version: int = Field(..., ge=1, description="Schema version number")
    timestamp: float = Field(..., description="Unix timestamp of goal generation")
    component: str = Field(..., min_length=1, description="Component identifier")
    goal_id: str = Field(..., min_length=1, description="Unique goal identifier")
    description: str = Field(..., min_length=1, description="Goal description")
    priority: int = Field(..., ge=1, le=5, description="Priority level (1-5)")
    constraints: Optional[List[str]] = Field(default=None, description="List of constraints")

    @field_validator('timestamp')
    def validate_timestamp(cls, v):
        if v < 0:
            raise ValueError('Timestamp must be non-negative')
        return v

    @field_validator('component')
    def validate_component(cls, v):
        allowed_components = ['reflection_parser', 'goal_generator', 'failure_analysis']
        if v not in allowed_components:
            raise ValueError(f'Component must be one of {allowed_components}')
        return v

class FailureRecord(BaseModel):
    schema_version: int = Field(..., ge=1, description="Schema version number")
    timestamp: float = Field(..., description="Unix timestamp of failure analysis")
    component: str = Field(..., min_length=1, description="Component identifier")
    failure_id: str = Field(..., min_length=1, description="Unique failure identifier")
    error_type: str = Field(..., min_length=1, description="Type of error encountered")
    error_message: str = Field(..., min_length=1, description="Detailed error message")
    stack_trace: Optional[str] = Field(default=None, description="Optional stack trace")
    severity: int = Field(..., ge=1, le=5, description="Severity level (1-5)")

    @field_validator('timestamp')
    def validate_timestamp(cls, v):
        if v < 0:
            raise ValueError('Timestamp must be non-negative')
        return v

    @field_validator('component')
    def validate_component(cls, v):
        allowed_components = ['reflection_parser', 'goal_generator', 'failure_analysis']
        if v not in allowed_components:
            raise ValueError(f'Component must be one of {allowed_components}')
        return v

# Migration registry: maps (from_version, to_version) -> callable
_migration_registry: Dict[tuple, Callable] = {}

def register_migration(from_version: int, to_version: int, func: Callable) -> None:
    """Register a migration function for a specific version transition."""
    _migration_registry[(from_version, to_version)] = func

def get_current_version() -> int:
    """Return the latest schema version number."""
    return 2

def migrate_v1_to_v2(old_report: dict) -> dict:
    """
    Transform a legacy v1 schema report to v2 schema.
    
    Expected v1 schema: { 'timestamp', 'component', 'cycle_id', 'reflection_summary', 'metrics' }
    v2 schema adds 'schema_version' field and ensures all required fields exist.
    """
    new_report = old_report.copy()
    new_report['schema_version'] = 2
    
    # Ensure all required fields exist with defaults if missing
    if 'timestamp' not in new_report:
        new_report['timestamp'] = datetime.now().timestamp()
    if 'component' not in new_report:
        new_report['component'] = 'reflection_parser'
    if 'cycle_id' not in new_report:
        new_report['cycle_id'] = 'unknown'
    if 'reflection_summary' not in new_report:
        new_report['reflection_summary'] = ''
    if 'metrics' not in new_report:
        new_report['metrics'] = None
    
    return new_report

# Register the v1 to v2 migration
register_migration(1, 2, migrate_v1_to_v2)