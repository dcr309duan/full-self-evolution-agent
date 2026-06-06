import sys
import os
import unittest

# Add the parent directory to sys.path to allow imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.nash_detector_and_forcer import NashEquilibriumDetectorAndForcer


class TestNashDetector(unittest.TestCase):
    """Test cases for NashEquilibriumDetectorAndForcer."""
    
    def setUp(self):
        """Create a fresh detector instance for each test."""
        self.detector = NashEquilibriumDetectorAndForcer()
    
    def test_plateau_detection(self):
        """Test that NashDetector correctly identifies a plateau when no single-module changes improve for 10+ cycles."""
        # Set up history with all improvements below threshold for 10 cycles
        self.detector.module_interaction_history = {
            'module1': {'success_rate': 0.95, 'last_change': 0, 'improvement': 0.003},
            'module2': {'success_rate': 0.92, 'last_change': 0, 'improvement': 0.005},
            'module3': {'success_rate': 0.97, 'last_change': 0, 'improvement': 0.002}
        }
        self.detector.stable_cycles = 10
        self.detector.modules = ['module1', 'module2', 'module3']
        
        # Verify plateau detection
        all_improvements_below_threshold = all(
            info.get('improvement', 1.0) < 0.01
            for info in self.detector.module_interaction_history.values()
        )
        self.assertTrue(all_improvements_below_threshold, 
                       "All modules should have improvement < 0.01 for plateau")
        self.assertGreaterEqual(self.detector.stable_cycles, 10, 
                               "Should have at least 10 stable cycles for plateau")
        
        # Test that plateau is broken when a module has improvement
        self.detector.module_interaction_history['module1']['improvement'] = 0.05
        all_improvements_below_threshold = all(
            info.get('improvement', 1.0) < 0.01
            for info in self.detector.module_interaction_history.values()
        )
        self.assertFalse(all_improvements_below_threshold,
                        "Plateau should be broken when a module has significant improvement")
    
    def test_nash_equilibrium_detection(self):
        """Test that NashDetector correctly identifies Nash equilibrium."""
        # Set up history showing Nash equilibrium (no module can improve unilaterally)
        self.detector.module_interaction_history = {
            'module1': {'success_rate': 0.95, 'last_change': 0, 'improvement': 0.001},
            'module2': {'success_rate': 0.92, 'last_change': 0, 'improvement': 0.002},
            'module3': {'success_rate': 0.97, 'last_change': 0, 'improvement': 0.003}
        }
        self.detector.stable_cycles = 15
        self.detector.modules = ['module1', 'module2', 'module3']
        
        # Verify Nash equilibrium detection
        all_improvements_below_threshold = all(
            info.get('improvement', 1.0) < 0.01
            for info in self.detector.module_interaction_history.values()
        )
        self.assertTrue(all_improvements_below_threshold,
                       "All modules should have improvement < 0.01 for Nash equilibrium")
        self.assertGreaterEqual(self.detector.stable_cycles, 10,
                               "Should have at least 10 stable cycles for Nash equilibrium")
    
    def test_multi_module_proposals(self):
        """Test that NashForcer generates multi-module proposals when a Nash equilibrium is detected."""
        # Set up equilibrium state
        self.detector.module_interaction_history = {
            'module1': {'success_rate': 0.95, 'last_change': 0, 'improvement': 0.003},
            'module2': {'success_rate': 0.92, 'last_change': 0, 'improvement': 0.005},
            'module3': {'success_rate': 0.97, 'last_change': 0, 'improvement': 0.002}
        }
        self.detector.stable_cycles = 12
        self.detector.modules = ['module1', 'module2', 'module3']
        
        # Generate multi-module proposals
        proposals = self.detector.generate_multi_module_proposals()
        
        # Verify proposals exist and are multi-module
        self.assertIsNotNone(proposals, "Should generate proposals")
        self.assertGreaterEqual(len(proposals), 2, 
                               "Should generate at least 2 multi-module proposals")
        
        # Verify proposal structure
        for proposal in proposals:
            self.assertIn('module', proposal, "Each proposal should specify a module")
            self.assertIn('change', proposal, "Each proposal should specify a change type")
            self.assertIsInstance(proposal['module'], str, "Module name should be a string")
            self.assertIsInstance(proposal['change'], str, "Change type should be a string")
        
        # Verify proposals cover multiple modules
        proposal_modules = {p['module'] for p in proposals}
        self.assertGreaterEqual(len(proposal_modules), 2,
                               "Proposals should cover at least 2 different modules")
        
        # Verify proposals would break the equilibrium
        for proposal in proposals:
            module = proposal['module']
            if module in self.detector.module_interaction_history:
                self.detector.module_interaction_history[module]['last_change'] = 1
                self.detector.module_interaction_history[module]['improvement'] = 0.1
        
        # After applying proposals, equilibrium should be broken
        self.detector.stable_cycles = 0
        all_stable_after = all(
            info['last_change'] == 0
            for info in self.detector.module_interaction_history.values()
        )
        self.assertFalse(all_stable_after, 
                        "Equilibrium should be broken after applying proposals")
        self.assertLess(self.detector.stable_cycles, 10,
                       "Stable cycles should be reset after proposals")
    
    def test_empty_history(self):
        """Test that the module handles empty history gracefully."""
        # Test with empty module_interaction_history
        self.detector.module_interaction_history = {}
        self.detector.stable_cycles = 0
        self.detector.modules = []
        
        # Should not raise errors
        all_improvements = all(
            info.get('improvement', 1.0) < 0.01
            for info in self.detector.module_interaction_history.values()
        )
        self.assertTrue(all_improvements, 
                       "Empty history should be considered as all improvements below threshold")
        self.assertEqual(self.detector.stable_cycles, 0,
                        "Empty history should have 0 stable cycles")
        
        # Generate proposals with empty history
        proposals = self.detector.generate_multi_module_proposals()
        self.assertIsNone(proposals, 
                         "Should return None for empty history")
    
    def test_single_module(self):
        """Test that the module handles single module correctly."""
        # Set up single module
        self.detector.module_interaction_history = {
            'module1': {'success_rate': 0.95, 'last_change': 0, 'improvement': 0.003}
        }
        self.detector.stable_cycles = 10
        self.detector.modules = ['module1']
        
        # Verify plateau detection with single module
        all_improvements_below_threshold = all(
            info.get('improvement', 1.0) < 0.01
            for info in self.detector.module_interaction_history.values()
        )
        self.assertTrue(all_improvements_below_threshold,
                       "Single module should be in plateau")
        self.assertGreaterEqual(self.detector.stable_cycles, 10,
                               "Single module should have at least 10 stable cycles")
        
        # Generate proposals with single module
        proposals = self.detector.generate_multi_module_proposals()
        self.assertIsNone(proposals,
                         "Should return None for single module (need at least 2 for multi-module)")
    
    def test_no_equilibrium(self):
        """Test that the module correctly identifies when there is no equilibrium."""
        # Set up history with one module having significant improvement
        self.detector.module_interaction_history = {
            'module1': {'success_rate': 0.95, 'last_change': 0, 'improvement': 0.003},
            'module2': {'success_rate': 0.92, 'last_change': 0, 'improvement': 0.08},
            'module3': {'success_rate': 0.97, 'last_change': 0, 'improvement': 0.002}
        }
        self.detector.stable_cycles = 0
        self.detector.modules = ['module1', 'module2', 'module3']
        
        # Verify no equilibrium detection
        any_improvement_above_threshold = any(
            info.get('improvement', 0.0) > 0.05
            for info in self.detector.module_interaction_history.values()
        )
        self.assertTrue(any_improvement_above_threshold,
                       "At least one module should have improvement > 0.05 for no equilibrium")
        self.assertLess(self.detector.stable_cycles, 10,
                       "Stable cycles should be less than 10 for no equilibrium")
        
        # Generate proposals when no equilibrium
        proposals = self.detector.generate_multi_module_proposals()
        self.assertIsNone(proposals,
                         "Should return None when no equilibrium detected")


def run_tests():
    """Run all tests with simple assert statements as an alternative."""
    detector = NashEquilibriumDetectorAndForcer()
    
    # Test 1: Plateau detection
    detector.module_interaction_history = {
        'module1': {'success_rate': 0.95, 'last_change': 0, 'improvement': 0.003},
        'module2': {'success_rate': 0.92, 'last_change': 0, 'improvement': 0.005}
    }
    detector.stable_cycles = 10
    detector.modules = ['module1', 'module2']
    
    all_below = all(info.get('improvement', 1.0) < 0.01 
                   for info in detector.module_interaction_history.values())
    assert all_below, "All improvements should be below threshold"
    assert detector.stable_cycles >= 10, "Should have 10+ stable cycles"
    
    # Test 2: Multi-module proposals
    detector.stable_cycles = 12
    proposals = detector.generate_multi_module_proposals()
    assert proposals is not None, "Should generate proposals"
    assert len(proposals) >= 2, "Should have at least 2 proposals"
    
    # Test 3: Empty history
    detector.module_interaction_history = {}
    detector.stable_cycles = 0
    detector.modules = []
    
    all_below = all(info.get('improvement', 1.0) < 0.01 
                   for info in detector.module_interaction_history.values())
    assert all_below, "Empty history should be all below threshold"
    assert detector.stable_cycles == 0, "Empty history should have 0 stable cycles"
    
    # Test 4: Single module
    detector.module_interaction_history = {
        'module1': {'success_rate': 0.95, 'last_change': 0, 'improvement': 0.003}
    }
    detector.stable_cycles = 10
    detector.modules = ['module1']
    
    proposals = detector.generate_multi_module_proposals()
    assert proposals is None, "Single module should return None for multi-module proposals"
    
    print("All simple assert tests passed!")


if __name__ == '__main__':
    # Run unittest tests
    unittest.main(exit=False)
    # Run simple assert tests
    run_tests()