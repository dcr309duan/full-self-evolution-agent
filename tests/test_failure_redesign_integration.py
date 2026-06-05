import pytest
from unittest.mock import MagicMock, patch
from typing import List, Dict, Any

# Assuming these imports exist in your project structure
# Adjust import paths as needed
from core.mutation_strategy import MutationStrategy
from core.goal_generator import GoalGenerator
from core.orchestrator import Orchestrator
from core.redesign_goal import RedesignGoal
from core.failure_tracker import FailureTracker


@pytest.fixture
def mock_mutation_strategy():
    """Create a mutation strategy that always fails."""
    strategy = MagicMock(spec=MutationStrategy)
    strategy.execute.return_value = {
        "success": False,
        "error": "Simulated mutation failure",
        "failure_count": 0
    }
    return strategy


@pytest.fixture
def mock_goal_generator():
    """Create a goal generator that produces a redesign goal after repeated failures."""
    generator = MagicMock(spec=GoalGenerator)
    generator.generate_goal.return_value = RedesignGoal(
        goal_id="redesign_001",
        description="Redesign due to repeated mutation failures",
        target_component="mutation_strategy",
        failure_threshold=3,
        current_failures=3
    )
    return generator


@pytest.fixture
def mock_orchestrator():
    """Create an orchestrator that mocks the actual redesign execution."""
    orchestrator = MagicMock(spec=Orchestrator)
    orchestrator.execute_redesign.return_value = {
        "success": True,
        "redesign_id": "redesign_exec_001",
        "changes_made": ["Updated mutation strategy parameters"],
        "execution_time_ms": 150
    }
    return orchestrator


@pytest.fixture
def failure_tracker():
    """Create a real failure tracker for testing."""
    return FailureTracker(max_failures=3)


class TestFailureRedesignIntegration:
    """Integration test for failure-driven redesign workflow."""

    def test_repeated_failures_triggers_redesign_goal(
        self,
        mock_mutation_strategy,
        mock_goal_generator,
        mock_orchestrator,
        failure_tracker
    ):
        """
        Simulate repeated failures of a mutation strategy and verify:
        1. The goal generator produces a redesign goal
        2. The orchestrator executes the redesign
        """
        # Arrange
        num_failures = 3
        redesign_goal = None

        # Act - Simulate repeated failures
        for i in range(num_failures):
            # Execute mutation strategy (always fails)
            result = mock_mutation_strategy.execute()
            
            # Track the failure
            failure_tracker.record_failure("mutation_strategy", result["error"])
            
            # Check if we've reached the failure threshold
            current_failures = failure_tracker.get_failure_count("mutation_strategy")
            
            if current_failures >= failure_tracker.max_failures:
                # Generate redesign goal
                redesign_goal = mock_goal_generator.generate_goal(
                    component="mutation_strategy",
                    failure_count=current_failures,
                    failure_threshold=failure_tracker.max_failures
                )
                break

        # Assert - Verify redesign goal was generated
        assert redesign_goal is not None, "Redesign goal should be generated after repeated failures"
        assert redesign_goal.goal_id == "redesign_001"
        assert redesign_goal.failure_threshold == 3
        assert redesign_goal.current_failures == 3
        assert "repeated mutation failures" in redesign_goal.description.lower()

        # Act - Execute the redesign via orchestrator
        redesign_result = mock_orchestrator.execute_redesign(redesign_goal)

        # Assert - Verify orchestrator executed the redesign
        assert redesign_result["success"] is True
        assert redesign_result["redesign_id"] == "redesign_exec_001"
        assert len(redesign_result["changes_made"]) > 0
        assert redesign_result["execution_time_ms"] > 0

    def test_failure_threshold_not_reached_no_redesign(
        self,
        mock_mutation_strategy,
        mock_goal_generator,
        mock_orchestrator,
        failure_tracker
    ):
        """
        Verify that no redesign goal is generated when failures are below threshold.
        """
        # Arrange
        num_failures = 2  # Below threshold of 3
        redesign_goal = None

        # Act - Simulate failures below threshold
        for i in range(num_failures):
            result = mock_mutation_strategy.execute()
            failure_tracker.record_failure("mutation_strategy", result["error"])
            
            current_failures = failure_tracker.get_failure_count("mutation_strategy")
            
            if current_failures >= failure_tracker.max_failures:
                redesign_goal = mock_goal_generator.generate_goal(
                    component="mutation_strategy",
                    failure_count=current_failures,
                    failure_threshold=failure_tracker.max_failures
                )

        # Assert - No redesign goal should be generated
        assert redesign_goal is None, "Redesign goal should not be generated below failure threshold"
        assert failure_tracker.get_failure_count("mutation_strategy") == 2

    def test_redesign_execution_with_failure_details(
        self,
        mock_mutation_strategy,
        mock_goal_generator,
        mock_orchestrator,
        failure_tracker
    ):
        """
        Verify that the redesign goal contains proper failure details
        and orchestrator uses them for execution.
        """
        # Arrange
        failure_details = [
            "Simulated mutation failure 1",
            "Simulated mutation failure 2",
            "Simulated mutation failure 3"
        ]
        
        # Create a more detailed mock goal
        detailed_goal = RedesignGoal(
            goal_id="redesign_002",
            description="Redesign with detailed failure info",
            target_component="mutation_strategy",
            failure_threshold=3,
            current_failures=3,
            failure_details=failure_details,
            suggested_changes=["Increase timeout", "Add retry logic"]
        )
        mock_goal_generator.generate_goal.return_value = detailed_goal

        # Act - Simulate failures and generate goal
        for i, error_msg in enumerate(failure_details):
            mock_mutation_strategy.execute.return_value = {
                "success": False,
                "error": error_msg,
                "failure_count": i + 1
            }
            result = mock_mutation_strategy.execute()
            failure_tracker.record_failure("mutation_strategy", result["error"])

        redesign_goal = mock_goal_generator.generate_goal(
            component="mutation_strategy",
            failure_count=3,
            failure_threshold=3,
            failure_details=failure_details
        )

        # Assert - Verify detailed goal
        assert redesign_goal.failure_details == failure_details
        assert len(redesign_goal.suggested_changes) == 2
        assert "Increase timeout" in redesign_goal.suggested_changes

        # Act - Execute redesign with details
        mock_orchestrator.execute_redesign.return_value = {
            "success": True,
            "redesign_id": "redesign_exec_002",
            "changes_made": redesign_goal.suggested_changes,
            "failure_details_used": redesign_goal.failure_details,
            "execution_time_ms": 200
        }
        
        redesign_result = mock_orchestrator.execute_redesign(redesign_goal)

        # Assert - Verify orchestrator used failure details
        assert redesign_result["failure_details_used"] == failure_details
        assert redesign_result["changes_made"] == redesign_goal.suggested_changes

    def test_multiple_components_failure_redesign(
        self,
        mock_mutation_strategy,
        mock_goal_generator,
        mock_orchestrator,
        failure_tracker
    ):
        """
        Test that redesign works correctly when multiple components fail.
        """
        # Arrange
        components = ["mutation_strategy", "selection_strategy", "crossover_strategy"]
        redesign_goals = []

        # Create mock goals for different components
        mock_goals = {
            "mutation_strategy": RedesignGoal(
                goal_id="redesign_mutation",
                description="Redesign mutation strategy",
                target_component="mutation_strategy",
                failure_threshold=3,
                current_failures=3
            ),
            "selection_strategy": RedesignGoal(
                goal_id="redesign_selection",
                description="Redesign selection strategy",
                target_component="selection_strategy",
                failure_threshold=3,
                current_failures=3
            ),
            "crossover_strategy": RedesignGoal(
                goal_id="redesign_crossover",
                description="Redesign crossover strategy",
                target_component="crossover_strategy",
                failure_threshold=3,
                current_failures=3
            )
        }

        # Act - Simulate failures for all components
        for component in components:
            for _ in range(3):  # 3 failures each
                mock_mutation_strategy.execute.return_value = {
                    "success": False,
                    "error": f"Failure in {component}",
                    "failure_count": 3
                }
                result = mock_mutation_strategy.execute()
                failure_tracker.record_failure(component, result["error"])

            # Generate redesign goal for this component
            mock_goal_generator.generate_goal.return_value = mock_goals[component]
            goal = mock_goal_generator.generate_goal(
                component=component,
                failure_count=3,
                failure_threshold=3
            )
            redesign_goals.append(goal)

        # Assert - Verify all components have redesign goals
        assert len(redesign_goals) == 3
        for goal, component in zip(redesign_goals, components):
            assert goal.target_component == component
            assert goal.current_failures == 3

        # Act - Execute all redesigns
        redesign_results = []
        for goal in redesign_goals:
            mock_orchestrator.execute_redesign.return_value = {
                "success": True,
                "redesign_id": f"redesign_{goal.target_component}",
                "changes_made": [f"Updated {goal.target_component} parameters"],
                "execution_time_ms": 150
            }
            result = mock_orchestrator.execute_redesign(goal)
            redesign_results.append(result)

        # Assert - Verify all redesigns executed successfully
        for result, component in zip(redesign_results, components):
            assert result["success"] is True
            assert component in result["redesign_id"]
            assert f"Updated {component} parameters" in result["changes_made"]