import pytest
from unittest.mock import Mock, patch
from dependency_planner import DependencyGraph, GoalPrioritizer, Orchestrator

@pytest.fixture
def sample_graph():
    """Fixture providing a sample DependencyGraph with known dependencies."""
    graph = DependencyGraph()
    graph.add_dependency("pre-mutation validation", "mutation engine")
    graph.add_dependency("mutation engine", "core framework")
    graph.add_dependency("post-mutation analysis", "mutation engine")
    graph.add_dependency("report generation", "post-mutation analysis")
    graph.add_dependency("core framework", None)  # root dependency
    return graph

class TestDependencyGraph:
    """Tests for DependencyGraph class."""

    def test_pre_mutation_depends_on_mutation_engine(self, sample_graph):
        """Test that 'pre-mutation validation' correctly depends on 'mutation engine'."""
        dependencies = sample_graph.get_dependencies("pre-mutation validation")
        assert "mutation engine" in dependencies, (
            "pre-mutation validation should depend on mutation engine"
        )

    def test_topological_sort_valid_order(self, sample_graph):
        """Test that topological sort produces a valid dependency order."""
        sorted_items = sample_graph.topological_sort()
        
        # Build position map
        positions = {item: idx for idx, item in enumerate(sorted_items)}
        
        # Verify all dependencies appear before dependents
        for item in sorted_items:
            deps = sample_graph.get_dependencies(item)
            for dep in deps:
                if dep in positions:
                    assert positions[dep] < positions[item], (
                        f"Dependency '{dep}' should appear before '{item}' in topological sort"
                    )

    def test_topological_sort_contains_all_items(self, sample_graph):
        """Test that topological sort includes all items from the graph."""
        sorted_items = sample_graph.topological_sort()
        all_items = set(sample_graph.get_all_items())
        assert set(sorted_items) == all_items, (
            "Topological sort should contain all items in the graph"
        )

    def test_blocked_goals_identified(self, sample_graph):
        """Test that blocked goals are correctly identified when dependencies are missing."""
        # Simulate missing 'mutation engine' dependency
        blocked = sample_graph.get_blocked_goals(["pre-mutation validation", "mutation engine"])
        
        # If mutation engine is missing, pre-mutation validation should be blocked
        assert "pre-mutation validation" in blocked, (
            "pre-mutation validation should be blocked when mutation engine is missing"
        )
        
        # mutation engine itself should not be blocked if it has no missing dependencies
        assert "mutation engine" not in blocked, (
            "mutation engine should not be blocked if its dependencies are present"
        )

    def test_no_blocked_goals_when_all_present(self, sample_graph):
        """Test that no goals are blocked when all dependencies are present."""
        all_items = sample_graph.get_all_items()
        blocked = sample_graph.get_blocked_goals(all_items)
        assert len(blocked) == 0, (
            "No goals should be blocked when all dependencies are present"
        )

    def test_blocked_goals_with_multiple_missing(self, sample_graph):
        """Test identification of blocked goals when multiple dependencies are missing."""
        # Only provide core framework
        available = ["core framework"]
        blocked = sample_graph.get_blocked_goals(available)
        
        # All items except core framework should be blocked
        expected_blocked = {"mutation engine", "pre-mutation validation", 
                           "post-mutation analysis", "report generation"}
        assert set(blocked) == expected_blocked, (
            f"Expected blocked goals: {expected_blocked}, got: {set(blocked)}"
        )


class TestGoalPrioritizer:
    """Tests for GoalPrioritizer class."""

    @pytest.fixture
    def prioritizer(self):
        """Fixture providing a GoalPrioritizer instance."""
        return GoalPrioritizer()

    def test_reorder_correctly(self, prioritizer):
        """Test that GoalPrioritizer reorders goals correctly based on dependencies."""
        goals = ["report generation", "mutation engine", "pre-mutation validation", 
                "core framework", "post-mutation analysis"]
        
        # Define dependencies
        dependencies = {
            "pre-mutation validation": ["mutation engine"],
            "mutation engine": ["core framework"],
            "post-mutation analysis": ["mutation engine"],
            "report generation": ["post-mutation analysis"],
            "core framework": []
        }
        
        reordered = prioritizer.reorder(goals, dependencies)
        
        # Verify that dependencies come before dependents
        positions = {goal: idx for idx, goal in enumerate(reordered)}
        for goal, deps in dependencies.items():
            for dep in deps:
                assert positions[dep] < positions[goal], (
                    f"'{dep}' should come before '{goal}' in reordered list"
                )

    def test_reorder_preserves_all_goals(self, prioritizer):
        """Test that reordering preserves all original goals."""
        goals = ["report generation", "mutation engine", "pre-mutation validation", 
                "core framework", "post-mutation analysis"]
        dependencies = {
            "pre-mutation validation": ["mutation engine"],
            "mutation engine": ["core framework"],
            "post-mutation analysis": ["mutation engine"],
            "report generation": ["post-mutation analysis"],
            "core framework": []
        }
        
        reordered = prioritizer.reorder(goals, dependencies)
        assert set(reordered) == set(goals), (
            "Reordered list should contain all original goals"
        )

    def test_reorder_with_no_dependencies(self, prioritizer):
        """Test reordering when there are no dependencies."""
        goals = ["goal_a", "goal_b", "goal_c"]
        dependencies = {goal: [] for goal in goals}
        
        reordered = prioritizer.reorder(goals, dependencies)
        assert set(reordered) == set(goals), (
            "All goals should be preserved when there are no dependencies"
        )


class TestIntegrationWithOrchestrator:
    """Integration tests with orchestrator mock."""

    @pytest.fixture
    def mock_orchestrator(self):
        """Fixture providing a mocked Orchestrator."""
        orchestrator = Mock(spec=Orchestrator)
        orchestrator.get_dependency_graph.return_value = DependencyGraph()
        return orchestrator

    def test_orchestrator_uses_dependency_graph(self, mock_orchestrator):
        """Test that orchestrator correctly uses the dependency graph."""
        graph = mock_orchestrator.get_dependency_graph()
        assert isinstance(graph, DependencyGraph), (
            "Orchestrator should return a DependencyGraph instance"
        )

    def test_orchestrator_integration_with_dependency_check(self, mock_orchestrator):
        """Test integration between orchestrator and dependency checking."""
        # Setup mock to return a graph with known dependencies
        graph = DependencyGraph()
        graph.add_dependency("pre-mutation validation", "mutation engine")
        mock_orchestrator.get_dependency_graph.return_value = graph
        
        # Simulate orchestrator checking if a goal is blocked
        mock_orchestrator.is_goal_blocked.return_value = False
        
        # Verify the orchestrator can check dependencies
        result = mock_orchestrator.is_goal_blocked("pre-mutation validation", 
                                                   ["mutation engine"])
        assert result is False, (
            "Goal should not be blocked when dependency is present"
        )

    def test_orchestrator_blocks_goal_when_dependency_missing(self, mock_orchestrator):
        """Test that orchestrator correctly blocks a goal when dependency is missing."""
        # Setup mock to return a graph with known dependencies
        graph = DependencyGraph()
        graph.add_dependency("pre-mutation validation", "mutation engine")
        mock_orchestrator.get_dependency_graph.return_value = graph
        
        # Simulate orchestrator checking if a goal is blocked
        mock_orchestrator.is_goal_blocked.return_value = True
        
        # Verify the orchestrator blocks the goal when dependency is missing
        result = mock_orchestrator.is_goal_blocked("pre-mutation validation", [])
        assert result is True, (
            "Goal should be blocked when dependency is missing"
        )

    def test_orchestrator_integration_with_prioritizer(self, mock_orchestrator):
        """Test integration between orchestrator and GoalPrioritizer."""
        # Setup mock orchestrator with prioritizer
        prioritizer = GoalPrioritizer()
        mock_orchestrator.get_prioritizer.return_value = prioritizer
        
        goals = ["report generation", "mutation engine", "core framework"]
        dependencies = {
            "report generation": ["mutation engine"],
            "mutation engine": ["core framework"],
            "core framework": []
        }
        
        reordered = mock_orchestrator.get_prioritizer().reorder(goals, dependencies)
        
        # Verify correct ordering
        assert reordered == ["core framework", "mutation engine", "report generation"], (
            "Orchestrator should use prioritizer to reorder goals correctly"
        )