import unittest
import sys
import os

# Add parent directory to path for imports if needed
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class TestNashEquilibrium(unittest.TestCase):
    """Test Nash Equilibrium detection and forcing logic."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.payoff_matrix = [
            [(3, 3), (1, 4)],
            [(4, 1), (2, 2)]
        ]
    
    def test_pure_nash_equilibrium_exists(self):
        """Test that pure Nash equilibrium is correctly identified."""
        from core.nash_detector_and_forcer import find_pure_nash_equilibria
        equilibria = find_pure_nash_equilibria(self.payoff_matrix)
        self.assertIsNotNone(equilibria)
        self.assertIn((1, 1), equilibria)  # Bottom-right is Nash equilibrium
    
    def test_no_pure_nash_equilibrium(self):
        """Test case with no pure Nash equilibrium."""
        from core.nash_detector_and_forcer import find_pure_nash_equilibria
        matrix = [
            [(2, 0), (0, 2)],
            [(0, 2), (2, 0)]
        ]
        equilibria = find_pure_nash_equilibria(matrix)
        self.assertEqual(len(equilibria), 0)
    
    def test_mixed_nash_equilibrium(self):
        """Test mixed strategy Nash equilibrium calculation."""
        from core.nash_detector_and_forcer import find_mixed_nash_equilibrium
        mixed_eq = find_mixed_nash_equilibrium(self.payoff_matrix)
        self.assertIsNotNone(mixed_eq)
        p1_strategy, p2_strategy = mixed_eq
        self.assertAlmostEqual(sum(p1_strategy), 1.0)
        self.assertAlmostEqual(sum(p2_strategy), 1.0)
    
    def test_force_nash_equilibrium(self):
        """Test forcing a game to Nash equilibrium."""
        from core.nash_detector_and_forcer import force_nash_equilibrium
        modified_matrix, eq = force_nash_equilibrium(self.payoff_matrix)
        self.assertIsNotNone(eq)
        # Verify the modified matrix has a Nash equilibrium at the forced point
        from core.nash_detector_and_forcer import find_pure_nash_equilibria
        new_equilibria = find_pure_nash_equilibria(modified_matrix)
        self.assertIn(eq, new_equilibria)
    
    def test_payoff_matrix_validation(self):
        """Test that invalid payoff matrices raise appropriate errors."""
        from core.nash_detector_and_forcer import validate_payoff_matrix
        # Test non-square matrix
        with self.assertRaises(ValueError):
            validate_payoff_matrix([[(1, 2)]])
        # Test empty matrix
        with self.assertRaises(ValueError):
            validate_payoff_matrix([])
    
    def test_strategy_profiles(self):
        """Test enumeration of strategy profiles."""
        from core.nash_detector_and_forcer import enumerate_strategy_profiles
        profiles = enumerate_strategy_profiles(self.payoff_matrix)
        expected_profiles = [(0, 0), (0, 1), (1, 0), (1, 1)]
        self.assertEqual(profiles, expected_profiles)

def run_tests():
    """Run the test suite."""
    unittest.main()

if __name__ == '__main__':
    run_tests()