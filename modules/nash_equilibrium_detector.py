"""Nash Equilibrium Detector Module

Monitors module interactions and detects Nash equilibria by tracking:
- Per-module fitness scores over time
- Pairwise interaction matrices
- Convergence detection when no single-module mutation improves overall fitness

Uses schema alignment checker and dependency graph for interaction modeling.
"""

from typing import Dict, List, Set, Tuple, Optional, Any
from collections import defaultdict
import numpy as np
from dataclasses import dataclass, field
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class ModuleState(Enum):
    """Possible states for module interactions."""
    STABLE = "stable"
    IMPROVING = "improving"
    DEGRADING = "degrading"
    CONFLICTING = "conflicting"


@dataclass
class InteractionRecord:
    """Records how module A affects module B's fitness."""
    source_module: str
    target_module: str
    fitness_impact: float  # Positive means beneficial, negative means harmful
    interaction_strength: float  # Magnitude of interaction (0-1)
    state: ModuleState = ModuleState.STABLE


@dataclass
class FitnessSnapshot:
    """Snapshot of all module fitness scores at a point in time."""
    timestamp: int
    fitness_scores: Dict[str, float]
    overall_fitness: float


@dataclass
class NashEquilibrium:
    """Represents a detected Nash equilibrium."""
    modules: Set[str]
    interaction_matrix: Dict[Tuple[str, str], InteractionRecord]
    fitness_scores: Dict[str, float]
    overall_fitness: float
    convergence_cycles: int


class NashEquilibriumDetector:
    """Detects Nash equilibria in module interactions."""

    def __init__(self, 
                 schema_checker: Any = None,
                 dependency_graph: Any = None,
                 convergence_threshold: int = 10,
                 fitness_improvement_threshold: float = 0.001):
        """
        Initialize the Nash equilibrium detector.

        Args:
            schema_checker: Schema alignment checker instance
            dependency_graph: Dependency graph instance
            convergence_threshold: Number of cycles without improvement to declare convergence
            fitness_improvement_threshold: Minimum fitness improvement to consider significant
        """
        self.schema_checker = schema_checker
        self.dependency_graph = dependency_graph
        self.convergence_threshold = convergence_threshold
        self.fitness_improvement_threshold = fitness_improvement_threshold

        # Tracking data structures
        self.fitness_history: List[FitnessSnapshot] = []
        self.interaction_matrix: Dict[Tuple[str, str], InteractionRecord] = {}
        self.module_fitness_history: Dict[str, List[float]] = defaultdict(list)
        self.cycles_without_improvement: int = 0
        self.best_overall_fitness: float = float('-inf')
        self.current_fitness_scores: Dict[str, float] = {}
        self.detected_equilibria: List[NashEquilibrium] = []

        # Track module mutations
        self.mutation_history: List[Dict[str, float]] = []
        self.last_mutation_effects: Dict[str, float] = {}

    def register_module_mutation(self, module_name: str, fitness_change: float) -> None:
        """
        Register a mutation event for a module.

        Args:
            module_name: Name of the mutated module
            fitness_change: Change in fitness resulting from mutation
        """
        self.last_mutation_effects[module_name] = fitness_change
        self.mutation_history.append({module_name: fitness_change})

        # Keep only recent history for memory efficiency
        if len(self.mutation_history) > 100:
            self.mutation_history.pop(0)

    def update_fitness_scores(self, fitness_scores: Dict[str, float]) -> None:
        """
        Update fitness scores for all modules.

        Args:
            fitness_scores: Dictionary mapping module names to their fitness scores
        """
        timestamp = len(self.fitness_history)
        self.current_fitness_scores = fitness_scores.copy()

        # Calculate overall fitness (average of all module fitness scores)
        overall_fitness = np.mean(list(fitness_scores.values())) if fitness_scores else 0.0

        # Create snapshot
        snapshot = FitnessSnapshot(
            timestamp=timestamp,
            fitness_scores=fitness_scores.copy(),
            overall_fitness=overall_fitness
        )
        self.fitness_history.append(snapshot)

        # Update per-module history
        for module_name, score in fitness_scores.items():
            self.module_fitness_history[module_name].append(score)

        # Check for improvement
        if overall_fitness > self.best_overall_fitness + self.fitness_improvement_threshold:
            self.best_overall_fitness = overall_fitness
            self.cycles_without_improvement = 0
        else:
            self.cycles_without_improvement += 1

        # Update interaction matrix based on recent mutations
        self._update_interaction_matrix()

        # Check for Nash equilibrium
        if self._check_nash_equilibrium():
            self._record_equilibrium()

    def _update_interaction_matrix(self) -> None:
        """Update the pairwise interaction matrix based on recent changes."""
        if not self.mutation_history or len(self.fitness_history) < 2:
            return

        # Get the last two fitness snapshots
        current = self.fitness_history[-1]
        previous = self.fitness_history[-2]

        # For each module that was mutated recently, calculate impact on all modules
        for mutated_module in self.last_mutation_effects:
            if mutated_module not in current.fitness_scores:
                continue

            for target_module in current.fitness_scores:
                if target_module == mutated_module:
                    continue

                # Calculate fitness impact
                prev_fitness = previous.fitness_scores.get(target_module, 0.0)
                curr_fitness = current.fitness_scores.get(target_module, 0.0)
                impact = curr_fitness - prev_fitness

                # Update interaction record
                key = (mutated_module, target_module)
                if key not in self.interaction_matrix:
                    self.interaction_matrix[key] = InteractionRecord(
                        source_module=mutated_module,
                        target_module=target_module,
                        fitness_impact=impact,
                        interaction_strength=abs(impact)
                    )
                else:
                    # Update with exponential moving average
                    alpha = 0.3
                    record = self.interaction_matrix[key]
                    record.fitness_impact = (1 - alpha) * record.fitness_impact + alpha * impact
                    record.interaction_strength = (1 - alpha) * record.interaction_strength + alpha * abs(impact)

                # Determine state based on impact
                record = self.interaction_matrix[key]
                if abs(impact) < self.fitness_improvement_threshold:
                    record.state = ModuleState.STABLE
                elif impact > 0:
                    record.state = ModuleState.IMPROVING
                else:
                    record.state = ModuleState.DEGRADING

    def _check_nash_equilibrium(self) -> bool:
        """
        Check if current state represents a Nash equilibrium.

        A Nash equilibrium exists when no single-module mutation can improve
        the overall system fitness.

        Returns:
            True if Nash equilibrium detected, False otherwise
        """
        # Check convergence criterion
        if self.cycles_without_improvement < self.convergence_threshold:
            return False

        # Check if any recent mutation improved fitness
        for mutation in self.mutation_history[-self.convergence_threshold:]:
            for module, change in mutation.items():
                if change > self.fitness_improvement_threshold:
                    return False

        # Check if all modules are in stable or degrading states
        # (no module can improve without hurting others)
        all_stable = True
        for key, record in self.interaction_matrix.items():
            if record.state == ModuleState.IMPROVING:
                all_stable = False
                break

        return all_stable

    def _record_equilibrium(self) -> None:
        """Record the detected Nash equilibrium."""
        modules = set(self.current_fitness_scores.keys())
        
        # Create interaction matrix subset for equilibrium modules
        eq_interaction_matrix = {}
        for key, record in self.interaction_matrix.items():
            if key[0] in modules and key[1] in modules:
                eq_interaction_matrix[key] = record

        equilibrium = NashEquilibrium(
            modules=modules,
            interaction_matrix=eq_interaction_matrix,
            fitness_scores=self.current_fitness_scores.copy(),
            overall_fitness=self.best_overall_fitness,
            convergence_cycles=self.cycles_without_improvement
        )

        self.detected_equilibria.append(equilibrium)
        logger.info(f"Nash equilibrium detected: {len(modules)} modules at fitness {self.best_overall_fitness:.4f}")

    def get_interaction_matrix(self) -> Dict[Tuple[str, str], InteractionRecord]:
        """
        Get the current pairwise interaction matrix.

        Returns:
            Dictionary mapping (source, target) module pairs to their interaction records
        """
        return self.interaction_matrix.copy()

    def get_module_fitness_history(self, module_name: str) -> List[float]:
        """
        Get fitness history for a specific module.

        Args:
            module_name: Name of the module

        Returns:
            List of fitness scores over time
        """
        return self.module_fitness_history.get(module_name, []).copy()

    def get_fitness_history(self) -> List[FitnessSnapshot]:
        """
        Get complete fitness history.

        Returns:
            List of fitness snapshots
        """
        return self.fitness_history.copy()

    def get_detected_equilibria(self) -> List[NashEquilibrium]:
        """
        Get all detected Nash equilibria.

        Returns:
            List of NashEquilibrium objects
        """
        return self.detected_equilibria.copy()

    def is_in_equilibrium(self) -> bool:
        """
        Check if the system is currently in a Nash equilibrium.

        Returns:
            True if in equilibrium, False otherwise
        """
        return self._check_nash_equilibrium()

    def get_equilibrium_details(self) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about the current equilibrium state.

        Returns:
            Dictionary with equilibrium details or None if not in equilibrium
        """
        if not self.is_in_equilibrium():
            return None

        return {
            "modules": list(self.current_fitness_scores.keys()),
            "fitness_scores": self.current_fitness_scores.copy(),
            "overall_fitness": self.best_overall_fitness,
            "convergence_cycles": self.cycles_without_improvement,
            "interaction_matrix": {
                f"{k[0]}->{k[1]}": {
                    "impact": v.fitness_impact,
                    "strength": v.interaction_strength,
                    "state": v.state.value
                }
                for k, v in self.interaction_matrix.items()
            }
        }

    def reset(self) -> None:
        """Reset all tracking data."""
        self.fitness_history.clear()
        self.interaction_matrix.clear()
        self.module_fitness_history.clear()
        self.mutation_history.clear()
        self.last_mutation_effects.clear()
        self.cycles_without_improvement = 0
        self.best_overall_fitness = float('-inf')
        self.current_fitness_scores.clear()
        self.detected_equilibria.clear()


# Module-level singleton instance
_detector_instance: Optional[NashEquilibriumDetector] = None


def get_detector(schema_checker: Any = None,
                 dependency_graph: Any = None,
                 convergence_threshold: int = 10,
                 fitness_improvement_threshold: float = 0.001) -> NashEquilibriumDetector:
    """
    Get or create the Nash equilibrium detector singleton.

    Args:
        schema_checker: Schema alignment checker instance
        dependency_graph: Dependency graph instance
        convergence_threshold: Number of cycles without improvement to declare convergence
        fitness_improvement_threshold: Minimum fitness improvement to consider significant

    Returns:
        NashEquilibriumDetector instance
    """
    global _detector_instance
    if _detector_instance is None:
        _detector_instance = NashEquilibriumDetector(
            schema_checker=schema_checker,
            dependency_graph=dependency_graph,
            convergence_threshold=convergence_threshold,
            fitness_improvement_threshold=fitness_improvement_threshold
        )
    return _detector_instance


def detect_equilibrium(fitness_scores: Dict[str, float],
                       mutations: Optional[Dict[str, float]] = None) -> Optional[Dict[str, Any]]:
    """
    Convenience function to detect Nash equilibrium in one call.

    Args:
        fitness_scores: Current fitness scores for all modules
        mutations: Optional dictionary of recent mutations and their effects

    Returns:
        Equilibrium details if detected, None otherwise
    """
    detector = get_detector()
    
    if mutations:
        for module, change in mutations.items():
            detector.register_module_mutation(module, change)
    
    detector.update_fitness_scores(fitness_scores)
    return detector.get_equilibrium_details()