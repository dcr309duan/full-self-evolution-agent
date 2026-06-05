import unittest
from unittest.mock import MagicMock, patch
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.nash_detector import NashDetector
from core.module_interface import BaseModule


class MockModule(BaseModule):
    """Mock module with controllable fitness function for testing."""
    
    def __init__(self, name, fitness_func, dependencies=None):
        super().__init__(name)
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
        """Set up three mock modules with interdependent fitness functions."""
        self.detector = NashDetector()
        
        # Module A: fitness depends on its own state and Module B's state
        def fitness_a(state):
            a_val = state.get('module_a', 0)
            b_val = state.get('module_b', 0)
            # Higher fitness when a_val is close to b_val
            return 10 - abs(a_val - b_val)
        
        # Module B: fitness depends on Module A and Module C
        def fitness_b(state):
            a_val = state.get('module_a', 0)
            c_val = state.get('module_c', 0)
            # Higher fitness when a_val + c_val is close to 10
            return 10 - abs(a_val + c_val - 10)
        
        # Module C: fitness depends on Module B only
        def fitness_c(state):
            b_val = state.get('module_b', 0)
            # Higher fitness when b_val is close to 5
            return 10 - abs(b_val - 5)
        
        self.module_a = MockModule('module_a', fitness_a, dependencies=['module_b'])
        self.module_b = MockModule('module_b', fitness_b, dependencies=['module_a', 'module_c'])
        self.module_c = MockModule('module_c', fitness_c, dependencies=['module_b'])
        
        self.modules = {
            'module_a': self.module_a,
            'module_b': self.module_b,
            'module_c': self.module_c
        }
        
        # Initial state that is a Nash equilibrium
        # For equilibrium: module_a=5, module_b=5, module_c=5
        # - Module A: 10 - |5-5| = 10 (optimal given B=5)
        # - Module B: 10 - |5+5-10| = 10 (optimal given A=5, C=5)
        # - Module C: 10 - |5-5| = 10 (optimal given B=5)
        self.equilibrium_state = {
            'module_a': 5,
            'module_b': 5,
            'module_c': 5
        }
        
        # Non-equilibrium state
        self.non_equilibrium_state = {
            'module_a': 2,
            'module_b': 8,
            'module_c': 1
        }
    
    def test_equilibrium_detection_single_changes_no_benefit(self):
        """Verify equilibrium detection when single changes have no benefit."""
        # Test that the equilibrium state is detected as equilibrium
        is_eq, deviations = self.detector.check_equilibrium(
            self.modules, self.equilibrium_state
        )
        
        self.assertTrue(is_eq, "Equilibrium state should be detected as equilibrium")
        self.assertEqual(len(deviations), 0, 
                         "No deviations should be found in equilibrium state")
        
        # Verify that each module cannot improve by changing alone
        for module_name, module in self.modules.items():
            current_fitness = module.get_fitness(self.equilibrium_state)
            # Try different single-module changes
            for new_val in [0, 2, 8, 10]:
                test_state = dict(self.equilibrium_state)
                test_state[module_name] = new_val
                new_fitness = module.get_fitness(test_state)
                self.assertLessEqual(
                    new_fitness, current_fitness,
                    f"Module {module_name} should not improve by changing to {new_val}"
                )
    
    def test_non_equilibrium_detection(self):
        """Verify that non-equilibrium states are correctly identified."""
        is_eq, deviations = self.detector.check_equilibrium(
            self.modules, self.non_equilibrium_state
        )
        
        self.assertFalse(is_eq, "Non-equilibrium state should not be detected as equilibrium")
        self.assertGreater(len(deviations), 0, 
                          "Deviations should be found in non-equilibrium state")
    
    def test_coordinated_change_detection(self):
        """Verify coordinated change detection produces multi-module mutation plans."""
        # Test with non-equilibrium state
        mutation_plans = self.detector.find_coordinated_changes(
            self.modules, self.non_equilibrium_state
        )
        
        self.assertIsNotNone(mutation_plans, "Should return mutation plans")
        self.assertGreater(len(mutation_plans), 0, 
                          "Should find at least one coordinated change")
        
        # Verify each plan has multiple modules
        for plan in mutation_plans:
            self.assertIn('modules', plan, "Each plan should specify modules")
            self.assertIn('new_state', plan, "Each plan should specify new state")
            self.assertGreaterEqual(
                len(plan['modules']), 2,
                "Coordinated change should involve at least 2 modules"
            )
            
            # Verify the plan improves fitness for all involved modules
            for module_name in plan['modules']:
                module = self.modules[module_name]
                current_fitness = module.get_fitness(self.non_equilibrium_state)
                new_fitness = module.get_fitness(plan['new_state'])
                self.assertGreater(
                    new_fitness, current_fitness,
                    f"Coordinated change should improve fitness for {module_name}"
                )
    
    def test_equilibrium_to_coordinated_plan(self):
        """Verify that equilibrium state produces no coordinated mutation plans."""
        mutation_plans = self.detector.find_coordinated_changes(
            self.modules, self.equilibrium_state
        )
        
        # Should either return empty list or None for equilibrium state
        if mutation_plans is None:
            pass  # None is acceptable for equilibrium
        else:
            self.assertEqual(
                len(mutation_plans), 0,
                "No coordinated changes should be found in equilibrium state"
            )
    
    def test_partial_equilibrium(self):
        """Test detection when some modules are in equilibrium but others are not."""
        # State where module_a is optimal given others, but others are not
        partial_state = {
            'module_a': 5,  # Optimal given B=5
            'module_b': 5,  # Optimal given A=5, C=5
            'module_c': 3   # Not optimal given B=5 (optimal would be 5)
        }
        
        is_eq, deviations = self.detector.check_equilibrium(
            self.modules, partial_state
        )
        
        self.assertFalse(is_eq, "Partial equilibrium should not be detected as full equilibrium")
        
        # Module C should be in deviations
        module_c_deviations = [d for d in deviations if d.get('module') == 'module_c']
        self.assertGreater(len(module_c_deviations), 0,
                          "Module C should have deviations")


if __name__ == '__main__':
    unittest.main()