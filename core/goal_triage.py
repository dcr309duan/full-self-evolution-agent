"""Goal Triage Module

Scans pending and in-progress goals, checks for stalled goals (no progress for 3+ consecutive generations),
and either breaks them into sub-goals or archives them with lessons learned.
Also monitors triage effectiveness by tracking incorrectly archived goals and sub-goal success rates.
"""

import logging
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
from enum import Enum

from core.goal_registry import GoalRegistry, Goal, GoalStatus
from core.knowledge_base import KnowledgeBase
from core.goal_breaker import GoalBreaker

logger = logging.getLogger(__name__)

# Number of consecutive generations without progress before flagging
STALL_THRESHOLD = 3


class TriageAction(Enum):
    """Possible actions resulting from triage."""
    BREAK_INTO_SUBGOALS = "break_into_subgoals"
    ARCHIVE_WITH_LESSON = "archive_with_lesson"
    NO_ACTION = "no_action"


class TriageResult:
    """Result of triaging a single goal."""

    def __init__(self, goal_id: str, action: TriageAction, details: str = ""):
        self.goal_id = goal_id
        self.action = action
        self.details = details
        self.timestamp = datetime.utcnow()

    def to_dict(self) -> Dict:
        return {
            "goal_id": self.goal_id,
            "action": self.action.value,
            "details": self.details,
            "timestamp": self.timestamp.isoformat()
        }


class GoalTriage:
    """Handles triage of stalled goals and monitors triage effectiveness."""

    def __init__(self, goal_registry: GoalRegistry, knowledge_base: KnowledgeBase, goal_breaker: GoalBreaker):
        self.goal_registry = goal_registry
        self.knowledge_base = knowledge_base
        self.goal_breaker = goal_breaker
        # Metrics for triage effectiveness monitoring
        self.incorrectly_archived_count = 0
        self.subgoal_success_count = 0
        self.subgoal_total_count = 0

    def run_triage(self, current_generation: int) -> List[TriageResult]:
        """Run triage on all pending and in-progress goals.

        Args:
            current_generation: The current generation number.

        Returns:
            List of TriageResult for each flagged goal.
        """
        results = []
        goals = self.goal_registry.get_goals_by_status([GoalStatus.PENDING, GoalStatus.IN_PROGRESS])

        for goal in goals:
            result = self._triage_goal(goal, current_generation)
            if result.action != TriageAction.NO_ACTION:
                results.append(result)

        # Log triage effectiveness metrics to knowledge base
        self._log_triage_metrics()

        return results

    def _triage_goal(self, goal: Goal, current_generation: int) -> TriageResult:
        """Triage a single goal.

        Args:
            goal: The goal to triage.
            current_generation: The current generation number.

        Returns:
            TriageResult indicating the action taken.
        """
        # Check if goal has been stalled (no progress for STALL_THRESHOLD consecutive generations)
        if not self._is_stalled(goal, current_generation):
            return TriageResult(goal.id, TriageAction.NO_ACTION)

        # Determine if goal can be broken into sub-goals
        if self._can_break_into_subgoals(goal):
            return self._break_goal(goal)
        else:
            return self._archive_goal(goal)

    def _is_stalled(self, goal: Goal, current_generation: int) -> bool:
        """Check if a goal has been stalled for STALL_THRESHOLD consecutive generations.

        Args:
            goal: The goal to check.
            current_generation: The current generation number.

        Returns:
            True if stalled, False otherwise.
        """
        # Check progress tracking fields
        progress_indicator = getattr(goal, 'progress_indicator', None)
        last_progress_update = getattr(goal, 'last_progress_update', None)
        
        # If progress tracking fields exist, use them
        if progress_indicator is not None and last_progress_update is not None:
            # Check if we have a history of progress indicators
            progress_history = getattr(goal, 'progress_history', [])
            if progress_history:
                # Count consecutive 'no_change' entries
                consecutive_no_change = 0
                for entry in reversed(progress_history):
                    if entry.get('indicator') == 'no_change':
                        consecutive_no_change += 1
                    else:
                        break
                return consecutive_no_change >= STALL_THRESHOLD
            else:
                # If no history, fall back to generation-based check
                last_active = getattr(goal, 'last_active_generation', None)
                if last_active is None:
                    return False
                generations_since_active = current_generation - last_active
                return generations_since_active >= STALL_THRESHOLD
        
        # Fall back to generation-based check if progress tracking fields are not set
        last_active = getattr(goal, 'last_active_generation', None)
        if last_active is None:
            return False

        generations_since_active = current_generation - last_active
        return generations_since_active >= STALL_THRESHOLD

    def _can_break_into_subgoals(self, goal: Goal) -> bool:
        """Determine if a goal can be broken into smaller sub-goals.

        Args:
            goal: The goal to evaluate.

        Returns:
            True if breaking is feasible, False otherwise.
        """
        # Check if goal is complex enough to break
        if not goal.description or len(goal.description) < 50:
            return False

        # Check if goal has dependencies that can be split
        if hasattr(goal, 'dependencies') and goal.dependencies:
            return True

        # Check if goal has multiple distinct objectives
        if 'and' in goal.description.lower() or ',' in goal.description:
            return True

        return False

    def _break_goal(self, goal: Goal) -> TriageResult:
        """Break a stalled goal into smaller sub-goals.

        Args:
            goal: The goal to break.

        Returns:
            TriageResult with BREAK_INTO_SUBGOALS action.
        """
        try:
            sub_goals = self.goal_breaker.break_goal(goal)
            if sub_goals:
                # Archive the original goal
                self.goal_registry.archive_goal(goal.id)

                # Add sub-goals to registry
                for sub_goal in sub_goals:
                    self.goal_registry.add_goal(sub_goal)
                    # Track sub-goals for success monitoring
                    self.subgoal_total_count += 1

                details = f"Broken into {len(sub_goals)} sub-goals: {', '.join(sg.id for sg in sub_goals)}"
                logger.info(f"Goal {goal.id} broken into sub-goals: {details}")
                return TriageResult(goal.id, TriageAction.BREAK_INTO_SUBGOALS, details)
            else:
                # If breaking fails, fall back to archive
                return self._archive_goal(goal)
        except Exception as e:
            logger.error(f"Failed to break goal {goal.id}: {e}")
            return self._archive_goal(goal)

    def _archive_goal(self, goal: Goal) -> TriageResult:
        """Archive a stalled goal and record a lesson in the knowledge base.

        Args:
            goal: The goal to archive.

        Returns:
            TriageResult with ARCHIVE_WITH_LESSON action.
        """
        try:
            # Record lesson in knowledge base
            lesson = self._generate_lesson(goal)
            self.knowledge_base.add_entry(
                title=f"Lesson from archived goal: {goal.title}",
                content=lesson,
                tags=["goal_triage", "archived_goal", "lesson_learned"]
            )

            # Archive the goal
            self.goal_registry.archive_goal(goal.id)

            details = f"Archived with lesson recorded in knowledge base"
            logger.info(f"Goal {goal.id} archived: {details}")
            return TriageResult(goal.id, TriageAction.ARCHIVE_WITH_LESSON, details)
        except Exception as e:
            logger.error(f"Failed to archive goal {goal.id}: {e}")
            return TriageResult(goal.id, TriageAction.ARCHIVE_WITH_LESSON, f"Archive failed: {e}")

    def _generate_lesson(self, goal: Goal) -> str:
        """Generate a lesson learned from a stalled goal.

        Args:
            goal: The stalled goal.

        Returns:
            A string containing the lesson.
        """
        progress_indicator = getattr(goal, 'progress_indicator', 'unknown')
        last_progress_update = getattr(goal, 'last_progress_update', 'unknown')
        progress_history = getattr(goal, 'progress_history', [])
        
        lesson_parts = [
            f"Goal: {goal.title}",
            f"Description: {goal.description}",
            f"Status: {goal.status.value}",
            f"Last active generation: {getattr(goal, 'last_active_generation', 'unknown')}",
            f"Last progress indicator: {progress_indicator}",
            f"Last progress update: {last_progress_update}",
            f"Progress history: {progress_history}",
            "",
            "Lesson: This goal was archived due to no progress for 3+ consecutive generations.",
            "Possible reasons for stalling:",
            "- Goal may have been too ambitious or vague.",
            "- Dependencies may have been unclear or missing.",
            "- Resources or context may have been insufficient.",
            "",
            "Recommendation for future similar goals:",
            "- Break down large goals into smaller, actionable steps.",
            "- Ensure clear dependencies and prerequisites are defined.",
            "- Set realistic timelines and checkpoints.",
            "- Regularly update progress indicators to track advancement.",
        ]
        return "\n".join(lesson_parts)

    def record_goal_unarchived(self, goal_id: str) -> None:
        """Record that an archived goal was later unarchived (incorrectly archived).

        Args:
            goal_id: The ID of the goal that was unarchived.
        """
        self.incorrectly_archived_count += 1
        logger.warning(f"Goal {goal_id} was incorrectly archived and has been unarchived.")

    def record_subgoal_completed(self, subgoal_id: str) -> None:
        """Record that a sub-goal was successfully completed.

        Args:
            subgoal_id: The ID of the completed sub-goal.
        """
        self.subgoal_success_count += 1
        logger.info(f"Sub-goal {subgoal_id} completed successfully.")

    def _log_triage_metrics(self) -> None:
        """Log triage effectiveness metrics to the knowledge base for self-improvement."""
        metrics = {
            "incorrectly_archived_count": self.incorrectly_archived_count,
            "subgoal_success_count": self.subgoal_success_count,
            "subgoal_total_count": self.subgoal_total_count,
            "subgoal_success_rate": (self.subgoal_success_count / self.subgoal_total_count * 100) if self.subgoal_total_count > 0 else 0.0,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Create a detailed log entry
        log_content = (
            f"Triage Effectiveness Metrics:\n"
            f"- Incorrectly archived goals: {self.incorrectly_archived_count}\n"
            f"- Sub-goals completed successfully: {self.subgoal_success_count}\n"
            f"- Total sub-goals created: {self.subgoal_total_count}\n"
            f"- Sub-goal success rate: {metrics['subgoal_success_rate']:.2f}%\n\n"
            f"Self-improvement insights:\n"
            f"- If incorrectly archived count is high, consider adjusting the stall threshold or improving goal evaluation criteria.\n"
            f"- If sub-goal success rate is low, review the goal-breaking strategy and ensure sub-goals are actionable.\n"
        )
        
        self.knowledge_base.add_entry(
            title="Triage Effectiveness Metrics",
            content=log_content,
            tags=["goal_triage", "effectiveness_monitor", "metrics", "self_improvement"]
        )
        
        logger.info(f"Triage effectiveness metrics logged to knowledge base: {metrics}")