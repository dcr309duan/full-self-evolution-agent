import sys
import os
import unittest

# Add the parent directory to sys.path to allow imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.nash_detector import NashEquilibriumDetector


class TestNashDetector(unittest.TestCase):
    def test_import_clean(self):
        """Test that the module imports cleanly without errors"""
        try:
            from core import nash_detector
            self.assertTrue(True)
        except ImportError as e:
            self.fail(f"Import failed: {e}")

    def test_initialization_empty_state(self):
        """Test initialization with empty state"""
        detector = NashEquilibriumDetector()
        self.assertIsNotNone(detector)
        self.assertEqual(len(detector.module_scores), 0)
        self.assertEqual(len(detector.history), 0)

    def test_add_scores_and_detect_equilibrium(self):
        """Test adding module scores and detecting equilibrium"""
        detector = NashEquilibriumDetector()
        
        module_scores = {
            'module_a': 0.8,
            'module_b': 0.6,
            'module_c': 0.9
        }
        
        result = detector.detect_equilibrium(module_scores)
        
        self.assertIsInstance(result, dict)
        self.assertIn('is_equilibrium', result)
        self.assertIn('deviations', result)
        self.assertIsInstance(result['is_equilibrium'], bool)
        self.assertIsInstance(result['deviations'], list)
        
        # With stable scores, should detect equilibrium
        self.assertTrue(result['is_equilibrium'])
        self.assertEqual(len(result['deviations']), 0)

    def test_coalition_improvements_at_equilibrium(self):
        """Test finding coalition improvements when at equilibrium"""
        detector = NashEquilibriumDetector()
        
        module_scores = {
            'module_a': 0.5,
            'module_b': 0.5,
            'module_c': 0.5
        }
        
        # First detect equilibrium
        result = detector.detect_equilibrium(module_scores)
        
        # Then find coalition improvements
        improvements = detector.find_coalition_improvements(module_scores)
        
        self.assertIsInstance(improvements, list)
        for improvement in improvements:
            self.assertIsInstance(improvement, tuple)
            self.assertEqual(len(improvement), 2)
            module_name, changes = improvement
            self.assertIsInstance(module_name, str)
            self.assertIsInstance(changes, dict)


if __name__ == '__main__':
    unittest.main()