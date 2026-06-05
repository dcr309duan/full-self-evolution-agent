import sys
import os

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


if __name__ == '__main__':
    test_import_no_errors()
    test_basic_detection()
    test_coordinated_change_generation()
    print("All tests passed!")