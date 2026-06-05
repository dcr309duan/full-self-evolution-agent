import unittest
from unittest.mock import MagicMock, patch
import sys
import os

# Add the parent directory to the path so we can import the modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from meta_evaluation import MetaEvaluationLoop
from mutation_engine import MutationEngine
from objective_manager import ObjectiveManager

class TestMetaEvaluationStagnation(unittest.TestCase):
    """Test suite for meta-evaluation stagnation detection and objective switching."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.objective_manager = ObjectiveManager()
        self.mutation_engine = MutationEngine()
        self.meta_eval = MetaEvaluationLoop(
            objective_manager=self.objective_manager,
            mutation_engine=self.mutation_engine
        )
        
        # Initialize with 'add_capabilities' as the current objective
        self.objective_manager.current_objective = 'add_capabilities'
        
    def simulate_stagnation(self, num_cycles=5):
        """Simulate num_cycles of no improvement in performance."""
        for _ in range(num_cycles):
            # Each cycle returns the same performance score (no improvement)
            performance_score = 0.5  # Stagnant score
            self.meta_eval.evaluate_cycle(performance_score)
            
    def test_objective_switches_after_stagnation(self):
        """Test that objective switches from 'add_capabilities' to 'refactor_architecture' after stagnation."""
        # Initially the objective should be 'add_capabilities'
        self.assertEqual(
            self.objective_manager.current_objective,
            'add_capabilities',
            "Initial objective should be 'add_capabilities'"
        )
        
        # Simulate 5 cycles of stagnation
        self.simulate_stagnation(5)
        
        # After stagnation, the objective should switch to 'refactor_architecture'
        self.assertEqual(
            self.objective_manager.current_objective,
            'refactor_architecture',
            "Objective should switch to 'refactor_architecture' after 5 cycles of stagnation"
        )
        
    def test_objective_does_not_switch_with_improvement(self):
        """Test that objective does not switch when there is improvement."""
        # Simulate cycles with improvement
        for i in range(5):
            performance_score = 0.5 + (i * 0.1)  # Increasing scores
            self.meta_eval.evaluate_cycle(performance_score)
        
        # Objective should remain 'add_capabilities'
        self.assertEqual(
            self.objective_manager.current_objective,
            'add_capabilities',
            "Objective should remain 'add_capabilities' when performance is improving"
        )
        
    def test_mutation_engine_respects_new_objective(self):
        """Test that mutation engine prefers refactoring operators after objective switch."""
        # First, trigger stagnation to switch objective
        self.simulate_stagnation(5)
        
        # Now the objective should be 'refactor_architecture'
        self.assertEqual(
            self.objective_manager.current_objective,
            'refactor_architecture',
            "Objective should be 'refactor_architecture' after stagnation"
        )
        
        # Get the mutation operators preferred by the engine for the current objective
        preferred_operators = self.mutation_engine.get_preferred_operators(
            self.objective_manager.current_objective
        )
        
        # Verify that refactoring operators are preferred
        self.assertIn(
            'refactor',
            preferred_operators,
            "Mutation engine should prefer 'refactor' operators when objective is 'refactor_architecture'"
        )
        
        # Verify that 'add_capabilities' operators are not preferred
        self.assertNotIn(
            'add_capability',
            preferred_operators,
            "Mutation engine should not prefer 'add_capability' operators when objective is 'refactor_architecture'"
        )
        
    def test_stagnation_counter_resets_on_improvement(self):
        """Test that the stagnation counter resets when improvement is detected."""
        # Simulate 3 cycles of stagnation
        self.simulate_stagnation(3)
        
        # Check that stagnation count is 3
        self.assertEqual(
            self.meta_eval.stagnation_count,
            3,
            "Stagnation count should be 3 after 3 stagnant cycles"
        )
        
        # Simulate an improvement
        self.meta_eval.evaluate_cycle(0.8)  # Higher score
        
        # Stagnation count should reset to 0
        self.assertEqual(
            self.meta_eval.stagnation_count,
            0,
            "Stagnation count should reset to 0 after improvement"
        )
        
    def test_exact_stagnation_threshold(self):
        """Test that objective switches exactly at the threshold (5 cycles)."""
        # Simulate 4 cycles of stagnation (should not switch yet)
        self.simulate_stagnation(4)
        
        self.assertEqual(
            self.objective_manager.current_objective,
            'add_capabilities',
            "Objective should not switch after only 4 cycles of stagnation"
        )
        
        # Simulate the 5th cycle of stagnation (should switch)
        self.meta_eval.evaluate_cycle(0.5)  # Still stagnant
        
        self.assertEqual(
            self.objective_manager.current_objective,
            'refactor_architecture',
            "Objective should switch after exactly 5 cycles of stagnation"
        )
        
    def test_mutation_operator_selection_after_switch(self):
        """Test that mutation operators are selected based on the new objective."""
        # Trigger stagnation and switch objective
        self.simulate_stagnation(5)
        
        # Mock the mutation selection to verify it uses the new objective
        with patch.object(self.mutation_engine, 'select_mutation') as mock_select:
            mock_select.return_value = 'refactor_method'
            
            # Perform a mutation operation
            self.meta_eval.perform_mutation()
            
            # Verify that select_mutation was called with the new objective
            mock_select.assert_called_once_with(
                objective='refactor_architecture'
            )

if __name__ == '__main__':
    unittest.main()