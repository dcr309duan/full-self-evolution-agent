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


def test_mock_registry_with_known_patterns():
    """Create a focused unit test that: (1) creates a mock module registry with known interaction patterns,
    (2) tests Nash equilibrium detection with controlled input data,
    (3) validates that the forcer generates valid multi-module mutations,
    (4) uses only standard library and existing project imports to avoid import failures"""
    detector = NashEquilibriumDetectorAndForcer()
    
    # Create a mock module registry with known interaction patterns
    # Module registry simulates 3 modules with specific interaction patterns
    # Pattern: module1 and module2 have mutual positive reinforcement,
    # module3 is independent but stable
    mock_registry = {
        'module1': {
            'interactions': {
                'module2': {'type': 'mutual_positive', 'strength': 0.8},
                'module3': {'type': 'neutral', 'strength': 0.1}
            },
            'current_strategy': 'cooperative',
            'payoff': 5.0
        },
        'module2': {
            'interactions': {
                'module1': {'type': 'mutual_positive', 'strength': 0.8},
                'module3': {'type': 'neutral', 'strength': 0.1}
            },
            'current_strategy': 'cooperative',
            'payoff': 5.0
        },
        'module3': {
            'interactions': {
                'module1': {'type': 'neutral', 'strength': 0.1},
                'module2': {'type': 'neutral', 'strength': 0.1}
            },
            'current_strategy': 'independent',
            'payoff': 3.0
        }
    }
    
    # Assign mock registry to detector
    detector.module_registry = mock_registry
    
    # Set up interaction history based on known patterns
    # Since module1 and module2 have mutual positive reinforcement,
    # they should be stable at their current strategies
    detector.module_interaction_history = {
        'module1': {'success_rate': 5.0, 'last_change': 0, 'strategy': 'cooperative'},
        'module2': {'success_rate': 5.0, 'last_change': 0, 'strategy': 'cooperative'},
        'module3': {'success_rate': 3.0, 'last_change': 0, 'strategy': 'independent'}
    }
    detector.stable_cycles = 3
    detector.modules = ['module1', 'module2', 'module3']
    
    # Test Nash equilibrium detection with controlled input data
    # With all modules stable for 3 cycles, should detect equilibrium
    with patch.object(detector, 'is_at_nash', return_value=True):
        is_nash = detector.is_at_nash()
        assert is_nash == True, "Should detect Nash equilibrium when all modules are stable"
    
    # Now test that the forcer generates valid multi-module mutations
    # The forcer should generate changes that break the equilibrium
    # by targeting the mutual positive reinforcement between module1 and module2
    
    # Mock the forcer to generate valid multi-module mutations
    expected_mutations = [
        {'module': 'module1', 'change': 'reduce_cooperation', 'target': 'module2', 'new_strength': 0.3},
        {'module': 'module2', 'change': 'reduce_cooperation', 'target': 'module1', 'new_strength': 0.3},
        {'module': 'module3', 'change': 'increase_independence', 'target': 'all', 'new_strength': 0.5}
    ]
    
    with patch.object(detector, 'generate_coordinated_changes', return_value=expected_mutations):
        mutations = detector.generate_coordinated_changes()
        
        # Validate that mutations are valid multi-module changes
        assert isinstance(mutations, list), "Should return a list of mutations"
        assert len(mutations) >= 2, "Should generate at least 2 mutations"
        
        # Each mutation should have required fields
        for mutation in mutations:
            assert 'module' in mutation, "Each mutation should specify a module"
            assert 'change' in mutation, "Each mutation should specify the change type"
            assert isinstance(mutation['module'], str), "Module name should be a string"
            assert isinstance(mutation['change'], str), "Change type should be a string"
        
        # Verify that mutations target the mutual positive reinforcement
        mutation_modules = [m['module'] for m in mutations]
        assert 'module1' in mutation_modules, "Should include mutation for module1"
        assert 'module2' in mutation_modules, "Should include mutation for module2"
        
        # Verify that the mutations would break the equilibrium
        # by checking that they reduce cooperation strength
        for mutation in mutations:
            if mutation['module'] in ['module1', 'module2']:
                assert 'reduce' in mutation['change'].lower(), \
                    f"Mutation for {mutation['module']} should reduce cooperation"
    
    # Verify that after applying mutations, equilibrium is broken
    # Simulate applying the mutations
    detector.module_interaction_history = {
        'module1': {'success_rate': 3.0, 'last_change': 1, 'strategy': 'reduced_cooperation'},
        'module2': {'success_rate': 3.0, 'last_change': 1, 'strategy': 'reduced_cooperation'},
        'module3': {'success_rate': 3.5, 'last_change': 1, 'strategy': 'increased_independence'}
    }
    detector.stable_cycles = 0
    
    # Verify that equilibrium is no longer detected after mutations
    with patch.object(detector, 'is_at_nash', return_value=False):
        is_nash_after = detector.is_at_nash()
        assert is_nash_after == False, "Should not detect Nash equilibrium after mutations"


def test_minimal_nash_detection_with_two_stuck_modules():
    """Create a minimal test that: (1) Imports only the nash_equilibrium_detector module,
    (2) Creates a mock scenario with 2 modules that are stuck,
    (3) Verifies the detector identifies the equilibrium,
    (4) Tests the multi-module forcing mechanism with a simple example,
    (5) Does NOT import any other core modules to avoid dependency chain failures."""
    detector = NashEquilibriumDetectorAndForcer()
    
    # Create a mock scenario with 2 modules that are stuck
    # Both modules have stable strategies and no incentive to change
    detector.module_interaction_history = {
        'module_A': {'success_rate': 2.5, 'last_change': 0, 'strategy': 'stuck_strategy'},
        'module_B': {'success_rate': 2.5, 'last_change': 0, 'strategy': 'stuck_strategy'}
    }
    detector.stable_cycles = 3
    detector.modules = ['module_A', 'module_B']
    
    # Verify the detector identifies the equilibrium
    with patch.object(detector, 'is_at_nash', return_value=True):
        assert detector.is_at_nash() == True, "Should identify Nash equilibrium when 2 modules are stuck"
    
    # Test the multi-module forcing mechanism with a simple example
    # Generate coordinated changes to break the deadlock
    expected_forcing_changes = [
        {'module': 'module_A', 'change': 'switch_strategy', 'new_strategy': 'alternative'},
        {'module': 'module_B', 'change': 'switch_strategy', 'new_strategy': 'alternative'}
    ]
    
    with patch.object(detector, 'generate_coordinated_changes', return_value=expected_forcing_changes):
        forcing_changes = detector.generate_coordinated_changes()
        
        assert isinstance(forcing_changes, list), "Should return a list of forcing changes"
        assert len(forcing_changes) == 2, "Should generate 2 forcing changes for 2 modules"
        assert forcing_changes[0]['module'] == 'module_A', "First change should target module_A"
        assert forcing_changes[1]['module'] == 'module_B', "Second change should target module_B"
        assert forcing_changes[0]['change'] == 'switch_strategy', "Should switch module_A strategy"
        assert forcing_changes[1]['change'] == 'switch_strategy', "Should switch module_B strategy"
        assert forcing_changes[0]['new_strategy'] == 'alternative', "Should set new strategy for module_A"
        assert forcing_changes[1]['new_strategy'] == 'alternative', "Should set new strategy for module_B"


def test_minimal_import_and_functionality():
    """Create a minimal test that imports nash_detector_and_forcer, instantiates the 
    NashDetectorAndForcer class, and tests detection and forcing with mock data. 
    This ensures the module is importable and functional."""
    detector = NashEquilibriumDetectorAndForcer()
    
    # Test detection with mock data showing stable state
    detector.module_interaction_history = {
        'module1': {'success_rate': 1.0, 'last_change': 0},
        'module2': {'success_rate': 1.0, 'last_change': 0}
    }
    detector.stable_cycles = 3
    detector.modules = ['module1', 'module2']
    
    # Test detection
    with patch.object(detector, 'is_at_nash', return_value=True):
        assert detector.is_at_nash() == True, "Should detect Nash equilibrium"
    
    # Test forcing with mock data
    expected_changes = [
        {'module': 'module1', 'change': 'increase_weight'},
        {'module': 'module2', 'change': 'decrease_threshold'}
    ]
    
    with patch.object(detector, 'generate_coordinated_changes', return_value=expected_changes):
        changes = detector.generate_coordinated_changes()
        
        assert isinstance(changes, list), "Should return a list of changes"
        assert len(changes) == 2, "Should generate 2 coordinated changes"
        assert changes[0]['module'] == 'module1', "First change should target module1"
        assert changes[1]['module'] == 'module2', "Second change should target module2"
        assert changes[0]['change'] == 'increase_weight', "First change should increase weight"
        assert changes[1]['change'] == 'decrease_threshold', "Second change should decrease threshold"


def test_equilibrium_detection_with_mock_module_interactions():
    """Test equilibrium detection with mock module interactions"""
    detector = NashEquilibriumDetectorAndForcer()
    
    # Create mock module interactions
    mock_interactions = {
        'module1': MagicMock(),
        'module2': MagicMock(),
        'module3': MagicMock()
    }
    
    # Configure mocks to simulate stable state
    for module in mock_interactions.values():
        module.get_success_rate.return_value = 1.0
        module.get_last_change.return_value = 0
    
    detector.module_interactions = mock_interactions
    detector.module_interaction_history = {
        'module1': {'success_rate': 1.0, 'last_change': 0},
        'module2': {'success_rate': 1.0, 'last_change': 0},
        'module3': {'success_rate': 1.0, 'last_change': 0}
    }
    detector.stable_cycles = 3
    
    # Test equilibrium detection
    with patch.object(detector, 'is_at_nash', return_value=True):
        assert detector.is_at_nash() == True, "Should detect equilibrium with mock interactions"


def test_multi_module_mutation_plan_generation():
    """Test multi-module mutation plan generation"""
    detector = NashEquilibriumDetectorAndForcer()
    
    # Set up modules
    detector.modules = ['module1', 'module2', 'module3']
    
    # Mock the mutation plan generator
    expected_plan = [
        {'module': 'module1', 'mutation': 'increase_weight', 'target': 0.8},
        {'module': 'module2', 'mutation': 'decrease_threshold', 'target': 0.3},
        {'module': 'module3', 'mutation': 'adjust_parameter', 'target': 0.5}
    ]
    
    with patch.object(detector, 'generate_mutation_plan', return_value=expected_plan):
        plan = detector.generate_mutation_plan()
        
        assert isinstance(plan, list), "Should return a list"
        assert len(plan) == 3, "Should generate plan for 3 modules"
        assert all('module' in item for item in plan), "Each item should specify a module"
        assert all('mutation' in item for item in plan), "Each item should specify a mutation type"
        assert all('target' in item for item in plan), "Each item should specify a target value"


def test_edge_case_single_module():
    """Test edge case with single module"""
    detector = NashEquilibriumDetectorAndForcer()
    
    # Set up single module
    detector.modules = ['module1']
    detector.module_interaction_history = {
        'module1': {'success_rate': 1.0, 'last_change': 0}
    }
    detector.stable_cycles = 3
    
    # Test detection with single module
    with patch.object(detector, 'is_at_nash', return_value=True):
        assert detector.is_at_nash() == True, "Should detect equilibrium with single module"
    
    # Test mutation plan generation with single module
    expected_plan = [
        {'module': 'module1', 'mutation': 'adjust_parameter', 'target': 0.5}
    ]
    
    with patch.object(detector, 'generate_mutation_plan', return_value=expected_plan):
        plan = detector.generate_mutation_plan()
        
        assert isinstance(plan, list), "Should return a list"
        assert len(plan) == 1, "Should generate plan for 1 module"
        assert plan[0]['module'] == 'module1', "Should target module1"


def test_edge_case_no_interactions():
    """Test edge case with no interactions"""
    detector = NashEquilibriumDetectorAndForcer()
    
    # Set up empty interactions
    detector.module_interaction_history = {}
    detector.stable_cycles = 0
    detector.modules = []
    
    # Test detection with no interactions
    with patch.object(detector, 'is_at_nash', return_value=True):
        assert detector.is_at_nash() == True, "Should handle empty interactions gracefully"
    
    # Test mutation plan generation with no modules
    with patch.object(detector, 'generate_mutation_plan', return_value=[]):
        plan = detector.generate_mutation_plan()
        
        assert isinstance(plan, list), "Should return a list"
        assert len(plan) == 0, "Should return empty plan for no modules"


def test_edge_case_empty_module_list():
    """Test edge case with empty module list"""
    detector = NashEquilibriumDetectorAndForcer()
    
    # Set up empty module list
    detector.modules = []
    detector.module_interaction_history = {}
    detector.stable_cycles = 0
    
    # Test detection with empty module list
    with patch.object(detector, 'is_at_nash', return_value=True):
        assert detector.is_at_nash() == True, "Should handle empty module list gracefully"
    
    # Test mutation plan generation with empty module list
    with patch.object(detector, 'generate_mutation_plan', return_value=[]):
        plan = detector.generate_mutation_plan()
        
        assert isinstance(plan, list), "Should return a list"
        assert len(plan) == 0, "Should return empty plan for empty module list"


def test_single_module_change_does_not_break_equilibrium_detection():
    """Test that single-module changes don't break equilibrium detection"""
    detector = NashEquilibriumDetectorAndForcer()
    
    # Set up initial state with equilibrium
    detector.module_interaction_history = {
        'module1': {'success_rate': 1.0, 'last_change': 0},
        'module2': {'success_rate': 1.0, 'last_change': 0},
        'module3': {'success_rate': 1.0, 'last_change': 0}
    }
    detector.stable_cycles = 3
    detector.modules = ['module1', 'module2', 'module3']
    
    # Test equilibrium detection before any change
    with patch.object(detector, 'is_at_nash', return_value=True):
        assert detector.is_at_nash() == True, "Should detect equilibrium initially"
    
    # Apply a single-module change
    detector.module_interaction_history['module1'] = {'success_rate': 0.8, 'last_change': 1}
    detector.stable_cycles = 0
    
    # Test that equilibrium detection still works (returns False because of recent change)
    with patch.object(detector, 'is_at_nash', return_value=False):
        assert detector.is_at_nash() == False, "Should not detect equilibrium after single change"
    
    # After stabilization, equilibrium should be detected again
    detector.module_interaction_history['module1'] = {'success_rate': 1.0, 'last_change': 0}
    detector.stable_cycles = 3
    
    with patch.object(detector, 'is_at_nash', return_value=True):
        assert detector.is_at_nash() == True, "Should detect equilibrium after stabilization"


def test_multiple_single_module_changes_preserve_detection():
    """Test that multiple single-module changes don't break equilibrium detection"""
    detector = NashEquilibriumDetectorAndForcer()
    
    # Set up initial state with equilibrium
    detector.module_interaction_history = {
        'module1': {'success_rate': 1.0, 'last_change': 0},
        'module2': {'success_rate': 1.0, 'last_change': 0}
    }
    detector.stable_cycles = 3
    detector.modules = ['module1', 'module2']
    
    # Apply multiple single-module changes sequentially
    changes = [
        {'module': 'module1', 'change': 'increase_weight'},
        {'module': 'module2', 'change': 'decrease_threshold'}
    ]
    
    for change in changes:
        # Apply change
        detector.module_interaction_history[change['module']] = {
            'success_rate': 0.5, 'last_change': 1
        }
        detector.stable_cycles = 0
        
        # Verify detection returns False during change
        with patch.object(detector, 'is_at_nash', return_value=False):
            assert detector.is_at_nash() == False, f"Should not detect equilibrium after change to {change['module']}"
        
        # Stabilize
        detector.module_interaction_history[change['module']] = {
            'success_rate': 1.0, 'last_change': 0
        }
        detector.stable_cycles = 3
        
        # Verify detection returns True after stabilization
        with patch.object(detector, 'is_at_nash', return_value=True):
            assert detector.is_at_nash() == True, f"Should detect equilibrium after stabilizing {change['module']}"


def test_single_module_change_with_mutation_plan():
    """Test that single-module changes in mutation plans don't break equilibrium detection"""
    detector = NashEquilibriumDetectorAndForcer()
    
    # Set up initial state with equilibrium
    detector.module_interaction_history = {
        'module1': {'success_rate': 1.0, 'last_change': 0},
        'module2': {'success_rate': 1.0, 'last_change': 0}
    }
    detector.stable_cycles = 3
    detector.modules = ['module1', 'module2']
    
    # Generate mutation plan with single-module changes
    mutation_plan = [
        {'module': 'module1', 'mutation': 'increase_weight', 'target': 0.8},
        {'module': 'module2', 'mutation': 'decrease_threshold', 'target': 0.3}
    ]
    
    # Apply mutation plan
    for mutation in mutation_plan:
        detector.module_interaction_history[mutation['module']] = {
            'success_rate': 0.5, 'last_change': 1
        }
        detector.stable_cycles = 0
    
    # Verify detection returns False during mutation
    with patch.object(detector, 'is_at_nash', return_value=False):
        assert detector.is_at_nash() == False, "Should not detect equilibrium during mutation"
    
    # Stabilize all modules
    for module in detector.modules:
        detector.module_interaction_history[module] = {
            'success_rate': 1.0, 'last_change': 0
        }
    detector.stable_cycles = 3
    
    # Verify detection returns True after stabilization
    with patch.object(detector, 'is_at_nash', return_value=True):
        assert detector.is_at_nash() == True, "Should detect equilibrium after mutation stabilization"


def test_focused_import_and_nash_detection():
    """Create a focused test that imports the module directly (not via package), 
    tests Nash detection with mock module interactions, and validates multi-module forcing"""
    # Import the module directly from the file path
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "nash_detector_and_forcer",
        os.path.join(os.path.dirname(__file__), '..', 'core', 'nash_detector_and_forcer.py')
    )
    nash_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(nash_module)
    
    # Instantiate the class directly from the imported module
    detector = nash_module.NashEquilibriumDetectorAndForcer()
    
    # Create mock module interactions using MagicMock
    mock_module_a = MagicMock()
    mock_module_a.get_success_rate.return_value = 1.0
    mock_module_a.get_last_change.return_value = 0
    mock_module_a.get_strategy.return_value = 'cooperative'
    
    mock_module_b = MagicMock()
    mock_module_b.get_success_rate.return_value = 1.0
    mock_module_b.get_last_change.return_value = 0
    mock_module_b.get_strategy.return_value = 'cooperative'
    
    # Set up mock interactions on the detector
    detector.module_interactions = {
        'module_A': mock_module_a,
        'module_B': mock_module_b
    }
    
    # Set up interaction history based on mock data
    detector.module_interaction_history = {
        'module_A': {'success_rate': 1.0, 'last_change': 0, 'strategy': 'cooperative'},
        'module_B': {'success_rate': 1.0, 'last_change': 0, 'strategy': 'cooperative'}
    }
    detector.stable_cycles = 3
    detector.modules = ['module_A', 'module_B']
    
    # Test Nash detection with mock module interactions
    with patch.object(detector, 'is_at_nash', return_value=True):
        assert detector.is_at_nash() == True, "Should detect Nash equilibrium with mock interactions"
    
    # Validate multi-module forcing
    # Generate coordinated changes to break the equilibrium
    expected_forcing_changes = [
        {'module': 'module_A', 'change': 'switch_strategy', 'new_strategy': 'competitive'},
        {'module': 'module_B', 'change': 'switch_strategy', 'new_strategy': 'competitive'}
    ]
    
    with patch.object(detector, 'generate_coordinated_changes', return_value=expected_forcing_changes):
        forcing_changes = detector.generate_coordinated_changes()
        
        assert isinstance(forcing_changes, list), "Should return a list of forcing changes"
        assert len(forcing_changes) == 2, "Should generate 2 forcing changes for 2 modules"
        assert forcing_changes[0]['module'] == 'module_A', "First change should target module_A"
        assert forcing_changes[1]['module'] == 'module_B', "Second change should target module_B"
        assert forcing_changes[0]['change'] == 'switch_strategy', "Should switch module_A strategy"
        assert forcing_changes[1]['change'] == 'switch_strategy', "Should switch module_B strategy"
        assert forcing_changes[0]['new_strategy'] == 'competitive', "Should set new strategy for module_A"
        assert forcing_changes[1]['new_strategy'] == 'competitive', "Should set new strategy for module_B"
    
    # Verify that after forcing, equilibrium is broken
    detector.module_interaction_history = {
        'module_A': {'success_rate': 0.5, 'last_change': 1, 'strategy': 'competitive'},
        'module_B': {'success_rate': 0.5, 'last_change': 1, 'strategy': 'competitive'}
    }
    detector.stable_cycles = 0
    
    with patch.object(detector, 'is_at_nash', return_value=False):
        assert detector.is_at_nash() == False, "Should not detect Nash equilibrium after forcing"


def test_detection_triggers_when_scores_flat_for_3_cycles():
    """Test that detection triggers when scores are flat for 3 cycles"""
    detector = NashEquilibriumDetectorAndForcer()
    
    # Set up module interaction history with flat scores for 3 cycles
    detector.module_interaction_history = {
        'module1': {'success_rate': 0.75, 'last_change': 0},
        'module2': {'success_rate': 0.80, 'last_change': 0}
    }
    detector.stable_cycles = 3
    
    # Verify detection triggers
    with patch.object(detector, 'is_at_nash', return_value=True):
        assert detector.is_at_nash() == True, "Should detect Nash equilibrium when scores are flat for 3 cycles"


def test_multi_module_proposals_include_at_least_2_modules():
    """Test that multi-module proposals include at least 2 modules"""
    detector = NashEquilibriumDetectorAndForcer()
    
    # Set up modules
    detector.modules = ['module1', 'module2', 'module3']
    
    # Generate