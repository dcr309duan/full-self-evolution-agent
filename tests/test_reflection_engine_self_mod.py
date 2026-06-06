import unittest
from unittest.mock import Mock, patch, MagicMock
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.reflection_engine_self_mod import (
    ReflectionEngineSelfMod,
    MutationResult,
    MutationType,
    SelfModError,
    generate_mutation,
    apply_mutation,
    rollback_mutation,
    compare_metrics,
    collect_metrics
)

class TestReflectionEngineSelfMod(unittest.TestCase):
    
    def setUp(self):
        self.engine = ReflectionEngineSelfMod()
        self.engine.mutation_history = []
        self.engine.current_prompt = "Original test prompt with constraints"
        self.engine.metrics_history = []
        
    def test_basic_mutation_generation_add_constraint(self):
        """Test generating a mutation that adds a constraint"""
        mutation = generate_mutation(MutationType.ADD_CONSTRAINT, "New constraint")
        self.assertIsInstance(mutation, MutationResult)
        self.assertEqual(mutation.mutation_type, MutationType.ADD_CONSTRAINT)
        self.assertIn("New constraint", mutation.payload)
        
    def test_basic_mutation_generation_delete_constraint(self):
        """Test generating a mutation that deletes a constraint"""
        mutation = generate_mutation(MutationType.DELETE_CONSTRAINT, "constraint_to_remove")
        self.assertIsInstance(mutation, MutationResult)
        self.assertEqual(mutation.mutation_type, MutationType.DELETE_CONSTRAINT)
        self.assertIn("constraint_to_remove", mutation.payload)
        
    def test_apply_mutation_add_constraint(self):
        """Test applying an add constraint mutation to the prompt"""
        original_prompt = "Test prompt"
        mutation = MutationResult(
            mutation_type=MutationType.ADD_CONSTRAINT,
            payload="New constraint",
            success=True
        )
        modified_prompt = apply_mutation(original_prompt, mutation)
        self.assertIn("New constraint", modified_prompt)
        self.assertNotEqual(modified_prompt, original_prompt)
        
    def test_apply_mutation_delete_constraint(self):
        """Test applying a delete constraint mutation to the prompt"""
        original_prompt = "Test prompt with constraint_to_remove"
        mutation = MutationResult(
            mutation_type=MutationType.DELETE_CONSTRAINT,
            payload="constraint_to_remove",
            success=True
        )
        modified_prompt = apply_mutation(original_prompt, mutation)
        self.assertNotIn("constraint_to_remove", modified_prompt)
        
    def test_metrics_collection_accuracy(self):
        """Test that metrics are collected accurately"""
        test_metrics = {
            'accuracy': 0.85,
            'completion_rate': 0.92,
            'response_time': 1.5,
            'error_rate': 0.05
        }
        collected = collect_metrics(test_metrics)
        self.assertIn('timestamp', collected)
        self.assertEqual(collected['accuracy'], 0.85)
        self.assertEqual(collected['completion_rate'], 0.92)
        self.assertEqual(collected['response_time'], 1.5)
        self.assertEqual(collected['error_rate'], 0.05)
        
    def test_metrics_collection_with_missing_fields(self):
        """Test metrics collection handles missing fields gracefully"""
        incomplete_metrics = {'accuracy': 0.75}
        collected = collect_metrics(incomplete_metrics)
        self.assertEqual(collected['accuracy'], 0.75)
        self.assertEqual(collected.get('completion_rate', 0.0), 0.0)
        
    def test_comparison_logic_greater_than_10_percent(self):
        """Test comparison logic with >10% threshold"""
        old_metrics = {'accuracy': 0.70, 'completion_rate': 0.80}
        new_metrics = {'accuracy': 0.85, 'completion_rate': 0.82}
        
        # Accuracy improved by more than 10%
        result = compare_metrics(old_metrics, new_metrics, threshold=0.10)
        self.assertTrue(result['accuracy']['improved'])
        self.assertGreater(result['accuracy']['change'], 0.10)
        
    def test_comparison_logic_below_threshold(self):
        """Test comparison logic with improvement below 10% threshold"""
        old_metrics = {'accuracy': 0.70, 'completion_rate': 0.80}
        new_metrics = {'accuracy': 0.72, 'completion_rate': 0.81}
        
        result = compare_metrics(old_metrics, new_metrics, threshold=0.10)
        self.assertFalse(result['accuracy']['improved'])
        self.assertLess(result['accuracy']['change'], 0.10)
        
    def test_rollback_on_failure(self):
        """Test rollback functionality when mutation fails"""
        original_prompt = "Original prompt"
        self.engine.current_prompt = original_prompt
        
        # Simulate a failed mutation
        failed_mutation = MutationResult(
            mutation_type=MutationType.ADD_CONSTRAINT,
            payload="Failed constraint",
            success=False,
            error="Test failure"
        )
        self.engine.mutation_history.append(failed_mutation)
        
        rollback_mutation(self.engine, failed_mutation)
        self.assertEqual(self.engine.current_prompt, original_prompt)
        self.assertEqual(len(self.engine.mutation_history), 0)
        
    def test_rollback_multiple_mutations(self):
        """Test rolling back multiple mutations in sequence"""
        original_prompt = "Original prompt"
        self.engine.current_prompt = original_prompt
        
        mutations = [
            MutationResult(MutationType.ADD_CONSTRAINT, "C1", success=True),
            MutationResult(MutationType.ADD_CONSTRAINT, "C2", success=True),
            MutationResult(MutationType.ADD_CONSTRAINT, "C3", success=False)
        ]
        
        for m in mutations:
            self.engine.mutation_history.append(m)
            
        # Rollback the failed mutation and its predecessors
        rollback_mutation(self.engine, mutations[-1])
        self.assertEqual(self.engine.current_prompt, original_prompt)
        self.assertEqual(len(self.engine.mutation_history), 0)
        
    def test_integration_with_evolution_orchestrator(self):
        """Test integration with evolution orchestrator"""
        mock_orchestrator = MagicMock()
        mock_orchestrator.apply_mutation = MagicMock(return_value=True)
        mock_orchestrator.rollback = MagicMock(return_value=True)
        
        self.engine.evolution_orchestrator = mock_orchestrator
        
        mutation = generate_mutation(MutationType.ADD_CONSTRAINT, "Integration test")
        result = self.engine.execute_mutation(mutation)
        
        self.assertTrue(result)
        mock_orchestrator.apply_mutation.assert_called_once_with(mutation)
        
    def test_integration_orchestrator_failure_handling(self):
        """Test that orchestrator failures trigger rollback"""
        mock_orchestrator = MagicMock()
        mock_orchestrator.apply_mutation = MagicMock(return_value=False)
        mock_orchestrator.rollback = MagicMock(return_value=True)
        
        self.engine.evolution_orchestrator = mock_orchestrator
        
        mutation = generate_mutation(MutationType.ADD_CONSTRAINT, "Should fail")
        result = self.engine.execute_mutation(mutation)
        
        self.assertFalse(result)
        mock_orchestrator.rollback.assert_called_once()
        
    def test_edge_case_empty_prompt(self):
        """Test handling of empty prompt"""
        self.engine.current_prompt = ""
        
        mutation = generate_mutation(MutationType.ADD_CONSTRAINT, "New constraint")
        with self.assertRaises(ValueError):
            apply_mutation("", mutation)
            
    def test_edge_case_all_constraints_deleted(self):
        """Test behavior when all constraints are deleted"""
        self.engine.current_prompt = "Constraint1, Constraint2, Constraint3"
        
        mutations = [
            MutationResult(MutationType.DELETE_CONSTRAINT, "Constraint1", success=True),
            MutationResult(MutationType.DELETE_CONSTRAINT, "Constraint2", success=True),
            MutationResult(MutationType.DELETE_CONSTRAINT, "Constraint3", success=True)
        ]
        
        for mutation in mutations:
            self.engine.current_prompt = apply_mutation(self.engine.current_prompt, mutation)
            
        self.assertEqual(self.engine.current_prompt.strip(), "")
        
    def test_edge_case_invalid_mutation(self):
        """Test handling of invalid mutation types"""
        with self.assertRaises(SelfModError):
            generate_mutation("INVALID_TYPE", "payload")
            
    def test_edge_case_none_payload(self):
        """Test handling of None payload"""
        with self.assertRaises(ValueError):
            generate_mutation(MutationType.ADD_CONSTRAINT, None)
            
    def test_metrics_collection_over_time(self):
        """Test that metrics are collected and stored over time"""
        test_metrics_list = [
            {'accuracy': 0.70, 'completion_rate': 0.80},
            {'accuracy': 0.75, 'completion_rate': 0.85},
            {'accuracy': 0.80, 'completion_rate': 0.90}
        ]
        
        for metrics in test_metrics_list:
            collected = collect_metrics(metrics)
            self.engine.metrics_history.append(collected)
            
        self.assertEqual(len(self.engine.metrics_history), 3)
        self.assertGreater(
            self.engine.metrics_history[-1]['accuracy'],
            self.engine.metrics_history[0]['accuracy']
        )
        
    def test_mutation_history_tracking(self):
        """Test that mutation history is properly tracked"""
        mutations = [
            generate_mutation(MutationType.ADD_CONSTRAINT, "C1"),
            generate_mutation(MutationType.ADD_CONSTRAINT, "C2"),
            generate_mutation(MutationType.DELETE_CONSTRAINT, "C1")
        ]
        
        for mutation in mutations:
            self.engine.mutation_history.append(mutation)
            
        self.assertEqual(len(self.engine.mutation_history), 3)
        self.assertEqual(
            self.engine.mutation_history[0].mutation_type,
            MutationType.ADD_CONSTRAINT
        )
        self.assertEqual(
            self.engine.mutation_history[-1].mutation_type,
            MutationType.DELETE_CONSTRAINT
        )

if __name__ == '__main__':
    unittest.main()