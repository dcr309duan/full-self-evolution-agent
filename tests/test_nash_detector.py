import sys
import os
import unittest

# Add the parent directory to sys.path to allow imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.nash_detector import NashEquilibriumDetector


class TestNashDetector(unittest.TestCase):
    def setUp(self):
        self.detector = NashEquilibriumDetector()
        
    def test_detect_equilibrium_with_stable_scores(self):
        """Test detection of equilibrium with stable scores where no module can improve"""
        module_scores = {
            'module_a': 0.8,
            'module_b': 0.6,
            'module_c': 0.9
        }
        
        result = self.detector.detect_equilibrium(module_scores)
        
        self.assertIsInstance(result, dict)
        self.assertIn('is_equilibrium', result)
        self.assertIn('deviations', result)
        self.assertIsInstance(result['is_equilibrium'], bool)
        self.assertIsInstance(result['deviations'], list)
        
        # With stable scores, should detect equilibrium
        self.assertTrue(result['is_equilibrium'])
        self.assertEqual(len(result['deviations']), 0)
        
    def test_non_detection_with_improving_scores(self):
        """Test non-detection of equilibrium when scores can be improved"""
        module_scores = {
            'module_a': 0.3,
            'module_b': 0.4,
            'module_c': 0.2
        }
        
        result = self.detector.detect_equilibrium(module_scores)
        
        self.assertIsInstance(result, dict)
        self.assertIn('is_equilibrium', result)
        self.assertIn('deviations', result)
        
        # With low scores that can be improved, should not detect equilibrium
        self.assertFalse(result['is_equilibrium'])
        self.assertGreater(len(result['deviations']), 0)
        
        # Verify deviations contain expected structure
        for deviation in result['deviations']:
            self.assertIn('module', deviation)
            self.assertIn('current_score', deviation)
            self.assertIn('suggested_score', deviation)
            self.assertIn('reason', deviation)
            
    def test_coordinated_mutation_generation(self):
        """Test that coordinated mutation generation returns list of tuples with module names and changes"""
        module_scores = {
            'module_a': 0.5,
            'module_b': 0.5,
            'module_c': 0.5
        }
        
        mutations = self.detector.generate_coordinated_mutations(module_scores)
        
        # Verify it returns a list
        self.assertIsInstance(mutations, list)
        
        # Verify each mutation is a tuple of (module_name, changes)
        for mutation in mutations:
            self.assertIsInstance(mutation, tuple)
            self.assertEqual(len(mutation), 2)
            module_name, changes = mutation
            self.assertIsInstance(module_name, str)
            self.assertIsInstance(changes, dict)


if __name__ == '__main__':
    unittest.main()