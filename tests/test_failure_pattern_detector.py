import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
from src.failure_pattern_detector import FailurePatternDetector
from src.goal import Goal, GoalPriority
from src.orchestrator import Orchestrator

class TestFailurePatternDetector:
    """Comprehensive test suite for FailurePatternDetector."""

    @pytest.fixture
    def detector(self):
        """Create a fresh FailurePatternDetector instance for each test."""
        return FailurePatternDetector()

    @pytest.fixture
    def sample_failure(self):
        """Create a sample failure event."""
        return {
            'type': 'AssertionError',
            'module': 'test_user_auth',
            'message': 'Expected True, got False',
            'timestamp': datetime.now()
        }

    def test_logging_failure_stores_correctly(self, detector, sample_failure):
        """Test that logging failures stores them with correct structure."""
        detector.log_failure(sample_failure)
        
        assert len(detector.failure_history) == 1
        stored = detector.failure_history[0]
        assert stored['type'] == 'AssertionError'
        assert stored['module'] == 'test_user_auth'
        assert stored['message'] == 'Expected True, got False'
        assert isinstance(stored['timestamp'], datetime)

    def test_two_consecutive_same_type_failures_no_goal(self, detector, sample_failure):
        """Test that 2 consecutive same-type failures don't trigger goal generation."""
        # Log two consecutive failures of the same type
        detector.log_failure(sample_failure)
        detector.log_failure(sample_failure)
        
        goals = detector.check_and_generate_goals()
        assert len(goals) == 0, "Should not generate goals for only 2 consecutive failures"

    def test_three_consecutive_same_type_failures_triggers_goal(self, detector, sample_failure):
        """Test that 3 consecutive same-type failures trigger goal generation."""
        # Log three consecutive failures of the same type
        detector.log_failure(sample_failure)
        detector.log_failure(sample_failure)
        detector.log_failure(sample_failure)
        
        goals = detector.check_and_generate_goals()
        assert len(goals) == 1, "Should generate exactly one goal for 3 consecutive failures"
        
        goal = goals[0]
        assert goal.priority == GoalPriority.HIGH
        assert 'AssertionError' in goal.description
        assert 'test_user_auth' in goal.description
        assert goal.action == 'debugging'

    def test_non_consecutive_failures_no_trigger(self, detector, sample_failure):
        """Test that non-consecutive failures don't trigger goal generation."""
        # Create a different failure type to interrupt the pattern
        other_failure = sample_failure.copy()
        other_failure['type'] = 'TimeoutError'
        
        # Log pattern: AssertionError, AssertionError, TimeoutError, AssertionError
        detector.log_failure(sample_failure)
        detector.log_failure(sample_failure)
        detector.log_failure(other_failure)
        detector.log_failure(sample_failure)
        
        goals = detector.check_and_generate_goals()
        assert len(goals) == 0, "Should not trigger for non-consecutive same-type failures"

    def test_generated_goal_has_correct_structure(self, detector, sample_failure):
        """Test that generated debugging goal has correct structure."""
        # Log three consecutive failures
        detector.log_failure(sample_failure)
        detector.log_failure(sample_failure)
        detector.log_failure(sample_failure)
        
        goals = detector.check_and_generate_goals()
        assert len(goals) == 1
        
        goal = goals[0]
        # Verify goal structure
        assert goal.priority == GoalPriority.HIGH
        assert goal.action == 'debugging'
        assert 'AssertionError' in goal.description
        assert 'test_user_auth' in goal.description
        assert hasattr(goal, 'id'), "Goal should have an id"
        assert hasattr(goal, 'created_at'), "Goal should have a created_at timestamp"

    def test_multiple_simultaneous_patterns_generate_multiple_goals(self, detector):
        """Test that multiple simultaneous patterns each generate their own goals."""
        # Create two different failure types
        failure_type_a = {
            'type': 'AssertionError',
            'module': 'test_user_auth',
            'message': 'Expected True, got False',
            'timestamp': datetime.now()
        }
        failure_type_b = {
            'type': 'TimeoutError',
            'module': 'test_api_integration',
            'message': 'Connection timed out',
            'timestamp': datetime.now()
        }
        
        # Log three consecutive failures for each type
        for _ in range(3):
            detector.log_failure(failure_type_a)
            detector.log_failure(failure_type_b)
        
        goals = detector.check_and_generate_goals()
        assert len(goals) == 2, "Should generate two goals for two simultaneous patterns"
        
        # Verify each goal corresponds to a different failure type
        goal_types = [g.description for g in goals]
        assert any('AssertionError' in desc for desc in goal_types)
        assert any('TimeoutError' in desc for desc in goal_types)

    def test_integration_with_orchestrator(self):
        """Test integration with orchestrator by mocking the test runner."""
        # Create mock orchestrator
        mock_orchestrator = MagicMock(spec=Orchestrator)
        mock_orchestrator.failure_pattern_detector = FailurePatternDetector()
        
        # Create controlled failure sequence
        failure_sequence = [
            {'type': 'AssertionError', 'module': 'test_user_auth', 'message': 'Failed 1'},
            {'type': 'AssertionError', 'module': 'test_user_auth', 'message': 'Failed 2'},
            {'type': 'AssertionError', 'module': 'test_user_auth', 'message': 'Failed 3'},
            {'type': 'TimeoutError', 'module': 'test_api', 'message': 'Timeout 1'},
            {'type': 'TimeoutError', 'module': 'test_api', 'message': 'Timeout 2'},
            {'type': 'TimeoutError', 'module': 'test_api', 'message': 'Timeout 3'},
        ]
        
        # Simulate test runner producing failures
        for failure in failure_sequence:
            mock_orchestrator.failure_pattern_detector.log_failure(failure)
        
        # Check for generated goals
        goals = mock_orchestrator.failure_pattern_detector.check_and_generate_goals()
        
        # Should have two goals (one for each pattern)
        assert len(goals) == 2
        
        # Verify goals are properly structured for orchestrator integration
        for goal in goals:
            assert goal.priority == GoalPriority.HIGH
            assert goal.action == 'debugging'
            assert hasattr(goal, 'id')
            assert hasattr(goal, 'created_at')

    def test_failure_history_clearing(self, detector, sample_failure):
        """Test that failure history can be cleared after goal generation."""
        # Log three consecutive failures
        for _ in range(3):
            detector.log_failure(sample_failure)
        
        # Generate goals
        goals = detector.check_and_generate_goals()
        assert len(goals) == 1
        
        # Clear history
        detector.clear_failure_history()
        assert len(detector.failure_history) == 0
        
        # Verify no more goals generated from old history
        goals_after_clear = detector.check_and_generate_goals()
        assert len(goals_after_clear) == 0

    def test_timestamp_ordering(self, detector):
        """Test that failures are stored in chronological order."""
        # Create failures with different timestamps
        past_failure = {
            'type': 'AssertionError',
            'module': 'test_module',
            'message': 'Old failure',
            'timestamp': datetime.now() - timedelta(hours=1)
        }
        recent_failure = {
            'type': 'AssertionError',
            'module': 'test_module',
            'message': 'Recent failure',
            'timestamp': datetime.now()
        }
        
        # Log out of order
        detector.log_failure(recent_failure)
        detector.log_failure(past_failure)
        
        # Verify chronological ordering
        assert detector.failure_history[0]['timestamp'] <= detector.failure_history[1]['timestamp']