from goal_dependency_graph import GoalDependencyGraph
from goal_generator import GoalGenerator
import json
import pytest

class TestGoalDependencyGraph:
    def setup_method(self):
        self.graph = GoalDependencyGraph()

    # Adding goals with no dependencies
    def test_add_goal_no_dependencies(self):
        self.graph.add_goal("goal_a")
        assert "goal_a" in self.graph.goals
        assert self.graph.goals["goal_a"]["dependencies"] == []
        assert self.graph.goals["goal_a"]["met"] is False

    def test_add_multiple_goals_no_dependencies(self):
        self.graph.add_goal("goal_a")
        self.graph.add_goal("goal_b")
        assert len(self.graph.goals) == 2

    # Adding goals with dependencies
    def test_add_goal_with_dependencies(self):
        self.graph.add_goal("goal_a")
        self.graph.add_goal("goal_b", dependencies=["goal_a"])
        assert "goal_b" in self.graph.goals
        assert self.graph.goals["goal_b"]["dependencies"] == ["goal_a"]

    def test_add_goal_with_multiple_dependencies(self):
        self.graph.add_goal("goal_a")
        self.graph.add_goal("goal_b")
        self.graph.add_goal("goal_c", dependencies=["goal_a", "goal_b"])
        assert self.graph.goals["goal_c"]["dependencies"] == ["goal_a", "goal_b"]

    def test_add_goal_dependency_not_exist(self):
        with pytest.raises(ValueError):
            self.graph.add_goal("goal_b", dependencies=["nonexistent"])

    # Detecting cycles
    def test_detect_self_cycle(self):
        self.graph.add_goal("goal_a")
        with pytest.raises(ValueError):
            self.graph.add_goal("goal_a", dependencies=["goal_a"])

    def test_detect_direct_cycle(self):
        self.graph.add_goal("goal_a")
        self.graph.add_goal("goal_b", dependencies=["goal_a"])
        with pytest.raises(ValueError):
            self.graph.add_goal("goal_a", dependencies=["goal_b"])

    def test_detect_indirect_cycle(self):
        self.graph.add_goal("goal_a")
        self.graph.add_goal("goal_b", dependencies=["goal_a"])
        self.graph.add_goal("goal_c", dependencies=["goal_b"])
        with pytest.raises(ValueError):
            self.graph.add_goal("goal_a", dependencies=["goal_c"])

    # Marking goals as met/unmet
    def test_mark_goal_met(self):
        self.graph.add_goal("goal_a")
        self.graph.mark_met("goal_a")
        assert self.graph.goals["goal_a"]["met"] is True

    def test_mark_goal_unmet(self):
        self.graph.add_goal("goal_a")
        self.graph.mark_met("goal_a")
        self.graph.mark_unmet("goal_a")
        assert self.graph.goals["goal_a"]["met"] is False

    def test_mark_nonexistent_goal(self):
        with pytest.raises(KeyError):
            self.graph.mark_met("nonexistent")

    # Getting blocked vs ready goals
    def test_get_ready_goals_no_dependencies(self):
        self.graph.add_goal("goal_a")
        self.graph.add_goal("goal_b")
        ready = self.graph.get_ready_goals()
        assert set(ready) == {"goal_a", "goal_b"}

    def test_get_ready_goals_with_met_dependencies(self):
        self.graph.add_goal("goal_a")
        self.graph.add_goal("goal_b", dependencies=["goal_a"])
        self.graph.mark_met("goal_a")
        ready = self.graph.get_ready_goals()
        assert "goal_b" in ready

    def test_get_ready_goals_with_unmet_dependencies(self):
        self.graph.add_goal("goal_a")
        self.graph.add_goal("goal_b", dependencies=["goal_a"])
        ready = self.graph.get_ready_goals()
        assert "goal_b" not in ready

    def test_get_blocked_goals(self):
        self.graph.add_goal("goal_a")
        self.graph.add_goal("goal_b", dependencies=["goal_a"])
        blocked = self.graph.get_blocked_goals()
        assert "goal_b" in blocked
        assert "goal_a" not in blocked

    def test_get_blocked_goals_all_met(self):
        self.graph.add_goal("goal_a")
        self.graph.add_goal("goal_b", dependencies=["goal_a"])
        self.graph.mark_met("goal_a")
        blocked = self.graph.get_blocked_goals()
        assert "goal_b" not in blocked

    # Serialization/deserialization
    def test_serialize_deserialize_empty(self):
        data = self.graph.serialize()
        new_graph = GoalDependencyGraph.deserialize(data)
        assert new_graph.goals == {}

    def test_serialize_deserialize_with_goals(self):
        self.graph.add_goal("goal_a")
        self.graph.add_goal("goal_b", dependencies=["goal_a"])
        self.graph.mark_met("goal_a")
        data = self.graph.serialize()
        new_graph = GoalDependencyGraph.deserialize(data)
        assert new_graph.goals == self.graph.goals

    def test_serialize_deserialize_json(self):
        self.graph.add_goal("goal_a")
        data = self.graph.serialize()
        json_data = json.dumps(data)
        parsed = json.loads(json_data)
        new_graph = GoalDependencyGraph.deserialize(parsed)
        assert new_graph.goals == self.graph.goals

    # Integration with mock goal generator
    def test_integration_mock_generator_initial(self):
        mock_gen = GoalGenerator()
        mock_gen.goals = {"goal_a": [], "goal_b": ["goal_a"]}
        self.graph.add_goal("goal_a")
        self.graph.add_goal("goal_b", dependencies=["goal_a"])
        ready = self.graph.get_ready_goals()
        assert ready == ["goal_a"]

    def test_integration_mock_generator_reprioritization(self):
        mock_gen = GoalGenerator()
        mock_gen.goals = {"goal_a": [], "goal_b": ["goal_a"], "goal_c": []}
        self.graph.add_goal("goal_a")
        self.graph.add_goal("goal_b", dependencies=["goal_a"])
        self.graph.add_goal("goal_c")
        # Initially goal_a and goal_c are ready
        ready = self.graph.get_ready_goals()
        assert "goal_a" in ready
        assert "goal_c" in ready
        # Mark goal_a met, now goal_b becomes ready
        self.graph.mark_met("goal_a")
        ready = self.graph.get_ready_goals()
        assert "goal_b" in ready
        assert "goal_c" in ready

    def test_integration_mock_generator_cycle_detection(self):
        mock_gen = GoalGenerator()
        mock_gen.goals = {"goal_a": ["goal_b"], "goal_b": ["goal_a"]}
        with pytest.raises(ValueError):
            self.graph.add_goal("goal_a", dependencies=["goal_b"])
            self.graph.add_goal("goal_b", dependencies=["goal_a"])