import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from typing import Dict, List, Any
import json

# Import the module under test - adjust import path as needed
try:
    from core.nash_detector_and_forcer import NashEquilibriumDetector, NashEquilibriumForcer
except ImportError:
    # Fallback for different project structures
    try:
        from nash_detector_and_forcer import NashEquilibriumDetector, NashEquilibriumForcer
    except ImportError:
        pytest.skip("Nash equilibrium modules not available", allow_module_level=True)


@pytest.fixture
def mock_mutation_engine():
    """Create a mock mutation engine that records calls but doesn't mutate."""
    engine = MagicMock()
    engine.mutate.return_value = {"mutated": True, "changes": []}
    engine.get_mutation_history.return_value = []
    return engine


@pytest.fixture
def mock_modules():
    """Create 3 mock modules with known interaction patterns that lead to Nash equilibrium."""
    module_a = MagicMock()
    module_a.name = "ModuleA"
    module_a.get_dependencies.return_value = ["ModuleB"]
    module_a.get_interaction_score.return_value = 0.85
    type(module_a).mutation_count = PropertyMock(return_value=5)
    type(module_a).last_mutation_time = PropertyMock(return_value=100.0)

    module_b = MagicMock()
    module_b.name = "ModuleB"
    module_b.get_dependencies.return_value = ["ModuleC"]
    module_b.get_interaction_score.return_value = 0.78
    type(module_b).mutation_count = PropertyMock(return_value=3)
    type(module_b).last_mutation_time = PropertyMock(return_value=95.0)

    module_c = MagicMock()
    module_c.name = "ModuleC"
    module_c.get_dependencies.return_value = ["ModuleA"]
    module_c.get_interaction_score.return_value = 0.82
    type(module_c).mutation_count = PropertyMock(return_value=4)
    type(module_c).last_mutation_time = PropertyMock(return_value=98.0)

    return [module_a, module_b, module_c]


@pytest.fixture
def equilibrium_detector(mock_mutation_engine, mock_modules):
    """Create a NashEquilibriumDetector with mock dependencies."""
    detector = NashEquilibriumDetector(
        modules=mock_modules,
        mutation_engine=mock_mutation_engine,
        plateau_threshold=3,  # Consider plateau after 3 mutations with <5% improvement
        stability_window=10.0  # Time window for stability check
    )
    return detector


class TestNashDetectionIntegration:
    """Integration tests for Nash equilibrium detection and breaking."""

    def test_equilibrium_detection_when_plateau_reached(self, equilibrium_detector, mock_modules):
        """Test that Nash equilibrium is detected when single-module changes plateau."""
        # Simulate that all modules have plateaued (no significant improvement from single mutations)
        for module in mock_modules:
            module.get_interaction_score.side_effect = [0.85, 0.86, 0.85, 0.85]  # Plateau at ~0.85

        # Configure the detector to recognize plateau
        with patch.object(equilibrium_detector, '_check_plateau', return_value=True):
            is_equilibrium = equilibrium_detector.detect_equilibrium()

        assert is_equilibrium, "Should detect Nash equilibrium when all modules plateau"
        
        # Verify the detector's internal state
        assert equilibrium_detector.equilibrium_detected == True
        assert len(equilibrium_detector.plateaued_modules) == 3

    def test_no_equilibrium_with_improving_module(self, equilibrium_detector, mock_modules):
        """Test that equilibrium is not detected if at least one module can still improve."""
        # Module A can still improve significantly
        mock_modules[0].get_interaction_score.side_effect = [0.85, 0.92, 0.95, 0.98]
        # Modules B and C are plateaued
        mock_modules[1].get_interaction_score.side_effect = [0.78, 0.79, 0.78, 0.78]
        mock_modules[2].get_interaction_score.side_effect = [0.82, 0.83, 0.82, 0.82]

        with patch.object(equilibrium_detector, '_check_plateau', side_effect=[False, True, True]):
            is_equilibrium = equilibrium_detector.detect_equilibrium()

        assert not is_equilibrium, "Should not detect equilibrium when one module can still improve"

    def test_coordinated_mutation_plan_generation(self, equilibrium_detector, mock_modules):
        """Test that a coordinated multi-module mutation plan is generated when equilibrium is detected."""
        # Force equilibrium detection
        equilibrium_detector.equilibrium_detected = True
        equilibrium_detector.plateaued_modules = mock_modules

        # Generate the break-equilibrium plan
        plan = equilibrium_detector.generate_break_plan()

        # Verify plan structure
        assert plan is not None, "Should generate a plan"
        assert "mutations" in plan, "Plan should contain mutations"
        assert len(plan["mutations"]) > 1, "Plan should involve multiple modules"
        
        # Verify all plateaued modules are included
        mutated_modules = {m["module"] for m in plan["mutations"]}
        for module in mock_modules:
            assert module.name in mutated_modules, f"Plan should include {module.name}"

        # Verify the plan is coordinated (not just independent mutations)
        assert "coordination" in plan, "Plan should have coordination strategy"
        assert plan["coordination"]["type"] in ["sequential", "parallel", "hybrid"]

    def test_plan_breaks_equilibrium(self, equilibrium_detector, mock_modules, mock_mutation_engine):
        """Test that executing the generated plan actually breaks the equilibrium."""
        # Setup: equilibrium detected
        equilibrium_detector.equilibrium_detected = True
        equilibrium_detector.plateaued_modules = mock_modules

        # Generate and execute the plan
        plan = equilibrium_detector.generate_break_plan()
        result = equilibrium_detector.execute_break_plan(plan)

        # Verify the mutation engine was called for each module in the plan
        expected_calls = len(plan["mutations"])
        assert mock_mutation_engine.mutate.call_count == expected_calls, \
            f"Mutation engine should be called {expected_calls} times"

        # Verify the equilibrium is broken (scores should change)
        for module in mock_modules:
            # After coordinated mutation, module should no longer be in plateau
            assert module.name not in equilibrium_detector.plateaued_modules, \
                f"{module.name} should no longer be plateaued"

        # Verify the result indicates success
        assert result["success"] == True, "Plan execution should succeed"
        assert result["equilibrium_broken"] == True, "Equilibrium should be broken"

    def test_plan_validation_prevents_bad_plans(self, equilibrium_detector, mock_modules):
        """Test that the system validates plans and rejects invalid ones."""
        # Create an invalid plan (e.g., missing coordination)
        bad_plan = {
            "mutations": [
                {"module": mock_modules[0].name, "type": "random"},
                {"module": mock_modules[1].name, "type": "random"}
            ]
            # Missing "coordination" key
        }

        with pytest.raises(ValueError, match=".*coordination.*"):
            equilibrium_detector.execute_break_plan(bad_plan)

    def test_equilibrium_detection_with_realistic_patterns(self, equilibrium_detector, mock_modules):
        """Test with more realistic interaction patterns that simulate actual code evolution."""
        # Simulate a scenario where modules have been stable for a while
        # Module A: stable at 0.85, Module B: stable at 0.78, Module C: stable at 0.82
        
        # Configure modules to show plateau behavior
        for module in mock_modules:
            # Return same score repeatedly to simulate plateau
            module.get_interaction_score.side_effect = None  # Reset
            if module.name == "ModuleA":
                module.get_interaction_score.return_value = 0.85
            elif module.name == "ModuleB":
                module.get_interaction_score.return_value = 0.78
            else:
                module.get_interaction_score.return_value = 0.82

        # Mock the plateau check to simulate time-based stability
        with patch.object(equilibrium_detector, '_check_plateau', return_value=True):
            with patch.object(equilibrium_detector, '_check_stability_window', return_value=True):
                is_equilibrium = equilibrium_detector.detect_equilibrium()

        assert is_equilibrium, "Should detect equilibrium with stable scores"

        # Now verify the generated plan considers the specific scores
        equilibrium_detector.equilibrium_detected = True
        equilibrium_detector.plateaued_modules = mock_modules
        plan = equilibrium_detector.generate_break_plan()

        # The plan should target modules with lowest scores first (Module B)
        if plan["coordination"]["type"] == "sequential":
            first_mutation = plan["mutations"][0]
            assert first_mutation["module"] == "ModuleB", \
                "Should target lowest-scoring module first in sequential plan"

    def test_mutation_engine_not_called_without_equilibrium(self, equilibrium_detector, mock_mutation_engine):
        """Test that mutation engine is not called when no equilibrium is detected."""
        # No equilibrium detected
        equilibrium_detector.equilibrium_detected = False
        equilibrium_detector.plateaued_modules = []

        # Attempt to generate a plan (should fail gracefully)
        plan = equilibrium_detector.generate_break_plan()
        assert plan is None, "Should not generate plan without equilibrium"

        # Verify mutation engine was not called
        mock_mutation_engine.mutate.assert_not_called()

    def test_full_workflow_simulation(self, equilibrium_detector, mock_modules, mock_mutation_engine):
        """End-to-end test simulating the full detection->plan->execution workflow."""
        # Step 1: Simulate initial state (no equilibrium)
        with patch.object(equilibrium_detector, '_check_plateau', return_value=False):
            initial_state = equilibrium_detector.detect_equilibrium()
        assert not initial_state, "Initial state should not be equilibrium"

        # Step 2: After some time, modules plateau
        with patch.object(equilibrium_detector, '_check_plateau', return_value=True):
            with patch.object(equilibrium_detector, '_check_stability_window', return_value=True):
                equilibrium_reached = equilibrium_detector.detect_equilibrium()
        assert equilibrium_reached, "Should detect equilibrium after plateau"

        # Step 3: Generate break plan
        plan = equilibrium_detector.generate_break_plan()
        assert plan is not None, "Should generate plan"

        # Step 4: Execute plan
        result = equilibrium_detector.execute_break_plan(plan)
        assert result["success"], "Plan execution should succeed"

        # Step 5: Verify equilibrium is broken (simulate post-mutation state)
        with patch.object(equilibrium_detector, '_check_plateau', return_value=False):
            post_equilibrium = equilibrium_detector.detect_equilibrium()
        assert not post_equilibrium, "Equilibrium should be broken after plan execution"

        # Step 6: Verify mutation history was updated
        mock_mutation_engine.get_mutation_history.assert_called_once()