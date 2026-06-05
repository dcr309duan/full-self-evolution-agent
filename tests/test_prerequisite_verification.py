import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set
import uuid

# Assuming the project structure:
# - src/orchestrator.py contains Orchestrator class
# - src/dependency_graph.py contains DependencyGraph, Goal, Prerequisite classes
# - src/capability_registry.py contains CapabilityRegistry

from src.orchestrator import Orchestrator
from src.dependency_graph import DependencyGraph, Goal, Prerequisite, GoalStatus
from src.capability_registry import CapabilityRegistry

class TestPrerequisiteVerification:
    """Integration test for prerequisite verification in goal execution pipeline."""

    @pytest.fixture
    def setup_environment(self):
        """Set up the test environment with fresh instances."""
        dependency_graph = DependencyGraph()
        capability_registry = CapabilityRegistry()
        orchestrator = Orchestrator(
            dependency_graph=dependency_graph,
            capability_registry=capability_registry
        )
        return dependency_graph, capability_registry, orchestrator

    def test_hard_prerequisite_blocks_goal_until_satisfied(self, setup_environment):
        """Integration test for hard prerequisite verification workflow."""
        dependency_graph, capability_registry, orchestrator = setup_environment

        # Step 1: Seed the dependency graph with a goal that has a hard prerequisite
        goal_id = str(uuid.uuid4())
        goal = Goal(
            id=goal_id,
            description="Perform mutation analysis",
            prerequisites=[
                Prerequisite(
                    name="mutation_engine_exists",
                    type="hard",  # Hard prerequisite - must be satisfied
                    description="Mutation engine capability must be registered"
                )
            ],
            action=lambda: "Mutation analysis completed successfully"
        )
        dependency_graph.add_goal(goal)

        # Step 2: Ensure the prerequisite is initially unmet
        assert not capability_registry.has_capability("mutation_engine_exists"), \
            "Prerequisite should be initially unmet"

        # Step 3: Run the orchestrator's goal execution pipeline
        result = orchestrator.execute_pipeline()

        # Step 4: Verify the goal is deferred with the correct blocker logged
        assert result.status == GoalStatus.DEFERRED, \
            f"Expected goal to be deferred, got {result.status}"
        
        # Check that the blocker is logged correctly
        assert "mutation_engine_exists" in result.blockers, \
            f"Expected blocker 'mutation_engine_exists' in {result.blockers}"
        assert result.blockers["mutation_engine_exists"] == "hard", \
            f"Expected hard blocker, got {result.blockers.get('mutation_engine_exists')}"

        # Verify the goal is still in the pending state
        assert dependency_graph.get_goal_status(goal_id) == GoalStatus.PENDING, \
            "Goal should remain pending when prerequisite is unmet"

        # Step 5: Satisfy the prerequisite by registering the mutation engine capability
        capability_registry.register_capability(
            name="mutation_engine_exists",
            description="Mutation engine is available",
            provider="test_provider",
            version="1.0.0"
        )

        # Verify the prerequisite is now met
        assert capability_registry.has_capability("mutation_engine_exists"), \
            "Prerequisite should be met after registration"

        # Step 6: Re-run the pipeline
        result = orchestrator.execute_pipeline()

        # Step 7: Verify the goal is now executed successfully
        assert result.status == GoalStatus.COMPLETED, \
            f"Expected goal to be completed, got {result.status}"
        
        # Verify the goal's action was executed
        assert dependency_graph.get_goal_status(goal_id) == GoalStatus.COMPLETED, \
            "Goal should be marked as completed"

        # Verify no blockers remain
        assert len(result.blockers) == 0, \
            f"Expected no blockers, got {result.blockers}"

    def test_multiple_prerequisites_partial_satisfaction(self, setup_environment):
        """Test that multiple prerequisites are handled correctly."""
        dependency_graph, capability_registry, orchestrator = setup_environment

        # Create a goal with multiple prerequisites
        goal_id = str(uuid.uuid4())
        goal = Goal(
            id=goal_id,
            description="Complex analysis task",
            prerequisites=[
                Prerequisite(name="mutation_engine_exists", type="hard"),
                Prerequisite(name="data_source_available", type="hard"),
                Prerequisite(name="logging_enabled", type="soft")  # Soft prerequisite
            ],
            action=lambda: "Complex analysis completed"
        )
        dependency_graph.add_goal(goal)

        # Initially, all prerequisites are unmet
        result = orchestrator.execute_pipeline()
        assert result.status == GoalStatus.DEFERRED
        assert "mutation_engine_exists" in result.blockers
        assert "data_source_available" in result.blockers
        assert "logging_enabled" not in result.blockers  # Soft prerequisites don't block

        # Satisfy one prerequisite
        capability_registry.register_capability("mutation_engine_exists", "Engine available", "test", "1.0")
        result = orchestrator.execute_pipeline()
        assert result.status == GoalStatus.DEFERRED
        assert "data_source_available" in result.blockers
        assert "mutation_engine_exists" not in result.blockers

        # Satisfy all hard prerequisites
        capability_registry.register_capability("data_source_available", "Data available", "test", "1.0")
        result = orchestrator.execute_pipeline()
        assert result.status == GoalStatus.COMPLETED
        assert len(result.blockers) == 0

    def test_prerequisite_removal_and_readdition(self, setup_environment):
        """Test that removing and re-adding a capability works correctly."""
        dependency_graph, capability_registry, orchestrator = setup_environment

        goal_id = str(uuid.uuid4())
        goal = Goal(
            id=goal_id,
            description="Analysis with removable prerequisite",
            prerequisites=[
                Prerequisite(name="mutation_engine_exists", type="hard")
            ],
            action=lambda: "Analysis completed"
        )
        dependency_graph.add_goal(goal)

        # Register and then remove the capability
        capability_registry.register_capability("mutation_engine_exists", "Engine", "test", "1.0")
        capability_registry.remove_capability("mutation_engine_exists")

        # Verify prerequisite is unmet again
        result = orchestrator.execute_pipeline()
        assert result.status == GoalStatus.DEFERRED
        assert "mutation_engine_exists" in result.blockers

        # Re-register the capability
        capability_registry.register_capability("mutation_engine_exists", "Engine", "test", "1.0")
        result = orchestrator.execute_pipeline()
        assert result.status == GoalStatus.COMPLETED

    def test_prerequisite_with_expiration(self, setup_environment):
        """Test that expired prerequisites are treated as unmet."""
        dependency_graph, capability_registry, orchestrator = setup_environment

        goal_id = str(uuid.uuid4())
        goal = Goal(
            id=goal_id,
            description="Time-sensitive analysis",
            prerequisites=[
                Prerequisite(name="temporary_license", type="hard")
            ],
            action=lambda: "Time-sensitive analysis completed"
        )
        dependency_graph.add_goal(goal)

        # Register a capability with an expiration
        capability_registry.register_capability(
            name="temporary_license",
            description="Temporary license",
            provider="test",
            version="1.0",
            expiration=datetime.now() - timedelta(hours=1)  # Already expired
        )

        # Verify expired prerequisite is treated as unmet
        result = orchestrator.execute_pipeline()
        assert result.status == GoalStatus.DEFERRED
        assert "temporary_license" in result.blockers

        # Register a non-expired capability
        capability_registry.register_capability(
            name="temporary_license",
            description="Temporary license",
            provider="test",
            version="1.0",
            expiration=datetime.now() + timedelta(hours=24)  # Valid for 24 hours
        )

        result = orchestrator.execute_pipeline()
        assert result.status == GoalStatus.COMPLETED

    def test_prerequisite_with_dependencies(self, setup_environment):
        """Test that prerequisites can depend on other goals."""
        dependency_graph, capability_registry, orchestrator = setup_environment

        # Create a prerequisite goal
        prereq_goal_id = str(uuid.uuid4())
        prereq_goal = Goal(
            id=prereq_goal_id,
            description="Setup mutation engine",
            prerequisites=[],
            action=lambda: capability_registry.register_capability(
                "mutation_engine_exists", "Engine setup", "test", "1.0"
            )
        )
        dependency_graph.add_goal(prereq_goal)

        # Create a goal that depends on the prerequisite
        main_goal_id = str(uuid.uuid4())
        main_goal = Goal(
            id=main_goal_id,
            description="Perform analysis",
            prerequisites=[
                Prerequisite(name="mutation_engine_exists", type="hard")
            ],
            action=lambda: "Analysis completed"
        )
        dependency_graph.add_goal(main_goal)

        # Initially, the main goal should be deferred
        result = orchestrator.execute_pipeline()
        assert result.status == GoalStatus.DEFERRED
        assert "mutation_engine_exists" in result.blockers

        # Execute the prerequisite goal first
        dependency_graph.set_goal_status(prereq_goal_id, GoalStatus.PENDING)
        result = orchestrator.execute_pipeline()
        
        # Now the main goal should be executable
        assert result.status == GoalStatus.COMPLETED
        assert dependency_graph.get_goal_status(main_goal_id) == GoalStatus.COMPLETED

    def test_concurrent_prerequisite_satisfaction(self, setup_environment):
        """Test that multiple prerequisites can be satisfied concurrently."""
        dependency_graph, capability_registry, orchestrator = setup_environment

        # Create a goal with multiple hard prerequisites
        goal_id = str(uuid.uuid4())
        goal = Goal(
            id=goal_id,
            description="Complex task with multiple prerequisites",
            prerequisites=[
                Prerequisite(name="engine_ready", type="hard"),
                Prerequisite(name="data_loaded", type="hard"),
                Prerequisite(name="config_validated", type="hard")
            ],
            action=lambda: "Complex task completed"
        )
        dependency_graph.add_goal(goal)

        # Initially all prerequisites are unmet
        result = orchestrator.execute_pipeline()
        assert result.status == GoalStatus.DEFERRED
        assert len(result.blockers) == 3

        # Satisfy all prerequisites at once
        capability_registry.register_capability("engine_ready", "Engine ready", "test", "1.0")
        capability_registry.register_capability("data_loaded", "Data loaded", "test", "1.0")
        capability_registry.register_capability("config_validated", "Config validated", "test", "1.0")

        # Verify all prerequisites are now satisfied
        result = orchestrator.execute_pipeline()
        assert result.status == GoalStatus.COMPLETED
        assert len(result.blockers) == 0

    def test_prerequisite_verification_logging(self, setup_environment):
        """Test that prerequisite verification produces proper logs."""
        dependency_graph, capability_registry, orchestrator = setup_environment

        goal_id = str(uuid.uuid4())
        goal = Goal(
            id=goal_id,
            description="Logging test goal",
            prerequisites=[
                Prerequisite(name="mutation_engine_exists", type="hard")
            ],
            action=lambda: "Logging test completed"
        )
        dependency_graph.add_goal(goal)

        # Capture logs during execution
        with patch('logging.getLogger') as mock_logger:
            mock_logger_instance = MagicMock()
            mock_logger.return_value = mock_logger_instance

            # Run pipeline with unmet prerequisite
            result = orchestrator.execute_pipeline()

            # Verify that the blocker was logged
            mock_logger_instance.warning.assert_called_with(
                "Goal %s deferred due to unmet hard prerequisite: %s",
                goal_id,
                "mutation_engine_exists"
            )

            # Satisfy the prerequisite
            capability_registry.register_capability("mutation_engine_exists", "Engine", "test", "1.0")

            # Run pipeline again
            result = orchestrator.execute_pipeline()

            # Verify that successful execution was logged
            mock_logger_instance.info.assert_called_with(
                "Goal %s completed successfully after prerequisite %s was satisfied",
                goal_id,
                "mutation_engine_exists"
            )