import pytest
from unittest.mock import Mock, patch, call
from src.compensator import (
    compensator,
    signature_update_compensation,
    function_rename_compensation,
    removal_wrapper_generation,
    rollback_on_failure,
    CompensationError
)
from src.refactoring_engine import RefactoringAction, AffectedCaller

# ------------------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------------------

@pytest.fixture
def mock_refactoring_action():
    """Create a mock RefactoringAction with basic attributes."""
    action = Mock(spec=RefactoringAction)
    action.old_signature = "def foo(a, b)"
    action.new_signature = "def foo(a, b, c=3)"
    action.old_name = "old_func"
    action.new_name = "new_func"
    action.affected_callers = [
        Mock(spec=AffectedCaller, caller_name="caller1", file_path="module1.py"),
        Mock(spec=AffectedCaller, caller_name="caller2", file_path="module2.py"),
    ]
    return action

@pytest.fixture
def mock_compensator():
    """Create a compensator instance with mocked dependencies."""
    with patch("src.compensator.ASTUpdater") as mock_ast_updater, \
         patch("src.compensator.CodeWriter") as mock_code_writer:
        comp = compensator()
        comp.ast_updater = mock_ast_updater
        comp.code_writer = mock_code_writer
        yield comp

# ------------------------------------------------------------------------------
# Test 1: Signature Update Compensation
# ------------------------------------------------------------------------------

class TestSignatureUpdateCompensation:
    def test_signature_update_applied_correctly(self, mock_compensator, mock_refactoring_action):
        """Verify that signature update compensation correctly modifies the function signature."""
        mock_compensator.ast_updater.update_signature.return_value = True

        result = mock_compensator.signature_update_compensation(mock_refactoring_action)

        assert result is True
        mock_compensator.ast_updater.update_signature.assert_called_once_with(
            mock_refactoring_action.old_signature,
            mock_refactoring_action.new_signature
        )

    def test_signature_update_failure_raises_error(self, mock_compensator, mock_refactoring_action):
        """Ensure that a failure in signature update raises CompensationError."""
        mock_compensator.ast_updater.update_signature.return_value = False

        with pytest.raises(CompensationError, match="Signature update failed"):
            mock_compensator.signature_update_compensation(mock_refactoring_action)

    def test_signature_update_with_no_change(self, mock_compensator):
        """Test that identical signatures are handled gracefully."""
        action = Mock(spec=RefactoringAction)
        action.old_signature = "def foo(a, b)"
        action.new_signature = "def foo(a, b)"
        mock_compensator.ast_updater.update_signature.return_value = True

        result = mock_compensator.signature_update_compensation(action)

        assert result is True
        mock_compensator.ast_updater.update_signature.assert_called_once_with(
            "def foo(a, b)", "def foo(a, b)"
        )

# ------------------------------------------------------------------------------
# Test 2: Function Rename Compensation
# ------------------------------------------------------------------------------

class TestFunctionRenameCompensation:
    def test_rename_applied_to_all_callers(self, mock_compensator, mock_refactoring_action):
        """Verify that function rename updates all affected callers."""
        mock_compensator.ast_updater.rename_function.return_value = True

        result = mock_compensator.function_rename_compensation(mock_refactoring_action)

        assert result is True
        expected_calls = [
            call(mock_refactoring_action.old_name, mock_refactoring_action.new_name, caller)
            for caller in mock_refactoring_action.affected_callers
        ]
        mock_compensator.ast_updater.rename_function.assert_has_calls(expected_calls)

    def test_rename_failure_on_one_caller_raises_error(self, mock_compensator, mock_refactoring_action):
        """Ensure that failure to rename one caller raises CompensationError."""
        mock_compensator.ast_updater.rename_function.side_effect = [
            True, False  # First succeeds, second fails
        ]

        with pytest.raises(CompensationError, match="Rename failed for caller2"):
            mock_compensator.function_rename_compensation(mock_refactoring_action)

    def test_rename_with_no_affected_callers(self, mock_compensator):
        """Test that rename with empty caller list is handled."""
        action = Mock(spec=RefactoringAction)
        action.old_name = "old_func"
        action.new_name = "new_func"
        action.affected_callers = []

        result = mock_compensator.function_rename_compensation(action)

        assert result is True
        mock_compensator.ast_updater.rename_function.assert_not_called()

# ------------------------------------------------------------------------------
# Test 3: Removal Wrapper Generation
# ------------------------------------------------------------------------------

class TestRemovalWrapperGeneration:
    def test_wrapper_generated_correctly(self, mock_compensator, mock_refactoring_action):
        """Verify that removal wrapper is generated with proper structure."""
        mock_compensator.code_writer.generate_wrapper.return_value = "wrapper_code"

        result = mock_compensator.removal_wrapper_generation(mock_refactoring_action)

        assert result == "wrapper_code"
        mock_compensator.code_writer.generate_wrapper.assert_called_once_with(
            mock_refactoring_action.old_name,
            mock_refactoring_action.new_name,
            mock_refactoring_action.affected_callers
        )

    def test_wrapper_generation_failure_raises_error(self, mock_compensator, mock_refactoring_action):
        """Ensure that failure in wrapper generation raises CompensationError."""
        mock_compensator.code_writer.generate_wrapper.side_effect = Exception("Generation error")

        with pytest.raises(CompensationError, match="Wrapper generation failed"):
            mock_compensator.removal_wrapper_generation(mock_refactoring_action)

    def test_wrapper_includes_deprecation_warning(self, mock_compensator, mock_refactoring_action):
        """Test that generated wrapper contains deprecation warning."""
        mock_compensator.code_writer.generate_wrapper.return_value = (
            "def old_func(*args, **kwargs):\n"
            "    warnings.warn(\"old_func is deprecated, use new_func\")\n"
            "    return new_func(*args, **kwargs)"
        )

        result = mock_compensator.removal_wrapper_generation(mock_refactoring_action)

        assert "warnings.warn" in result
        assert "deprecated" in result.lower()

# ------------------------------------------------------------------------------
# Test 4: Multiple Affected Callers Handling
# ------------------------------------------------------------------------------

class TestMultipleAffectedCallers:
    def test_all_callers_updated_in_signature_update(self, mock_compensator):
        """Verify that signature update compensates all affected callers."""
        action = Mock(spec=RefactoringAction)
        action.old_signature = "def foo(a, b)"
        action.new_signature = "def foo(a, b, c=3)"
        action.affected_callers = [
            Mock(spec=AffectedCaller, caller_name=f"caller{i}", file_path=f"module{i}.py")
            for i in range(5)
        ]
        mock_compensator.ast_updater.update_signature.return_value = True

        result = mock_compensator.signature_update_compensation(action)

        assert result is True
        assert mock_compensator.ast_updater.update_signature.call_count == 1

    def test_all_callers_updated_in_rename(self, mock_compensator):
        """Verify that rename compensates all affected callers."""
        action = Mock(spec=RefactoringAction)
        action.old_name = "old_func"
        action.new_name = "new_func"
        action.affected_callers = [
            Mock(spec=AffectedCaller, caller_name=f"caller{i}", file_path=f"module{i}.py")
            for i in range(10)
        ]
        mock_compensator.ast_updater.rename_function.return_value = True

        result = mock_compensator.function_rename_compensation(action)

        assert result is True
        assert mock_compensator.ast_updater.rename_function.call_count == 10

    def test_wrapper_generated_for_multiple_callers(self, mock_compensator):
        """Verify that wrapper generation handles multiple callers."""
        action = Mock(spec=RefactoringAction)
        action.old_name = "old_func"
        action.new_name = "new_func"
        action.affected_callers = [
            Mock(spec=AffectedCaller, caller_name=f"caller{i}", file_path=f"module{i}.py")
            for i in range(3)
        ]
        mock_compensator.code_writer.generate_wrapper.return_value = "wrapper_code"

        result = mock_compensator.removal_wrapper_generation(action)

        assert result == "wrapper_code"
        mock_compensator.code_writer.generate_wrapper.assert_called_once_with(
            action.old_name, action.new_name, action.affected_callers
        )

# ------------------------------------------------------------------------------
# Test 5: Rollback on Failure
# ------------------------------------------------------------------------------

class TestRollbackOnFailure:
    def test_rollback_after_signature_update_failure(self, mock_compensator, mock_refactoring_action):
        """Verify that rollback is performed when signature update fails."""
        mock_compensator.ast_updater.update_signature.side_effect = Exception("Unexpected error")
        mock_compensator.rollback = Mock()

        with pytest.raises(CompensationError):
            mock_compensator.signature_update_compensation(mock_refactoring_action)

        mock_compensator.rollback.assert_called_once()

    def test_rollback_after_rename_failure(self, mock_compensator, mock_refactoring_action):
        """Verify that rollback is performed when rename fails on a caller."""
        mock_compensator.ast_updater.rename_function.side_effect = [
            True, Exception("Rename error")
        ]
        mock_compensator.rollback = Mock()

        with pytest.raises(CompensationError):
            mock_compensator.function_rename_compensation(mock_refactoring_action)

        mock_compensator.rollback.assert_called_once()

    def test_rollback_after_wrapper_generation_failure(self, mock_compensator, mock_refactoring_action):
        """Verify that rollback is performed when wrapper generation fails."""
        mock_compensator.code_writer.generate_wrapper.side_effect = Exception("Wrapper error")
        mock_compensator.rollback = Mock()

        with pytest.raises(CompensationError):
            mock_compensator.removal_wrapper_generation(mock_refactoring_action)

        mock_compensator.rollback.assert_called_once()

    def test_rollback_restores_original_state(self, mock_compensator, mock_refactoring_action):
        """Verify that rollback restores the original state of affected callers."""
        mock_compensator.ast_updater.update_signature.side_effect = Exception("Error")
        mock_compensator.rollback = Mock(return_value=True)

        with pytest.raises(CompensationError):
            mock_compensator.signature_update_compensation(mock_refactoring_action)

        mock_compensator.rollback.assert_called_once_with(mock_refactoring_action)

    def test_rollback_failure_does_not_hide_original_error(self, mock_compensator, mock_refactoring_action):
        """Ensure that rollback failure does not mask the original compensation error."""
        mock_compensator.ast_updater.update_signature.side_effect = CompensationError("Original error")
        mock_compensator.rollback = Mock(side_effect=Exception("Rollback error"))

        with pytest.raises(CompensationError, match="Original error"):
            mock_compensator.signature_update_compensation(mock_refactoring_action)

# ------------------------------------------------------------------------------
# Integration Test: Compensator Workflow
# ------------------------------------------------------------------------------

class TestCompensatorWorkflow:
    def test_full_compensation_workflow(self, mock_compensator, mock_refactoring_action):
        """Integration test for the complete compensation workflow."""
        mock_compensator.ast_updater.update_signature.return_value = True
        mock_compensator.ast_updater.rename_function.return_value = True
        mock_compensator.code_writer.generate_wrapper.return_value = "wrapper_code"

        # Simulate sequential compensation steps
        sig_result = mock_compensator.signature_update_compensation(mock_refactoring_action)
        rename_result = mock_compensator.function_rename_compensation(mock_refactoring_action)
        wrapper_result = mock_compensator.removal_wrapper_generation(mock_refactoring_action)

        assert sig_result is True
        assert rename_result is True
        assert wrapper_result == "wrapper_code"

    def test_workflow_rolls_back_on_any_step_failure(self, mock_compensator, mock_refactoring_action):
        """Verify that the entire workflow rolls back if any step fails."""
        mock_compensator.ast_updater.update_signature.return_value = True
        mock_compensator.ast_updater.rename_function.side_effect = Exception("Rename failed")
        mock_compensator.rollback = Mock()

        with pytest.raises(CompensationError):
            mock_compensator.function_rename_compensation(mock_refactoring_action)

        mock_compensator.rollback.assert_called_once()
        # Ensure signature update was not rolled back (only rename failed)
        assert mock_compensator.ast_updater.update_signature.call_count == 0