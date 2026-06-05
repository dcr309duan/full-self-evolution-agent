"""Goal generation for improving simulation accuracy.

This module provides functions to generate goals based on simulation accuracy
metrics and unexpected side effects. Goals are prioritized to expand simulation
coverage. Enhanced to proactively resolve blocking dependencies by querying
the knowledge base and generating blocker resolution sub-goals.
"""

from typing import List, Dict, Optional
from dataclasses import dataclass, field
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class GoalPriority(Enum):
    """Priority levels for generated goals."""
    HIGH = 1
    MEDIUM = 2
    LOW = 3


@dataclass
class Goal:
    """Represents a generated goal for improving simulation."""
    description: str
    priority: GoalPriority
    module: str
    goal_type: str  # 'accuracy', 'dependency_tracking', or 'blocker_resolution'
    archived: bool = False
    lesson: Optional[str] = None
    dependencies: List[str] = field(default_factory=list)  # List of sub-goal descriptions this goal depends on
    tags: List[str] = field(default_factory=list)  # Tags for categorization

    def __str__(self) -> str:
        return f"[{self.priority.name}] {self.description}"


@dataclass
class SimulationMetrics:
    """Metrics from a simulation run."""
    module: str
    accuracy: float  # 0.0 to 1.0
    has_unexpected_side_effects: bool = False
    coverage: float = 0.0  # 0.0 to 1.0, how much of the module is covered


# Global registries for goals and knowledge
goal_registry: Dict[str, Goal] = {}
knowledge_base: Dict[str, str] = {}


def generate_goals(
    metrics_list: List[SimulationMetrics],
    accuracy_threshold: float = 0.8,
    coverage_weight: float = 0.5
) -> List[Goal]:
    """Generate goals based on simulation metrics.

    Args:
        metrics_list: List of simulation metrics for different modules.
        accuracy_threshold: Threshold below which accuracy goals are generated.
        coverage_weight: Weight for coverage in priority calculation (0-1).

    Returns:
        List of generated goals, sorted by priority (highest first).
    """
    goals: List[Goal] = []

    for metrics in metrics_list:
        # Generate accuracy improvement goals if accuracy is below threshold
        if metrics.accuracy < accuracy_threshold:
            goal = Goal(
                description=f"Improve simulation accuracy for {metrics.module}",
                priority=_calculate_priority(metrics, coverage_weight),
                module=metrics.module,
                goal_type="accuracy"
            )
            goals.append(goal)
            logger.debug(
                "Generated accuracy goal for %s (accuracy=%.2f, threshold=%.2f)",
                metrics.module, metrics.accuracy, accuracy_threshold
            )

        # Generate dependency tracking goals if unexpected side effects
        if metrics.has_unexpected_side_effects:
            goal = Goal(
                description=f"Add dependency tracking for {metrics.module}",
                priority=_calculate_priority(metrics, coverage_weight),
                module=metrics.module,
                goal_type="dependency_tracking"
            )
            goals.append(goal)
            logger.debug(
                "Generated dependency tracking goal for %s (side effects detected)",
                metrics.module
            )

    # Sort goals by priority (HIGH first) to prioritize coverage expansion
    goals.sort(key=lambda g: (g.priority.value, -_coverage_score(g, metrics_list)))

    return goals


def _calculate_priority(
    metrics: SimulationMetrics,
    coverage_weight: float
) -> GoalPriority:
    """Calculate priority based on metrics and coverage weight.

    Lower coverage and lower accuracy increase priority.
    """
    # Base priority on accuracy deficit and coverage
    accuracy_deficit = 1.0 - metrics.accuracy
    coverage_deficit = 1.0 - metrics.coverage

    # Weighted score: higher = more urgent
    score = (accuracy_deficit * (1 - coverage_weight) +
             coverage_deficit * coverage_weight)

    if score > 0.7:
        return GoalPriority.HIGH
    elif score > 0.4:
        return GoalPriority.MEDIUM
    else:
        return GoalPriority.LOW


def _coverage_score(goal: Goal, metrics_list: List[SimulationMetrics]) -> float:
    """Calculate coverage score for a goal to prioritize coverage expansion.

    Returns higher score for modules with lower coverage.
    """
    for metrics in metrics_list:
        if metrics.module == goal.module:
            return 1.0 - metrics.coverage
    return 0.0


def generate_goals_from_report(
    report: Dict,
    accuracy_threshold: float = 0.8,
    coverage_weight: float = 0.5
) -> List[Goal]:
    """Generate goals from a simulation report dictionary.

    Expected report format:
    {
        "modules": [
            {
                "name": "module_name",
                "accuracy": 0.95,
                "has_unexpected_side_effects": False,
                "coverage": 0.8
            },
            ...
        ]
    }

    Args:
        report: Dictionary containing simulation report data.
        accuracy_threshold: Threshold for accuracy goals.
        coverage_weight: Weight for coverage in priority.

    Returns:
        List of generated goals.
    """
    metrics_list = []
    for module_data in report.get("modules", []):
        metrics = SimulationMetrics(
            module=module_data.get("name", "unknown"),
            accuracy=module_data.get("accuracy", 1.0),
            has_unexpected_side_effects=module_data.get(
                "has_unexpected_side_effects", False
            ),
            coverage=module_data.get("coverage", 0.0)
        )
        metrics_list.append(metrics)

    return generate_goals(metrics_list, accuracy_threshold, coverage_weight)


def prioritize_goals(goals: List[Goal]) -> List[Goal]:
    """Re-prioritize goals to expand simulation coverage.

    This function sorts goals so that those related to modules with
    lower coverage come first, within the same priority level.

    Args:
        goals: List of goals to prioritize.

    Returns:
        Re-prioritized list of goals.
    """
    # Sort by priority first, then by coverage (lower coverage first)
    # This assumes goals have been generated with coverage info
    return sorted(goals, key=lambda g: (g.priority.value, g.description))


def generate_sub_goals(
    parent_goal: Goal,
    decomposition_strategy: str = "sequential"
) -> List[Goal]:
    """Break a complex goal into 2-3 smaller, more achievable sub-goals with explicit dependencies.

    Args:
        parent_goal: The complex goal to break down.
        decomposition_strategy: Strategy for generating sub-goals and dependencies.
            Supported strategies:
            - 'sequential': Sub-goals are generated in a linear chain where each depends on the previous.
            - 'parallel': Sub-goals are generated with no dependencies between them.
            - 'dependency-based': Sub-goals are generated with explicit dependencies based on goal type.

    Returns:
        List of 2-3 sub-goals derived from the parent goal, with dependency edges set.
    """
    sub_goals: List[Goal] = []
    
    if parent_goal.goal_type == "accuracy":
        # Break accuracy improvement into smaller steps
        analyze_goal = Goal(
            description=f"Analyze accuracy gaps in {parent_goal.module}",
            priority=parent_goal.priority,
            module=parent_goal.module,
            goal_type="accuracy"
        )
        implement_goal = Goal(
            description=f"Implement targeted fixes for {parent_goal.module}",
            priority=parent_goal.priority,
            module=parent_goal.module,
            goal_type="accuracy"
        )
        validate_goal = Goal(
            description=f"Validate accuracy improvements for {parent_goal.module}",
            priority=parent_goal.priority,
            module=parent_goal.module,
            goal_type="accuracy"
        )
        
        if decomposition_strategy == "sequential":
            # Linear chain: analyze -> implement -> validate
            implement_goal.dependencies.append(analyze_goal.description)
            validate_goal.dependencies.append(implement_goal.description)
            sub_goals = [analyze_goal, implement_goal, validate_goal]
        elif decomposition_strategy == "parallel":
            # No dependencies between sub-goals
            sub_goals = [analyze_goal, implement_goal, validate_goal]
        elif decomposition_strategy == "dependency-based":
            # Dependency-based: analyze is independent, implement depends on analyze, validate depends on implement
            implement_goal.dependencies.append(analyze_goal.description)
            validate_goal.dependencies.append(implement_goal.description)
            sub_goals = [analyze_goal, implement_goal, validate_goal]
        else:
            # Default to sequential for unknown strategies
            implement_goal.dependencies.append(analyze_goal.description)
            validate_goal.dependencies.append(implement_goal.description)
            sub_goals = [analyze_goal, implement_goal, validate_goal]
            
    elif parent_goal.goal_type == "dependency_tracking":
        # Break dependency tracking into smaller steps
        identify_goal = Goal(
            description=f"Identify dependencies for {parent_goal.module}",
            priority=parent_goal.priority,
            module=parent_goal.module,
            goal_type="dependency_tracking"
        )
        implement_goal = Goal(
            description=f"Implement dependency tracking for {parent_goal.module}",
            priority=parent_goal.priority,
            module=parent_goal.module,
            goal_type="dependency_tracking"
        )
        
        if decomposition_strategy == "sequential":
            # Linear chain: identify -> implement
            implement_goal.dependencies.append(identify_goal.description)
            sub_goals = [identify_goal, implement_goal]
        elif decomposition_strategy == "parallel":
            # No dependencies between sub-goals
            sub_goals = [identify_goal, implement_goal]
        elif decomposition_strategy == "dependency-based":
            # Dependency-based: implement depends on identify
            implement_goal.dependencies.append(identify_goal.description)
            sub_goals = [identify_goal, implement_goal]
        else:
            # Default to sequential for unknown strategies
            implement_goal.dependencies.append(identify_goal.description)
            sub_goals = [identify_goal, implement_goal]
    else:
        # Generic breakdown for unknown goal types
        research_goal = Goal(
            description=f"Research requirements for {parent_goal.description}",
            priority=parent_goal.priority,
            module=parent_goal.module,
            goal_type=parent_goal.goal_type
        )
        implement_goal = Goal(
            description=f"Implement solution for {parent_goal.description}",
            priority=parent_goal.priority,
            module=parent_goal.module,
            goal_type=parent_goal.goal_type
        )
        
        if decomposition_strategy == "sequential":
            # Linear chain: research -> implement
            implement_goal.dependencies.append(research_goal.description)
            sub_goals = [research_goal, implement_goal]
        elif decomposition_strategy == "parallel":
            # No dependencies between sub-goals
            sub_goals = [research_goal, implement_goal]
        elif decomposition_strategy == "dependency-based":
            # Dependency-based: implement depends on research
            implement_goal.dependencies.append(research_goal.description)
            sub_goals = [research_goal, implement_goal]
        else:
            # Default to sequential for unknown strategies
            implement_goal.dependencies.append(research_goal.description)
            sub_goals = [research_goal, implement_goal]
    
    logger.debug(
        "Generated %d sub-goals for parent goal: %s using strategy: %s",
        len(sub_goals), parent_goal.description, decomposition_strategy
    )
    
    return sub_goals


def query_knowledge_base_for_blockers(module: str) -> List[str]:
    """Query the knowledge base for top blocking dependencies related to a module.

    Args:
        module: The module to check for blockers.

    Returns:
        List of blocker descriptions found in the knowledge base.
    """
    blockers = []
    # Search knowledge base for entries related to this module that indicate blockers
    for key, value in knowledge_base.items():
        if module in key and "blocker" in key.lower():
            blockers.append(value)
        # Also check if the value mentions blocking
        if module in key and "block" in value.lower():
            blockers.append(value)
    
    # Sort by impact (prioritize entries with 'critical' or 'high' impact)
    high_impact = [b for b in blockers if 'critical' in b.lower() or 'high' in b.lower()]
    medium_impact = [b for b in blockers if b not in high_impact]
    
    return high_impact + medium_impact


def generate_blocker_resolution_goals(module: str) -> List[Goal]:
    """Generate sub-goals to resolve the most impactful blockers for a module.

    Queries the knowledge base for blocking dependencies and creates high-priority
    sub-goals tagged as 'blocker_resolution' to proactively address them.

    Args:
        module: The module to generate blocker resolution goals for.

    Returns:
        List of blocker resolution goals, each with HIGH priority and 'blocker_resolution' tag.
    """
    blockers = query_knowledge_base_for_blockers(module)
    resolution_goals = []
    
    if not blockers:
        logger.debug("No blockers found in knowledge base for module: %s", module)
        return resolution_goals
    
    # Generate resolution goals for top blockers (limit to 3 most impactful)
    for i, blocker in enumerate(blockers[:3]):
        goal = Goal(
            description=f"Resolve blocking dependency: {blocker} in {module}",
            priority=GoalPriority.HIGH,
            module=module,
            goal_type="blocker_resolution",
            tags=["blocker_resolution"]
        )
        resolution_goals.append(goal)
        logger.info(
            "Generated blocker resolution goal for %s: %s",
            module, blocker
        )
    
    return resolution_goals


def archive_goal_with_lesson(goal: Goal, lesson: str) -> None:
    """Record the goal as archived in the goal registry and store the lesson in the knowledge base.

    Args:
        goal: The goal to archive.
        lesson: The lesson learned from working on this goal.
    """
    # Mark the goal as archived and store the lesson
    goal.archived = True
    goal.lesson = lesson
    
    # Store in goal registry
    goal_key = f"{goal.module}:{goal.goal_type}:{goal.description}"
    goal_registry[goal_key] = goal
    
    # Store lesson in knowledge base
    lesson_key = f"lesson:{goal.module}:{goal.goal_type}"
    knowledge_base[lesson_key] = lesson
    
    # If this was a blocker resolution, also store blocker info
    if "blocker_resolution" in goal.tags:
        blocker_key = f"blocker:{goal.module}:{goal.description}"
        knowledge_base[blocker_key] = f"Resolved: {lesson}"
    
    logger.info(
        "Archived goal '%s' with lesson: %s",
        goal.description, lesson
    )


# Example usage (for testing)
if __name__ == "__main__":
    # Example metrics
    example_metrics = [
        SimulationMetrics(
            module="module_a",
            accuracy=0.65,
            has_unexpected_side_effects=True,
            coverage=0.3
        ),
        SimulationMetrics(
            module="module_b",
            accuracy=0.95,
            has_unexpected_side_effects=False,
            coverage=0.9
        ),
        SimulationMetrics(
            module="module_c",
            accuracy=0.75,
            has_unexpected_side_effects=True,
            coverage=0.5
        ),
    ]

    generated = generate_goals(example_metrics)
    print("Generated goals:")
    for goal in generated:
        print(f"  {goal}")

    print("\nPrioritized goals:")
    prioritized = prioritize_goals(generated)
    for goal in prioritized:
        print(f"  {goal}")

    # Test sub-goal generation with different strategies
    print("\nSub-goals for first goal (sequential):")
    if generated:
        sub_goals = generate_sub_goals(generated[0], decomposition_strategy="sequential")
        for sub_goal in sub_goals:
            deps = f" (depends on: {sub_goal.dependencies})" if sub_goal.dependencies else ""
            print(f"  {sub_goal}{deps}")

    print("\nSub-goals for first goal (parallel):")
    if generated:
        sub_goals = generate_sub_goals(generated[0], decomposition_strategy="parallel")
        for sub_goal in sub_goals:
            deps = f" (depends on: {sub_goal.dependencies})" if sub_goal.dependencies else ""
            print(f"  {sub_goal}{deps}")

    print("\nSub-goals for first goal (dependency-based):")
    if generated:
        sub_goals = generate_sub_goals(generated[0], decomposition_strategy="dependency-based")
        for sub_goal in sub_goals:
            deps = f" (depends on: {sub_goal.dependencies})" if sub_goal.dependencies else ""
            print(f"  {sub_goal}{deps}")

    # Test blocker resolution goals
    print("\nTesting blocker resolution goals:")
    # Add some blocker info to knowledge base
    knowledge_base["blocker:module_a:critical_dependency"] = "Critical: Module A depends on outdated library X"
    knowledge_base["blocker:module_c:high_impact"] = "High impact: Module C has circular dependency with Module D"
    
    for module in ["module_a", "module_b", "module_c"]:
        blocker_goals = generate_blocker_resolution_goals(module)
        if blocker_goals:
            print(f"  Blocker goals for {module}:")
            for bg in blocker_goals:
                print(f"    {bg} (tags: {bg.tags})")
        else:
            print(f"  No blocker goals for {module}")

    # Test archiving
    print("\nArchiving first goal with lesson:")
    if generated:
        archive_goal_with_lesson(generated[0], "Found critical accuracy issue in module_a")
        print(f"  Archived: {generated[0].archived}")
        print(f"  Lesson: {generated[0].lesson}")
        print(f"  Registry size: {len(goal_registry)}")
        print(f"  Knowledge base size: {len(knowledge_base)}")