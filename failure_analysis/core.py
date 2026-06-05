from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, Any, Dict, List
import uuid


@dataclass
class FailureRecord:
    """
    Represents a single failure record with canonical schema support.
    
    Attributes:
        id: Unique identifier for the failure record.
        failure_type: Type/category of the failure.
        component: The component or subsystem where failure occurred.
        description: Human-readable description of the failure.
        severity: Severity level (e.g., 'critical', 'major', 'minor').
        timestamp: ISO 8601 timestamp when the failure was recorded.
        schema_version: Version of the schema used for this record.
        metadata: Optional dictionary for additional contextual data.
        root_cause: Optional identified root cause of the failure.
        resolution: Optional resolution or mitigation steps.
        related_failures: Optional list of related failure record IDs.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    failure_type: str = ""
    component: str = ""
    description: str = ""
    severity: str = "minor"
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    schema_version: str = "1.0"
    metadata: Optional[Dict[str, Any]] = None
    root_cause: Optional[str] = None
    resolution: Optional[str] = None
    related_failures: Optional[List[str]] = None

    def __post_init__(self):
        """Validate and set defaults after initialization."""
        if self.metadata is None:
            self.metadata = {}
        if self.related_failures is None:
            self.related_failures = []

    def to_dict(self) -> Dict[str, Any]:
        """Convert the FailureRecord to a dictionary."""
        return {
            "id": self.id,
            "failure_type": self.failure_type,
            "component": self.component,
            "description": self.description,
            "severity": self.severity,
            "timestamp": self.timestamp,
            "schema_version": self.schema_version,
            "metadata": self.metadata,
            "root_cause": self.root_cause,
            "resolution": self.resolution,
            "related_failures": self.related_failures,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FailureRecord":
        """Create a FailureRecord from a dictionary."""
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            failure_type=data.get("failure_type", ""),
            component=data.get("component", ""),
            description=data.get("description", ""),
            severity=data.get("severity", "minor"),
            timestamp=data.get("timestamp", datetime.now(timezone.utc).isoformat()),
            schema_version=data.get("schema_version", "1.0"),
            metadata=data.get("metadata", {}),
            root_cause=data.get("root_cause"),
            resolution=data.get("resolution"),
            related_failures=data.get("related_failures", []),
        )


def create_failure_record(
    failure_type: str,
    component: str,
    description: str,
    severity: str = "minor",
    metadata: Optional[Dict[str, Any]] = None,
    root_cause: Optional[str] = None,
    resolution: Optional[str] = None,
) -> FailureRecord:
    """
    Factory function to create a FailureRecord with proper defaults.
    
    Args:
        failure_type: Type/category of the failure.
        component: The component or subsystem where failure occurred.
        description: Human-readable description of the failure.
        severity: Severity level (default: 'minor').
        metadata: Optional dictionary for additional contextual data.
        root_cause: Optional identified root cause.
        resolution: Optional resolution steps.
    
    Returns:
        A new FailureRecord instance.
    """
    return FailureRecord(
        failure_type=failure_type,
        component=component,
        description=description,
        severity=severity,
        metadata=metadata or {},
        root_cause=root_cause,
        resolution=resolution,
    )