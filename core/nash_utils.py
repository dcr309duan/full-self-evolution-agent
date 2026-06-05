from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Tuple
from collections import defaultdict


class EquilibriumState(Enum):
    """Represents the current state of a Nash equilibrium analysis."""
    NOT_ANALYZED = auto()
    NO_EQUILIBRIUM = auto()
    PURE_STRATEGY = auto()
    MIXED_STRATEGY = auto()
    PARTIAL = auto()
    STABLE = auto()
    UNSTABLE = auto()


@dataclass
class InteractionRecord:
    """Records a single interaction between two modules during Nash analysis."""
    source_module: str
    target_module: str
    interaction_type: str  # e.g., 'call', 'import', 'data_flow'
    frequency: int = 1
    success_count: int = 0
    failure_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def total_attempts(self) -> int:
        return self.success_count + self.failure_count

    @property
    def success_rate(self) -> float:
        if self.total_attempts == 0:
            return 0.0
        return self.success_count / self.total_attempts

    def record_outcome(self, success: bool) -> None:
        if success:
            self.success_count += 1
        else:
            self.failure_count += 1


@dataclass
class MultiModuleChange:
    """Represents a proposed change that affects multiple modules."""
    source_module: str
    target_modules: List[str]
    change_type: str  # e.g., 'refactor', 'dependency_add', 'dependency_remove'
    expected_impact: float = 0.0  # Expected improvement in Nash stability
    risk_score: float = 0.0  # Higher means riskier change
    dependencies: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def add_target_module(self, module: str) -> None:
        if module not in self.target_modules:
            self.target_modules.append(module)

    def remove_target_module(self, module: str) -> None:
        if module in self.target_modules:
            self.target_modules.remove(module)


def calculate_interaction_frequencies(
    interaction_records: List[InteractionRecord]
) -> Dict[Tuple[str, str], int]:
    """
    Calculate interaction frequencies between module pairs from a list of InteractionRecords.

    Args:
        interaction_records: List of InteractionRecord objects.

    Returns:
        Dictionary mapping (source_module, target_module) tuples to total interaction frequencies.
    """
    freq: Dict[Tuple[str, str], int] = defaultdict(int)
    for record in interaction_records:
        key = (record.source_module, record.target_module)
        freq[key] += record.frequency
    return dict(freq)


def calculate_success_rates(
    interaction_records: List[InteractionRecord]
) -> Dict[Tuple[str, str], float]:
    """
    Calculate success rates for each module pair interaction.

    Args:
        interaction_records: List of InteractionRecord objects.

    Returns:
        Dictionary mapping (source_module, target_module) tuples to success rates (0.0 to 1.0).
    """
    success_rates: Dict[Tuple[str, str], float] = {}
    for record in interaction_records:
        key = (record.source_module, record.target_module)
        if record.total_attempts > 0:
            success_rates[key] = record.success_rate
        else:
            success_rates[key] = 0.0
    return success_rates


def aggregate_failure_patterns(
    failure_data: Dict[str, Any]
) -> Dict[Tuple[str, str], Dict[str, Any]]:
    """
    Aggregate failure pattern learner data into structured interaction statistics.

    Expected failure_data format (example):
    {
        "module_pairs": {
            ("modA", "modB"): {
                "failures": [{"type": "timeout", "count": 3}, ...],
                "successes": 10,
                "total_attempts": 15
            },
            ...
        }
    }

    Args:
        failure_data: Raw failure pattern data from the learner.

    Returns:
        Dictionary mapping (source, target) tuples to aggregated stats including
        failure count, success count, and success rate.
    """
    aggregated: Dict[Tuple[str, str], Dict[str, Any]] = {}
    module_pairs = failure_data.get("module_pairs", {})
    for pair, data in module_pairs.items():
        successes = data.get("successes", 0)
        total = data.get("total_attempts", 0)
        failures = total - successes
        success_rate = successes / total if total > 0 else 0.0
        aggregated[pair] = {
            "successes": successes,
            "failures": failures,
            "total_attempts": total,
            "success_rate": success_rate,
            "failure_types": data.get("failures", [])
        }
    return aggregated


def build_interaction_records_from_failure_data(
    failure_data: Dict[str, Any]
) -> List[InteractionRecord]:
    """
    Build a list of InteractionRecord objects from failure pattern learner data.

    Args:
        failure_data: Raw failure pattern data (see aggregate_failure_patterns).

    Returns:
        List of InteractionRecord instances.
    """
    records: List[InteractionRecord] = []
    module_pairs = failure_data.get("module_pairs", {})
    for (source, target), data in module_pairs.items():
        successes = data.get("successes", 0)
        failures = data.get("total_attempts", 0) - successes
        record = InteractionRecord(
            source_module=source,
            target_module=target,
            interaction_type="call",
            frequency=data.get("total_attempts", 0),
            success_count=successes,
            failure_count=failures
        )
        records.append(record)
    return records