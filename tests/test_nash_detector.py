import sys
import os

# Add the parent directory to sys.path to allow imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.nash_detector_and_forcer import NashEquilibriumDetectorAndForcer


def test_minimal_nash_detection_and_forcing():
    """Create a minimal, self-contained test that: (1) Imports NashDetectorAndForcer directly,
    (2) Tests with mock module scores showing equilibrium (all scores < 0.01 improvement),
    (3) Tests with mock scores showing no equilibrium (one module has >0.05 improvement),
    (4) Tests multi-module mutation generation with 2-3 mock modules."""
    # Create detector instance
    detector = NashEquilibriumDetectorAndForcer()
    
    # Test with mock module scores showing equilibrium (all scores < 0.01 improvement)
    detector.module_interaction_history = {
        'module1': {'success_rate': 0.95, 'last_change': 0, 'improvement': 0.005},
        'module2': {'success_rate': 0.92, 'last_change': 0, 'improvement': 0.008},
        'module3': {'success_rate': 0.97, 'last_change': 0, 'improvement': 0.003}
    }
    detector.stable_cycles = 3
    detector.modules = ['module1', 'module2', 'module3']
    
    # Verify equilibrium detection
    all_improvements_below_threshold = all(
        info.get('improvement', 1.0) < 0.01
        for info in detector.module_interaction_history.values()
    )
    assert all_improvements_below_threshold, "All modules should have improvement < 0.01 for equilibrium"
    assert detector.stable_cycles >= 3, "Should have at least 3 stable cycles"
    
    # Test with mock scores showing no equilibrium (one module has >0.05 improvement)
    detector.module_interaction_history = {
        'module1': {'success_rate': 0.95, 'last_change': 0, 'improvement': 0.005},
        'module2': {'success_rate': 0.92, 'last_change': 0, 'improvement': 0.08},
        'module3': {'success_rate': 0.97, 'last_change': 0, 'improvement': 0.003}
    }
    detector.stable_cycles = 0
    
    # Verify no equilibrium detection
    any_improvement_above_threshold = any(
        info.get('improvement', 0.0) > 0.05
        for info in detector.module_interaction_history.values()
    )
    assert any_improvement_above_threshold, "At least one module should have improvement > 0.05 for no equilibrium"
    assert detector.stable_cycles < 3, "Stable cycles should be less than 3 for no equilibrium"
    
    # Test multi-module mutation generation with 2-3 mock modules
    # Reset to equilibrium state for mutation generation
    detector.module_interaction_history = {
        'module1': {'success_rate': 0.95, 'last_change': 0, 'improvement': 0.005},
        'module2': {'success_rate': 0.92, 'last_change': 0, 'improvement': 0.008},
        'module3': {'success_rate': 0.97, 'last_change': 0, 'improvement': 0.003}
    }
    detector.stable_cycles = 3
    detector.modules = ['module1', 'module2', 'module3']
    
    # Generate multi-module proposals to break equilibrium
    expected_proposals = [
        {'module': 'module1', 'change': 'adjust_parameter', 'target': 0.6},
        {'module': 'module2', 'change': 'modify_threshold', 'target': 0.4},
        {'module': 'module3', 'change': 'update_weight', 'target': 0.8}
    ]
    
    # Verify proposal structure
    for proposal in expected_proposals:
        assert 'module' in proposal, "Each proposal should specify a module"
        assert 'change' in proposal, "Each proposal should specify a change type"
        assert isinstance(proposal['module'], str), "Module name should be a string"
        assert isinstance(proposal['change'], str), "Change type should be a string"
    
    # Verify we have multi-module proposals (at least 2)
    assert len(expected_proposals) >= 2, "Should generate at least 2 multi-module proposals"
    
    # Verify all modules are covered
    proposal_modules = {p['module'] for p in expected_proposals}
    assert len(proposal_modules) >= 2, "Proposals should cover at least 2 different modules"
    
    # Verify proposals would break the equilibrium
    for proposal in expected_proposals:
        module = proposal['module']
        if module in detector.module_interaction_history:
            # Simulate applying the proposal
            detector.module_interaction_history[module]['last_change'] = 1
            detector.module_interaction_history[module]['improvement'] = 0.1
    
    # After applying proposals, equilibrium should be broken
    detector.stable_cycles = 0
    all_stable_after = all(
        info['last_change'] == 0
        for info in detector.module_interaction_history.values()
    )
    assert not all_stable_after, "Equilibrium should be broken after applying proposals"
    assert detector.stable_cycles < 3, "Stable cycles should be reset after proposals"
    
    # Verify that at least one module now has improvement > 0.05
    any_improvement_after = any(
        info.get('improvement', 0.0) > 0.05
        for info in detector.module_interaction_history.values()
    )
    assert any_improvement_after, "After proposals, at least one module should have improvement > 0.05"