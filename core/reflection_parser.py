from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field, validator
from enum import Enum
from collections import deque


class SimulationPrediction(str, Enum):
    PASS = "pass"
    FAIL = "fail"


class CuriosityInsights(BaseModel):
    """Schema for curiosity engine insights analysis."""
    most_failed_task_types: List[str] = Field(
        default_factory=list,
        description="List of task types that fail most often based on curiosity engine results."
    )
    missing_capabilities: List[str] = Field(
        default_factory=list,
        description="List of capabilities that are missing or underperforming."
    )
    suggested_template_expansions: List[str] = Field(
        default_factory=list,
        description="Suggestions for expanding the template library in areas of weakness."
    )


class FitnessTrendAnalysis(BaseModel):
    """Schema for fitness trend analysis fields."""
    fitness_scores: deque = Field(
        default_factory=lambda: deque(maxlen=10),
        description="Last 10 fitness scores, ordered chronologically."
    )
    declining_areas: List[str] = Field(
        default_factory=list,
        description="List of areas where fitness is declining."
    )
    suggested_improvements: List[str] = Field(
        default_factory=list,
        description="List of specific code improvements to address declining areas."
    )

    def add_fitness_score(self, score: float) -> None:
        """Add a new fitness score and update analysis."""
        self.fitness_scores.append(score)
        self._analyze_trend()

    def _analyze_trend(self) -> None:
        """Analyze fitness trend and update declining areas and suggestions."""
        if len(self.fitness_scores) < 3:
            self.declining_areas = []
            self.suggested_improvements = []
            return

        scores = list(self.fitness_scores)
        self.declining_areas = []
        self.suggested_improvements = []

        # Check overall trend
        if scores[-1] < scores[0]:
            self.declining_areas.append("overall_fitness")
            self.suggested_improvements.append(
                "Review recent code changes for performance regressions. "
                "Consider profiling and optimizing critical paths."
            )

        # Check for recent decline (last 3 scores)
        if len(scores) >= 3 and scores[-1] < scores[-2] < scores[-3]:
            self.declining_areas.append("recent_trend")
            self.suggested_improvements.append(
                "Recent consecutive decline detected. Investigate recent commits "
                "for potential issues. Run regression tests and compare with baseline."
            )

        # Check for volatility (high variance in last 5 scores)
        if len(scores) >= 5:
            recent_scores = scores[-5:]
            mean = sum(recent_scores) / len(recent_scores)
            variance = sum((s - mean) ** 2 for s in recent_scores) / len(recent_scores)
            if variance > 0.1:
                self.declining_areas.append("high_volatility")
                self.suggested_improvements.append(
                    "High fitness score volatility detected. Implement more consistent "
                    "testing practices and stabilize deployment pipeline."
                )

        # Check for sustained low performance
        if all(s < 0.5 for s in scores[-3:]):
            self.declining_areas.append("sustained_low_performance")
            self.suggested_improvements.append(
                "Sustained low fitness scores. Consider a major refactoring of "
                "core components. Prioritize fixing known bugs and improving test coverage."
            )


class GoalTriageResults(BaseModel):
    """Schema for goal triage results fields."""
    goals_triaged: int = Field(
        ...,
        ge=0,
        description="Number of goals that were triaged in this reflection cycle."
    )
    goals_flagged_stale: int = Field(
        ...,
        ge=0,
        description="Number of goals flagged as stale during triage."
    )
    goals_decomposed: int = Field(
        ...,
        ge=0,
        description="Number of goals that were decomposed into sub-goals."
    )
    goals_archived: int = Field(
        ...,
        ge=0,
        description="Number of goals archived during triage."
    )
    goals_correctly_archived: int = Field(
        default=0,
        ge=0,
        description="Number of archived goals that would have failed anyway (correctly archived)."
    )
    goals_incorrectly_archived: int = Field(
        default=0,
        ge=0,
        description="Number of archived goals that would have succeeded (incorrectly archived)."
    )
    sub_goals_generated: int = Field(
        default=0,
        ge=0,
        description="Total number of sub-goals generated from decomposition."
    )
    sub_goals_succeeded: int = Field(
        default=0,
        ge=0,
        description="Number of sub-goals that succeeded."
    )
    triage_quality_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Triage quality score based on archival accuracy and sub-goal success rate."
    )
    lessons_learned: List[str] = Field(
        default_factory=list,
        description="List of lessons learned from the triage process."
    )
    prerequisite_blocker_analysis: Dict[str, Any] = Field(
        default_factory=dict,
        description="Analysis of blocking dependencies: identifies most common blockers, average deferral time per blocker, and suggests which blocker to resolve first."
    )
    fitness_trend_analysis: FitnessTrendAnalysis = Field(
        default_factory=FitnessTrendAnalysis,
        description="Analysis of fitness score trends over the last 10 cycles, identifying declining areas and suggesting improvements."
    )
    curiosity_insights: CuriosityInsights = Field(
        default_factory=CuriosityInsights,
        description="Analysis of curiosity engine results: which task types fail most often, which capabilities are missing, and suggests expanding the template library in areas of weakness."
    )

    @validator("triage_quality_score", always=True)
    def compute_triage_quality_score(cls, v: float, values: Dict[str, Any]) -> float:
        """Compute triage quality score based on archival accuracy and sub-goal success rate."""
        correctly_archived = values.get("goals_correctly_archived", 0)
        incorrectly_archived = values.get("goals_incorrectly_archived", 0)
        sub_goals_generated = values.get("sub_goals_generated", 0)
        sub_goals_succeeded = values.get("sub_goals_succeeded", 0)

        # Calculate archival accuracy ratio
        total_archived = correctly_archived + incorrectly_archived
        if total_archived > 0:
            archival_accuracy = correctly_archived / total_archived
        else:
            archival_accuracy = 0.0

        # Calculate sub-goal success rate
        if sub_goals_generated > 0:
            sub_goal_success_rate = sub_goals_succeeded / sub_goals_generated
        else:
            sub_goal_success_rate = 0.0

        # Combine both metrics (weighted average, equal weight)
        quality_score = (archival_accuracy + sub_goal_success_rate) / 2.0
        return min(max(quality_score, 0.0), 1.0)

    @validator("prerequisite_blocker_analysis", always=True)
    def compute_prerequisite_blocker_analysis(cls, v: Dict[str, Any], values: Dict[str, Any]) -> Dict[str, Any]:
        """Compute prerequisite blocker analysis from knowledge base data."""
        # This is a placeholder that would normally query the knowledge base.
        # For demonstration, we simulate the analysis with default values.
        # In a real implementation, this would access a knowledge base of dependencies.
        knowledge_base = values.get("_knowledge_base", {})
        if not knowledge_base:
            # Simulate knowledge base data for demonstration
            knowledge_base = {
                "blockers": {
                    "dependency_A": {"goals_blocked": ["goal1", "goal2"], "deferral_times": [5, 7]},
                    "dependency_B": {"goals_blocked": ["goal3"], "deferral_times": [3]},
                    "dependency_C": {"goals_blocked": ["goal1", "goal3", "goal4"], "deferral_times": [2, 4, 6]}
                }
            }
        
        blockers = knowledge_base.get("blockers", {})
        if not blockers:
            return {"most_common_blockers": [], "average_deferral_times": {}, "suggested_first_blocker": None}
        
        # (a) Identify most common blocking dependencies
        blocker_counts = {blocker: len(info["goals_blocked"]) for blocker, info in blockers.items()}
        max_count = max(blocker_counts.values()) if blocker_counts else 0
        most_common_blockers = [blocker for blocker, count in blocker_counts.items() if count == max_count]
        
        # (b) Calculate average deferral time for goals blocked by each dependency
        average_deferral_times = {}
        for blocker, info in blockers.items():
            deferral_times = info.get("deferral_times", [])
            if deferral_times:
                average_deferral_times[blocker] = sum(deferral_times) / len(deferral_times)
            else:
                average_deferral_times[blocker] = 0.0
        
        # (c) Suggest which blocker to resolve first based on how many goals it blocks
        suggested_first_blocker = max(blocker_counts, key=blocker_counts.get) if blocker_counts else None
        
        return {
            "most_common_blockers": most_common_blockers,
            "average_deferral_times": average_deferral_times,
            "suggested_first_blocker": suggested_first_blocker
        }


class SimulationResult(BaseModel):
    """Schema for simulation result fields."""
    simulation_prediction: SimulationPrediction = Field(
        ...,
        description="Prediction result of the simulation: 'pass' or 'fail'."
    )
    simulation_confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence level of the simulation prediction, between 0.0 and 1.0."
    )
    simulation_side_effects: List[str] = Field(
        default_factory=list,
        description="List of module names that may be affected by the simulation."
    )
    simulation_accuracy_trend: List[float] = Field(
        default_factory=list,
        description="Recent accuracy values from simulation runs, ordered chronologically."
    )

    @validator("simulation_confidence")
    def validate_confidence(cls, v: float) -> float:
        if v < 0.0 or v > 1.0:
            raise ValueError("simulation_confidence must be between 0.0 and 1.0")
        return v

    @validator("simulation_accuracy_trend")
    def validate_accuracy_trend(cls, v: List[float]) -> List[float]:
        for val in v:
            if val < 0.0 or val > 1.0:
                raise ValueError("Each accuracy value must be between 0.0 and 1.0")
        return v


class FsAbstractionStats(BaseModel):
    """Schema for filesystem abstraction usage statistics."""
    atomic_writes: int = Field(
        default=0,
        ge=0,
        description="Number of atomic write operations performed."
    )
    retries_triggered: int = Field(
        default=0,
        ge=0,
        description="Number of retries triggered during filesystem operations."
    )
    permission_failures: int = Field(
        default=0,
        ge=0,
        description="Number of permission failures caught during filesystem operations."
    )
    average_write_latency: float = Field(
        default=0.0,
        ge=0.0,
        description="Average write latency in milliseconds."
    )


class SchemaAlignmentLayer:
    """
    Schema alignment layer that integrates simulation result fields
    and goal triage results into the existing schema structure.
    """

    def __init__(self, base_schema: Optional[Dict[str, Any]] = None):
        self.base_schema = base_schema or {}
        self.simulation_fields = SimulationResult.schema()
        self.goal_triage_fields = GoalTriageResults.schema()
        self.fs_abstraction_fields = FsAbstractionStats.schema()

    def align_schema(self, schema: Dict[str, Any]) -> Dict[str, Any]:
        """
        Align the given schema by injecting simulation result fields
        and goal triage results.

        Args:
            schema: The existing schema dictionary to be updated.

        Returns:
            Updated schema dictionary with simulation and triage fields added.
        """
        aligned = schema.copy()
        aligned.setdefault("properties", {}).update(
            {
                "simulation_prediction": self.simulation_fields["properties"]["simulation_prediction"],
                "simulation_confidence": self.simulation_fields["properties"]["simulation_confidence"],
                "simulation_side_effects": self.simulation_fields["properties"]["simulation_side_effects"],
                "simulation_accuracy_trend": self.simulation_fields["properties"]["simulation_accuracy_trend"],
                "goal_triage_results": {
                    "type": "object",
                    "properties": {
                        "goals_triaged": self.goal_triage_fields["properties"]["goals_triaged"],
                        "goals_flagged_stale": self.goal_triage_fields["properties"]["goals_flagged_stale"],
                        "goals_decomposed": self.goal_triage_fields["properties"]["goals_decomposed"],
                        "goals_archived": self.goal_triage_fields["properties"]["goals_archived"],
                        "goals_correctly_archived": self.goal_triage_fields["properties"]["goals_correctly_archived"],
                        "goals_incorrectly_archived": self.goal_triage_fields["properties"]["goals_incorrectly_archived"],
                        "sub_goals_generated": self.goal_triage_fields["properties"]["sub_goals_generated"],
                        "sub_goals_succeeded": self.goal_triage_fields["properties"]["sub_goals_succeeded"],
                        "triage_quality_score": self.goal_triage_fields["properties"]["triage_quality_score"],
                        "lessons_learned": self.goal_triage_fields["properties"]["lessons_learned"],
                        "prerequisite_blocker_analysis": self.goal_triage_fields["properties"]["prerequisite_blocker_analysis"],
                        "fitness_trend_analysis": {
                            "type": "object",
                            "properties": {
                                "fitness_scores": {
                                    "type": "array",
                                    "items": {"type": "number"},
                                    "maxItems": 10,
                                    "description": "Last 10 fitness scores, ordered chronologically."
                                },
                                "declining_areas": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "description": "List of areas where fitness is declining."
                                },
                                "suggested_improvements": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "description": "List of specific code improvements to address declining areas."
                                }
                            },
                            "description": "Analysis of fitness score trends over the last 10 cycles."
                        },
                        "curiosity_insights": {
                            "type": "object",
                            "properties": {
                                "most_failed_task_types": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "description": "List of task types that fail most often based on curiosity engine results."
                                },
                                "missing_capabilities": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "description": "List of capabilities that are missing or underperforming."
                                },
                                "suggested_template_expansions": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "description": "Suggestions for expanding the template library in areas of weakness."
                                }
                            },
                            "description": "Analysis of curiosity engine results: which task types fail most often, which capabilities are missing, and suggests expanding the template library in areas of weakness."
                        }
                    },
                    "required": ["goals_triaged", "goals_flagged_stale", "goals_decomposed", "goals_archived"],
                    "description": "Triage results for goals in this reflection cycle."
                },
                "fs_abstraction_stats": {
                    "type": "object",
                    "properties": {
                        "atomic_writes": self.fs_abstraction_fields["properties"]["atomic_writes"],
                        "retries_triggered": self.fs_abstraction_fields["properties"]["retries_triggered"],
                        "permission_failures": self.fs_abstraction_fields["properties"]["permission_failures"],
                        "average_write_latency": self.fs_abstraction_fields["properties"]["average_write_latency"]
                    },
                    "description": "Filesystem abstraction usage statistics for infrastructure health monitoring."
                }
            }
        )
        # Ensure required fields are present
        required = aligned.get("required", [])
        for field in ["simulation_prediction", "simulation_confidence", "goal_triage_results", "fs_abstraction_stats"]:
            if field not in required:
                required.append(field)
        aligned["required"] = required
        return aligned

    def validate_simulation_data(self, data: Dict[str, Any]) -> SimulationResult:
        """
        Validate and return a SimulationResult instance from raw data.

        Args:
            data: Dictionary containing simulation result fields.

        Returns:
            SimulationResult instance if validation passes.

        Raises:
            ValidationError: If data does not conform to the schema.
        """
        return SimulationResult(**data)

    def validate_goal_triage_data(self, data: Dict[str, Any]) -> GoalTriageResults:
        """
        Validate and return a GoalTriageResults instance from raw data.

        Args:
            data: Dictionary containing goal triage result fields.

        Returns:
            GoalTriageResults instance if validation passes.

        Raises:
            ValidationError: If data does not conform to the schema.
        """
        return GoalTriageResults(**data)

    def validate_fs_abstraction_data(self, data: Dict[str, Any]) -> FsAbstractionStats:
        """
        Validate and return a FsAbstractionStats instance from raw data.

        Args:
            data: Dictionary containing filesystem abstraction statistics.

        Returns:
            FsAbstractionStats instance if validation passes.

        Raises:
            ValidationError: If data does not conform to the schema.
        """
        return FsAbstractionStats(**data)