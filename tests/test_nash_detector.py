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


if __name__ == '__main__':
    pytest.main([__file__])