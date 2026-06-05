import unittest
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


class TestNashDetector(unittest.TestCase):
    
    def setUp(self):
        self.detector = NashEquilibriumDetector()
        
        # Create 3 mock modules with interdependent fitness functions
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
        
        self.module_a = MockModule('module_a', fitness_a, dependencies=['module_b'])
        self.module_b = MockModule('module_b', fitness_b, dependencies=['module_a', 'module_c'])
        self.module_c = MockModule('module_c', fitness_c, dependencies=['module_b'])
        
        self.modules = {
            'module_a': self.module_a,
            'module_b': self.module_b,
            'module_c': self.module_c
        }
        
        self.equilibrium_state = {
            'module_a': 5,
            'module_b': 5,
            'module_c': 5
        }
        
        self.non_equilibrium_state = {
            'module_a': 2,
            'module_b': 8,
            'module_c': 1
        }
    
    def test_initial_detect_equilibrium_returns_false(self):
        """Test that detect_equilibrium() returns False initially."""
        result = self.detector.detect_equilibrium(self.modules, self.non_equilibrium_state)
        self.assertFalse(result, "detect_equilibrium should return False for non-equilibrium state")
    
    def test_detect_equilibrium_returns_true_after_simulation(self):
        """Test that after simulating equilibrium conditions, detect_equilibrium() returns True."""
        # First verify it returns False for non-equilibrium
        result = self.detector.detect_equilibrium(self.modules, self.non_equilibrium_state)
        self.assertFalse(result, "detect_equilibrium should return False initially")
        
        # Simulate equilibrium conditions by checking equilibrium state multiple times
        for _ in range(5):
            self.detector.check_equilibrium(self.modules, self.equilibrium_state)
        
        # Now detect_equilibrium should return True
        result = self.detector.detect_equilibrium(self.modules, self.equilibrium_state)
        self.assertTrue(result, "detect_equilibrium should return True after equilibrium conditions are simulated")
    
    def test_detection_with_mock_scores(self):
        """Test that equilibrium detection works with mock module data (stable success rates)."""
        # Test equilibrium detection with stable state
        is_eq, deviations = self.detector.check_equilibrium(self.modules, self.equilibrium_state)
        self.assertTrue(is_eq, "Equilibrium state should be detected as equilibrium")
        self.assertEqual(len(deviations), 0, "No deviations should be found in equilibrium state")
        
        # Test non-equilibrium detection
        is_eq, deviations = self.detector.check_equilibrium(self.modules, self.non_equilibrium_state)
        self.assertFalse(is_eq, "Non-equilibrium state should not be detected as equilibrium")
        self.assertGreater(len(deviations), 0, "Deviations should be found in non-equilibrium state")
    
    def test_force_coordinated_change_returns_valid_plan(self):
        """Test that force_coordinated_change returns a valid plan with at least 2 modules."""
        mutation_plan = self.detector.force_coordinated_change(self.modules, self.non_equilibrium_state)
        
        # Verify mutation plan structure
        self.assertIsNotNone(mutation_plan, "Should return a mutation plan")
        self.assertIn('modules', mutation_plan, "Plan should specify modules")
        self.assertIn('new_state', mutation_plan, "Plan should specify new state")
        
        # Verify at least 2 module targets
        num_modules = len(mutation_plan['modules'])
        self.assertGreaterEqual(num_modules, 2, "Coordinated change should involve at least 2 modules")
        
        # Verify all specified modules are valid
        for module_name in mutation_plan['modules']:
            self.assertIn(module_name, self.modules, f"Module {module_name} should exist in modules")
        
        # Verify fitness improvement for all involved modules
        for module_name in mutation_plan['modules']:
            module = self.modules[module_name]
            current_fitness = module.get_fitness(self.non_equilibrium_state)
            new_fitness = module.get_fitness(mutation_plan['new_state'])
            self.assertGreater(new_fitness, current_fitness, 
                             f"Coordinated change should improve fitness for {module_name}")
        
        # Verify the new state is valid (all required keys present)
        for module_name in self.modules:
            self.assertIn(module_name, mutation_plan['new_state'], 
                        f"New state should include {module_name}")
    
    def test_detector_resets_after_coordinated_change(self):
        """Test that the detector resets after a coordinated change is applied."""
        # First, detect non-equilibrium
        is_eq, deviations = self.detector.check_equilibrium(self.modules, self.non_equilibrium_state)
        self.assertFalse(is_eq, "Should detect non-equilibrium")
        
        # Force coordinated change
        mutation_plan = self.detector.force_coordinated_change(self.modules, self.non_equilibrium_state)
        self.assertIsNotNone(mutation_plan, "Should return a mutation plan")
        
        # Apply the coordinated change
        new_state = mutation_plan['new_state'].copy()
        for module_name in mutation_plan['modules']:
            module = self.modules[module_name]
            new_state = module.mutate(new_state)
        
        # Verify modules were mutated
        for module in self.modules.values():
            if module.name in mutation_plan['modules']:
                self.assertGreater(module.mutation_count, 0, 
                                 f"Module {module.name} should have been mutated")
        
        # Check that detector resets (should detect equilibrium in the new state)
        is_eq, deviations = self.detector.check_equilibrium(self.modules, new_state)
        # The new state should be closer to equilibrium
        self.assertTrue(is_eq or len(deviations) < len(self.modules), 
                       "After coordinated change, state should be closer to equilibrium")
        
        # Verify detector state is reset
        self.assertEqual(len(self.detector.deviation_history), 0, 
                        "Deviation history should be reset after coordinated change")
        self.assertEqual(self.detector.equilibrium_count, 0, 
                        "Equilibrium count should be reset after coordinated change")


if __name__ == '__main__':
    unittest.main()