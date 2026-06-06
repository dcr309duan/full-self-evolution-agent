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
import random

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
    goal_type: str  # 'accuracy', 'dependency_tracking', 'blocker_resolution', 'challenge',
                    # 'curiosity', 'infrastructure_hardening', 'cluster_resolution', 'meta_goal',
                    # 'ecological_evolution', 'ecological_gap', 'nash_escape', 'coordinated_mutation',
                    # 'adapt_to_pressure', 'nash_equilibrium_meta', 'coordinated_multi_module_change',
                    # 'ecological_pressure', 'multi_module_change', 'COORDINATED_MULTI_MODULE',
                    # 'nash_equilibrium_detection', 'AV_RESEARCH', or 'GAME_THEORY'
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

# Test coverage tracking for ecological pressure goals
test_coverage_map: Dict[str, List[str]] = {}  # Maps module names to lists of tested areas

# Goal prioritization settings for Nash equilibrium coordination
nash_coordination_bonus: float = 0.2  # Bonus score for coordinated multi-module goals when Nash equilibrium is detected
single_module_penalty: float = 0.3  # Penalty applied to single-module goals when Nash equilibrium is active
nash_coordination_min_modules: int = 2  # Minimum number of modules for a goal to be considered coordinated

# COORDINATED_MULTI_MODULE goal tracking
coordinated_multi_module_active: bool = False  # Whether a COORDINATED_MULTI_MODULE goal is active
coordinated_multi_module_modules: List[str] = []  # Modules involved in the active COORDINATED_MULTI_MODULE goal
coordinated_multi_module_description: str = ""  # Description of the active COORDINATED_MULTI_MODULE goal

# AV_RESEARCH goal tracking
av_research_active: bool = False  # Whether an AV_RESEARCH goal is active
av_research_description: str = ""  # Description of the active AV_RESEARCH goal
av_knowledge_gaps: Dict[str, List[str]] = {}  # Maps module names to lists of missing AV domain knowledge areas

# GAME_THEORY goal tracking
game_theory_active: bool = False  # Whether a GAME_THEORY goal is active
game_theory_description: str = ""  # Description of the active GAME_THEORY goal
game_theory_completed: bool = False  # Whether the GAME_THEORY goal has been completed


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
        'coordinated_multi_module_change', 'ecological_pressure', 'multi_module_change',
        'COORDINATED_MULTI_MODULE', 'nash_equilibrium_detection', 'AV_RESEARCH',
        'GAME_THEORY'
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


def _is_coordinated_goal(goal: Goal) -> bool:
    """Check if a goal involves multiple modules (coordinated multi-module change).

    Args:
        goal: The goal to check.

    Returns:
        True if the goal involves multiple modules, False otherwise.
    """
    # Check if the module field contains multiple modules (comma-separated)
    if "," in goal.module:
        modules = [m.strip() for m in goal.module.split(",") if m.strip()]
        return len(modules) >= nash_coordination_min_modules
    
    # Check tags for coordinated change indicators
    coordinated_tags = ["coordinated_multi_module_change", "nash_escape", "coordinated_mutation", "multi_module", "multi_module_change", "COORDINATED_MULTI_MODULE"]
    for tag in goal.tags:
        if tag in coordinated_tags:
            return True
    
    # Check goal type for coordinated types
    coordinated_types = ["coordinated_multi_module_change", "nash_escape", "coordinated_mutation", "nash_equilibrium_meta", "multi_module_change", "COORDINATED_MULTI_MODULE"]
    if goal.goal_type in coordinated_types:
        return True
    
    return False


def _is_single_module_goal(goal: Goal) -> bool:
    """Check if a goal targets a single module only.

    Args:
        goal: The goal to check.

    Returns:
        True if the goal targets a single module, False otherwise.
    """
    # Check if the module field contains a single module
    if "," in goal.module:
        return False
    
    # Check if the goal type is typically single-module
    single_module_types = ["accuracy", "dependency_tracking", "infrastructure_hardening", "cluster_resolution"]
    if goal.goal_type in single_module_types:
        return True
    
    return False


def prioritize_pending_goals() -> List[Goal]:
    """Load all pending goals from memory, score them, and return only high-impact ones.

    This function:
    (1) Loads all pending goals from the goal_registry.
    (2) Calls goal_impact_prioritizer.score_goal() for each.
    (3) Applies Nash equilibrium coordination bonus/penalty if Nash equilibrium is detected.
    (4) Returns only goals with score > 0.7 for mutation consideration.
    (5) Archives goals with score < 0.3.

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
            
            # Apply Nash equilibrium coordination bonus/penalty
            if nash_equilibrium_detected:
                if _is_coordinated_goal(goal):
                    # Boost coordinated multi-module goals when Nash equilibrium is detected
                    score += nash_coordination_bonus
                    logger.debug(
                        "Applied Nash coordination bonus to goal '%s': score increased to %.2f",
                        goal.description, score
                    )
                elif _is_single_module_goal(goal):
                    # Penalize single-module goals when Nash equilibrium is detected
                    score -= single_module_penalty
                    logger.debug(
                        "Applied single-module penalty to goal '%s': score decreased to %.2f",
                        goal.description, score
                    )
            
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
    (2) Applies Nash equilibrium coordination bonus/penalty if Nash equilibrium is detected.
    (3) Archives goals with score < 0.3.
    (4) Returns only goals with score > 0.7 for mutation consideration.

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
            
            # Apply Nash equilibrium coordination bonus/penalty
            if nash_equilibrium_detected:
                if _is_coordinated_goal(goal):
                    # Boost coordinated multi-module goals when Nash equilibrium is detected
                    score += nash_coordination_bonus
                    logger.debug(
                        "Applied Nash coordination bonus to goal '%s': score increased to %.2f",
                        goal.description, score
                    )
                elif _is_single_module_goal(goal):
                    # Penalize single-module goals when Nash equilibrium is detected
                    score -= single_module_penalty
                    logger.debug(
                        "Applied single-module penalty to goal '%s': score decreased to %.2f",
                        goal.description, score
                    )
            
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


def generate_multi_module_change_goal(stuck_modules: List[str], nash_analysis: Dict) -> Goal:
    """Generate a multi_module_change goal when Nash equilibrium is detected.

    This goal triggers when Nash equilibrium is detected and includes the specific
    modules and coordinated changes needed to break the equilibrium.

    Args:
        stuck_modules: List of module names currently stuck in Nash equilibrium.
        nash_analysis: Dictionary containing Nash equilibrium analysis details,
            including fitness scores and interaction patterns.

    Returns:
        A Goal object with type 'multi_module_change' that specifies the modules
        and coordinated changes needed.
    """
    if not stuck_modules:
        logger.warning("generate_multi_module_change_goal called with empty stuck_modules list")
        return None

    modules_str = ", ".join(stuck_modules)
    
    # Extract coordinated changes from nash_analysis if available
    coordinated_changes = nash_analysis.get('coordinated_changes', [])
    if coordinated_changes:
        changes_str = "; ".join(coordinated_changes)
        description = (
            f"Multi-module change required to escape Nash equilibrium: "
            f"modules [{modules_str}] are stuck. "
            f"Coordinated changes needed: {changes_str}. "
            f"All modules must be modified simultaneously to break the local optimum."
        )
    else:
        description = (
            f"Multi-module change required to escape Nash equilibrium: "
            f"modules [{modules_str}] are stuck in a local optimum. "
            f"Coordinated changes needed across all modules to break the equilibrium "
            f"and explore new fitness landscapes."
        )

    goal = Goal(
        description=description,
        priority=GoalPriority.CRITICAL,
        module=",".join(stuck_modules),
        goal_type="multi_module_change",
        source="fitness",
        tags=["multi_module_change", "nash_equilibrium", "coordinated_change", "equilibrium_break"]
    )

    # Add nash analysis details as tags for reference
    if nash_analysis:
        for key, value in nash_analysis.items():
            if isinstance(value, str):
                goal.tags.append(f"nash_{key}:{value}")
            elif isinstance(value, (int, float)):
                goal.tags.append(f"nash_{key}:{value:.2f}")
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, str):
                        goal.tags.append(f"nash_{key}:{item}")

    logger.info(
        "Generated multi_module_change goal for modules %s with coordinated changes",
        stuck_modules
    )

    return goal


def generate_ecological_pressure_goals() -> List[Goal]:
    """Generate ecological pressure goals by analyzing test coverage gaps.

    This function analyzes the current test coverage map to identify areas
    with no tests or low coverage, and generates goals to add tests in those
    areas. It creates new environmental pressures by modifying the test suite
    to add constraints that don't yet exist.

    Returns:
        List of Goal objects with type 'ecological_pressure' that specify
        new test constraints to add.
    """
    ecological_pressure_goals = []
    
    if not test_coverage_map:
        logger.info("No test coverage data available, generating generic ecological pressure goal")
        goal = Goal(
            description="Create comprehensive test coverage map for all modules to identify untested areas",
            priority=GoalPriority.HIGH,
            module="test_suite",
            goal_type="ecological_pressure",
            source="fitness",
            tags=["ecological_pressure", "coverage_analysis", "test_creation"]
        )
        ecological_pressure_goals.append(goal)
        return ecological_pressure_goals

    for module_name, tested_areas in test_coverage_map.items():
        # Identify areas with no tests
        untested_areas = []
        known_areas = ["error_handling", "edge_cases", "performance", "security", "integration", "boundary_conditions"]
        
        for area in known_areas:
            if area not in tested_areas:
                untested_areas.append(area)
        
        if untested_areas:
            areas_str = ", ".join(untested_areas)
            description = (
                f"Add environmental pressure to module '{module_name}': create new tests for "
                f"untested areas [{areas_str}]. This will introduce new constraints that the "
                f"system must adapt to, expanding the fitness landscape."
            )
            goal = Goal(
                description=description,
                priority=GoalPriority.HIGH,
                module=module_name,
                goal_type="ecological_pressure",
                source="fitness",
                tags=["ecological_pressure", "test_coverage_gap", "new_constraints", f"module:{module_name}"]
            )
            ecological_pressure_goals.append(goal)
            logger.info(
                "Generated ecological pressure goal for module '%s' with untested areas: %s",
                module_name, areas_str
            )
        else:
            # If all known areas are tested, generate a goal to find new edge cases
            description = (
                f"Add environmental pressure to module '{module_name}': all known areas are tested, "
                f"so create novel edge cases and stress tests to push the system beyond current "
                f"capabilities and introduce new constraints."
            )
            goal = Goal(
                description=description,
                priority=GoalPriority.MEDIUM,
                module=module_name,
                goal_type="ecological_pressure",
                source="fitness",
                tags=["ecological_pressure", "novel_edge_cases", "stress_testing", f"module:{module_name}"]
            )
            ecological_pressure_goals.append(goal)
            logger.info(
                "Generated ecological pressure goal for module '%s' to create novel edge cases",
                module_name
            )

    return ecological_pressure_goals


def _generate_challenge_goals_from_knowledge_base() -> List[Goal]:
    """Generate challenge goals based on knowledge base entries.

    This internal function queries the knowledge base for fitness scores and
    generates challenge goals for modules with low fitness scores.

    Returns:
        List of Goal objects with type 'challenge' for low-fitness modules.
    """
    challenge_goals = []
    for module, fitness_str in knowledge_base.items():
        try:
            fitness = float(fitness_str)
            if fitness < 0.5:  # Low fitness threshold
                goal = Goal(
                    description=f"Improve fitness of module {module} from {fitness:.2f} to above 0.5",
                    priority=GoalPriority.HIGH,
                    module=module,
                    goal_type="challenge",
                    source="fitness",
                    tags=["challenge", "fitness_improvement", f"module:{module}"]
                )
                challenge_goals.append(goal)
                logger.debug("Generated challenge goal for module %s (fitness=%.2f)", module, fitness)
        except (ValueError, TypeError):
            logger.warning("Invalid fitness value for module %s: %s", module, fitness_str)
    return challenge_goals


def archive_goal_with_lesson(goal: Goal, lesson: str) -> None:
    """Archive a goal with a lesson learned.

    Args:
        goal: The goal to archive.
        lesson: The lesson to associate with the archived goal.
    """
    goal.archived = True
    goal.lesson = lesson
    logger.info("Archived goal '%s' with lesson: %s", goal.description, lesson)


def generate_coordinated_multi_module_goal(modules: List[str], description: str) -> Goal:
    """Generate a COORDINATED_MULTI_MODULE goal that the NashDetector can request.

    When this goal is active, the mutation system should generate changes across
    multiple modules simultaneously rather than one at a time. This goal type
    is designed to be requested by the NashDetector to break Nash equilibria
    by forcing coordinated mutations across stuck modules.

    Args:
        modules: List of module names that need to be changed simultaneously.
        description: Description of the coordinated change needed.

    Returns:
        A Goal object with type 'COORDINATED_MULTI_MODULE' that specifies the
        coordinated changes needed across multiple modules.
    """
    if not modules or len(modules) < 2:
        logger.warning(
            "generate_coordinated_multi_module_goal called with %d modules, need at least 2",
            len(modules) if modules else 0
        )
        return None

    if not description or not description.strip():
        logger.warning("generate_coordinated_multi_module_goal called with empty description")
        return None

    modules_str = ", ".join(modules)
    full_description = (
        f"COORDINATED_MULTI_MODULE: {description}. "
        f"Requires simultaneous changes to modules [{modules_str}] to break Nash equilibrium. "
        f"All {len(modules)} modules must be modified together to escape local optima."
    )

    goal = Goal(
        description=full_description,
        priority=GoalPriority.CRITICAL,
        module=",".join(modules),  # Use comma-separated module names
        goal_type="COORDINATED_MULTI_MODULE",
        source="fitness",
        tags=["COORDINATED_MULTI_MODULE", "multi_module", "nash_escape", "coordinated_change"]
    )

    # Add individual module tags for tracking
    for module in modules:
        goal.tags.append(f"module:{module}")

    # Register the goal in the coordinated change candidates for tracking
    coordinated_change_candidates[full_description] = modules

    # Set the global tracking variables for COORDINATED_MULTI_MODULE
    global coordinated_multi_module_active, coordinated_multi_module_modules, coordinated_multi_module_description
    coordinated_multi_module_active = True
    coordinated_multi_module_modules = modules
    coordinated_multi_module_description = full_description

    logger.info(
        "Generated COORDINATED_MULTI_MODULE goal for %d modules: %s",
        len(modules),
        modules_str
    )

    return goal


def is_coordinated_multi_module_active() -> bool:
    """Check if a COORDINATED_MULTI_MODULE goal is currently active.

    Returns:
        True if a COORDINATED_MULTI_MODULE goal is active, False otherwise.
    """
    return coordinated_multi_module_active


def get_coordinated_multi_module_modules() -> List[str]:
    """Get the list of modules involved in the active COORDINATED_MULTI_MODULE goal.

    Returns:
        List of module names involved in the active COORDINATED_MULTI_MODULE goal,
        or an empty list if no such goal is active.
    """
    return coordinated_multi_module_modules


def clear_coordinated_multi_module_goal() -> None:
    """Clear the active COORDINATED_MULTI_MODULE goal.

    This should be called when the coordinated multi-module mutation has been
    completed or the goal is no longer relevant.
    """
    global coordinated_multi_module_active, coordinated_multi_module_modules, coordinated_multi_module_description
    coordinated_multi_module_active = False
    coordinated_multi_module_modules = []
    coordinated_multi_module_description = ""
    logger.info("Cleared active COORDINATED_MULTI_MODULE goal")


def generate_nash_equilibrium_detection_goal(stuck_modules: List[str], nash_analysis: Dict) -> Goal:
    """Generate a goal when Nash equilibrium is detected in the system.

    This goal type is registered as 'nash_equilibrium_detection' and is triggered
    when the Nash detector identifies that modules are stuck in a local optimum.
    The goal includes the specific modules involved and the analysis details
    to help break the equilibrium.

    Args:
        stuck_modules: List of module names currently stuck in Nash equilibrium.
        nash_analysis: Dictionary containing Nash equilibrium analysis details,
            including fitness scores and interaction patterns.

    Returns:
        A Goal object with type 'nash_equilibrium_detection' that specifies the
        detected equilibrium and the modules involved.
    """
    if not stuck_modules:
        logger.warning("generate_nash_equilibrium_detection_goal called with empty stuck_modules list")
        return None

    modules