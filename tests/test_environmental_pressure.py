import unittest
from unittest.mock import patch, MagicMock
from core.environmental_pressure import introduce_environmental_pressure, PressureRegistry, get_pressure_registry
from core.goal_generator import GoalGenerator

class TestEnvironmentalPressure(unittest.TestCase):
    """Unit tests for the environmental pressure module."""

    def setUp(self):
        """Set up test fixtures."""
        self.goal_generator = GoalGenerator()
        self.ecology_engine = MagicMock()
        self.ecology_engine.cycle_count = 0

    @patch('core.environmental_pressure.get_cycle_count')
    def test_introduce_pressure_adds_goal(self, mock_get_cycle_count):
        """Test that introducing pressure adds a new goal to the goal generator."""
        # Arrange: simulate cycle 10 (pressure trigger)
        mock_get_cycle_count.return_value = 10

        # Act
        introduce_environmental_pressure(self.ecology_engine, self.goal_generator)

        # Assert
        goals = self.goal_generator.get_active_goals()
        self.assertGreater(len(goals), 0, "No goal was added after introducing pressure")

    @patch('core.environmental_pressure.get_cycle_count')
    def test_introduced_goal_is_valid(self, mock_get_cycle_count):
        """Test that the introduced goal has required fields and is actionable."""
        # Arrange
        mock_get_cycle_count.return_value = 10

        # Act
        introduce_environmental_pressure(self.ecology_engine, self.goal_generator)

        # Assert
        goals = self.goal_generator.get_active_goals()
        goal = goals[-1]  # Get the most recently added goal

        # Check required fields
        self.assertIn('type', goal, "Goal missing 'type' field")
        self.assertIn('description', goal, "Goal missing 'description' field")
        self.assertIn('priority', goal, "Goal missing 'priority' field")
        self.assertIn('actionable', goal, "Goal missing 'actionable' field")

        # Check goal is actionable
        self.assertTrue(goal['actionable'], "Goal is not marked as actionable")

        # Check goal type is appropriate for pressure
        self.assertEqual(goal['type'], 'adapt_to_pressure', 
                         f"Expected goal type 'adapt_to_pressure', got '{goal['type']}'")

    @patch('core.environmental_pressure.get_cycle_count')
    def test_no_pressure_before_cycle_10(self, mock_get_cycle_count):
        """Test that no pressure is introduced before cycle 10."""
        # Arrange
        mock_get_cycle_count.return_value = 5

        # Act
        introduce_environmental_pressure(self.ecology_engine, self.goal_generator)

        # Assert
        goals = self.goal_generator.get_active_goals()
        self.assertEqual(len(goals), 0, "Goal was incorrectly added before cycle 10")

    @patch('core.environmental_pressure.get_cycle_count')
    def test_pressure_every_10_cycles(self, mock_get_cycle_count):
        """Test that pressure is introduced every 10 cycles."""
        # Arrange
        mock_get_cycle_count.return_value = 20

        # Act
        introduce_environmental_pressure(self.ecology_engine, self.goal_generator)

        # Assert
        goals = self.goal_generator.get_active_goals()
        self.assertGreater(len(goals), 0, "No goal added at cycle 20")

    @patch('core.environmental_pressure.get_cycle_count')
    def test_goal_description_is_meaningful(self, mock_get_cycle_count):
        """Test that the goal description provides useful context."""
        # Arrange
        mock_get_cycle_count.return_value = 10

        # Act
        introduce_environmental_pressure(self.ecology_engine, self.goal_generator)

        # Assert
        goals = self.goal_generator.get_active_goals()
        goal = goals[-1]
        description = goal['description']
        self.assertIsInstance(description, str)
        self.assertGreater(len(description), 10, "Goal description is too short")
        self.assertIn('pressure', description.lower(), 
                      "Goal description should mention 'pressure'")

    def test_pressure_generation_logic(self):
        """Test that pressure generation logic produces valid pressure objects."""
        # Arrange
        pressure = PressureRegistry.generate_pressure('test_pressure', 'Test pressure description', 5)

        # Assert
        self.assertIsNotNone(pressure)
        self.assertIn('id', pressure)
        self.assertIn('name', pressure)
        self.assertIn('description', pressure)
        self.assertIn('severity', pressure)
        self.assertEqual(pressure['name'], 'test_pressure')
        self.assertEqual(pressure['description'], 'Test pressure description')
        self.assertEqual(pressure['severity'], 5)

    def test_generated_pressures_are_importable(self):
        """Test that generated pressures can be imported and used."""
        # Arrange
        from core.environmental_pressure import PRESSURE_TYPES, get_pressure_types

        # Act
        pressure_types = get_pressure_types()

        # Assert
        self.assertIsNotNone(pressure_types)
        self.assertIsInstance(pressure_types, list)
        self.assertGreater(len(pressure_types), 0)
        for pressure_type in pressure_types:
            self.assertIn('name', pressure_type)
            self.assertIn('description', pressure_type)

    def test_pressure_registry_works(self):
        """Test that the pressure registry correctly stores and retrieves pressures."""
        # Arrange
        registry = get_pressure_registry()
        initial_count = len(registry.get_all_pressures())

        # Act
        pressure = PressureRegistry.generate_pressure('test_registry_pressure', 'Test registry pressure', 3)
        registry.register_pressure(pressure)
        all_pressures = registry.get_all_pressures()

        # Assert
        self.assertEqual(len(all_pressures), initial_count + 1)
        self.assertIn(pressure, all_pressures)

        # Test retrieval by ID
        retrieved = registry.get_pressure_by_id(pressure['id'])
        self.assertEqual(retrieved, pressure)

        # Test clearing
        registry.clear_pressures()
        self.assertEqual(len(registry.get_all_pressures()), 0)

    def test_cycle_based_scheduling(self):
        """Test that pressure introduction follows cycle-based scheduling."""
        # Arrange
        from core.environmental_pressure import should_introduce_pressure

        # Act & Assert - Test various cycle counts
        self.assertFalse(should_introduce_pressure(0), "Should not introduce pressure at cycle 0")
        self.assertFalse(should_introduce_pressure(5), "Should not introduce pressure at cycle 5")
        self.assertTrue(should_introduce_pressure(10), "Should introduce pressure at cycle 10")
        self.assertFalse(should_introduce_pressure(15), "Should not introduce pressure at cycle 15")
        self.assertTrue(should_introduce_pressure(20), "Should introduce pressure at cycle 20")
        self.assertFalse(should_introduce_pressure(25), "Should not introduce pressure at cycle 25")
        self.assertTrue(should_introduce_pressure(30), "Should introduce pressure at cycle 30")

    def test_cycle_based_scheduling_with_ecology_engine(self):
        """Test cycle-based scheduling integrates with ecology engine."""
        # Arrange
        from core.environmental_pressure import get_cycle_count

        # Act - Simulate different cycle counts
        with patch('core.environmental_pressure.get_cycle_count') as mock_get_cycle_count:
            mock_get_cycle_count.return_value = 10
            self.assertTrue(should_introduce_pressure(10))

            mock_get_cycle_count.return_value = 20
            self.assertTrue(should_introduce_pressure(20))

            mock_get_cycle_count.return_value = 30
            self.assertTrue(should_introduce_pressure(30))

    def test_pressure_registry_singleton(self):
        """Test that pressure registry behaves as a singleton."""
        # Arrange
        registry1 = get_pressure_registry()
        registry2 = get_pressure_registry()

        # Assert
        self.assertIs(registry1, registry2, "Pressure registry should be a singleton")

    def test_pressure_generation_with_different_severities(self):
        """Test pressure generation with various severity levels."""
        # Arrange
        severities = [1, 3, 5, 7, 10]

        for severity in severities:
            with self.subTest(severity=severity):
                # Act
                pressure = PressureRegistry.generate_pressure(f'pressure_severity_{severity}', f'Test severity {severity}', severity)

                # Assert
                self.assertEqual(pressure['severity'], severity)
                self.assertGreaterEqual(pressure['severity'], 1)
                self.assertLessEqual(pressure['severity'], 10)

if __name__ == '__main__':
    unittest.main()