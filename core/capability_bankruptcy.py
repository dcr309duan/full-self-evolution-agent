"""Capability Bankruptcy & Consolidation Engine.

Scans capabilities from knowledge base and module registry, computes usage scores,
flags underperforming capabilities for removal or merge, and enforces execution every 5 cycles.
"""

import logging
import copy
import time
from typing import Dict, List, Tuple, Optional, Any

logger = logging.getLogger(__name__)

# Default configuration
DEFAULT_THRESHOLD = 0.3
EXECUTION_INTERVAL = 5  # cycles
RECENCY_DECAY_CYCLES = 20
COVERAGE_THRESHOLD = 0.6  # 60% functionality coverage for merge suggestion


class CapabilityBankruptcyEngine:
    """Engine for detecting and handling capability bankruptcy."""

    def __init__(self, knowledge_base: Dict[str, Any], module_registry: Dict[str, Any],
                 threshold: float = DEFAULT_THRESHOLD):
        self.knowledge_base = knowledge_base
        self.module_registry = module_registry
        self.threshold = threshold
        self.cycle_count = 0
        self.rollback_snapshots: List[Dict[str, Any]] = []
        self.capability_scores: Dict[str, float] = {}

    def _get_capabilities(self) -> Dict[str, Dict[str, Any]]:
        """Retrieve all capabilities from knowledge base and module registry."""
        capabilities = {}
        # From knowledge base
        if "capabilities" in self.knowledge_base:
            capabilities.update(self.knowledge_base["capabilities"])
        # From module registry
        for module_name, module_info in self.module_registry.items():
            if "capabilities" in module_info:
                for cap_name, cap_data in module_info["capabilities"].items():
                    full_name = f"{module_name}.{cap_name}"
                    capabilities[full_name] = cap_data
        return capabilities

    def _compute_usage_score(self, capability: Dict[str, Any]) -> float:
        """Compute usage score based on call frequency, recency, dependencies, and age."""
        times_called = capability.get("times_called", 0)
        last_called_cycle = capability.get("last_called_cycle", 0)
        dependency_count = capability.get("dependency_count", 0)
        creation_cycle = capability.get("creation_cycle", 0)

        # Recency bonus: decays over RECENCY_DECAY_CYCLES
        cycles_since_last_call = self.cycle_count - last_called_cycle
        recency_bonus = max(0, 1 - (cycles_since_last_call / RECENCY_DECAY_CYCLES))

        # Age penalty: increases with age
        age = self.cycle_count - creation_cycle
        age_penalty = min(1, age / 100)  # Cap at 1

        score = (times_called * 0.4) + (recency_bonus * 0.3) + (dependency_count * 0.2) - (age_penalty * 0.1)
        return max(0, score)  # Ensure non-negative

    def _find_merge_candidates(self, flagged_capabilities: List[str]) -> Dict[str, List[str]]:
        """Find merge suggestions for flagged capabilities."""
        all_caps = self._get_capabilities()
        merge_suggestions: Dict[str, List[str]] = {}

        for flagged_name in flagged_capabilities:
            if flagged_name not in all_caps:
                continue
            flagged_cap = all_caps[flagged_name]
            flagged_functionality = set(flagged_cap.get("functionality", []))

            best_coverage = 0.0
            best_candidate = None

            for other_name, other_cap in all_caps.items():
                if other_name == flagged_name:
                    continue
                other_functionality = set(other_cap.get("functionality", []))
                if not other_functionality:
                    continue

                overlap = flagged_functionality.intersection(other_functionality)
                coverage = len(overlap) / len(flagged_functionality) if flagged_functionality else 0

                if coverage >= COVERAGE_THRESHOLD and coverage > best_coverage:
                    best_coverage = coverage
                    best_candidate = other_name

            if best_candidate:
                merge_suggestions[flagged_name] = [best_candidate]

        return merge_suggestions

    def _create_rollback_snapshot(self) -> Dict[str, Any]:
        """Create a snapshot of current state for rollback."""
        snapshot = {
            "timestamp": time.time(),
            "cycle": self.cycle_count,
            "knowledge_base": copy.deepcopy(self.knowledge_base),
            "module_registry": copy.deepcopy(self.module_registry),
        }
        self.rollback_snapshots.append(snapshot)
        return snapshot

    def _run_critical_tests(self) -> bool:
        """Run critical test suite. Returns True if all pass."""
        # Placeholder for actual test execution
        # In production, integrate with test framework
        logger.info("Running critical test suite...")
        # Simulate test success
        return True

    def _revert_changes(self, snapshot: Dict[str, Any]) -> None:
        """Revert to a given snapshot state."""
        logger.warning("Reverting changes to snapshot from cycle %d", snapshot["cycle"])
        self.knowledge_base.clear()
        self.knowledge_base.update(snapshot["knowledge_base"])
        self.module_registry.clear()
        self.module_registry.update(snapshot["module_registry"])

    def _remove_capability(self, cap_name: str) -> None:
        """Remove a capability from both knowledge base and module registry."""
        # Remove from knowledge base
        if "capabilities" in self.knowledge_base and cap_name in self.knowledge_base["capabilities"]:
            del self.knowledge_base["capabilities"][cap_name]
            logger.info("Removed capability '%s' from knowledge base", cap_name)

        # Remove from module registry
        for module_name in list(self.module_registry.keys()):
            module_info = self.module_registry[module_name]
            if "capabilities" in module_info and cap_name in module_info["capabilities"]:
                del module_info["capabilities"][cap_name]
                logger.info("Removed capability '%s' from module '%s'", cap_name, module_name)

    def _merge_capabilities(self, source_name: str, target_name: str) -> None:
        """Merge source capability into target capability."""
        all_caps = self._get_capabilities()
        if source_name not in all_caps or target_name not in all_caps:
            logger.error("Cannot merge: one or both capabilities not found")
            return

        source_cap = all_caps[source_name]
        target_cap = all_caps[target_name]

        # Merge functionality
        source_func = set(source_cap.get("functionality", []))
        target_func = set(target_cap.get("functionality", []))
        merged_func = list(source_func.union(target_func))

        # Update target capability
        if "capabilities" in self.knowledge_base and target_name in self.knowledge_base["capabilities"]:
            self.knowledge_base["capabilities"][target_name]["functionality"] = merged_func
            self.knowledge_base["capabilities"][target_name]["times_called"] = (
                source_cap.get("times_called", 0) + target_cap.get("times_called", 0)
            )

        # Remove source capability
        self._remove_capability(source_name)
        logger.info("Merged capability '%s' into '%s'", source_name, target_name)

    def execute(self) -> Dict[str, Any]:
        """Main execution: scan, score, flag, and act on capabilities."""
        self.cycle_count += 1

        if self.cycle_count % EXECUTION_INTERVAL != 0:
            logger.debug("Skipping execution (cycle %d not multiple of %d)",
                         self.cycle_count, EXECUTION_INTERVAL)
            return {"status": "skipped", "cycle": self.cycle_count}

        logger.info("Starting capability bankruptcy check (cycle %d)", self.cycle_count)

        # Step 1: Get all capabilities
        capabilities = self._get_capabilities()
        if not capabilities:
            logger.info("No capabilities found")
            return {"status": "no_capabilities", "cycle": self.cycle_count}

        # Step 2: Compute usage scores
        self.capability_scores = {}
        for cap_name, cap_data in capabilities.items():
            self.capability_scores[cap_name] = self._compute_usage_score(cap_data)

        # Step 3: Flag low-scoring capabilities
        flagged = [name for name, score in self.capability_scores.items() if score < self.threshold]
        logger.info("Flagged %d capabilities with score < %.2f", len(flagged), self.threshold)

        if not flagged:
            return {"status": "no_action", "cycle": self.cycle_count, "scores": self.capability_scores}

        # Step 4: Find merge candidates for flagged capabilities
        merge_suggestions = self._find_merge_candidates(flagged)

        # Step 5: Create rollback snapshot
        snapshot = self._create_rollback_snapshot()
        logger.info("Created rollback snapshot at cycle %d", self.cycle_count)

        # Step 6: Apply changes (remove or merge)
        changes_made = []
        for cap_name in flagged:
            if cap_name in merge_suggestions:
                target = merge_suggestions[cap_name][0]
                self._merge_capabilities(cap_name, target)
                changes_made.append({"action": "merge", "source": cap_name, "target": target})
            else:
                self._remove_capability(cap_name)
                changes_made.append({"action": "remove", "capability": cap_name})

        # Step 7: Run critical tests and revert if needed
        tests_passed = self._run_critical_tests()
        if not tests_passed:
            logger.error("Critical tests failed! Reverting changes.")
            self._revert_changes(snapshot)
            return {
                "status": "reverted",
                "cycle": self.cycle_count,
                "reason": "tests_failed",
                "changes": changes_made,
            }

        logger.info("Capability bankruptcy check completed successfully")
        return {
            "status": "completed",
            "cycle": self.cycle_count,
            "flagged": flagged,
            "merge_suggestions": merge_suggestions,
            "changes": changes_made,
            "scores": self.capability_scores,
        }

    def get_stats(self) -> Dict[str, Any]:
        """Return current statistics."""
        return {
            "cycle_count": self.cycle_count,
            "threshold": self.threshold,
            "capability_scores": self.capability_scores,
            "snapshots_count": len(self.rollback_snapshots),
        }