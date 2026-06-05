import unittest
from unittest.mock import MagicMock, patch
import numpy as np

# Assuming the module is named 'meta_parameter_evolution'
# Adjust import path as needed
from meta_parameter_evolution import (
    FitnessTracker,
    HillClimber,
    ParameterBounds,
    TriggerController
)

class TestMetaParameterEvolution(unittest.TestCase):
    """Test suite for meta-parameter evolution system."""

    def setUp(self):
        """Set up test fixtures."""
        self.tracker = FitnessTracker(max_entries=20)
        self.climber = HillClimber(step_size=0.1)
        self.bounds = ParameterBounds(low=0.0, high=1.0)
        self.trigger = TriggerController(interval=10)

    def generate_synthetic_fitness_data(self, generations=30, trend='improving'):
        """
        Generate synthetic fitness data for testing.
        
        Args:
            generations: Number of generations to simulate
            trend: 'improving', 'degrading', or 'random'
        
        Returns:
            List of fitness values
        """
        np.random.seed(42)  # For reproducibility
        fitness_values = []
        
        if trend == 'improving':
            base = 0.3
            for i in range(generations):
                noise = np.random.normal(0, 0.05)
                fitness = base + (i * 0.02) + noise
                fitness_values.append(max(0.0, min(1.0, fitness)))
        elif trend == 'degrading':
            base = 0.8
            for i in range(generations):
                noise = np.random.normal(0, 0.05)
                fitness = base - (i * 0.02) + noise
                fitness_values.append(max(0.0, min(1.0, fitness)))
        else:  # random
            for i in range(generations):
                fitness = np.random.uniform(0.2, 0.8)
                fitness_values.append(fitness)
        
        return fitness_values

    def test_tracker_stores_last_20_entries(self):
        """
        Test that FitnessTracker correctly stores only the last 20 entries
        when more than 20 generations of data are provided.
        """
        # Generate 30 generations of synthetic data
        fitness_data = self.generate_synthetic_fitness_data(30)
        
        # Feed data into tracker
        for i, fitness in enumerate(fitness_data):
            self.tracker.add_entry(generation=i, fitness=fitness)
        
        # Verify tracker has exactly 20 entries
        self.assertEqual(len(self.tracker.get_all_entries()), 20,
                         "Tracker should store exactly 20 entries")
        
        # Verify the entries are the last 20 (generations 10-29)
        entries = self.tracker.get_all_entries()
        expected_generations = list(range(10, 30))
        actual_generations = [entry['generation'] for entry in entries]
        self.assertEqual(actual_generations, expected_generations,
                         "Tracker should store generations 10-29")
        
        # Verify fitness values match
        expected_fitness = fitness_data[10:]
        actual_fitness = [entry['fitness'] for entry in entries]
        for expected, actual in zip(expected_fitness, actual_fitness):
            self.assertAlmostEqual(expected, actual, places=5,
                                   msg="Fitness values should match")

    def test_hill_climbing_adjusts_parameters_correctly(self):
        """
        Test that hill-climbing adjusts parameters in the correct direction
        based on fitness trend.
        """
        # Test with improving trend - should increase parameter
        improving_data = self.generate_synthetic_fitness_data(30, 'improving')
        current_param = 0.5
        
        # Feed data and check parameter adjustment
        for i, fitness in enumerate(improving_data):
            self.tracker.add_entry(generation=i, fitness=fitness)
        
        # Get trend from tracker
        trend = self.tracker.get_trend()
        
        # Adjust parameter based on trend
        adjusted_param = self.climber.adjust_parameter(
            current_param, trend, self.bounds
        )
        
        # For improving trend, parameter should increase
        self.assertGreater(adjusted_param, current_param,
                           "Parameter should increase for improving trend")
        
        # Test with degrading trend - should decrease parameter
        degrading_data = self.generate_synthetic_fitness_data(30, 'degrading')
        current_param = 0.5
        
        # Reset tracker
        self.tracker = FitnessTracker(max_entries=20)
        
        for i, fitness in enumerate(degrading_data):
            self.tracker.add_entry(generation=i, fitness=fitness)
        
        trend = self.tracker.get_trend()
        adjusted_param = self.climber.adjust_parameter(
            current_param, trend, self.bounds
        )
        
        # For degrading trend, parameter should decrease
        self.assertLess(adjusted_param, current_param,
                        "Parameter should decrease for degrading trend")
        
        # Test with random trend - parameter should stay relatively stable
        random_data = self.generate_synthetic_fitness_data(30, 'random')
        current_param = 0.5
        
        self.tracker = FitnessTracker(max_entries=20)
        
        for i, fitness in enumerate(random_data):
            self.tracker.add_entry(generation=i, fitness=fitness)
        
        trend = self.tracker.get_trend()
        adjusted_param = self.climber.adjust_parameter(
            current_param, trend, self.bounds
        )
        
        # For random trend, adjustment should be minimal
        adjustment = abs(adjusted_param - current_param)
        self.assertLess(adjustment, 0.15,
                        "Parameter should have minimal adjustment for random trend")

    def test_trigger_fires_every_10_cycles(self):
        """
        Test that the trigger only fires every 10 cycles as configured.
        """
        # Test for 30 generations
        for generation in range(30):
            should_fire = self.trigger.check_and_update(generation)
            
            # Trigger should fire at generations 0, 10, 20
            if generation % 10 == 0:
                self.assertTrue(should_fire,
                                f"Trigger should fire at generation {generation}")
            else:
                self.assertFalse(should_fire,
                                 f"Trigger should not fire at generation {generation}")
        
        # Verify trigger count
        self.assertEqual(self.trigger.get_fire_count(), 3,
                         "Trigger should have fired exactly 3 times in 30 generations")

    def test_parameters_stay_within_bounds(self):
        """
        Test that parameters always stay within defined bounds during
        hill-climbing adjustments.
        """
        # Create bounds with specific range
        bounds = ParameterBounds(low=0.1, high=0.9)
        
        # Test with extreme adjustments
        test_cases = [
            (0.05, 'improving'),   # Below lower bound
            (0.95, 'degrading'),   # Above upper bound
            (0.5, 'improving'),    # Within bounds, improving
            (0.5, 'degrading'),    # Within bounds, degrading
        ]
        
        for current_param, trend in test_cases:
            # Generate appropriate synthetic data
            if trend == 'improving':
                fitness_data = self.generate_synthetic_fitness_data(30, 'improving')
            else:
                fitness_data = self.generate_synthetic_fitness_data(30, 'degrading')
            
            # Reset tracker and feed data
            self.tracker = FitnessTracker(max_entries=20)
            for i, fitness in enumerate(fitness_data):
                self.tracker.add_entry(generation=i, fitness=fitness)
            
            trend_value = self.tracker.get_trend()
            adjusted_param = self.climber.adjust_parameter(
                current_param, trend_value, bounds
            )
            
            # Verify parameter stays within bounds
            self.assertGreaterEqual(adjusted_param, bounds.low,
                                    f"Parameter {adjusted_param} should be >= {bounds.low}")
            self.assertLessEqual(adjusted_param, bounds.high,
                                 f"Parameter {adjusted_param} should be <= {bounds.high}")
        
        # Test multiple iterations to ensure bounds are maintained over time
        current_param = 0.5
        for _ in range(50):
            fitness_data = self.generate_synthetic_fitness_data(5, 'improving')
            self.tracker = FitnessTracker(max_entries=20)
            for i, fitness in enumerate(fitness_data):
                self.tracker.add_entry(generation=i, fitness=fitness)
            
            trend = self.tracker.get_trend()
            current_param = self.climber.adjust_parameter(
                current_param, trend, bounds
            )
            
            self.assertGreaterEqual(current_param, bounds.low,
                                    f"Parameter should not go below {bounds.low}")
            self.assertLessEqual(current_param, bounds.high,
                                 f"Parameter should not exceed {bounds.high}")

    def test_integration_full_evolution_cycle(self):
        """
        Integration test that simulates a full evolution cycle with
        30 generations, verifying all components work together.
        """
        # Initialize all components
        tracker = FitnessTracker(max_entries=20)
        climber = HillClimber(step_size=0.1)
        bounds = ParameterBounds(low=0.0, high=1.0)
        trigger = TriggerController(interval=10)
        
        # Generate synthetic fitness data
        fitness_data = self.generate_synthetic_fitness_data(30, 'improving')
        
        # Track parameter evolution
        current_param = 0.5
        trigger_fire_generations = []
        
        for generation in range(30):
            # Add fitness data to tracker
            tracker.add_entry(generation=generation, 
                            fitness=fitness_data[generation])
            
            # Check if trigger should fire
            if trigger.check_and_update(generation):
                trigger_fire_generations.append(generation)
                
                # Get trend and adjust parameter
                if len(tracker.get_all_entries()) >= 2:
                    trend = tracker.get_trend()
                    current_param = climber.adjust_parameter(
                        current_param, trend, bounds
                    )
        
        # Verify trigger fired at correct generations
        self.assertEqual(trigger_fire_generations, [0, 10, 20],
                         "Trigger should fire at generations 0, 10, 20")
        
        # Verify tracker has correct number of entries
        self.assertEqual(len(tracker.get_all_entries()), 20,
                         "Tracker should have 20 entries")
        
        # Verify parameter has evolved (improving trend should increase it)
        self.assertGreater(current_param, 0.5,
                           "Parameter should have increased due to improving trend")
        
        # Verify parameter is within bounds
        self.assertGreaterEqual(current_param, bounds.low)
        self.assertLessEqual(current_param, bounds.high)

    def test_tracker_edge_cases(self):
        """
        Test edge cases for the fitness tracker.
        """
        # Test with empty tracker
        self.assertEqual(len(self.tracker.get_all_entries()), 0,
                         "Empty tracker should have 0 entries")
        
        # Test with single entry
        self.tracker.add_entry(generation=0, fitness=0.5)
        self.assertEqual(len(self.tracker.get_all_entries()), 1,
                         "Tracker should have 1 entry after adding one")
        
        # Test with exactly 20 entries
        for i in range(1, 20):
            self.tracker.add_entry(generation=i, fitness=0.5 + i*0.01)
        self.assertEqual(len(self.tracker.get_all_entries()), 20,
                         "Tracker should have exactly 20 entries")
        
        # Test trend calculation with insufficient data
        self.tracker = FitnessTracker(max_entries=20)
        self.tracker.add_entry(generation=0, fitness=0.5)
        trend = self.tracker.get_trend()
        self.assertEqual(trend, 0.0,
                         "Trend should be 0 with insufficient data")


if __name__ == '__main__':
    unittest.main()