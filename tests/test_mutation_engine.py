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


def test_mutation_prompt_includes_lessons_learned_when_failures_exist(caplog):
    """Test that the mutation prompt includes 'Lessons Learned' section when failures exist."""
    # Arrange: mock failure_pattern_learner to return failures
    with patch('mutation_engine.FailurePatternLearner') as MockLearner:
        mock_learner_instance = MockLearner.return_value
        mock_learner_instance.get_failures.return_value = [
            {"module": "module_a", "failure_type": "TypeError", "count": 3}
        ]
        mock_learner_instance.get_lessons_learned.return_value = [
            "Avoid using NoneType in arithmetic operations",
            "Always validate input types before processing"
        ]

        engine = MutationEngine(failure_learner=mock_learner_instance)

        # Act: generate mutation prompt
        prompt = engine.generate_mutation_prompt(module_name="module_a")

        # Assert: prompt contains 'Lessons Learned' section
        assert "Lessons Learned" in prompt, \
            "Expected 'Lessons Learned' section in mutation prompt when failures exist"
        assert "Avoid using NoneType in arithmetic operations" in prompt, \
            "Expected lesson content in mutation prompt"
        assert "Always validate input types before processing" in prompt, \
            "Expected all lessons to be included in mutation prompt"


def test_mutation_prompt_omits_lessons_learned_when_no_failures(caplog):
    """Test that the mutation prompt omits 'Lessons Learned' section when no failures are recorded."""
    # Arrange: mock failure_pattern_learner to return no failures
    with patch('mutation_engine.FailurePatternLearner') as MockLearner:
        mock_learner_instance = MockLearner.return_value
        mock_learner_instance.get_failures.return_value = []
        mock_learner_instance.get_lessons_learned.return_value = []

        engine = MutationEngine(failure_learner=mock_learner_instance)

        # Act: generate mutation prompt
        prompt = engine.generate_mutation_prompt(module_name="module_a")

        # Assert: prompt does not contain 'Lessons Learned' section
        assert "Lessons Learned" not in prompt, \
            "Expected no 'Lessons Learned' section in mutation prompt when no failures exist"
        assert "lessons" not in prompt.lower(), \
            "Expected no lesson-related content in mutation prompt when no failures exist"


def test_lessons_learned_ordered_by_recency_after_consecutive_failures(caplog):
    """Test that after 5 consecutive mutation failures, the generated prompt contains a 'Lessons Learned' section with at least 5 entries, ordered by recency."""
    # Arrange: mock failure_pattern_learner to simulate 5 consecutive failures
    with patch('mutation_engine.FailurePatternLearner') as MockLearner:
        mock_learner_instance = MockLearner.return_value
        # Simulate 5 consecutive failures with timestamps for recency ordering
        mock_learner_instance.get_failures.return_value = [
            {"module": "module_a", "failure_type": "TypeError", "count": 1, "timestamp": "2023-01-05T10:00:00"},
            {"module": "module_a", "failure_type": "ValueError", "count": 1, "timestamp": "2023-01-04T10:00:00"},
            {"module": "module_a", "failure_type": "KeyError", "count": 1, "timestamp": "2023-01-03T10:00:00"},
            {"module": "module_a", "failure_type": "AttributeError", "count": 1, "timestamp": "2023-01-02T10:00:00"},
            {"module": "module_a", "failure_type": "IndexError", "count": 1, "timestamp": "2023-01-01T10:00:00"}
        ]
        # Return 5 lessons learned, ordered by recency (most recent first)
        mock_learner_instance.get_lessons_learned.return_value = [
            "Lesson 5: Avoid TypeError by checking types before operations",
            "Lesson 4: Validate inputs to prevent ValueError",
            "Lesson 3: Ensure dictionary keys exist to avoid KeyError",
            "Lesson 2: Check object attributes before access to prevent AttributeError",
            "Lesson 1: Validate list indices to avoid IndexError"
        ]

        engine = MutationEngine(failure_learner=mock_learner_instance)

        # Act: generate mutation prompt
        prompt = engine.generate_mutation_prompt(module_name="module_a")

        # Assert: prompt contains 'Lessons Learned' section
        assert "Lessons Learned" in prompt, \
            "Expected 'Lessons Learned' section in mutation prompt after consecutive failures"

        # Assert: at least 5 entries in the Lessons Learned section
        # Count the number of lesson entries (lines starting with '-' or numbered)
        lesson_entries = [line for line in prompt.split('\n') if line.strip().startswith('-') or line.strip()[0].isdigit()]
        assert len(lesson_entries) >= 5, \
            f"Expected at least 5 lesson entries, but found {len(lesson_entries)}"

        # Assert: lessons are ordered by recency (most recent first)
        # The mock returns lessons in recency order, so we check the order in the prompt
        expected_order = [
            "Lesson 5: Avoid TypeError by checking types before operations",
            "Lesson 4: Validate inputs to prevent ValueError",
            "Lesson 3: Ensure dictionary keys exist to avoid KeyError",
            "Lesson 2: Check object attributes before access to prevent AttributeError",
            "Lesson 1: Validate list indices to avoid IndexError"
        ]
        # Find the position of each lesson in the prompt
        positions = []
        for lesson in expected_order:
            pos = prompt.find(lesson)
            assert pos != -1, f"Expected lesson '{lesson}' to be in the prompt"
            positions.append(pos)
        # Check that positions are in increasing order (most recent first)
        assert positions == sorted(positions), \
            f"Expected lessons ordered by recency (most recent first), but got positions: {positions}"