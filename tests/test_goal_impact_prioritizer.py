import pytest
from modules.goal_impact_prioritizer import (
    score_goal,
    classify_goal,
    archive_low_scoring_goals,
    prioritize_goals,
    GoalImpactPrioritizer
)

# ---------- Fixtures ----------

@pytest.fixture
def sample_goal():
    return {
        "id": "goal_001",
        "description": "Test goal",
        "test_pass_rate": 0.8,
        "novelty_score": 0.6,
        "dependency_count": 3,
        "complexity": 0.5
    }

@pytest.fixture
def sample_goals():
    return [
        {"id": "g1", "test_pass_rate": 0.9, "novelty_score": 0.8, "dependency_count": 1, "complexity": 0.3},
        {"id": "g2", "test_pass_rate": 0.7, "novelty_score": 0.6, "dependency_count": 3, "complexity": 0.5},
        {"id": "g3", "test_pass_rate": 0.4, "novelty_score": 0.3, "dependency_count": 5, "complexity": 0.8},
        {"id": "g4", "test_pass_rate": 0.2, "novelty_score": 0.1, "dependency_count": 7, "complexity": 0.9},
    ]

# ---------- Tests for score_goal ----------

class TestScoreGoal:
    def test_score_with_known_inputs(self, sample_goal):
        """Test that score_goal returns expected value for known inputs."""
        score = score_goal(sample_goal)
        # Expected: 0.8 * 0.5 + 0.6 * 0.3 + (1/3) * 0.2 = 0.4 + 0.18 + 0.0666... = 0.6466...
        expected = 0.8 * 0.5 + 0.6 * 0.3 + (1 / 3) * 0.2
        assert abs(score - expected) < 1e-6

    def test_score_high_pass_rate(self):
        """Test that high pass rate yields high score."""
        goal = {"test_pass_rate": 1.0, "novelty_score": 0.0, "dependency_count": 1, "complexity": 0.0}
        score = score_goal(goal)
        expected = 1.0 * 0.5 + 0.0 * 0.3 + (1 / 1) * 0.2
        assert abs(score - expected) < 1e-6

    def test_score_zero_dependency(self):
        """Test division by zero handling when dependency_count is 0."""
        goal = {"test_pass_rate": 0.5, "novelty_score": 0.5, "dependency_count": 0, "complexity": 0.5}
        score = score_goal(goal)
        # Should treat dependency_count as 1 to avoid division by zero
        expected = 0.5 * 0.5 + 0.5 * 0.3 + (1 / 1) * 0.2
        assert abs(score - expected) < 1e-6

    def test_score_missing_keys(self):
        """Test that missing keys default to 0."""
        goal = {"test_pass_rate": 0.5}
        score = score_goal(goal)
        expected = 0.5 * 0.5 + 0 * 0.3 + (1 / 1) * 0.2
        assert abs(score - expected) < 1e-6

    def test_score_high_pass_rate_simple(self):
        """Test that high pass rate + simple complexity yields score > 0.7."""
        goal = {
            "test_pass_rate": 0.95,
            "novelty_score": 0.5,
            "dependency_count": 2,
            "complexity": 0.1
        }
        score = score_goal(goal)
        assert score > 0.7, f"Expected score > 0.7, got {score}"

    def test_score_low_pass_rate_complex(self):
        """Test that low pass rate + complex complexity yields score < 0.3."""
        goal = {
            "test_pass_rate": 0.1,
            "novelty_score": 0.2,
            "dependency_count": 10,
            "complexity": 0.9
        }
        score = score_goal(goal)
        assert score < 0.3, f"Expected score < 0.3, got {score}"

    def test_score_zero_lines_added(self):
        """Test edge case: zero lines added (dependency_count = 0)."""
        goal = {
            "test_pass_rate": 0.5,
            "novelty_score": 0.5,
            "dependency_count": 0,
            "complexity": 0.5
        }
        score = score_goal(goal)
        # Should handle division by zero gracefully
        assert score >= 0 and score <= 1

    def test_score_zero_dependencies(self):
        """Test edge case: zero dependencies (dependency_count = 0)."""
        goal = {
            "test_pass_rate": 0.8,
            "novelty_score": 0.6,
            "dependency_count": 0,
            "complexity": 0.3
        }
        score = score_goal(goal)
        # Should not raise division by zero
        assert score >= 0 and score <= 1

    def test_score_missing_metrics_default(self):
        """Test that missing metrics default to 0.5."""
        goal = {"id": "test_goal"}
        score = score_goal(goal)
        # All missing metrics should default to 0.5
        expected = 0.5 * 0.5 + 0.5 * 0.3 + (1 / 1) * 0.2
        assert abs(score - expected) < 1e-6

    def test_score_partial_missing_metrics(self):
        """Test that some missing metrics default to 0.5."""
        goal = {
            "test_pass_rate": 0.8,
            "novelty_score": 0.6
        }
        score = score_goal(goal)
        # Missing dependency_count defaults to 1, missing complexity defaults to 0.5
        expected = 0.8 * 0.5 + 0.6 * 0.3 + (1 / 1) * 0.2
        assert abs(score - expected) < 1e-6

    def test_score_boundary_0_3(self):
        """Test that a goal with score exactly 0.3 is handled correctly."""
        goal = {
            "test_pass_rate": 0.3,
            "novelty_score": 0.3,
            "dependency_count": 1,
            "complexity": 0.3
        }
        score = score_goal(goal)
        expected = 0.3 * 0.5 + 0.3 * 0.3 + (1 / 1) * 0.2
        assert abs(score - expected) < 1e-6

    def test_score_boundary_0_7(self):
        """Test that a goal with score exactly 0.7 is handled correctly."""
        goal = {
            "test_pass_rate": 0.9,
            "novelty_score": 0.5,
            "dependency_count": 1,
            "complexity": 0.3
        }
        score = score_goal(goal)
        expected = 0.9 * 0.5 + 0.5 * 0.3 + (1 / 1) * 0.2
        assert abs(score - expected) < 1e-6

# ---------- Tests for classify_goal ----------

class TestClassifyGoal:
    def test_high_impact_classification(self):
        """Test that high scores are classified as 'high'."""
        classification = classify_goal(0.9)
        assert classification == "high"

    def test_medium_impact_classification(self):
        """Test that medium scores are classified as 'medium'."""
        classification = classify_goal(0.5)
        assert classification == "medium"

    def test_low_impact_classification(self):
        """Test that low scores are classified as 'low'."""
        classification = classify_goal(0.2)
        assert classification == "low"

    def test_boundary_high_medium(self):
        """Test boundary between high and medium (0.7)."""
        assert classify_goal(0.7) == "high"
        assert classify_goal(0.699) == "medium"

    def test_boundary_medium_low(self):
        """Test boundary between medium and low (0.3)."""
        assert classify_goal(0.3) == "medium"
        assert classify_goal(0.299) == "low"

    def test_classify_zero(self):
        """Test classification of zero score."""
        assert classify_goal(0.0) == "low"

    def test_classify_one(self):
        """Test classification of maximum score."""
        assert classify_goal(1.0) == "high"

    def test_classify_negative(self):
        """Test classification of negative score (should be low)."""
        assert classify_goal(-0.1) == "low"

# ---------- Tests for archive_low_scoring_goals ----------

class TestArchiveLowScoringGoals:
    def test_archives_low_scoring_goals(self, sample_goals):
        """Test that goals with score < 0.3 are archived."""
        active, archived = archive_low_scoring_goals(sample_goals, threshold=0.3)
        assert len(archived) == 2  # g3 and g4 should be archived
        assert all(g["id"] in ["g3", "g4"] for g in archived)
        assert len(active) == 2
        assert all(g["id"] in ["g1", "g2"] for g in active)

    def test_no_goals_below_threshold(self, sample_goals):
        """Test that no goals are archived when all are above threshold."""
        active, archived = archive_low_scoring_goals(sample_goals, threshold=0.0)
        assert len(archived) == 0
        assert len(active) == 4

    def test_all_goals_below_threshold(self, sample_goals):
        """Test that all goals are archived when threshold is high."""
        active, archived = archive_low_scoring_goals(sample_goals, threshold=1.0)
        assert len(archived) == 4
        assert len(active) == 0

    def test_empty_goal_list(self):
        """Test handling of empty goal list."""
        active, archived = archive_low_scoring_goals([], threshold=0.3)
        assert active == []
        assert archived == []

    def test_archives_correctly_moves_low_scoring(self):
        """Test that archive_low_impact correctly moves low-scoring goals."""
        goals = [
            {"id": "g1", "test_pass_rate": 0.9, "novelty_score": 0.8, "dependency_count": 1, "complexity": 0.2},
            {"id": "g2", "test_pass_rate": 0.1, "novelty_score": 0.1, "dependency_count": 10, "complexity": 0.9},
        ]
        active, archived = archive_low_scoring_goals(goals, threshold=0.3)
        assert len(active) == 1
        assert active[0]["id"] == "g1"
        assert len(archived) == 1
        assert archived[0]["id"] == "g2"

    def test_threshold_at_boundary(self):
        """Test that goals exactly at threshold are not archived."""
        goals = [
            {"id": "g1", "test_pass_rate": 0.5, "novelty_score": 0.5, "dependency_count": 1, "complexity": 0.5},
        ]
        # Score should be exactly 0.5 * 0.5 + 0.5 * 0.3 + 1 * 0.2 = 0.45
        active, archived = archive_low_scoring_goals(goals, threshold=0.45)
        assert len(archived) == 0
        assert len(active) == 1

    def test_archive_with_missing_metrics(self):
        """Test archive functionality with goals that have missing metrics."""
        goals = [
            {"id": "g1", "test_pass_rate": 0.9},
            {"id": "g2", "test_pass_rate": 0.1},
        ]
        active, archived = archive_low_scoring_goals(goals, threshold=0.3)
        assert len(active) == 1
        assert len(archived) == 1

    def test_archive_with_zero_dependencies(self):
        """Test archive functionality with goals that have zero dependencies."""
        goals = [
            {"id": "g1", "test_pass_rate": 0.9, "novelty_score": 0.8, "dependency_count": 0, "complexity": 0.2},
            {"id": "g2", "test_pass_rate": 0.1, "novelty_score": 0.1, "dependency_count": 0, "complexity": 0.9},
        ]
        active, archived = archive_low_scoring_goals(goals, threshold=0.3)
        assert len(active) == 1
        assert len(archived) == 1

# ---------- Tests for prioritize_goals ----------

class TestPrioritizeGoals:
    def test_prioritization_ordering(self, sample_goals):
        """Test that goals are returned in descending order of score."""
        prioritized = prioritize_goals(sample_goals)
        scores = [score_goal(g) for g in prioritized]
        assert all(scores[i] >= scores[i+1] for i in range(len(scores)-1))

    def test_prioritization_with_scores(self, sample_goals):
        """Test that each goal in result has a 'priority_score' key."""
        prioritized = prioritize_goals(sample_goals)
        for goal in prioritized:
            assert "priority_score" in goal

    def test_empty_goal_list(self):
        """Test that empty list returns empty list."""
        result = prioritize_goals([])
        assert result == []

    def test_single_goal(self):
        """Test prioritization with a single goal."""
        goals = [{"id": "g1", "test_pass_rate": 0.5, "novelty_score": 0.5, "dependency_count": 2, "complexity": 0.5}]
        result = prioritize_goals(goals)
        assert len(result) == 1
        assert result[0]["id"] == "g1"
        assert "priority_score" in result[0]

    def test_prioritization_preserves_original_data(self):
        """Test that prioritization preserves original goal data."""
        goals = [
            {"id": "g1", "test_pass_rate": 0.9, "novelty_score": 0.8, "dependency_count": 1, "complexity": 0.3},
            {"id": "g2", "test_pass_rate": 0.4, "novelty_score": 0.3, "dependency_count": 5, "complexity": 0.8},
        ]
        result = prioritize_goals(goals)
        for goal in result:
            assert "id" in goal
            assert "test_pass_rate" in goal
            assert "novelty_score" in goal
            assert "dependency_count" in goal
            assert "complexity" in goal

    def test_prioritize_only_high_scoring(self):
        """Test that only goals with score > 0.7 proceed to mutation."""
        goals = [
            {"id": "g1", "test_pass_rate": 0.9, "novelty_score": 0.8, "dependency_count": 1, "complexity": 0.2},
            {"id": "g2", "test_pass_rate": 0.6, "novelty_score": 0.5, "dependency_count": 3, "complexity": 0.5},
            {"id": "g3", "test_pass_rate": 0.3, "novelty_score": 0.2, "dependency_count": 5, "complexity": 0.8},
        ]
        prioritized = prioritize_goals(goals)
        # Only g1 should have score > 0.7
        high_scoring = [g for g in prioritized if g["priority_score"] > 0.7]
        assert len(high_scoring) == 1
        assert high_scoring[0]["id"] == "g1"

# ---------- Tests for GoalImpactPrioritizer class ----------

class TestGoalImpactPrioritizer:
    def test_initialization(self):
        """Test that the class initializes with default threshold."""
        prioritizer = GoalImpactPrioritizer()
        assert prioritizer.archive_threshold == 0.3

    def test_initialization_custom_threshold(self):
        """Test initialization with custom threshold."""
        prioritizer = GoalImpactPrioritizer(threshold=0.5)
        assert prioritizer.archive_threshold == 0.5

    def test_process_goals(self, sample_goals):
        """Test the full process method returns prioritized and archived lists."""
        prioritizer = GoalImpactPrioritizer()
        prioritized, archived = prioritizer.process_goals(sample_goals)
        # Check that prioritized list is sorted
        scores = [g["priority_score"] for g in prioritized]
        assert all(scores[i] >= scores[i+1] for i in range(len(scores)-1))
        # Check that archived goals are low scoring
        for goal in archived:
            assert score_goal(goal) < prioritizer.archive_threshold

    def test_process_empty_goals(self):
        """Test process with empty goal list."""
        prioritizer = GoalImpactPrioritizer()
        prioritized, archived = prioritizer.process_goals([])
        assert prioritized == []
        assert archived == []

    def test_process_goals_all_high(self):
        """Test process when all goals are high scoring."""
        goals = [
            {"id": "g1", "test_pass_rate": 0.9, "novelty_score": 0.9, "dependency_count": 1, "complexity": 0.1},
            {"id": "g2", "test_pass_rate": 0.8, "novelty_score": 0.8, "dependency_count": 2, "complexity": 0.2},
        ]
        prioritizer = GoalImpactPrioritizer(threshold=0.3)
        prioritized, archived = prioritizer.process_goals(goals)
        assert len(archived) == 0
        assert len(prioritized) == 2

    def test_process_goals_all_low(self):
        """Test process when all goals are low scoring."""
        goals = [
            {"id": "g1", "test_pass_rate": 0.1, "novelty_score": 0.1, "dependency_count": 10, "complexity": 0.9},
            {"id": "g2", "test_pass_rate": 0.2, "novelty_score": 0.2, "dependency_count": 8, "complexity": 0.8},
        ]
        prioritizer = GoalImpactPrioritizer(threshold=0.5)
        prioritized, archived = prioritizer.process_goals(goals)
        assert len(archived) == 2
        assert len(prioritized) == 0

    def test_process_goals_with_missing_metrics(self):
        """Test process with goals that have missing metrics."""
        goals = [
            {"id": "g1", "test_pass_rate": 0.9},
            {"id": "g2", "novelty_score": 0.8},
        ]
        prioritizer = GoalImpactPrioritizer()
        prioritized, archived = prioritizer.process_goals(goals)
        # Should not raise exceptions
        assert len(prioritized) + len(archived) == 2

    def test_process_goals_with_zero_dependencies(self):
        """Test process with goals that have zero dependencies."""
        goals = [
            {"id": "g1", "test_pass_rate": 0.5, "novelty_score": 0.5, "dependency_count": 0, "complexity": 0.5},
        ]
        prioritizer = GoalImpactPrioritizer()
        prioritized, archived = prioritizer.process_goals(goals)
        # Should not raise division by zero
        assert len(prioritized) == 1 or len(archived) == 1

    def test_process_goals_boundary_scores(self):
        """Test process with goals at boundary scores 0.3 and 0.7."""
        goals = [
            {"id": "g1", "test_pass_rate": 0.5, "novelty_score": 0.5, "dependency_count": 1, "complexity": 0.5},
            {"id": "g2", "test_pass_rate": 0.9, "novelty_score": 0.5, "dependency_count": 1, "complexity": 0.3},
        ]
        prioritizer = GoalImpactPrioritizer(threshold=0.3)
        prioritized, archived = prioritizer.process_goals(goals)
        # g1 has score 0.45, g2 has score 0.7
        assert len(archived) == 0  # Both should be above threshold
        assert len(prioritized) == 2

    def test_process_goals_only_high_go_to_mutation(self):
        """Test that only goals with score > 0.7 proceed to mutation."""
        goals = [
            {"id": "g1", "test_pass_rate": 0.9, "novelty_score": 0.8, "dependency_count": 1, "complexity": 0.2},
            {"id": "g2", "test_pass_rate": 0.6, "novelty_score": 0.5, "dependency_count": 3, "complexity": 0.5},
            {"id": "g3", "test_pass_rate": 0.3, "novelty_score": 0.2, "dependency_count": 5, "complexity": 0.8},
        ]
        prioritizer = GoalImpactPrioritizer(threshold=0.3)
        prioritized, archived = prioritizer.process_goals(goals)
        # Only g1 should have score > 0.7
        high_scoring = [g for g in prioritized if g["priority_score"] > 0.7]
        assert len(high_scoring) == 1
        assert high_scoring[0]["id"] == "g1"