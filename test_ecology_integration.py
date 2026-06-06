import unittest
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from core.ecology_pressure_engine import evolve_fitness_landscape

class TestEcologyIntegration(unittest.TestCase):
    def test_full_ecology_cycle(self):
        result = evolve_fitness_landscape()
        self.assertIsInstance(result, dict)
        self.assertIn('fitness_scores', result)
        self.assertIn('population', result)
        self.assertIn('generation', result)
        self.assertIn('test_suite', result)
        test_suite = result['test_suite']
        self.assertIsInstance(test_suite, list)
        self.assertGreater(len(test_suite), 0)
        initial_count = len(test_suite)
        result2 = evolve_fitness_landscape()
        test_suite2 = result2['test_suite']
        self.assertGreaterEqual(len(test_suite2), initial_count - 1)

if __name__ == '__main__':
    unittest.main()