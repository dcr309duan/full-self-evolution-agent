import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
from your_module import GoalRegistry, TriageRoutine, KnowledgeBase  # Replace with actual imports

@pytest.fixture
def goal_registry():
    """Fixture to create a fresh GoalRegistry instance."""
    return GoalRegistry()

@pytest.fixture
def knowledge_base():
    """Fixture to create a fresh KnowledgeBase instance."""
    return KnowledgeBase()

@pytest.fixture
def triage_routine(goal_registry, knowledge_base):
    """Fixture to create a TriageRoutine instance with dependencies."""
    return TriageRoutine(goal_registry, knowledge_base)

def seed_goals(goal_registry):
    """Seed the goal registry with 5 goals of varying staleness."""
    now = datetime.now()
    goals_data = [
        {
            "id": "goal_1",
            "name": "Active Goal",
            "last_progress": now - timedelta(days=1),
            "generations_no_progress": 0,
            "archived": False,
            "decomposed": False,
            "parent_id": None
        },
        {
            "id": "goal_2",
            "name": "Stale Goal 1",
            "last_progress": now - timedelta(days=30),
            "generations_no_progress": 2,
            "archived": False,
            "decomposed": False,
            "parent_id": None
        },
        {
            "id": "goal_3",
            "name": "Stale Goal 2 (Flagged)",
            "last_progress": now - timedelta(days=60),
            "generations_no_progress": 3,
            "archived": False,
            "decomposed": False,
            "parent_id": None
        },
        {
            "id": "goal_4",
            "name": "Archived Goal",
            "last_progress": now - timedelta(days=90),
            "generations_no_progress": 5,
            "archived": True,
            "decomposed": False,
            "parent_id": None
        },
        {
            "id": "goal_5",
            "name": "Decomposed Goal",
            "last_progress": now - timedelta(days=10),
            "generations_no_progress": 1,
            "archived": False,
            "decomposed": True,
            "parent_id": "goal_1"
        }
    ]
    for goal_data in goals_data:
        goal_registry.add_goal(goal_data)

class TestGoalTriageIntegration:
    """Integration tests for the goal triage system."""

    def test_triage_flags_stale_goals(self, goal_registry, triage_routine):
        """Test that only goals with 3+ generations of no progress are flagged."""
        seed_goals(goal_registry)
        flagged_goals = triage_routine.run()
        
        # Verify only goal_3 is flagged (3 generations no progress)
        flagged_ids = [goal["id"] for goal in flagged_goals]
        assert "goal_3" in flagged_ids
        assert "goal_1" not in flagged_ids
        assert "goal_2" not in flagged_ids
        assert "goal_4" not in flagged_ids  # Archived, not flagged
        assert "goal_5" not in flagged_ids

    def test_archived_goals_have_lessons(self, goal_registry, knowledge_base, triage_routine):
        """Test that archived goals have lessons recorded in the knowledge base."""
        seed_goals(goal_registry)
        triage_routine.run()
        
        # Check that lessons for goal_4 (archived) exist in knowledge base
        lessons = knowledge_base.get_lessons_for_goal("goal_4")
        assert lessons is not None
        assert len(lessons) > 0
        # Verify lesson content includes relevant information
        assert any("archived" in lesson.lower() for lesson in lessons)

    def test_decomposed_goals_appear_as_subgoals(self, goal_registry, triage_routine):
        """Test that decomposed goals appear as sub-goals in the registry."""
        seed_goals(goal_registry)
        triage_routine.run()
        
        # Verify goal_5 is a sub-goal of goal_1
        parent_goal = goal_registry.get_goal("goal_1")
        sub_goals = goal_registry.get_sub_goals("goal_1")
        assert "goal_5" in sub_goals
        assert parent_goal["decomposed"] is True or parent_goal["name"] == "Active Goal"

    def test_triage_does_not_flag_active_goals(self, goal_registry, triage_routine):
        """Test that active goals (0 generations no progress) are not flagged."""
        seed_goals(goal_registry)
        flagged_goals = triage_routine.run()
        flagged_ids = [goal["id"] for goal in flagged_goals]
        assert "goal_1" not in flagged_ids

    def test_triage_handles_mixed_staleness(self, goal_registry, triage_routine):
        """Test that triage correctly handles goals with varying staleness levels."""
        seed_goals(goal_registry)
        flagged_goals = triage_routine.run()
        
        # Verify only goal_3 is flagged (exactly 3 generations)
        assert len(flagged_goals) == 1
        assert flagged_goals[0]["id"] == "goal_3"

    def test_archived_goals_not_flagged_but_lessons_recorded(self, goal_registry, knowledge_base, triage_routine):
        """Test that archived goals are not flagged but have lessons recorded."""
        seed_goals(goal_registry)
        flagged_goals = triage_routine.run()
        flagged_ids = [goal["id"] for goal in flagged_goals]
        
        # goal_4 is archived but has 5 generations no progress - should not be flagged
        assert "goal_4" not in flagged_ids
        
        # But lessons should still be recorded
        lessons = knowledge_base.get_lessons_for_goal("goal_4")
        assert len(lessons) > 0

    def test_decomposed_goals_maintain_hierarchy(self, goal_registry, triage_routine):
        """Test that decomposed goals maintain proper parent-child relationships."""
        seed_goals(goal_registry)
        triage_routine.run()
        
        # Verify goal_5's parent is goal_1
        sub_goal = goal_registry.get_goal("goal_5")
        assert sub_goal["parent_id"] == "goal_1"
        
        # Verify goal_1 has goal_5 as a sub-goal
        sub_goals = goal_registry.get_sub_goals("goal_1")
        assert "goal_5" in sub_goals

    def test_triage_does_not_duplicate_lessons(self, goal_registry, knowledge_base, triage_routine):
        """Test that running triage multiple times doesn't duplicate lessons."""
        seed_goals(goal_registry)
        
        # Run triage twice
        triage_routine.run()
        first_lessons = knowledge_base.get_lessons_for_goal("goal_4")
        
        triage_routine.run()
        second_lessons = knowledge_base.get_lessons_for_goal("goal_4")
        
        # Verify no duplication
        assert len(first_lessons) == len(second_lessons)