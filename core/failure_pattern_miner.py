from typing import Dict, List, Optional, Set, Tuple
from enum import Enum
from dataclasses import dataclass, field
from collections import defaultdict
import json
from datetime import datetime


class ConflictType(Enum):
    OVERLAP = "overlap"
    DEPENDENCY = "dependency"
    INTERFACE = "interface"


@dataclass
class FailurePattern:
    """Represents a recorded failure pattern between modules."""
    conflict_type: ConflictType
    modules_involved: Tuple[str, str]
    rollback_count: int = 0
    first_observed: datetime = field(default_factory=datetime.now)
    last_observed: datetime = field(default_factory=datetime.now)
    metadata: Dict = field(default_factory=dict)

    def increment_rollback(self) -> None:
        self.rollback_count += 1
        self.last_observed = datetime.now()


class FailurePatternMiner:
    """
    Records and analyzes multi-module failure patterns.
    Tracks conflict types, module interactions, rollback frequency,
    and provides data for meta-mutation selection.
    """

    def __init__(self):
        self._patterns: Dict[Tuple[str, str, ConflictType], FailurePattern] = {}
        self._module_conflicts: Dict[str, Set[str]] = defaultdict(set)
        self._conflict_type_counts: Dict[ConflictType, int] = defaultdict(int)
        self._total_rollbacks: int = 0

    def record_failure(
        self,
        module_a: str,
        module_b: str,
        conflict_type: ConflictType,
        metadata: Optional[Dict] = None
    ) -> None:
        """
        Record a failure pattern between two modules.

        Args:
            module_a: First module involved
            module_b: Second module involved
            conflict_type: Type of conflict (overlap, dependency, interface)
            metadata: Optional additional information about the failure
        """
        # Normalize module order for consistent key
        modules = tuple(sorted([module_a, module_b]))
        pattern_key = (modules[0], modules[1], conflict_type)

        if pattern_key in self._patterns:
            pattern = self._patterns[pattern_key]
            pattern.increment_rollback()
            if metadata:
                pattern.metadata.update(metadata)
        else:
            self._patterns[pattern_key] = FailurePattern(
                conflict_type=conflict_type,
                modules_involved=modules,
                rollback_count=1,
                metadata=metadata or {}
            )

        # Update tracking structures
        self._module_conflicts[module_a].add(module_b)
        self._module_conflicts[module_b].add(module_a)
        self._conflict_type_counts[conflict_type] += 1
        self._total_rollbacks += 1

    def get_module_conflict_summary(self, module: str) -> Dict:
        """
        Get conflict summary for a specific module.

        Args:
            module: Module name to query

        Returns:
            Dictionary with conflict statistics for the module
        """
        conflicts = self._module_conflicts.get(module, set())
        patterns = []

        for (m1, m2, ctype), pattern in self._patterns.items():
            if module in (m1, m2):
                patterns.append({
                    "other_module": m2 if m1 == module else m1,
                    "conflict_type": ctype.value,
                    "rollback_count": pattern.rollback_count,
                    "first_observed": pattern.first_observed.isoformat(),
                    "last_observed": pattern.last_observed.isoformat()
                })

        return {
            "module": module,
            "total_conflicting_modules": len(conflicts),
            "conflicting_modules": list(conflicts),
            "patterns": patterns,
            "total_rollbacks": sum(p["rollback_count"] for p in patterns)
        }

    def get_high_risk_patterns(self, min_rollbacks: int = 3) -> List[FailurePattern]:
        """
        Get patterns that have exceeded the minimum rollback threshold.

        Args:
            min_rollbacks: Minimum number of rollbacks to consider high risk

        Returns:
            List of high-risk failure patterns
        """
        return [
            pattern for pattern in self._patterns.values()
            if pattern.rollback_count >= min_rollbacks
        ]

    def get_meta_mutation_data(self) -> Dict:
        """
        Prepare data for meta-mutation selector.
        Returns structured data about failure patterns for informed mutation decisions.

        Returns:
            Dictionary with failure pattern statistics and recommendations
        """
        high_risk = self.get_high_risk_patterns()
        
        # Calculate conflict type distribution
        conflict_distribution = {
            ctype.value: self._conflict_type_counts.get(ctype, 0)
            for ctype in ConflictType
        }

        # Identify most problematic module pairs
        module_pair_risk = []
        for (m1, m2, ctype), pattern in self._patterns.items():
            if pattern.rollback_count > 0:
                module_pair_risk.append({
                    "modules": [m1, m2],
                    "conflict_type": ctype.value,
                    "rollback_count": pattern.rollback_count,
                    "risk_score": pattern.rollback_count / self._total_rollbacks if self._total_rollbacks > 0 else 0
                })

        # Sort by risk score descending
        module_pair_risk.sort(key=lambda x: x["risk_score"], reverse=True)

        return {
            "total_rollbacks": self._total_rollbacks,
            "unique_patterns": len(self._patterns),
            "high_risk_patterns": len(high_risk),
            "conflict_type_distribution": conflict_distribution,
            "module_pair_risk": module_pair_risk[:10],  # Top 10 riskiest pairs
            "recommendations": self._generate_recommendations(high_risk)
        }

    def _generate_recommendations(self, high_risk_patterns: List[FailurePattern]) -> List[str]:
        """Generate recommendations based on failure patterns."""
        recommendations = []
        
        if not high_risk_patterns:
            return recommendations

        # Group high-risk patterns by conflict type
        type_groups = defaultdict(list)
        for pattern in high_risk_patterns:
            type_groups[pattern.conflict_type].append(pattern)

        for conflict_type, patterns in type_groups.items():
            modules_affected = set()
            for pattern in patterns:
                modules_affected.update(pattern.modules_involved)
            
            if conflict_type == ConflictType.OVERLAP:
                recommendations.append(
                    f"High overlap conflicts detected between modules: {', '.join(sorted(modules_affected))}. "
                    "Consider refactoring to reduce code duplication."
                )
            elif conflict_type == ConflictType.DEPENDENCY:
                recommendations.append(
                    f"Circular or problematic dependencies detected between: {', '.join(sorted(modules_affected))}. "
                    "Review dependency graph and consider dependency inversion."
                )
            elif conflict_type == ConflictType.INTERFACE:
                recommendations.append(
                    f"Interface mismatches detected between: {', '.join(sorted(modules_affected))}. "
                    "Standardize interface contracts and add validation."
                )

        return recommendations

    def export_patterns(self, filepath: str) -> None:
        """Export failure patterns to a JSON file."""
        data = {
            "export_time": datetime.now().isoformat(),
            "patterns": [
                {
                    "modules": list(pattern.modules_involved),
                    "conflict_type": pattern.conflict_type.value,
                    "rollback_count": pattern.rollback_count,
                    "first_observed": pattern.first_observed.isoformat(),
                    "last_observed": pattern.last_observed.isoformat(),
                    "metadata": pattern.metadata
                }
                for pattern in self._patterns.values()
            ],
            "statistics": self.get_meta_mutation_data()
        }

        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)

    def import_patterns(self, filepath: str) -> None:
        """Import failure patterns from a JSON file."""
        with open(filepath, 'r') as f:
            data = json.load(f)

        for pattern_data in data.get("patterns", []):
            modules = tuple(pattern_data["modules"])
            conflict_type = ConflictType(pattern_data["conflict_type"])
            pattern_key = (modules[0], modules[1], conflict_type)

            pattern = FailurePattern(
                conflict_type=conflict_type,
                modules_involved=modules,
                rollback_count=pattern_data["rollback_count"],
                first_observed=datetime.fromisoformat(pattern_data["first_observed"]),
                last_observed=datetime.fromisoformat(pattern_data["last_observed"]),
                metadata=pattern_data.get("metadata", {})
            )

            self._patterns[pattern_key] = pattern
            self._module_conflicts[modules[0]].add(modules[1])
            self._module_conflicts[modules[1]].add(modules[0])
            self._conflict_type_counts[conflict_type] += pattern.rollback_count
            self._total_rollbacks += pattern.rollback_count

    def clear(self) -> None:
        """Clear all recorded patterns and statistics."""
        self._patterns.clear()
        self._module_conflicts.clear()
        self._conflict_type_counts.clear()
        self._total_rollbacks = 0