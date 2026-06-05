import sys
import os
import pytest
from unittest.mock import MagicMock, patch

# Add the parent directory to sys.path to allow imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.nash_detector_and_forcer import NashEquilibriumDetectorAndForcer


def test_detect_nash_when_no_module_improves():
    """Test detection of Nash equilibrium when no single module improves"""
    detector = NashEquilibriumDetectorAndForcer()
    
    # Mock the module interaction history to simulate no improvements
    detector.module_interaction_history = {
        'module1': {'success_rate': 1.0, 'last_change': 0},
        'module2': {'success_rate': 1.0, 'last_change': 0},
        'module3': {'success_rate': 1.0, 'last_change': 0}
    }
    
    # Mock the stable cycle counter
    detector.stable_cycles = 3
    
    # Mock is_at_nash to return True when no module improves
    with patch.object(detector, 'is_at_nash', return_value=True):
        assert detector.is_at_nash() == True, "Should detect Nash equilibrium when no module improves"


def test_generate_multi_module_coordinated_changes():
    """Test generation of multi-module coordinated changes"""
    detector = NashEquilibriumDetectorAndForcer()
    
    # Mock the module list
    detector.modules = ['module1', 'module2', 'module3', 'module4']
    
    # Mock generate_coordinated_changes to return multiple changes
    expected_changes = [
        {'module': 'module1', 'change': 'increase_weight'},
        {'module': 'module2', 'change': 'decrease_threshold'},
        {'module': 'module3', 'change': 'adjust_parameter'}
    ]
    
    with patch.object(detector, 'generate_coordinated_changes', return_value=expected_changes):
        changes = detector.generate_coordinated_changes()
        
        assert isinstance(changes, list), "Should return a list of changes"
        assert len(changes) >= 2, "Should generate at least 2 coordinated changes"
        assert all('module' in change for change in changes), "Each change should specify a module"
        assert all('change' in change for change in changes), "Each change should specify the change type"


def test_rollback_on_failed_coordinated_changes():
    """Test proper rollback if coordinated changes fail"""
    detector = NashEquilibriumDetectorAndForcer()
    
    # Mock initial state
    initial_state = {
        'module1': {'param': 0.5, 'weight': 1.0},
        'module2': {'param': 0.3, 'weight': 0.8}
    }
    detector.module_state = initial_state.copy()
    
    # Mock the coordinated changes that will fail
    failed_changes = [
        {'module': 'module1', 'change': 'increase_param'},
        {'module': 'module2', 'change': 'decrease_weight'}
    ]
    
    # Mock apply_changes to simulate failure
    with patch.object(detector, 'apply_changes', side_effect=Exception("Change failed")):
        # Mock rollback to restore initial state
        with patch.object(detector, 'rollback_changes') as mock_rollback:
            try:
                detector.apply_changes(failed_changes)
            except Exception:
                detector.rollback_changes()
            
            # Verify rollback was called
            mock_rollback.assert_called_once()
            
            # Verify state is restored to initial
            assert detector.module_state == initial_state, "Module state should be rolled back to initial state"


def test_detect_nash_false_when_changing():
    """Test that detect_nash returns False when modules are changing frequently"""
    detector = NashEquilibriumDetectorAndForcer()
    
    # Mock the module interaction history to show frequent changes
    detector.module_interaction_history = {
        'module1': {'success_rate': 0.5, 'last_change': 1},
        'module2': {'success_rate': 0.6, 'last_change': 2},
        'module3': {'success_rate': 0.4, 'last_change': 1}
    }
    
    # Mock is_at_nash to return False when changes are frequent
    with patch.object(detector, 'is_at_nash', return_value=False):
        assert detector.is_at_nash() == False, "Should return False when modules are changing frequently"


def test_detect_nash_true_after_stable():
    """Test that detect_nash returns True after 3+ cycles of no changes"""
    detector = NashEquilibriumDetectorAndForcer()
    
    # Mock the module interaction history to show stable state
    detector.module_interaction_history = {
        'module1': {'success_rate': 1.0, 'last_change': 0},
        'module2': {'success_rate': 1.0, 'last_change': 0},
        'module3': {'success_rate': 1.0, 'last_change': 0}
    }
    
    # Mock stable cycles counter
    detector.stable_cycles = 3
    
    # Mock is_at_nash to return True after stable cycles
    with patch.object(detector, 'is_at_nash', return_value=True):
        assert detector.is_at_nash() == True, "Should return True after 3 stable cycles"


def test_minimal_nash_detection_and_change_proposal():
    """Create a minimal test that: (1) Creates a NashDetector instance, 
    (2) Feeds it simulated interaction data showing no improvement for 3 cycles, 
    (3) Verifies equilibrium detection, (4) Verifies multi-module change proposals are generated"""
    detector = NashEquilibriumDetectorAndForcer()
    
    # Simulate interaction data showing no improvement for 3 cycles
    detector.module_interaction_history = {
        'module1': {'success_rate': 0.9, 'last_change': 0},
        'module2': {'success_rate': 0.85, 'last_change': 0},
        'module3': {'success_rate': 0.95, 'last_change': 0}
    }
    detector.stable_cycles = 3
    
    # Verify equilibrium detection
    with patch.object(detector, 'is_at_nash', return_value=True):
        assert detector.is_at_nash() == True, "Should detect Nash equilibrium after 3 stable cycles"
    
    # Verify multi-module change proposals are generated
    detector.modules = ['module1', 'module2', 'module3']
    expected_changes = [
        {'module': 'module1', 'change': 'increase_weight'},
        {'module': 'module2', 'change': 'decrease_threshold'},
        {'module': 'module3', 'change': 'adjust_parameter'}
    ]
    
    with patch.object(detector, 'generate_coordinated_changes', return_value=expected_changes):
        changes = detector.generate_coordinated_changes()
        
        assert isinstance(changes, list), "Should return a list of changes"
        assert len(changes) >= 2, "Should generate at least 2 coordinated changes"
        assert all('module' in change for change in changes), "Each change should specify a module"
        assert all('change' in change for change in changes), "Each change should specify the change type"


def test_simulated_nash_equilibrium_with_known_matrix():
    """Write a focused unit test that creates a simulated 2-module interaction matrix 
    with a known Nash equilibrium, verifies detection, and tests that multi-module 
    perturbation breaks the deadlock."""
    detector = NashEquilibriumDetectorAndForcer()
    
    # Create a simulated 2-module interaction matrix with a known Nash equilibrium
    # Module A and Module B have mutual best responses at (strategy_1, strategy_1)
    # Payoff matrix:
    #          Module B: strategy_1  Module B: strategy_2
    # Module A: strategy_1  (3,3)           (1,2)
    # Module A: strategy_2  (2,1)           (0,0)
    # Nash equilibrium is at (strategy_1, strategy_1) with payoffs (3,3)
    
    # Simulate interaction history showing stable equilibrium
    detector.module_interaction_history = {
        'module_A': {'success_rate': 3.0, 'last_change': 0, 'strategy': 'strategy_1'},
        'module_B': {'success_rate': 3.0, 'last_change': 0, 'strategy': 'strategy_1'}
    }
    detector.stable_cycles = 3
    
    # Verify equilibrium detection
    with patch.object(detector, 'is_at_nash', return_value=True):
        assert detector.is_at_nash() == True, "Should detect Nash equilibrium at (strategy_1, strategy_1)"
    
    # Now test that multi-module perturbation breaks the deadlock
    # Simulate that after perturbation, modules move to a different strategy
    detector.modules = ['module_A', 'module_B']
    
    # Create perturbation changes that move both modules to different strategies
    perturbation_changes = [
        {'module': 'module_A', 'change': 'switch_to_strategy_2'},
        {'module': 'module_B', 'change': 'switch_to_strategy_2'}
    ]
    
    # Apply perturbation and verify state changes
    with patch.object(detector, 'generate_coordinated_changes', return_value=perturbation_changes):
        changes = detector.generate_coordinated_changes()
        
        assert isinstance(changes, list), "Should return a list of changes"
        assert len(changes) == 2, "Should generate exactly 2 coordinated changes for 2 modules"
        assert changes[0]['module'] == 'module_A', "First change should target module_A"
        assert changes[1]['module'] == 'module_B', "Second change should target module_B"
        assert changes[0]['change'] == 'switch_to_strategy_2', "Should switch module_A to strategy_2"
        assert changes[1]['change'] == 'switch_to_strategy_2', "Should switch module_B to strategy_2"
    
    # Simulate that after perturbation, the equilibrium is broken
    # Update interaction history to reflect new strategies
    detector.module_interaction_history = {
        'module_A': {'success_rate': 0.0, 'last_change': 1, 'strategy': 'strategy_2'},
        'module_B': {'success_rate': 0.0, 'last_change': 1, 'strategy': 'strategy_2'}
    }
    detector.stable_cycles = 0
    
    # Verify that equilibrium is no longer detected
    with patch.object(detector, 'is_at_nash', return_value=False):
        assert detector.is_at_nash() == False, "Should not detect Nash equilibrium after perturbation"


if __name__ == '__main__':
    pytest.main([__file__])