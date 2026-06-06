import json
import os
from datetime import datetime, timezone
from collections import deque
from typing import Optional, List, Dict, Any

DATA_DIR = "data"
MEMORY_FILE = os.path.join(DATA_DIR, "failure_memory.json")
MAX_ENTRIES = 50


class FailureMemory:
    """Maintains a sliding window of mutation failures with lessons learned."""

    def __init__(self, memory_file: str = MEMORY_FILE, max_entries: int = MAX_ENTRIES):
        self.memory_file = memory_file
        self.max_entries = max_entries
        self._entries: deque = deque(maxlen=max_entries)
        self._load()

    def _load(self) -> None:
        """Load entries from the JSON file, if it exists."""
        if os.path.exists(self.memory_file):
            try:
                with open(self.memory_file, "r") as f:
                    data = json.load(f)
                # Ensure data is a list of dicts
                if isinstance(data, list):
                    for entry in data:
                        if isinstance(entry, dict):
                            self._entries.append(entry)
            except (json.JSONDecodeError, IOError):
                # If file is corrupt, start fresh
                self._entries.clear()

    def _save(self) -> None:
        """Persist current entries to the JSON file."""
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(self.memory_file, "w") as f:
            json.dump(list(self._entries), f, indent=2)

    def record_failure(
        self,
        error_type: str,
        module: str,
        message: str,
        lesson: Optional[str] = None
    ) -> str:
        """
        Record a mutation failure and return a unique lesson_id.

        Args:
            error_type: One of 'syntax', 'integration', 'import'.
            module: The affected module name.
            message: The error message text.
            lesson: Optional lesson learned from this failure.

        Returns:
            A string lesson_id (timestamp-based) for referencing this entry.
        """
        timestamp = datetime.now(timezone.utc).isoformat()
        lesson_id = f"fail_{timestamp}"

        entry = {
            "lesson_id": lesson_id,
            "timestamp": timestamp,
            "error_type": error_type,
            "module": module,
            "message": message,
            "lesson": lesson or ""
        }

        self._entries.append(entry)
        self._save()
        return lesson_id

    def get_lessons(self) -> List[Dict[str, Any]]:
        """
        Return a list of recent lessons (entries with non-empty lesson field).

        Returns:
            List of dicts containing lesson_id, timestamp, error_type, module, message, lesson.
        """
        return [
            entry for entry in self._entries
            if entry.get("lesson")
        ]

    def clear_old_entries(self) -> None:
        """
        Remove entries beyond the sliding window (oldest first).
        This is automatically handled by deque(maxlen=...), but this method
        explicitly trims and saves.
        """
        while len(self._entries) > self.max_entries:
            self._entries.popleft()
        self._save()

    def get_all_entries(self) -> List[Dict[str, Any]]:
        """Return all stored entries (for debugging or analysis)."""
        return list(self._entries)

    def count(self) -> int:
        """Return the number of stored entries."""
        return len(self._entries)