import pytest
import sys
import os
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.multi_module_forcer import MultiModuleForcer
from core.nash_equilibrium_detector import NashEquilibriumDetector
from core.module_interaction_analyzer import ModuleInteractionAnalyzer
from core.orchestrator import Orchestrator


@pytest.fixture
def mock_modules():
    """Set up 3 mock modules that are stuck in equilibrium."""
    module_a = MagicMock()
    module_a.name = "module_a"
    module_a.get_state.return_value = {"value": 10, "stuck": True}
    module_a.get_dependencies.return_value = ["module_b"]
    module_a.get_dependents.return_value = ["module_c"]
    module_a.get_performance.return_value = 0.5

    module_b = MagicMock()
    module_b.name = "module_b"
    module_b.get_state.return_value = {"value": 20, "stuck": True}
    module_b.get_dependencies.return_value = ["module_c"]
    module_b.get_dependents.return_value = ["module_a"]
    module_b.get_performance.return_value = 0.5

    module_c = MagicMock()
    module_c.name = "module_c"
    module_c.get_state.return_value = {"value": 30, "stuck": True}
    module_c.get_dependencies.return_value = ["module_a"]
    module_c.get_dependents.return_value = ["module_b"]
    module_c.get_performance.return_value = 0.5

    return {"module_a": module_a, "module_b": module_b, "module_c": module_c}


@pytest.fixture
def mock_interaction_analyzer(mock_modules):
    """Create a mock interaction analyzer with equilibrium data."""
    analyzer = MagicMock(spec=ModuleInteractionAnalyzer)
    analyzer.detect_equilibrium.return_value = {
        "in_equilibrium": True,
        "modules": ["module_a", "module_b", "module_c"],
        "cycle": ["module_a", "module_b", "module_c"],
        "stability_score": 0.95
    }
    analyzer.get_interaction_matrix.return_value = {
        "module_a": {"module_b": 0.8, "module_c": -0.2},
        "module_b": {"module_c": 0.7, "module_a": -0.3},
        "module_c": {"module_a": 0.6, "module_b": -0.1}
    }
    return analyzer


@pytest.fixture
def mock_equilibrium_detector(mock_modules):
    """Create a mock equilibrium detector."""
    detector = MagicMock(spec=NashEquilibriumDetector)
    detector.detect_equilibrium.return_value = {
        "in_equilibrium": True,
        "modules": ["module_a", "module_b", "module_c"],
        "nash_equilibrium": True,
        "best_responses": {
            "module_a": {"current": 10, "best": 15},
            "module_b": {"current": 20, "best": 25},
            "module_c": {"current": 30, "best": 35}
        }
    }
    return detector


@pytest.fixture
def mock_orchestrator(mock_modules, mock_interaction_analyzer, mock_equilibrium_detector):
    """Create a mock orchestrator with no improvements."""
    orchestrator = MagicMock(spec=Orchestrator)
    orchestrator.modules = mock_modules
    orchestrator.interaction_analyzer = mock_interaction_analyzer
    orchestrator.equilibrium_detector = mock_equilibrium_detector
    orchestrator.run_cycle.return_value = {
        "cycle_complete": True,
        "improvements_made": False,
        "equilibrium_detected": True,
        "modules_updated": []
    }
    orchestrator.trigger_multi_module_changes.return_value = {
        "changes_applied": True,
        "modules_changed": ["module_a", "module_b", "module_c"],
        "new_performance": 0.8
    }
    return orchestrator


def test_equilibrium_detection_and_plan_generation(mock_modules, mock_interaction_analyzer, mock_equilibrium_detector):
    """Test that equilibrium is detected and a multi-module plan is generated."""
    forcer = MultiModuleForcer(mock_modules, mock_interaction_analyzer, mock_equilibrium_detector)

    result = forcer.analyze_and_force()

    assert result["equilibrium_detected"] is True
    assert "plan" in result
    assert len(result["plan"]["actions"]) > 0
    assert result["plan"]["type"] == "multi_module"


def test_plan_application_improves_performance(mock_modules, mock_interaction_analyzer, mock_equilibrium_detector):
    """Test that applying the generated plan improves module performance."""
    forcer = MultiModuleForcer(mock_modules, mock_interaction_analyzer, mock_equilibrium_detector)

    result = forcer.analyze_and_force()
    plan = result["plan"]

    initial_performance = sum(m.get_performance() for m in mock_modules.values())

    forcer.apply_plan(plan)

    for module in mock_modules.values():
        module.get_performance.return_value = 0.8

    final_performance = sum(m.get_performance() for m in mock_modules.values())

    assert final_performance > initial_performance


def test_plan_contains_all_modules(mock_modules, mock_interaction_analyzer, mock_equilibrium_detector):
    """Test that the generated plan includes actions for all modules in equilibrium."""
    forcer = MultiModuleForcer(mock_modules, mock_interaction_analyzer, mock_equilibrium_detector)

    result = forcer.analyze_and_force()
    plan = result["plan"]

    plan_modules = set(action["module"] for action in plan["actions"])
    assert "module_a" in plan_modules
    assert "module_b" in plan_modules
    assert "module_c" in plan_modules


def test_plan_breaks_equilibrium_cycle(mock_modules, mock_interaction_analyzer, mock_equilibrium_detector):
    """Test that the plan is designed to break the equilibrium cycle."""
    forcer = MultiModuleForcer(mock_modules, mock_interaction_analyzer, mock_equilibrium_detector)

    result = forcer.analyze_and_force()
    plan = result["plan"]

    assert plan["breaks_cycle"] is True
    assert len(plan["actions"]) >= 3


def test_equilibrium_detector_called_correctly(mock_modules, mock_interaction_analyzer, mock_equilibrium_detector):
    """Test that the equilibrium detector is called with correct parameters."""
    forcer = MultiModuleForcer(mock_modules, mock_interaction_analyzer, mock_equilibrium_detector)

    forcer.analyze_and_force()

    mock_equilibrium_detector.detect_equilibrium.assert_called_once()
    mock_interaction_analyzer.detect_equilibrium.assert_called_once()


def test_full_cycle_no_improvements(mock_orchestrator, mock_modules, mock_interaction_analyzer, mock_equilibrium_detector):
    """Integration test: Simulate a full cycle with no improvements and verify multi-module changes on equilibrium."""
    # Import orchestrator and nash detector
    from core.orchestrator import Orchestrator
    from core.nash_equilibrium_detector import NashEquilibriumDetector

    # Simulate a full cycle with no improvements
    cycle_result = mock_orchestrator.run_cycle()

    # Verify cycle completed with no improvements
    assert cycle_result["cycle_complete"] is True
    assert cycle_result["improvements_made"] is False
    assert cycle_result["equilibrium_detected"] is True

    # Verify orchestrator triggers multi-module changes when equilibrium is detected
    if cycle_result["equilibrium_detected"]:
        change_result = mock_orchestrator.trigger_multi_module_changes()

        # Verify changes were applied
        assert change_result["changes_applied"] is True
        assert len(change_result["modules_changed"]) == 3
        assert change_result["new_performance"] > 0.5

        # Verify the orchestrator was called correctly
        mock_orchestrator.trigger_multi_module_changes.assert_called_once()