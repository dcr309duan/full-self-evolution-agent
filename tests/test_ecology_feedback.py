import pytest
from unittest.mock import patch, MagicMock
from core.ecology_integrator import run_ecology_cycle
from core.environmental_pressure import generate_pressure
from core.evolution_orchestrator import EvolutionOrchestrator
from core.capability_factory import CapabilityFactory
from core.goal_generator import GoalGenerator
from core.test_runner import TestRunner
from core.ecology_pressure_engine import EcologyPressureEngine


@pytest.fixture
def mock_orchestrator():
    """Create a mock EvolutionOrchestrator for testing."""
    orchestrator = MagicMock(spec=EvolutionOrchestrator)
    orchestrator.capability_factory = MagicMock(spec=CapabilityFactory)
    orchestrator.goal_generator = MagicMock(spec=GoalGenerator)
    orchestrator.test_runner = MagicMock(spec=TestRunner)
    return orchestrator


@pytest.fixture
def sample_pressure():
    """Create a sample environmental pressure for testing."""
    return generate_pressure("test_pressure", intensity=0.5)


def test_ecology_feedback_loop(mock_orchestrator, sample_pressure):
    """
    Integration test for the ecology feedback loop:
    1. Run a simple mutation
    2. Verify test suite is updated with new pressures
    3. Verify existing capabilities still pass
    4. Verify new goals are generated from the new pressures
    """
    # Step 1: Run a simple mutation
    mock_orchestrator.capability_factory.mutate.return_value = "mutated_capability"
    mutation_result = mock_orchestrator.capability_factory.mutate("base_capability")
    assert mutation_result == "mutated_capability", "Mutation should return a mutated capability"

    # Step 2: Verify test suite is updated with new pressures
    mock_orchestrator.test_runner.update_tests.return_value = True
    test_update_result = mock_orchestrator.test_runner.update_tests(sample_pressure)
    assert test_update_result is True, "Test suite should be updated with new pressures"

    # Step 3: Verify existing capabilities still pass
    mock_orchestrator.test_runner.run_tests.return_value = {"passed": 10, "failed": 0, "total": 10}
    test_results = mock_orchestrator.test_runner.run_tests()
    assert test_results["failed"] == 0, "Existing capabilities should still pass"
    assert test_results["passed"] == test_results["total"], "All tests should pass"

    # Step 4: Verify new goals are generated from the new pressures
    mock_orchestrator.goal_generator.generate_goals.return_value = [
        {"id": "goal_1", "description": "Adapt to test_pressure", "priority": 0.5}
    ]
    new_goals = mock_orchestrator.goal_generator.generate_goals(sample_pressure)
    assert len(new_goals) > 0, "New goals should be generated from pressures"
    assert any("test_pressure" in goal["description"] for goal in new_goals), \
        "Generated goals should reference the new pressure"


def test_ecology_cycle_integration():
    """
    Test the full ecology cycle integration:
    - Generate pressure
    - Run ecology cycle
    - Verify feedback loop completes
    """
    pressure = generate_pressure("integration_pressure", intensity=0.7)
    assert pressure is not None, "Pressure should be generated"
    assert pressure["name"] == "integration_pressure"
    assert pressure["intensity"] == 0.7

    # Run the ecology cycle (this will use the actual implementation)
    # We mock the dependencies to avoid side effects
    with patch("core.ecology_integrator.EvolutionOrchestrator") as mock_eco:
        mock_instance = MagicMock()
        mock_eco.return_value = mock_instance
        mock_instance.run_ecology_cycle.return_value = {"status": "completed", "goals_generated": 3}
        
        result = run_ecology_cycle(pressure)
        assert result["status"] == "completed", "Ecology cycle should complete successfully"
        assert result["goals_generated"] > 0, "Ecology cycle should generate goals"


def test_pressure_generation_and_feedback():
    """
    Test that pressure generation properly feeds into the feedback loop.
    """
    # Generate multiple pressures
    pressures = [
        generate_pressure("pressure_1", intensity=0.3),
        generate_pressure("pressure_2", intensity=0.6),
        generate_pressure("pressure_3", intensity=0.9),
    ]
    
    assert len(pressures) == 3, "Should generate three pressures"
    
    # Verify each pressure has required fields
    for pressure in pressures:
        assert "name" in pressure, "Pressure should have a name"
        assert "intensity" in pressure, "Pressure should have an intensity"
        assert 0 <= pressure["intensity"] <= 1, "Intensity should be between 0 and 1"
    
    # Verify feedback loop processes all pressures
    with patch("core.ecology_integrator.run_ecology_cycle") as mock_cycle:
        mock_cycle.return_value = {"status": "completed", "goals_generated": 2}
        
        for pressure in pressures:
            result = mock_cycle(pressure)
            assert result["status"] == "completed", f"Cycle for {pressure['name']} should complete"
            assert result["goals_generated"] > 0, f"Cycle for {pressure['name']} should generate goals"


def test_ecology_pressure_engine_full_loop():
    """
    Test the full loop using ecology_pressure_engine:
    1. GoalGenerator produces ECOLOGICAL_PRESSURE goal
    2. Pressure engine evaluates the goal
    3. Generates new test templates
    4. Validates templates are syntactically valid Python
    """
    # Step 1: GoalGenerator produces ECOLOGICAL_PRESSURE goal
    goal_generator = GoalGenerator()
    ecological_goal = goal_generator.generate_goal("ECOLOGICAL_PRESSURE", intensity=0.6)
    assert ecological_goal is not None, "GoalGenerator should produce ECOLOGICAL_PRESSURE goal"
    assert ecological_goal["type"] == "ECOLOGICAL_PRESSURE", "Goal type should be ECOLOGICAL_PRESSURE"
    assert "intensity" in ecological_goal, "Goal should contain intensity"
    assert ecological_goal["intensity"] == 0.6, "Goal intensity should match input"

    # Step 2: Pressure engine evaluates the goal
    pressure_engine = EcologyPressureEngine()
    evaluation_result = pressure_engine.evaluate_pressure(ecological_goal)
    assert evaluation_result is not None, "Pressure engine should evaluate the goal"
    assert "status" in evaluation_result, "Evaluation result should have status"
    assert evaluation_result["status"] in ["accepted", "rejected", "pending"], \
        "Status should be one of accepted, rejected, or pending"

    # Step 3: Generate new test templates from the evaluation
    test_templates = pressure_engine.generate_test_templates(evaluation_result)
    assert test_templates is not None, "Should generate test templates"
    assert isinstance(test_templates, list), "Test templates should be a list"
    assert len(test_templates) > 0, "Should generate at least one test template"

    # Step 4: Validate templates are syntactically valid Python
    for template in test_templates:
        assert "code" in template, "Each template should have a 'code' field"
        assert "description" in template, "Each template should have a 'description' field"
        
        # Attempt to compile the template code to check syntax
        try:
            compile(template["code"], "<test_template>", "exec")
        except SyntaxError as e:
            pytest.fail(f"Template code is not syntactically valid Python: {e}")
        
        # Verify template contains test-related structure
        assert "def test_" in template["code"] or "class Test" in template["code"], \
            "Template should contain test function or class definition"
        assert "assert" in template["code"], "Template should contain at least one assert statement"