from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from enum import Enum

# Import internal components (assuming they exist in the same package)
from .goal_parser import GoalParser
from .dependency_resolver import DependencyResolver
from .readiness_checker import ReadinessChecker
from .priority_assigner import PriorityAssigner


class GoalStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    BLOCKED = "blocked"


@dataclass
class SubGoal:
    id: str
    description: str
    effort_estimate: float  # in story points or hours
    priority: int
    dependencies: List[str] = field(default_factory=list)
    status: GoalStatus = GoalStatus.PENDING
    readiness_score: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DecompositionPlan:
    goal_id: str
    abstract_goal: str
    sub_goals: List[SubGoal]
    total_effort: float
    dependency_graph: Dict[str, List[str]]  # node -> list of dependencies
    visualization_data: Dict[str, Any]  # For graph visualization (nodes, edges, etc.)


class GoalDecompositionOrchestrator:
    """
    Orchestrates the decomposition of an abstract goal into a structured plan.
    Follows the pipeline: GoalParser -> DependencyResolver -> ReadinessChecker -> PriorityAssigner.
    """

    def __init__(
        self,
        goal_parser: Optional[GoalParser] = None,
        dependency_resolver: Optional[DependencyResolver] = None,
        readiness_checker: Optional[ReadinessChecker] = None,
        priority_assigner: Optional[PriorityAssigner] = None,
    ):
        self.goal_parser = goal_parser or GoalParser()
        self.dependency_resolver = dependency_resolver or DependencyResolver()
        self.readiness_checker = readiness_checker or ReadinessChecker()
        self.priority_assigner = priority_assigner or PriorityAssigner()

    def decompose(self, abstract_goal: str, context: Optional[Dict[str, Any]] = None) -> DecompositionPlan:
        """
        Main entry point: accepts an abstract goal and returns a complete DecompositionPlan.

        Args:
            abstract_goal: The high-level goal to decompose.
            context: Optional dictionary with additional context (e.g., constraints, resources).

        Returns:
            DecompositionPlan with ordered sub-goals, estimated effort, and visualization data.
        """
        context = context or {}

        # Step 1: Parse the abstract goal into sub-goals
        parsed_sub_goals = self.goal_parser.parse(abstract_goal, context)

        # Step 2: Resolve dependencies between sub-goals
        sub_goals_with_deps = self.dependency_resolver.resolve(parsed_sub_goals, context)

        # Step 3: Check readiness of each sub-goal
        sub_goals_with_readiness = self.readiness_checker.check(sub_goals_with_deps, context)

        # Step 4: Assign priorities and order sub-goals
        ordered_sub_goals = self.priority_assigner.assign(sub_goals_with_readiness, context)

        # Build final plan
        plan = self._build_plan(abstract_goal, ordered_sub_goals)
        return plan

    def _build_plan(self, abstract_goal: str, sub_goals: List[SubGoal]) -> DecompositionPlan:
        """Construct the DecompositionPlan from processed sub-goals."""
        total_effort = sum(sg.effort_estimate for sg in sub_goals)

        # Build dependency graph
        dependency_graph: Dict[str, List[str]] = {}
        for sg in sub_goals:
            dependency_graph[sg.id] = sg.dependencies

        # Build visualization data (nodes and edges)
        nodes = []
        edges = []
        for sg in sub_goals:
            nodes.append({
                "id": sg.id,
                "label": sg.description[:50],  # Truncate for display
                "priority": sg.priority,
                "effort": sg.effort_estimate,
                "status": sg.status.value,
                "readiness": sg.readiness_score,
            })
            for dep_id in sg.dependencies:
                edges.append({
                    "from": dep_id,
                    "to": sg.id,
                    "type": "dependency",
                })

        visualization_data = {
            "nodes": nodes,
            "edges": edges,
            "layout": "hierarchical",  # Suggest a layout for visualization
        }

        # Generate a simple goal ID
        goal_id = f"goal_{hash(abstract_goal) & 0xFFFFFFFF:08x}"

        return DecompositionPlan(
            goal_id=goal_id,
            abstract_goal=abstract_goal,
            sub_goals=sub_goals,
            total_effort=total_effort,
            dependency_graph=dependency_graph,
            visualization_data=visualization_data,
        )