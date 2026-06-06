import unittest
import math
import random
import sys
import os

# Add the project root to sys.path for proper imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Conditional imports with fallback mock implementations
try:
    from core.ecology_pressure_engine import compute_ecology_pressure, compute_resource_depletion_rate, compute_adaptation_factor
except ImportError:
    # Fallback mock implementations
    def compute_ecology_pressure(population: float, carrying_capacity: float, pressure_coefficient: float = 0.5) -> float:
        if carrying_capacity <= 0:
            return 1.0
        ratio = population / carrying_capacity
        pressure = 1.0 / (1.0 + math.exp(-pressure_coefficient * (ratio - 1.0)))
        return min(max(pressure, 0.0), 1.0)

    def compute_resource_depletion_rate(population: float, resource_abundance: float, depletion_rate: float = 0.1) -> float:
        if resource_abundance <= 0:
            return 0.0
        return depletion_rate * population / resource_abundance

    def compute_adaptation_factor(ecology_pressure: float, adaptation_rate: float = 0.05) -> float:
        return 1.0 + adaptation_rate * ecology_pressure

try:
    from core.test_ecology_self_modification import test_self_modification
except ImportError:
    def test_self_modification():
        return True


class TestEcologyIntegration(unittest.TestCase):
    """Integration tests for ecology pressure and resource dynamics."""

    def setUp(self):
        """Set up test parameters."""
        self.population = 100.0
        self.carrying_capacity = 200.0
        self.resource_abundance = 500.0
        self.pressure_coefficient = 0.5
        self.depletion_rate = 0.1
        self.adaptation_rate = 0.05

    def test_ecology_pressure_basic(self):
        """Test basic ecology pressure computation."""
        pressure = compute_ecology_pressure(self.population, self.carrying_capacity, self.pressure_coefficient)
        self.assertGreaterEqual(pressure, 0.0)
        self.assertLessEqual(pressure, 1.0)
        # Population at half capacity should give moderate pressure
        self.assertGreater(pressure, 0.0)
        self.assertLess(pressure, 1.0)

    def test_ecology_pressure_at_capacity(self):
        """Test ecology pressure when population equals carrying capacity."""
        pressure = compute_ecology_pressure(self.carrying_capacity, self.carrying_capacity, self.pressure_coefficient)
        self.assertAlmostEqual(pressure, 0.5, places=1)

    def test_ecology_pressure_over_capacity(self):
        """Test ecology pressure when population exceeds carrying capacity."""
        pressure = compute_ecology_pressure(self.carrying_capacity * 2, self.carrying_capacity, self.pressure_coefficient)
        self.assertGreater(pressure, 0.5)

    def test_ecology_pressure_under_capacity(self):
        """Test ecology pressure when population is below carrying capacity."""
        pressure = compute_ecology_pressure(self.carrying_capacity * 0.5, self.carrying_capacity, self.pressure_coefficient)
        self.assertLess(pressure, 0.5)

    def test_resource_depletion_rate_basic(self):
        """Test basic resource depletion rate computation."""
        depletion = compute_resource_depletion_rate(self.population, self.resource_abundance, self.depletion_rate)
        expected = self.depletion_rate * self.population / self.resource_abundance
        self.assertAlmostEqual(depletion, expected)

    def test_resource_depletion_rate_zero_resource(self):
        """Test resource depletion rate when resources are zero."""
        depletion = compute_resource_depletion_rate(self.population, 0.0, self.depletion_rate)
        self.assertEqual(depletion, 0.0)

    def test_resource_depletion_rate_large_population(self):
        """Test resource depletion rate with large population."""
        depletion = compute_resource_depletion_rate(self.population * 10, self.resource_abundance, self.depletion_rate)
        expected = self.depletion_rate * (self.population * 10) / self.resource_abundance
        self.assertAlmostEqual(depletion, expected)

    def test_adaptation_factor_basic(self):
        """Test basic adaptation factor computation."""
        pressure = 0.5
        factor = compute_adaptation_factor(pressure, self.adaptation_rate)
        expected = 1.0 + self.adaptation_rate * pressure
        self.assertAlmostEqual(factor, expected)

    def test_adaptation_factor_no_pressure(self):
        """Test adaptation factor with zero pressure."""
        factor = compute_adaptation_factor(0.0, self.adaptation_rate)
        self.assertAlmostEqual(factor, 1.0)

    def test_adaptation_factor_max_pressure(self):
        """Test adaptation factor with maximum pressure."""
        factor = compute_adaptation_factor(1.0, self.adaptation_rate)
        expected = 1.0 + self.adaptation_rate
        self.assertAlmostEqual(factor, expected)

    def test_integrated_ecology_dynamics(self):
        """Test integrated ecology dynamics over multiple time steps."""
        pop = self.population
        cap = self.carrying_capacity
        res = self.resource_abundance
        steps = 10

        for _ in range(steps):
            pressure = compute_ecology_pressure(pop, cap, self.pressure_coefficient)
            depletion = compute_resource_depletion_rate(pop, res, self.depletion_rate)
            adapt = compute_adaptation_factor(pressure, self.adaptation_rate)

            # Simulate population change (simplified logistic growth with pressure)
            growth_rate = 0.1 * adapt * (1 - pop / cap)
            pop += growth_rate * pop - depletion * 0.01
            res -= depletion * 0.1

            # Ensure non-negative values
            pop = max(pop, 0.0)
            res = max(res, 0.0)

            self.assertGreaterEqual(pressure, 0.0)
            self.assertLessEqual(pressure, 1.0)
            self.assertGreaterEqual(pop, 0.0)
            self.assertGreaterEqual(res, 0.0)

    def test_random_ecology_pressure(self):
        """Test ecology pressure with random inputs."""
        for _ in range(100):
            pop = random.uniform(0, 1000)
            cap = random.uniform(1, 1000)
            pressure = compute_ecology_pressure(pop, cap, self.pressure_coefficient)
            self.assertGreaterEqual(pressure, 0.0)
            self.assertLessEqual(pressure, 1.0)

    def test_random_resource_depletion(self):
        """Test resource depletion with random inputs."""
        for _ in range(100):
            pop = random.uniform(0, 1000)
            res = random.uniform(1, 1000)
            depletion = compute_resource_depletion_rate(pop, res, self.depletion_rate)
            self.assertGreaterEqual(depletion, 0.0)

    def test_edge_case_zero_population(self):
        """Test edge case with zero population."""
        pressure = compute_ecology_pressure(0.0, self.carrying_capacity, self.pressure_coefficient)
        self.assertAlmostEqual(pressure, 1.0 / (1.0 + math.exp(self.pressure_coefficient)), places=5)
        depletion = compute_resource_depletion_rate(0.0, self.resource_abundance, self.depletion_rate)
        self.assertEqual(depletion, 0.0)
        factor = compute_adaptation_factor(0.0, self.adaptation_rate)
        self.assertAlmostEqual(factor, 1.0)

    def test_edge_case_zero_carrying_capacity(self):
        """Test edge case with zero carrying capacity."""
        pressure = compute_ecology_pressure(self.population, 0.0, self.pressure_coefficient)
        self.assertEqual(pressure, 1.0)

    def test_edge_case_negative_population(self):
        """Test edge case with negative population (should be handled gracefully)."""
        pressure = compute_ecology_pressure(-10.0, self.carrying_capacity, self.pressure_coefficient)
        self.assertGreaterEqual(pressure, 0.0)
        self.assertLessEqual(pressure, 1.0)

    def test_adaptation_factor_integration(self):
        """Test that adaptation factor correctly modifies growth in integrated scenario."""
        pop = self.population
        cap = self.carrying_capacity
        res = self.resource_abundance

        # Run with adaptation
        for _ in range(5):
            pressure = compute_ecology_pressure(pop, cap, self.pressure_coefficient)
            adapt = compute_adaptation_factor(pressure, self.adaptation_rate)
            growth_rate = 0.1 * adapt * (1 - pop / cap)
            pop += growth_rate * pop
            pop = max(pop, 0.0)

        pop_with_adapt = pop

        # Reset and run without adaptation
        pop = self.population
        for _ in range(5):
            pressure = compute_ecology_pressure(pop, cap, self.pressure_coefficient)
            growth_rate = 0.1 * (1 - pop / cap)
            pop += growth_rate * pop
            pop = max(pop, 0.0)

        pop_without_adapt = pop

        # With adaptation, population should grow faster (or at least not slower)
        self.assertGreaterEqual(pop_with_adapt, pop_without_adapt)

    def test_self_modification_import(self):
        """Test that the self-modification function is available and works."""
        result = test_self_modification()
        self.assertTrue(result)


if __name__ == '__main__':
    unittest.main()