import unittest
from unittest.mock import MagicMock, patch
import json
from datetime import datetime, timedelta

# Assuming these are the modules we're testing
from goal_generator import GoalGenerator, KnowledgeBaseEntry, Goal, PriorityScorer
from orchestrator import Orchestrator

class TestGoalGenerator(unittest.TestCase):
    """Comprehensive test suite for the Goal Generator system."""
    
    def setUp(self):
        """Set up test fixtures before each test."""
        self.goal_generator = GoalGenerator()
        self.orchestrator = Orchestrator()
        
        # Sample knowledge base entries for testing
        self.sample_entries = [
            KnowledgeBaseEntry(
                id="KB001",
                content="User reported login issues on mobile app version 2.1",
                source="bug_report",
                timestamp=datetime.now() - timedelta(hours=2),
                metadata={"priority": "high", "component": "authentication"}
            ),
            KnowledgeBaseEntry(
                id="KB002",
                content="Server response time increased by 30% in last hour",
                source="monitoring",
                timestamp=datetime.now() - timedelta(minutes=30),
                metadata={"metric": "response_time", "threshold": "critical"}
            ),
            KnowledgeBaseEntry(
                id="KB003",
                content="New feature request for dark mode implementation",
                source="user_feedback",
                timestamp=datetime.now() - timedelta(days=1),
                metadata={"votes": 150, "status": "under_review"}
            ),
            KnowledgeBaseEntry(
                id="KB004",
                content="Database connection pool exhaustion detected",
                source="alert",
                timestamp=datetime.now() - timedelta(minutes=5),
                metadata={"severity": "critical", "affected_services": ["api", "web"]}
            )
        ]
        
        # Duplicate entries for testing
        self.duplicate_entries = [
            KnowledgeBaseEntry(
                id="KB005",
                content="User reported login issues on mobile app version 2.1",
                source="bug_report",
                timestamp=datetime.now() - timedelta(hours=1),
                metadata={"priority": "high", "component": "authentication"}
            ),
            KnowledgeBaseEntry(
                id="KB006",
                content="User reported login issues on mobile app version 2.1",
                source="bug_report",
                timestamp=datetime.now() - timedelta(minutes=45),
                metadata={"priority": "high", "component": "authentication"}
            )
        ]

    # Test 1: Correct parsing of knowledge base entries
    def test_parse_knowledge_base_entry(self):
        """Test that knowledge base entries are correctly parsed."""
        entry_data = {
            "id": "KB001",
            "content": "User reported login issues on mobile app version 2.1",
            "source": "bug_report",
            "timestamp": datetime.now().isoformat(),
            "metadata": {"priority": "high", "component": "authentication"}
        }
        
        parsed_entry = self.goal_generator.parse_entry(entry_data)
        
        self.assertIsInstance(parsed_entry, KnowledgeBaseEntry)
        self.assertEqual(parsed_entry.id, "KB001")
        self.assertEqual(parsed_entry.source, "bug_report")
        self.assertIn("login", parsed_entry.content.lower())
        self.assertIn("priority", parsed_entry.metadata)
        self.assertEqual(parsed_entry.metadata["priority"], "high")

    def test_parse_entry_with_missing_fields(self):
        """Test parsing entries with missing optional fields."""
        incomplete_data = {
            "id": "KB007",
            "content": "Test entry without metadata"
        }
        
        parsed_entry = self.goal_generator.parse_entry(incomplete_data)
        
        self.assertIsNotNone(parsed_entry)
        self.assertEqual(parsed_entry.metadata, {})

    def test_parse_entry_with_invalid_data(self):
        """Test parsing with invalid data raises appropriate error."""
        with self.assertRaises(ValueError):
            self.goal_generator.parse_entry({"invalid": "data"})

    # Test 2: Priority scoring produces consistent ordering
    def test_priority_scoring_consistency(self):
        """Test that priority scoring produces consistent results."""
        scorer = PriorityScorer()
        
        # Score the same entries multiple times
        first_scores = [scorer.score(entry) for entry in self.sample_entries]
        second_scores = [scorer.score(entry) for entry in self.sample_entries]
        
        # Scores should be identical for the same entries
        self.assertEqual(first_scores, second_scores)

    def test_priority_scoring_ordering(self):
        """Test that priority scoring produces correct ordering."""
        scorer = PriorityScorer()
        
        # Critical severity should score higher than high priority
        critical_entry = self.sample_entries[3]  # Database connection pool exhaustion
        high_priority_entry = self.sample_entries[0]  # Login issues
        
        critical_score = scorer.score(critical_entry)
        high_score = scorer.score(high_priority_entry)
        
        self.assertGreater(critical_score, high_score,
                          "Critical severity should score higher than high priority")

    def test_priority_scoring_time_decay(self):
        """Test that older entries receive lower priority scores."""
        scorer = PriorityScorer()
        
        # Recent entry should score higher than older entry with same content
        recent_entry = KnowledgeBaseEntry(
            id="KB008",
            content="Test entry",
            source="test",
            timestamp=datetime.now(),
            metadata={}
        )
        old_entry = KnowledgeBaseEntry(
            id="KB009",
            content="Test entry",
            source="test",
            timestamp=datetime.now() - timedelta(days=7),
            metadata={}
        )
        
        recent_score = scorer.score(recent_entry)
        old_score = scorer.score(old_entry)
        
        self.assertGreater(recent_score, old_score,
                          "Recent entries should score higher than older ones")

    # Test 3: Generated goals reference actual evidence from knowledge base
    def test_generated_goals_reference_evidence(self):
        """Test that generated goals contain references to knowledge base entries."""
        goals = self.goal_generator.generate_goals(self.sample_entries)
        
        for goal in goals:
            self.assertIsInstance(goal, Goal)
            self.assertTrue(goal.evidence_ids,
                          f"Goal '{goal.description}' should reference evidence")
            
            # Verify each evidence ID exists in the sample entries
            for evidence_id in goal.evidence_ids:
                matching_entries = [e for e in self.sample_entries if e.id == evidence_id]
                self.assertTrue(matching_entries,
                              f"Evidence ID {evidence_id} should exist in knowledge base")

    def test_goal_content_based_on_evidence(self):
        """Test that goal content is derived from actual evidence."""
        goals = self.goal_generator.generate_goals(self.sample_entries)
        
        # Check that goals reference actual content from entries
        for goal in goals:
            for evidence_id in goal.evidence_ids:
                entry = next(e for e in self.sample_entries if e.id == evidence_id)
                # Goal description should contain key terms from the evidence
                key_terms = entry.content.split()[:3]  # First 3 words
                has_reference = any(term.lower() in goal.description.lower() 
                                  for term in key_terms)
                self.assertTrue(has_reference,
                              f"Goal should reference content from evidence {evidence_id}")

    # Test 4: Duplicate detection works
    def test_duplicate_detection_exact_match(self):
        """Test detection of exact duplicate entries."""
        duplicates = self.goal_generator.detect_duplicates(self.duplicate_entries)
        
        self.assertTrue(duplicates)
        self.assertIn("KB005", duplicates)
        self.assertIn("KB006", duplicates)

    def test_duplicate_detection_similar_content(self):
        """Test detection of similar (but not identical) entries."""
        similar_entries = [
            KnowledgeBaseEntry(
                id="KB010",
                content="User cannot login to mobile app version 2.1",
                source="bug_report",
                timestamp=datetime.now(),
                metadata={}
            ),
            KnowledgeBaseEntry(
                id="KB011",
                content="Login failure on mobile app version 2.1",
                source="bug_report",
                timestamp=datetime.now(),
                metadata={}
            )
        ]
        
        duplicates = self.goal_generator.detect_duplicates(similar_entries)
        
        self.assertTrue(duplicates,
                       "Similar content should be detected as potential duplicates")

    def test_duplicate_detection_no_false_positives(self):
        """Test that non-duplicate entries are not flagged."""
        unique_entries = [
            KnowledgeBaseEntry(id="KB012", content="Entry one", source="test", 
                             timestamp=datetime.now(), metadata={}),
            KnowledgeBaseEntry(id="KB013", content="Entry two", source="test",
                             timestamp=datetime.now(), metadata={})
        ]
        
        duplicates = self.goal_generator.detect_duplicates(unique_entries)
        
        self.assertFalse(duplicates,
                        "Different entries should not be flagged as duplicates")

    def test_duplicate_handling_in_goal_generation(self):
        """Test that duplicates are handled appropriately during goal generation."""
        # Generate goals with duplicates present
        all_entries = self.sample_entries + self.duplicate_entries
        goals = self.goal_generator.generate_goals(all_entries)
        
        # Should not create separate goals for duplicate entries
        login_goals = [g for g in goals if "login" in g.description.lower()]
        self.assertLessEqual(len(login_goals), 1,
                           "Duplicate entries should not create duplicate goals")

    # Test 5: Integration with orchestrator produces valid execution queue
    def test_integration_with_orchestrator(self):
        """Test that goals integrate properly with orchestrator."""
        # Generate goals
        goals = self.goal_generator.generate_goals(self.sample_entries)
        
        # Create execution queue
        execution_queue = self.orchestrator.create_execution_queue(goals)
        
        self.assertIsInstance(execution_queue, list)
        self.assertTrue(len(execution_queue) > 0,
                       "Execution queue should not be empty")

    def test_execution_queue_ordering(self):
        """Test that execution queue maintains proper ordering."""
        goals = self.goal_generator.generate_goals(self.sample_entries)
        execution_queue = self.orchestrator.create_execution_queue(goals)
        
        # Verify queue is ordered by priority
        for i in range(len(execution_queue) - 1):
            self.assertGreaterEqual(
                execution_queue[i].priority,
                execution_queue[i + 1].priority,
                "Execution queue should be ordered by priority (descending)"
            )

    def test_execution_queue_validity(self):
        """Test that each item in execution queue is valid."""
        goals = self.goal_generator.generate_goals(self.sample_entries)
        execution_queue = self.orchestrator.create_execution_queue(goals)
        
        for item in execution_queue:
            # Each item should have required fields
            self.assertTrue(hasattr(item, 'id'))
            self.assertTrue(hasattr(item, 'action'))
            self.assertTrue(hasattr(item, 'priority'))
            self.assertTrue(hasattr(item, 'dependencies'))
            
            # Dependencies should reference valid items
            for dep in item.dependencies:
                dep_ids = [q.id for q in execution_queue]
                self.assertIn(dep, dep_ids,
                            f"Dependency {dep} should exist in execution queue")

    def test_orchestrator_handles_empty_goals(self):
        """Test orchestrator behavior with no goals."""
        empty_queue = self.orchestrator.create_execution_queue([])
        
        self.assertEqual(empty_queue, [],
                        "Empty goals should produce empty execution queue")

    def test_full_integration_flow(self):
        """Test the complete flow from knowledge base to execution queue."""
        # Simulate knowledge base input
        kb_input = [
            {
                "id": "KB100",
                "content": "Critical security vulnerability found in authentication module",
                "source": "security_scan",
                "timestamp": datetime.now().isoformat(),
                "metadata": {"severity": "critical", "cve": "CVE-2024-1234"}
            },
            {
                "id": "KB101",
                "content": "Performance degradation in database queries",
                "source": "monitoring",
                "timestamp": datetime.now().isoformat(),
                "metadata": {"impact": "high", "queries_affected": 50}
            }
        ]
        
        # Parse entries
        parsed_entries = [self.goal_generator.parse_entry(entry) for entry in kb_input]
        
        # Generate goals
        goals = self.goal_generator.generate_goals(parsed_entries)
        
        # Create execution queue
        execution_queue = self.orchestrator.create_execution_queue(goals)
        
        # Verify complete flow
        self.assertEqual(len(goals), len(execution_queue))
        self.assertTrue(all(hasattr(goal, 'evidence_ids') for goal in goals))
        self.assertTrue(all(hasattr(item, 'action') for item in execution_queue))
        
        # Verify evidence references are maintained
        for goal in goals:
            for evidence_id in goal.evidence_ids:
                matching_entries = [e for e in parsed_entries if e.id == evidence_id]
                self.assertTrue(matching_entries,
                              f"Evidence {evidence_id} should be traceable back to input")

    def test_performance_with_large_input(self):
        """Test performance with a large number of knowledge base entries."""
        # Generate 1000 sample entries
        large_entries = []
        for i in range(1000):
            entry = KnowledgeBaseEntry(
                id=f"KB{i:04d}",
                content=f"Test entry number {i} for performance testing",
                source="test",
                timestamp=datetime.now(),
                metadata={"index": i}
            )
            large_entries.append(entry)
        
        # Time the goal generation
        import time
        start_time = time.time()
        goals = self.goal_generator.generate_goals(large_entries)
        end_time = time.time()
        
        generation_time = end_time - start_time
        
        # Should complete within reasonable time (adjust threshold as needed)
        self.assertLess(generation_time, 5.0,
                       f"Goal generation took {generation_time:.2f}s, expected < 5s")
        self.assertEqual(len(goals), 1000,
                        "Should generate one goal per entry")

if __name__ == '__main__':
    unittest.main()