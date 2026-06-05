"""Module for pre-checking goal feasibility based on dependency analysis and test coverage."""

from typing import Dict, List, Optional, Tuple
from enum import Enum
from dataclasses import dataclass, field
import logging

# Assuming these exist in the project's test infrastructure
from test_coverage import get_module_coverage, CoverageResult
from dependency_graph import DependencyGraph, DependencyNode

logger = logging.getLogger(__name__)


class FeasibilityDecision(Enum):
    """Enum representing the feasibility decision for a goal."""
    BLOCK = "BLOCK"
    DOWNGRADE = "DOWNGRADE"
    ALLOW = "ALLOW"


@dataclass
class FeasibilityResult:
    """Result of a goal feasibility pre-check."""
    decision: FeasibilityDecision
    score: float
    justification: str
    dependency_details: Dict[str, 'DependencyCheckResult'] = field(default_factory=dict)


@dataclass
class DependencyCheckResult:
    """Result of checking a single dependency's feasibility."""
    module_name: str
    exists: bool
    test_coverage: Optional[float]
    coverage_sufficient: bool
    details: str


class GoalFeasibilityPrecheck:
    """Performs feasibility pre-checks on proposed goals."""

    def __init__(self, dependency_graph: DependencyGraph, 
                 min_coverage_threshold: float = 0.7,
                 critical_coverage_threshold: float = 0.9):
        """
        Initialize the pre-checker.
        
        Args:
            dependency_graph: The project's dependency graph
            min_coverage_threshold: Minimum acceptable test coverage (0.0-1.0)
            critical_coverage_threshold: Coverage required for critical dependencies
        """
        self.dependency_graph = dependency_graph
        self.min_coverage_threshold = min_coverage_threshold
        self.critical_coverage_threshold = critical_coverage_threshold

    def check_goal_feasibility(self, goal: str) -> FeasibilityResult:
        """
        Perform a feasibility pre-check on a proposed goal.
        
        Args:
            goal: The proposed goal description or identifier
            
        Returns:
            FeasibilityResult with decision, score, and justification
        """
        logger.info(f"Running feasibility pre-check for goal: {goal}")
        
        # Step 1: Identify all modules the goal depends on
        dependent_modules = self._get_dependent_modules(goal)
        
        if not dependent_modules:
            return FeasibilityResult(
                decision=FeasibilityDecision.ALLOW,
                score=1.0,
                justification="Goal has no module dependencies; no pre-check issues found."
            )
        
        # Step 2: Check test coverage for each dependent module
        dependency_results = self._check_dependency_coverage(dependent_modules)
        
        # Step 3: Compute feasibility score
        score = self._compute_feasibility_score(dependency_results)
        
        # Step 4: Determine decision and justification
        decision, justification = self._make_decision(dependency_results, score)
        
        return FeasibilityResult(
            decision=decision,
            score=score,
            justification=justification,
            dependency_details=dependency_results
        )

    def _get_dependent_modules(self, goal: str) -> List[str]:
        """
        Query the dependency graph to identify all modules the goal depends on.
        
        Args:
            goal: The proposed goal
            
        Returns:
            List of module names that the goal depends on
        """
        try:
            # Parse goal to identify relevant modules (implementation-specific)
            goal_modules = self._parse_goal_to_modules(goal)
            
            # Get all transitive dependencies
            all_dependencies = set()
            for module in goal_modules:
                deps = self.dependency_graph.get_transitive_dependencies(module)
                all_dependencies.update(deps)
                all_dependencies.add(module)
            
            return list(all_dependencies)
        except Exception as e:
            logger.error(f"Failed to get dependent modules for goal '{goal}': {e}")
            return []

    def _parse_goal_to_modules(self, goal: str) -> List[str]:
        """
        Parse a goal string to identify the primary modules involved.
        This is a placeholder - actual implementation depends on goal format.
        
        Args:
            goal: The goal string
            
        Returns:
            List of primary module names
        """
        # Placeholder: In a real implementation, this would parse the goal
        # to identify modules (e.g., from a task description, feature name, etc.)
        # For now, we assume the goal directly names the primary module
        return [goal] if goal else []

    def _check_dependency_coverage(self, modules: List[str]) -> Dict[str, DependencyCheckResult]:
        """
        Check test coverage for each dependent module.
        
        Args:
            modules: List of module names to check
            
        Returns:
            Dictionary mapping module names to their check results
        """
        results = {}
        
        for module in modules:
            try:
                # Check if module exists in dependency graph
                node = self.dependency_graph.get_node(module)
                if node is None:
                    results[module] = DependencyCheckResult(
                        module_name=module,
                        exists=False,
                        test_coverage=None,
                        coverage_sufficient=False,
                        details=f"Module '{module}' not found in dependency graph"
                    )
                    continue
                
                # Get test coverage using existing test infrastructure
                coverage = get_module_coverage(module)
                
                if coverage is None:
                    results[module] = DependencyCheckResult(
                        module_name=module,
                        exists=True,
                        test_coverage=None,
                        coverage_sufficient=False,
                        details=f"No test coverage data available for module '{module}'"
                    )
                else:
                    # Determine if coverage is sufficient
                    is_critical = node.is_critical if hasattr(node, 'is_critical') else False
                    threshold = self.critical_coverage_threshold if is_critical else self.min_coverage_threshold
                    sufficient = coverage.coverage_percentage >= threshold
                    
                    results[module] = DependencyCheckResult(
                        module_name=module,
                        exists=True,
                        test_coverage=coverage.coverage_percentage,
                        coverage_sufficient=sufficient,
                        details=(
                            f"Module '{module}' has {coverage.coverage_percentage:.1%} coverage "
                            f"({'sufficient' if sufficient else 'insufficient'}, "
                            f"threshold: {threshold:.0%})"
                        )
                    )
                    
            except Exception as e:
                logger.error(f"Error checking coverage for module '{module}': {e}")
                results[module] = DependencyCheckResult(
                    module_name=module,
                    exists=True,
                    test_coverage=None,
                    coverage_sufficient=False,
                    details=f"Error checking coverage: {str(e)}"
                )
        
        return results

    def _compute_feasibility_score(self, dependency_results: Dict[str, DependencyCheckResult]) -> float:
        """
        Compute a feasibility score based on dependency completeness and test coverage.
        
        Args:
            dependency_results: Results from checking dependencies
            
        Returns:
            Feasibility score between 0.0 and 1.0
        """
        if not dependency_results:
            return 1.0
        
        total_weight = len(dependency_results)
        if total_weight == 0:
            return 1.0
        
        score_sum = 0.0
        
        for result in dependency_results.values():
            # Score for module existence
            if not result.exists:
                score_sum += 0.0
                continue
            
            # Score for test coverage
            if result.test_coverage is None:
                score_sum += 0.3  # Partial credit for unknown coverage
            elif result.coverage_sufficient:
                score_sum += 1.0
            else:
                # Proportional score for insufficient coverage
                score_sum += result.test_coverage
        
        return score_sum / total_weight

    def _make_decision(self, dependency_results: Dict[str, DependencyCheckResult], 
                      score: float) -> Tuple[FeasibilityDecision, str]:
        """
        Make a feasibility decision based on dependency results and score.
        
        Args:
            dependency_results: Results from checking dependencies
            score: Computed feasibility score
            
        Returns:
            Tuple of (decision, justification string)
        """
        # Check for blocking issues
        missing_modules = [r for r in dependency_results.values() if not r.exists]
        if missing_modules:
            module_list = ", ".join(r.module_name for r in missing_modules)
            return (
                FeasibilityDecision.BLOCK,
                f"Goal is blocked: missing required modules: {module_list}. "
                f"Feasibility score: {score:.2f}"
            )
        
        # Check for critical coverage issues
        insufficient_coverage = [
            r for r in dependency_results.values() 
            if r.exists and r.test_coverage is not None and not r.coverage_sufficient
        ]
        
        if insufficient_coverage and score < self.min_coverage_threshold:
            module_list = ", ".join(
                f"{r.module_name} ({r.test_coverage:.1%})" 
                for r in insufficient_coverage
            )
            return (
                FeasibilityDecision.BLOCK,
                f"Goal is blocked: critical coverage deficiencies in modules: {module_list}. "
                f"Feasibility score: {score:.2f}"
            )
        
        # Check for downgrade conditions
        if insufficient_coverage:
            module_list = ", ".join(
                f"{r.module_name} ({r.test_coverage:.1%})" 
                for r in insufficient_coverage
            )
            return (
                FeasibilityDecision.DOWNGRADE,
                f"Goal downgraded: insufficient test coverage in modules: {module_list}. "
                f"Feasibility score: {score:.2f}. Proceed with caution."
            )
        
        # No issues found
        return (
            FeasibilityDecision.ALLOW,
            f"Goal is feasible: all dependencies have sufficient test coverage. "
            f"Feasibility score: {score:.2f}"
        )


# Convenience function for quick pre-check
def precheck_goal(goal: str, 
                  dependency_graph: DependencyGraph,
                  min_coverage: float = 0.7,
                  critical_coverage: float = 0.9) -> FeasibilityResult:
    """
    Convenience function to perform a quick goal feasibility pre-check.
    
    Args:
        goal: The proposed goal
        dependency_graph: The project's dependency graph
        min_coverage: Minimum acceptable test coverage
        critical_coverage: Coverage required for critical dependencies
        
    Returns:
        FeasibilityResult with decision, score, and justification
    """
    prechecker = GoalFeasibilityPrecheck(
        dependency_graph=dependency_graph,
        min_coverage_threshold=min_coverage,
        critical_coverage_threshold=critical_coverage
    )
    return prechecker.check_goal_feasibility(goal)