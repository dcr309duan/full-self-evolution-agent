import pytest
from unittest.mock import Mock, patch, call
from pre_mutation_hook import PreMutationHook
import logging

@pytest.fixture
def hook():
    return PreMutationHook()

@pytest.fixture
def mock_logger():
    with patch('pre_mutation_hook.logger') as mock:
        yield mock

def test_mutation_breaking_integration_is_blocked(hook, mock_logger):
    """
    Simulates a mutation that would break the integration test.
    Verifies the hook blocks it and triggers rollback.
    """
    # Arrange
    mutation_code = "def vulnerable_function(): return 1/0"
    test_results = Mock()
    test_results.failed = True
    test_results.failures = [("test_integration", "ZeroDivisionError: division by zero")]
    
    # Act
    result = hook.check_mutation(mutation_code, test_results)
    
    # Assert
    assert result is False, "Mutation should be blocked"
    assert hook.rollback_triggered is True, "Rollback should be triggered"
    mock_logger.error.assert_called_once_with(
        "Mutation blocked: integration test failed with ZeroDivisionError"
    )

def test_failure_pattern_is_logged(hook, mock_logger):
    """
    Verifies that the failure pattern is properly logged when a mutation
    causes integration test failure.
    """
    # Arrange
    mutation_code = "def process_data(data): return data['missing_key']"
    test_results = Mock()
    test_results.failed = True
    test_results.failures = [
        ("test_integration", "KeyError: 'missing_key'"),
        ("test_unit", "AssertionError: Expected 5 but got None")
    ]
    
    # Act
    result = hook.check_mutation(mutation_code, test_results)
    
    # Assert
    assert result is False
    mock_logger.error.assert_called_once()
    log_message = mock_logger.error.call_args[0][0]
    assert "KeyError" in log_message, "Failure pattern should include KeyError"
    assert "test_integration" in log_message, "Failure pattern should include test name"
    assert hook.failure_patterns == ["KeyError: 'missing_key'"], "Failure patterns should be stored"

def test_happy_path_mutation_proceeds(hook, mock_logger):
    """
    Tests the happy path where all tests pass and mutation proceeds.
    """
    # Arrange
    mutation_code = "def add(a, b): return a + b"
    test_results = Mock()
    test_results.failed = False
    test_results.failures = []
    test_results.passed = True
    
    # Act
    result = hook.check_mutation(mutation_code, test_results)
    
    # Assert
    assert result is True, "Mutation should proceed when tests pass"
    assert hook.rollback_triggered is False, "Rollback should not be triggered"
    mock_logger.info.assert_called_once_with(
        "Mutation passed all tests, proceeding with mutation"
    )

def test_rollback_mechanism_with_multiple_failures(hook, mock_logger):
    """
    Tests that rollback is triggered and properly handles multiple failure patterns.
    """
    # Arrange
    mutation_code = "def complex_operation(): return [1,2,3][10]"
    test_results = Mock()
    test_results.failed = True
    test_results.failures = [
        ("test_integration_1", "IndexError: list index out of range"),
        ("test_integration_2", "AssertionError: Expected valid index")
    ]
    
    # Act
    result = hook.check_mutation(mutation_code, test_results)
    
    # Assert
    assert result is False
    assert hook.rollback_triggered is True
    assert len(hook.failure_patterns) == 2, "Should capture all failure patterns"
    mock_logger.error.assert_called_once_with(
        "Mutation blocked: integration test failed with IndexError, AssertionError"
    )

def test_hook_returns_to_original_state_after_rollback(hook, mock_logger):
    """
    Tests that after a rollback, the system returns to its original state.
    """
    # Arrange
    original_code = "def original_function(): return 'original'"
    mutation_code = "def original_function(): return 'mutated'"
    
    # Simulate first mutation attempt that fails
    test_results_fail = Mock()
    test_results_fail.failed = True
    test_results_fail.failures = [("test_integration", "AssertionError: Expected 'original'")]
    
    # Act - First attempt fails
    result_fail = hook.check_mutation(mutation_code, test_results_fail)
    
    # Simulate rollback restoring original code
    hook.rollback(original_code)
    
    # Simulate second attempt with original code that passes
    test_results_pass = Mock()
    test_results_pass.failed = False
    test_results_pass.failures = []
    result_pass = hook.check_mutation(original_code, test_results_pass)
    
    # Assert
    assert result_fail is False, "First mutation should be blocked"
    assert result_pass is True, "Original code should pass after rollback"
    assert hook.rollback_triggered is False, "Rollback flag should be reset"
    mock_logger.info.assert_any_call("Rollback completed: restored to original state")

def test_hook_handles_empty_test_results(hook, mock_logger):
    """
    Tests that the hook properly handles empty test results (edge case).
    """
    # Arrange
    mutation_code = "def new_function(): pass"
    test_results = Mock()
    test_results.failed = False
    test_results.failures = []
    test_results.passed = True
    
    # Act
    result = hook.check_mutation(mutation_code, test_results)
    
    # Assert
    assert result is True, "Mutation should proceed with empty test results"
    mock_logger.info.assert_called_once_with(
        "Mutation passed all tests, proceeding with mutation"
    )