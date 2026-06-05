import unittest
from core.nash_detector import NashEquilibriumDetector


class TestNashDetector(unittest.TestCase):
    def setUp(self):
        self.detector = NashEquilibriumDetector()
        
    def test_equilibrium_detection_and_coordinated_change(self):
        # Simulate module scores
        module_scores = {
            'module_a': 0.8,
            'module_b': 0.6,
            'module_c': 0.9
        }
        
        # Test equilibrium detection
        is_equilibrium, deviations = self.detector.check_equilibrium(module_scores)
        self.assertIsInstance(is_equilibrium, bool)
        self.assertIsInstance(deviations, list)
        
        # Test coordinated change forcing
        new_scores = self.detector.force_coordinated_change(module_scores)
        self.assertIsInstance(new_scores, dict)
        self.assertEqual(len(new_scores), len(module_scores))
        
        # Verify all modules are present in new scores
        for module in module_scores:
            self.assertIn(module, new_scores)
            
        # Verify scores are within valid range
        for score in new_scores.values():
            self.assertGreaterEqual(score, 0.0)
            self.assertLessEqual(score, 1.0)


if __name__ == '__main__':
    unittest.main()