import pytest
from unittest.mock import Mock, patch
from src.feasibility_estimator import FeasibilityEstimator
from src.system_model import SystemModel
from src.goal import Goal

@pytest.fixture
def system_model():
    """Fixture to create a mock system model with predefined components and dependencies."""
    model = Mock(spec=SystemModel)
    # Define components and their statuses
    model.components = {
        "auth_service": {"status": "ready", "dependencies": []},
        "data_pipeline": {"status": "ready", "dependencies": ["auth_service"]},
        "frontend": {"status": "ready", "dependencies": ["auth_service", "data_pipeline"]},
        "reporting_module": {"status": "in_progress", "dependencies": ["data_pipeline"]},
        "external_api": {"status": "untested", "dependencies": []}
    }
    # Define schema alignment statuses
    model.schema_alignment = {
        "auth_service": True,
        "data_pipeline": True,
        "frontend": True,
        "reporting_module": False,
        "external_api": True
    }
    # Define cross-component interactions
    model.interactions = [
        {"from": "auth_service", "to": "data_pipeline", "status": "tested"},
        {"from": "data_pipeline", "to": "frontend", "status": "tested"},
        {"from": "frontend", "to": "reporting_module", "status": "untested"},
        {"from": "external_api", "to": "data_pipeline", "status": "untested"}
    ]
    return model

@pytest.fixture
def estimator(system_model):
    """Fixture to create a FeasibilityEstimator instance with the mock system model."""
    return FeasibilityEstimator(system_model)

def test_goal_with_all_prerequisites_met_gets_high_score(estimator):
    """Test that a goal with all prerequisites met gets a high feasibility score."""
    goal = Goal(
        id="goal_1",
        description="Deploy frontend with all dependencies ready",
        dependencies=["auth_service", "data_pipeline", "frontend"],
        schema_requirements=["auth_service", "data_pipeline", "frontend"]
    )
    score = estimator.estimate_feasibility(goal)
    # Expected high score: all dependencies ready, schema aligned, no untested cross-component interactions
    assert score >= 0.8, f"Expected high score >= 0.8, got {score}"

def test_goal_requiring_untested_cross_component_interaction_gets_penalty(estimator):
    """Test that a goal involving untested cross-component interaction gets a penalty."""
    goal = Goal(
        id="goal_2",
        description="Integrate external API with data pipeline (untested interaction)",
        dependencies=["external_api", "data_pipeline"],
        schema_requirements=["external_api", "data_pipeline"]
    )
    score = estimator.estimate_feasibility(goal)
    # Expected penalty due to untested interaction between external_api and data_pipeline
    assert score < 0.7, f"Expected score < 0.7 due to untested interaction, got {score}"

def test_goal_with_unmet_schema_alignment_is_blocked(estimator):
    """Test that a goal with unmet schema alignment is blocked (score 0)."""
    goal = Goal(
        id="goal_3",
        description="Use reporting module with misaligned schema",
        dependencies=["reporting_module"],
        schema_requirements=["reporting_module"]
    )
    score = estimator.estimate_feasibility(goal)
    assert score == 0.0, f"Expected score 0.0 for blocked goal, got {score}"

def test_estimator_parses_goal_dependencies_from_system_model(estimator, system_model):
    """Test that the estimator correctly parses goal dependencies from the system model."""
    # Simulate parsing a goal that depends on components with specific statuses
    goal_dependencies = estimator.parse_goal_dependencies("goal_4", ["auth_service", "frontend"])
    # Verify that the parsed dependencies include status and schema alignment info
    assert "auth_service" in goal_dependencies
    assert goal_dependencies["auth_service"]["status"] == "ready"
    assert goal_dependencies["auth_service"]["schema_aligned"] == True
    assert "frontend" in goal_dependencies
    assert goal_dependencies["frontend"]["status"] == "ready"
    assert goal_dependencies["frontend"]["schema_aligned"] == True

    # Test parsing with a component that has unmet schema alignment
    goal_dependencies_blocked = estimator.parse_goal_dependencies("goal_5", ["reporting_module"])
    assert "reporting_module" in goal_dependencies_blocked
    assert goal_dependencies_blocked["reporting_module"]["schema_aligned"] == False

    # Test parsing with a component that is in progress
    goal_dependencies_in_progress = estimator.parse_goal_dependencies("goal_6", ["reporting_module"])
    assert goal_dependencies_in_progress["reporting_module"]["status"] == "in_progress"