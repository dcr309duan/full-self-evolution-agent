from typing import Any, Dict, List, Optional
from datetime import datetime
from .schema import CycleReport, SchemaVersion

def parse_reflection(data: Dict[str, Any]) -> CycleReport:
    """
    Parse a raw reflection dictionary into a validated CycleReport object.
    
    Args:
        data: Raw dictionary containing reflection data.
        
    Returns:
        CycleReport object with all required fields populated.
        
    Raises:
        ValueError: If required fields are missing or invalid.
    """
    # Extract and validate required fields
    cycle_id = data.get("cycle_id")
    if not cycle_id:
        raise ValueError("Missing required field: cycle_id")
    
    timestamp = data.get("timestamp")
    if not timestamp:
        timestamp = datetime.utcnow().isoformat()
    
    content = data.get("content")
    if not content:
        raise ValueError("Missing required field: content")
    
    # Extract optional fields with defaults
    tags = data.get("tags", [])
    if not isinstance(tags, list):
        tags = [tags] if tags else []
    
    metadata = data.get("metadata", {})
    if not isinstance(metadata, dict):
        metadata = {}
    
    # Build the CycleReport with schema_version
    report = CycleReport(
        cycle_id=cycle_id,
        timestamp=timestamp,
        content=content,
        tags=tags,
        metadata=metadata,
        schema_version=SchemaVersion.current()
    )
    
    # Ensure all required fields are populated
    _validate_report(report)
    
    return report


def parse_reflections_batch(data_list: List[Dict[str, Any]]) -> List[CycleReport]:
    """
    Parse a list of raw reflection dictionaries into CycleReport objects.
    
    Args:
        data_list: List of raw dictionaries containing reflection data.
        
    Returns:
        List of validated CycleReport objects.
    """
    return [parse_reflection(data) for data in data_list]


def _validate_report(report: CycleReport) -> None:
    """
    Validate that all required fields in a CycleReport are populated.
    
    Args:
        report: CycleReport object to validate.
        
    Raises:
        ValueError: If any required field is missing or invalid.
    """
    required_fields = ["cycle_id", "timestamp", "content", "schema_version"]
    
    for field in required_fields:
        value = getattr(report, field, None)
        if value is None or (isinstance(value, str) and not value.strip()):
            raise ValueError(f"Required field '{field}' is empty or missing")
    
    # Validate schema_version is a proper SchemaVersion object
    if not isinstance(report.schema_version, SchemaVersion):
        raise ValueError("schema_version must be a SchemaVersion object")


def update_report_metadata(
    report: CycleReport,
    metadata_updates: Dict[str, Any]
) -> CycleReport:
    """
    Update the metadata of an existing CycleReport.
    
    Args:
        report: Existing CycleReport object.
        metadata_updates: Dictionary of metadata fields to update.
        
    Returns:
        Updated CycleReport object.
    """
    updated_metadata = {**report.metadata, **metadata_updates}
    return CycleReport(
        cycle_id=report.cycle_id,
        timestamp=report.timestamp,
        content=report.content,
        tags=report.tags,
        metadata=updated_metadata,
        schema_version=report.schema_version
    )