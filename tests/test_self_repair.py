import pytest
from unittest.mock import patch, MagicMock, call
import ast
import sys
from typing import List, Dict, Any, Optional

# Import the module under test
from src.self_repair import (
    SelfRepairEngine,
    FailureClassifier,
    StrategySelector,
    ASTStrategy,
    WrapperStrategy,
    RepairStrategy,
    MutationResult,
    RepairOutcome,
    ErrorCategory,
)


# -----------------------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------------------

@pytest.fixture
def engine() -> SelfRepairEngine:
    """Create a SelfRepairEngine instance with default configuration."""
    return SelfRepairEngine(max_ast_retries=3)


@pytest.fixture
def classifier() -> FailureClassifier:
    """Create a FailureClassifier instance."""
    return FailureClassifier()


@pytest.fixture
def strategy_selector() -> StrategySelector:
    """Create a StrategySelector instance."""
    return StrategySelector()


@pytest.fixture
def sample_ast() -> ast.Module:
    """Return a simple valid AST for testing."""
    return ast.parse("x = 42")


@pytest.fixture
def invalid_ast_source() -> str:
    """Return a source string that will produce an invalid AST."""
    return "x = "  # incomplete assignment


# -----------------------------------------------------------------------------
# Test 1: 3 consecutive AST failures trigger switch to wrapper strategy
# -----------------------------------------------------------------------------

def test_three_ast_failures_trigger_wrapper_strategy(engine: SelfRepairEngine, sample_ast: ast.Module):
    """
    Given an engine that experiences 3 consecutive AST failures,
    the engine should switch from ASTStrategy to WrapperStrategy.
    """
    # Arrange
    # Simulate ASTStrategy always failing
    failing_ast_strategy = MagicMock(spec=ASTStrategy)
    failing_ast_strategy.execute.return_value = MutationResult(
        success=False,
        error="AST parsing error",
        error_category=ErrorCategory.AST_FAILURE,
    )
    engine.ast_strategy = failing_ast_strategy

    wrapper_strategy = MagicMock(spec=WrapperStrategy)
    wrapper_strategy.execute.return_value = MutationResult(
        success=True,
        mutated_code="x = 42",
        error=None,
        error_category=None,
    )
    engine.wrapper_strategy = wrapper_strategy

    # Act
    for i in range(3):
        result = engine.repair(sample_ast)
        # The first two should still use AST strategy (or fallback to wrapper after 3)
        # We'll check after the third call

    # After 3 failures, the engine should have switched to wrapper strategy
    # The fourth call should use wrapper strategy
    result = engine.repair(sample_ast)

    # Assert
    assert result.success is True
    assert result.mutated_code == "x = 42"
    # Verify that wrapper strategy was called at least once after the switch
    wrapper_strategy.execute.assert_called()
    # Verify that the engine's current strategy is now WrapperStrategy
    assert isinstance(engine.current_strategy, WrapperStrategy) or engine.current_strategy is wrapper_strategy


def test_ast_failure_counter_resets_on_success(engine: SelfRepairEngine, sample_ast: ast.Module):
    """
    If an AST failure occurs but then a success, the counter should reset.
    """
    # Arrange
    ast_strategy = MagicMock(spec=ASTStrategy)
    # First call fails, second call succeeds
    ast_strategy.execute.side_effect = [
        MutationResult(success=False, error="fail", error_category=ErrorCategory.AST_FAILURE),
        MutationResult(success=True, mutated_code="x = 42", error=None, error_category=None),
    ]
    engine.ast_strategy = ast_strategy

    wrapper_strategy = MagicMock(spec=WrapperStrategy)
    engine.wrapper_strategy = wrapper_strategy

    # Act
    result1 = engine.repair(sample_ast)  # fails
    result2 = engine.repair(sample_ast)  # succeeds

    # Assert
    assert result1.success is False
    assert result2.success is True
    # The counter should have reset after success, so no switch to wrapper
    wrapper_strategy.execute.assert_not_called()


# -----------------------------------------------------------------------------
# Test 2: Wrapper strategy produces valid mutations
# -----------------------------------------------------------------------------

def test_wrapper_strategy_produces_valid_mutations(engine: SelfRepairEngine):
    """
    The wrapper strategy should produce syntactically valid Python code.
    """
    # Arrange
    wrapper = WrapperStrategy()
    # Use a simple source that might be problematic
    source = "def foo():\n    pass"

    # Act
    result = wrapper.execute(source)

    # Assert
    assert result.success is True
    # The mutated code should be valid Python
    try:
        ast.parse(result.mutated_code)
    except SyntaxError:
        pytest.fail(f"Wrapper strategy produced invalid Python: {result.mutated_code}")


def test_wrapper_strategy_handles_edge_cases(engine: SelfRepairEngine):
    """
    Wrapper strategy should handle edge cases like empty code or comments.
    """
    # Arrange
    wrapper = WrapperStrategy()
    edge_cases = [
        "",
        "# just a comment",
        "'''docstring'''",
        "x = 1; y = 2",
        "if True:\n    pass",
    ]

    for source in edge_cases:
        # Act
        result = wrapper.execute(source)

        # Assert
        assert result.success is True, f"Wrapper failed on: {source!r}"
        # Should always produce valid Python
        try:
            ast.parse(result.mutated_code)
        except SyntaxError as e:
            pytest.fail(f"Wrapper produced invalid Python for {source!r}: {e}")


# -----------------------------------------------------------------------------
# Test 3: Failure classifier correctly categorizes different error types
# -----------------------------------------------------------------------------

def test_failure_classifier_categorizes_ast_errors(classifier: FailureClassifier):
    """AST-related errors should be classified as AST_FAILURE."""
    # Arrange
    errors = [
        "SyntaxError: invalid syntax",
        "IndentationError: unexpected indent",
        "TabError: inconsistent use of tabs and spaces",
        "ast.parse failed: unexpected token",
    ]

    for error in errors:
        # Act
        category = classifier.classify(error)

        # Assert
        assert category == ErrorCategory.AST_FAILURE, f"Expected AST_FAILURE for: {error}"


def test_failure_classifier_categorizes_runtime_errors(classifier: FailureClassifier):
    """Runtime errors should be classified as RUNTIME_ERROR."""
    # Arrange
    errors = [
        "ZeroDivisionError: division by zero",
        "NameError: name 'x' is not defined",
        "TypeError: unsupported operand type(s)",
        "ValueError: invalid literal for int()",
    ]

    for error in errors:
        # Act
        category = classifier.classify(error)

        # Assert
        assert category == ErrorCategory.RUNTIME_ERROR, f"Expected RUNTIME_ERROR for: {error}"


def test_failure_classifier_categorizes_unknown_errors(classifier: FailureClassifier):
    """Unknown or generic errors should be classified as UNKNOWN."""
    # Arrange
    errors = [
        "Some random error message",
        "OSError: file not found",
        "KeyboardInterrupt",
        "",
    ]

    for error in errors:
        # Act
        category = classifier.classify(error)

        # Assert
        assert category == ErrorCategory.UNKNOWN, f"Expected UNKNOWN for: {error}"


def test_failure_classifier_case_insensitive(classifier: FailureClassifier):
    """Classification should be case-insensitive."""
    # Arrange
    error = "syntaxerror: invalid syntax"

    # Act
    category = classifier.classify(error)

    # Assert
    assert category == ErrorCategory.AST_FAILURE


# -----------------------------------------------------------------------------
# Test 4: Strategy selector avoids repeating failed strategies on same target
# -----------------------------------------------------------------------------

def test_strategy_selector_avoids_repeating_failed_strategies(strategy_selector: StrategySelector):
    """
    The strategy selector should not select a strategy that has already failed
    on the same target.
    """
    # Arrange
    target_id = "target_123"
    strategy_a = MagicMock(spec=RepairStrategy)
    strategy_a.name = "StrategyA"
    strategy_b = MagicMock(spec=RepairStrategy)
    strategy_b.name = "StrategyB"
    strategy_c = MagicMock(spec=RepairStrategy)
    strategy_c.name = "StrategyC"

    strategies = [strategy_a, strategy_b, strategy_c]
    strategy_selector.register_strategies(strategies)

    # Act: Mark strategy_a as failed on target_123
    strategy_selector.record_failure(target_id, strategy_a)

    # Now select a strategy for target_123
    selected = strategy_selector.select_strategy(target_id)

    # Assert
    assert selected is not None
    assert selected.name != "StrategyA", "Should not select failed strategy"
    assert selected.name in ("StrategyB", "StrategyC")


def test_strategy_selector_allows_retry_after_reset(strategy_selector: StrategySelector):
    """
    After resetting failure records for a target, previously failed strategies
    should be selectable again.
    """
    # Arrange
    target_id = "target_456"
    strategy_a = MagicMock(spec=RepairStrategy)
    strategy_a.name = "StrategyA"
    strategy_b = MagicMock(spec=RepairStrategy)
    strategy_b.name = "StrategyB"

    strategy_selector.register_strategies([strategy_a, strategy_b])
    strategy_selector.record_failure(target_id, strategy_a)

    # Act: Reset failures for this target
    strategy_selector.reset_failures(target_id)

    # Now select a strategy
    selected = strategy_selector.select_strategy(target_id)

    # Assert
    assert selected is not None
    # Should be able to select strategy_a again
    assert selected.name == "StrategyA"


def test_strategy_selector_returns_none_when_all_strategies_failed(strategy_selector: StrategySelector):
    """
    If all strategies have failed on a target, the selector should return None.
    """
    # Arrange
    target_id = "target_789"
    strategy_a = MagicMock(spec=RepairStrategy)
    strategy_a.name = "StrategyA"
    strategy_b = MagicMock(spec=RepairStrategy)
    strategy_b.name = "StrategyB"

    strategy_selector.register_strategies([strategy_a, strategy_b])
    strategy_selector.record_failure(target_id, strategy_a)
    strategy_selector.record_failure(target_id, strategy_b)

    # Act
    selected = strategy_selector.select_strategy(target_id)

    # Assert
    assert selected is None, "Should return None when all strategies failed"


def test_strategy_selector_independence_between_targets(strategy_selector: StrategySelector):
    """
    Failure records for different targets should be independent.
    """
    # Arrange
    target_a = "target_A"
    target_b = "target_B"
    strategy = MagicMock(spec=RepairStrategy)
    strategy.name = "CommonStrategy"

    strategy_selector.register_strategies([strategy])

    # Act: Fail on target_a only
    strategy_selector.record_failure(target_a, strategy)

    # Assert: target_b should still be able to use the strategy
    selected_for_b = strategy_selector.select_strategy(target_b)
    assert selected_for_b is not None
    assert selected_for_b.name == "CommonStrategy"

    # target_a should have no available strategies
    selected_for_a = strategy_selector.select_strategy(target_a)
    assert selected_for_a is None


# -----------------------------------------------------------------------------
# Integration test: Full self-repair flow
# -----------------------------------------------------------------------------

def test_full_self_repair_flow_with_strategy_switch(engine: SelfRepairEngine, sample_ast: ast.Module):
    """
    Integration test: Simulate a scenario where AST strategy fails 3 times,
    then wrapper strategy succeeds.
    """
    # Arrange
    # Create a mock AST strategy that fails 3 times then succeeds
    ast_strategy = MagicMock(spec=ASTStrategy)
    ast_strategy.execute.side_effect = [
        MutationResult(success=False, error="AST error 1", error_category=ErrorCategory.AST_FAILURE),
        MutationResult(success=False, error="AST error 2", error_category=ErrorCategory.AST_FAILURE),
        MutationResult(success=False, error="AST error 3", error_category=ErrorCategory.AST_FAILURE),
    ]
    engine.ast_strategy = ast_strategy

    wrapper_strategy = MagicMock(spec=WrapperStrategy)
    wrapper_strategy.execute.return_value = MutationResult(
        success=True,
        mutated_code="x = 42",
        error=None,
        error_category=None,
    )
    engine.wrapper_strategy = wrapper_strategy

    # Act
    results = []
    for i in range(4):
        result = engine.repair(sample_ast)
        results.append(result)

    # Assert
    # First 3 should fail (AST strategy)
    for i in range(3):
        assert results[i].success is False, f"Result {i} should be failure"
    # Fourth should succeed (wrapper strategy)
    assert results[3].success is True
    assert results[3].mutated_code == "x = 42"

    # Verify that wrapper strategy was called
    wrapper_strategy.execute.assert_called_once()