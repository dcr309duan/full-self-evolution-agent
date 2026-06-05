from typing import Dict, List, Optional, Set
import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
import json
import hashlib
import time

logger = logging.getLogger(__name__)

class GoalType(Enum):
    REGULAR = "regular"
    CURIOSITY = "curiosity"

@dataclass
class Goal:
    id: str
    description: str
    goal_type: GoalType = GoalType.REGULAR
    priority: int = 0
    completed: bool = False
    created_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None
    sandbox_test_results: int = 0  # Track sandbox test failures

@dataclass
class StructuralDiff:
    new_files: List[str] = field(default_factory=list)
    modified_interfaces: List[str] = field(default_factory=list)
    added_dependencies: List[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)

class GoalManager:
    """
    Manages goals with support for curiosity tasks.
    Curiosity tasks are identified by a special prefix 'curiosity:' in the goal ID
    or by a dedicated flag. They are prioritized over regular evolution goals.
    After completing a curiosity task, a structural diff is automatically triggered.
    """

    CURIOSITY_PREFIX = "curiosity:"
    CURIOSITY_PRIORITY_BOOST = 1000
    SANDBOX_FAILURE_PENALTY = 100  # Priority reduction per sandbox failure

    def __init__(self, codebase_path: Optional[Path] = None):
        self.goals: List[Goal] = []
        self.completed_goals: List[Goal] = []
        self.structural_diffs: List[StructuralDiff] = []
        self.codebase_path = codebase_path or Path.cwd()
        self._codebase_snapshot: Dict[str, str] = {}

    def add_goal(self, goal_id: str, description: str, goal_type: Optional[GoalType] = None) -> Goal:
        """
        Add a new goal. If goal_type is not provided, it is inferred from the goal ID prefix.
        """
        if goal_type is None:
            goal_type = self._infer_goal_type(goal_id)

        priority = 0
        if goal_type == GoalType.CURIOSITY:
            priority = self.CURIOSITY_PRIORITY_BOOST

        goal = Goal(
            id=goal_id,
            description=description,
            goal_type=goal_type,
            priority=priority
        )
        self.goals.append(goal)
        logger.info(f"Added goal: {goal_id} (type={goal_type.value}, priority={priority})")
        return goal

    def _infer_goal_type(self, goal_id: str) -> GoalType:
        """Infer goal type from ID prefix."""
        if goal_id.lower().startswith(self.CURIOSITY_PREFIX):
            return GoalType.CURIOSITY
        return GoalType.REGULAR

    def get_next_goal(self) -> Optional[Goal]:
        """
        Get the highest priority incomplete goal.
        Curiosity tasks are prioritized over regular goals.
        Goals with sandbox test failures are deprioritized.
        """
        incomplete = [g for g in self.goals if not g.completed]
        if not incomplete:
            return None

        # Sort by effective priority (base priority minus sandbox failure penalty)
        incomplete.sort(key=lambda g: g.priority - (g.sandbox_test_results * self.SANDBOX_FAILURE_PENALTY), reverse=True)
        return incomplete[0]

    def record_sandbox_failure(self, goal_id: str) -> bool:
        """
        Record a sandbox test failure for a goal.
        Returns True if the goal was found and updated, False otherwise.
        """
        for goal in self.goals:
            if goal.id == goal_id and not goal.completed:
                goal.sandbox_test_results += 1
                logger.info(f"Recorded sandbox failure for goal: {goal_id} (total failures: {goal.sandbox_test_results})")
                return True
        logger.warning(f"Goal not found or already completed: {goal_id}")
        return False

    def get_sandbox_failure_count(self, goal_id: str) -> Optional[int]:
        """Get the number of sandbox test failures for a goal."""
        for goal in self.goals:
            if goal.id == goal_id:
                return goal.sandbox_test_results
        return None

    def complete_goal(self, goal_id: str) -> Optional[StructuralDiff]:
        """
        Mark a goal as completed. If it's a curiosity task, trigger a structural diff.
        Returns the StructuralDiff if one was generated, otherwise None.
        """
        for goal in self.goals:
            if goal.id == goal_id and not goal.completed:
                goal.completed = True
                goal.completed_at = time.time()
                self.completed_goals.append(goal)
                logger.info(f"Completed goal: {goal_id}")

                if goal.goal_type == GoalType.CURIOSITY:
                    diff = self._perform_structural_diff()
                    self.structural_diffs.append(diff)
                    logger.info(f"Structural diff generated for curiosity task: {goal_id}")
                    return diff
                return None
        logger.warning(f"Goal not found or already completed: {goal_id}")
        return None

    def _perform_structural_diff(self) -> StructuralDiff:
        """
        Compare the current codebase state with the last snapshot.
        Identifies new files, modified interfaces, and added dependencies.
        """
        current_snapshot = self._take_codebase_snapshot()
        diff = StructuralDiff()

        if not self._codebase_snapshot:
            # First snapshot, no diff possible
            self._codebase_snapshot = current_snapshot
            return diff

        # Detect new files
        new_files = set(current_snapshot.keys()) - set(self._codebase_snapshot.keys())
        diff.new_files = sorted(new_files)

        # Detect modified interfaces (files that changed content)
        common_files = set(current_snapshot.keys()) & set(self._codebase_snapshot.keys())
        for filepath in common_files:
            if current_snapshot[filepath] != self._codebase_snapshot[filepath]:
                diff.modified_interfaces.append(filepath)
        diff.modified_interfaces.sort()

        # Detect added dependencies (simplified: look for new import statements)
        diff.added_dependencies = self._detect_new_dependencies(current_snapshot)

        # Update snapshot
        self._codebase_snapshot = current_snapshot

        logger.info(f"Structural diff: {len(diff.new_files)} new files, "
                    f"{len(diff.modified_interfaces)} modified interfaces, "
                    f"{len(diff.added_dependencies)} new dependencies")
        return diff

    def _take_codebase_snapshot(self) -> Dict[str, str]:
        """
        Take a snapshot of the current codebase, returning a dict of filepath -> content hash.
        Only considers Python files and common config files.
        """
        snapshot = {}
        extensions = {'.py', '.json', '.yaml', '.yml', '.toml', '.cfg', '.ini', '.txt', '.md'}

        for filepath in self.codebase_path.rglob('*'):
            if filepath.is_file() and filepath.suffix in extensions:
                # Skip __pycache__ and hidden directories
                if any(part.startswith('__') or part.startswith('.') for part in filepath.parts):
                    continue
                try:
                    content = filepath.read_text(encoding='utf-8', errors='ignore')
                    snapshot[str(filepath.relative_to(self.codebase_path))] = hashlib.sha256(content.encode()).hexdigest()
                except Exception as e:
                    logger.warning(f"Could not read file {filepath}: {e}")
        return snapshot

    def _detect_new_dependencies(self, current_snapshot: Dict[str, str]) -> List[str]:
        """
        Detect new dependencies by comparing import statements in current vs previous snapshot.
        This is a simplified implementation.
        """
        # For simplicity, we'll just scan all Python files for import statements
        # and compare with a stored set of known dependencies.
        # In a real implementation, you'd use AST parsing.
        current_imports = set()
        for filepath_str in current_snapshot.keys():
            if filepath_str.endswith('.py'):
                filepath = self.codebase_path / filepath_str
                try:
                    content = filepath.read_text(encoding='utf-8', errors='ignore')
                    for line in content.splitlines():
                        line = line.strip()
                        if line.startswith('import ') or line.startswith('from '):
                            # Extract the module name
                            parts = line.split()
                            if len(parts) >= 2:
                                current_imports.add(parts[1].split('.')[0])
                except Exception:
                    continue

        # Compare with previous imports (stored in a simple attribute)
        if not hasattr(self, '_previous_imports'):
            self._previous_imports = current_imports
            return []

        new_imports = current_imports - self._previous_imports
        self._previous_imports = current_imports
        return sorted(new_imports)

    def get_goals_by_type(self, goal_type: GoalType) -> List[Goal]:
        """Get all goals of a specific type."""
        return [g for g in self.goals if g.goal_type == goal_type]

    def get_statistics(self) -> Dict:
        """Get statistics about goals and diffs."""
        total = len(self.goals)
        completed = len(self.completed_goals)
        curiosity = len(self.get_goals_by_type(GoalType.CURIOSITY))
        curiosity_completed = len([g for g in self.completed_goals if g.goal_type == GoalType.CURIOSITY])
        total_sandbox_failures = sum(g.sandbox_test_results for g in self.goals)
        return {
            "total_goals": total,
            "completed_goals": completed,
            "curiosity_goals": curiosity,
            "curiosity_completed": curiosity_completed,
            "structural_diffs": len(self.structural_diffs),
            "pending_goals": total - completed,
            "total_sandbox_failures": total_sandbox_failures
        }

    def clear_completed_goals(self) -> int:
        """Remove all completed goals from the active list. Returns count removed."""
        count = len(self.completed_goals)
        self.goals = [g for g in self.goals if not g.completed]
        self.completed_goals = []
        return count

    def reset(self) -> None:
        """Reset the goal manager to initial state."""
        self.goals.clear()
        self.completed_goals.clear()
        self.structural_diffs.clear()
        self._codebase_snapshot.clear()
        if hasattr(self, '_previous_imports'):
            del self._previous_imports
        logger.info("Goal manager reset")