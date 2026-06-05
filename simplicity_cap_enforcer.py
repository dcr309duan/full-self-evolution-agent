import os
import logging
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

CORE_MODULES = [
    "evolution_orchestrator.py",
    "goal_generator.py",
    "mutation_engine.py",
    "meta_cognitive_evaluator.py",
    "self_diagnosis_module.py",
    "dependency_graph.py"
]

class SimplicityCapEnforcer:
    def __init__(self, baseline: Optional[Dict[str, int]] = None):
        self.baseline: Dict[str, int] = baseline or {}
        self.current_total: int = 0
        self.previous_total: int = 0
        self.consolidation_required: bool = False
        self.complexity_debt_log: List[Dict] = []
        self._load_baseline()

    def _load_baseline(self) -> None:
        """Initialize baseline from existing files if not provided."""
        if not self.baseline:
            for module in CORE_MODULES:
                loc = self._count_lines(module)
                self.baseline[module] = loc
        self._update_totals()

    def _count_lines(self, filepath: str) -> int:
        """Count non-empty, non-comment lines in a Python file."""
        try:
            with open(filepath, 'r') as f:
                lines = f.readlines()
            count = 0
            for line in lines:
                stripped = line.strip()
                if stripped and not stripped.startswith('#'):
                    count += 1
            return count
        except FileNotFoundError:
            logger.warning(f"File {filepath} not found, assuming 0 lines.")
            return 0

    def _update_totals(self) -> None:
        """Recalculate total LOC across all core modules."""
        self.previous_total = self.current_total
        self.current_total = sum(self.baseline.values())

    def get_current_totals(self) -> Dict[str, int]:
        """Return current LOC counts for each core module."""
        totals = {}
        for module in CORE_MODULES:
            totals[module] = self._count_lines(module)
        return totals

    def check_mutation_impact(self) -> bool:
        """
        After mutation, recalculate total LOC and check if threshold exceeded.
        Returns True if mutation is safe, False if rollback needed.
        """
        new_totals = self.get_current_totals()
        new_total = sum(new_totals.values())
        self.current_total = new_total

        if self.previous_total == 0:
            # First run, no previous baseline to compare
            self.baseline = new_totals
            self._update_totals()
            return True

        increase_ratio = (new_total - self.previous_total) / self.previous_total
        threshold = 0.05  # 5%

        if increase_ratio > threshold:
            self._log_complexity_debt(new_total, increase_ratio)
            logger.warning(f"Complexity cap exceeded: {increase_ratio*100:.2f}% increase. Rollback required.")
            self.consolidation_required = True
            return False
        else:
            # Update baseline with new counts
            self.baseline = new_totals
            self._update_totals()
            # Set consolidation flag if approaching limit
            if increase_ratio > 0.04:  # 4% threshold for warning
                self.consolidation_required = True
            else:
                self.consolidation_required = False
            return True

    def _log_complexity_debt(self, new_total: int, increase_ratio: float) -> None:
        """Log a complexity debt entry."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "previous_total": self.previous_total,
            "new_total": new_total,
            "increase_ratio": increase_ratio,
            "modules_affected": self._get_affected_modules()
        }
        self.complexity_debt_log.append(entry)
        logger.info(f"Complexity debt logged: {entry}")

    def _get_affected_modules(self) -> List[str]:
        """Identify which modules changed LOC from baseline."""
        affected = []
        for module in CORE_MODULES:
            current = self._count_lines(module)
            if current != self.baseline.get(module, 0):
                affected.append(module)
        return affected

    def rollback_mutation(self, backup_path: str = None) -> None:
        """
        Rollback the last mutation by restoring from backup.
        Placeholder implementation - actual rollback depends on version control.
        """
        logger.warning("Rollback triggered. Restoring previous state.")
        # In a real implementation, this would restore files from backup
        # For now, we just reset the baseline to previous state
        if self.complexity_debt_log:
            last_debt = self.complexity_debt_log[-1]
            # Reset baseline to previous totals (approximation)
            # Actual rollback would restore file contents
            logger.info(f"Rolling back to previous total: {last_debt['previous_total']}")

    def get_consolidation_status(self) -> Dict:
        """Return current consolidation status."""
        return {
            "consolidation_required": self.consolidation_required,
            "current_total": self.current_total,
            "previous_total": self.previous_total,
            "baseline": self.baseline,
            "debt_log_count": len(self.complexity_debt_log)
        }

# Module-level singleton for easy import
_enforcer = None

def get_enforcer() -> SimplicityCapEnforcer:
    """Get or create the singleton enforcer instance."""
    global _enforcer
    if _enforcer is None:
        _enforcer = SimplicityCapEnforcer()
    return _enforcer

def check_complexity_cap() -> bool:
    """Convenience function to check if current mutation is within cap."""
    enforcer = get_enforcer()
    return enforcer.check_mutation_impact()

def is_consolidation_required() -> bool:
    """Check if consolidation is needed based on current state."""
    enforcer = get_enforcer()
    return enforcer.consolidation_required

def log_complexity_debt() -> None:
    """Force log a complexity debt entry for current state."""
    enforcer = get_enforcer()
    enforcer._log_complexity_debt(enforcer.current_total, 0.0)  # Placeholder ratio