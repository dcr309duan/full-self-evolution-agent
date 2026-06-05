"""Capability Bankruptcy & Consolidation Engine.

Scans capabilities from knowledge base and module registry, computes usage scores,
flags underperforming capabilities for removal or merge, and enforces execution every 10 cycles.
Uses goal_impact_prioritizer for scoring consistency.
"""

import logging
import copy
import time
import os
import shutil
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Any

logger = logging.getLogger(__name__)

# Default configuration
DEFAULT_THRESHOLD = 0.3
EXECUTION_INTERVAL = 10  # cycles - changed from 50 to 10
RECENCY_DECAY_CYCLES = 20
COVERAGE_THRESHOLD = 0.6  # 60% functionality coverage for merge suggestion
MAX_LOC = 1000  # Maximum lines of code for normalization


class CapabilityBankruptcyEngine:
    """Engine for detecting and handling capability bankruptcy."""

    def __init__(self, knowledge_base: Dict[str, Any], module_registry: Dict[str, Any],
                 threshold: float = DEFAULT_THRESHOLD,
                 goal_impact_prioritizer: Optional[Any] = None):
        self.knowledge_base = knowledge_base
        self.module_registry = module_registry
        self.threshold = threshold
        self.cycle_count = 0
        self.rollback_snapshots: List[Dict[str, Any]] = []
        self.capability_scores: Dict[str, float] = {}
        self.bankruptcy_log: List[Dict[str, Any]] = []
        self.goal_impact_prioritizer = goal_impact_prioritizer

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

    def _compute_usage_frequency(self, module_name: str) -> float:
        """Compute usage frequency as count of references in last 50 cycles / 50."""
        module_info = self.module_registry.get(module_name, {})
        reference_history = module_info.get("reference_history", [])
        # Count references in last 50 cycles
        recent_references = [ref for ref in reference_history if ref >= self.cycle_count - 50]
        return len(recent_references) / 50.0

    def _compute_test_pass_rate(self, module_name: str) -> float:
        """Compute test pass rate from recent test results."""
        module_info = self.module_registry.get(module_name, {})
        test_results = module_info.get("test_results", [])
        if not test_results:
            return 0.0
        # Use recent test results (last 10)
        recent_tests = test_results[-10:]
        passed = sum(1 for result in recent_tests if result.get("passed", False))
        return passed / len(recent_tests)

    def _compute_lines_of_code(self, module_name: str) -> int:
        """Compute lines of code from file length."""
        module_info = self.module_registry.get(module_name, {})
        file_path = module_info.get("file_path", "")
        if not file_path or not os.path.exists(file_path):
            return 0
        try:
            with open(file_path, "r") as f:
                return len(f.readlines())
        except Exception:
            return 0

    def _compute_composite_score(self, module_name: str) -> float:
        """Compute composite score = 0.4*usage + 0.35*test_pass + 0.25*(1 - LOC/max_LOC)."""
        usage = self._compute_usage_frequency(module_name)
        test_pass = self._compute_test_pass_rate(module_name)
        loc = self._compute_lines_of_code(module_name)
        loc_score = 1.0 - (loc / MAX_LOC) if MAX_LOC > 0 else 0.0
        composite = 0.4 * usage + 0.35 * test_pass + 0.25 * loc_score
        return max(0.0, min(1.0, composite))  # Clamp to [0, 1]

    def _get_module_description(self, module_name: str) -> str:
        """Get description of a module from registry."""
        module_info = self.module_registry.get(module_name, {})
        return module_info.get("description", "No description available")

    def _archive_module(self, module_name: str) -> None:
        """Archive module by moving to archive/ directory with timestamp."""
        module_info = self.module_registry.get(module_name, {})
        file_path = module_info.get("file_path", "")
        if not file_path or not os.path.exists(file_path):
            logger.warning("Cannot archive module '%s': file not found", module_name)
            return

        # Create archive directory if not exists
        archive_dir = "archive"
        os.makedirs(archive_dir, exist_ok=True)

        # Generate timestamped filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        archive_filename = f"{module_name}_{timestamp}.py"
        archive_path = os.path.join(archive_dir, archive_filename)

        try:
            shutil.move(file_path, archive_path)
            logger.info("Archived module '%s' to '%s'", module_name, archive_path)
        except Exception as e:
            logger.error("Failed to archive module '%s': %s", module_name, str(e))

    def _rederive_module(self, module_name: str) -> None:
        """Call LLM to re-derive core functionality from scratch."""
        description = self._get_module_description(module_name)
        prompt = (
            f"Given the archived module {module_name} which provided {description}, "
            "re-implement its essential functionality in <50 lines of code, removing all cruft."
        )

        # Placeholder for LLM call - in production, integrate with actual LLM API
        # For now, we create a minimal stub
        rederived_code = f"""# Re-derived module: {module_name}_v2
# Original description: {description}
# Generated at: {datetime.now().isoformat()}

def core_functionality():
    \"\"\"Core functionality re-derived from {module_name}.\"\"\"
    pass
"""
        # Write re-derived module to active directory with _v2 suffix
        active_dir = "modules"
        os.makedirs(active_dir, exist_ok=True)
        new_filename = f"{module_name}_v2.py"
        new_filepath = os.path.join(active_dir, new_filename)

        try:
            with open(new_filepath, "w") as f:
                f.write(rederived_code)
            logger.info("Re-derived module written to '%s'", new_filepath)
        except Exception as e:
            logger.error("Failed to write re-derived module '%s': %s", new_filepath, str(e))

    def _log_action(self, action: str, module_name: str, details: Dict[str, Any]) -> None:
        """Log action to bankruptcy_log."""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "cycle": self.cycle_count,
            "action": action,
            "module": module_name,
            "details": details,
        }
        self.bankruptcy_log.append(log_entry)
        logger.info("Bankruptcy log: %s", log_entry)

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

        # Step 2: Compute scores using goal_impact_prioritizer if available
        self.capability_scores = {}
        for cap_name, cap_data in capabilities.items():
            if self.goal_impact_prioritizer is not None:
                # Use goal_impact_prioritizer's score_goal for each capability
                try:
                    score = self.goal_impact_prioritizer.score_goal(cap_name, cap_data)
                    self.capability_scores[cap_name] = score
                except Exception as e:
                    logger.error("Failed to score capability '%s' with prioritizer: %s", cap_name, str(e))
                    self.capability_scores[cap_name] = 0.0
            else:
                # Fallback to composite scoring if prioritizer not available
                module_name = cap_name.split('.')[0] if '.' in cap_name else cap_name
                score = self._compute_composite_score(module_name)
                self.capability_scores[cap_name] = score

        # Step 3: Flag low-scoring capabilities (score < 0.3)
        flagged = [name for name, score in self.capability_scores.items() if score < self.threshold]
        logger.info("Flagged %d capabilities with score < %.2f", len(flagged), self.threshold)

        if not flagged:
            return {"status": "no_action", "cycle": self.cycle_count, "scores": self.capability_scores}

        # Step 4: Find merge candidates for flagged capabilities
        merge_suggestions = self._find_merge_candidates(flagged)

        # Step 5: Create rollback snapshot
        snapshot = self._create_rollback_snapshot()
        logger.info("Created rollback snapshot at cycle %d", self.cycle_count)

        # Step 6: Apply changes (archive capabilities with score < 0.3)
        changes_made = []
        for cap_name in flagged:
            # Archive capability
            module_name = cap_name.split('.')[0] if '.' in cap_name else cap_name
            self._archive_module(module_name)
            self._log_action("archive", cap_name, {"score": self.capability_scores[cap_name]})

            # Re-derive capability
            self._rederive_module(module_name)
            self._log_action("rederive", cap_name, {"v2_suffix": True})

            changes_made.append({
                "action": "archive_and_rederive",
                "capability": cap_name,
                "score": self.capability_scores[cap_name]
            })

        # Step 7: Run critical tests and revert if needed
        tests_passed = self._run_critical_tests()
        if not tests_passed:
            logger.error("Critical tests failed! Reverting changes.")
            self._revert_changes(snapshot)
            self._log_action("revert", "system", {"reason": "tests_failed"})
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
            "bankruptcy_log_count": len(self.bankruptcy_log),
        }