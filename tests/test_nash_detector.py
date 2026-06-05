import sys
import os
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.nash_detector import NashEquilibriumDetector


class MockModule:
    """Minimal mock module for testing."""
    
    def __init__(self, name, fitness_func, dependencies=None):
        self.name = name
        self._fitness_func = fitness_func
        self._dependencies = dependencies or []
        self.mutation_count = 0
        
    def get_fitness(self, state):
        return self._fitness_func(state)
    
    def get_dependencies(self):
        return self._dependencies
    
    def mutate(self, state):
        self.mutation_count += 1
        return state


def test_import_no_errors():
    """Test that NashEquilibriumDetector can be imported without errors."""
    detector = NashEquilibriumDetector()
    assert detector is not None
    assert isinstance(detector, NashEquilibriumDetector)


def test_basic_detection():
    """Test basic equilibrium detection with mock data."""
    detector = NashEquilibriumDetector()
    
    # Create mock modules with interdependent fitness
    def fitness_a(state):
        a_val = state.get('module_a', 0)
        b_val = state.get('module_b', 0)
        return 10 - abs(a_val - b_val)
    
    def fitness_b(state):
        a_val = state.get('module_a', 0)
        c_val = state.get('module_c', 0)
        return 10 - abs(a_val + c_val - 10)
    
    def fitness_c(state):
        b_val = state.get('module_b', 0)
        return 10 - abs(b_val - 5)
    
    module_a = MockModule('module_a', fitness_a, dependencies=['module_b'])
    module_b = MockModule('module_b', fitness_b, dependencies=['module_a', 'module_c'])
    module_c = MockModule('module_c', fitness_c, dependencies=['module_b'])
    
    modules = {
        'module_a': module_a,
        'module_b': module_b,
        'module_c': module_c
    }
    
    # Test equilibrium state
    equilibrium_state = {
        'module_a': 5,
        'module_b': 5,
        'module_c': 5
    }
    
    is_eq, deviations = detector.check_equilibrium(modules, equilibrium_state)
    assert is_eq, "Equilibrium state should be detected as equilibrium"
    assert len(deviations) == 0, "No deviations should be found in equilibrium state"
    
    # Test non-equilibrium state
    non_equilibrium_state = {
        'module_a': 2,
        'module_b': 8,
        'module_c': 1
    }
    
    is_eq, deviations = detector.check_equilibrium(modules, non_equilibrium_state)
    assert not is_eq, "Non-equilibrium state should not be detected as equilibrium"
    assert len(deviations) > 0, "Deviations should be found in non-equilibrium state"


def test_coordinated_change_generation():
    """Test coordinated change generation produces valid mutation plans."""
    detector = NashEquilibriumDetector()
    
    def fitness_a(state):
        a_val = state.get('module_a', 0)
        b_val = state.get('module_b', 0)
        return 10 - abs(a_val - b_val)
    
    def fitness_b(state):
        a_val = state.get('module_a', 0)
        c_val = state.get('module_c', 0)
        return 10 - abs(a_val + c_val - 10)
    
    def fitness_c(state):
        b_val = state.get('module_b', 0)
        return 10 - abs(b_val - 5)
    
    module_a = MockModule('module_a', fitness_a, dependencies=['module_b'])
    module_b = MockModule('module_b', fitness_b, dependencies=['module_a', 'module_c'])
    module_c = MockModule('module_c', fitness_c, dependencies=['module_b'])
    
    modules = {
        'module_a': module_a,
        'module_b': module_b,
        'module_c': module_c
    }
    
    non_equilibrium_state = {
        'module_a': 2,
        'module_b': 8,
        'module_c': 1
    }
    
    # Test find_coordinated_changes
    mutation_plans = detector.find_coordinated_changes(modules, non_equilibrium_state)
    assert mutation_plans is not None, "Should return mutation plans"
    assert len(mutation_plans) > 0, "Should find at least one coordinated change"
    
    for plan in mutation_plans:
        assert 'modules' in plan, "Each plan should specify modules"
        assert 'new_state' in plan, "Each plan should specify new state"
        assert len(plan['modules']) >= 2, "Coordinated change should involve at least 2 modules"
        
        for module_name in plan['modules']:
            module = modules[module_name]
            current_fitness = module.get_fitness(non_equilibrium_state)
            new_fitness = module.get_fitness(plan['new_state'])
            assert new_fitness > current_fitness, f"Coordinated change should improve fitness for {module_name}"
    
    # Test generate_coordinated_changes
    mutation_plans2 = detector.generate_coordinated_changes(modules, non_equilibrium_state)
    assert mutation_plans2 is not None, "Should return mutation plans"
    assert len(mutation_plans2) > 0, "Should find at least one coordinated change"
    
    for plan in mutation_plans2:
        assert 'modules' in plan, "Each plan should specify modules"
        assert 'new_state' in plan, "Each plan should specify new state"
        assert len(plan['modules']) >= 2, "Coordinated change should involve at least 2 modules"
        
        for module_name in plan['modules']:
            module = modules[module_name]
            current_fitness = module.get_fitness(non_equilibrium_state)
            new_fitness = module.get_fitness(plan['new_state'])
            assert new_fitness > current_fitness, f"Coordinated change should improve fitness for {module_name}"
    
    # Test equilibrium state produces no coordinated changes
    equilibrium_state = {
        'module_a': 5,
        'module_b': 5,
        'module_c': 5
    }
    
    eq_plans = detector.find_coordinated_changes(modules, equilibrium_state)
    if eq_plans is not None:
        assert len(eq_plans) == 0, "No coordinated changes should be found in equilibrium state"
    
    eq_plans2 = detector.generate_coordinated_changes(modules, equilibrium_state)
    if eq_plans2 is not None:
        assert len(eq_plans2) == 0, "No coordinated changes should be found in equilibrium state"


def test_stagnant_cycles_detection():
    """Test that equilibrium detection triggers after 3 stagnant cycles."""
    detector = NashEquilibriumDetector()
    
    # Create mock modules with simple fitness functions
    def fitness_a(state):
        return 10 - abs(state.get('module_a', 0) - state.get('module_b', 0))
    
    def fitness_b(state):
        return 10 - abs(state.get('module_b', 0) - state.get('module_c', 0))
    
    def fitness_c(state):
        return 10 - abs(state.get('module_c', 0) - state.get('module_a', 0))
    
    module_a = MockModule('module_a', fitness_a, dependencies=['module_b'])
    module_b = MockModule('module_b', fitness_b, dependencies=['module_c'])
    module_c = MockModule('module_c', fitness_c, dependencies=['module_a'])
    
    modules = {
        'module_a': module_a,
        'module_b': module_b,
        'module_c': module_c
    }
    
    # Simulate stagnant state (same state for 3 cycles)
    stagnant_state = {
        'module_a': 5,
        'module_b': 5,
        'module_c': 5
    }
    
    # Cycle 1: Not stagnant yet
    is_stagnant = detector.check_stagnant_cycles(stagnant_state)
    assert not is_stagnant, "Cycle 1 should not be detected as stagnant"
    
    # Cycle 2: Still not stagnant
    is_stagnant = detector.check_stagnant_cycles(stagnant_state)
    assert not is_stagnant, "Cycle 2 should not be detected as stagnant"
    
    # Cycle 3: Should trigger stagnation detection
    is_stagnant = detector.check_stagnant_cycles(stagnant_state)
    assert is_stagnant, "Cycle 3 should trigger stagnation detection"
    
    # Verify equilibrium is detected after stagnation
    is_eq, deviations = detector.check_equilibrium(modules, stagnant_state)
    assert is_eq, "Stagnant state should be detected as equilibrium"
    assert len(deviations) == 0, "No deviations should be found in stagnant state"
    
    # Change state to break stagnation
    new_state = {
        'module_a': 3,
        'module_b': 7,
        'module_c': 4
    }
    
    # Reset stagnation counter by providing different state
    is_stagnant = detector.check_stagnant_cycles(new_state)
    assert not is_stagnant, "New state should reset stagnation detection"
    
    # Verify non-equilibrium after state change
    is_eq, deviations = detector.check_equilibrium(modules, new_state)
    assert not is_eq, "New state should not be equilibrium"
    assert len(deviations) > 0, "Deviations should be found in new state"


def test_force_coordinated_change_mutations():
    """Test that force_coordinated_change produces valid multi-module mutations."""
    detector = NashEquilibriumDetector()
    
    # Create mock modules with interdependent fitness
    def fitness_a(state):
        a_val = state.get('module_a', 0)
        b_val = state.get('module_b', 0)
        return 10 - abs(a_val - b_val)
    
    def fitness_b(state):
        a_val = state.get('module_a', 0)
        c_val = state.get('module_c', 0)
        return 10 - abs(a_val + c_val - 10)
    
    def fitness_c(state):
        b_val = state.get('module_b', 0)
        return 10 - abs(b_val - 5)
    
    module_a = MockModule('module_a', fitness_a, dependencies=['module_b'])
    module_b = MockModule('module_b', fitness_b, dependencies=['module_a', 'module_c'])
    module_c = MockModule('module_c', fitness_c, dependencies=['module_b'])
    
    modules = {
        'module_a': module_a,
        'module_b': module_b,
        'module_c': module_c
    }
    
    # Test with non-equilibrium state
    non_equilibrium_state = {
        'module_a': 2,
        'module_b': 8,
        'module_c': 1
    }
    
    # Force coordinated change
    mutation_plan = detector.force_coordinated_change(modules, non_equilibrium_state)
    
    # Verify mutation plan structure
    assert mutation_plan is not None, "Should return a mutation plan"
    assert 'modules' in mutation_plan, "Plan should specify modules"
    assert 'new_state' in mutation_plan, "Plan should specify new state"
    assert len(mutation_plan['modules']) >= 2, "Coordinated change should involve at least 2 modules"
    
    # Verify all specified modules are valid
    for module_name in mutation_plan['modules']:
        assert module_name in modules, f"Module {module_name} should exist in modules"
    
    # Verify fitness improvement for all involved modules
    for module_name in mutation_plan['modules']:
        module = modules[module_name]
        current_fitness = module.get_fitness(non_equilibrium_state)
        new_fitness = module.get_fitness(mutation_plan['new_state'])
        assert new_fitness > current_fitness, f"Coordinated change should improve fitness for {module_name}"
    
    # Verify the new state is valid (all required keys present)
    for module_name in modules:
        assert module_name in mutation_plan['new_state'], f"New state should include {module_name}"
    
    # Test with equilibrium state (should return None or empty plan)
    equilibrium_state = {
        'module_a': 5,
        'module_b': 5,
        'module_c': 5
    }
    
    eq_mutation_plan = detector.force_coordinated_change(modules, equilibrium_state)
    assert eq_mutation_plan is None or len(eq_mutation_plan.get('modules', [])) == 0, \
        "Should not force coordinated change in equilibrium state"
    
    # Test that mutation plan can be applied to modules
    test_state = non_equilibrium_state.copy()
    for module_name in mutation_plan['modules']:
        module = modules[module_name]
        test_state = module.mutate(mutation_plan['new_state'])
    
    # Verify modules were mutated
    for module in modules.values():
        if module.name in mutation_plan['modules']:
            assert module.mutation_count > 0, f"Module {module.name} should have been mutated"


def test_integration_10_cycles():
    """Minimal integration test: 10 cycles of module interactions with equilibrium detection."""
    detector = NashEquilibriumDetector()
    
    # Create mock modules with interdependent fitness
    def fitness_a(state):
        a_val = state.get('module_a', 0)
        b_val = state.get('module_b', 0)
        return 10 - abs(a_val - b_val)
    
    def fitness_b(state):
        a_val = state.get('module_a', 0)
        c_val = state.get('module_c', 0)
        return 10 - abs(a_val + c_val - 10)
    
    def fitness_c(state):
        b_val = state.get('module_b', 0)
        return 10 - abs(b_val - 5)
    
    module_a = MockModule('module_a', fitness_a, dependencies=['module_b'])
    module_b = MockModule('module_b', fitness_b, dependencies=['module_a', 'module_c'])
    module_c = MockModule('module_c', fitness_c, dependencies=['module_b'])
    
    modules = {
        'module_a': module_a,
        'module_b': module_b,
        'module_c': module_c
    }
    
    # Initial state
    state = {
        'module_a': 2,
        'module_b': 8,
        'module_c': 1
    }
    
    equilibrium_detected = False
    coordinated_changes_generated = False
    
    for cycle in range(10):
        # Check equilibrium
        is_eq, deviations = detector.check_equilibrium(modules, state)
        
        if is_eq:
            equilibrium_detected = True
            # Generate coordinated changes from equilibrium
            plans = detector.generate_coordinated_changes(modules, state)
            if plans and len(plans) > 0:
                coordinated_changes_generated = True
                # Apply first plan
                plan = plans[0]
                state = plan['new_state']
            else:
                # Force a change to break equilibrium
                plan = detector.force_coordinated_change(modules, state)
                if plan:
                    coordinated_changes_generated = True
                    state = plan['new_state']
        else:
            # Apply mutations based on deviations
            for module_name, deviation in deviations:
                module = modules[module_name]
                new_val = state[module_name] + deviation
                new_val = max(0, min(10, new_val))
                state[module_name] = new_val
        
        # Check stagnant cycles
        detector.check_stagnant_cycles(state)
    
    # Verify equilibrium detection occurred
    assert equilibrium_detected, "Equilibrium should be detected within 10 cycles"
    
    # Verify coordinated change generation occurred
    assert coordinated_changes_generated, "Coordinated changes should be generated within 10 cycles"


if __name__ == '__main__':
    test_import_no_errors()
    test_basic_detection()
    test_coordinated_change_generation()
    test_stagnant_cycles_detection()
    test_force_coordinated_change_mutations()
    test_integration_10_cycles()
    print("All tests passed!")