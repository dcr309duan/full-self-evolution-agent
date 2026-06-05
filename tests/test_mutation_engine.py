import pytest
from unittest.mock import Mock, patch, PropertyMock
import logging

# Assuming the module structure:
# - mutation_engine.py contains MutationEngine class
# - failure_pattern_learner.py contains FailurePatternLearner class

from mutation_engine import MutationEngine
from failure_pattern_learner import FailurePatternLearner


@pytest.fixture
def mock_failure_learner():
    """Fixture to mock FailurePatternLearner with controllable failure data."""
    learner = Mock(spec=FailurePatternLearner)
    # Default: no failures
    learner.get_failures.return_value = []
    return learner


@pytest.fixture
def mutation_engine(mock_failure_learner):
    """Fixture to create MutationEngine with mocked failure learner."""
    engine = MutationEngine(failure_learner=mock_failure_learner)
    return engine


def test_failure_penalty_applied_and_rationale_logged(caplog):
    """Test that module with failures gets reduced selection probability and rationale is logged."""
    # Arrange: mock failure_pattern_learner to return failures for a specific module
    with patch('mutation_engine.FailurePatternLearner') as MockLearner:
        mock_learner_instance = MockLearner.return_value
        mock_learner_instance.get_failures.return_value = [
            {"module": "module_a", "failure_type": "TypeError", "count": 3},
            {"module": "module_b", "failure_type": "ValueError", "count": 1}
        ]

        engine = MutationEngine(failure_learner=mock_learner_instance)

        # Act: get selection probabilities
        with caplog.at_level(logging.INFO):
            probabilities = engine.get_selection_probabilities()

        # Assert: module_a should have reduced probability
        # Assuming initial uniform distribution: each module has 0.5 probability
        # After penalty, module_a should be less than module_b
        assert probabilities["module_a"] < probabilities["module_b"], \
            f"Expected module_a probability ({probabilities['module_a']}) to be less than module_b ({probabilities['module_b']})"

        # Assert: rationale is logged
        assert any("module_a" in record.message and "penalty" in record.message.lower()
                   for record in caplog.records), \
            "Expected a log message about module_a penalty"


def test_no_failures_no_penalty(caplog):
    """Test that when no failures exist, no penalty is applied and no rationale is logged."""
    # Arrange: mock failure_pattern_learner to return empty failures
    with patch('mutation_engine.FailurePatternLearner') as MockLearner:
        mock_learner_instance = MockLearner.return_value
        mock_learner_instance.get_failures.return_value = []

        engine = MutationEngine(failure_learner=mock_learner_instance)

        # Act: get selection probabilities
        with caplog.at_level(logging.INFO):
            probabilities = engine.get_selection_probabilities()

        # Assert: probabilities remain uniform (no penalty)
        # Assuming two modules: module_a and module_b
        assert probabilities["module_a"] == pytest.approx(0.5, rel=1e-2), \
            f"Expected module_a probability ~0.5, got {probabilities['module_a']}"
        assert probabilities["module_b"] == pytest.approx(0.5, rel=1e-2), \
            f"Expected module_b probability ~0.5, got {probabilities['module_b']}"

        # Assert: no penalty rationale logged
        penalty_logs = [record for record in caplog.records
                        if "penalty" in record.message.lower()]
        assert len(penalty_logs) == 0, \
            f"Expected no penalty logs, but found: {penalty_logs}"


def test_failure_penalty_multiple_modules(caplog):
    """Test that multiple modules with failures get appropriate penalties."""
    # Arrange: mock failure_pattern_learner with failures for multiple modules
    with patch('mutation_engine.FailurePatternLearner') as MockLearner:
        mock_learner_instance = MockLearner.return_value
        mock_learner_instance.get_failures.return_value = [
            {"module": "module_a", "failure_type": "TypeError", "count": 5},
            {"module": "module_b", "failure_type": "ValueError", "count": 2},
            {"module": "module_c", "failure_type": "KeyError", "count": 1}
        ]

        engine = MutationEngine(failure_learner=mock_learner_instance)

        # Act: get selection probabilities
        with caplog.at_level(logging.INFO):
            probabilities = engine.get_selection_probabilities()

        # Assert: probabilities decrease with failure count
        # module_a has most failures -> lowest probability
        # module_c has fewest failures -> highest probability
        assert probabilities["module_a"] < probabilities["module_b"] < probabilities["module_c"], \
            f"Expected module_a < module_b < module_c, got {probabilities}"

        # Assert: rationale logged for each penalized module
        for module in ["module_a", "module_b", "module_c"]:
            assert any(module in record.message and "penalty" in record.message.lower()
                       for record in caplog.records), \
                f"Expected a log message about {module} penalty"