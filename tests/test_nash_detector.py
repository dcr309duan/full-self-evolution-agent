import unittest
from core.nash_detector import NashEquilibriumDetector


class TestNashDetector(unittest.TestCase):
    def setUp(self):
        self.detector = NashEquilibriumDetector()
        
    def test_detect_equilibrium_with_mock_scenario(self):
        # Create a simple mock scenario with module scores
        module_scores = {
            'module_a': 0.8,
            'module_b': 0.6,
            'module_c': 0.9
        }
        
        # Test detect_equilibrium method
        result = self.detector.detect_equilibrium(module_scores)
        
        # Verify result is a dictionary
        self.assertIsInstance(result, dict)
        
        # Verify result contains expected keys
        self.assertIn('is_equilibrium', result)
        self.assertIn('deviations', result)
        
        # Verify types of values
        self.assertIsInstance(result['is_equilibrium'], bool)
        self.assertIsInstance(result['deviations'], list)
        
        # Verify deviations contain expected structure
        for deviation in result['deviations']:
            self.assertIn('module', deviation)
            self.assertIn('current_score', deviation)
            self.assertIn('suggested_score', deviation)
            self.assertIn('reason', deviation)


if __name__ == '__main__':
    unittest.main()