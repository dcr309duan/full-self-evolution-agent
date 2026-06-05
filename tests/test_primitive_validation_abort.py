import pytest
from unittest.mock import Mock, patch, call
from orchestrator import Orchestrator
from primitive_validation import PrimitiveValidation
from goal import Goal, GoalStatus

@pytest.fixture
def mock_logger():
    with patch('orchestrator.logger') as mock_log:
        yield mock_log

@pytest.fixture
def mock_primitive_validation():
    validator = Mock(spec=PrimitiveValidation)
    validator.validate.return_value = False  # Simulate validation failure
    return validator

@pytest.fixture
def orchestrator(mock_primitive_validation):
    return Orchestrator(primitive_validator=mock_primitive_validation)

def test_primitive_validation_abort_behavior(orchestrator, mock_primitive_validation, mock_logger):
    """
    Test that when primitive validation fails, the orchestrator:
    1. Aborts higher-level goals
    2. Logs the error appropriately
    """
    # Setup: Create a goal hierarchy
    high_level_goal = Goal("high_level_task", status=GoalStatus.ACTIVE)
    mid_level_goal = Goal("mid_level_task", parent=high_level_goal, status=GoalStatus.ACTIVE)
    low_level_goal = Goal("low_level_task", parent=mid_level_goal, status=GoalStatus.ACTIVE)
    
    # Execute the primitive action that should fail validation
    result = orchestrator.execute_primitive(low_level_goal)
    
    # Verify validation was called
    mock_primitive_validation.validate.assert_called_once_with(low_level_goal)
    
    # Verify the primitive action was not executed
    assert result is False, "Primitive execution should return False on validation failure"
    
    # Verify higher-level goals were aborted
    assert high_level_goal.status == GoalStatus.ABORTED, "High-level goal should be aborted"
    assert mid_level_goal.status == GoalStatus.ABORTED, "Mid-level goal should be aborted"
    assert low_level_goal.status == GoalStatus.FAILED, "Low-level goal should be marked as failed"
    
    # Verify error was logged
    mock_logger.error.assert_called_once()
    log_call_args = mock_logger.error.call_args
    assert "validation" in str(log_call_args).lower(), "Log should mention validation failure"
    assert "abort" in str(log_call_args).lower(), "Log should mention abort action"

def test_primitive_validation_abort_with_multiple_goals(orchestrator, mock_primitive_validation, mock_logger):
    """
    Test abort behavior with multiple concurrent goals when one fails validation.
    """
    # Setup: Create multiple goal hierarchies
    goal_a = Goal("goal_a", status=GoalStatus.ACTIVE)
    goal_b = Goal("goal_b", status=GoalStatus.ACTIVE)
    sub_goal_a = Goal("sub_goal_a", parent=goal_a, status=GoalStatus.ACTIVE)
    sub_goal_b = Goal("sub_goal_b", parent=goal_b, status=GoalStatus.ACTIVE)
    
    # Execute a primitive that fails validation for goal_a's hierarchy
    result = orchestrator.execute_primitive(sub_goal_a)
    
    # Verify only the failing hierarchy is aborted
    assert goal_a.status == GoalStatus.ABORTED, "Goal A hierarchy should be aborted"
    assert sub_goal_a.status == GoalStatus.FAILED, "Sub-goal A should be failed"
    
    # Verify other goals remain unaffected
    assert goal_b.status == GoalStatus.ACTIVE, "Goal B should remain active"
    assert sub_goal_b.status == GoalStatus.ACTIVE, "Sub-goal B should remain active"
    
    # Verify error was logged
    mock_logger.error.assert_called_once()

def test_primitive_validation_abort_no_side_effects(orchestrator, mock_primitive_validation, mock_logger):
    """
    Test that aborting due to validation failure doesn't leave the system in an inconsistent state.
    """
    # Setup: Create a goal with dependencies
    parent_goal = Goal("parent", status=GoalStatus.ACTIVE)
    child_goal = Goal("child", parent=parent_goal, status=GoalStatus.ACTIVE)
    grandchild_goal = Goal("grandchild", parent=child_goal, status=GoalStatus.ACTIVE)
    
    # Execute primitive that fails validation
    result = orchestrator.execute_primitive(grandchild_goal)
    
    # Verify all goals in hierarchy are properly terminated
    assert parent_goal.status == GoalStatus.ABORTED
    assert child_goal.status == GoalStatus.ABORTED
    assert grandchild_goal.status == GoalStatus.FAILED
    
    # Verify no new goals were created
    assert len(orchestrator.goals) == 3, "No new goals should be created"
    
    # Verify the orchestrator is still operational
    assert orchestrator.is_running, "Orchestrator should continue running after abort"

def test_primitive_validation_abort_logs_detailed_error(orchestrator, mock_primitive_validation, mock_logger):
    """
    Test that the error log contains detailed information about the validation failure.
    """
    # Setup: Create a goal with specific parameters
    goal = Goal("specific_task", parameters={"param1": "value1"}, status=GoalStatus.ACTIVE)
    
    # Execute primitive that fails validation
    orchestrator.execute_primitive(goal)
    
    # Verify detailed log
    mock_logger.error.assert_called_once()
    log_message = mock_logger.error.call_args[0][0]
    
    # Check log contains relevant information
    assert "specific_task" in log_message, "Log should contain goal name"
    assert "param1" in log_message or "value1" in log_message, "Log should contain goal parameters"
    assert "validation" in log_message.lower(), "Log should mention validation"
    assert "abort" in log_message.lower(), "Log should mention abort"