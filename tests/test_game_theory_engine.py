import unittest
from unittest.mock import Mock, patch
import sys
import os

# Add parent directory to path to import game_theory_engine
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from game_theory_engine import NashDetector, CoordinatedMutator, GameTheoryEngine

class TestNashDetector(unittest.TestCase):
    """Test suite for Nash equilibrium detection."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.detector = NashDetector()
        self.mock_agent = Mock()
        self.mock_agent.get_current_strategy.return_value = {
            'modules': ['module_a', 'module_b'],
            'parameters': {'param1': 0.5, 'param2': 0.3}
        }
        
    def test_identify_equilibrium_all_single_module_changes_fail(self):
        """Test that equilibrium is detected when all single-module changes fail."""
        # Mock the evaluation function to return False for all single-module changes
        def mock_evaluate_single_change(agent, module_name, change_type):
            return False  # All single-module changes fail
            
        self.detector.evaluate_single_change = mock_evaluate_single_change
        
        # Test with multiple modules
        modules = ['module_a', 'module_b', 'module_c']
        result = self.detector.detect_equilibrium(self.mock_agent, modules)
        
        self.assertTrue(result, "Should detect equilibrium when all single-module changes fail")
        
    def test_no_equilibrium_when_some_changes_succeed(self):
        """Test that equilibrium is not detected when some changes succeed."""
        # Mock evaluation to return True for one module
        call_count = [0]
        def mock_evaluate_single_change(agent, module_name, change_type):
            call_count[0] += 1
            if call_count[0] == 1:
                return True  # First module change succeeds
            return False
            
        self.detector.evaluate_single_change = mock_evaluate_single_change
        
        modules = ['module_a', 'module_b']
        result = self.detector.detect_equilibrium(self.mock_agent, modules)
        
        self.assertFalse(result, "Should not detect equilibrium when some changes succeed")


class TestCoordinatedMutator(unittest.TestCase):
    """Test suite for coordinated mutation generation."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.mutator = CoordinatedMutator()
        self.mock_agent = Mock()
        self.mock_agent.get_current_strategy.return_value = {
            'modules': ['module_a', 'module_b'],
            'parameters': {'param1': 0.5, 'param2': 0.3}
        }
        
    def test_generate_valid_multi_module_changes(self):
        """Test that coordinated mutator generates valid multi-module changes."""
        # Mock the validation function to accept valid changes
        def mock_validate_change(change):
            return True
            
        self.mutator.validate_change = mock_validate_change
        
        # Generate coordinated changes
        modules = ['module_a', 'module_b', 'module_c']
        changes = self.mutator.generate_coordinated_changes(self.mock_agent, modules)
        
        # Verify changes are valid
        for change in changes:
            self.assertTrue(change['is_valid'], "Each change should be valid")
            self.assertIn('modules', change, "Change should specify modules")
            self.assertIn('parameters', change, "Change should specify parameters")
            self.assertGreaterEqual(len(change['modules']), 2, 
                                   "Coordinated change should involve at least 2 modules")
            
    def test_coordinated_changes_maintain_invariants(self):
        """Test that coordinated changes maintain system invariants."""
        # Mock validation to check invariants
        def mock_validate_change(change):
            # Check that total parameter sum remains constant
            total_params = sum(change['parameters'].values())
            return abs(total_params - 0.8) < 0.01  # Original sum was 0.8
            
        self.mutator.validate_change = mock_validate_change
        
        changes = self.mutator.generate_coordinated_changes(self.mock_agent, 
                                                           ['module_a', 'module_b'])
        
        for change in changes:
            self.assertTrue(change['is_valid'], 
                           "Coordinated changes should maintain system invariants")


class TestGameTheoryEngine(unittest.TestCase):
    """Test suite for the main Game Theory Engine."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.engine = GameTheoryEngine()
        self.mock_agent = Mock()
        self.mock_agent.get_current_strategy.return_value = {
            'modules': ['module_a', 'module_b'],
            'parameters': {'param1': 0.5, 'param2': 0.3}
        }
        
    def test_system_escapes_equilibrium_within_two_cycles(self):
        """Test that system escapes equilibrium within 2 cycles of detection."""
        # Mock the detection to return True (equilibrium detected)
        self.engine.detector.detect_equilibrium = Mock(return_value=True)
        
        # Mock the mutator to generate valid changes
        self.engine.mutator.generate_coordinated_changes = Mock(return_value=[
            {'modules': ['module_a', 'module_b'], 
             'parameters': {'param1': 0.4, 'param2': 0.4},
             'is_valid': True}
        ])
        
        # Run the engine for up to 3 cycles
        for cycle in range(3):
            equilibrium_detected = self.engine.check_equilibrium(self.mock_agent)
            if equilibrium_detected:
                self.engine.escape_equilibrium(self.mock_agent)
                # After escape, equilibrium should no longer be detected
                self.engine.detector.detect_equilibrium = Mock(return_value=False)
                break
                
        self.assertLess(cycle, 2, 
                       "System should escape equilibrium within 2 cycles of detection")
        
    def test_coordinated_changes_dont_break_existing_functionality(self):
        """Test that coordinated changes don't break existing functionality."""
        # Define existing functionality as a set of functions
        existing_functions = {
            'function_a': lambda x: x * 2,
            'function_b': lambda x: x + 1,
            'function_c': lambda x: x ** 2
        }
        
        # Mock the agent to have these functions
        self.mock_agent.functions = existing_functions
        
        # Generate and apply coordinated changes
        changes = self.engine.mutator.generate_coordinated_changes(
            self.mock_agent, 
            ['module_a', 'module_b']
        )
        
        # Apply the first change
        change = changes[0]
        self.engine.apply_change(self.mock_agent, change)
        
        # Verify existing functions still work
        for func_name, func in existing_functions.items():
            test_input = 5
            expected_output = func(test_input)
            actual_output = self.mock_agent.functions[func_name](test_input)
            self.assertEqual(expected_output, actual_output,
                            f"Function {func_name} should still work after coordinated changes")
            
    def test_engine_handles_no_equilibrium(self):
        """Test that engine handles case when no equilibrium is detected."""
        # Mock detection to return False
        self.engine.detector.detect_equilibrium = Mock(return_value=False)
        
        # Run engine cycle
        result = self.engine.run_cycle(self.mock_agent)
        
        self.assertFalse(result['equilibrium_detected'], 
                        "Should not report equilibrium when none detected")
        self.assertIsNone(result['changes_applied'],
                         "Should not apply changes when no equilibrium")


if __name__ == '__main__':
    unittest.main()