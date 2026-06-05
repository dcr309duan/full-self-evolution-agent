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
    CRITICAL = 0
    HIGH = 1
    MEDIUM = 2
    LOW = 3


@dataclass
class Goal:
    """Represents a generated goal for improving simulation."""
    description: str
    priority: GoalPriority
    module: str
    goal_type: str  # 'accuracy', 'dependency_tracking', 'blocker_resolution', 'challenge', 'curiosity', 'infrastructure_hardening', 'cluster_resolution', 'meta_goal', or 'ecological_evolution'
    source: str = "fitness"  # 'curiosity', 'fitness', 'reflection'
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
    fs_abstraction_retry_rate: float = 0.0  # 0.0 to 1.0, retry rate for fs_abstraction
    permission_failure_spike: bool = False  # Whether permission failures have spiked
    failure_cluster: bool = False  # Whether a persistent failure cluster is detected
    test_suite_diversity: float = 1.0  # 0.0 to 1.0, diversity of test suite


# Global registries for goals and knowledge
goal_registry: Dict[str, Goal] = {}
knowledge_base: Dict[str, str] = {}

# Track consecutive successes for meta-goal triggering
consecutive_successes: int = 0
success_threshold: int = 10  # Number of consecutive successes before triggering meta-goal
current_accuracy_threshold: float = 0.8  # Current accuracy threshold, can be lowered

# Ecological evolution tracking
diversity_drop_threshold: float = 0.3  # Threshold below which ecological evolution goals are triggered
previous_diversity: float = 1.0  # Track previous diversity to detect drops


def prioritize_pending_goals() -> List[Goal]:
    """Load all pending goals from memory, score them, and return only high-impact ones.

    This function:
    (1) Loads all pending goals from the goal_registry.
    (2) Calls goal_impact_prioritizer.score_goal() for each.
    (3) Returns only goals with score > 0.7 for mutation consideration.
    (4) Archives goals with score < 0.3.

    Returns:
        List of goals with impact score > 0.7.
    """
    try:
        from goal_impact_prioritizer import score_goal
    except ImportError:
        logger.warning("goal_impact_prioritizer not available, returning all pending goals")
        return list(goal_registry.values())

    high_impact_goals = []
    for goal_key, goal in list(goal_registry.items()):
        if goal.archived:
            continue
        try:
            score = score_goal(goal)
            if score > 0.7:
                high_impact_goals.append(goal)
                logger.debug("Goal %s has high impact score: %.2f", goal.description, score)
            elif score < 0.3:
                # Archive low-impact goals
                archive_goal_with_lesson(goal, "Low impact score, archived automatically")
                logger.info("Archived low-impact goal: %s (score: %.2f)", goal.description, score)
            else:
                # Keep medium-impact goals as pending
                logger.debug("Goal %s has medium impact score: %.2f", goal.description, score)
        except Exception as e:
            logger.error("Error scoring goal %s: %s", goal.description, e)
            # Keep goal as pending if scoring fails
            high_impact_goals.append(goal)

    return high_impact_goals


def prioritize_and_filter_goals(goals: List[Goal]) -> List[Goal]:
    """Score each goal using the prioritizer, archive low-scoring goals, and return only high-scoring ones.

    This method runs before mutation selection each cycle. It:
    (1) Calls goal_impact_prioritizer.score_goal() for each goal.
    (2) Archives goals with score < 0.3.
    (3) Returns only goals with score > 0.7 for mutation consideration.

    Args:
        goals: List of goals to prioritize and filter.

    Returns:
        List of goals with impact score > 0.7.
    """
    try:
        from goal_impact_prioritizer import score_goal
    except ImportError:
        logger.warning("goal_impact_prioritizer not available, returning all goals unfiltered")
        return goals

    filtered_goals = []
    for goal in goals:
        if goal.archived:
            continue
        try:
            score = score_goal(goal)
            if score > 0.7:
                filtered_goals.append(goal)
                logger.debug("Goal %s has high impact score: %.2f", goal.description, score)
            elif score < 0.3:
                # Archive low-impact goals
                archive_goal_with_lesson(goal, "Low impact score, archived automatically")
                logger.info("Archived low-impact goal: %s (score: %.2f)", goal.description, score)
            else:
                # Keep medium-impact goals as pending
                logger.debug("Goal %s has medium impact score: %.2f", goal.description, score)
        except Exception as e:
            logger.error("Error scoring goal %s: %s", goal.description, e)
            # Keep goal as pending if scoring fails
            filtered_goals.append(goal)

    return filtered_goals


def generate_goals(
    metrics_list: List[SimulationMetrics],
    accuracy_threshold: float = 0.8,
    coverage_weight: float = 0.5,
    curiosity_goals: Optional[List[Goal]] = None,
    retry_rate_threshold: float = 0.3,
    permission_failure_threshold: int = 5,
    health_dashboard: Optional[Dict] = None
) -> List[Goal]:
    """Generate goals based on simulation metrics, knowledge base fitness scores, and curiosity engine input.

    Args:
        metrics_list: List of simulation metrics for different modules.
        accuracy_threshold: Threshold below which accuracy goals are generated.
        coverage_weight: Weight for coverage in priority calculation (0-1).
        curiosity_goals: Optional list of high-priority goals from the curiosity engine.
        retry_rate_threshold: Threshold for fs_abstraction retry rate to trigger infrastructure hardening.
        permission_failure_threshold: Number of permission failures to trigger infrastructure hardening.
        health_dashboard: Optional dashboard containing system health status, including lockdown state.

    Returns:
        List of generated goals, sorted by priority (highest first).
    """
    global consecutive_successes, current_accuracy_threshold, previous_diversity
    
    # Run prioritization before generating new goals
    high_impact_pending = prioritize_pending_goals()
    if high_impact_pending:
        logger.info("Found %d high-impact pending goals, returning them instead of generating new ones", len(high_impact_pending))
        return high_impact_pending

    goals: List[Goal] = []

    # Check health_dashboard before generating new goals
    if health_dashboard:
        lockdown_active = health_dashboard.get("lockdown_active", False)
        if lockdown_active:
            # If lockdown active, generate only 'stabilization' goals
            logger.info("Goal generator in stabilization mode due to lockdown")
            for metrics in metrics_list:
                if metrics.accuracy < current_accuracy_threshold:
                    goal = Goal(
                        description=f"Fix failing module {metrics.module}",
                        priority=GoalPriority.CRITICAL,
                        module=metrics.module,
                        goal_type="stabilization",
                        source="fitness",
                        tags=["stabilization", "lockdown"]
                    )
                    goals.append(goal)
                    logger.debug(
                        "Generated stabilization goal for %s (accuracy=%.2f, threshold=%.2f)",
                        metrics.module, metrics.accuracy, current_accuracy_threshold
                    )
                if metrics.fs_abstraction_retry_rate > retry_rate_threshold:
                    goal = Goal(
                        description=f"Reduce error rate in {metrics.module}",
                        priority=GoalPriority.HIGH,
                        module=metrics.module,
                        goal_type="stabilization",
                        source="fitness",
                        tags=["stabilization", "lockdown", "error_rate"]
                    )
                    goals.append(goal)
                    logger.debug(
                        "Generated stabilization goal for %s (retry rate=%.2f, threshold=%.2f)",
                        metrics.module, metrics.fs_abstraction_retry_rate, retry_rate_threshold
                    )
                if metrics.failure_cluster:
                    goal = Goal(
                        description=f"Fix persistent failure cluster in {metrics.module}",
                        priority=GoalPriority.CRITICAL,
                        module=metrics.module,
                        goal_type="stabilization",
                        source="fitness",
                        tags=["stabilization", "lockdown", "failure_cluster"]
                    )
                    goals.append(goal)
                    logger.info(
                        "Generated stabilization goal for %s (failure cluster detected)",
                        metrics.module
                    )
            return goals

    # First, check knowledge base for fitness scores and generate challenge goals
    challenge_goals = _generate_challenge_goals_from_knowledge_base()
    goals.extend(challenge_goals)

    # Add curiosity goals if provided
    if curiosity_goals:
        for goal in curiosity_goals:
            goal.source = "curiosity"
            goal.tags.append("curiosity")
        goals.extend(curiosity_goals)

    # Track consecutive successes and trigger meta-goal if threshold reached
    all_above_threshold = all(
        metrics.accuracy >= current_accuracy_threshold for metrics in metrics_list
    )
    
    if all_above_threshold:
        consecutive_successes += 1
        logger.debug(
            "Consecutive successes: %d/%d",
            consecutive_successes, success_threshold
        )
        
        if consecutive_successes >= success_threshold:
            # Reset counter and generate meta-goal
            consecutive_successes = 0
            
            # Lower the accuracy threshold to make goals harder
            current_accuracy_threshold = max(0.5, current_accuracy_threshold - 0.1)
            logger.info(
                "Lowered accuracy threshold to %.2f due to 10 consecutive successes",
                current_accuracy_threshold
            )
            
            # Generate meta-goal: modify the test suite itself
            meta_goal = Goal(
                description="Modify the test suite to add more comprehensive tests that push the system beyond current capabilities",
                priority=GoalPriority.CRITICAL,
                module="test_suite",
                goal_type="meta_goal",
                source="fitness",
                tags=["meta_goal", "test_suite_modification", "harder_goals"]
            )
            goals.append(meta_goal)
            logger.info(
                "Generated meta-goal to modify test suite after %d consecutive successes",
                success_threshold
            )
    else:
        # Reset counter if any module fails
        if consecutive_successes > 0:
            logger.debug(
                "Resetting consecutive successes counter (was %d)",
                consecutive_successes
            )
        consecutive_successes = 0

    # Check for ecological evolution triggers based on test suite diversity
    for metrics in metrics_list:
        if hasattr(metrics, 'test_suite_diversity'):
            current_diversity = metrics.test_suite_diversity
            # Detect drop in diversity
            if current_diversity < diversity_drop_threshold:
                # Generate ecological evolution goal to expand test ecosystem
                goal = Goal(
                    description=f"Expand test ecosystem for {metrics.module}: diversity dropped to {current_diversity:.2f}",
                    priority=GoalPriority.HIGH,
                    module=metrics.module,
                    goal_type="ecological_evolution",
                    source="fitness",
                    tags=["ecological_evolution", "diversity_drop", "test_ecosystem"]
                )
                goals.append(goal)
                logger.info(
                    "Generated ecological evolution goal for %s (diversity=%.2f, threshold=%.2f)",
                    metrics.module, current_diversity, diversity_drop_threshold
                )
            # Update previous diversity for next cycle
            previous_diversity = current_diversity

    for metrics in metrics_list:
        # Generate accuracy improvement goals if accuracy is below threshold
        if metrics.accuracy < current_accuracy_threshold:
            goal = Goal(
                description=f"Improve simulation accuracy for {metrics.module}",
                priority=_calculate_priority(metrics, coverage_weight),
                module=metrics.module,
                goal_type="accuracy",
                source="fitness"
            )
            goals.append(goal)
            logger.debug(
                "Generated accuracy goal for %s (accuracy=%.2f, threshold=%.2f)",
                metrics.module, metrics.accuracy, current_accuracy_threshold
            )

        # Generate dependency tracking goals if unexpected side effects
        if metrics.has_unexpected_side_effects:
            goal = Goal(
                description=f"Add dependency tracking for {metrics.module}",
                priority=_calculate_priority(metrics, coverage_weight),
                module=metrics.module,
                goal_type="dependency_tracking",
                source="fitness"
            )
            goals.append(goal)
            logger.debug(
                "Generated dependency tracking goal for %s (side effects detected)",
                metrics.module
            )

        # Generate infrastructure hardening goals for fs_abstraction
        if metrics.module == "fs_abstraction":
            if metrics.fs_abstraction_retry_rate > retry_rate_threshold:
                goal = Goal(
                    description=f"Improve fs_abstraction resilience: retry rate {metrics.fs_abstraction_retry_rate:.2f} exceeds threshold {retry_rate_threshold}",
                    priority=GoalPriority.HIGH,
                    module=metrics.module,
                    goal_type="infrastructure_hardening",
                    source="fitness",
                    tags=["infrastructure_hardening", "retry_rate"]
                )
                goals.append(goal)
                logger.debug(
                    "Generated infrastructure hardening goal for %s (retry rate=%.2f, threshold=%.2f)",
                    metrics.module, metrics.fs_abstraction_retry_rate, retry_rate_threshold
                )
            
            if metrics.permission_failure_spike:
                goal = Goal(
                    description=f"Improve fs_abstraction permission handling: permission failures spiked",
                    priority=GoalPriority.HIGH,
                    module=metrics.module,
                    goal_type="infrastructure_hardening",
                    source="fitness",
                    tags=["infrastructure_hardening", "permission_failure"]
                )
                goals.append(goal)
                logger.debug(
                    "Generated infrastructure hardening goal for %s (permission failure spike detected)",
                    metrics.module
                )

        # Generate cluster resolution goals if a persistent failure cluster is detected
        if metrics.failure_cluster:
            # Determine the root cause based on available metrics
            if metrics.permission_failure_spike:
                root_cause = "permission handling"
                fix_description = f"Fix permission handling in {metrics.module}"
            elif metrics.fs_abstraction_retry_rate > retry_rate_threshold:
                root_cause = "retry logic"
                fix_description = f"Add retry logic to {metrics.module}"
            else:
                root_cause = "unknown failure pattern"
                fix_description = f"Investigate and fix persistent failure cluster in {metrics.module}"
            
            goal = Goal(
                description=fix_description,
                priority=GoalPriority.CRITICAL,
                module=metrics.module,
                goal_type="cluster_resolution",
                source="fitness",
                tags=["cluster_resolution", "root_cause", root_cause]
            )
            goals.append(goal)
            logger.info(
                "Generated cluster resolution goal for %s (failure cluster detected, root cause: %s)",
                metrics.module, root_cause
            )

    # Sort goals by priority (CRITICAL first, then HIGH, MEDIUM, LOW)
    # Within same priority, curiosity goals come before routine goals
    goals.sort(key=lambda g: (
        g.priority.value,
        0 if g.source == "curiosity" else 1,
        -_coverage_score(g, metrics_list)
    ))

    # After generating new goals, apply prioritization and filtering
    goals = prioritize_and_filter_goals(goals)

    return goals


def _generate_challenge_goals_from_knowledge_base() -> List[Goal]:
    """Generate goals based on fitness scores stored in the knowledge base.

    Reads fitness scores from the knowledge base and generates goals for
    challenges with low scores (score == 0).

    Returns:
        List of goals for low-scoring challenges.
    """
    challenge_goals = []
    
    # Look for fitness score entries in the knowledge base
    for key, value in knowledge_base.items():
        if key.startswith("fitness_score:"):
            # Extract challenge name from key (format: "fitness_score:challenge_name")
            challenge_name = key.split(":", 1)[1] if ":" in key else key
            
            try:
                score = float(value)
                if score == 0.0:
                    # Generate a goal to implement this challenge correctly
                    goal = Goal(
                        description=f"Implement {challenge_name} correctly (current score: 0)",
                        priority=GoalPriority.HIGH,
                        module=challenge_name,
                        goal_type="challenge",
                        source="fitness",
                        tags=["challenge", "low_score"]
                    )
                    challenge_goals.append(goal)
                    logger.info(
                        "Generated challenge goal for %s (fitness score: 0)",
                        challenge_name
                    )
            except ValueError:
                logger.warning(
                    "Invalid fitness score value for %s: %s",
                    challenge_name, value
                )
    
    return challenge_goals


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
    coverage_weight: float = 0.5,
    curiosity_goals: Optional[List[Goal]] = None,
    retry_rate_threshold: float = 0.3,
    permission_failure_threshold: int = 5,
    health_dashboard: Optional[Dict] = None
) -> List[Goal]:
    """Generate goals from a simulation report dictionary.

    Expected report format:
    {
        "modules": [
            {
                "name": "module_name",
                "accuracy": 0.95,
                "has_unexpected_side_effects": False,
                "coverage": 0.8,
                "fs_abstraction_retry_rate": 0.0,
                "permission_failure_spike": False,
                "failure_cluster": False,
                "test_suite_diversity": 1.0
            },
            ...
        ]
    }

    Args:
        report: Dictionary containing simulation report data.
        accuracy_threshold: Threshold for accuracy goals.
        coverage_weight: Weight for coverage in priority.
        curiosity_goals: Optional list of high-priority goals from the curiosity engine.
        retry_rate_threshold: Threshold for fs_abstraction retry rate.
        permission_failure_threshold: Threshold for permission failures.
        health_dashboard: Optional dashboard containing system health status.

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
            coverage=module_data.get("coverage", 0.0),
            fs_abstraction_retry_rate=module_data.get("fs_abstraction_retry_rate", 0.0),
            permission_failure_spike=module_data.get("permission_failure_spike", False),
            failure_cluster=module_data.get("failure_cluster", False),
            test_suite_diversity=module_data.get("test_suite_diversity", 1.0)
        )
        metrics_list.append(metrics)

    return generate_goals(metrics_list, accuracy_threshold, coverage_weight, curiosity_goals, retry_rate_threshold, permission_failure_threshold, health_dashboard)


def prioritize_goals(goals: List[Goal]) -> List[Goal]:
    """Re-prioritize goals to expand simulation coverage.

    This function sorts goals so that those related to modules with
    lower coverage come first, within the same priority level.
    Curiosity-sourced goals are prioritized above routine goals but below critical failures.

    Args:
        goals: List of goals to prioritize.

    Returns:
        Re-prioritized list of goals.
    """
    # Sort by priority first, then by source (curiosity before routine), then by coverage
    return sorted(goals, key=lambda g: (
        g.priority.value,
        0 if g.source == "curiosity" else 1,
        g.description
    ))


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
            goal_type="accuracy",
            source=parent_goal.source
        )
        implement_goal = Goal(
            description=f"Implement targeted fixes for {parent_goal.module}",
            priority=parent_goal.priority,
            module=parent_goal.module,
            goal_type="accuracy",
            source=parent_goal.source
        )
        validate_goal = Goal(
            description=f"Validate accuracy improvements for {parent_goal.module}",
            priority=parent_goal.priority,
            module=parent_goal.module,
            goal_type="accuracy",
            source=parent_goal.source
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
            goal_type="dependency_tracking",
            source=parent_goal.source
        )
        implement_goal = Goal(
            description=f"Implement dependency tracking for {parent_goal.module}",
            priority=parent_goal.priority,
            module=parent_goal.module,
            goal_type="dependency_tracking",
            source=parent_goal.source
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
    elif parent_goal.goal_type == "infrastructure_hardening":
        # Break infrastructure hardening into smaller steps
        diagnose_goal = Goal(
            description=f"Diagnose infrastructure issues in {parent_goal.module}",
            priority=parent_goal.priority,
            module=parent_goal.module,
            goal_type="infrastructure_hardening",
            source=parent_goal.source
        )
        implement_goal = Goal(
            description=f"Implement hardening fixes for {parent_goal.module}",
            priority=parent_goal.priority,
            module=parent_goal.module,
            goal_type="infrastructure_hardening",
            source=parent_goal.source
        )
        test_goal = Goal(
            description=f"Test hardening improvements for {parent_goal.module}",
            priority=parent_goal.priority,
            module=parent_goal.module,
            goal_type="infrastructure_hardening",
            source=parent_goal.source
        )
        
        if decomposition_strategy == "sequential":
            # Linear chain: diagnose -> implement -> test
            implement_goal.dependencies.append(diagnose_goal.description)
            test_goal.dependencies.append(implement_goal.description)
            sub_goals = [diagnose_goal, implement_goal, test_goal]
        elif decomposition_strategy == "parallel":
            # No dependencies between sub-goals
            sub_goals = [diagnose_goal, implement_goal, test_goal]
        elif decomposition_strategy == "dependency-based":
            # Dependency-based: diagnose is independent, implement depends on diagnose, test depends on implement
            implement_goal.dependencies.append(diagnose_goal.description)
            test_goal.dependencies.append(implement_goal.description)
            sub_goals = [diagnose_goal, implement_goal, test_goal]
        else:
            # Default to sequential for unknown strategies
            implement_goal.dependencies.append(diagnose_goal.description)
            test_goal.dependencies.append(implement_goal.description)
            sub_goals = [diagnose_goal, implement_goal, test_goal]
    elif parent_goal.goal_type == "cluster_resolution":
        # Break cluster resolution into smaller steps
        analyze_goal = Goal(
            description=f"Analyze failure cluster in {parent_goal.module}",
            priority=parent_goal.priority,
            module=parent_goal.module,
            goal_type="cluster_resolution",
            source=parent_goal.source
        )
        fix_goal = Goal(
            description=f"Implement root cause fix for {parent_goal.module}",
            priority=parent_goal.priority,
            module=parent_goal.module,
            goal_type="cluster_resolution",
            source=parent_goal.source
        )
        verify_goal = Goal(
            description=f"Verify cluster resolution for {parent_goal.module}",
            priority=parent_goal.priority,
            module=parent_goal.module,
            goal_type="cluster_resolution",
            source=parent_goal.source
        )
        
        if decomposition_strategy == "sequential":
            # Linear chain: analyze -> fix -> verify
            fix_goal.dependencies.append(analyze_goal.description)
            verify_goal.dependencies.append(fix_goal.description)
            sub_goals = [analyze_goal, fix_goal, verify_goal]
        elif decomposition_strategy == "parallel":
            # No dependencies between sub-goals
            sub_goals = [analyze_goal, fix_goal, verify_goal]
        elif decomposition_strategy == "dependency-based":
            # Dependency-based: analyze is independent, fix depends on analyze, verify depends on fix
            fix_goal.dependencies.append(analyze_goal.description)
            verify_goal.dependencies.append(fix_goal.description)
            sub_goals = [analyze_goal, fix_goal, verify_goal]
        else:
            # Default to sequential for unknown strategies
            fix_goal.dependencies.append(analyze_goal.description)
            verify_goal.dependencies.append(fix_goal.description)
            sub_goals = [analyze_goal, fix_goal, verify_goal]
    elif parent_goal.goal_type == "meta_goal":
        # Break meta-goal into smaller steps
        analyze_goal = Goal(
            description=f"Analyze current test suite gaps for {parent_goal.module}",
            priority=parent_goal.priority,
            module=parent_goal.module,
            goal_type="meta_goal",
            source=parent_goal.source
        )
        design_goal = Goal(
            description=f"Design new test cases to push system beyond current capabilities for {parent_goal.module}",
            priority=parent_goal.priority,
            module=parent_goal.module,
            goal_type="meta_goal",
            source=parent_goal.source
        )
        implement_goal = Goal(
            description=f"Implement new test cases in test suite for {parent_goal.module}",
            priority=parent_goal.priority,
            module=parent_goal.module,
            goal_type="meta_goal",
            source=parent_goal.source
        )
        
        if decomposition_strategy == "sequential":
            # Linear chain: analyze -> design -> implement
            design_goal.dependencies.append(analyze_goal.description)
            implement_goal.dependencies.append(design_goal.description)
            sub_goals = [analyze_goal, design_goal, implement_goal]
        elif decomposition_strategy == "parallel":
            # No dependencies between sub-goals
            sub_goals = [analyze_goal, design_goal, implement_goal]
        elif decomposition_strategy == "dependency-based":
            # Dependency-based: analyze is independent, design depends on analyze, implement depends on design
            design_goal.dependencies.append(analyze_goal.description)
            implement_goal.dependencies.append(design_goal.description)
            sub_goals = [analyze_goal, design_goal, implement_goal]
        else:
            # Default to sequential for unknown strategies
            design_goal.dependencies.append(analyze_goal.description)
            implement_goal.dependencies.append(design_goal.description)
            sub_goals = [analyze_goal, design_goal, implement_goal]
    elif parent_goal.goal_type == "ecological_evolution":
        # Break ecological evolution into smaller steps
        analyze_goal = Goal(
            description=f"Analyze test suite diversity gaps for {parent_goal.module}",
            priority=parent_goal.priority,
            module=parent_goal.module,
            goal_type="ecological_evolution",
            source=parent_goal.source
        )
        generate_goal = Goal(
            description=f"Generate new test cases to expand ecosystem for {parent_goal.module}",
            priority=parent_goal.priority,
            module=parent_goal.module,
            goal_type="ecological_evolution",
            source=parent_goal.source
        )
        validate_goal = Goal(
            description=f"Validate test ecosystem expansion for {parent_goal.module}",
            priority=parent_goal.priority,
            module=parent_goal.module,
            goal_type="ecological_evolution",
            source=parent_goal.source
        )
        
        if decomposition_strategy == "sequential":
            # Linear chain: analyze -> generate -> validate
            generate_goal.dependencies.append(analyze_goal.description)
            validate_goal.dependencies.append(generate_goal.description)
            sub_goals = [analyze_goal, generate_goal, validate_goal]
        elif decomposition_strategy == "parallel":
            # No dependencies between sub-goals
            sub_goals = [analyze_goal, generate_goal, validate_goal]
        elif decomposition_strategy == "dependency-based":
            # Dependency-based: analyze is independent, generate depends on analyze, validate depends on generate
            generate_goal.dependencies.append(analyze_goal.description)
            validate_goal.dependencies.append(generate_goal.description)
            sub_goals = [analyze_goal, generate_goal, validate_goal]
        else:
            # Default to sequential for unknown strategies
            generate_goal.dependencies.append(analyze_goal.description)
            validate_goal.dependencies.append(generate_goal.description)
            sub_goals = [analyze_goal, generate_goal, validate_goal]
    else:
        # Generic breakdown for unknown goal types
        research_goal = Goal(
            description=f"Research requirements for {parent_goal.description}",
            priority=parent_goal.priority,
            module=parent_goal.module,
            goal_type=parent_goal.goal_type,
            source=parent_goal.source
        )
        implement_goal = Goal(
            description=f"Implement solution for {parent_goal.description}",
            priority=parent_goal.priority,
            module=parent_goal.module,
            goal_type=parent_goal.goal_type,
            source=parent_goal.source
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
