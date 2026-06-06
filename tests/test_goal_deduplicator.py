import unittest
from unittest.mock import Mock, patch
from core.goal_deduplicator import GoalDeduplicator

class TestGoalDeduplicator(unittest.TestCase):
    def setUp(self):
        self.deduplicator = GoalDeduplicator()
        self.deduplicator.pending_goals = []

    def test_extract_keywords(self):
        """Test that extract_keywords removes stopwords and tokenizes correctly."""
        description = "the quick brown fox jumps over the lazy dog"
        keywords = self.deduplicator.extract_keywords(description)
        expected_keywords = {"quick", "brown", "fox", "jumps", "lazy", "dog"}
        self.assertEqual(keywords, expected_keywords)
        self.assertNotIn("the", keywords)
        self.assertNotIn("over", keywords)

    def test_extract_keywords_empty_string(self):
        """Test that empty string returns empty set."""
        keywords = self.deduplicator.extract_keywords("")
        self.assertEqual(keywords, set())

    def test_jaccard_similarity_identical(self):
        """Test that identical strings return similarity of 1.0."""
        goal1 = "implement user authentication"
        goal2 = "implement user authentication"
        similarity = self.deduplicator.jaccard_similarity(goal1, goal2)
        self.assertAlmostEqual(similarity, 1.0)

    def test_jaccard_similarity_disjoint(self):
        """Test that completely different strings return similarity of 0.0."""
        goal1 = "implement user authentication"
        goal2 = "fix database connection timeout"
        similarity = self.deduplicator.jaccard_similarity(goal1, goal2)
        self.assertAlmostEqual(similarity, 0.0)

    def test_jaccard_similarity_partial_overlap(self):
        """Test that partially overlapping strings return similarity of 0.5."""
        goal1 = "implement user authentication"
        goal2 = "implement user authorization"
        similarity = self.deduplicator.jaccard_similarity(goal1, goal2)
        self.assertAlmostEqual(similarity, 0.5)

    def test_deduplicate_goals_near_identical(self):
        """Test that two near-identical goals merge correctly."""
        goal1 = {"id": "goal1", "description": "implement user authentication", "priority": 5}
        goal2 = {"id": "goal2", "description": "implement user authentication system", "priority": 3}
        self.deduplicator.pending_goals = [goal1, goal2]
        merged_goals = self.deduplicator.deduplicate_goals()
        self.assertEqual(len(merged_goals), 1)
        self.assertEqual(merged_goals[0]["priority"], 5)  # Higher priority preserved

    def test_pre_insertion_filter_similar_goal(self):
        """Test that a new goal similar to an existing one gets merged."""
        existing_goal = {"id": "existing", "description": "implement user authentication", "priority": 5}
        self.deduplicator.pending_goals = [existing_goal]
        new_goal = {"id": "new_goal", "description": "implement user authentication system", "priority": 3}
        result = self.deduplicator.pre_insertion_filter(new_goal)
        self.assertIsNone(result)
        self.assertEqual(len(self.deduplicator.pending_goals), 1)
        self.assertEqual(self.deduplicator.pending_goals[0]["priority"], 5)

    def test_pre_insertion_filter_different_goal(self):
        """Test that a completely different goal passes through."""
        existing_goal = {"id": "existing", "description": "implement user authentication", "priority": 5}
        self.deduplicator.pending_goals = [existing_goal]
        new_goal = {"id": "new_goal", "description": "fix database connection timeout", "priority": 3}
        result = self.deduplicator.pre_insertion_filter(new_goal)
        self.assertEqual(result, new_goal)
        self.assertEqual(len(self.deduplicator.pending_goals), 2)

    def test_batch_deduplicate_full_cleanup(self):
        """Test that batch_deduplicate processes the full list correctly."""
        goals = [
            {"id": "goal1", "description": "implement user authentication", "priority": 5},
            {"id": "goal2", "description": "implement user authentication system", "priority": 3},
            {"id": "goal3", "description": "fix database connection timeout", "priority": 2},
            {"id": "goal4", "description": "fix database connection", "priority": 4},
            {"id": "goal5", "description": "implement user auth", "priority": 1},
        ]
        self.deduplicator.pending_goals = goals
        cleaned_goals = self.deduplicator.batch_deduplicate()
        self.assertLess(len(cleaned_goals), len(goals))
        # Should have at least 2 groups: authentication-related and database-related
        self.assertGreaterEqual(len(cleaned_goals), 2)

    def test_merge_log_verify_logging(self):
        """Test that merge_log records merge operations correctly."""
        self.deduplicator.merge_log = []
        goal1 = {"id": "goal1", "description": "implement user authentication", "priority": 5}
        goal2 = {"id": "goal2", "description": "implement user authentication system", "priority": 3}
        self.deduplicator.pending_goals = [goal1, goal2]
        self.deduplicator.deduplicate_goals()
        self.assertEqual(len(self.deduplicator.merge_log), 1)
        log_entry = self.deduplicator.merge_log[0]
        self.assertIn("goal1", log_entry)
        self.assertIn("goal2", log_entry)
        self.assertIn("merged", log_entry.lower())

    def test_merge_log_empty_when_no_merges(self):
        """Test that merge_log remains empty when no merges occur."""
        self.deduplicator.merge_log = []
        goal1 = {"id": "goal1", "description": "implement user authentication", "priority": 5}
        goal2 = {"id": "goal2", "description": "fix database connection", "priority": 3}
        self.deduplicator.pending_goals = [goal1, goal2]
        self.deduplicator.deduplicate_goals()
        self.assertEqual(len(self.deduplicator.merge_log), 0)

if __name__ == '__main__':
    unittest.main()