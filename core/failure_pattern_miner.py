from typing import Dict, List, Optional, Set, Tuple
from enum import Enum
from dataclasses import dataclass, field
from collections import defaultdict
import json
from datetime import datetime, timedelta
import re
import hashlib
from core.failure_pattern_ban_list import FailurePatternBanList


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
        self._failure_events: List[Dict] = []  # For health dashboard
        self._cycle_count: int = 0
        self._failure_log: List[Dict] = []  # Accumulated error records
        self._error_records: List[Dict] = []  # Shared error log for clustering
        self._last_fix_suggestions: Dict[Tuple[str, str], str] = {}
        self._lessons_learned: Dict = {}  # Lessons learned data
        self._capability_list: List[str] = []  # Capability list for duplication detection
        self._ban_list: FailurePatternBanList = FailurePatternBanList()  # Ban list for tracking failure patterns

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

        # Emit structured failure event to health dashboard
        failure_event = {
            "module_a": module_a,
            "module_b": module_b,
            "conflict_type": conflict_type.value,
            "error_type": self._classify_failure(conflict_type),
            "timestamp": datetime.now().isoformat(),
            "rollback_count": self._patterns[pattern_key].rollback_count
        }
        self._failure_events.append(failure_event)
        
        # Add to failure log for analysis
        self._failure_log.append({
            "module_a": module_a,
            "module_b": module_b,
            "conflict_type": conflict_type.value,
            "error_type": self._classify_failure(conflict_type),
            "timestamp": datetime.now().isoformat(),
            "error_message": metadata.get("error_message", "") if metadata else ""
        })
        
        # Add to shared error records
        self._error_records.append({
            "module_a": module_a,
            "module_b": module_b,
            "conflict_type": conflict_type.value,
            "error_type": self._classify_failure(conflict_type),
            "timestamp": datetime.now().isoformat(),
            "error_message": metadata.get("error_message", "") if metadata else ""
        })

        # Feed failure data into the ban list for tracking
        self._ban_list.record_failure(
            module_a=module_a,
            module_b=module_b,
            conflict_type=conflict_type.value,
            error_type=self._classify_failure(conflict_type),
            metadata=metadata
        )

    def _classify_failure(self, conflict_type: ConflictType) -> str:
        """Classify failure based on conflict type."""
        if conflict_type == ConflictType.DEPENDENCY:
            return "dependency"
        elif conflict_type == ConflictType.OVERLAP:
            return "sandbox"
        elif conflict_type == ConflictType.INTERFACE:
            return "rollback"
        else:
            return "other"

    def get_recent_failures(self, window_size: int = 3600) -> List[Dict]:
        """
        Get failures that occurred within the specified time window.

        Args:
            window_size: Time window in seconds (default 1 hour)

        Returns:
            List of failure events within the time window
        """
        cutoff_time = datetime.now() - timedelta(seconds=window_size)
        recent_failures = []
        
        for event in self._failure_events:
            event_time = datetime.fromisoformat(event["timestamp"])
            if event_time >= cutoff_time:
                recent_failures.append(event)
        
        return recent_failures

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

        # Include ban list data for more accurate domain tracking
        ban_list_data = self._ban_list.get_ban_list_data()

        return {
            "total_rollbacks": self._total_rollbacks,
            "unique_patterns": len(self._patterns),
            "high_risk_patterns": len(high_risk),
            "conflict_type_distribution": conflict_distribution,
            "module_pair_risk": module_pair_risk[:10],  # Top 10 riskiest pairs
            "recommendations": self._generate_recommendations(high_risk),
            "ban_list_data": ban_list_data  # Include ban list data for comprehensive tracking
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
            "statistics": self.get_meta_mutation_data(),
            "ban_list_data": self._ban_list.get_ban_list_data()
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

        # Import ban list data if available
        if "ban_list_data" in data:
            self._ban_list.import_data(data["ban_list_data"])

    def clear(self) -> None:
        """Clear all recorded patterns and statistics."""
        self._patterns.clear()
        self._module_conflicts.clear()
        self._conflict_type_counts.clear()
        self._total_rollbacks = 0
        self._failure_events.clear()
        self._failure_log.clear()
        self._error_records.clear()
        self._last_fix_suggestions.clear()
        self._lessons_learned.clear()
        self._cycle_count = 0
        self._capability_list.clear()
        self._ban_list.clear()

    def increment_cycle(self) -> None:
        """Increment the cycle counter and run failure log analysis every 10 cycles."""
        self._cycle_count += 1
        if self._cycle_count % 10 == 0:
            self._run_miner()

    def _run_miner(self) -> None:
        """
        Main miner execution: reads error records, runs clustering, generates suggestions,
        updates lessons_learned.json, and flags critical patterns.
        """
        if not self._error_records:
            return

        # Cluster errors by error type and module
        error_clusters = defaultdict(list)
        for record in self._error_records:
            error_type = record.get("error_type", "unknown")
            module = record.get("module_a", "unknown")
            error_clusters[(error_type, module)].append(record)
            
            module_b = record.get("module_b", "unknown")
            if module_b != module:
                error_clusters[(error_type, module_b)].append(record)

        # Generate fix suggestions and track pattern counts
        fix_suggestions: Dict[Tuple[str, str], str] = {}
        pattern_counts: Dict[Tuple[str, str], int] = defaultdict(int)
        
        for (error_type, module), records in error_clusters.items():
            count = len(records)
            pattern_counts[(error_type, module)] = count
            
            # Generate appropriate fix suggestion based on error type and module
            if error_type == "import error" or "import" in error_type.lower():
                error_messages = [r.get("error_message", "") for r in records]
                import_errors = [msg for msg in error_messages if "import" in msg.lower()]
                
                if import_errors:
                    module_names = set()
                    for msg in import_errors:
                        matches = re.findall(r"'(.*?)'", msg)
                        module_names.update(matches)
                    
                    if module_names:
                        fix_suggestions[(error_type, module)] = (
                            f"check import paths in {module}/ for modules: {', '.join(sorted(module_names))}"
                        )
                    else:
                        fix_suggestions[(error_type, module)] = (
                            f"check import paths in {module}/"
                        )
                else:
                    fix_suggestions[(error_type, module)] = (
                        f"check import paths in {module}/"
                    )
                    
            elif error_type == "syntax error" or "syntax" in error_type.lower():
                fix_suggestions[(error_type, module)] = (
                    f"fix syntax errors in {module}/"
                )
                
            elif error_type == "dependency":
                conflicting_modules = set()
                for r in records:
                    conflicting_modules.add(r.get("module_b", ""))
                conflicting_modules.discard(module)
                
                if conflicting_modules:
                    fix_suggestions[(error_type, module)] = (
                        f"resolve dependency conflicts between {module} and {', '.join(sorted(conflicting_modules))}"
                    )
                else:
                    fix_suggestions[(error_type, module)] = (
                        f"review dependencies in {module}/"
                    )
                    
            elif error_type == "sandbox":
                fix_suggestions[(error_type, module)] = (
                    f"refactor overlapping code in {module}/"
                )
                
            elif error_type == "rollback":
                fix_suggestions[(error_type, module)] = (
                    f"standardize interfaces in {module}/"
                )
                
            else:
                fix_suggestions[(error_type, module)] = (
                    f"investigate {error_type} errors in {module}/"
                )

        self._last_fix_suggestions = fix_suggestions

        # Build lessons learned data with critical flagging
        lessons = {}
        for (error_type, module), count in pattern_counts.items():
            suggestion = fix_suggestions.get((error_type, module), "")
            is_critical = count > 3
            lessons[f"{error_type}_{module}"] = {
                "error_type": error_type,
                "module": module,
                "occurrence_count": count,
                "is_critical": is_critical,
                "suggestion": suggestion,
                "last_updated": datetime.now().isoformat()
            }

        # Update internal lessons learned
        self._lessons_learned = lessons

        # Export to lessons_learned.json
        try:
            with open("lessons_learned.json", "w") as f:
                json.dump(lessons, f, indent=2)
        except IOError:
            pass  # Silently handle file write errors

        # Clear error records after processing to avoid reprocessing
        self._error_records.clear()

    def get_fix_suggestions(self) -> Dict[Tuple[str, str], str]:
        """
        Get the most recent fix suggestions from failure log analysis.

        Returns:
            Dictionary mapping (error_type, module) -> fix_suggestion
        """
        return self._last_fix_suggestions

    def get_cycle_count(self) -> int:
        """Get the current cycle count."""
        return self._cycle_count

    def get_lessons_learned(self) -> Dict:
        """Get the current lessons learned data."""
        return self._lessons_learned

    def add_error_record(self, record: Dict) -> None:
        """Add an error record to the shared error log."""
        self._error_records.append(record)

    def add_capability(self, capability: str) -> None:
        """
        Add a capability to the capability list for duplication detection.

        Args:
            capability: The capability text to add
        """
        self._capability_list.append(capability)

    def add_capabilities(self, capabilities: List[str]) -> None:
        """
        Add multiple capabilities to the capability list for duplication detection.

        Args:
            capabilities: List of capability texts to add
        """
        self._capability_list.extend(capabilities)

    def detect_capability_duplications(self) -> Dict[str, Dict]:
        """
        Detect goal/capability duplication patterns in the capability list.
        Parses the capability list for repeated entries (same text appearing >3 times),
        clusters them by content hash, and generates fix suggestions.

        Returns:
            Dictionary with duplication analysis results, including clusters and fix suggestions
        """
        if not self._capability_list:
            return {"duplications": [], "fix_suggestions": []}

        # Count occurrences of each capability text
        text_counts: Dict[str, int] = defaultdict(int)
        for capability in self._capability_list:
            text_counts[capability] += 1

        # Filter for repeated entries (appearing >3 times)
        duplicate_texts = {text: count for text, count in text_counts.items() if count > 3}

        if not duplicate_texts:
            return {"duplications": [], "fix_suggestions": []}

        # Cluster by content hash
        hash_clusters: Dict[str, List[str]] = defaultdict(list)
        for text in duplicate_texts:
            content_hash = hashlib.sha256(text.encode()).hexdigest()
            hash_clusters[content_hash].append(text)

        # Build duplication analysis results
        duplications = []
        fix_suggestions = []
        for content_hash, texts in hash_clusters.items():
            total_occurrences = sum(text_counts[text] for text in texts)
            cluster_info = {
                "content_hash": content_hash,
                "texts": texts,
                "total_occurrences": total_occurrences,
                "unique_texts": len(texts)
            }
            duplications.append(cluster_info)

            # Generate fix suggestion for this cluster
            if len(texts) == 1:
                text = texts[0]
                fix_suggestions.append(
                    f"add goal deduplication pass to goal_generator for text: '{text[:50]}...' "
                    f"(appeared {text_counts[text]} times)"
                )
            else:
                # Multiple similar texts in the same hash cluster
                sample_text = texts[0][:50] if texts[0] else "unknown"
                fix_suggestions.append(
                    f"add goal deduplication pass to goal_generator for cluster with hash {content_hash[:8]}... "
                    f"(sample: '{sample_text}...', total occurrences: {total_occurrences})"
                )

        # Add fix suggestions to lessons learned
        for suggestion in fix_suggestions:
            lesson_key = f"capability_duplication_{datetime.now().timestamp()}"
            self._lessons_learned[lesson_key] = {
                "error_type": "capability_duplication",
                "module": "goal_generator",
                "occurrence_count": sum(d["total_occurrences"] for d in duplications),
                "is_critical": True,
                "suggestion": suggestion,
                "last_updated": datetime.now().isoformat()
            }

        # Update last fix suggestions with capability duplication fixes
        for suggestion in fix_suggestions:
            self._last_fix_suggestions[("capability_duplication", "goal_generator")] = suggestion

        # Export updated lessons learned
        try:
            with open("lessons_learned.json", "w") as f:
                json.dump(self._lessons_learned, f, indent=2)
        except IOError:
            pass

        return {
            "duplications": duplications,
            "fix_suggestions": fix_suggestions
        }

    def get_capability_duplication_report(self) -> Dict:
        """
        Get a comprehensive report on capability duplications.

        Returns:
            Dictionary with duplication statistics and recommendations
        """
        duplication_data = self.detect_capability_duplications()
        
        if not duplication_data["duplications"]:
            return {
                "has_duplications": False,
                "total_duplicate_entries": 0,
                "total_clusters": 0,
                "fix_suggestions": []
            }

        total_duplicate_entries = sum(d["total_occurrences"] for d in duplication_data["duplications"])
        
        return {
            "has_duplications": True,
            "total_duplicate_entries": total_duplicate_entries,
            "total_clusters": len(duplication_data["duplications"]),
            "duplications": duplication_data["duplications"],
            "fix_suggestions": duplication_data["fix_suggestions"]
        }

    def get_ban_list(self) -> FailurePatternBanList:
        """
        Get the ban list instance for direct access.

        Returns:
            The FailurePatternBanList instance
        """
        return self._ban_list

    def get_ban_list_data(self) -> Dict:
        """
        Get the ban list data for external use.

        Returns:
            Dictionary with ban list data
        """
        return self._ban_list.get_ban_list_data()