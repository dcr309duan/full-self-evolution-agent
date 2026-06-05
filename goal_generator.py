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
10. Analyzes accumulated knowledge base to autonomously generate new sub-goals.
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
    source: str  # e.g., "parsed", "experimental", "manual", "retry", "alternative", "autonomous"
    success_count: int = 0
    failure_count: int = 0
    last_selected: Optional[datetime] = None
    failure_type: Optional[FailureType] = None  # Track failure type for retry
    original_goal: Optional[str] = None  # Reference to original goal for alternatives
    rationale: Optional[str] = None  # Rationale for autonomous goal generation

    def success_rate(self) -> float:
        total = self.success_count + self.failure_count
        return self.success_count / total if total > 0 else 0.0

@dataclass
class KnowledgeEntry:
    """Represents a single entry in the knowledge base."""
    type: str  # "failure_pattern", "successful_strategy", "self_reflection"
    description: str
    frequency: int = 1
    impact_score: float = 0.5  # 0.0 to 1.0
    alignment_score: float = 0.5  # 0.0 to 1.0
    timestamp: datetime = field(default_factory=datetime.now)

class KnowledgeBase:
    """
    Accumulates and analyzes knowledge from failures, successes, and self-reflections.
    Used by AutonomousGoalAnalyzer to generate new goals.
    """
    
    def __init__(self):
        self.entries: List[KnowledgeEntry] = []
        self.logger = logging.getLogger(__name__)
    
    def add_entry(self, entry: KnowledgeEntry) -> None:
        """Add a new entry to the knowledge base."""
        # Check if similar entry exists and update frequency
        for existing in self.entries:
            if (existing.type == entry.type and 
                existing.description.lower() == entry.description.lower()):
                existing.frequency += 1
                existing.impact_score = max(existing.impact_score, entry.impact_score)
                existing.alignment_score = max(existing.alignment_score, entry.alignment_score)
                existing.timestamp = datetime.now()
                self.logger.debug(f"Updated existing knowledge entry: {entry.description}")
                return
        
        self.entries.append(entry)
        self.logger.debug(f"Added new knowledge entry: {entry.description}")
    
    def add_failure_pattern(self, description: str, impact_score: float = 0.5) -> None:
        """Add a failure pattern to the knowledge base."""
        entry = KnowledgeEntry(
            type="failure_pattern",
            description=description,
            impact_score=impact_score,
            alignment_score=0.3  # Default alignment for failures
        )
        self.add_entry(entry)
    
    def add_successful_strategy(self, description: str, impact_score: float = 0.7) -> None:
        """Add a successful strategy to the knowledge base."""
        entry = KnowledgeEntry(
            type="successful_strategy",
            description=description,
            impact_score=impact_score,
            alignment_score=0.8  # Default alignment for successes
        )
        self.add_entry(entry)
    
    def add_self_reflection(self, description: str, alignment_score: float = 0.6) -> None:
        """Add a self-reflection insight to the knowledge base."""
        entry = KnowledgeEntry(
            type="self_reflection",
            description=description,
            impact_score=0.4,  # Default impact for reflections
            alignment_score=alignment_score
        )
        self.add_entry(entry)
    
    def get_failure_patterns(self) -> List[KnowledgeEntry]:
        """Get all failure pattern entries."""
        return [e for e in self.entries if e.type == "failure_pattern"]
    
    def get_successful_strategies(self) -> List[KnowledgeEntry]:
        """Get all successful strategy entries."""
        return [e for e in self.entries if e.type == "successful_strategy"]
    
    def get_self_reflections(self) -> List[KnowledgeEntry]:
        """Get all self-reflection entries."""
        return [e for e in self.entries if e.type == "self_reflection"]
    
    def get_all_entries(self) -> List[KnowledgeEntry]:
        """Get all knowledge entries."""
        return self.entries
    
    def clear(self) -> None:
        """Clear all knowledge entries."""
        self.entries.clear()
        self.logger.debug("Knowledge base cleared")

class AutonomousGoalAnalyzer:
    """
    Analyzes the accumulated knowledge base and autonomously generates new sub-goals.
    Uses priority scoring based on frequency of failure, potential impact, and alignment with self-reflection insights.
    """
    
    def __init__(self, knowledge_base: KnowledgeBase):
        self.knowledge_base = knowledge_base
        self.logger = logging.getLogger(__name__)
    
    def analyze_and_generate_goals(self, max_goals: int = 5) -> List[Goal]:
        """
        Analyze knowledge base and generate new sub-goals with priority scores.
        
        Args:
            max_goals: Maximum number of goals to generate
            
        Returns:
            List of Goal objects with priority scores and rationale
        """
        failure_patterns = self.knowledge_base.get_failure_patterns()
        successful_strategies = self.knowledge_base.get_successful_strategies()
        self_reflections = self.knowledge_base.get_self_reflections()
        
        if not failure_patterns and not successful_strategies and not self_reflections:
            self.logger.info("Knowledge base is empty, no goals to generate")
            return []
        
        # Calculate priority scores for potential goals
        goal_candidates = []
        
        # 1. Generate goals from failure patterns (address recurring issues)
        for pattern in failure_patterns:
            priority_score = self._calculate_priority_score(
                frequency=pattern.frequency,
                impact=pattern.impact_score,
                alignment=pattern.alignment_score,
                is_failure=True
            )
            
            # Generate goal description from failure pattern
            goal_desc = self._generate_goal_from_failure(pattern.description)
            
            goal_candidates.append({
                "description": goal_desc,
                "priority_score": priority_score,
                "rationale": f"Addresses recurring failure pattern: '{pattern.description}' (frequency: {pattern.frequency}, impact: {pattern.impact_score:.2f})",
                "source": "autonomous_failure"
            })
        
        # 2. Generate goals from successful strategies (reinforce what works)
        for strategy in successful_strategies:
            priority_score = self._calculate_priority_score(
                frequency=strategy.frequency,
                impact=strategy.impact_score,
                alignment=strategy.alignment_score,
                is_failure=False
            )
            
            # Generate goal description from successful strategy
            goal_desc = self._generate_goal_from_success(strategy.description)
            
            goal_candidates.append({
                "description": goal_desc,
                "priority_score": priority_score,
                "rationale": f"Reinforces successful strategy: '{strategy.description}' (frequency: {strategy.frequency}, impact: {strategy.impact_score:.2f})",
                "source": "autonomous_success"
            })
        
        # 3. Generate goals from self-reflections (align with insights)
        for reflection in self_reflections:
            priority_score = self._calculate_priority_score(
                frequency=reflection.frequency,
                impact=reflection.impact_score,
                alignment=reflection.alignment_score,
                is_failure=False
            )
            
            # Generate goal description from self-reflection
            goal_desc = self._generate_goal_from_reflection(reflection.description)
            
            goal_candidates.append({
                "description": goal_desc,
                "priority_score": priority_score,
                "rationale": f"Aligns with self-reflection insight: '{reflection.description}' (alignment: {reflection.alignment_score:.2f})",
                "source": "autonomous_reflection"
            })
        
        # Sort by priority score (higher is better)
        goal_candidates.sort(key=lambda x: x["priority_score"], reverse=True)
        
        # Select top goals
        selected_candidates = goal_candidates[:max_goals]
        
        # Create Goal objects
        generated_goals = []
        for i, candidate in enumerate(selected_candidates):
            goal = Goal(
                description=candidate["description"],
                priority=i + 1,  # Sequential priority based on score
                source=candidate["source"],
                last_selected=datetime.now(),
                rationale=candidate["rationale"]
            )
            generated_goals.append(goal)
            self.logger.info(f"Generated autonomous goal: '{goal.description}' (priority: {goal.priority}, score: {candidate['priority_score']:.2f})")
        
        return generated_goals
    
    def _calculate_priority_score(self, frequency: int, impact: float, alignment: float, is_failure: bool) -> float:
        """
        Calculate priority score for a goal candidate.
        
        Formula: (frequency_weight * frequency_normalized) + (impact_weight * impact) + (alignment_weight * alignment)
        
        Args:
            frequency: How often this pattern/strategy appears
            impact: Potential impact score (0.0 to 1.0)
            alignment: Alignment with self-reflection insights (0.0 to 1.0)
            is_failure: Whether this is from a failure pattern
            
        Returns:
            Priority score (0.0 to 1.0)
        """
        # Normalize frequency (assume max frequency of 10 for normalization)
        frequency_normalized = min(frequency / 10.0, 1.0)
        
        # Weights for different components
        frequency_weight = 0.3
        impact_weight = 0.4
        alignment_weight = 0.3
        
        # Boost impact for failure patterns (they need more attention)
        if is_failure:
            impact_weight += 0.1
            frequency_weight += 0.1
            alignment_weight -= 0.2
        
        # Ensure weights sum to 1.0
        total_weight = frequency_weight + impact_weight + alignment_weight
        frequency_weight /= total_weight
        impact_weight /= total_weight
        alignment_weight /= total_weight
        
        score = (frequency_weight * frequency_normalized) + (impact_weight * impact) + (alignment_weight * alignment)
        return min(max(score, 0.0), 1.0)  # Clamp to [0.0, 1.0]
    
    def _generate_goal_from_failure(self, failure_description: str) -> str:
        """Generate a goal description from a failure pattern."""
        # Simple transformation: add "Fix" or "Address" prefix
        prefixes = ["Fix", "Address", "Resolve", "Eliminate", "Prevent"]
        import random
        prefix = random.choice(prefixes)
        return f"{prefix} {failure_description}"
    
    def _generate_goal_from_success(self, success_description: str) -> str:
        """Generate a goal description from a successful strategy."""
        # Simple transformation: add "Continue" or "Expand" prefix
        prefixes = ["Continue", "Expand", "Reinforce", "Optimize", "Scale"]
        import random
        prefix = random.choice(prefixes)
        return f"{prefix} {success_description}"
    
    def _generate_goal_from_reflection(self, reflection_description: str) -> str:
        """Generate a goal description from a self-reflection insight."""
        # Simple transformation: add "Implement" or "Apply" prefix
        prefixes = ["Implement", "Apply", "Integrate", "Adopt", "Practice"]
        import random
        prefix = random.choice(prefixes)
        return f"{prefix} {reflection_description}"

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
    Includes autonomous goal generation from knowledge base analysis.
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
        self.knowledge_base = KnowledgeBase()  # Initialize knowledge base
        self.autonomous_analyzer = AutonomousGoalAnalyzer(self.knowledge_base)  # Initialize analyzer
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
        
        # Add reflection insights to knowledge base
        self._add_reflection_to_knowledge_base(reflection_text)
        
        # Generate autonomous goals from knowledge base
        self._generate_autonomous_goals()
        
        summary = self._generate_summary(parsed)
        self._record_feedback(parsed, summary)
        return summary

    def _add_reflection_to_knowledge_base(self, reflection_text: str) -> None:
        """Parse reflection text and add relevant entries to knowledge base."""
        # Simple parsing: look for keywords indicating failures, successes, or reflections
        reflection_lower = reflection_text.lower()
        
        # Check for failure indicators
        failure_indicators = ["failed", "struggled", "couldn't", "didn't work", "error", "bug", "issue", "problem"]
        for indicator in failure_indicators:
            if indicator in reflection_lower:
                # Extract the context around the failure indicator
                idx = reflection_lower.find(indicator)
                start = max(0, idx - 50)
                end = min(len(reflection_text), idx + 50)
                context = reflection_text[start:end].strip()
                self.knowledge_base.add_failure_pattern(context, impact_score=0.6)
                break
        
        # Check for success indicators
        success_indicators = ["succeeded", "completed", "achieved", "solved", "fixed", "resolved", "worked"]
        for indicator in success_indicators:
            if indicator in reflection_lower:
                idx = reflection_lower.find(indicator)
                start = max(0, idx - 50)
                end = min(len(reflection_text), idx + 50)
                context = reflection_text[start:end].strip()
                self.knowledge_base.add_successful_strategy(context, impact_score=0.7)
                break
        
        # Check for self-reflection indicators
        reflection_indicators = ["realized", "learned", "understood", "noticed", "observed", "felt", "thought"]
        for indicator in reflection_indicators:
            if indicator in reflection_lower:
                idx = reflection_lower.find(indicator)
                start = max(0, idx - 50)
                end = min(len(reflection_text), idx + 50)
                context = reflection_text[start:end].strip()
                self.knowledge_base.add_self_reflection(context, alignment_score=0.6)
                break

    def _generate_autonomous_goals(self, max_goals: int = 3) -> None:
        """
        Generate autonomous goals from knowledge base analysis.
        Adds generated goals to the regular goals list.
        """
        generated_goals = self.autonomous_analyzer.analyze_and_generate_goals(max_goals=max_goals)
        
        for goal in generated_goals:
            # Check if similar goal already exists
            if not any(g.description.lower() == goal.description.lower() for g in self.goals):
                # Perform feasibility check
                if self.feasibility_check:
                    feasibility_result = self.feasibility_estimator.estimate(goal.description, self.current_assessment)
                    
                    if feasibility_result == FeasibilityResult.BLOCK:
                        self.logger.info(f"Feasibility check blocked autonomous goal: '{goal.description}'")
                        self.blocked_goals.append({
                            "description": goal.description,
                            "reason": "Feasibility check blocked autonomous goal",
                            "timestamp": datetime.now().isoformat()
                        })
                        continue
                    elif feasibility_result == FeasibilityResult.ADJUST_COMPLEXITY:
                        goal.description = self._simplify_goal(goal.description)
                        self.logger.info(f"Feasibility check adjusted autonomous goal complexity: '{goal.description}'")
                
                self.goals.append(goal)
                self.logger.info(f"Added autonomous goal: '{goal.description}' (priority: {goal.priority})")

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
        Also updates knowledge base with outcome.
        """
        if success:
            goal.success_count += 1
            # Add successful strategy to knowledge base
            self.knowledge_base.add_successful_strategy(goal.description, impact_score=0.7)
        else:
            goal.failure_count += 1
            if failure_type:
                goal.failure_type = failure_type
                self.failed_goals.append(goal)
                # Add failure pattern to knowledge base
                self.knowledge_base.add_failure_pattern(goal.description, impact_score=0.6)
            else:
                # Add generic failure pattern
                self.knowledge_base.add_failure_pattern(goal.description, impact_score=0.4)

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

        #