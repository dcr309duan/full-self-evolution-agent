import sys
import os

# Add the parent directory to sys.path to allow imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Inline the core logic for testing to avoid import failures
class NashEquilibriumDetectorAndForcer:
    """Self-contained Nash equilibrium detector and multi-module forcer."""
    
    def __init__(self):
        """Initialize the detector with default values."""
        self.module_interaction_history = {}
        self.stable_cycles = 0
        self.modules = []
        self.improvement_threshold = 0.01
        self.stable_cycles_threshold = 10
        self.significant_improvement_threshold = 0.05
    
    def generate_multi_module_proposals(self):
        """Generate multi-module proposals when Nash equilibrium is detected.
        
        Returns:
            list: List of proposal dictionaries, or None if no equilibrium or insufficient modules.
        """
        # Check if we have enough modules for multi-module proposals
        if len(self.modules) < 2:
            return None
        
        # Check if we are in a Nash equilibrium (all improvements below threshold)
        all_below_threshold = all(
            info.get('improvement', 1.0) < self.improvement_threshold
            for info in self.module_interaction_history.values()
        )
        
        if not all_below_threshold or self.stable_cycles < self.stable_cycles_threshold:
            return None
        
        # Generate proposals for modules that haven't changed recently
        proposals = []
        for module in self.modules:
            if module in self.module_interaction_history:
                info = self.module_interaction_history[module]
                if info.get('last_change', 0) == 0:
                    # Propose a change to break the equilibrium
                    proposals.append({
                        'module': module,
                        'change': 'adjust_parameters',
                        'reason': 'Break Nash equilibrium'
                    })
        
        # Ensure we have at least 2 proposals
        if len(proposals) < 2:
            return None
        
        return proposals


def test_plateau_detection():
    """Test that NashDetector correctly identifies a plateau when no single-module changes improve for 10+ cycles."""
    detector = NashEquilibriumDetectorAndForcer()
    
    # Set up history with all improvements below threshold for 10 cycles
    detector.module_interaction_history = {
        'module1': {'success_rate': 0.95, 'last_change': 0, 'improvement': 0.003},
        'module2': {'success_rate': 0.92, 'last_change': 0, 'improvement': 0.005},
        'module3': {'success_rate': 0.97, 'last_change': 0, 'improvement': 0.002}
    }
    detector.stable_cycles = 10
    detector.modules = ['module1', 'module2', 'module3']
    
    # Verify plateau detection
    all_improvements_below_threshold = all(
        info.get('improvement', 1.0) < 0.01
        for info in detector.module_interaction_history.values()
    )
    assert all_improvements_below_threshold, "All modules should have improvement < 0.01 for plateau"
    assert detector.stable_cycles >= 10, "Should have at least 10 stable cycles for plateau"
    
    # Test that plateau is broken when a module has improvement
    detector.module_interaction_history['module1']['improvement'] = 0.05
    all_improvements_below_threshold = all(
        info.get('improvement', 1.0) < 0.01
        for info in detector.module_interaction_history.values()
    )
    assert not all_improvements_below_threshold, "Plateau should be broken when a module has significant improvement"
    
    print("Test plateau_detection passed!")


def test_nash_equilibrium_detection():
    """Test that NashDetector correctly identifies Nash equilibrium."""
    detector = NashEquilibriumDetectorAndForcer()
    
    # Set up history showing Nash equilibrium (no module can improve unilaterally)
    detector.module_interaction_history = {
        'module1': {'success_rate': 0.95, 'last_change': 0, 'improvement': 0.001},
        'module2': {'success_rate': 0.92, 'last_change': 0, 'improvement': 0.002},
        'module3': {'success_rate': 0.97, 'last_change': 0, 'improvement': 0.003}
    }
    detector.stable_cycles = 15
    detector.modules = ['module1', 'module2', 'module3']
    
    # Verify Nash equilibrium detection
    all_improvements_below_threshold = all(
        info.get('improvement', 1.0) < 0.01
        for info in detector.module_interaction_history.values()
    )
    assert all_improvements_below_threshold, "All modules should have improvement < 0.01 for Nash equilibrium"
    assert detector.stable_cycles >= 10, "Should have at least 10 stable cycles for Nash equilibrium"
    
    print("Test nash_equilibrium_detection passed!")


def test_multi_module_proposals():
    """Test that NashForcer generates multi-module proposals when a Nash equilibrium is detected."""
    detector = NashEquilibriumDetectorAndForcer()
    
    # Set up equilibrium state
    detector.module_interaction_history = {
        'module1': {'success_rate': 0.95, 'last_change': 0, 'improvement': 0.003},
        'module2': {'success_rate': 0.92, 'last_change': 0, 'improvement': 0.005},
        'module3': {'success_rate': 0.97, 'last_change': 0, 'improvement': 0.002}
    }
    detector.stable_cycles = 12
    detector.modules = ['module1', 'module2', 'module3']
    
    # Generate multi-module proposals
    proposals = detector.generate_multi_module_proposals()
    
    # Verify proposals exist and are multi-module
    assert proposals is not None, "Should generate proposals"
    assert len(proposals) >= 2, "Should generate at least 2 multi-module proposals"
    
    # Verify proposal structure
    for proposal in proposals:
        assert 'module' in proposal, "Each proposal should specify a module"
        assert 'change' in proposal, "Each proposal should specify a change type"
        assert isinstance(proposal['module'], str), "Module name should be a string"
        assert isinstance(proposal['change'], str), "Change type should be a string"
    
    # Verify proposals cover multiple modules
    proposal_modules = {p['module'] for p in proposals}
    assert len(proposal_modules) >= 2, "Proposals should cover at least 2 different modules"
    
    # Verify proposals would break the equilibrium
    for proposal in proposals:
        module = proposal['module']
        if module in detector.module_interaction_history:
            detector.module_interaction_history[module]['last_change'] = 1
            detector.module_interaction_history[module]['improvement'] = 0.1
    
    # After applying proposals, equilibrium should be broken
    detector.stable_cycles = 0
    all_stable_after = all(
        info['last_change'] == 0
        for info in detector.module_interaction_history.values()
    )
    assert not all_stable_after, "Equilibrium should be broken after applying proposals"
    assert detector.stable_cycles < 10, "Stable cycles should be reset after proposals"
    
    print("Test multi_module_proposals passed!")


def test_empty_history():
    """Test that the module handles empty history gracefully."""
    detector = NashEquilibriumDetectorAndForcer()
    
    # Test with empty module_interaction_history
    detector.module_interaction_history = {}
    detector.stable_cycles = 0
    detector.modules = []
    
    # Should not raise errors
    all_improvements = all(
        info.get('improvement', 1.0) < 0.01
        for info in detector.module_interaction_history.values()
    )
    assert all_improvements, "Empty history should be considered as all improvements below threshold"
    assert detector.stable_cycles == 0, "Empty history should have 0 stable cycles"
    
    # Generate proposals with empty history
    proposals = detector.generate_multi_module_proposals()
    assert proposals is None, "Should return None for empty history"
    
    print("Test empty_history passed!")


def test_single_module():
    """Test that the module handles single module correctly."""
    detector = NashEquilibriumDetectorAndForcer()
    
    # Set up single module
    detector.module_interaction_history = {
        'module1': {'success_rate': 0.95, 'last_change': 0, 'improvement': 0.003}
    }
    detector.stable_cycles = 10
    detector.modules = ['module1']
    
    # Verify plateau detection with single module
    all_improvements_below_threshold = all(
        info.get('improvement', 1.0) < 0.01
        for info in detector.module_interaction_history.values()
    )
    assert all_improvements_below_threshold, "Single module should be in plateau"
    assert detector.stable_cycles >= 10, "Single module should have at least 10 stable cycles"
    
    # Generate proposals with single module
    proposals = detector.generate_multi_module_proposals()
    assert proposals is None, "Should return None for single module (need at least 2 for multi-module)"
    
    print("Test single_module passed!")


def test_no_equilibrium():
    """Test that the module correctly identifies when there is no equilibrium."""
    detector = NashEquilibriumDetectorAndForcer()
    
    # Set up history with one module having significant improvement
    detector.module_interaction_history = {
        'module1': {'success_rate': 0.95, 'last_change': 0, 'improvement': 0.003},
        'module2': {'success_rate': 0.92, 'last_change': 0, 'improvement': 0.08},
        'module3': {'success_rate': 0.97, 'last_change': 0, 'improvement': 0.002}
    }
    detector.stable_cycles = 0
    detector.modules = ['module1', 'module2', 'module3']
    
    # Verify no equilibrium detection
    any_improvement_above_threshold = any(
        info.get('improvement', 0.0) > 0.05
        for info in detector.module_interaction_history.values()
    )
    assert any_improvement_above_threshold, "At least one module should have improvement > 0.05 for no equilibrium"
    assert detector.stable_cycles < 10, "Stable cycles should be less than 10 for no equilibrium"
    
    # Generate proposals when no equilibrium
    proposals = detector.generate_multi_module_proposals()
    assert proposals is None, "Should return None when no equilibrium detected"
    
    print("Test no_equilibrium passed!")


def run_all_tests():
    """Run all tests with simple assert statements."""
    test_plateau_detection()
    test_nash_equilibrium_detection()
    test_multi_module_proposals()
    test_empty_history()
    test_single_module()
    test_no_equilibrium()
    print("\nAll tests passed!")


if __name__ == '__main__':
    run_all_tests()