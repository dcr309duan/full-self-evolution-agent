"""meta_cognitive_evaluator.py

Tracks long-term fitness trends for evolutionary parameter adjustments.
Records mutation outcomes, maintains rolling windows, computes success rates,
detects brittleness, and recommends parameter adjustments.
Includes ecological health metrics: test suite diversity, novelty scoring,
fitness landscape change rate, correlation analysis, and static test alerts.
"""

import time
import math
from collections import deque, Counter
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

# --- Data Structures ---

@dataclass
class MutationRecord:
    """Record of a single mutation outcome."""
    timestamp: float
    category: str  # 'core' or 'peripheral'
    success: bool
    parameters: Dict[str, float]
    test_type: Optional[str] = None  # Type of test for diversity tracking
    test_content: Optional[str] = None  # Content hash for novelty scoring

@dataclass
class TrendState:
    """Current trend analysis state."""
    core_success_rate: float
    peripheral_success_rate: float
    overall_success_rate: float
    core_consecutive_failures: int
    is_brittle: bool
    window_size: int
    total_records: int
    recommended_adjustments: Dict[str, float]
    # Ecological health metrics
    test_diversity_index: float = 0.0
    novelty_score: float = 0.0
    landscape_change_rate: float = 0.0
    landscape_capability_correlation: float = 0.0
    static_test_alert: bool = False

# --- Main Evaluator Class ---

class MetaCognitiveEvaluator:
    """Evaluates long-term fitness trends and detects brittleness."""

    WINDOW_SIZE = 30
    BRITTLENESS_CORE_THRESHOLD = 0.6  # 60%
    BRITTLENESS_CONSECUTIVE_FAILURES = 3
    PERFORMANCE_DEGRADATION_THRESHOLD = 0.15  # 15% degradation
    PERFORMANCE_DEGRADATION_CYCLES = 20  # over 20 cycles
    STATIC_TEST_THRESHOLD = 20  # cycles before alerting static tests

    def __init__(self, window_size: int = WINDOW_SIZE):
        self.window_size = window_size
        self._records: deque = deque(maxlen=window_size)
        self._all_records: List[MutationRecord] = []  # full history
        self._core_consecutive_failures = 0
        self._performance_history: List[float] = []  # stores overall success rates over time
        self._baseline_performance: Optional[float] = None  # historical baseline
        # Ecological health tracking
        self._test_type_history: deque = deque(maxlen=window_size)  # For diversity index
        self._test_content_history: deque = deque(maxlen=window_size)  # For novelty scoring
        self._landscape_change_history: List[float] = []  # Rate of landscape change
        self._capability_speed_history: List[float] = []  # Capability acquisition speed
        self._cycles_since_last_new_test: int = 0  # Counter for static test detection

    # --- Recording ---

    def record_mutation(self, category: str, success: bool, parameters: Dict[str, float], 
                       test_type: Optional[str] = None, test_content: Optional[str] = None) -> None:
        """Record a mutation outcome with current timestamp and optional test metadata."""
        record = MutationRecord(
            timestamp=time.time(),
            category=category,
            success=success,
            parameters=parameters.copy(),
            test_type=test_type,
            test_content=test_content
        )
        self._records.append(record)
        self._all_records.append(record)

        # Track test type for diversity
        if test_type:
            self._test_type_history.append(test_type)
        
        # Track test content for novelty
        if test_content:
            self._test_content_history.append(test_content)
            self._cycles_since_last_new_test = 0
        else:
            self._cycles_since_last_new_test += 1

        # Track landscape changes (based on parameter changes)
        if len(self._landscape_change_history) == 0 or parameters != self._records[-2].parameters if len(self._records) > 1 else True:
            self._landscape_change_history.append(1.0)  # Change detected
        else:
            self._landscape_change_history.append(0.0)  # No change

        # Track capability acquisition speed (success rate over time)
        if success:
            self._capability_speed_history.append(1.0)
        else:
            self._capability_speed_history.append(0.0)

        # Track consecutive core failures
        if category == 'core' and not success:
            self._core_consecutive_failures += 1
        elif category == 'core' and success:
            self._core_consecutive_failures = 0

    # --- Analysis ---

    def _compute_success_rate(self, category: Optional[str] = None) -> float:
        """Compute success rate for given category (or overall if None) over rolling window."""
        if not self._records:
            return 0.0

        if category:
            relevant = [r for r in self._records if r.category == category]
        else:
            relevant = list(self._records)

        if not relevant:
            return 0.0

        successes = sum(1 for r in relevant if r.success)
        return successes / len(relevant)

    def _detect_brittleness(self) -> bool:
        """Return True if core success rate < 60% or core failures >= 3 consecutively."""
        core_rate = self._compute_success_rate('core')
        if core_rate < self.BRITTLENESS_CORE_THRESHOLD:
            return True
        if self._core_consecutive_failures >= self.BRITTLENESS_CONSECUTIVE_FAILURES:
            return True
        return False

    def _update_performance_history(self) -> None:
        """Update performance history with current overall success rate."""
        overall_rate = self._compute_success_rate()
        self._performance_history.append(overall_rate)
        # Keep only last PERFORMANCE_DEGRADATION_CYCLES records for comparison
        if len(self._performance_history) > self.PERFORMANCE_DEGRADATION_CYCLES:
            self._performance_history = self._performance_history[-self.PERFORMANCE_DEGRADATION_CYCLES:]

    def _set_baseline_performance(self) -> None:
        """Set baseline performance from the first available data point."""
        if self._baseline_performance is None and self._performance_history:
            self._baseline_performance = self._performance_history[0]

    def _check_performance_degradation(self) -> bool:
        """Check if performance is degrading compared to baseline over last 20 cycles."""
        if self._baseline_performance is None or len(self._performance_history) < self.PERFORMANCE_DEGRADATION_CYCLES:
            return False
        
        current_performance = self._performance_history[-1]
        # Calculate degradation percentage
        if self._baseline_performance > 0:
            degradation = (self._baseline_performance - current_performance) / self._baseline_performance
            return degradation > self.PERFORMANCE_DEGRADATION_THRESHOLD
        return False

    def _compute_test_diversity_index(self) -> float:
        """Compute Shannon entropy of test types in the rolling window."""
        if not self._test_type_history:
            return 0.0
        
        type_counts = Counter(self._test_type_history)
        total = len(self._test_type_history)
        entropy = 0.0
        
        for count in type_counts.values():
            if count > 0:
                p = count / total
                entropy -= p * math.log2(p)
        
        # Normalize by max possible entropy (log2 of number of unique types)
        unique_types = len(type_counts)
        if unique_types > 1:
            max_entropy = math.log2(unique_types)
            return entropy / max_entropy if max_entropy > 0 else 0.0
        return 0.0

    def _compute_novelty_score(self) -> float:
        """Compute novelty score of new tests vs existing ones."""
        if len(self._test_content_history) < 2:
            return 0.0
        
        # Compare most recent test content with previous ones
        recent_content = list(self._test_content_history)[-1]
        previous_contents = list(self._test_content_history)[:-1]
        
        if not previous_contents:
            return 1.0  # First test is always novel
        
        # Simple novelty: 1 if new content not seen before, else 0
        # Could be enhanced with more sophisticated similarity metrics
        if recent_content not in previous_contents:
            return 1.0
        return 0.0

    def _compute_landscape_change_rate(self) -> float:
        """Compute rate of fitness landscape change (how quickly tests evolve)."""
        if len(self._landscape_change_history) < 2:
            return 0.0
        
        # Calculate rate as proportion of changes in recent window
        recent_changes = self._landscape_change_history[-self.window_size:]
        if not recent_changes:
            return 0.0
        
        change_count = sum(recent_changes)
        return change_count / len(recent_changes)

    def _compute_landscape_capability_correlation(self) -> float:
        """Compute correlation between landscape changes and capability acquisition speed."""
        if len(self._landscape_change_history) < 2 or len(self._capability_speed_history) < 2:
            return 0.0
        
        # Align lengths
        min_len = min(len(self._landscape_change_history), len(self._capability_speed_history))
        landscape = self._landscape_change_history[-min_len:]
        capability = self._capability_speed_history[-min_len:]
        
        # Compute Pearson correlation coefficient
        n = len(landscape)
        if n < 2:
            return 0.0
        
        mean_landscape = sum(landscape) / n
        mean_capability = sum(capability) / n
        
        numerator = sum((l - mean_landscape) * (c - mean_capability) for l, c in zip(landscape, capability))
        denom_landscape = math.sqrt(sum((l - mean_landscape) ** 2 for l in landscape))
        denom_capability = math.sqrt(sum((c - mean_capability) ** 2 for c in capability))
        
        if denom_landscape == 0 or denom_capability == 0:
            return 0.0
        
        correlation = numerator / (denom_landscape * denom_capability)
        return max(-1.0, min(1.0, correlation))  # Clamp to [-1, 1]

    def _check_static_test_alert(self) -> bool:
        """Alert if test suite becomes static for >20 cycles."""
        return self._cycles_since_last_new_test > self.STATIC_TEST_THRESHOLD

    def _recommend_adjustments(self) -> Dict[str, float]:
        """Generate recommended parameter adjustments based on trend state."""
        adjustments = {}
        core_rate = self._compute_success_rate('core')
        peripheral_rate = self._compute_success_rate('peripheral')
        is_brittle = self._detect_brittleness()
        performance_degraded = self._check_performance_degradation()
        static_test = self._check_static_test_alert()

        if is_brittle or performance_degraded or static_test:
            # Reduce mutation aggressiveness for core parameters
            adjustments['core_mutation_rate'] = 0.5  # reduce by half
            adjustments['core_mutation_scale'] = 0.7  # smaller steps
            adjustments['exploration_rate'] = 0.3     # more exploitation
            if performance_degraded:
                adjustments['trigger_optimization_engine'] = 1.0  # flag for optimization
            if static_test:
                adjustments['force_test_diversification'] = 1.0  # flag for new tests
        else:
            # Normal adjustments based on success rates
            if core_rate < 0.7:
                adjustments['core_mutation_rate'] = 0.8  # slight reduction
            else:
                adjustments['core_mutation_rate'] = 1.0  # keep default

            if peripheral_rate < 0.5:
                adjustments['peripheral_mutation_rate'] = 1.2  # increase exploration
            else:
                adjustments['peripheral_mutation_rate'] = 1.0

            # General trend: if overall success is high, increase exploration
            overall_rate = self._compute_success_rate()
            if overall_rate > 0.8:
                adjustments['exploration_rate'] = 1.1
            else:
                adjustments['exploration_rate'] = 1.0

        return adjustments

    # --- Query Methods ---

    def get_trend_state(self) -> TrendState:
        """Return current trend analysis state with ecological health metrics."""
        # Update performance tracking before returning state
        self._update_performance_history()
        self._set_baseline_performance()
        
        return TrendState(
            core_success_rate=self._compute_success_rate('core'),
            peripheral_success_rate=self._compute_success_rate('peripheral'),
            overall_success_rate=self._compute_success_rate(),
            core_consecutive_failures=self._core_consecutive_failures,
            is_brittle=self._detect_brittleness(),
            window_size=self.window_size,
            total_records=len(self._all_records),
            recommended_adjustments=self._recommend_adjustments(),
            test_diversity_index=self._compute_test_diversity_index(),
            novelty_score=self._compute_novelty_score(),
            landscape_change_rate=self._compute_landscape_change_rate(),
            landscape_capability_correlation=self._compute_landscape_capability_correlation(),
            static_test_alert=self._check_static_test_alert()
        )

    def get_recommended_adjustments(self) -> Dict[str, float]:
        """Return recommended parameter adjustments based on current trends."""
        self._update_performance_history()
        self._set_baseline_performance()
        return self._recommend_adjustments()

    def is_brittle(self) -> bool:
        """Return True if system is currently in brittle state."""
        return self._detect_brittleness()

    def get_core_success_rate(self) -> float:
        """Return core success rate over rolling window."""
        return self._compute_success_rate('core')

    def get_peripheral_success_rate(self) -> float:
        """Return peripheral success rate over rolling window."""
        return self._compute_success_rate('peripheral')

    def get_overall_success_rate(self) -> float:
        """Return overall success rate over rolling window."""
        return self._compute_success_rate()

    def get_core_consecutive_failures(self) -> int:
        """Return number of consecutive core failures."""
        return self._core_consecutive_failures

    def get_window_size(self) -> int:
        """Return current rolling window size."""
        return self.window_size

    def set_window_size(self, size: int) -> None:
        """Change rolling window size (preserves recent records up to new size)."""
        if size < 1:
            raise ValueError("Window size must be at least 1")
        self.window_size = size
        # Rebuild deque with new maxlen, keeping most recent records
        current_records = list(self._records)
        self._records = deque(maxlen=size)
        for record in current_records[-size:]:
            self._records.append(record)
        # Rebuild test type and content histories
        self._test_type_history = deque(maxlen=size)
        self._test_content_history = deque(maxlen=size)
        for record in self._records:
            if record.test_type:
                self._test_type_history.append(record.test_type)
            if record.test_content:
                self._test_content_history.append(record.test_content)
        # Recompute consecutive failures from remaining records
        self._core_consecutive_failures = 0
        for record in reversed(self._records):
            if record.category == 'core' and not record.success:
                self._core_consecutive_failures += 1
            elif record.category == 'core' and record.success:
                break

    def get_full_history(self) -> List[MutationRecord]:
        """Return all recorded mutations (full history)."""
        return self._all_records.copy()

    def get_window_records(self) -> List[MutationRecord]:
        """Return records currently in rolling window."""
        return list(self._records)

    def clear_history(self) -> None:
        """Clear all recorded data and reset state."""
        self._records.clear()
        self._all_records.clear()
        self._core_consecutive_failures = 0
        self._performance_history.clear()
        self._baseline_performance = None
        self._test_type_history.clear()
        self._test_content_history.clear()
        self._landscape_change_history.clear()
        self._capability_speed_history.clear()
        self._cycles_since_last_new_test = 0

    def __repr__(self) -> str:
        state = self.get_trend_state()
        return (
            f"MetaCognitiveEvaluator(window={self.window_size}, "
            f"records={state.total_records}, "
            f"core_rate={state.core_success_rate:.2%}, "
            f"peripheral_rate={state.peripheral_success_rate:.2%}, "
            f"brittle={state.is_brittle}, "
            f"diversity={state.test_diversity_index:.3f}, "
            f"novelty={state.novelty_score:.3f}, "
            f"landscape_change={state.landscape_change_rate:.3f}, "
            f"static_alert={state.static_test_alert})"
        )


# --- Convenience Functions ---

def create_default_evaluator() -> MetaCognitiveEvaluator:
    """Create an evaluator with default settings."""
    return MetaCognitiveEvaluator()

def evaluate_trends(evaluator: MetaCognitiveEvaluator) -> TrendState:
    """Convenience function to get trend state from an evaluator."""
    return evaluator.get_trend_state()