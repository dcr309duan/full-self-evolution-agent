import sys
import os

# Add the parent directory to sys.path to allow imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.nash_detector_and_forcer import NashEquilibriumDetectorAndForcer


def test_import():
    """Test that the module can be imported without errors"""
    assert NashEquilibriumDetectorAndForcer is not None


def test_detect_nash_false_when_changing():
    """Test that detect_nash returns False when modules are changing frequently"""
    detector = NashEquilibriumDetectorAndForcer()
    
    # Simulate frequent changes by adding unstable cycles
    for _ in range(5):
        detector.add_stable_cycle()
        detector.apply_perturbation()
    
    assert detector.is_at_nash() == False, "is_at_nash should return False when modules are changing frequently"


def test_detect_nash_true_after_stable():
    """Test that detect_nash returns True after 3+ cycles of no changes"""
    detector = NashEquilibriumDetectorAndForcer()
    
    # Add stable cycles without perturbations
    for _ in range(3):
        detector.add_stable_cycle()
    
    assert detector.is_at_nash() == True, "is_at_nash should return True after 3 stable cycles"


def test_generate_coordinated_changes():
    """Test that generate_coordinated_changes returns at least 2 module changes when Nash is detected"""
    detector = NashEquilibriumDetectorAndForcer()
    
    # Reach Nash equilibrium
    for _ in range(3):
        detector.add_stable_cycle()
    
    # Generate coordinated changes
    changes = detector.generate_coordinated_changes()
    
    assert isinstance(changes, list), "generate_coordinated_changes should return a list"
    assert len(changes) >= 2, "generate_coordinated_changes should return at least 2 module changes"


if __name__ == '__main__':
    test_import()
    test_detect_nash_false_when_changing()
    test_detect_nash_true_after_stable()
    test_generate_coordinated_changes()
    print("All tests passed!")