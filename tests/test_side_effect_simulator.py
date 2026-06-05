import pytest
from unittest.mock import MagicMock, patch
from side_effect_simulator import (
    SideEffectSimulator,
    FunctionChange,
    ChangeType,
    RiskLevel,
    CallGraph,
    CircularDependencyError
)


@pytest.fixture
def simulator():
    """Fixture providing a fresh SideEffectSimulator instance."""
    return SideEffectSimulator()


@pytest.fixture
def sample_call_graph():
    """Fixture providing a sample call graph for testing."""
    graph = CallGraph()
    # Define a simple call graph:
    # main -> func_a -> func_b
    # main -> func_c
    # func_d -> func_a
    graph.add_call("main", "func_a")
    graph.add_call("main", "func_c")
    graph.add_call("func_a", "func_b")
    graph.add_call("func_d", "func_a")
    return graph


class TestSideEffectSimulator:
    """Test suite for SideEffectSimulator."""

    def test_changing_function_signature_identifies_callers(self, simulator, sample_call_graph):
        """Test that changing a function signature correctly identifies all callers."""
        # Arrange
        simulator.call_graph = sample_call_graph
        change = FunctionChange(
            name="func_a",
            change_type=ChangeType.SIGNATURE_CHANGE,
            old_signature="(x: int, y: str)",
            new_signature="(x: int, y: str, z: float)"
        )

        # Act
        result = simulator.analyze_change(change)

        # Assert
        assert "main" in result.affected_callers
        assert "func_d" in result.affected_callers
        assert len(result.affected_callers) == 2
        assert result.risk_score > 0
        assert result.risk_level in (RiskLevel.MEDIUM, RiskLevel.HIGH)

    def test_renaming_function_propagates_to_all_call_sites(self, simulator, sample_call_graph):
        """Test that renaming a function propagates to all call sites."""
        # Arrange
        simulator.call_graph = sample_call_graph
        change = FunctionChange(
            name="func_a",
            change_type=ChangeType.RENAME,
            old_name="func_a",
            new_name="func_a_new"
        )

        # Act
        result = simulator.analyze_change(change)

        # Assert
        assert "main" in result.affected_callers
        assert "func_d" in result.affected_callers
        assert result.risk_level == RiskLevel.HIGH
        # All call sites should be flagged for update
        assert len(result.call_sites_to_update) == 2
        assert all(site.function_name == "func_a" for site in result.call_sites_to_update)

    def test_removing_function_triggers_high_risk_score(self, simulator, sample_call_graph):
        """Test that removing a function triggers a high risk score."""
        # Arrange
        simulator.call_graph = sample_call_graph
        change = FunctionChange(
            name="func_b",
            change_type=ChangeType.REMOVE
        )

        # Act
        result = simulator.analyze_change(change)

        # Assert
        assert result.risk_level == RiskLevel.CRITICAL
        assert result.risk_score >= 0.8  # High risk threshold
        assert "func_a" in result.affected_callers
        # The removal should cascade through the call chain
        assert "main" in result.indirectly_affected

    def test_adding_new_function_has_no_side_effects(self, simulator, sample_call_graph):
        """Test that adding a new function has no side effects on existing code."""
        # Arrange
        simulator.call_graph = sample_call_graph
        change = FunctionChange(
            name="func_new",
            change_type=ChangeType.ADD,
            new_signature="(x: int) -> str"
        )

        # Act
        result = simulator.analyze_change(change)

        # Assert
        assert len(result.affected_callers) == 0
        assert result.risk_score == 0.0
        assert result.risk_level == RiskLevel.NONE
        assert len(result.call_sites_to_update) == 0
        assert len(result.indirectly_affected) == 0

    def test_circular_dependency_detection(self, simulator):
        """Test that circular dependencies are correctly detected."""
        # Arrange
        # Create a circular dependency: func_a -> func_b -> func_c -> func_a
        graph = CallGraph()
        graph.add_call("func_a", "func_b")
        graph.add_call("func_b", "func_c")
        graph.add_call("func_c", "func_a")
        simulator.call_graph = graph

        # Act & Assert
        with pytest.raises(CircularDependencyError) as exc_info:
            simulator.detect_circular_dependencies()

        assert "func_a" in str(exc_info.value)
        assert "func_b" in str(exc_info.value)
        assert "func_c" in str(exc_info.value)

    def test_circular_dependency_with_multiple_cycles(self, simulator):
        """Test detection of multiple circular dependencies."""
        # Arrange
        graph = CallGraph()
        # Cycle 1: x -> y -> z -> x
        graph.add_call("x", "y")
        graph.add_call("y", "z")
        graph.add_call("z", "x")
        # Cycle 2: a -> b -> a
        graph.add_call("a", "b")
        graph.add_call("b", "a")
        simulator.call_graph = graph

        # Act
        cycles = simulator.detect_circular_dependencies()

        # Assert
        assert len(cycles) == 2
        # Verify both cycles are detected
        cycle_nodes = [set(cycle) for cycle in cycles]
        assert {"x", "y", "z"} in cycle_nodes
        assert {"a", "b"} in cycle_nodes

    def test_no_circular_dependency(self, simulator, sample_call_graph):
        """Test that acyclic graphs are correctly identified."""
        # Arrange
        simulator.call_graph = sample_call_graph

        # Act
        cycles = simulator.detect_circular_dependencies()

        # Assert
        assert len(cycles) == 0

    def test_self_reference_detection(self, simulator):
        """Test that self-referencing functions are detected as circular."""
        # Arrange
        graph = CallGraph()
        graph.add_call("func_a", "func_a")  # Self-reference
        simulator.call_graph = graph

        # Act
        cycles = simulator.detect_circular_dependencies()

        # Assert
        assert len(cycles) == 1
        assert cycles[0] == ["func_a", "func_a"]

    def test_risk_score_calculation_for_signature_change(self, simulator, sample_call_graph):
        """Test risk score calculation for signature changes."""
        # Arrange
        simulator.call_graph = sample_call_graph
        change = FunctionChange(
            name="func_a",
            change_type=ChangeType.SIGNATURE_CHANGE,
            old_signature="(x: int, y: str)",
            new_signature="(x: int, y: str, z: float = 0.0)"
        )

        # Act
        result = simulator.analyze_change(change)

        # Assert
        # Adding an optional parameter should have lower risk than required parameter
        assert result.risk_score < 0.8
        assert result.risk_level in (RiskLevel.LOW, RiskLevel.MEDIUM)

    def test_risk_score_for_breaking_signature_change(self, simulator, sample_call_graph):
        """Test risk score for breaking signature changes."""
        # Arrange
        simulator.call_graph = sample_call_graph
        change = FunctionChange(
            name="func_a",
            change_type=ChangeType.SIGNATURE_CHANGE,
            old_signature="(x: int, y: str)",
            new_signature="(x: int)"  # Removed parameter
        )

        # Act
        result = simulator.analyze_change(change)

        # Assert
        assert result.risk_score >= 0.8
        assert result.risk_level == RiskLevel.HIGH

    def test_affected_callers_chain_propagation(self, simulator):
        """Test that changes propagate through the call chain."""
        # Arrange
        graph = CallGraph()
        # Create a deeper chain: main -> a -> b -> c -> d
        graph.add_call("main", "a")
        graph.add_call("a", "b")
        graph.add_call("b", "c")
        graph.add_call("c", "d")
        simulator.call_graph = graph

        change = FunctionChange(
            name="d",
            change_type=ChangeType.REMOVE
        )

        # Act
        result = simulator.analyze_change(change)

        # Assert
        assert "c" in result.affected_callers
        assert "b" in result.indirectly_affected
        assert "a" in result.indirectly_affected
        assert "main" in result.indirectly_affected

    def test_multiple_callers_same_function(self, simulator):
        """Test that a function called from multiple places is correctly analyzed."""
        # Arrange
        graph = CallGraph()
        graph.add_call("module1", "helper")
        graph.add_call("module2", "helper")
        graph.add_call("module3", "helper")
        simulator.call_graph = graph

        change = FunctionChange(
            name="helper",
            change_type=ChangeType.RENAME,
            old_name="helper",
            new_name="helper_v2"
        )

        # Act
        result = simulator.analyze_change(change)

        # Assert
        assert len(result.affected_callers) == 3
        assert "module1" in result.affected_callers
        assert "module2" in result.affected_callers
        assert "module3" in result.affected_callers

    def test_empty_call_graph(self, simulator):
        """Test behavior with an empty call graph."""
        # Arrange
        simulator.call_graph = CallGraph()
        change = FunctionChange(
            name="nonexistent_func",
            change_type=ChangeType.REMOVE
        )

        # Act
        result = simulator.analyze_change(change)

        # Assert
        assert len(result.affected_callers) == 0
        assert result.risk_score == 0.0
        assert result.risk_level == RiskLevel.NONE

    def test_invalid_change_type(self, simulator, sample_call_graph):
        """Test handling of invalid change types."""
        # Arrange
        simulator.call_graph = sample_call_graph
        change = FunctionChange(
            name="func_a",
            change_type="INVALID_TYPE"  # Invalid change type
        )

        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            simulator.analyze_change(change)
        assert "Invalid change type" in str(exc_info.value)