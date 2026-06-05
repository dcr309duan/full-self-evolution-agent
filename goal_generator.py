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
11. Meta-insight analyzer that parses knowledge for key insights and converts to concrete goals.
12. Generates 'complexity reduction' goals when triggered by rollback events.
"""

from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
import json
import logging
from datetime import datetime
import random

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
    target_module: Optional[str] = None  # Module targeted by this goal

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

class MetaInsightAnalyzer:
    """
    Meta-insight analyzer that:
    1. Parses accumulated knowledge for key insights about system architecture
    2. Extracts patterns like 'core modules need sandboxing', 'capabilities need consolidation'
    3. Converts each insight into a concrete goal with priority heuristic applied
    4. Merges with gap analysis results to produce final 3 goals
    """
    
    def __init__(self, knowledge_base: KnowledgeBase):
        self.knowledge_base = knowledge_base
        self.logger = logging.getLogger(__name__)
        
        # Known architectural patterns to detect
        self.architecture_patterns = {
            "sandboxing": ["sandbox", "isolation", "containment", "separate", "compartmentalize"],
            "consolidation": ["consolidate", "merge", "unify", "combine", "centralize"],
            "modularization": ["modular", "module", "component", "decouple", "loose coupling"],
            "scalability": ["scale", "scalable", "performance", "throughput", "load"],
            "security": ["security", "secure", "authentication", "authorization", "encryption"],
            "testing": ["test", "testing", "validation", "verification", "coverage"],
            "monitoring": ["monitor", "observability", "logging", "metrics", "alerting"],
            "documentation": ["document", "documentation", "docs", "readme", "wiki"]
        }
        
        # Priority heuristic weights
        self.priority_weights = {
            "frequency": 0.3,
            "impact": 0.4,
            "alignment": 0.3
        }
    
    def analyze(self) -> List[Dict[str, Any]]:
        """
        Analyze accumulated knowledge and extract key insights.
        
        Returns:
            List of insight dictionaries with keys: insight, pattern, priority_score, goal_description
        """
        all_entries = self.knowledge_base.get_all_entries()
        if not all_entries:
            self.logger.info("Knowledge base is empty, no insights to analyze")
            return []
        
        insights = []
        
        # Analyze failure patterns
        failure_patterns = self.knowledge_base.get_failure_patterns()
        for pattern in failure_patterns:
            detected_patterns = self._detect_architecture_patterns(pattern.description)
            for arch_pattern in detected_patterns:
                insight = {
                    "insight": pattern.description,
                    "pattern": arch_pattern,
                    "type": "failure",
                    "frequency": pattern.frequency,
                    "impact_score": pattern.impact_score,
                    "alignment_score": pattern.alignment_score
                }
                insights.append(insight)
        
        # Analyze successful strategies
        successful_strategies = self.knowledge_base.get_successful_strategies()
        for strategy in successful_strategies:
            detected_patterns = self._detect_architecture_patterns(strategy.description)
            for arch_pattern in detected_patterns:
                insight = {
                    "insight": strategy.description,
                    "pattern": arch_pattern,
                    "type": "success",
                    "frequency": strategy.frequency,
                    "impact_score": strategy.impact_score,
                    "alignment_score": strategy.alignment_score
                }
                insights.append(insight)
        
        # Analyze self-reflections
        self_reflections = self.knowledge_base.get_self_reflections()
        for reflection in self_reflections:
            detected_patterns = self._detect_architecture_patterns(reflection.description)
            for arch_pattern in detected_patterns:
                insight = {
                    "insight": reflection.description,
                    "pattern": arch_pattern,
                    "type": "reflection",
                    "frequency": reflection.frequency,
                    "impact_score": reflection.impact_score,
                    "alignment_score": reflection.alignment_score
                }
                insights.append(insight)
        
        # Deduplicate insights based on similar descriptions
        unique_insights = self._deduplicate_insights(insights)
        
        # Calculate priority scores for each insight
        for insight in unique_insights:
            insight["priority_score"] = self._calculate_priority_score(
                frequency=insight["frequency"],
                impact=insight["impact_score"],
                alignment=insight["alignment_score"],
                is_failure=(insight["type"] == "failure")
            )
        
        # Sort by priority score descending
        unique_insights.sort(key=lambda x: x["priority_score"], reverse=True)
        
        # Generate concrete goal descriptions for each insight
        for insight in unique_insights:
            insight["goal_description"] = self._generate_goal_from_insight(insight)
        
        return unique_insights
    
    def _detect_architecture_patterns(self, text: str) -> List[str]:
        """
        Detect architecture patterns in text.
        
        Args:
            text: The text to analyze
            
        Returns:
            List of detected pattern names
        """
        detected = []
        text_lower = text.lower()
        
        for pattern_name, keywords in self.architecture_patterns.items():
            for keyword in keywords:
                if keyword in text_lower:
                    detected.append(pattern_name)
                    break
        
        return detected if detected else ["general"]
    
    def _deduplicate_insights(self, insights: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Deduplicate insights based on similar descriptions.
        
        Args:
            insights: List of insight dictionaries
            
        Returns:
            Deduplicated list of insight dictionaries
        """
        unique = []
        seen_descriptions = set()
        
        for insight in insights:
            # Normalize description for comparison
            normalized = insight["insight"].lower().strip()
            
            # Check if similar description already exists
            is_duplicate = False
            for seen in seen_descriptions:
                # Simple similarity check: if one contains the other
                if normalized in seen or seen in normalized:
                    is_duplicate = True
                    break
            
            if not is_duplicate:
                seen_descriptions.add(normalized)
                unique.append(insight)
        
        return unique
    
    def _calculate_priority_score(self, frequency: int, impact: float, alignment: float, is_failure: bool) -> float:
        """
        Calculate priority score for an insight.
        
        Args:
            frequency: How often this pattern appears
            impact: Potential impact score (0.0 to 1.0)
            alignment: Alignment with self-reflection insights (0.0 to 1.0)
            is_failure: Whether this is from a failure pattern
            
        Returns:
            Priority score (0.0 to 1.0)
        """
        # Normalize frequency (assume max frequency of 10 for normalization)
        frequency_normalized = min(frequency / 10.0, 1.0)
        
        # Adjust weights based on failure status
        frequency_weight = self.priority_weights["frequency"]
        impact_weight = self.priority_weights["impact"]
        alignment_weight = self.priority_weights["alignment"]
        
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
    
    def _generate_goal_from_insight(self, insight: Dict[str, Any]) -> str:
        """
        Generate a concrete goal description from an insight.
        
        Args:
            insight: The insight dictionary
            
        Returns:
            Goal description string
        """
        pattern = insight["pattern"]
        insight_text = insight["insight"]
        
        # Generate goal based on pattern type
        if pattern == "sandboxing":
            return f"Implement sandboxing for {insight_text}"
        elif pattern == "consolidation":
            return f"Consolidate {insight_text}"
        elif pattern == "modularization":
            return f"Modularize {insight_text}"
        elif pattern == "scalability":
            return f"Improve scalability of {insight_text}"
        elif pattern == "security":
            return f"Enhance security for {insight_text}"
        elif pattern == "testing":
            return f"Add comprehensive tests for {insight_text}"
        elif pattern == "monitoring":
            return f"Implement monitoring for {insight_text}"
        elif pattern == "documentation":
            return f"Document {insight_text}"
        else:
            # Generic goal generation
            prefixes = ["Address", "Improve", "Optimize", "Refactor", "Enhance"]
            prefix = random.choice(prefixes)
            return f"{prefix} {insight_text}"
    
    def merge_with_gap_analysis(self, insights: List[Dict[str, Any]], key_gaps: List[str]) -> List[Goal]:
        """
        Merge insights with gap analysis results to produce final goals.
        
        Args:
            insights: List of insight dictionaries
            key_gaps: List of key gaps from reflection parsing
            
        Returns:
            List of Goal objects (top 3)
        """
        # Convert insights to goals
        insight_goals = []
        for i, insight in enumerate(insights):
            goal = Goal(
                description=insight["goal_description"],
                priority=i + 1,
                source="meta_insight",
                last_selected=datetime.now(),
                rationale=f"Meta-insight from pattern '{insight['pattern']}': {insight['insight']}"
            )
            insight_goals.append(goal)
        
        # Convert key gaps to goals
        gap_goals = []
        for gap in key_gaps:
            # Check if gap already covered by an insight goal
            if not any(gap.lower() in g.description.lower() for g in insight_goals):
                goal = Goal(
                    description=f"Address gap: {gap}",
                    priority=len(insight_goals) + len(gap_goals) + 1,
                    source="gap_analysis",
                    last_selected=datetime.now(),
                    rationale=f"Key gap identified: {gap}"
                )
                gap_goals.append(goal)
        
        # Combine and sort by priority
        all_goals = insight_goals + gap_goals
        all_goals.sort(key=lambda g: g.priority)
        
        # Return top 3 goals
        return all_goals[:3]

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
        prefix = random.choice(prefixes)
        return f"{prefix} {failure_description}"
    
    def _generate_goal_from_success(self, success_description: str) -> str:
        """Generate a goal description from a successful strategy."""
        # Simple transformation: add "Continue" or "Expand" prefix
        prefixes = ["Continue", "Expand", "Reinforce", "Optimize", "Scale"]
        prefix = random.choice(prefixes)
        return f"{prefix} {success_description}"
    
    def _generate_goal_from_reflection(self, reflection_description: str) -> str:
        """Generate a goal description from a self-reflection insight."""
        # Simple transformation: add "Implement" or "Apply" prefix
        prefixes = ["Implement", "Apply", "Integrate", "Adopt", "Practice"]
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
    Includes meta-insight analyzer for extracting architectural insights.
    Includes complexity reduction goal generation triggered by rollback events.
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
        self.meta_insight_analyzer = MetaInsightAnalyzer(self.knowledge_base)  # Initialize meta-insight analyzer
        self.rollback_events: List[Dict[str, Any]] = []  # Track rollback events for complexity reduction
        self.logger = logging.getLogger(__name__)
        
        # Core files list for priority scoring
        self.core_files = [
            "evolution_orchestrator.py",
            "goal_generator.py",
            "mutation_engine.py",
            "reflection_engine.py"
        ]

    def calculate_priority_score(self, goal_description: str, target_files: List[str]) -> int:
        """
        Calculate priority score for a proposed goal based on target files and description.
        
        Args:
            goal_description: The proposed goal description
            target_files: List of target files for the goal
            
        Returns:
            Integer priority score (higher = higher priority)
        """
        base_priority = 0
        
        # Check if any target files are in the core list
        has_core_file = any(f in self.core_files for f in target_files)
        has_new_module = any("new" in f.lower() or "module" in f.lower() for f in target_files)
        has_test_file = any("test" in f.lower() or "tests" in f.lower() for f in target_files)
        
        # Assign base priority
        if has_core_file:
            base_priority = 10
        elif has_new_module:
            base_priority = 3
        elif has_test_file:
            base_priority = 1
        else:
            base_priority = 3  # Default for other files
        
        # Check for recursive self-modification pattern
        self_modification_keywords = [
            "self-modify", "self modify", "recursive", "self-improve", 
            "self improve", "self-evolve", "self evolve", "self-rewrite",
            "self rewrite", "self-generate", "self generate", "autonomous modification"
        ]
        
        has_self_modification = any(
            keyword in goal_description.lower() for keyword in self_modification_keywords
        )
        
        # Apply bonus for recursive self-modification
        if has_self_modification:
            base_priority += 2
        
        return base_priority

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
        
        # Run meta-insight analysis and merge with gap analysis
        self._run_meta_insight_analysis(parsed.get("key_gaps", []))
        
        # Check for rollback events and generate complexity reduction goals
        self._check_rollback_events(reflection_text)
        
        summary = self._generate_summary(parsed)
        self._record_feedback(parsed, summary)
        return summary

    def _check_rollback_events(self, reflection_text: str) -> None:
        """
        Check reflection text for rollback events and generate complexity reduction goals.
        
        Args:
            reflection_text: The reflection text to analyze
        """
        # Keywords indicating a rollback event
        rollback_keywords = [
            "rollback", "revert", "undo", "backout", "back out",
            "failed change", "breaking change", "regression",
            "reverted", "rolled back", "undone"
        ]
        
        reflection_lower = reflection_text.lower()
        
        # Check if any rollback keywords are present
        has_rollback = any(keyword in reflection_lower for keyword in rollback_keywords)
        
        if not has_rollback:
            return
        
        # Extract the module that caused the failure
        # Look for file names or module names in the reflection text
        module_patterns = [
            r'\b(\w+\.py)\b',  # Python files
            r'\bmodule\s+(\w+)\b',  # Module references
            r'\b(\w+_engine)\b',  # Engine modules
            r'\b(\w+_orchestrator)\b',  # Orchestrator modules
        ]
        
        import re
        failed_module = None
        
        for pattern in module_patterns:
            matches = re.findall(pattern, reflection_lower)
            if matches:
                # Use the first match as the failed module
                failed_module = matches[0]
                break
        
        if not failed_module:
            # Default to generic module if none found
            failed_module = "unknown_module"
        
        # Record the rollback event
        rollback_event = {
            "timestamp": datetime.now().isoformat(),
            "module": failed_module,
            "reflection_text": reflection_text,
            "processed": False
        }
        self.rollback_events.append(rollback_event)
        
        # Generate complexity reduction goal
        complexity_goal = self._generate_complexity_reduction_goal(failed_module)
        
        if complexity_goal:
            # Add the goal with high priority
            self.goals.insert(0, complexity_goal)  # Insert at beginning for highest priority
            self.logger.info(f"Generated complexity reduction goal for module '{failed_module}' with high priority")
            
            # Mark rollback event as processed
            rollback_event["processed"] = True

    def _generate_complexity_reduction_goal(self, module_name: str) -> Optional[Goal]:
        """
        Generate a complexity reduction goal for a specific module.
        
        Args:
            module_name: The name of the module that caused the failure
            
        Returns:
            Goal object with high priority, or None if generation fails
        """
        # Generate goal description based on module name
        if module_name.endswith('.py'):
            module_display = module_name
        else:
            module_display = f"{module_name}.py"
        
        # Create goal description
        goal_description = f"Reduce LOC in {module_display} by removing dead code"
        
        # Create the goal with high priority (priority 1 = highest)
        goal = Goal(
            description=goal_description,
            priority=1,  # High priority
            source="complexity_reduction",
            last_selected=datetime.now(),
            rationale=f"Rollback event detected involving module '{module_name}'. Reducing complexity to prevent future failures.",
            target_module=module_name
        )
        
        # Perform feasibility check if enabled
        if self.feasibility_check:
            feasibility_result = self.feasibility_estimator.estimate(goal_description, self.current_assessment)
            
            if feasibility_result == FeasibilityResult.BLOCK:
                self.logger.info(f"Feasibility check blocked complexity reduction goal: '{goal_description}'")
                self.blocked_goals.append({
                    "description": goal_description,
                    "reason": "Feasibility check blocked complexity reduction goal",
                    "timestamp": datetime.now().isoformat()
                })
                return None
            elif feasibility_result == FeasibilityResult.ADJUST_COMPLEXITY:
                goal.description = self._simplify_goal(goal_description)
                self.logger.info(f"Feasibility check adjusted complexity reduction goal: '{goal.description}'")
        
        return goal

    def _simplify_goal(self, goal_description: str) -> str:
        """
        Simplify a goal description to make it more feasible.
        
        Args:
            goal_description: The original goal description
            
        Returns:
            Simplified goal description
        """
        # Remove complexity indicators
        complexity_indicators = [
            "all", "everything", "complete", "full", "entire",
            "multiple", "several", "many", "various", "numerous",
            "large", "massive", "extensive", "comprehensive"
        ]
        
       