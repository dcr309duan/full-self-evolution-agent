import sys
import os

# Add the parent directory to sys.path to allow imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.nash_detector import NashEquilibriumDetector


def test_is_at_nash_initial_false():
    """Test that is_at_nash() returns False initially"""
    detector = NashEquilibriumDetector()
    assert detector.is_at_nash() == False, "is_at_nash should return False initially"


def test_is_at_nash_true_after_3_stable_cycles():
    """Test that adding 3+ stable cycles triggers True"""
    detector = NashEquilibriumDetector()
    for _ in range(3):
        detector.add_stable_cycle()
    assert detector.is_at_nash() == True, "is_at_nash should return True after 3 stable cycles"


def test_get_stable_modules_returns_correct_list():
    """Test that get_stable_modules() returns correct list"""
    detector = NashEquilibriumDetector()
    # Initially should return empty list
    assert detector.get_stable_modules() == [], "get_stable_modules should return empty list initially"
    
    # After adding stable cycles, should return list with module names
    for _ in range(3):
        detector.add_stable_cycle()
    stable_modules = detector.get_stable_modules()
    assert isinstance(stable_modules, list), "get_stable_modules should return a list"
    assert len(stable_modules) > 0, "get_stable_modules should return non-empty list after stable cycles"


if __name__ == '__main__':
    test_is_at_nash_initial_false()
    test_is_at_nash_true_after_3_stable_cycles()
    test_get_stable_modules_returns_correct_list()
    print("All tests passed!")