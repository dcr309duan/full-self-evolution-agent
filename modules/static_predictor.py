"""StaticPredictor: Pre-checks mutations against dependency graph and schema alignment."""

from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field

from modules.dependency_graph import DependencyGraph
from modules.schema_alignment import SchemaAlignmentChecker


@dataclass
class MutationProposal:
    """Represents a proposed mutation to a target file."""
    target_file: str
    changes: Dict[str, Any]  # e.g., {"added_lines": [...], "removed_lines": [...]}


@dataclass
class PredictionResult:
    """Result of static prediction for a mutation."""
    abort: bool = False
    conflict_score: float = 0.0
    reasoning: List[str] = field(default_factory=list)
    affected_modules: List[str] = field(default_factory=list)


class StaticPredictor:
    """
    Evaluates a proposed mutation by:
    - Querying the dependency graph for affected modules.
    - Running schema alignment checks on those modules.
    - Computing a conflict score.
    - Returning an abort signal if the score exceeds a configurable threshold.
    """

    def __init__(
        self,
        dependency_graph: DependencyGraph,
        schema_checker: SchemaAlignmentChecker,
        conflict_threshold: float = 0.7,
    ):
        """
        Args:
            dependency_graph: Graph of module dependencies.
            schema_checker: Checks schema alignment across modules.
            conflict_threshold: Score above which mutation is aborted (0.0 to 1.0).
        """
        self.dependency_graph = dependency_graph
        self.schema_checker = schema_checker
        self.conflict_threshold = conflict_threshold

    def evaluate(self, proposal: MutationProposal) -> PredictionResult:
        """
        Evaluate a mutation proposal and return a prediction result.

        Steps:
        1. Get all modules affected by the target file (direct and transitive dependencies).
        2. For each affected module, run schema alignment checks.
        3. Compute a conflict score based on alignment failures.
        4. If score > threshold, set abort=True with reasoning.
        """
        result = PredictionResult()

        # Step 1: Query dependency graph for affected modules
        affected = self.dependency_graph.get_affected_modules(proposal.target_file)
        if not affected:
            result.reasoning.append(f"No affected modules found for '{proposal.target_file}'.")
            result.conflict_score = 0.0
            return result

        result.affected_modules = list(affected)

        # Step 2: Run schema alignment checks on each affected module
        alignment_issues: List[str] = []
        for module in affected:
            issues = self.schema_checker.check_module(module, proposal.changes)
            alignment_issues.extend(issues)

        # Step 3: Compute conflict score
        # Simple heuristic: ratio of modules with issues to total affected modules
        modules_with_issues = set()
        for issue in alignment_issues:
            # Assuming issue format includes module name, e.g., "module_name: description"
            module_name = issue.split(":")[0].strip()
            modules_with_issues.add(module_name)

        if result.affected_modules:
            result.conflict_score = len(modules_with_issues) / len(result.affected_modules)
        else:
            result.conflict_score = 0.0

        # Step 4: Check threshold and set abort signal
        if result.conflict_score > self.conflict_threshold:
            result.abort = True
            result.reasoning.append(
                f"Conflict score {result.conflict_score:.2f} exceeds threshold {self.conflict_threshold}."
            )
            result.reasoning.extend(alignment_issues[:5])  # Limit reasoning length
        else:
            result.reasoning.append(
                f"Conflict score {result.conflict_score:.2f} is within threshold {self.conflict_threshold}."
            )

        return result

    def set_threshold(self, new_threshold: float) -> None:
        """Update the conflict threshold."""
        if not 0.0 <= new_threshold <= 1.0:
            raise ValueError("Threshold must be between 0.0 and 1.0.")
        self.conflict_threshold = new_threshold