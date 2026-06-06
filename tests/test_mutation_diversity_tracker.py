import unittest
import sys
import os
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.mutation_diversity_tracker import MutationRecord, DiversityTracker


class TestMutationRecord(unittest.TestCase):
    """Test the MutationRecord class."""

    def setUp(self):
        self.feature_vector = np.array([0.5, 0.3, 0.8, 0.2])
        self.goal_type = "improve_performance"
        self.proposal_summary = "Optimize loop unrolling factor"
        self.record = MutationRecord(
            feature_vector=self.feature_vector,
            goal_type=self.goal_type,
            proposal_summary=self.proposal_summary
        )

    def test_initialization(self):
        """Test that MutationRecord is initialized correctly."""
        np.testing.assert_array_equal(self.record.feature_vector, self.feature_vector)
        self.assertEqual(self.record.goal_type, self.goal_type)
        self.assertEqual(self.record.proposal_summary, self.proposal_summary)
        self.assertIsNotNone(self.record.timestamp)

    def test_default_proposal_summary(self):
        """Test default proposal summary."""
        record = MutationRecord(feature_vector=self.feature_vector, goal_type=self.goal_type)
        self.assertEqual(record.proposal_summary, "")


class TestDiversityTracker(unittest.TestCase):
    """Test the DiversityTracker class."""

    def setUp(self):
        self.tracker = DiversityTracker(max_history=20)

    def test_identical_feature_vectors_return_high_similarity(self):
        """Test that identical feature vectors return similarity > 0.8."""
        vector = np.array([0.5, 0.3, 0.8, 0.2])
        record1 = MutationRecord(feature_vector=vector, goal_type="improve_performance")
        record2 = MutationRecord(feature_vector=vector, goal_type="improve_performance")
        similarity = self.tracker.compute_similarity(record1, record2)
        self.assertGreater(similarity, 0.8)

    def test_very_different_vectors_return_low_similarity(self):
        """Test that very different vectors return similarity < 0.3."""
        vector1 = np.array([0.0, 0.0, 0.0, 0.0])
        vector2 = np.array([1.0, 1.0, 1.0, 1.0])
        record1 = MutationRecord(feature_vector=vector1, goal_type="improve_performance")
        record2 = MutationRecord(feature_vector=vector2, goal_type="refactor_code")
        similarity = self.tracker.compute_similarity(record1, record2)
        self.assertLess(similarity, 0.3)

    def test_circular_buffer_maintains_last_20_records(self):
        """Test that circular buffer correctly maintains last 20 records."""
        for i in range(25):
            vector = np.random.rand(4)
            record = MutationRecord(
                feature_vector=vector,
                goal_type="test_goal",
                proposal_summary=f"Proposal {i}"
            )
            self.tracker.add_record(record)
        
        self.assertEqual(len(self.tracker.history), 20)
        self.assertEqual(self.tracker.history[-1].proposal_summary, "Proposal 24")
        self.assertEqual(self.tracker.history[0].proposal_summary, "Proposal 5")

    def test_inject_noise_produces_different_vectors(self):
        """Test that inject_noise() produces different vectors."""
        original_vector = np.array([0.5, 0.3, 0.8, 0.2])
        noise_level = 0.1
        noisy_vector = self.tracker.inject_noise(original_vector, noise_level)
        
        # Vectors should be different
        self.assertFalse(np.array_equal(original_vector, noisy_vector))
        
        # Noisy vector should be close to original (within noise level bounds)
        difference = np.abs(original_vector - noisy_vector)
        self.assertTrue(np.all(difference <= noise_level + 1e-10))  # Allow small floating point errors

    def test_force_goal_type_change_actually_changes_goal_type(self):
        """Test that force_goal_type_change() actually changes goal type."""
        original_goal = "improve_performance"
        record = MutationRecord(
            feature_vector=np.array([0.5, 0.3, 0.8, 0.2]),
            goal_type=original_goal
        )
        
        changed_record = self.tracker.force_goal_type_change(record)
        self.assertNotEqual(changed_record.goal_type, original_goal)
        
        # Verify the changed goal type is one of the valid alternatives
        valid_goals = [
            "refactor_code", "add_feature", "fix_bug",
            "improve_readability", "optimize_memory", "enhance_security"
        ]
        self.assertIn(changed_record.goal_type, valid_goals)

    def test_repeated_similar_proposals_get_blocked(self):
        """Integration test showing that repeated similar proposals get blocked."""
        base_vector = np.array([0.5, 0.3, 0.8, 0.2])
        
        # Add several similar records
        for i in range(5):
            vector = base_vector + np.random.normal(0, 0.05, size=4)
            vector = np.clip(vector, 0, 1)
            record = MutationRecord(
                feature_vector=vector,
                goal_type="improve_performance",
                proposal_summary=f"Similar proposal {i}"
            )
            self.tracker.add_record(record)
        
        # Try to add another very similar proposal
        new_vector = base_vector + np.random.normal(0, 0.02, size=4)
        new_vector = np.clip(new_vector, 0, 1)
        new_record = MutationRecord(
            feature_vector=new_vector,
            goal_type="improve_performance",
            proposal_summary="Another similar proposal"
        )
        
        # Check if it would be blocked
        is_blocked, reason = self.tracker.should_block(new_record, similarity_threshold=0.7)
        self.assertTrue(is_blocked)
        self.assertIn("similarity", reason.lower())

    def test_diverse_proposals_not_blocked(self):
        """Test that diverse proposals are not blocked."""
        # Add some records
        for i in range(3):
            vector = np.random.rand(4)
            record = MutationRecord(
                feature_vector=vector,
                goal_type="improve_performance",
                proposal_summary=f"Proposal {i}"
            )
            self.tracker.add_record(record)
        
        # Try to add a very different proposal
        new_vector = np.array([1.0, 0.0, 1.0, 0.0])
        new_record = MutationRecord(
            feature_vector=new_vector,
            goal_type="refactor_code",
            proposal_summary="Completely different proposal"
        )
        
        is_blocked, reason = self.tracker.should_block(new_record, similarity_threshold=0.7)
        self.assertFalse(is_blocked)

    def test_empty_history_does_not_block(self):
        """Test that empty history does not block any proposal."""
        record = MutationRecord(
            feature_vector=np.array([0.5, 0.3, 0.8, 0.2]),
            goal_type="improve_performance"
        )
        
        is_blocked, reason = self.tracker.should_block(record)
        self.assertFalse(is_blocked)

    def test_get_statistics(self):
        """Test that get_statistics returns correct information."""
        # Add some records with different goal types
        goal_types = ["improve_performance", "refactor_code", "fix_bug"]
        for i, goal in enumerate(goal_types):
            vector = np.random.rand(4)
            record = MutationRecord(
                feature_vector=vector,
                goal_type=goal,
                proposal_summary=f"Proposal {i}"
            )
            self.tracker.add_record(record)
        
        stats = self.tracker.get_statistics()
        self.assertEqual(stats["total_records"], 3)
        self.assertEqual(stats["max_history"], 20)
        self.assertIn("goal_type_distribution", stats)
        self.assertEqual(stats["goal_type_distribution"]["improve_performance"], 1)
        self.assertEqual(stats["goal_type_distribution"]["refactor_code"], 1)
        self.assertEqual(stats["goal_type_distribution"]["fix_bug"], 1)


if __name__ == '__main__':
    unittest.main()