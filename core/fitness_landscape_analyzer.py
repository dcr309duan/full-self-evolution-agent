"""Module for analyzing the fitness landscape of an agent's test performance.

This module tracks test outcomes over time, identifies patterns in test
passing/failing, computes diversity metrics, and suggests new test types
to fill coverage gaps. Also includes Nash equilibrium visualization data
tracking stagnation periods, coordination potential scores, and coordinated
mutation targets.
"""

from collections import defaultdict, Counter
from typing import Dict, List, Set, Tuple, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
import numpy as np
from enum import Enum


class TestOutcome(Enum):
    """Possible outcomes for a test execution."""
    PASS = "pass"
    FAIL = "fail"
    ERROR = "error"
    TIMEOUT = "timeout"


@dataclass
class TestRecord:
    """Record of a single test execution."""
    test_id: str
    test_type: str
    outcome: TestOutcome
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TestTypeInfo:
    """Information about a specific test type."""
    name: str
    description: str
    difficulty: float = 0.5  # 0.0 (easy) to 1.0 (hard)
    category: str = "general"
    prerequisites: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)


@dataclass
class NashEquilibriumData:
    """Data related to Nash equilibrium detection and visualization."""
    stagnation_periods: List[Dict[str, Any]] = field(default_factory=list)
    coordination_potential: Dict[Tuple[str, str], float] = field(default_factory=dict)
    recommended_mutation_targets: List[Tuple[str, str]] = field(default_factory=list)
    equilibrium_detected: bool = False


class FitnessLandscapeAnalyzer:
    """Analyzes the fitness landscape of an agent's test performance over time."""

    def __init__(self):
        self.test_history: List[TestRecord] = []
        self.test_types: Dict[str, TestTypeInfo] = {}
        self._current_episode: List[TestRecord] = []
        # Nash equilibrium tracking
        self._module_improvement_history: Dict[str, List[bool]] = defaultdict(list)
        self._stagnation_threshold: int = 5  # episodes without improvement
        self._nash_data: NashEquilibriumData = NashEquilibriumData()

    def register_test_type(self, test_type_info: TestTypeInfo) -> None:
        """Register a new test type for tracking."""
        self.test_types[test_type_info.name] = test_type_info

    def record_test_outcome(self, test_id: str, test_type: str,
                            outcome: TestOutcome, **metadata) -> None:
        """Record the outcome of a test execution."""
        record = TestRecord(
            test_id=test_id,
            test_type=test_type,
            outcome=outcome,
            metadata=metadata
        )
        self.test_history.append(record)
        self._current_episode.append(record)

    def start_new_episode(self) -> None:
        """Start tracking a new episode (e.g., new training run)."""
        self._current_episode = []

    def get_test_outcomes_over_time(self, test_type: Optional[str] = None
                                    ) -> Dict[str, List[Tuple[datetime, TestOutcome]]]:
        """Get test outcomes over time, optionally filtered by test type.

        Returns:
            Dict mapping test_id to list of (timestamp, outcome) tuples.
        """
        outcomes: Dict[str, List[Tuple[datetime, TestOutcome]]] = defaultdict(list)
        for record in self.test_history:
            if test_type is None or record.test_type == test_type:
                outcomes[record.test_id].append((record.timestamp, record.outcome))
        return dict(outcomes)

    def find_always_passed_tests(self, min_attempts: int = 5) -> List[str]:
        """Identify tests that have always been passed.

        Args:
            min_attempts: Minimum number of attempts to consider a test.

        Returns:
            List of test_ids that have never failed.
        """
        test_outcomes: Dict[str, List[TestOutcome]] = defaultdict(list)
        for record in self.test_history:
            test_outcomes[record.test_id].append(record.outcome)

        always_passed = []
        for test_id, outcomes in test_outcomes.items():
            if len(outcomes) >= min_attempts:
                if all(o == TestOutcome.PASS for o in outcomes):
                    always_passed.append(test_id)
        return always_passed

    def find_never_passed_tests(self, min_attempts: int = 3) -> List[str]:
        """Identify tests that have never been passed.

        Args:
            min_attempts: Minimum number of attempts to consider a test.

        Returns:
            List of test_ids that have never passed.
        """
        test_outcomes: Dict[str, List[TestOutcome]] = defaultdict(list)
        for record in self.test_history:
            test_outcomes[record.test_id].append(record.outcome)

        never_passed = []
        for test_id, outcomes in test_outcomes.items():
            if len(outcomes) >= min_attempts:
                if all(o != TestOutcome.PASS for o in outcomes):
                    never_passed.append(test_id)
        return never_passed

    def compute_pass_rate(self, test_id: str) -> float:
        """Compute the pass rate for a specific test.

        Returns:
            Float between 0.0 and 1.0 representing pass rate.
        """
        outcomes = [r.outcome for r in self.test_history if r.test_id == test_id]
        if not outcomes:
            return 0.0
        return sum(1 for o in outcomes if o == TestOutcome.PASS) / len(outcomes)

    def compute_landscape_diversity_score(self) -> Dict[str, float]:
        """Compute diversity metrics for the fitness landscape.

        Returns:
            Dict with diversity metrics:
                - 'type_diversity': Shannon entropy of test type distribution
                - 'difficulty_diversity': Variance in test difficulties
                - 'category_diversity': Number of distinct categories
                - 'overall_diversity': Composite diversity score
        """
        if not self.test_history:
            return {
                'type_diversity': 0.0,
                'difficulty_diversity': 0.0,
                'category_diversity': 0.0,
                'overall_diversity': 0.0
            }

        # Type diversity (Shannon entropy)
        type_counts = Counter(r.test_type for r in self.test_history)
        total = sum(type_counts.values())
        type_probs = [count / total for count in type_counts.values()]
        type_diversity = -sum(p * np.log(p) for p in type_probs if p > 0)

        # Difficulty diversity
        difficulties = []
        for record in self.test_history:
            if record.test_type in self.test_types:
                difficulties.append(self.test_types[record.test_type].difficulty)
        difficulty_diversity = float(np.var(difficulties)) if difficulties else 0.0

        # Category diversity
        categories = set()
        for record in self.test_history:
            if record.test_type in self.test_types:
                categories.add(self.test_types[record.test_type].category)
        category_diversity = len(categories)

        # Overall composite score (normalized)
        max_type_diversity = np.log(len(type_counts)) if type_counts else 1
        normalized_type_div = type_diversity / max_type_diversity if max_type_diversity > 0 else 0
        normalized_difficulty_div = min(difficulty_diversity / 0.25, 1.0)  # Normalize to [0,1]
        normalized_category_div = min(category_diversity / 10.0, 1.0)  # Normalize to [0,1]

        overall_diversity = (normalized_type_div + normalized_difficulty_div +
                             normalized_category_div) / 3.0

        return {
            'type_diversity': float(type_diversity),
            'difficulty_diversity': difficulty_diversity,
            'category_diversity': category_diversity,
            'overall_diversity': overall_diversity
        }

    def suggest_new_test_types(self, max_suggestions: int = 5) -> List[Dict[str, Any]]:
        """Suggest new test types based on gaps in coverage.

        Analyzes current test coverage and suggests new test types to fill
        identified gaps.

        Args:
            max_suggestions: Maximum number of suggestions to return.

        Returns:
            List of dicts with keys:
                - 'suggested_type': Name of suggested test type
                - 'rationale': Reason for suggestion
                - 'target_difficulty': Suggested difficulty level
                - 'related_types': Existing related test types
        """
        suggestions = []

        # Analyze current coverage
        covered_types = set(r.test_type for r in self.test_history)
        all_registered_types = set(self.test_types.keys())

        # Check for difficulty gaps
        difficulties_covered = set()
        for record in self.test_history:
            if record.test_type in self.test_types:
                diff = self.test_types[record.test_type].difficulty
                difficulties_covered.add(round(diff * 10) / 10)  # Round to 1 decimal

        # Suggest missing difficulty levels
        for difficulty_level in [0.2, 0.4, 0.6, 0.8]:
            if difficulty_level not in difficulties_covered:
                suggestions.append({
                    'suggested_type': f'gap_difficulty_{difficulty_level:.1f}',
                    'rationale': f'No tests at difficulty level {difficulty_level:.1f}',
                    'target_difficulty': difficulty_level,
                    'related_types': list(covered_types)
                })

        # Check for category gaps
        covered_categories = set()
        for record in self.test_history:
            if record.test_type in self.test_types:
                covered_categories.add(self.test_types[record.test_type].category)

        # Suggest missing categories
        all_possible_categories = {'logic', 'math', 'language', 'reasoning',
                                   'memory', 'planning', 'creativity'}
        missing_categories = all_possible_categories - covered_categories
        for category in missing_categories:
            suggestions.append({
                'suggested_type': f'new_category_{category}',
                'rationale': f'Missing test category: {category}',
                'target_difficulty': 0.5,
                'related_types': []
            })

        # Check for tests that are too easy (always passed)
        always_passed = self.find_always_passed_tests(min_attempts=5)
        if always_passed:
            suggestions.append({
                'suggested_type': 'increased_difficulty_variant',
                'rationale': f'{len(always_passed)} tests are always passed; '
                             f'consider creating harder variants',
                'target_difficulty': 0.7,
                'related_types': always_passed[:3]
            })

        # Check for tests that are too hard (never passed)
        never_passed = self.find_never_passed_tests(min_attempts=3)
        if never_passed:
            suggestions.append({
                'suggested_type': 'simplified_variant',
                'rationale': f'{len(never_passed)} tests are never passed; '
                             f'consider creating simplified versions or hints',
                'target_difficulty': 0.3,
                'related_types': never_passed[:3]
            })

        return suggestions[:max_suggestions]

    def get_performance_summary(self) -> Dict[str, Any]:
        """Get a comprehensive summary of the current fitness landscape.

        Returns:
            Dict with summary statistics.
        """
        if not self.test_history:
            return {'total_tests': 0, 'status': 'no_data'}

        total = len(self.test_history)
        passes = sum(1 for r in self.test_history if r.outcome == TestOutcome.PASS)
        fails = sum(1 for r in self.test_history if r.outcome == TestOutcome.FAIL)
        errors = sum(1 for r in self.test_history if r.outcome == TestOutcome.ERROR)

        unique_tests = len(set(r.test_id for r in self.test_history))
        unique_types = len(set(r.test_type for r in self.test_history))

        diversity = self.compute_landscape_diversity_score()

        return {
            'total_tests': total,
            'total_passes': passes,
            'total_fails': fails,
            'total_errors': errors,
            'pass_rate': passes / total if total > 0 else 0.0,
            'unique_tests': unique_tests,
            'unique_test_types': unique_types,
            'diversity_scores': diversity,
            'always_passed_count': len(self.find_always_passed_tests()),
            'never_passed_count': len(self.find_never_passed_tests()),
            'suggested_new_types': self.suggest_new_test_types(),
            'nash_equilibrium_data': self._get_nash_equilibrium_data()
        }

    def get_test_type_distribution(self) -> Dict[str, int]:
        """Get the distribution of test types in the history."""
        return dict(Counter(r.test_type for r in self.test_history))

    def get_recent_performance(self, n_recent: int = 100) -> Dict[str, float]:
        """Get performance metrics for the most recent tests.

        Args:
            n_recent: Number of most recent tests to consider.

        Returns:
            Dict with pass_rate and fail_rate for recent tests.
        """
        recent = self.test_history[-n_recent:] if self.test_history else []
        if not recent:
            return {'pass_rate': 0.0, 'fail_rate': 0.0}

        passes = sum(1 for r in recent if r.outcome == TestOutcome.PASS)
        return {
            'pass_rate': passes / len(recent),
            'fail_rate': (len(recent) - passes) / len(recent)
        }

    def record_module_improvement(self, module_name: str, improved: bool) -> None:
        """Record whether a module showed improvement in the current episode.

        Args:
            module_name: Name of the module (e.g., test type or agent component).
            improved: Whether the module improved in this episode.
        """
        self._module_improvement_history[module_name].append(improved)
        self._update_nash_equilibrium_data()

    def _update_nash_equilibrium_data(self) -> None:
        """Update Nash equilibrium tracking data based on module improvement history."""
        # Reset nash data
        self._nash_data = NashEquilibriumData()

        # Track stagnation periods for each module
        for module, improvements in self._module_improvement_history.items():
            stagnation_start = None
            for i, improved in enumerate(improvements):
                if not improved:
                    if stagnation_start is None:
                        stagnation_start = i
                else:
                    if stagnation_start is not None:
                        duration = i - stagnation_start
                        if duration >= self._stagnation_threshold:
                            self._nash_data.stagnation_periods.append({
                                'module': module,
                                'start_episode': stagnation_start,
                                'end_episode': i - 1,
                                'duration': duration
                            })
                        stagnation_start = None
            # Check if still in stagnation at end
            if stagnation_start is not None:
                duration = len(improvements) - stagnation_start
                if duration >= self._stagnation_threshold:
                    self._nash_data.stagnation_periods.append({
                        'module': module,
                        'start_episode': stagnation_start,
                        'end_episode': len(improvements) - 1,
                        'duration': duration
                    })

        # Compute coordination potential for each module pair
        modules = list(self._module_improvement_history.keys())
        for i in range(len(modules)):
            for j in range(i + 1, len(modules)):
                mod_a = modules[i]
                mod_b = modules[j]
                improvements_a = self._module_improvement_history[mod_a]
                improvements_b = self._module_improvement_history[mod_b]

                # Compute coordination potential as correlation of improvement patterns
                min_len = min(len(improvements_a), len(improvements_b))
                if min_len > 1:
                    a_recent = improvements_a[-min_len:]
                    b_recent = improvements_b[-min_len:]
                    # Convert to numeric: 1 for improvement, 0 for no improvement
                    a_numeric = [1 if x else 0 for x in a_recent]
                    b_numeric = [1 if x else 0 for x in b_recent]
                    if len(set(a_numeric)) > 1 and len(set(b_numeric)) > 1:
                        correlation = np.corrcoef(a_numeric, b_numeric)[0, 1]
                        # Normalize to [0, 1] where 1 means perfect correlation
                        coordination_potential = (correlation + 1) / 2
                    else:
                        coordination_potential = 0.0
                else:
                    coordination_potential = 0.0

                self._nash_data.coordination_potential[(mod_a, mod_b)] = coordination_potential

        # Detect equilibrium: all modules stagnant and high coordination potential
        stagnant_modules = set()
        for period in self._nash_data.stagnation_periods:
            if period['duration'] >= self._stagnation_threshold:
                stagnant_modules.add(period['module'])

        if len(stagnant_modules) >= 2:
            # Check if all stagnant modules have high coordination potential
            high_coordination_pairs = 0
            total_pairs = 0
            stagnant_list = list(stagnant_modules)
            for i in range(len(stagnant_list)):
                for j in range(i + 1, len(stagnant_list)):
                    pair = (stagnant_list[i], stagnant_list[j])
                    if pair in self._nash_data.coordination_potential:
                        total_pairs += 1
                        if self._nash_data.coordination_potential[pair] > 0.7:
                            high_coordination_pairs += 1

            if total_pairs > 0 and high_coordination_pairs / total_pairs > 0.5:
                self._nash_data.equilibrium_detected = True

        # Generate recommended coordinated mutation targets when equilibrium detected
        if self._nash_data.equilibrium_detected:
            # Find pairs with highest coordination potential among stagnant modules
            sorted_pairs = sorted(
                [(pair, score) for pair, score in self._nash_data.coordination_potential.items()
                 if pair[0] in stagnant_modules and pair[1] in stagnant_modules],
                key=lambda x: x[1],
                reverse=True
            )
            # Recommend top 3 pairs for coordinated mutation
            for pair, score in sorted_pairs[:3]:
                self._nash_data.recommended_mutation_targets.append(pair)

    def _get_nash_equilibrium_data(self) -> Dict[str, Any]:
        """Get the current Nash equilibrium tracking data as a dictionary.

        Returns:
            Dict with keys:
                - 'stagnation_periods': List of stagnation period dicts
                - 'coordination_potential': Dict mapping module pair to score
                - 'recommended_mutation_targets': List of recommended mutation pairs
                - 'equilibrium_detected': Boolean flag
        """
        return {
            'stagnation_periods': self._nash_data.stagnation_periods,
            'coordination_potential': {
                f"{pair[0]}-{pair[1]}": score
                for pair, score in self._nash_data.coordination_potential.items()
            },
            'recommended_mutation_targets': [
                f"{pair[0]}-{pair[1]}"
                for pair in self._nash_data.recommended_mutation_targets
            ],
            'equilibrium_detected': self._nash_data.equilibrium_detected
        }

    def get_nash_equilibrium_data(self) -> NashEquilibriumData:
        """Get the current Nash equilibrium tracking data object.

        Returns:
            NashEquilibriumData instance with current tracking data.
        """
        return self._nash_data