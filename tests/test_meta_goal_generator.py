import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta
from src.meta_goal_generator import MetaGoalGenerator
from src.goal import Goal, GoalPriority

class TestMetaGoalGeneratorIntegration(unittest.TestCase):
    """Integration tests for MetaGoalGenerator with real Goal system."""

    def setUp(self):
        """Set up test fixtures."""
        self.generator = MetaGoalGenerator()
        self.radical_goals = []
        self.conservative_goals = []
        self.goal_history = []
        self.current_goals = []

    def _create_goal(self, name, priority=GoalPriority.NORMAL, is_radical=False):
        """Helper to create a Goal object."""
        goal = Goal(name=name, priority=priority)
        if is_radical:
            goal.tags.append('radical')
        return goal

    def _add_goal_history(self, success_rate, cycles_ago=0):
        """Add a historical goal entry with given success rate."""
        timestamp = datetime.now() - timedelta(hours=cycles_ago)
        self.goal_history.append({
            'timestamp': timestamp,
            'success_rate': success_rate,
            'goal_count': len(self.current_goals)
        })

    def test_disruptive_goal_injected_when_radical_goals_below_20_percent(self):
        """Test that a disruptive goal is injected when radical goals are below 20%."""
        # Setup: 1 radical goal out of 10 total (10%)
        self.radical_goals = [self._create_goal("Radical Goal 1", is_radical=True)]
        self.conservative_goals = [self._create_goal(f"Conservative Goal {i}") for i in range(9)]
        self.current_goals = self.radical_goals + self.conservative_goals

        # Ensure no plateau in history
        self._add_goal_history(0.7, cycles_ago=6)
        self._add_goal_history(0.72, cycles_ago=5)
        self._add_goal_history(0.71, cycles_ago=4)
        self._add_goal_history(0.73, cycles_ago=3)
        self._add_goal_history(0.72, cycles_ago=2)
        self._add_goal_history(0.71, cycles_ago=1)

        # Act
        injected_goals = self.generator.evaluate_and_inject(
            radical_goals=self.radical_goals,
            conservative_goals=self.conservative_goals,
            goal_history=self.goal_history,
            current_goals=self.current_goals
        )

        # Assert
        self.assertEqual(len(injected_goals), 1, "Should inject exactly one disruptive goal")
        injected = injected_goals[0]
        self.assertTrue(injected.is_disruptive, "Injected goal should be disruptive")
        self.assertIn('disruptive', injected.tags, "Goal should have 'disruptive' tag")

    def test_disruptive_goal_injected_when_success_rate_plateaus(self):
        """Test that a disruptive goal is injected when success rate plateaus for 5+ cycles."""
        # Setup: Enough radical goals to avoid the <20% trigger
        self.radical_goals = [self._create_goal(f"Radical Goal {i}", is_radical=True) for i in range(3)]
        self.conservative_goals = [self._create_goal(f"Conservative Goal {i}") for i in range(7)]
        self.current_goals = self.radical_goals + self.conservative_goals

        # Simulate plateau: success rate around 0.65 for 6 cycles
        self._add_goal_history(0.65, cycles_ago=6)
        self._add_goal_history(0.64, cycles_ago=5)
        self._add_goal_history(0.66, cycles_ago=4)
        self._add_goal_history(0.65, cycles_ago=3)
        self._add_goal_history(0.63, cycles_ago=2)
        self._add_goal_history(0.65, cycles_ago=1)

        # Act
        injected_goals = self.generator.evaluate_and_inject(
            radical_goals=self.radical_goals,
            conservative_goals=self.conservative_goals,
            goal_history=self.goal_history,
            current_goals=self.current_goals
        )

        # Assert
        self.assertEqual(len(injected_goals), 1, "Should inject exactly one disruptive goal")
        injected = injected_goals[0]
        self.assertTrue(injected.is_disruptive, "Injected goal should be disruptive")

    def test_no_injection_when_conditions_not_met(self):
        """Test that no injection occurs when neither condition is triggered."""
        # Setup: 30% radical goals (above 20%)
        self.radical_goals = [self._create_goal(f"Radical Goal {i}", is_radical=True) for i in range(3)]
        self.conservative_goals = [self._create_goal(f"Conservative Goal {i}") for i in range(7)]
        self.current_goals = self.radical_goals + self.conservative_goals

        # No plateau: success rate varies significantly
        self._add_goal_history(0.5, cycles_ago=6)
        self._add_goal_history(0.6, cycles_ago=5)
        self._add_goal_history(0.7, cycles_ago=4)
        self._add_goal_history(0.65, cycles_ago=3)
        self._add_goal_history(0.75, cycles_ago=2)
        self._add_goal_history(0.8, cycles_ago=1)

        # Act
        injected_goals = self.generator.evaluate_and_inject(
            radical_goals=self.radical_goals,
            conservative_goals=self.conservative_goals,
            goal_history=self.goal_history,
            current_goals=self.current_goals
        )

        # Assert
        self.assertEqual(len(injected_goals), 0, "Should not inject any goals")

    def test_injected_goal_has_highest_priority(self):
        """Test that the injected disruptive goal has the highest priority."""
        # Setup: Trigger injection via low radical goals
        self.radical_goals = [self._create_goal("Radical Goal 1", is_radical=True)]
        self.conservative_goals = [self._create_goal(f"Conservative Goal {i}") for i in range(9)]
        self.current_goals = self.radical_goals + self.conservative_goals

        # Ensure plateau condition is not met
        self._add_goal_history(0.7, cycles_ago=6)
        self._add_goal_history(0.72, cycles_ago=5)
        self._add_goal_history(0.71, cycles_ago=4)
        self._add_goal_history(0.73, cycles_ago=3)
        self._add_goal_history(0.72, cycles_ago=2)
        self._add_goal_history(0.71, cycles_ago=1)

        # Act
        injected_goals = self.generator.evaluate_and_inject(
            radical_goals=self.radical_goals,
            conservative_goals=self.conservative_goals,
            goal_history=self.goal_history,
            current_goals=self.current_goals
        )

        # Assert
        self.assertEqual(len(injected_goals), 1)
        injected = injected_goals[0]
        self.assertEqual(injected.priority, GoalPriority.CRITICAL,
                         "Injected goal should have CRITICAL priority")
        # Verify it's higher than any existing goal
        for goal in self.current_goals:
            self.assertGreater(injected.priority.value, goal.priority.value,
                               f"Injected goal priority should be higher than {goal.name}")

    def test_curated_disruptive_actions_list_non_empty_and_diverse(self):
        """Test that the curated list of disruptive actions is non-empty and diverse."""
        # Access the curated actions list from the generator
        curated_actions = self.generator.curated_disruptive_actions

        # Assert non-empty
        self.assertGreater(len(curated_actions), 0, "Curated actions list should not be empty")

        # Assert diversity: at least 3 different action types/categories
        action_categories = set()
        for action in curated_actions:
            # Assuming each action has a 'category' attribute or similar
            if hasattr(action, 'category'):
                action_categories.add(action.category)
            elif hasattr(action, 'type'):
                action_categories.add(action.type)
            else:
                # Fallback: use first word of action name as category
                action_categories.add(action.name.split()[0] if hasattr(action, 'name') else str(action))

        self.assertGreaterEqual(len(action_categories), 3,
                                "Curated actions should have at least 3 different categories")

        # Verify each action has required fields
        for action in curated_actions:
            self.assertTrue(hasattr(action, 'name'), "Each action should have a name")
            self.assertTrue(hasattr(action, 'description'), "Each action should have a description")
            self.assertTrue(hasattr(action, 'expected_impact'), "Each action should have expected_impact")

    def test_injection_with_both_conditions_met_only_injects_once(self):
        """Test that when both conditions are met, only one disruptive goal is injected."""
        # Setup: Both low radical goals AND plateau
        self.radical_goals = [self._create_goal("Radical Goal 1", is_radical=True)]
        self.conservative_goals = [self._create_goal(f"Conservative Goal {i}") for i in range(9)]
        self.current_goals = self.radical_goals + self.conservative_goals

        # Plateau for 6 cycles
        self._add_goal_history(0.65, cycles_ago=6)
        self._add_goal_history(0.64, cycles_ago=5)
        self._add_goal_history(0.66, cycles_ago=4)
        self._add_goal_history(0.65, cycles_ago=3)
        self._add_goal_history(0.63, cycles_ago=2)
        self._add_goal_history(0.65, cycles_ago=1)

        # Act
        injected_goals = self.generator.evaluate_and_inject(
            radical_goals=self.radical_goals,
            conservative_goals=self.conservative_goals,
            goal_history=self.goal_history,
            current_goals=self.current_goals
        )

        # Assert: Only one injection despite two conditions
        self.assertEqual(len(injected_goals), 1, "Should inject exactly one goal even when both conditions met")
        injected = injected_goals[0]
        self.assertTrue(injected.is_disruptive, "Injected goal should be disruptive")

if __name__ == '__main__':
    unittest.main()