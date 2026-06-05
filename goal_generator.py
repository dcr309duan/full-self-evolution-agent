"""
goal_generator.py - Integrates ReflectionParser into the goal generation pipeline.

After each reflection cycle, this module:
1. Parses the latest reflection text using ReflectionParser.
2. Updates current_assessment with parsed context.
3. Prioritizes goals that address identified key_gaps.
4. Sets next_priority as the primary goal.
5. Injects novel_ideas as experimental goal variants.
6. Tracks feedback on how parsed reflections influence goal selection success.
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
import json
import logging
from datetime import datetime

# Assuming ReflectionParser is defined elsewhere; adjust import as needed.
# For demonstration, we define a minimal ReflectionParser here.
# In practice, replace with actual import: from reflection_parser import ReflectionParser
class ReflectionParser:
    """Mock ReflectionParser for demonstration. Replace with actual implementation."""
    def parse(self, reflection_text: str) -> Dict[str, Any]:
        """Parse reflection text and return structured output."""
        # Placeholder: in real implementation, this would use NLP/LLM parsing.
        return {
            "current_assessment": {"mood": "neutral", "progress": "moderate"},
            "key_gaps": ["lack of focus", "time management"],
            "next_priority": "improve focus",
            "novel_ideas": ["pomodoro technique", "deep work blocks"]
        }

@dataclass
class Goal:
    """Represents a single goal with metadata."""
    description: str
    priority: int  # Lower number = higher priority
    source: str  # e.g., "parsed", "experimental", "manual"
    success_count: int = 0
    failure_count: int = 0
    last_selected: Optional[datetime] = None

    def success_rate(self) -> float:
        total = self.success_count + self.failure_count
        return self.success_count / total if total > 0 else 0.0

class GoalGenerator:
    """
    Integrates ReflectionParser into goal generation.
    Maintains a feedback loop tracking how parsed reflections influence goal selection.
    """

    def __init__(self, parser: Optional[ReflectionParser] = None):
        self.parser = parser or ReflectionParser()
        self.current_assessment: Dict[str, Any] = {}
        self.goals: List[Goal] = []
        self.experimental_goals: List[Goal] = []
        self.feedback_history: List[Dict[str, Any]] = []
        self.logger = logging.getLogger(__name__)

    def process_reflection(self, reflection_text: str) -> Dict[str, Any]:
        """
        Main entry point: parse reflection and update goal pipeline.
        Returns a summary of changes made.
        """
        parsed = self.parser.parse(reflection_text)
        self._update_assessment(parsed.get("current_assessment", {}))
        self._prioritize_goals(parsed.get("key_gaps", []))
        self._set_primary_goal(parsed.get("next_priority", ""))
        self._inject_experimental_goals(parsed.get("novel_ideas", []))
        summary = self._generate_summary(parsed)
        self._record_feedback(parsed, summary)
        return summary

    def _update_assessment(self, assessment: Dict[str, Any]) -> None:
        """Update current_assessment with parsed context."""
        self.current_assessment.update(assessment)
        self.logger.debug(f"Updated assessment: {self.current_assessment}")

    def _prioritize_goals(self, key_gaps: List[str]) -> None:
        """
        Prioritize existing goals that address key_gaps.
        Goals matching gaps get higher priority (lower number).
        """
        if not key_gaps:
            return

        for gap in key_gaps:
            gap_lower = gap.lower()
            for goal in self.goals:
                if gap_lower in goal.description.lower():
                    # Increase priority (lower number) for matching goals
                    goal.priority = max(1, goal.priority - 1)
                    self.logger.debug(f"Boosted priority for goal: {goal.description}")

        # Re-sort goals by priority
        self.goals.sort(key=lambda g: g.priority)

    def _set_primary_goal(self, next_priority: str) -> None:
        """
        Set next_priority as the primary goal.
        If it already exists, move to front; otherwise create new goal.
        """
        if not next_priority:
            return

        # Check if goal already exists
        existing = [g for g in self.goals if g.description.lower() == next_priority.lower()]
        if existing:
            existing[0].priority = 1
            self.goals.sort(key=lambda g: g.priority)
            self.logger.debug(f"Set existing goal as primary: {next_priority}")
        else:
            new_goal = Goal(
                description=next_priority,
                priority=1,
                source="parsed",
                last_selected=datetime.now()
            )
            self.goals.insert(0, new_goal)
            self.logger.debug(f"Created new primary goal: {next_priority}")

    def _inject_experimental_goals(self, novel_ideas: List[str]) -> None:
        """
        Inject novel_ideas as experimental goal variants.
        These are tracked separately and can be promoted to regular goals.
        """
        for idea in novel_ideas:
            if not any(g.description.lower() == idea.lower() for g in self.experimental_goals):
                exp_goal = Goal(
                    description=idea,
                    priority=999,  # Low priority initially
                    source="experimental",
                    last_selected=datetime.now()
                )
                self.experimental_goals.append(exp_goal)
                self.logger.debug(f"Injected experimental goal: {idea}")

    def promote_experimental_goal(self, description: str) -> bool:
        """
        Promote an experimental goal to a regular goal.
        Returns True if successful.
        """
        for exp_goal in self.experimental_goals:
            if exp_goal.description.lower() == description.lower():
                new_goal = Goal(
                    description=exp_goal.description,
                    priority=5,  # Moderate priority
                    source="promoted_experimental",
                    success_count=exp_goal.success_count,
                    failure_count=exp_goal.failure_count
                )
                self.goals.append(new_goal)
                self.experimental_goals.remove(exp_goal)
                self.logger.info(f"Promoted experimental goal: {description}")
                return True
        return False

    def select_goal(self) -> Optional[Goal]:
        """
        Select the highest priority goal for execution.
        Updates last_selected timestamp.
        """
        if not self.goals:
            return None

        # Consider experimental goals if they have high success rate
        best_exp = None
        for exp in self.experimental_goals:
            if exp.success_rate() > 0.7 and (best_exp is None or exp.success_rate() > best_exp.success_rate()):
                best_exp = exp

        # Select from regular goals first
        if self.goals:
            selected = self.goals[0]
            selected.last_selected = datetime.now()
            return selected
        elif best_exp:
            best_exp.last_selected = datetime.now()
            return best_exp
        return None

    def record_goal_outcome(self, goal: Goal, success: bool) -> None:
        """
        Record the outcome of a goal execution for feedback tracking.
        """
        if success:
            goal.success_count += 1
        else:
            goal.failure_count += 1

        # Update feedback history
        feedback_entry = {
            "timestamp": datetime.now().isoformat(),
            "goal_description": goal.description,
            "goal_source": goal.source,
            "success": success,
            "current_assessment": self.current_assessment.copy()
        }
        self.feedback_history.append(feedback_entry)
        self.logger.debug(f"Recorded outcome for goal '{goal.description}': {'success' if success else 'failure'}")

    def _generate_summary(self, parsed: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a summary of changes made during processing."""
        return {
            "timestamp": datetime.now().isoformat(),
            "assessment_updated": bool(parsed.get("current_assessment")),
            "goals_prioritized": len(parsed.get("key_gaps", [])),
            "primary_goal_set": bool(parsed.get("next_priority")),
            "experimental_goals_injected": len(parsed.get("novel_ideas", [])),
            "total_goals": len(self.goals),
            "total_experimental": len(self.experimental_goals)
        }

    def _record_feedback(self, parsed: Dict[str, Any], summary: Dict[str, Any]) -> None:
        """Record feedback for the feedback loop."""
        feedback = {
            "parsed_data": parsed,
            "summary": summary,
            "timestamp": datetime.now().isoformat()
        }
        self.feedback_history.append(feedback)
        self.logger.debug("Feedback recorded")

    def get_feedback_analysis(self) -> Dict[str, Any]:
        """
        Analyze feedback history to determine how parsed reflections influence goal success.
        Returns statistics and insights.
        """
        if not self.feedback_history:
            return {"message": "No feedback data available"}

        total_goals = len(self.goals) + len(self.experimental_goals)
        successful_goals = sum(1 for g in self.goals if g.success_count > 0)
        successful_exp = sum(1 for g in self.experimental_goals if g.success_count > 0)

        # Analyze correlation between parsed reflections and goal success
        parsed_sources = [g for g in self.goals if g.source == "parsed"]
        parsed_success_rate = sum(g.success_rate() for g in parsed_sources) / len(parsed_sources) if parsed_sources else 0

        experimental_success_rate = sum(g.success_rate() for g in self.experimental_goals) / len(self.experimental_goals) if self.experimental_goals else 0

        return {
            "total_goals": total_goals,
            "successful_goals": successful_goals + successful_exp,
            "parsed_goal_success_rate": round(parsed_success_rate, 2),
            "experimental_goal_success_rate": round(experimental_success_rate, 2),
            "feedback_entries": len(self.feedback_history),
            "current_assessment": self.current_assessment,
            "top_priority_goal": self.goals[0].description if self.goals else None
        }

    def get_goals(self) -> List[Goal]:
        """Return current list of regular goals."""
        return self.goals

    def get_experimental_goals(self) -> List[Goal]:
        """Return current list of experimental goals."""
        return self.experimental_goals

    def get_current_assessment(self) -> Dict[str, Any]:
        """Return current assessment context."""
        return self.current_assessment

# Example usage (commented out):
# if __name__ == "__main__":
#     logging.basicConfig(level=logging.INFO)
#     generator = GoalGenerator()
#     reflection = "I struggled with focus today. Key gaps: lack of focus, time management. Next priority: improve focus. Novel ideas: pomodoro technique, deep work blocks."
#     summary = generator.process_reflection(reflection)
#     print(json.dumps(summary, indent=2))
#     goal = generator.select_goal()
#     if goal:
#         print(f"Selected goal: {goal.description}")
#         generator.record_goal_outcome(goal, success=True)
#     analysis = generator.get_feedback_analysis()
#     print(json.dumps(analysis, indent=2))