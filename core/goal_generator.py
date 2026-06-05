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
    goal_type: str  # 'accuracy', 'dependency_tracking', 'blocker_resolution', 'challenge', 'curiosity', 'infrastructure_hardening', 'cluster_resolution', 'meta_goal', 'ecological_evolution', 'ecological_gap', 'nash_escape', 'coordinated_mutation', 'adapt_to_pressure', 'nash_equilibrium_meta', or 'coordinated_multi_module_change'
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

# Ecological gap tracking
capability_coverage: Dict[str, float] = {}  # Maps capability names to their coverage scores (0.0 to 1.0)

# Environmental pressure tracking
environmental_pressure_active: bool = False  # Whether environmental pressure has been introduced
environmental_pressure_description: str = ""  # Description of the current environmental pressure

# Nash equilibrium tracking for meta-goal triggering
nash_equilibrium_detected: bool = False  # Whether Nash equilibrium has been detected
nash_equilibrium_modules: List[str] = []  # Modules stuck in Nash equilibrium
nash_equilibrium_analysis: Dict = {}  # Analysis details of the detected Nash equilibrium

# External goal queue for environmental pressure module
external_goal_queue: List[Goal] = []  # Queue for goals injected by external modules

# Coordinated multi-module change tracking
coordinated_change_candidates: Dict[str, List[str]] = {}  # Maps goal descriptions to lists of module names requiring changes


def add_external_goal(goal: Goal) -> bool:
    """Add an external goal to the goal queue after validation.

    This method allows the environmental pressure module to inject new goals
    into the system. It validates the goal format and adds it to the external
    goal queue, enabling the ecology engine to modify the fitness landscape.

    Args:
        goal: The Goal object to add. Must have a non-empty description,
              a valid GoalPriority, a non-empty module, and a valid goal_type.

    Returns:
        True if the goal was successfully added, False if validation failed.
    """
    # Validate goal format
    if not isinstance(goal, Goal):
        logger.error("add_external_goal: goal must be a Goal instance, got %s", type(goal).__name__)
        return False

    if not goal.description or not goal.description.strip():
        logger.error("add_external_goal: goal description cannot be empty")
        return False

    if not isinstance(goal.priority, GoalPriority):
        logger.error("add_external_goal: goal priority must be a GoalPriority enum value")
        return False

    if not goal.module or not goal.module.strip():
        logger.error("add_external_goal: goal module cannot be empty")
        return False

    valid_goal_types = [
        'accuracy', 'dependency_tracking', 'blocker_resolution', 'challenge',
        'curiosity', 'infrastructure_hardening', 'cluster_resolution', 'meta_goal',
        'ecological_evolution', 'ecological_gap', 'nash_escape', 'coordinated_mutation',
        'adapt_to_pressure', 'nash_equilibrium_meta', 'external_pressure',
        'coordinated_multi_module_change'
    ]
    if goal.goal_type not in valid_goal_types:
        logger.error("add_external_goal: invalid goal_type '%s', must be one of %s",
                     goal.goal_type, valid_goal_types)
        return False

    # Add the goal to the external queue
    external_goal_queue.append(goal)
    logger.info("External goal added to queue: %s (type: %s, priority: %s)",
                goal.description, goal.goal_type, goal.priority.name)
    return True


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


def generate_nash_escape_goal(stuck_modules: List[str], nash_analysis: Dict) -> Goal:
    """Generate a coordinated multi-module change proposal to escape Nash equilibrium.

    When called by the orchestrator after equilibrium detection, this method produces
    a goal specifically targeting the stuck modules with a coordinated multi-module
    change proposal.

    Args:
        stuck_modules: List of module names currently stuck in Nash equilibrium.
        nash_analysis: Dictionary containing Nash equilibrium analysis details,
            including fitness scores and interaction patterns.

    Returns:
        A Goal object with type 'nash_escape' that proposes coordinated changes
        across the stuck modules to break the equilibrium.
    """
    if not stuck_modules:
        logger.warning("generate_nash_escape_goal called with empty stuck_modules list")
        return None

    # Build a description that proposes coordinated changes
    modules_str = ", ".join(stuck_modules)
    description = (
        f"Coordinated multi-module change proposal to escape Nash equilibrium: "
        f"modules [{modules_str}] are stuck in a local optimum. "
        f"Propose simultaneous mutations across all stuck modules to break the "
        f"equilibrium and explore new fitness landscapes."
    )

    # Create the goal with high priority
    goal = Goal(
        description=description,
        priority=GoalPriority.CRITICAL,
        module=",".join(stuck_modules),  # Use comma-separated module names
        goal_type="nash_escape",
        source="fitness",
        tags=["nash_escape", "coordinated_change", "equilibrium_break"]
    )

    # Add nash analysis details as tags for reference
    if nash_analysis:
        for key, value in nash_analysis.items():
            if isinstance(value, str):
                goal.tags.append(f"nash_{key}:{value}")
            elif isinstance(value, (int, float)):
                goal.tags.append(f"nash_{key}:{value:.2f}")

    logger.info(
        "Generated Nash escape goal for modules %s with coordinated change proposal",
        stuck_modules
    )

    return goal


def generate_coordinated_mutation_goal(stuck_modules: List[str], nash_analysis: Dict) -> Goal:
    """Generate a coordinated mutation goal when Nash equilibrium is detected.

    This goal specifies multiple modules to mutate and the desired interaction
    improvement to break the equilibrium.

    Args:
        stuck_modules: List of module names currently stuck in Nash equilibrium.
        nash_analysis: Dictionary containing Nash equilibrium analysis details,
            including fitness scores and interaction patterns.

    Returns:
        A Goal object with type 'coordinated_mutation' that specifies multiple
        modules to mutate and the desired interaction improvement.
    """
    if not stuck_modules:
        logger.warning("generate_coordinated_mutation_goal called with empty stuck_modules list")
        return None

    # Build a description that specifies multiple modules and desired interaction improvement
    modules_str = ", ".join(stuck_modules)
    description = (
        f"Coordinated mutation across modules [{modules_str}] to escape Nash equilibrium. "
        f"Desired interaction improvement: break the local optimum by simultaneously "
        f"mutating all stuck modules to explore new interaction patterns and fitness landscapes."
    )

    # Create the goal with critical priority
    goal = Goal(
        description=description,
        priority=GoalPriority.CRITICAL,
        module=",".join(stuck_modules),  # Use comma-separated module names
        goal_type="coordinated_mutation",
        source="fitness",
        tags=["coordinated_mutation", "nash_equilibrium", "multi_module_mutation", "interaction_improvement"]
    )

    # Add nash analysis details as tags for reference
    if nash_analysis:
        for key, value in nash_analysis.items():
            if isinstance(value, str):
                goal.tags.append(f"nash_{key}:{value}")
            elif isinstance(value, (int, float)):
                goal.tags.append(f"nash_{key}:{value:.2f}")

    logger.info(
        "Generated coordinated mutation goal for modules %s with desired interaction improvement",
        stuck_modules
    )

    return goal


def generate_nash_equilibrium_meta_goal(stuck_modules: List[str], nash_analysis: Dict) -> Goal:
    """Generate a meta-goal when Nash equilibrium is detected.

    This meta-goal triggers a higher-level strategy to break the Nash equilibrium
    by modifying the test suite or evaluation criteria to force exploration of
    new fitness landscapes.

    Args:
        stuck_modules: List of module names currently stuck in Nash equilibrium.
        nash_analysis: Dictionary containing Nash equilibrium analysis details,
            including fitness scores and interaction patterns.

    Returns:
        A Goal object with type 'nash_equilibrium_meta' that specifies the
        meta-level strategy to break the equilibrium.
    """
    if not stuck_modules:
        logger.warning("generate_nash_equilibrium_meta_goal called with empty stuck_modules list")
        return None

    modules_str = ", ".join(stuck_modules)
    description = (
        f"Nash equilibrium detected in modules [{modules_str}]. "
        f"Meta-goal: Modify test suite or evaluation criteria to break the equilibrium "
        f"and force exploration of new fitness landscapes. Current fitness scores: "
        f"{nash_analysis.get('fitness_scores', 'unknown')}."
    )

    goal = Goal(
        description=description,
        priority=GoalPriority.CRITICAL,
        module="test_suite",
        goal_type="nash_equilibrium_meta",
        source="fitness",
        tags=["nash_equilibrium_meta", "test_suite_modification", "equilibrium_break", "meta_goal"]
    )

    # Add nash analysis details as tags for reference
    if nash_analysis:
        for key, value in nash_analysis.items():
            if isinstance(value, str):
                goal.tags.append(f"nash_{key}:{value}")
            elif isinstance(value, (int, float)):
                goal.tags.append(f"nash_{key}:{value:.2f}")

    logger.info(
        "Generated Nash equilibrium meta-goal for modules %s",
        stuck_modules
    )

    return goal


def generate_adapt_to_pressure_goal(pressure_description: str) -> Goal:
    """Generate a goal to adapt to a new environmental pressure.

    This goal is triggered when ecology_engine.introduce_environmental_pressure()
    has been called. It forces the agent to evolve as the tests change.

    Args:
        pressure_description: Description of the new environmental pressure.

    Returns:
        A Goal object with type 'adapt_to_pressure' that specifies the adaptation needed.
    """
    if not pressure_description:
        logger.warning("generate_adapt_to_pressure_goal called with empty pressure_description")
        return None

    description = (
        f"Adapt to new environmental pressure: {pressure_description}. "
        f"Update the relevant module to pass the modified test."
    )

    goal = Goal(
        description=description,
        priority=GoalPriority.CRITICAL,
        module="test_suite",  # The test suite is the primary module affected
        goal_type="adapt_to_pressure",
        source="fitness",
        tags=["adapt_to_pressure", "environmental_pressure", "test_evolution"]
    )

    logger.info(
        "Generated adapt_to_pressure goal for pressure: %s",
        pressure_description
    )

    return goal


def generate_coordinated_multi_module_change_goal(modules: List[str], description: str) -> Goal:
    """Generate a coordinated multi-module change goal that requires changes to 3+ modules simultaneously.

    This goal type is designed to be requested by the nash handler or other components
    that need to coordinate changes across multiple modules to achieve a system-wide improvement.
    The goal ensures that the goal generator can produce goals requiring changes to 3 or more
    modules simultaneously.

    Args:
        modules: List of module names that need to be changed (must be 3 or more).
        description: Description of the coordinated change needed.

    Returns:
        A Goal object with type 'coordinated_multi_module_change' that specifies the
        coordinated changes needed across multiple modules.
    """
    if not modules or len(modules) < 3:
        logger.warning(
            "generate_coordinated_multi_module_change_goal called with %d modules, need at least 3",
            len(modules) if modules else 0
        )
        return None

    if not description or not description.strip():
        logger.warning("generate_coordinated_multi_module_change_goal called with empty description")
        return None

    modules_str = ", ".join(modules)
    full_description = (
        f"Coordinated multi-module change: {description}. "
        f"Requires simultaneous changes to modules [{modules_str}] to achieve system-wide improvement. "
        f"All {len(modules)} modules must be modified together to avoid breaking dependencies."
    )

    goal = Goal(
        description=full_description,
        priority=GoalPriority.CRITICAL,
        module=",".join(modules),  # Use comma-separated module names
        goal_type="coordinated_multi_module_change",
        source="fitness",
        tags=["coordinated_multi_module_change", "multi_module", "system_wide_change"]
    )

    # Add individual module tags for tracking
    for module in modules:
        goal.tags.append(f"module:{module}")

    # Register the goal in the coordinated change candidates for tracking
    coordinated_change_candidates[full_description] = modules

    logger.info(
        "Generated coordinated multi-module change goal for %d modules: %s",
        len(modules),
        modules_str
    )

    return goal


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
    global consecutive_successes, current_accuracy_threshold, previous_diversity, capability_coverage
    global environmental_pressure_active, environmental_pressure_description
    global nash_equilibrium_detected, nash_equilibrium_modules, nash_equilibrium_analysis
    global external_goal_queue, coordinated_change_candidates
    
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

    # Check if environmental pressure is active and generate adapt_to_pressure goal
    if environmental_pressure_active and environmental_pressure_description:
        adapt_goal = generate_adapt_to_pressure_goal(environmental_pressure_description)
        if adapt_goal:
            goals.append(adapt_goal)
            logger.info(
                "Generated adapt_to_pressure goal for pressure: %s",
                environmental_pressure_description
            )

    # Check if Nash equilibrium is detected and generate appropriate goals
    if nash_equilibrium_detected and nash_equilibrium_modules:
        # Generate Nash escape goal to actively seek to break out of local optima
        nash_escape_goal = generate_nash_escape_goal(
            nash_equilibrium_modules,
            nash_equilibrium_analysis
        )
        if nash_escape_goal:
            goals.append(nash_escape_goal)
            logger.info(
                "Generated Nash escape goal for modules %s to break equilibrium",
                nash_equilibrium_modules
            )
        
        # Also generate the meta-goal for higher-level strategy
        nash_meta_goal = generate_nash_equilibrium_meta_goal(
            nash_equilibrium_modules,
            nash_equilibrium_analysis
        )
        if nash_meta_goal:
            goals.append(nash_meta_goal)
            logger.info(
                "Generated Nash equilibrium meta-goal for modules %s",
                nash_equilibrium_modules
            )
        
        # Generate coordinated mutation goal as well
        coordinated_mutation_goal = generate_coordinated_mutation_goal(
            nash_equilibrium_modules,
            nash_equilibrium_analysis
        )
        if coordinated_mutation_goal:
            goals.append(coordinated_mutation_goal)
            logger.info(
                "Generated coordinated mutation goal for modules %s",
                nash_equilibrium_modules
            )
        
        # Generate coordinated multi-module change goal if there are 3+ modules
        if len(nash_equilibrium_modules) >= 3:
            coordinated_multi_module_goal = generate_coordinated_multi_module_change_goal(
                nash_equilibrium_modules,
                f"Break Nash equilibrium across {len(nash_equilibrium_modules)} modules"
            )
            if coordinated_multi_module_goal:
                goals.append(coordinated_multi_module_goal)
                logger.info(
                    "Generated coordinated multi-module change goal for %d modules",
                    len(nash_equilibrium_modules)
                )
        
        # Reset the flag after generating the goals to avoid duplicate generation
        nash_equilibrium_detected = False

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

    # Check for ecological gap triggers after ecology engine evaluation
    for metrics in metrics_list:
        if hasattr(metrics, 'test_suite_diversity'):
            current_diversity = metrics.test_suite_diversity
            # If diversity drops below threshold, find the least-covered capability
            if current_diversity < diversity_drop_threshold:
                # Determine the least-covered capability from capability_coverage
                if capability_coverage:
                    least_covered_capability = min(capability_coverage, key=capability_coverage.get)
                    least_covered_score = capability_coverage[least_covered_capability]
                    
                    # Generate ecological gap goal to create tests for the least-covered capability
                    goal = Goal(
                        description=f"Create tests for least-covered capability '{least_covered_capability}' in {metrics.module} (coverage: {least_covered_score:.2f})",
                        priority=GoalPriority.HIGH,
                        module=metrics.module,
                        goal_type="ecological_gap",
                        source="fitness",
                        tags=["ecological_gap", "capability_coverage", "test_creation"]
                    )
                    goals.append(goal)
                    logger.info(
                        "Generated ecological gap goal for %s: least-covered capability '%s' (coverage=%.2f, diversity=%.2f, threshold=%.2f)",
                        metrics.module, least_covered_capability, least_covered_score, current_diversity, diversity_drop_threshold
                    )
                else:
                    # If no capability coverage data, generate a generic ecological gap goal
                    goal = Goal(
                        description=f"Assess and expand capability coverage for {metrics.module} to improve test suite diversity",
                        priority=GoalPriority.HIGH,
                        module=metrics.module,
                        goal_type="ecological_gap",
                        source="fitness",
                        tags=["ecological_gap", "capability_assessment", "test_creation"]
                    )
                    goals.append(goal)
                    logger.info(
                        "Generated ecological gap goal for %s (no capability coverage data available, diversity=%.2f, threshold=%.2f)",
                        metrics.module, current_diversity, diversity_drop_threshold
                    )

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

    # Add external goals from the queue to the generated goals
    if external_goal_queue:
        logger.info("Adding %d external goals from queue to generated goals", len(external_goal_queue))
        goals.extend(external_goal_queue)
        external_goal_queue.clear()  # Clear the queue after processing

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
    coverage_deficit