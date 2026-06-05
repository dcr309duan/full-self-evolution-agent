import pytest
import os
import json
import tempfile
from unittest.mock import MagicMock, patch

# Assuming the module is named meta_parameter_scheduler
# Adjust imports based on actual module structure
from meta_parameter_scheduler import MetaParameterScheduler

@pytest.fixture
def scheduler():
    """Create a scheduler instance with default parameters for testing."""
    return MetaParameterScheduler(
        window_size=10,
        mutation_rate=0.1,
        threshold=0.5,
        persistence_file=None  # No persistence for basic tests
    )

@pytest.fixture
def scheduler_with_persistence():
    """Create a scheduler with a temporary persistence file."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
        temp_file = f.name
    yield MetaParameterScheduler(
        window_size=10,
        mutation_rate=0.1,
        threshold=0.5,
        persistence_file=temp_file
    )
    os.unlink(temp_file)

class TestSlidingWindow:
    """Test that sliding window correctly tracks last 10 outcomes."""

    def test_window_starts_empty(self, scheduler):
        """Initially, the window should be empty."""
        assert len(scheduler.outcomes) == 0

    def test_window_accumulates_outcomes(self, scheduler):
        """Adding outcomes should fill the window up to window_size."""
        for i in range(5):
            scheduler.record_outcome(True)
        assert len(scheduler.outcomes) == 5

    def test_window_max_size(self, scheduler):
        """Window should not exceed window_size (10) outcomes."""
        for i in range(15):
            scheduler.record_outcome(True)
        assert len(scheduler.outcomes) == 10

    def test_window_sliding_behavior(self, scheduler):
        """Oldest outcomes should be removed when new ones are added beyond window_size."""
        # Add 10 outcomes
        for i in range(10):
            scheduler.record_outcome(i % 2 == 0)  # Alternating True/False
        first_outcome = scheduler.outcomes[0]
        # Add one more outcome
        scheduler.record_outcome(True)
        # The first outcome should now be the second one originally
        assert len(scheduler.outcomes) == 10
        assert scheduler.outcomes[0] != first_outcome  # Oldest removed

    def test_window_order_preserved(self, scheduler):
        """Outcomes should be in the order they were added."""
        outcomes = [True, False, True, True, False]
        for o in outcomes:
            scheduler.record_outcome(o)
        assert list(scheduler.outcomes) == outcomes

class TestSuccessRateBelow30:
    """Test that success rate < 30% triggers reduction in mutation rate and increase in threshold."""

    def test_success_rate_below_30_triggers_adjustment(self, scheduler):
        """When success rate is below 30%, mutation rate should decrease and threshold increase."""
        initial_mutation = scheduler.mutation_rate
        initial_threshold = scheduler.threshold
        
        # Record 10 outcomes with only 2 successes (20% success rate)
        for i in range(10):
            scheduler.record_outcome(i < 2)  # First 2 are True, rest False
        
        # Trigger adjustment
        scheduler.adjust_parameters()
        
        assert scheduler.mutation_rate < initial_mutation
        assert scheduler.threshold > initial_threshold

    def test_success_rate_29_percent(self, scheduler):
        """Exactly 29% success rate (2/7) should trigger adjustment."""
        initial_mutation = scheduler.mutation_rate
        initial_threshold = scheduler.threshold
        
        # Record 7 outcomes with 2 successes (28.57% ≈ 29%)
        for i in range(7):
            scheduler.record_outcome(i < 2)
        
        scheduler.adjust_parameters()
        
        assert scheduler.mutation_rate < initial_mutation
        assert scheduler.threshold > initial_threshold

    def test_success_rate_30_percent_no_adjustment(self, scheduler):
        """Exactly 30% success rate should NOT trigger adjustment (boundary)."""
        initial_mutation = scheduler.mutation_rate
        initial_threshold = scheduler.threshold
        
        # Record 10 outcomes with 3 successes (30%)
        for i in range(10):
            scheduler.record_outcome(i < 3)
        
        scheduler.adjust_parameters()
        
        assert scheduler.mutation_rate == initial_mutation
        assert scheduler.threshold == initial_threshold

    def test_success_rate_0_percent(self, scheduler):
        """0% success rate should trigger maximum adjustment."""
        initial_mutation = scheduler.mutation_rate
        initial_threshold = scheduler.threshold
        
        for i in range(10):
            scheduler.record_outcome(False)
        
        scheduler.adjust_parameters()
        
        assert scheduler.mutation_rate < initial_mutation
        assert scheduler.threshold > initial_threshold

class TestSuccessRateAbove70:
    """Test that success rate > 70% triggers increase in mutation rate and decrease in threshold."""

    def test_success_rate_above_70_triggers_adjustment(self, scheduler):
        """When success rate is above 70%, mutation rate should increase and threshold decrease."""
        initial_mutation = scheduler.mutation_rate
        initial_threshold = scheduler.threshold
        
        # Record 10 outcomes with 8 successes (80% success rate)
        for i in range(10):
            scheduler.record_outcome(i < 8)  # First 8 are True
        
        scheduler.adjust_parameters()
        
        assert scheduler.mutation_rate > initial_mutation
        assert scheduler.threshold < initial_threshold

    def test_success_rate_71_percent(self, scheduler):
        """Exactly 71% success rate (5/7) should trigger adjustment."""
        initial_mutation = scheduler.mutation_rate
        initial_threshold = scheduler.threshold
        
        # Record 7 outcomes with 5 successes (71.43% ≈ 71%)
        for i in range(7):
            scheduler.record_outcome(i < 5)
        
        scheduler.adjust_parameters()
        
        assert scheduler.mutation_rate > initial_mutation
        assert scheduler.threshold < initial_threshold

    def test_success_rate_70_percent_no_adjustment(self, scheduler):
        """Exactly 70% success rate should NOT trigger adjustment (boundary)."""
        initial_mutation = scheduler.mutation_rate
        initial_threshold = scheduler.threshold
        
        # Record 10 outcomes with 7 successes (70%)
        for i in range(10):
            scheduler.record_outcome(i < 7)
        
        scheduler.adjust_parameters()
        
        assert scheduler.mutation_rate == initial_mutation
        assert scheduler.threshold == initial_threshold

    def test_success_rate_100_percent(self, scheduler):
        """100% success rate should trigger maximum adjustment."""
        initial_mutation = scheduler.mutation_rate
        initial_threshold = scheduler.threshold
        
        for i in range(10):
            scheduler.record_outcome(True)
        
        scheduler.adjust_parameters()
        
        assert scheduler.mutation_rate > initial_mutation
        assert scheduler.threshold < initial_threshold

class TestPersistence:
    """Test that persistence file is created and contains correct data."""

    def test_persistence_file_created(self, scheduler_with_persistence):
        """Persistence file should be created after saving."""
        scheduler_with_persistence.save_state()
        assert os.path.exists(scheduler_with_persistence.persistence_file)

    def test_persistence_file_contains_correct_data(self, scheduler_with_persistence):
        """Persistence file should contain correct state data."""
        # Add some outcomes and parameters
        for i in range(5):
            scheduler_with_persistence.record_outcome(True)
        scheduler_with_persistence.mutation_rate = 0.2
        scheduler_with_persistence.threshold = 0.6
        
        scheduler_with_persistence.save_state()
        
        with open(scheduler_with_persistence.persistence_file, 'r') as f:
            data = json.load(f)
        
        assert data['mutation_rate'] == 0.2
        assert data['threshold'] == 0.6
        assert len(data['outcomes']) == 5
        assert all(data['outcomes'])

    def test_persistence_file_loaded_correctly(self, scheduler_with_persistence):
        """State should be correctly loaded from persistence file."""
        # Save state
        for i in range(3):
            scheduler_with_persistence.record_outcome(False)
        scheduler_with_persistence.mutation_rate = 0.05
        scheduler_with_persistence.threshold = 0.8
        scheduler_with_persistence.save_state()
        
        # Create new scheduler that loads from same file
        new_scheduler = MetaParameterScheduler(
            window_size=10,
            mutation_rate=0.1,
            threshold=0.5,
            persistence_file=scheduler_with_persistence.persistence_file
        )
        
        assert new_scheduler.mutation_rate == 0.05
        assert new_scheduler.threshold == 0.8
        assert len(new_scheduler.outcomes) == 3
        assert not any(new_scheduler.outcomes)

    def test_persistence_no_file(self, scheduler):
        """Scheduler without persistence file should not create file."""
        scheduler.save_state()
        # No file should be created; just ensure no error

class TestHistoryAccumulation:
    """Test that history is properly accumulated over multiple cycles."""

    def test_history_starts_empty(self, scheduler):
        """History should start empty."""
        assert len(scheduler.history) == 0

    def test_history_records_parameters(self, scheduler):
        """History should record parameters after each adjustment."""
        for i in range(5):
            scheduler.record_outcome(i < 2)  # 40% success rate (below 70%, above 30%)
        scheduler.adjust_parameters()
        assert len(scheduler.history) == 1
        assert 'mutation_rate' in scheduler.history[0]
        assert 'threshold' in scheduler.history[0]
        assert 'success_rate' in scheduler.history[0]

    def test_history_accumulates_over_multiple_cycles(self, scheduler):
        """History should accumulate over multiple adjustment cycles."""
        # Cycle 1: low success rate
        for i in range(10):
            scheduler.record_outcome(i < 2)  # 20% success
        scheduler.adjust_parameters()
        
        # Cycle 2: high success rate
        for i in range(10):
            scheduler.record_outcome(i < 8)  # 80% success
        scheduler.adjust_parameters()
        
        assert len(scheduler.history) == 2

    def test_history_contains_parameter_changes(self, scheduler):
        """History should show changes in parameters over time."""
        initial_mutation = scheduler.mutation_rate
        initial_threshold = scheduler.threshold
        
        # Low success rate cycle
        for i in range(10):
            scheduler.record_outcome(i < 2)
        scheduler.adjust_parameters()
        
        first_entry = scheduler.history[0]
        assert first_entry['mutation_rate'] < initial_mutation
        assert first_entry['threshold'] > initial_threshold
        
        # High success rate cycle
        for i in range(10):
            scheduler.record_outcome(i < 8)
        scheduler.adjust_parameters()
        
        second_entry = scheduler.history[1]
        assert second_entry['mutation_rate'] > first_entry['mutation_rate']
        assert second_entry['threshold'] < first_entry['threshold']

    def test_history_tracks_success_rate(self, scheduler):
        """History should track the success rate at each adjustment."""
        # 20% success rate
        for i in range(10):
            scheduler.record_outcome(i < 2)
        scheduler.adjust_parameters()
        assert scheduler.history[0]['success_rate'] == 0.2
        
        # 80% success rate
        for i in range(10):
            scheduler.record_outcome(i < 8)
        scheduler.adjust_parameters()
        assert scheduler.history[1]['success_rate'] == 0.8

class TestEdgeCases:
    """Test edge cases: exactly 30% and 70% boundaries."""

    def test_exactly_30_percent_no_adjustment(self, scheduler):
        """Exactly 30% success rate should not trigger adjustment."""
        initial_mutation = scheduler.mutation_rate
        initial_threshold = scheduler.threshold
        
        # 3 out of 10 = 30%
        for i in range(10):
            scheduler.record_outcome(i < 3)
        
        scheduler.adjust_parameters()
        
        assert scheduler.mutation_rate == initial_mutation
        assert scheduler.threshold == initial_threshold

    def test_exactly_70_percent_no_adjustment(self, scheduler):
        """Exactly 70% success rate should not trigger adjustment."""
        initial_mutation = scheduler.mutation_rate
        initial_threshold = scheduler.threshold
        
        # 7 out of 10 = 70%
        for i in range(10):
            scheduler.record_outcome(i < 7)
        
        scheduler.adjust_parameters()
        
        assert scheduler.mutation_rate == initial_mutation
        assert scheduler.threshold == initial_threshold

    def test_just_below_30_triggers_adjustment(self, scheduler):
        """Just below 30% (e.g., 29%) should trigger adjustment."""
        initial_mutation = scheduler.mutation_rate
        initial_threshold = scheduler.threshold
        
        # 2 out of 7 ≈ 28.57% (just below 30%)
        for i in range(7):
            scheduler.record_outcome(i < 2)
        
        scheduler.adjust_parameters()
        
        assert scheduler.mutation_rate < initial_mutation
        assert scheduler.threshold > initial_threshold

    def test_just_above_70_triggers_adjustment(self, scheduler):
        """Just above 70% (e.g., 71%) should trigger adjustment."""
        initial_mutation = scheduler.mutation_rate
        initial_threshold = scheduler.threshold
        
        # 5 out of 7 ≈ 71.43% (just above 70%)
        for i in range(7):
            scheduler.record_outcome(i < 5)
        
        scheduler.adjust_parameters()
        
        assert scheduler.mutation_rate > initial_mutation
        assert scheduler.threshold < initial_threshold

    def test_empty_window_no_adjustment(self, scheduler):
        """Empty window should not cause adjustment."""
        initial_mutation = scheduler.mutation_rate
        initial_threshold = scheduler.threshold
        
        scheduler.adjust_parameters()
        
        assert scheduler.mutation_rate == initial_mutation
        assert scheduler.threshold == initial_threshold

    def test_single_outcome_no_adjustment(self, scheduler):
        """Single outcome should not trigger adjustment (insufficient data)."""
        initial_mutation = scheduler.mutation_rate
        initial_threshold = scheduler.threshold
        
        scheduler.record_outcome(True)
        scheduler.adjust_parameters()
        
        assert scheduler.mutation_rate == initial_mutation
        assert scheduler.threshold == initial_threshold

if __name__ == '__main__':
    pytest.main([__file__])