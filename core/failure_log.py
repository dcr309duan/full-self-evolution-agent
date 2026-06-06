import json
import os
from datetime import datetime, timezone
from typing import Optional

LOG_FILE_PATH = "logs/failure_log.jsonl"

def _ensure_log_exists() -> None:
    """Initialize the log file with a header comment if it doesn't exist."""
    if not os.path.exists(LOG_FILE_PATH):
        os.makedirs(os.path.dirname(LOG_FILE_PATH), exist_ok=True)
        with open(LOG_FILE_PATH, "w") as f:
            f.write("# failure_log.jsonl - each line is a JSON object with fields: error_type, file, line, timestamp, mutation_id\n")

def log_failure(
    error_type: str,
    file: str,
    line: int,
    mutation_id: Optional[str] = None,
    timestamp: Optional[str] = None,
) -> None:
    """Append a structured error record to the failure log file.

    Args:
        error_type: A short string describing the error category (e.g., 'syntax_error', 'runtime_error').
        file: The source file path where the failure occurred.
        line: The line number in the source file where the failure occurred.
        mutation_id: Optional identifier for the mutation that caused the failure.
        timestamp: Optional ISO 8601 timestamp string. If not provided, current UTC time is used.
    """
    _ensure_log_exists()

    if timestamp is None:
        timestamp = datetime.now(timezone.utc).isoformat()

    record = {
        "error_type": error_type,
        "file": file,
        "line": line,
        "timestamp": timestamp,
        "mutation_id": mutation_id,
    }

    with open(LOG_FILE_PATH, "a") as f:
        f.write(json.dumps(record) + "\n")