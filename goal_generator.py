"""
goal_generator.py - Integrates ReflectionParser into the goal generation pipeline.

After each reflection cycle, this module:
1. Parses the latest reflection text using ReflectionParser.
2. Updates current_assessment with parsed context.
3. Prioritizes goals that address identified key_gaps.
4. Sets next_priority as the primary goal.
5. Injects novel_ideas as experimental goal variants.
6. Tracks feedback on how parsed reflections influence goal selection success.
7. Supports retry_generation mode for self-healing loops with focused sub-goals.
8. Generates alternative strategies using different approaches than original failed goals.
9. Integrates feasibility estimator to check goal viability before generation.
"""

from typing import Dict, List, Optional, Any, Tuple
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

class FailureType(Enum):
    """Enumeration of failure types for retry generation."""
    IMPLEMENTATION_BUG = "implementation_bug"
    DESIGN_LIMITATION = "design_limitation"
    UNKNOWN = "unknown"

class FeasibilityResult(Enum):
    """Enumeration of feasibility check results."""
    ALLOW = "allow"
    BLOCK = "block"
    ADJUST_COMPLEXITY = "adjust_complexity"

@dataclass
class Goal:
    """Represents a single goal with metadata."""
    description: str
    priority: int  # Lower number = higher priority
    source: str  # e.g., "parsed", "experimental", "manual", "retry", "alternative"
    success_count: int = 0
    failure_count: int = 0
    last_selected: Optional[datetime] = None
    failure_type: Optional[FailureType] = None  # Track failure type for retry
    original_goal: Optional[str] = None  # Reference to original goal for alternatives

    def success_rate(self) -> float:
        total = self.success_count + self.failure_count
        return self.success_count / total if total > 0 else 0.0

class FeasibilityEstimator:
    """
    Estimates the feasibility of a goal before generation.
    Returns a FeasibilityResult indicating whether to allow, block, or adjust complexity.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def estimate(self, goal_description: str, context: Dict[str, Any]) -> FeasibilityResult:
        """
        Estimate the feasibility of a goal.
        
        Args:
            goal_description: The goal to evaluate
            context: Current assessment context
            
        Returns:
            FeasibilityResult: ALLOW, BLOCK, or ADJUST_COMPLEXITY
        """
        # Simple heuristic-based feasibility estimation
        # In a real implementation, this would use more sophisticated analysis
        
        # Check for overly complex goals (many sub-steps or broad scope)
        complexity_indicators = [
            "all", "everything", "complete", "full", "entire",
            "multiple", "several", "many", "various", "numerous"
        ]
        
        # Check for resource-intensive goals
        resource_indicators = [
            "large", "massive", "extensive", "comprehensive",
            "complex", "difficult", "challenging", "ambitious"
        ]
        
        # Check for vague or poorly defined goals
        vague_indicators = [
            "improve", "enhance", "optimize", "streamline",
            "better", "more", "less", "some", "something"
        ]
        
        goal_lower = goal_description.lower()
        
        # Count indicators
        complexity_count = sum(1 for indicator in complexity_indicators if indicator in goal_lower)
        resource_count = sum(1 for indicator in resource_indicators if indicator in goal_lower)
        vague_count = sum(1 for indicator in vague_indicators if indicator in goal_lower)
        
        # Check context for feasibility signals
        mood = context.get("mood", "neutral")
        progress = context.get("progress", "moderate")
        
        # Decision logic
        if complexity_count >= 3 or resource_count >= 3:
            self.logger.info(f"Feasibility check BLOCK for '{goal_description}': too complex/resource-intensive")
            return FeasibilityResult.BLOCK
        elif complexity_count >= 2 or resource_count >= 2:
            self.logger.info(f"Feasibility check ADJUST_COMPLEXITY for '{goal_description}': moderately complex")
            return FeasibilityResult.ADJUST_COMPLEXITY
        elif vague_count >= 3 and mood in ["negative", "frustrated"]:
            self.logger.info(f"Feasibility check BLOCK for '{goal_description}': vague goal in negative mood")
            return FeasibilityResult.BLOCK
        elif vague_count >= 2 and progress == "low":
            self.logger.info(f"Feasibility check ADJUST_COMPLEXITY for '{goal_description}': vague goal with low progress")
            return FeasibilityResult.ADJUST_COMPLEXITY
        else:
            return FeasibilityResult.ALLOW

class GoalGenerator:
    """
    Integrates ReflectionParser into goal generation.
    Maintains a feedback loop tracking how parsed reflections influence goal selection.
    Supports retry_generation mode for self-healing loops.
    """

    def __init__(self, parser: Optional[ReflectionParser] = None, feasibility_check: bool = True):
        self.parser = parser or ReflectionParser()
        self.feasibility_estimator = FeasibilityEstimator()
        self.feasibility_check = feasibility_check
        self.current_assessment: Dict[str, Any] = {}
        self.goals: List[Goal] = []
        self.experimental_goals: List[Goal] = []
        self.feedback_history: List[Dict[str, Any]] = []
        self.retry_mode: bool = False
        self.failed_goals: List[Goal] = []  # Track failed goals for retry
        self.alternative_strategies: List[Goal] = []  # Track alternative strategies
        self.blocked_goals: List[Dict[str, Any]] = []  # Track blocked goals with reasons
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
            # Perform feasibility check before creating new goal
            if self.feasibility_check:
                feasibility_result = self.feasibility_estimator.estimate(next_priority, self.current_assessment)
                
                if feasibility_result == FeasibilityResult.BLOCK:
                    self.logger.info(f"Feasibility check blocked goal: '{next_priority}'")
                    self.blocked_goals.append({
                        "description": next_priority,
                        "reason": "Feasibility check blocked due to complexity or resource constraints",
                        "timestamp": datetime.now().isoformat()
                    })
                    return
                elif feasibility_result == FeasibilityResult.ADJUST_COMPLEXITY:
                    # Reduce goal scope by simplifying the description
                    simplified_goal = self._simplify_goal(next_priority)
                    self.logger.info(f"Feasibility check adjusted complexity: '{next_priority}' -> '{simplified_goal}'")
                    next_priority = simplified_goal
            
            new_goal = Goal(
                description=next_priority,
                priority=1,
                source="parsed",
                last_selected=datetime.now()
            )
            self.goals.insert(0, new_goal)
            self.logger.debug(f"Created new primary goal: {next_priority}")

    def _simplify_goal(self, goal_description: str) -> str:
        """
        Simplify a goal description by reducing scope.
        Removes complexity indicators and vague terms.
        """
        # Remove complexity indicators
        complexity_indicators = [
            "all ", "everything ", "complete ", "full ", "entire ",
            "multiple ", "several ", "many ", "various ", "numerous ",
            "large ", "massive ", "extensive ", "comprehensive ",
            "complex ", "difficult ", "challenging ", "ambitious "
        ]
        
        simplified = goal_description
        for indicator in complexity_indicators:
            simplified = simplified.replace(indicator, "")
        
        # Add scope reduction prefix if not already present
        if not any(prefix in simplified.lower() for prefix in ["simple ", "basic ", "initial ", "first step "]):
            simplified = f"Simple {simplified}"
        
        # Limit to first 50 characters to ensure focus
        if len(simplified) > 50:
            simplified = simplified[:50].rsplit(" ", 1)[0]
        
        return simplified.strip()

    def _inject_experimental_goals(self, novel_ideas: List[str]) -> None:
        """
        Inject novel_ideas as experimental goal variants.
        These are tracked separately and can be promoted to regular goals.
        """
        for idea in novel_ideas:
            if not any(g.description.lower() == idea.lower() for g in self.experimental_goals):
                # Perform feasibility check for experimental goals
                if self.feasibility_check:
                    feasibility_result = self.feasibility_estimator.estimate(idea, self.current_assessment)
                    
                    if feasibility_result == FeasibilityResult.BLOCK:
                        self.logger.info(f"Feasibility check blocked experimental goal: '{idea}'")
                        self.blocked_goals.append({
                            "description": idea,
                            "reason": "Feasibility check blocked experimental goal",
                            "timestamp": datetime.now().isoformat()
                        })
                        continue
                    elif feasibility_result == FeasibilityResult.ADJUST_COMPLEXITY:
                        idea = self._simplify_goal(idea)
                        self.logger.info(f"Feasibility check adjusted experimental goal complexity: '{idea}'")
                
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
                # Perform feasibility check before promoting
                if self.feasibility_check:
                    feasibility_result = self.feasibility_estimator.estimate(description, self.current_assessment)
                    
                    if feasibility_result == FeasibilityResult.BLOCK:
                        self.logger.info(f"Feasibility check blocked promotion of experimental goal: '{description}'")
                        self.blocked_goals.append({
                            "description": description,
                            "reason": "Feasibility check blocked promotion",
                            "timestamp": datetime.now().isoformat()
                        })
                        return False
                    elif feasibility_result == FeasibilityResult.ADJUST_COMPLEXITY:
                        description = self._simplify_goal(description)
                        self.logger.info(f"Feasibility check adjusted promoted goal complexity: '{description}'")
                
                new_goal = Goal(
                    description=description,
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

    def record_goal_outcome(self, goal: Goal, success: bool, failure_type: Optional[FailureType] = None) -> None:
        """
        Record the outcome of a goal execution for feedback tracking.
        Optionally specify failure type for retry generation.
        """
        if success:
            goal.success_count += 1
        else:
            goal.failure_count += 1
            if failure_type:
                goal.failure_type = failure_type
                self.failed_goals.append(goal)

        # Update feedback history
        feedback_entry = {
            "timestamp": datetime.now().isoformat(),
            "goal_description": goal.description,
            "goal_source": goal.source,
            "success": success,
            "failure_type": failure_type.value if failure_type else None,
            "current_assessment": self.current_assessment.copy()
        }
        self.feedback_history.append(feedback_entry)
        self.logger.debug(f"Recorded outcome for goal '{goal.description}': {'success' if success else 'failure'}")

    def enable_retry_mode(self, enabled: bool = True) -> None:
        """Enable or disable retry generation mode."""
        self.retry_mode = enabled
        self.logger.info(f"Retry mode {'enabled' if enabled else 'disabled'}")

    def generate_retry_goals(self, failed_goal: Goal) -> List[Goal]:
        """
        Generate smaller, more focused sub-goals for retry based on failure type.
        Returns a list of new retry goals.
        """
        if not self.retry_mode:
            self.logger.warning("Retry mode is not enabled")
            return []

        retry_goals = []
        failure_type = failed_goal.failure_type or FailureType.UNKNOWN

        if failure_type == FailureType.IMPLEMENTATION_BUG:
            # Generate focused sub-goals for implementation bugs
            sub_goals = [
                f"Debug and fix {failed_goal.description} - step 1: isolate the bug",
                f"Debug and fix {failed_goal.description} - step 2: implement fix",
                f"Debug and fix {failed_goal.description} - step 3: test the fix",
                f"Review code quality for {failed_goal.description}",
                f"Add unit tests for {failed_goal.description}"
            ]
        elif failure_type == FailureType.DESIGN_LIMITATION:
            # Generate focused sub-goals for design limitations
            sub_goals = [
                f"Redesign approach for {failed_goal.description} - phase 1: requirements analysis",
                f"Redesign approach for {failed_goal.description} - phase 2: prototype new design",
                f"Redesign approach for {failed_goal.description} - phase 3: validate with stakeholders",
                f"Research alternative architectures for {failed_goal.description}",
                f"Create design document for {failed_goal.description}"
            ]
        else:
            # Generic retry sub-goals for unknown failures
            sub_goals = [
                f"Analyze root cause of {failed_goal.description}",
                f"Create mitigation plan for {failed_goal.description}",
                f"Implement mitigation for {failed_goal.description}",
                f"Verify resolution of {failed_goal.description}"
            ]

        for i, sub_goal_desc in enumerate(sub_goals):
            # Perform feasibility check for each retry sub-goal
            if self.feasibility_check:
                feasibility_result = self.feasibility_estimator.estimate(sub_goal_desc, self.current_assessment)
                
                if feasibility_result == FeasibilityResult.BLOCK:
                    self.logger.info(f"Feasibility check blocked retry goal: '{sub_goal_desc}'")
                    self.blocked_goals.append({
                        "description": sub_goal_desc,
                        "reason": "Feasibility check blocked retry sub-goal",
                        "timestamp": datetime.now().isoformat()
                    })
                    continue
                elif feasibility_result == FeasibilityResult.ADJUST_COMPLEXITY:
                    sub_goal_desc = self._simplify_goal(sub_goal_desc)
                    self.logger.info(f"Feasibility check adjusted retry goal complexity: '{sub_goal_desc}'")
            
            retry_goal = Goal(
                description=sub_goal_desc,
                priority=i + 1,  # Sequential priority
                source="retry",
                last_selected=datetime.now(),
                failure_type=failure_type,
                original_goal=failed_goal.description
            )
            retry_goals.append(retry_goal)
            self.goals.append(retry_goal)
            self.logger.debug(f"Generated retry goal: {sub_goal_desc}")

        return retry_goals

    def generate_alternative_strategies(self, failed_goal: Goal, num_alternatives: int = 3) -> List[Goal]:
        """
        Generate alternative strategies that use different approaches than the original failed goal.
        Returns a list of alternative strategy goals.
        """
        if not self.retry_mode:
            self.logger.warning("Retry mode is not enabled for alternative strategies")
            return []

        alternative_goals = []
        failure_type = failed_goal.failure_type or FailureType.UNKNOWN

        # Generate alternative approaches based on failure type
        if failure_type == FailureType.IMPLEMENTATION_BUG:
            alternatives = [
                f"Alternative approach: Use library X instead of custom implementation for {failed_goal.description}",
                f"Alternative approach: Refactor {failed_goal.description} using design pattern Y",
                f"Alternative approach: Implement {failed_goal.description} with different algorithm",
                f"Alternative approach: Use third-party service for {failed_goal.description}",
                f"Alternative approach: Simplify {failed_goal.description} by reducing scope"
            ]
        elif failure_type == FailureType.DESIGN_LIMITATION:
            alternatives = [
                f"Alternative design: Use microservices architecture for {failed_goal.description}",
                f"Alternative design: Implement event-driven approach for {failed_goal.description}",
                f"Alternative design: Use caching layer for {failed_goal.description}",
                f"Alternative design: Adopt serverless architecture for {failed_goal.description}",
                f"Alternative design: Use message queue for {failed_goal.description}"
            ]
        else:
            alternatives = [
                f"Alternative approach: Try different methodology for {failed_goal.description}",
                f"Alternative approach: Use different tooling for {failed_goal.description}",
                f"Alternative approach: Collaborate with team on {failed_goal.description}",
                f"Alternative approach: Break down {failed_goal.description} into smaller tasks",
                f"Alternative approach: Seek external expertise for {failed_goal.description}"
            ]

        # Select the requested number of alternatives
        selected_alternatives = alternatives[:min(num_alternatives, len(alternatives))]

        for i, alt_desc in enumerate(selected_alternatives):
            # Perform feasibility check for each alternative strategy
            if self.feasibility_check:
                feasibility_result = self.feasibility_estimator.estimate(alt_desc, self.current_assessment)
                
                if feasibility_result == FeasibilityResult.BLOCK:
                    self.logger.info(f"Feasibility check blocked alternative strategy: '{alt_desc}'")
                    self.blocked_goals.append({
                        "description": alt_desc,
                        "reason": "Feasibility check blocked alternative strategy",
                        "timestamp": datetime.now().isoformat()
                    })
                    continue
                elif feasibility_result == FeasibilityResult.ADJUST_COMPLEXITY:
                    alt_desc = self._simplify_goal(alt_desc)
                    self.logger.info(f"Feasibility check adjusted alternative strategy complexity: '{alt_desc}'")
            
            alt_goal = Goal(
                description=alt_desc,
                priority=10 + i,  # Lower priority than retry goals
                source="alternative",
                last_selected=datetime.now(),
                failure_type=failure_type,
                original_goal=failed_goal.description
            )
            alternative_goals.append(alt_goal)
            self.alternative_strategies.append(alt_goal)
            self.goals.append(alt_goal)
            self.logger.debug(f"Generated alternative strategy: {alt_desc}")

        return alternative_goals

    def handle_failed_goal(self, goal: Goal, failure_type: FailureType, generate_alternatives: bool = True) -> Dict[str, Any]:
        """
        Complete handler for failed goals in retry mode.
        Generates retry sub-goals and optionally alternative strategies.
        Returns a summary of what was generated.
        """
        if not self.retry_mode:
            return {"message": "Retry mode not enabled", "retry_goals": [], "alternatives": []}

        # Record the failure with type
        self.record_goal_outcome(goal, success=False, failure_type=failure_type)

        # Generate retry sub-goals
        retry_goals = self.generate_retry_goals(goal)

        # Generate alternative strategies if requested
        alternatives = []
        if generate_alternatives:
            alternatives = self.generate_alternative_strategies(goal)

        return {
            "failed_goal": goal.description,
            "failure_type": failure_type.value,
            "retry_goals_generated": len(retry_goals),
            "alternative_strategies_generated": len(alternatives),
            "retry_goals": [g.description for g in retry_goals],
            "alternatives": [g.description for g in alternatives]
        }

    def _generate_summary(self, parsed: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a summary of changes made during processing."""
        return {
            "timestamp": datetime.now().isoformat(),
            "assessment_updated": bool(parsed.get("current_assessment")),
            "goals_prioritized": len(parsed.get("key_gaps", [])),
            "primary_goal_set": bool(parsed.get("next_priority")),
            "experimental_goals_injected": len(parsed.get("novel_ideas", [])),
            "total_goals": len(self.goals),
            "total_experimental": len(self.experimental_goals),
            "retry_mode": self.retry_mode,
            "failed_goals_count": len(self.failed_goals),
            "alternative_strategies_count": len(self.alternative_strategies),
            "blocked_goals_count": len(self.blocked_goals),
            "feasibility_check_enabled": self.feasibility_check
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

        # Analyze retry and alternative strategy success
        retry_goals = [g for g in self.goals if g.source == "retry"]
        alternative_goals = [g for g in self.goals if g.source == "alternative"]
        retry_success_rate = sum(g.success_rate() for g in retry_goals) / len(retry_goals) if retry_goals else 0
        alternative_success_rate = sum(g.success_rate() for g in alternative_goals) / len(alternative_goals) if alternative_goals else 0

        # Analyze blocked goals
        blocked_by_reason = {}
        for blocked in self.blocked_goals:
            reason = blocked.get("reason", "unknown")
            blocked_by_reason[reason] = blocked_by_reason.get(reason, 0) + 1

        return {
            "total_goals": total_goals,
            "successful_goals": successful_goals + successful_exp,
            "parsed_goal_success_rate": round(parsed_success_rate, 2),
            "experimental_goal_success_rate": round(experimental_success_rate, 2),
            "retry_goal_success_rate": round(retry_success_rate, 2),
            "alternative_strategy_success_rate": round(alternative_success_rate, 2),
            "feedback_entries": len(self.feedback_history),
            "current_assessment": self.current_assessment,
            "top_priority_goal": self.goals[0].description if self.goals else None,
            "retry_mode": self.retry_mode,
            "failed_goals_count": len(self.failed_goals),
            "alternative_strategies_count": len(self.alternative_strategies),
            "blocked_goals_count": len(self.blocked_goals),
            "blocked_goals_by_reason": blocked_by_reason,
            "feasibility_check_enabled": self.feasibility_check
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

    def get_failed_goals(self) -> List[Goal]:
        """Return list of failed goals for retry analysis."""
        return self.failed_goals

    def get_alternative_strategies(self) -> List[Goal]:
        """Return list of generated alternative strategies."""
        return self.alternative_strategies

    def get_blocked_goals(self) -> List[Dict[str, Any]]:
        """Return list of blocked goals with reasons."""
        return self.blocked_goals

    def set_feasibility_check(self, enabled: bool) -> None:
        """Enable or disable feasibility checking."""
        self.feasibility_check = enabled
        self.logger.info(f"Feasibility check {'enabled' if enabled else 'disabled'}")

# Example usage (commented out):
# if __name__ == "__main__":
#     logging.basicConfig(level=logging.INFO)
#     generator = GoalGenerator(feasibility_check=True)
#     
#     # Enable retry mode
#     generator.enable_retry_mode(True)
#     
#     # Process initial reflection
#     reflection = "I struggled with focus today. Key gaps: lack of focus, time management. Next priority: improve focus. Novel ideas: pomodoro technique, deep work blocks."
#     summary = generator.process_reflection(reflection)
#     print(json.dumps(summary, indent=2))
#     
#     # Select and execute a goal
#     goal = generator.select_goal()
#     if goal:
#         print(f"Selected goal: {goal.description}")
#         # Simulate failure with implementation bug
#         result = generator.handle_failed_goal(goal, FailureType.IMPLEMENTATION_BUG, generate_alternatives=True)
#         print(json.dumps(result, indent=2))
#     
#     # Get analysis
#     analysis = generator.get_feedback_analysis()
#     print(json.dumps(analysis, indent=2))
#     
#     # Check blocked goals
#     blocked = generator.get_blocked_goals()
#     print(f"Blocked goals: {len(blocked)}")
#     for b in blocked:
#         print(f"  - {b['description']}: {b['reason']}")