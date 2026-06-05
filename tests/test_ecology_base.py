import pytest
import sys
import os

# Add the project root to the path so we can import from core
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from core.ecology_engine import EcologyEngine


class TestEcologyBase:
    """Base test class for ecology-related tests."""

    @pytest.fixture
    def engine(self):
        """Create a basic EcologyEngine instance for testing."""
        return EcologyEngine()

    def test_engine_creation(self, engine):
        """Test that the EcologyEngine can be instantiated."""
        assert engine is not None
        assert isinstance(engine, EcologyEngine)

    def test_engine_default_attributes(self, engine):
        """Test that the engine has expected default attributes."""
        # Check for common expected attributes
        assert hasattr(engine, 'species')
        assert hasattr(engine, 'environment')
        assert hasattr(engine, 'time_step')

    def test_engine_initial_state(self, engine):
        """Test the initial state of the engine."""
        # Verify initial species list is empty or has expected structure
        assert isinstance(engine.species, (list, dict))
        # Verify initial environment is properly initialized
        assert engine.environment is not None

    def test_engine_step(self, engine):
        """Test that the engine can perform a simulation step."""
        # Run a single step
        result = engine.step()
        # Step should return something (could be None, dict, etc.)
        assert result is not None

    def test_engine_multiple_steps(self, engine):
        """Test that the engine can run multiple steps."""
        initial_time = engine.time_step
        # Run 5 steps
        for _ in range(5):
            engine.step()
        # Time should have advanced
        assert engine.time_step > initial_time

    def test_engine_reset(self, engine):
        """Test that the engine can be reset to initial state."""
        # Run some steps
        for _ in range(3):
            engine.step()
        # Reset
        engine.reset()
        # After reset, time should be back to initial
        assert engine.time_step == 0

    def test_engine_add_species(self, engine):
        """Test adding a species to the engine."""
        species_name = "TestSpecies"
        engine.add_species(species_name)
        assert species_name in engine.species

    def test_engine_remove_species(self, engine):
        """Test removing a species from the engine."""
        species_name = "TestSpecies"
        engine.add_species(species_name)
        engine.remove_species(species_name)
        assert species_name not in engine.species

    def test_engine_get_metrics(self, engine):
        """Test that the engine can return metrics."""
        metrics = engine.get_metrics()
        assert metrics is not None
        # Metrics should be a dict or have expected structure
        assert isinstance(metrics, dict)