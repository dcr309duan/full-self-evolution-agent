"""Minimal test file for NashEquilibriumDetector.

Tests:
1. Detection of equilibrium state
2. Generation of coordinated change plan
3. Non-triggering on non-equilibrium states
"""

import pytest
from core.nash_detector import NashEquilibriumDetector


@pytest.fixture
def detector():
    """Create a NashEquilibriumDetector instance for testing."""
    return NashEquilibriumDetector()


@pytest.fixture
def equilibrium_state():
    """Return a state where all modules are in equilibrium."""
    return {
        "module_a": {"strategy": "cooperate", "payoff": 10},
        "module_b": {"strategy": "cooperate", "payoff": 10},
        "module_c": {"strategy": "cooperate", "payoff": 10},
    }


@pytest.fixture
def non_equilibrium_state():
    """Return a state where modules are not in equilibrium."""
    return {
        "module_a": {"strategy": "defect", "payoff": 15},
        "module_b": {"strategy": "cooperate", "payoff": 5},
        "module_c": {"strategy": "cooperate", "payoff": 5},
    }


def test_detection_of_equilibrium_state(detector, equilibrium_state):
    """Test that the detector correctly identifies an equilibrium state."""
    result = detector.detect(equilibrium_state)
    assert result is True, "Detector should return True for equilibrium state"


def test_generation_of_coordinated_change_plan(detector, equilibrium_state):
    """Test that a coordinated change plan is generated for equilibrium."""
    plan = detector.generate_plan(equilibrium_state)
    assert plan is not None, "Should generate a plan for equilibrium state"
    assert "actions" in plan, "Plan should contain actions"
    assert len(plan["actions"]) > 0, "Plan should have at least one action"


def test_non_trigger_on_non_equilibrium(detector, non_equilibrium_state):
    """Test that the detector does not trigger on non-equilibrium states."""
    result = detector.detect(non_equilibrium_state)
    assert result is False, "Detector should return False for non-equilibrium state"


def test_no_plan_for_non_equilibrium(detector, non_equilibrium_state):
    """Test that no plan is generated for non-equilibrium states."""
    plan = detector.generate_plan(non_equilibrium_state)
    assert plan is None, "Should not generate a plan for non-equilibrium state"