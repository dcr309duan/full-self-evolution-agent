import sys
import os

# Add the parent directory to sys.path to allow imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.nash_detector import NashEquilibriumDetector


def test_initial_state():
    """Test that detect_nash() returns False initially"""
    detector = NashEquilibriumDetector()
    assert detector.detect_nash() == False, "Initial state should not be Nash equilibrium"


def test_stable_cycles_trigger_nash():
    """Test that feeding 3+ stable cycles triggers True"""
    detector = NashEquilibriumDetector()
    
    # Feed 4 stable cycles (more than 3)
    for _ in range(4):
        detector.add_stable_cycle()
    
    assert detector.detect_nash() == True, "Should detect Nash after 3+ stable cycles"


def test_get_stable_modules():
    """Test that get_stable_modules() returns a list"""
    detector = NashEquilibriumDetector()
    
    # Add some stable cycles first
    for _ in range(2):
        detector.add_stable_cycle()
    
    result = detector.get_stable_modules()
    assert isinstance(result, list), "get_stable_modules() should return a list"


if __name__ == '__main__':
    test_initial_state()
    test_stable_cycles_trigger_nash()
    test_get_stable_modules()
    print("All tests passed!")