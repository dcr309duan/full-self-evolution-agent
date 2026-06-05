import sys
import os

# Add the parent directory to sys.path to allow imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.nash_detector import NashEquilibriumDetector


def test_equilibrium_detection():
    """Test equilibrium detection on a simple 2x2 payoff matrix"""
    detector = NashEquilibriumDetector()
    
    # Simple 2x2 payoff matrix where both players have a dominant strategy
    module_scores = {
        'player1': 0.9,
        'player2': 0.9
    }
    
    result = detector.detect_equilibrium(module_scores)
    
    assert isinstance(result, dict), "Result should be a dictionary"
    assert 'is_equilibrium' in result, "Result should contain 'is_equilibrium'"
    assert 'deviations' in result, "Result should contain 'deviations'"
    assert isinstance(result['is_equilibrium'], bool), "is_equilibrium should be boolean"
    assert isinstance(result['deviations'], list), "deviations should be a list"
    
    # With stable high scores, should detect equilibrium
    assert result['is_equilibrium'] == True, "Should detect equilibrium with stable scores"
    assert len(result['deviations']) == 0, "Should have no deviations at equilibrium"


def test_non_equilibrium_detection():
    """Test detection of non-equilibrium state"""
    detector = NashEquilibriumDetector()
    
    # Scores that are not in equilibrium (one player can improve)
    module_scores = {
        'player1': 0.3,
        'player2': 0.9
    }
    
    result = detector.detect_equilibrium(module_scores)
    
    assert isinstance(result, dict), "Result should be a dictionary"
    assert 'is_equilibrium' in result, "Result should contain 'is_equilibrium'"
    assert 'deviations' in result, "Result should contain 'deviations'"
    
    # With unbalanced scores, should not detect equilibrium
    assert result['is_equilibrium'] == False, "Should not detect equilibrium with unbalanced scores"
    assert len(result['deviations']) > 0, "Should have deviations in non-equilibrium state"


def test_coordinated_change_detection():
    """Test coordinated change detection"""
    detector = NashEquilibriumDetector()
    
    # Initial scores at equilibrium
    initial_scores = {
        'player1': 0.5,
        'player2': 0.5
    }
    
    # Detect initial equilibrium
    initial_result = detector.detect_equilibrium(initial_scores)
    assert initial_result['is_equilibrium'] == True, "Initial state should be equilibrium"
    
    # Simulate a coordinated change (both players improve together)
    new_scores = {
        'player1': 0.8,
        'player2': 0.8
    }
    
    # Detect new equilibrium after coordinated change
    new_result = detector.detect_equilibrium(new_scores)
    assert new_result['is_equilibrium'] == True, "New state should be equilibrium"
    assert len(new_result['deviations']) == 0, "Should have no deviations after coordinated change"
    
    # Verify that the coordinated change improved both players
    for player in initial_scores:
        assert new_scores[player] > initial_scores[player], f"{player} should have improved"


def test_equilibrium_after_cycles():
    """Test equilibrium detection after 3+ cycles of no improvement"""
    detector = NashEquilibriumDetector()
    
    # Create mock module performance data with stable scores across cycles
    module_performance_data = []
    for cycle in range(5):  # 5 cycles of stable performance
        module_performance_data.append({
            'module1': 0.85,
            'module2': 0.85,
            'module3': 0.85
        })
    
    # Simulate detection across cycles
    for cycle_data in module_performance_data:
        result = detector.detect_equilibrium(cycle_data)
    
    # After 3+ cycles of no improvement, should detect equilibrium
    assert result['is_equilibrium'] == True, "Should detect equilibrium after stable cycles"
    assert len(result['deviations']) == 0, "Should have no deviations at equilibrium"


if __name__ == '__main__':
    test_equilibrium_detection()
    test_non_equilibrium_detection()
    test_coordinated_change_detection()
    test_equilibrium_after_cycles()
    print("All tests passed!")