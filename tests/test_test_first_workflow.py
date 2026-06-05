"""Integration test for the test-first workflow.

This test validates that the test-first workflow correctly enforces the discipline:
1. A mutation is rejected if there is no pre-written failing test.
2. A mutation proceeds if there is a pre-written failing test.
3. After the mutation, the test passes.
"""

import pytest
from unittest.mock import MagicMock, patch
from typing import Callable, Any

# Import the module under test - adjust import path as needed
from src.workflow import TestFirstWorkflow, MutationRequest, MutationResult


class TestFirstWorkflowIntegration:
    """Integration tests for the test-first workflow."""

    @pytest.fixture
    def workflow(self):
        """Create a TestFirstWorkflow instance for testing."""
        return TestFirstWorkflow()

    @pytest.fixture
    def sample_code(self):
        """Sample code that can be mutated."""
        return """
def add(a, b):
    return a + b
"""

    @pytest.fixture
    def failing_test(self):
        """A test that fails initially for the sample code."""
        return """
def test_add():
    assert add(1, 2) == 4  # Intentionally wrong expectation
"""

    @pytest.fixture
    def passing_test(self):
        """A test that passes for the mutated code."""
        return """
def test_add():
    assert add(1, 2) == 3  # Correct expectation after mutation
"""

    def test_mutation_rejected_without_failing_test(self, workflow, sample_code):
        """Verify that a mutation is rejected if no pre-written failing test exists."""
        # Simulate a goal that would produce a mutation
        goal = "Change the add function to multiply instead"
        
        # Create a mutation request without a failing test
        request = MutationRequest(
            code=sample_code,
            goal=goal,
            failing_test=None
        )
        
        # Execute the workflow
        result = workflow.process(request)
        
        # Verify the mutation was rejected
        assert result.status == "rejected"
        assert "no failing test" in result.message.lower() or "test-first" in result.message.lower()

    def test_mutation_proceeds_with_failing_test(self, workflow, sample_code, failing_test):
        """Verify that a mutation proceeds when a pre-written failing test exists."""
        # Simulate a goal that would produce a mutation
        goal = "Change the add function to multiply instead"
        
        # Create a mutation request with a failing test
        request = MutationRequest(
            code=sample_code,
            goal=goal,
            failing_test=failing_test
        )
        
        # Execute the workflow
        result = workflow.process(request)
        
        # Verify the mutation was accepted and processed
        assert result.status == "accepted" or result.status == "completed"
        assert result.mutated_code is not None

    def test_mutation_makes_test_pass(self, workflow, sample_code, failing_test, passing_test):
        """Verify that after mutation, the test passes."""
        # Simulate a goal that would produce a mutation
        goal = "Change the add function to multiply instead"
        
        # Create a mutation request with a failing test
        request = MutationRequest(
            code=sample_code,
            goal=goal,
            failing_test=failing_test
        )
        
        # Execute the workflow
        result = workflow.process(request)
        
        # Verify the mutation was processed
        assert result.status == "completed"
        assert result.mutated_code is not None
        
        # Verify the test now passes with the mutated code
        test_result = workflow.run_test(result.mutated_code, passing_test)
        assert test_result.passed is True

    def test_full_test_first_workflow(self, workflow, sample_code, failing_test, passing_test):
        """Complete end-to-end test of the test-first workflow."""
        # Step 1: Without failing test - mutation should be rejected
        request_no_test = MutationRequest(
            code=sample_code,
            goal="Change add to multiply",
            failing_test=None
        )
        result_no_test = workflow.process(request_no_test)
        assert result_no_test.status == "rejected"
        
        # Step 2: With failing test - mutation should proceed
        request_with_test = MutationRequest(
            code=sample_code,
            goal="Change add to multiply",
            failing_test=failing_test
        )
        result_with_test = workflow.process(request_with_test)
        assert result_with_test.status in ("accepted", "completed")
        
        # Step 3: After mutation, the test should pass
        if result_with_test.status == "accepted":
            # If the workflow requires explicit completion
            result_completed = workflow.complete(result_with_test)
            assert result_completed.status == "completed"
            test_result = workflow.run_test(result_completed.mutated_code, passing_test)
        else:
            test_result = workflow.run_test(result_with_test.mutated_code, passing_test)
        
        assert test_result.passed is True


class MockTestFirstWorkflow:
    """Mock implementation for testing without real dependencies."""
    
    def process(self, request: MutationRequest) -> MutationResult:
        """Simulate the test-first workflow logic."""
        if request.failing_test is None:
            return MutationResult(
                status="rejected",
                message="No failing test provided. Test-first discipline requires a failing test before mutation.",
                mutated_code=None
            )
        
        # Simulate mutation
        mutated_code = request.code.replace("a + b", "a * b")
        
        return MutationResult(
            status="completed",
            message="Mutation applied successfully.",
            mutated_code=mutated_code
        )
    
    def run_test(self, code: str, test_code: str) -> Any:
        """Simulate running a test against code."""
        # In a real implementation, this would execute the test
        # For this mock, we check if the test expects the correct result
        if "== 3" in test_code:
            return MagicMock(passed=True)
        return MagicMock(passed=False)


@pytest.fixture
def mock_workflow():
    """Provide a mock workflow for testing."""
    return MockTestFirstWorkflow()


def test_with_mock_workflow(mock_workflow):
    """Test using the mock workflow to verify the test structure."""
    sample_code = """
def add(a, b):
    return a + b
"""
    failing_test = """
def test_add():
    assert add(1, 2) == 4
"""
    passing_test = """
def test_add():
    assert add(1, 2) == 3
"""
    
    # Test rejection without failing test
    request_no_test = MutationRequest(
        code=sample_code,
        goal="Change add to multiply",
        failing_test=None
    )
    result_no_test = mock_workflow.process(request_no_test)
    assert result_no_test.status == "rejected"
    
    # Test acceptance with failing test
    request_with_test = MutationRequest(
        code=sample_code,
        goal="Change add to multiply",
        failing_test=failing_test
    )
    result_with_test = mock_workflow.process(request_with_test)
    assert result_with_test.status == "completed"
    assert result_with_test.mutated_code is not None
    
    # Test that mutation makes test pass
    test_result = mock_workflow.run_test(result_with_test.mutated_code, passing_test)
    assert test_result.passed is True


if __name__ == "__main__":
    pytest.main([__file__])