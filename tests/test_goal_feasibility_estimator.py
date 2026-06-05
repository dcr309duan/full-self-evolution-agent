"""Tests for the goal feasibility estimator module."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta

from src.goal_feasibility_estimator import GoalFeasibilityEstimator, FeasibilityResult
from src.goal_generator import GoalGenerator
from src.orchestrator import Orchestrator


@pytest.fixture
def estimator():
    """Create a GoalFeasibilityEstimator instance for testing."""
    return GoalFeasibilityEstimator()


@pytest.fixture
def mock_goal_generator():
    """Create a mock GoalGenerator."""
    generator = Mock(spec=GoalGenerator)
    generator.get_required_capabilities.return_value = {"nlp", "vision", "memory"}
    return generator


@pytest.fixture
def mock_orchestrator():
    """Create a mock Orchestrator."""
    orchestrator = Mock(spec=Orchestrator)
    orchestrator.get_available_capabilities.return_value = {"nlp", "vision", "memory", "planning"}
    return orchestrator


class TestGoalFeasibilityEstimator:
    """Test suite for GoalFeasibilityEstimator."""

    def test_missing_capabilities_identified(self, estimator, mock_goal_generator, mock_orchestrator):
        """Test that estimator correctly identifies missing capabilities."""
        mock_orchestrator.get_available_capabilities.return_value = {"nlp", "memory"}
        mock_goal_generator.get_required_capabilities.return_value = {"nlp", "vision", "memory"}
        
        result = estimator.estimate_feasibility("test_goal", mock_goal_generator, mock_orchestrator)
        
        assert not result.is_feasible
        assert "vision" in result.missing_capabilities
        assert result.block_reason is not None
        assert "missing" in result.block_reason.lower()

    def test_low_success_rate_triggers_block(self, estimator, mock_goal_generator, mock_orchestrator):
        """Test that low historical success rate (<20%) triggers block."""
        mock_orchestrator.get_historical_success_rate.return_value = 0.15  # 15%
        mock_orchestrator.get_available_capabilities.return_value = {"nlp", "vision", "memory"}
        
        result = estimator.estimate_feasibility("test_goal", mock_goal_generator, mock_orchestrator)
        
        assert not result.is_feasible
        assert result.success_rate == 0.15
        assert result.block_reason is not None
        assert "success rate" in result.block_reason.lower()

    def test_partial_capability_overlap_triggers_complexity_adjustment(self, estimator, mock_goal_generator, mock_orchestrator):
        """Test that partial capability overlap triggers complexity adjustment."""
        mock_orchestrator.get_available_capabilities.return_value = {"nlp", "memory", "planning"}
        mock_goal_generator.get_required_capabilities.return_value = {"nlp", "vision", "memory", "reasoning"}
        mock_goal_generator.get_goal_complexity.return_value = 0.5
        
        result = estimator.estimate_feasibility("test_goal", mock_goal_generator, mock_orchestrator)
        
        assert result.complexity_adjustment is not None
        assert result.complexity_adjustment > 0.5  # Complexity should increase
        assert result.is_feasible  # Still feasible but with adjustment

    def test_high_success_rate_with_full_capabilities_allows_proceed(self, estimator, mock_goal_generator, mock_orchestrator):
        """Test that high success rate with full capabilities allows proceed."""
        mock_orchestrator.get_historical_success_rate.return_value = 0.85  # 85%
        mock_orchestrator.get_available_capabilities.return_value = {"nlp", "vision", "memory", "planning"}
        
        result = estimator.estimate_feasibility("test_goal", mock_goal_generator, mock_orchestrator)
        
        assert result.is_feasible
        assert result.block_reason is None
        assert result.confidence_score >= 0.8

    def test_empty_history_handling(self, estimator, mock_goal_generator, mock_orchestrator):
        """Test edge case: empty history."""
        mock_orchestrator.get_historical_success_rate.return_value = None
        mock_orchestrator.get_available_capabilities.return_value = {"nlp", "vision", "memory"}
        
        result = estimator.estimate_feasibility("test_goal", mock_goal_generator, mock_orchestrator)
        
        # Should still work with default assumptions
        assert result.is_feasible
        assert result.success_rate is None or result.success_rate == 0.5  # Default assumption

    def test_unknown_goal_type(self, estimator, mock_goal_generator, mock_orchestrator):
        """Test edge case: unknown goal type."""
        mock_goal_generator.get_required_capabilities.side_effect = ValueError("Unknown goal type")
        
        result = estimator.estimate_feasibility("unknown_goal", mock_goal_generator, mock_orchestrator)
        
        assert not result.is_feasible
        assert result.block_reason is not None
        assert "unknown" in result.block_reason.lower()

    def test_integration_with_goal_generator(self, estimator, mock_goal_generator, mock_orchestrator):
        """Test integration with goal generator."""
        mock_goal_generator.get_required_capabilities.return_value = {"nlp", "vision"}
        mock_goal_generator.get_goal_complexity.return_value = 0.3
        
        result = estimator.estimate_feasibility("simple_goal", mock_goal_generator, mock_orchestrator)
        
        assert result.is_feasible
        mock_goal_generator.get_required_capabilities.assert_called_once_with("simple_goal")
        mock_goal_generator.get_goal_complexity.assert_called_once_with("simple_goal")

    def test_integration_with_orchestrator(self, estimator, mock_goal_generator, mock_orchestrator):
        """Test integration with orchestrator."""
        mock_orchestrator.get_available_capabilities.return_value = {"nlp", "vision", "memory", "planning"}
        mock_orchestrator.get_historical_success_rate.return_value = 0.75
        
        result = estimator.estimate_feasibility("test_goal", mock_goal_generator, mock_orchestrator)
        
        assert result.is_feasible
        mock_orchestrator.get_available_capabilities.assert_called_once()
        mock_orchestrator.get_historical_success_rate.assert_called_once_with("test_goal")

    def test_full_integration_flow(self):
        """Test complete integration with goal generator and orchestrator."""
        # Create real instances (or more complex mocks)
        estimator = GoalFeasibilityEstimator()
        goal_generator = Mock(spec=GoalGenerator)
        orchestrator = Mock(spec=Orchestrator)
        
        # Setup complex scenario
        orchestrator.get_available_capabilities.return_value = {"nlp", "memory"}
        orchestrator.get_historical_success_rate.return_value = 0.1  # Low success rate
        goal_generator.get_required_capabilities.return_value = {"nlp", "vision", "memory", "planning"}
        goal_generator.get_goal_complexity.return_value = 0.8
        
        result = estimator.estimate_feasibility("complex_goal", goal_generator, orchestrator)
        
        # Should be blocked due to multiple issues
        assert not result.is_feasible
        assert len(result.missing_capabilities) > 0
        assert result.success_rate < 0.2
        assert result.complexity_adjustment is not None

    def test_estimator_initialization(self):
        """Test that estimator initializes with default parameters."""
        estimator = GoalFeasibilityEstimator()
        assert estimator.min_success_rate == 0.2
        assert estimator.max_missing_capabilities is not None

    def test_custom_parameters(self):
        """Test estimator with custom parameters."""
        estimator = GoalFeasibilityEstimator(min_success_rate=0.3, max_missing_capabilities=1)
        assert estimator.min_success_rate == 0.3
        assert estimator.max_missing_capabilities == 1

    def test_confidence_score_calculation(self, estimator, mock_goal_generator, mock_orchestrator):
        """Test confidence score calculation logic."""
        mock_orchestrator.get_historical_success_rate.return_value = 0.9
        mock_orchestrator.get_available_capabilities.return_value = {"nlp", "vision", "memory", "planning"}
        
        result = estimator.estimate_feasibility("test_goal", mock_goal_generator, mock_orchestrator)
        
        assert 0 <= result.confidence_score <= 1.0
        assert result.confidence_score > 0.5  # Should be high confidence

    def test_estimator_returns_feasibility_result(self, estimator, mock_goal_generator, mock_orchestrator):
        """Test that estimator returns proper FeasibilityResult object."""
        result = estimator.estimate_feasibility("test_goal", mock_goal_generator, mock_orchestrator)
        
        assert isinstance(result, FeasibilityResult)
        assert hasattr(result, 'is_feasible')
        assert hasattr(result, 'missing_capabilities')
        assert hasattr(result, 'success_rate')
        assert hasattr(result, 'confidence_score')
        assert hasattr(result, 'complexity_adjustment')
        assert hasattr(result, 'block_reason')

    def test_estimator_handles_none_capabilities(self, estimator, mock_goal_generator, mock_orchestrator):
        """Test estimator handles None capabilities gracefully."""
        mock_orchestrator.get_available_capabilities.return_value = None
        mock_goal_generator.get_required_capabilities.return_value = {"nlp", "vision"}
        
        result = estimator.estimate_feasibility("test_goal", mock_goal_generator, mock_orchestrator)
        
        assert not result.is_feasible
        assert result.block_reason is not None

    def test_estimator_handles_empty_capabilities(self, estimator, mock_goal_generator, mock_orchestrator):
        """Test estimator handles empty capabilities set."""
        mock_orchestrator.get_available_capabilities.return_value = set()
        mock_goal_generator.get_required_capabilities.return_value = {"nlp", "vision"}
        
        result = estimator.estimate_feasibility("test_goal", mock_goal_generator, mock_orchestrator)
        
        assert not result.is_feasible
        assert len(result.missing_capabilities) == 2

    def test_estimator_handles_exceptions_gracefully(self, estimator, mock_goal_generator, mock_orchestrator):
        """Test estimator handles exceptions from dependencies gracefully."""
        mock_orchestrator.get_available_capabilities.side_effect = Exception("Connection error")
        
        result = estimator.estimate_feasibility("test_goal", mock_goal_generator, mock_orchestrator)
        
        assert not result.is_feasible
        assert "error" in result.block_reason.lower()