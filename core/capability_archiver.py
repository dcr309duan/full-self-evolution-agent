import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

ARCHIVE_DIR = "archived_capabilities"
INDEX_FILE = os.path.join(ARCHIVE_DIR, "index.json")


def _ensure_archive_dir() -> None:
    """Create the archive directory if it does not exist."""
    os.makedirs(ARCHIVE_DIR, exist_ok=True)


def _load_index() -> List[Dict[str, Any]]:
    """Load the archive index from disk, returning an empty list if missing."""
    _ensure_archive_dir()
    if not os.path.exists(INDEX_FILE):
        return []
    with open(INDEX_FILE, "r") as f:
        return json.load(f)


def _save_index(index: List[Dict[str, Any]]) -> None:
    """Persist the archive index to disk."""
    _ensure_archive_dir()
    with open(INDEX_FILE, "w") as f:
        json.dump(index, f, indent=2)


def archive_capability(capability: Dict[str, Any]) -> str:
    """
    Archive a single capability dictionary to a dated JSON file.

    Args:
        capability: A dictionary representing the capability to archive.

    Returns:
        The filename (relative path) of the newly created archive file.
    """
    _ensure_archive_dir()
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename = os.path.join(ARCHIVE_DIR, f"{timestamp}.json")

    with open(filename, "w") as f:
        json.dump(capability, f, indent=2)

    # Update index
    index = _load_index()
    index.append({
        "filename": filename,
        "timestamp": timestamp,
        "capability_id": capability.get("id", capability.get("name", "unknown")),
    })
    _save_index(index)

    return filename


def list_archived_capabilities() -> List[Dict[str, Any]]:
    """Return the list of archived capability metadata from the index."""
    return _load_index()


def restore_capability(index_entry: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Restore a capability from an archive file given its index entry.

    Args:
        index_entry: A dictionary with at least a 'filename' key.

    Returns:
        The capability dictionary if found, None otherwise.
    """
    filename = index_entry.get("filename")
    if not filename or not os.path.exists(filename):
        return None
    with open(filename, "r") as f:
        return json.load(f)


def restore_latest_capability() -> Optional[Dict[str, Any]]:
    """Restore the most recently archived capability."""
    index = list_archived_capabilities()
    if not index:
        return None
    return restore_capability(index[-1])