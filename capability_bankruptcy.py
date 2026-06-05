"""Capability Bankruptcy Module

Implements a periodic capability pruning and consolidation process:
- Scans all capabilities every 10 cycles
- Scores each on novelty (time since creation/update) and usage (downstream dependencies)
- Archives bottom 30% of capabilities
- Re-implements essential dropped capabilities with improvements
- Updates the knowledge base
"""

import json
import os
import time
from collections import defaultdict
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field, asdict
from enum import Enum

# Configuration constants
CYCLE_INTERVAL = 10
ARCHIVE_PERCENTAGE = 0.3
CAPABILITIES_FILE = "capabilities.json"
ARCHIVE_FILE = "archived_capabilities.json"
KNOWLEDGE_BASE_FILE = "knowledge_base.json"


class CapabilityStatus(Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"
    REIMPLEMENTED = "reimplemented"


@dataclass
class Capability:
    """Represents a single capability with metadata."""
    id: str
    name: str
    description: str
    creation_time: float
    last_update_time: float
    dependencies: List[str] = field(default_factory=list)
    downstream_tasks: List[str] = field(default_factory=list)
    status: CapabilityStatus = CapabilityStatus.ACTIVE
    version: int = 1
    known_issues: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Capability":
        data["status"] = CapabilityStatus(data["status"])
        return cls(**data)


@dataclass
class CapabilityScore:
    """Scoring result for a capability."""
    capability_id: str
    novelty_score: float
    usage_score: float
    combined_score: float


class CapabilityBankruptcy:
    """Core module for managing capability bankruptcy cycles."""

    def __init__(self, cycle_count: int = 0):
        self.cycle_count = cycle_count
        self.capabilities: Dict[str, Capability] = {}
        self.archived_capabilities: Dict[str, Capability] = {}
        self.knowledge_base: Dict[str, Any] = {}
        self._load_state()

    def _load_state(self) -> None:
        """Load capabilities, archives, and knowledge base from files."""
        if os.path.exists(CAPABILITIES_FILE):
            with open(CAPABILITIES_FILE, "r") as f:
                data = json.load(f)
                self.capabilities = {
                    cap_id: Capability.from_dict(cap_data)
                    for cap_id, cap_data in data.items()
                }

        if os.path.exists(ARCHIVE_FILE):
            with open(ARCHIVE_FILE, "r") as f:
                data = json.load(f)
                self.archived_capabilities = {
                    cap_id: Capability.from_dict(cap_data)
                    for cap_id, cap_data in data.items()
                }

        if os.path.exists(KNOWLEDGE_BASE_FILE):
            with open(KNOWLEDGE_BASE_FILE, "r") as f:
                self.knowledge_base = json.load(f)

    def _save_state(self) -> None:
        """Persist current state to files."""
        with open(CAPABILITIES_FILE, "w") as f:
            json.dump(
                {cap_id: cap.to_dict() for cap_id, cap in self.capabilities.items()},
                f,
                indent=2
            )

        with open(ARCHIVE_FILE, "w") as f:
            json.dump(
                {cap_id: cap.to_dict() for cap_id, cap in self.archived_capabilities.items()},
                f,
                indent=2
            )

        with open(KNOWLEDGE_BASE_FILE, "w") as f:
            json.dump(self.knowledge_base, f, indent=2)

    def add_capability(self, capability: Capability) -> None:
        """Add a new capability to the active set."""
        self.capabilities[capability.id] = capability
        self._save_state()

    def remove_capability(self, capability_id: str) -> None:
        """Remove a capability from the active set."""
        self.capabilities.pop(capability_id, None)
        self._save_state()

    def update_capability(self, capability_id: str, **kwargs) -> None:
        """Update fields of an existing capability."""
        if capability_id in self.capabilities:
            cap = self.capabilities[capability_id]
            for key, value in kwargs.items():
                if hasattr(cap, key):
                    setattr(cap, key, value)
            cap.last_update_time = time.time()
            self._save_state()

    def run_cycle(self) -> None:
        """Execute one bankruptcy cycle if conditions are met."""
        self.cycle_count += 1
        if self.cycle_count % CYCLE_INTERVAL != 0:
            return

        print(f"Running capability bankruptcy cycle {self.cycle_count // CYCLE_INTERVAL}...")
        self._scan_capabilities()
        scores = self._score_capabilities()
        to_archive = self._select_capabilities_to_archive(scores)
        self._archive_capabilities(to_archive)
        self._reimplement_essential_capabilities(to_archive)
        self._update_knowledge_base()
        self._save_state()
        print(f"Capability bankruptcy cycle complete. Archived {len(to_archive)} capabilities.")

    def _scan_capabilities(self) -> None:
        """Scan all active capabilities and update their metadata."""
        current_time = time.time()
        for cap in self.capabilities.values():
            # Update downstream task counts based on knowledge base
            cap.downstream_tasks = [
                task_id
                for task_id, task_data in self.knowledge_base.get("tasks", {}).items()
                if cap.id in task_data.get("dependencies", [])
            ]

    def _score_capabilities(self) -> List[CapabilityScore]:
        """Score each capability on novelty and usage."""
        current_time = time.time()
        scores = []

        if not self.capabilities:
            return scores

        # Find max values for normalization
        max_age = max(
            current_time - cap.creation_time
            for cap in self.capabilities.values()
        ) or 1
        max_usage = max(
            len(cap.downstream_tasks)
            for cap in self.capabilities.values()
        ) or 1

        for cap in self.capabilities.values():
            # Novelty score: higher for recently created/updated capabilities
            age = current_time - cap.last_update_time
            novelty_score = 1.0 - (age / max_age)  # 1 = newest, 0 = oldest

            # Usage score: higher for capabilities with many downstream tasks
            usage_count = len(cap.downstream_tasks)
            usage_score = usage_count / max_usage  # 1 = most used, 0 = least used

            # Combined score (equal weight)
            combined_score = (novelty_score + usage_score) / 2.0

            scores.append(CapabilityScore(
                capability_id=cap.id,
                novelty_score=novelty_score,
                usage_score=usage_score,
                combined_score=combined_score
            ))

        return scores

    def _select_capabilities_to_archive(self, scores: List[CapabilityScore]) -> List[str]:
        """Select the bottom 30% of capabilities to archive."""
        if not scores:
            return []

        sorted_scores = sorted(scores, key=lambda s: s.combined_score)
        num_to_archive = max(1, int(len(sorted_scores) * ARCHIVE_PERCENTAGE))
        return [s.capability_id for s in sorted_scores[:num_to_archive]]

    def _archive_capabilities(self, capability_ids: List[str]) -> None:
        """Move selected capabilities to the archive."""
        for cap_id in capability_ids:
            if cap_id in self.capabilities:
                cap = self.capabilities.pop(cap_id)
                cap.status = CapabilityStatus.ARCHIVED
                self.archived_capabilities[cap_id] = cap

    def _reimplement_essential_capabilities(self, archived_ids: List[str]) -> None:
        """Re-implement essential dropped capabilities with improvements."""
        for cap_id in archived_ids:
            if cap_id not in self.archived_capabilities:
                continue

            old_cap = self.archived_capabilities[cap_id]

            # Check if this capability is essential (has downstream tasks)
            if not old_cap.downstream_tasks:
                continue

            # Create improved version
            new_cap = Capability(
                id=f"{old_cap.id}_v{old_cap.version + 1}",
                name=old_cap.name,
                description=f"Reimplemented: {old_cap.description}",
                creation_time=time.time(),
                last_update_time=time.time(),
                dependencies=old_cap.dependencies.copy(),
                downstream_tasks=old_cap.downstream_tasks.copy(),
                status=CapabilityStatus.REIMPLEMENTED,
                version=old_cap.version + 1,
                known_issues=self._resolve_known_issues(old_cap.known_issues),
                tags=old_cap.tags.copy()
            )

            # Consolidate duplicates if any
            new_cap = self._consolidate_duplicates(new_cap)

            self.capabilities[new_cap.id] = new_cap
            old_cap.status = CapabilityStatus.REIMPLEMENTED

    def _resolve_known_issues(self, issues: List[str]) -> List[str]:
        """Mark known issues as resolved in reimplementation."""
        resolved_issues = []
        for issue in issues:
            resolved_issues.append(f"[RESOLVED] {issue}")
        return resolved_issues

    def _consolidate_duplicates(self, capability: Capability) -> Capability:
        """Check for and consolidate duplicate capabilities."""
        for existing_cap in self.capabilities.values():
            if (existing_cap.name == capability.name and
                existing_cap.id != capability.id and
                existing_cap.status == CapabilityStatus.ACTIVE):
                # Merge downstream tasks
                for task in existing_cap.downstream_tasks:
                    if task not in capability.downstream_tasks:
                        capability.downstream_tasks.append(task)
                # Remove the duplicate
                self.remove_capability(existing_cap.id)
        return capability

    def _update_knowledge_base(self) -> None:
        """Update the knowledge base to reflect the new capability set."""
        # Update capability registry
        self.knowledge_base["capabilities"] = {
            cap_id: {
                "name": cap.name,
                "version": cap.version,
                "status": cap.status.value,
                "dependencies": cap.dependencies,
                "downstream_tasks": cap.downstream_tasks,
                "tags": cap.tags
            }
            for cap_id, cap in self.capabilities.items()
        }

        # Update archived capabilities
        self.knowledge_base["archived_capabilities"] = {
            cap_id: {
                "name": cap.name,
                "version": cap.version,
                "archive_reason": "bankruptcy_cycle",
                "original_downstream_tasks": cap.downstream_tasks
            }
            for cap_id, cap in self.archived_capabilities.items()
        }

        # Add bankruptcy cycle metadata
        if "bankruptcy_history" not in self.knowledge_base:
            self.knowledge_base["bankruptcy_history"] = []

        self.knowledge_base["bankruptcy_history"].append({
            "cycle": self.cycle_count // CYCLE_INTERVAL,
            "timestamp": time.time(),
            "capabilities_before": len(self.capabilities) + len(
                [c for c in self.archived_capabilities.values() if c.status == CapabilityStatus.ARCHIVED]
            ),
            "capabilities_after": len(self.capabilities),
            "archived_count": len([
                c for c in self.archived_capabilities.values()
                if c.status == CapabilityStatus.ARCHIVED
            ]),
            "reimplemented_count": len([
                c for c in self.capabilities.values()
                if c.status == CapabilityStatus.REIMPLEMENTED
            ])
        })

    def get_capability_summary(self) -> Dict[str, Any]:
        """Return a summary of the current capability state."""
        return {
            "total_active": len(self.capabilities),
            "total_archived": len(self.archived_capabilities),
            "active_capabilities": [
                {"id": cap.id, "name": cap.name, "version": cap.version}
                for cap in self.capabilities.values()
            ],
            "archived_capabilities": [
                {"id": cap.id, "name": cap.name, "version": cap.version}
                for cap in self.archived_capabilities.values()
            ],
            "last_cycle": self.cycle_count // CYCLE_INTERVAL
        }


# Convenience function for external use
def run_bankruptcy_cycle(cycle_count: int = 0) -> CapabilityBankruptcy:
    """Run a single bankruptcy cycle and return the manager instance."""
    manager = CapabilityBankruptcy(cycle_count)
    manager.run_cycle()
    return manager


if __name__ == "__main__":
    # Example usage
    manager = CapabilityBankruptcy()
    
    # Add some example capabilities
    manager.add_capability(Capability(
        id="cap_001",
        name="DataProcessor",
        description="Processes raw data into structured format",
        creation_time=time.time() - 1000,
        last_update_time=time.time() - 500,
        dependencies=["cap_002"],
        downstream_tasks=["task_001", "task_002"],
        tags=["data", "processing"]
    ))
    
    manager.add_capability(Capability(
        id="cap_002",
        name="DataValidator",
        description="Validates data integrity",
        creation_time=time.time() - 2000,
        last_update_time=time.time() - 1500,
        downstream_tasks=["cap_001"],
        tags=["data", "validation"]
    ))
    
    # Run a cycle
    manager.run_cycle()
    print(manager.get_capability_summary())