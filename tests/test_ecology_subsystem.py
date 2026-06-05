import pytest
import sys
import os
from unittest.mock import patch, MagicMock, PropertyMock
from pathlib import Path
import importlib

# Ensure core modules are importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from core.goal_generator import Goal, GoalType, GoalGenerator
from core.ecology_integrator import run_ecology_cycle
from core.ecology_pressure import (
    EcologyPressure,
    PressureType,
    PressureSeverity,
    generate_ecology_pressure,
    apply_pressure_to_tests,
    get_active_pressures,
    clear_pressures,
    ECOLOGY_PRESSURE_GOAL_TYPE
)
from core.ecology_foundation import (
    EcologyState,
    EcologyConfig,
    EcologyMetrics,
    initialize_ecology,
    update_ecology_state,
    get_ecology_metrics,
    ECOLOGY_ENABLED
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def reset_ecology_state():
    """Reset global ecology state before and after each test."""
    clear_pressures()
    yield
    clear_pressures()


@pytest.fixture
def mock_test_file(tmp_path):
    """Create a temporary test file for mutation testing."""
    test_file = tmp_path / "test_sample.py"
    test_file.write_text("""
def test_pass():
    assert True

def test_fail():
    assert False

def test_skip():
    import pytest
    pytest.skip("skipped")
""")
    return test_file


@pytest.fixture
def mock_goal_generator():
    """Create a mock goal generator that returns ECOLOGICAL_PRESSURE goals."""
    generator = MagicMock(spec=GoalGenerator)
    goal = Goal(
        type=GoalType.ECOLOGICAL_PRESSURE,
        description="Apply ecological pressure to improve test suite",
        priority=5,
        context={"pressure_type": "MUTATION", "severity": "MODERATE"}
    )
    generator.generate_goals.return_value = [goal]
    return generator


# ---------------------------------------------------------------------------
# Test: Pressure Generation
# ---------------------------------------------------------------------------

class TestPressureGeneration:
    """Validate that ecology pressures are generated correctly."""

    def test_generate_ecology_pressure_default(self, reset_ecology_state):
        """Generate default ecology pressure and verify structure."""
        pressure = generate_ecology_pressure()
        assert isinstance(pressure, EcologyPressure)
        assert pressure.pressure_type in PressureType
        assert pressure.severity in PressureSeverity
        assert pressure.description
        assert pressure.source == "ecology_subsystem"
        assert pressure.timestamp > 0

    def test_generate_ecology_pressure_mutation(self, reset_ecology_state):
        """Generate MUTATION pressure type."""
        pressure = generate_ecology_pressure(pressure_type=PressureType.MUTATION)
        assert pressure.pressure_type == PressureType.MUTATION

    def test_generate_ecology_pressure_coverage(self, reset_ecology_state):
        """Generate COVERAGE pressure type."""
        pressure = generate_ecology_pressure(pressure_type=PressureType.COVERAGE)
        assert pressure.pressure_type == PressureType.COVERAGE

    def test_generate_ecology_pressure_performance(self, reset_ecology_state):
        """Generate PERFORMANCE pressure type."""
        pressure = generate_ecology_pressure(pressure_type=PressureType.PERFORMANCE)
        assert pressure.pressure_type == PressureType.PERFORMANCE

    def test_generate_ecology_pressure_severity_high(self, reset_ecology_state):
        """Generate pressure with HIGH severity."""
        pressure = generate_ecology_pressure(severity=PressureSeverity.HIGH)
        assert pressure.severity == PressureSeverity.HIGH

    def test_generate_ecology_pressure_severity_low(self, reset_ecology_state):
        """Generate pressure with LOW severity."""
        pressure = generate_ecology_pressure(severity=PressureSeverity.LOW)
        assert pressure.severity == PressureSeverity.LOW

    def test_generate_ecology_pressure_custom_description(self, reset_ecology_state):
        """Generate pressure with custom description."""
        desc = "Custom test pressure"
        pressure = generate_ecology_pressure(description=desc)
        assert pressure.description == desc

    def test_generate_multiple_pressures(self, reset_ecology_state):
        """Generate multiple pressures and verify they are tracked."""
        pressures = []
        for _ in range(3):
            p = generate_ecology_pressure()
            pressures.append(p)
        active = get_active_pressures()
        assert len(active) == 3
        for p in pressures:
            assert p in active

    def test_clear_pressures(self, reset_ecology_state):
        """Clear all active pressures."""
        generate_ecology_pressure()
        generate_ecology_pressure()
        assert len(get_active_pressures()) == 2
        clear_pressures()
        assert len(get_active_pressures()) == 0


# ---------------------------------------------------------------------------
# Test: Test Suite Mutation
# ---------------------------------------------------------------------------

class TestTestSuiteMutation:
    """Validate that ecology pressures mutate test suites correctly."""

    def test_apply_pressure_mutation_adds_test(self, reset_ecology_state, mock_test_file):
        """Applying MUTATION pressure should add a new test to the file."""
        pressure = generate_ecology_pressure(
            pressure_type=PressureType.MUTATION,
            description="Add a new failing test"
        )
        result = apply_pressure_to_tests(pressure, str(mock_test_file))
        assert result is True
        content = mock_test_file.read_text()
        assert "def test_mutated_" in content
        assert "assert False" in content

    def test_apply_pressure_mutation_multiple(self, reset_ecology_state, mock_test_file):
        """Applying MUTATION pressure multiple times should add multiple tests."""
        for _ in range(3):
            pressure = generate_ecology_pressure(pressure_type=PressureType.MUTATION)
            apply_pressure_to_tests(pressure, str(mock_test_file))
        content = mock_test_file.read_text()
        mutated_count = content.count("def test_mutated_")
        assert mutated_count == 3

    def test_apply_pressure_coverage_adds_test(self, reset_ecology_state, mock_test_file):
        """Applying COVERAGE pressure should add a coverage test."""
        pressure = generate_ecology_pressure(
            pressure_type=PressureType.COVERAGE,
            description="Improve coverage"
        )
        result = apply_pressure_to_tests(pressure, str(mock_test_file))
        assert result is True
        content = mock_test_file.read_text()
        assert "def test_coverage_" in content

    def test_apply_pressure_performance_adds_test(self, reset_ecology_state, mock_test_file):
        """Applying PERFORMANCE pressure should add a performance test."""
        pressure = generate_ecology_pressure(
            pressure_type=PressureType.PERFORMANCE,
            description="Test performance"
        )
        result = apply_pressure_to_tests(pressure, str(mock_test_file))
        assert result is True
        content = mock_test_file.read_text()
        assert "def test_performance_" in content

    def test_apply_pressure_invalid_file(self, reset_ecology_state):
        """Applying pressure to a non-existent file should return False."""
        pressure = generate_ecology_pressure()
        result = apply_pressure_to_tests(pressure, "/nonexistent/path/test.py")
        assert result is False

    def test_apply_pressure_preserves_existing_tests(self, reset_ecology_state, mock_test_file):
        """Applying pressure should not remove existing tests."""
        original_content = mock_test_file.read_text()
        pressure = generate_ecology_pressure(pressure_type=PressureType.MUTATION)
        apply_pressure_to_tests(pressure, str(mock_test_file))
        content = mock_test_file.read_text()
        assert "def test_pass()" in content
        assert "def test_fail()" in content
        assert "def test_skip()" in content


# ---------------------------------------------------------------------------
# Test: Goal Integration
# ---------------------------------------------------------------------------

class TestGoalIntegration:
    """Validate that ecology pressures integrate with the goal system."""

    def test_goal_type_constant_exists(self):
        """ECOLOGY_PRESSURE_GOAL_TYPE should be defined."""
        assert ECOLOGY_PRESSURE_GOAL_TYPE == "ECOLOGICAL_PRESSURE"

    def test_goal_generator_can_create_ecology_goal(self, mock_goal_generator):
        """Goal generator should be able to create ECOLOGICAL_PRESSURE goals."""
        goals = mock_goal_generator.generate_goals()
        assert len(goals) == 1
        goal = goals[0]
        assert goal.type == GoalType.ECOLOGICAL_PRESSURE
        assert "pressure_type" in goal.context
        assert "severity" in goal.context

    def test_ecology_cycle_processes_goals(self, reset_ecology_state, mock_goal_generator):
        """Running ecology cycle should process goals and generate pressures."""
        with patch('core.ecology_integrator.GoalGenerator', return_value=mock_goal_generator):
            result = run_ecology_cycle()
            assert result is True
            active = get_active_pressures()
            assert len(active) > 0

    def test_ecology_cycle_with_no_goals(self, reset_ecology_state):
        """Running ecology cycle with no goals should still generate default pressure."""
        generator = MagicMock(spec=GoalGenerator)
        generator.generate_goals.return_value = []
        with patch('core.ecology_integrator.GoalGenerator', return_value=generator):
            result = run_ecology_cycle()
            assert result is True
            active = get_active_pressures()
            assert len(active) > 0

    def test_ecology_cycle_applies_pressure_to_tests(self, reset_ecology_state, mock_test_file):
        """Ecology cycle should apply pressure to test files."""
        generator = MagicMock(spec=GoalGenerator)
        goal = Goal(
            type=GoalType.ECOLOGICAL_PRESSURE,
            description="Test",
            priority=5,
            context={"pressure_type": "MUTATION", "severity": "MODERATE", "target_file": str(mock_test_file)}
        )
        generator.generate_goals.return_value = [goal]
        with patch('core.ecology_integrator.GoalGenerator', return_value=generator):
            result = run_ecology_cycle()
            assert result is True
            content = mock_test_file.read_text()
            assert "def test_mutated_" in content

    def test_ecology_cycle_handles_errors_gracefully(self, reset_ecology_state):
        """Ecology cycle should handle errors without crashing."""
        generator = MagicMock(spec=GoalGenerator)
        generator.generate_goals.side_effect = Exception("Generator error")
        with patch('core.ecology_integrator.GoalGenerator', return_value=generator):
            result = run_ecology_cycle()
            assert result is False


# ---------------------------------------------------------------------------
# Test: Import Correctness
# ---------------------------------------------------------------------------

class TestImportCorrectness:
    """Validate that all ecology subsystem modules import correctly."""

    def test_import_ecology_pressure(self):
        """core.ecology_pressure should import without errors."""
        import core.ecology_pressure
        assert hasattr(core.ecology_pressure, 'EcologyPressure')
        assert hasattr(core.ecology_pressure, 'PressureType')
        assert hasattr(core.ecology_pressure, 'PressureSeverity')
        assert hasattr(core.ecology_pressure, 'generate_ecology_pressure')
        assert hasattr(core.ecology_pressure, 'apply_pressure_to_tests')
        assert hasattr(core.ecology_pressure, 'get_active_pressures')
        assert hasattr(core.ecology_pressure, 'clear_pressures')

    def test_import_ecology_foundation(self):
        """core.ecology_foundation should import without errors."""
        import core.ecology_foundation
        assert hasattr(core.ecology_foundation, 'EcologyState')
        assert hasattr(core.ecology_foundation, 'EcologyConfig')
        assert hasattr(core.ecology_foundation, 'EcologyMetrics')
        assert hasattr(core.ecology_foundation, 'initialize_ecology')
        assert hasattr(core.ecology_foundation, 'update_ecology_state')
        assert hasattr(core.ecology_foundation, 'get_ecology_metrics')

    def test_import_ecology_integrator(self):
        """core.ecology_integrator should import without errors."""
        import core.ecology_integrator
        assert hasattr(core.ecology_integrator, 'run_ecology_cycle')

    def test_import_goal_generator(self):
        """core.goal_generator should import without errors."""
        import core.goal_generator
        assert hasattr(core.goal_generator, 'Goal')
        assert hasattr(core.goal_generator, 'GoalType')
        assert hasattr(core.goal_generator, 'GoalGenerator')

    def test_goal_type_enum_has_ecology_pressure(self):
        """GoalType enum should have ECOLOGICAL_PRESSURE member."""
        assert hasattr(GoalType, 'ECOLOGICAL_PRESSURE')
        assert GoalType.ECOLOGICAL_PRESSURE.value == "ECOLOGICAL_PRESSURE"

    def test_ecology_enabled_flag(self):
        """ECOLOGY_ENABLED flag should exist and be boolean."""
        assert isinstance(ECOLOGY_ENABLED, bool)

    def test_pressure_type_enum_values(self):
        """PressureType enum should have expected members."""
        assert hasattr(PressureType, 'MUTATION')
        assert hasattr(PressureType, 'COVERAGE')
        assert hasattr(PressureType, 'PERFORMANCE')

    def test_pressure_severity_enum_values(self):
        """PressureSeverity enum should have expected members."""
        assert hasattr(PressureSeverity, 'LOW')
        assert hasattr(PressureSeverity, 'MODERATE')
        assert hasattr(PressureSeverity, 'HIGH')

    def test_ecology_state_defaults(self):
        """EcologyState should have default values."""
        state = EcologyState()
        assert hasattr(state, 'active_pressures')
        assert hasattr(state, 'pressure_history')
        assert hasattr(state, 'metrics')

    def test_ecology_config_defaults(self):
        """EcologyConfig should have default values."""
        config = EcologyConfig()
        assert hasattr(config, 'max_pressures')
        assert hasattr(config, 'pressure_decay_rate')
        assert hasattr(config, 'mutation_rate')

    def test_ecology_metrics_defaults(self):
        """EcologyMetrics should have default values."""
        metrics = EcologyMetrics()
        assert hasattr(metrics, 'total_pressures_generated')
        assert hasattr(metrics, 'total_pressures_applied')
        assert hasattr(metrics, 'total_mutations_created')
        assert hasattr(metrics, 'total_coverage_tests_added')
        assert hasattr(metrics, 'total_performance_tests_added')


# ---------------------------------------------------------------------------
# Test: End-to-End Ecology Cycle
# ---------------------------------------------------------------------------

class TestEndToEndEcologyCycle:
    """Full end-to-end test of the ecology subsystem."""

    def test_full_ecology_cycle(self, reset_ecology_state, mock_test_file):
        """Run a complete ecology cycle and verify all components work together."""
        # Step 1: Initialize ecology
        initialize_ecology()
        state = update_ecology_state()
        assert state is not None

        # Step 2: Generate a goal
        generator = GoalGenerator()
        goals = generator.generate_goals()
        assert len(goals) > 0

        # Step 3: Run ecology cycle
        with patch('core.ecology_integrator.GoalGenerator', return_value=generator):
            result = run_ecology_cycle()
            assert result is True

        # Step 4: Verify pressures were generated
        active = get_active_pressures()
        assert len(active) > 0

        # Step 5: Verify metrics were updated
        metrics = get_ecology_metrics()
        assert metrics.total_pressures_generated > 0

        # Step 6: Clear state
        clear_pressures()
        assert len(get_active_pressures()) == 0

    def test_ecology_cycle_with_mutation(self, reset_ecology_state, mock_test_file):
        """Run ecology cycle that mutates a test file."""
        initialize_ecology()
        generator = GoalGenerator()
        # Force a MUTATION goal
        goal = Goal(
            type=GoalType.ECOLOGICAL_PRESSURE,
            description="Mutate tests",
            priority=5,
            context={"pressure_type": "MUTATION", "severity": "HIGH", "target_file": str(mock_test_file)}
        )
        generator.generate_goals = MagicMock(return_value=[goal])

        with patch('core.ecology_integrator.GoalGenerator', return_value=generator):
            result = run_ecology_cycle()
            assert result is True

        content = mock_test_file.read_text()
        assert "def test_mutated_" in content

        metrics = get_ecology_metrics()
        assert metrics.total_mutations_created > 0

    def test_ecology_cycle_pressure_decay(self, reset_ecology_state):
        """Verify that old pressures decay and are removed."""
        initialize_ecology()
        # Generate pressures
        for _ in range(5):
            generate_ecology_pressure()
        assert len(get_active_pressures()) == 5

        # Simulate pressure decay by running cycle multiple times
        for _ in range(10):
            run_ecology_cycle()

        # After many cycles, old pressures should have decayed
        active = get_active_pressures()
        assert len(active) <= 5  # Should not exceed max_pressures