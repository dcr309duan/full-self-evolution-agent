import json
import os
from datetime import datetime
from typing import Optional, List, Dict, Any

FAILURE_LOG_PATH = os.path.join("logs", "failure_log.jsonl")

def _ensure_log_dir():
    os.makedirs(os.path.dirname(FAILURE_LOG_PATH), exist_ok=True)

def log_failure(error_type: str, file: str, message: str, details: Optional[Dict[str, Any]] = None) -> None:
    """Append a structured error record to the failure log."""
    _ensure_log_dir()
    record = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "error_type": error_type,
        "file": file,
        "message": message,
        "details": details or {}
    }
    with open(FAILURE_LOG_PATH, "a") as f:
        f.write(json.dumps(record) + "\n")

def query_failures(error_type: Optional[str] = None, file: Optional[str] = None) -> List[Dict[str, Any]]:
    """Return all failure records matching the given error_type and/or file."""
    _ensure_log_dir()
    if not os.path.exists(FAILURE_LOG_PATH):
        return []
    results = []
    with open(FAILURE_LOG_PATH, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if error_type is not None and record.get("error_type") != error_type:
                continue
            if file is not None and record.get("file") != file:
                continue
            results.append(record)
    return results

def get_recent_failures(count: int = 10) -> List[Dict[str, Any]]:
    """Return the most recent failure records (up to `count`)."""
    _ensure_log_dir()
    if not os.path.exists(FAILURE_LOG_PATH):
        return []
    all_records = []
    with open(FAILURE_LOG_PATH, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            all_records.append(record)
    # Return the last `count` records (most recent)
    return all_records[-count:]