from ecology_core import (
    EcologyCore,
    Pressure,
    PressureType,
    TestCase,
    TestSuite,
    EcologyResult,
    Severity,
    generate_pressure_id,
)
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum
import hashlib
import time


class SeverityScore(Enum):
    """Scoring for pressure severity based on type and context."""
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class PressureSeverity:
    """Tracks severity scoring for a given pressure."""
    pressure: Pressure
    base_score: SeverityScore
    context_multiplier: float = 1.0
    final_score: float = 0.0
    scored_at: float = field(default_factory=time.time)

    def __post_init__(self):
        self.final_score = self.base_score.value * self.context_multiplier


@dataclass
class PressureDiversityRecord:
    """Tracks diversity of pressures to avoid duplicates."""
    pressure_type: PressureType
    target_module: str
    first_seen: float = field(default_factory=time.time)
    last_seen: float = field(default_factory=time.time)
    occurrence_count: int = 1
    related_test_ids: Set[str] = field(default_factory=set)


class EcologyEngine:
    """
    Higher-level ecology engine that builds on EcologyCore.
    
    Features:
    - Pressure severity scoring based on type and context
    - Automatic test suite expansion based on pressure types
    - Pressure diversity tracking to avoid duplicate pressures
    """

    def __init__(self, core: Optional[EcologyCore] = None):
        self.core = core if core is not None else EcologyCore()
        self.severity_scores: Dict[str, PressureSeverity] = {}
        self.diversity_records: Dict[str, PressureDiversityRecord] = {}
        self.expanded_test_suites: Dict[str, TestSuite] = {}
        self._diversity_hash_set: Set[str] = set()

    def _compute_diversity_hash(self, pressure: Pressure) -> str:
        """Compute a hash for diversity tracking based on pressure type and target."""
        raw = f"{pressure.pressure_type.value}:{pressure.target_module}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def _score_severity(self, pressure: Pressure) -> PressureSeverity:
        """Score the severity of a given pressure."""
        # Base severity mapping
        type_severity_map = {
            PressureType.COVERAGE: SeverityScore.MEDIUM,
            PressureType.PERFORMANCE: SeverityScore.HIGH,
            PressureType.SECURITY: SeverityScore.CRITICAL,
            PressureType.RELIABILITY: SeverityScore.HIGH,
            PressureType.MAINTENANCE: SeverityScore.MEDIUM,
            PressureType.COMPATIBILITY: SeverityScore.MEDIUM,
            PressureType.USABILITY: SeverityScore.LOW,
            PressureType.ACCESSIBILITY: SeverityScore.MEDIUM,
            PressureType.LOCALIZATION: SeverityScore.LOW,
            PressureType.REGRESSION: SeverityScore.CRITICAL,
        }

        base_score = type_severity_map.get(pressure.pressure_type, SeverityScore.MEDIUM)

        # Context multiplier based on pressure details
        context_multiplier = 1.0
        if pressure.severity == Severity.HIGH:
            context_multiplier *= 1.5
        elif pressure.severity == Severity.LOW:
            context_multiplier *= 0.7

        # Boost if target is critical (e.g., core modules)
        critical_modules = {"core", "main", "engine", "api", "auth"}
        if pressure.target_module in critical_modules:
            context_multiplier *= 1.3

        return PressureSeverity(
            pressure=pressure,
            base_score=base_score,
            context_multiplier=context_multiplier,
        )

    def _expand_test_suite(self, pressure: Pressure, base_suite: TestSuite) -> TestSuite:
        """
        Automatically expand a test suite based on pressure type.
        
        Returns an expanded TestSuite with additional test cases tailored to the pressure.
        """
        expanded_cases = list(base_suite.test_cases)
        base_id = base_suite.suite_id

        # Generate expansion test cases based on pressure type
        if pressure.pressure_type == PressureType.COVERAGE:
            expanded_cases.append(
                TestCase(
                    test_id=f"{base_id}_cov_expand_1",
                    name=f"Coverage expansion for {pressure.target_module}",
                    target_module=pressure.target_module,
                    description=f"Additional coverage test generated from {pressure.pressure_type.value} pressure",
                    tags={"coverage", "expansion", "auto-generated"},
                )
            )
        elif pressure.pressure_type == PressureType.PERFORMANCE:
            expanded_cases.append(
                TestCase(
                    test_id=f"{base_id}_perf_expand_1",
                    name=f"Performance benchmark for {pressure.target_module}",
                    target_module=pressure.target_module,
                    description=f"Performance test generated from {pressure.pressure_type.value} pressure",
                    tags={"performance", "expansion", "auto-generated"},
                )
            )
        elif pressure.pressure_type == PressureType.SECURITY:
            expanded_cases.append(
                TestCase(
                    test_id=f"{base_id}_sec_expand_1",
                    name=f"Security audit for {pressure.target_module}",
                    target_module=pressure.target_module,
                    description=f"Security test generated from {pressure.pressure_type.value} pressure",
                    tags={"security", "expansion", "auto-generated"},
                )
            )
        elif pressure.pressure_type == PressureType.REGRESSION:
            expanded_cases.append(
                TestCase(
                    test_id=f"{base_id}_reg_expand_1",
                    name=f"Regression check for {pressure.target_module}",
                    target_module=pressure.target_module,
                    description=f"Regression test generated from {pressure.pressure_type.value} pressure",
                    tags={"regression", "expansion", "auto-generated"},
                )
            )
        else:
            # Generic expansion for other pressure types
            expanded_cases.append(
                TestCase(
                    test_id=f"{base_id}_gen_expand_1",
                    name=f"Generic expansion for {pressure.target_module}",
                    target_module=pressure.target_module,
                    description=f"Test generated from {pressure.pressure_type.value} pressure",
                    tags={"generic", "expansion", "auto-generated"},
                )
            )

        expanded_suite = TestSuite(
            suite_id=f"{base_id}_expanded",
            name=f"Expanded: {base_suite.name}",
            test_cases=expanded_cases,
            metadata={
                **base_suite.metadata,
                "expanded": True,
                "source_pressure_type": pressure.pressure_type.value,
                "source_pressure_id": pressure.pressure_id,
            },
        )
        return expanded_suite

    def _track_diversity(self, pressure: Pressure) -> bool:
        """
        Track pressure diversity to avoid duplicates.
        Returns True if this is a new unique pressure, False if duplicate.
        """
        div_hash = self._compute_diversity_hash(pressure)

        if div_hash in self._diversity_hash_set:
            # Update existing record
            if div_hash in self.diversity_records:
                record = self.diversity_records[div_hash]
                record.last_seen = time.time()
                record.occurrence_count += 1
                if pressure.related_test_id:
                    record.related_test_ids.add(pressure.related_test_id)
            return False  # Duplicate

        # New diversity record
        self._diversity_hash_set.add(div_hash)
        record = PressureDiversityRecord(
            pressure_type=pressure.pressure_type,
            target_module=pressure.target_module,
            related_test_ids={pressure.related_test_id} if pressure.related_test_id else set(),
        )
        self.diversity_records[div_hash] = record
        return True  # Unique

    def apply_pressure_with_scoring(
        self, pressure: Pressure, test_suite: TestSuite
    ) -> Tuple[EcologyResult, PressureSeverity, TestSuite]:
        """
        Apply a pressure with full engine features:
        1. Score severity
        2. Track diversity
        3. Expand test suite if unique
        4. Apply pressure via core
        """
        # Score severity
        severity = self._score_severity(pressure)
        self.severity_scores[pressure.pressure_id] = severity

        # Track diversity
        is_unique = self._track_diversity(pressure)

        # Expand test suite if unique (avoid redundant expansion)
        if is_unique:
            expanded_suite = self._expand_test_suite(pressure, test_suite)
            self.expanded_test_suites[pressure.pressure_id] = expanded_suite
        else:
            expanded_suite = test_suite

        # Apply pressure via core
        result = self.core.apply_pressure(pressure, expanded_suite)

        return result, severity, expanded_suite

    def get_pressure_diversity_summary(self) -> Dict[str, Dict]:
        """Get a summary of pressure diversity tracked so far."""
        summary = {}
        for div_hash, record in self.diversity_records.items():
            summary[div_hash] = {
                "pressure_type": record.pressure_type.value,
                "target_module": record.target_module,
                "first_seen": record.first_seen,
                "last_seen": record.last_seen,
                "occurrence_count": record.occurrence_count,
                "related_test_count": len(record.related_test_ids),
            }
        return summary

    def get_severity_report(self) -> Dict[str, Dict]:
        """Get a report of all severity scores."""
        report = {}
        for pressure_id, severity in self.severity_scores.items():
            report[pressure_id] = {
                "base_score": severity.base_score.name,
                "context_multiplier": severity.context_multiplier,
                "final_score": severity.final_score,
                "scored_at": severity.scored_at,
                "pressure_type": severity.pressure.pressure_type.value,
                "target_module": severity.pressure.target_module,
            }
        return report

    def get_unique_pressure_count(self) -> int:
        """Get the count of unique pressures tracked."""
        return len(self._diversity_hash_set)

    def get_total_pressure_applications(self) -> int:
        """Get the total number of pressure applications (including duplicates)."""
        return sum(r.occurrence_count for r in self.diversity_records.values())

    def reset(self) -> None:
        """Reset all engine state."""
        self.severity_scores.clear()
        self.diversity_records.clear()
        self.expanded_test_suites.clear()
        self._diversity_hash_set.clear()
        self.core.reset()