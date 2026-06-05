"""Unit tests for the nash_breaker module.

Tests that nash_breaker correctly identifies modules in equilibrium,
generates coordinated changes, and handles edge cases.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import numpy as np

from modules.nash_breaker import NashBreaker, EquilibriumState, CoordinatedChange


@pytest.fixture
def nash_breaker():
    """Create a NashBreaker instance for testing."""
    return NashBreaker()


@pytest.fixture
def sample_modules():
    """Create sample module data for testing."""
    return {
        "module_a": {
            "fitness": 0.85,
            "dependencies": ["module_b"],
            "complexity": 0.6,
            "stability": 0.9,
        },
        "module_b": {
            "fitness": 0.82,
            "dependencies": ["module_c"],
            "complexity": 0.5,
            "stability": 0.85,
        },
        "module_c": {
            "fitness": 0.88,
            "dependencies": [],
            "complexity": 0.4,
            "stability": 0.95,
        },
    }


@pytest.fixture
def equilibrium_modules():
    """Create modules in Nash equilibrium state."""
    return {
        "mod_1": {
            "fitness": 0.9,
            "dependencies": ["mod_2"],
            "complexity": 0.3,
            "stability": 0.98,
            "best_response": True,
        },
        "mod_2": {
            "fitness": 0.9,
            "dependencies": ["mod_1"],
            "complexity": 0.3,
            "stability": 0.98,
            "best_response": True,
        },
    }


class TestNashBreakerInitialization:
    """Test NashBreaker initialization and configuration."""

    def test_initialization_defaults(self, nash_breaker):
        """Test default initialization parameters."""
        assert nash_breaker.equilibrium_threshold == 0.05
        assert nash_breaker.min_change_magnitude == 0.1
        assert nash_breaker.max_coordinated_changes == 5

    def test_initialization_custom(self):
        """Test custom initialization parameters."""
        breaker = NashBreaker(
            equilibrium_threshold=0.1,
            min_change_magnitude=0.2,
            max_coordinated_changes=10,
        )
        assert breaker.equilibrium_threshold == 0.1
        assert breaker.min_change_magnitude == 0.2
        assert breaker.max_coordinated_changes == 10


class TestEquilibriumDetection:
    """Test equilibrium detection functionality."""

    def test_detect_equilibrium(self, nash_breaker, equilibrium_modules):
        """Test detection of modules in equilibrium."""
        result = nash_breaker.detect_equilibrium(equilibrium_modules)
        assert isinstance(result, list)
        assert len(result) > 0
        for state in result:
            assert isinstance(state, EquilibriumState)
            assert state.in_equilibrium

    def test_detect_no_equilibrium(self, nash_breaker, sample_modules):
        """Test detection when no equilibrium exists."""
        result = nash_breaker.detect_equilibrium(sample_modules)
        assert isinstance(result, list)
        # Modules with different fitness values should not be in equilibrium
        assert all(not state.in_equilibrium for state in result)

    def test_single_module_equilibrium(self, nash_breaker):
        """Test detection with a single module in equilibrium."""
        single_module = {
            "mod_1": {
                "fitness": 0.95,
                "dependencies": [],
                "complexity": 0.2,
                "stability": 0.99,
                "best_response": True,
            }
        }
        result = nash_breaker.detect_equilibrium(single_module)
        assert len(result) == 1
        assert result[0].in_equilibrium

    def test_partial_equilibrium(self, nash_breaker):
        """Test detection when only some modules are in equilibrium."""
        mixed_modules = {
            "mod_1": {
                "fitness": 0.9,
                "dependencies": ["mod_2"],
                "complexity": 0.3,
                "stability": 0.98,
                "best_response": True,
            },
            "mod_2": {
                "fitness": 0.7,
                "dependencies": ["mod_1"],
                "complexity": 0.5,
                "stability": 0.8,
                "best_response": False,
            },
        }
        result = nash_breaker.detect_equilibrium(mixed_modules)
        equilibrium_states = [r for r in result if r.in_equilibrium]
        assert len(equilibrium_states) == 1
        assert equilibrium_states[0].module_id == "mod_1"


class TestCoordinatedChanges:
    """Test generation of coordinated changes."""

    def test_generate_coordinated_changes(self, nash_breaker, equilibrium_modules):
        """Test generation of coordinated changes for equilibrium modules."""
        changes = nash_breaker.generate_coordinated_changes(equilibrium_modules)
        assert isinstance(changes, list)
        assert len(changes) > 0
        for change in changes:
            assert isinstance(change, CoordinatedChange)
            assert hasattr(change, "module_id")
            assert hasattr(change, "change_type")
            assert hasattr(change, "magnitude")

    def test_change_magnitude_within_bounds(self, nash_breaker, equilibrium_modules):
        """Test that change magnitudes are within configured bounds."""
        changes = nash_breaker.generate_coordinated_changes(equilibrium_modules)
        for change in changes:
            assert change.magnitude >= nash_breaker.min_change_magnitude
            assert change.magnitude <= 1.0

    def test_max_coordinated_changes(self, nash_breaker):
        """Test that maximum number of coordinated changes is respected."""
        many_modules = {
            f"mod_{i}": {
                "fitness": 0.9,
                "dependencies": [],
                "complexity": 0.3,
                "stability": 0.98,
                "best_response": True,
            }
            for i in range(20)
        }
        changes = nash_breaker.generate_coordinated_changes(many_modules)
        assert len(changes) <= nash_breaker.max_coordinated_changes

    def test_no_changes_for_non_equilibrium(self, nash_breaker, sample_modules):
        """Test that no changes are generated for non-equilibrium modules."""
        changes = nash_breaker.generate_coordinated_changes(sample_modules)
        assert len(changes) == 0


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_modules(self, nash_breaker):
        """Test handling of empty module dictionary."""
        result = nash_breaker.detect_equilibrium({})
        assert result == []

        changes = nash_breaker.generate_coordinated_changes({})
        assert changes == []

    def test_none_modules(self, nash_breaker):
        """Test handling of None input."""
        with pytest.raises(TypeError):
            nash_breaker.detect_equilibrium(None)

        with pytest.raises(TypeError):
            nash_breaker.generate_coordinated_changes(None)

    def test_malformed_module_data(self, nash_breaker):
        """Test handling of malformed module data."""
        malformed_modules = {
            "mod_1": {
                "fitness": "invalid",  # Should be numeric
                "dependencies": [],
                "complexity": 0.3,
                "stability": 0.98,
            }
        }
        with pytest.raises((ValueError, TypeError)):
            nash_breaker.detect_equilibrium(malformed_modules)

    def test_modules_with_missing_fields(self, nash_breaker):
        """Test handling of modules with missing required fields."""
        incomplete_modules = {
            "mod_1": {
                "fitness": 0.9,
                # Missing dependencies, complexity, stability
            }
        }
        with pytest.raises(KeyError):
            nash_breaker.detect_equilibrium(incomplete_modules)

    def test_extreme_fitness_values(self, nash_breaker):
        """Test handling of extreme fitness values."""
        extreme_modules = {
            "mod_1": {
                "fitness": 0.0,
                "dependencies": [],
                "complexity": 0.0,
                "stability": 0.0,
                "best_response": True,
            },
            "mod_2": {
                "fitness": 1.0,
                "dependencies": [],
                "complexity": 1.0,
                "stability": 1.0,
                "best_response": True,
            },
        }
        result = nash_breaker.detect_equilibrium(extreme_modules)
        # Modules with very different fitness should not be in equilibrium
        assert not result[0].in_equilibrium or not result[1].in_equilibrium


class TestIntegration:
    """Test integration of detection and change generation."""

    def test_full_workflow(self, nash_breaker, equilibrium_modules):
        """Test the complete workflow from detection to change generation."""
        # Detect equilibrium
        equilibrium_states = nash_breaker.detect_equilibrium(equilibrium_modules)
        assert len(equilibrium_states) > 0

        # Generate changes for equilibrium modules
        changes = nash_breaker.generate_coordinated_changes(equilibrium_modules)
        assert len(changes) > 0

        # Verify changes target modules in equilibrium
        equilibrium_module_ids = {
            state.module_id
            for state in equilibrium_states
            if state.in_equilibrium
        }
        change_module_ids = {change.module_id for change in changes}
        assert change_module_ids.issubset(equilibrium_module_ids)

    def test_break_equilibrium_cycle(self, nash_breaker):
        """Test breaking a cycle of mutual equilibrium."""
        cycle_modules = {
            "mod_a": {
                "fitness": 0.85,
                "dependencies": ["mod_b"],
                "complexity": 0.4,
                "stability": 0.9,
                "best_response": True,
            },
            "mod_b": {
                "fitness": 0.85,
                "dependencies": ["mod_c"],
                "complexity": 0.4,
                "stability": 0.9,
                "best_response": True,
            },
            "mod_c": {
                "fitness": 0.85,
                "dependencies": ["mod_a"],
                "complexity": 0.4,
                "stability": 0.9,
                "best_response": True,
            },
        }

        # Detect equilibrium
        states = nash_breaker.detect_equilibrium(cycle_modules)
        assert all(state.in_equilibrium for state in states)

        # Generate changes to break the cycle
        changes = nash_breaker.generate_coordinated_changes(cycle_modules)
        assert len(changes) > 0

        # Verify changes are diverse (not all targeting same module)
        target_modules = [change.module_id for change in changes]
        assert len(set(target_modules)) > 1


class TestEquilibriumState:
    """Test EquilibriumState data class."""

    def test_equilibrium_state_creation(self):
        """Test creation of EquilibriumState instances."""
        state = EquilibriumState(
            module_id="test_mod",
            in_equilibrium=True,
            fitness=0.9,
            deviation=0.02,
        )
        assert state.module_id == "test_mod"
        assert state.in_equilibrium
        assert state.fitness == 0.9
        assert state.deviation == 0.02

    def test_equilibrium_state_repr(self):
        """Test string representation of EquilibriumState."""
        state = EquilibriumState("mod_1", True, 0.9, 0.01)
        repr_str = repr(state)
        assert "mod_1" in repr_str
        assert "True" in repr_str


class TestCoordinatedChange:
    """Test CoordinatedChange data class."""

    def test_coordinated_change_creation(self):
        """Test creation of CoordinatedChange instances."""
        change = CoordinatedChange(
            module_id="test_mod",
            change_type="fitness",
            magnitude=0.15,
            description="Increase fitness to break equilibrium",
        )
        assert change.module_id == "test_mod"
        assert change.change_type == "fitness"
        assert change.magnitude == 0.15
        assert "Increase fitness" in change.description

    def test_coordinated_change_repr(self):
        """Test string representation of CoordinatedChange."""
        change = CoordinatedChange("mod_1", "complexity", 0.2, "Test change")
        repr_str = repr(change)
        assert "mod_1" in repr_str
        assert "complexity" in repr_str


if __name__ == "__main__":
    pytest.main([__file__])