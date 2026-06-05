"""Module interface definitions for the evolution orchestrator."""

from enum import Enum
from typing import Any, Dict, Optional
from dataclasses import dataclass


class ModuleStatus(Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"
    INITIALIZING = "initializing"


@dataclass
class ModuleInterface:
    module_id: str
    name: str
    status: ModuleStatus = ModuleStatus.INACTIVE
    schema_name: Optional[str] = None
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

    def activate(self):
        self.status = ModuleStatus.ACTIVE

    def deactivate(self):
        self.status = ModuleStatus.INACTIVE

    def set_error(self, error_msg: str):
        self.status = ModuleStatus.ERROR
        self.metadata["last_error"] = error_msg
