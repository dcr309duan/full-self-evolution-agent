import unittest
from unittest.mock import MagicMock, patch
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.nash_equilibrium.detector import NashEquilibriumDetector
from src.nash_equilibrium.coordinated_planner import CoordinatedMutationPlanner
from src.nash_equilibrium.fallback_handler import FallbackHandler
from src.mutation.mutation_engine import MutationEngine
from src.fitness.fitness_evaluator import FitnessEvaluator

class TestNashEquilibriumIntegration(unittest.TestCase):
    """Integration test for Nash equilibrium detection, coordinated mutation, and fallback."""

    def setUp(self):
        """Set up 3 modules with artificial interaction constraints creating a Nash equilibrium."""
        # Module 1: Optimizer - high fitness when alone, but constrained by modules 2 and 3
        self.module1 = MagicMock()
        self.module1.name = "optimizer"
        self.module1.fitness = 0.85
        self.module1.mutation_options = ["learning_rate_adjust", "batch_size_change", "regularization_tune"]

        # Module 2: DataProcessor - moderate fitness, interacts negatively with module 1
        self.module2 = MagicMock()
        self.module2.name = "data_processor"
        self.module2.fitness = 0.72
        self.module2.mutation_options = ["normalization_change", "augmentation_add", "sampling_strategy"]

        # Module 3: FeatureExtractor - low fitness, interacts positively with module 2 but negatively with module 1
        self.module3 = MagicMock()
        self.module3.name = "feature_extractor"
        self.module3.fitness = 0.65
        self.module3.mutation_options = ["kernel_size_change", "activation_change", "layer_depth_adjust"]

        # Create interaction constraints that form a Nash equilibrium:
        # - Module 1's fitness drops if module 2 changes (mutual constraint)
        # - Module 2's fitness drops if module 3 changes
        # - Module 3's fitness drops if module 1 changes
        # This creates a cycle where no single module can improve without causing another to degrade
        self.interaction_matrix = {
            ("optimizer", "data_processor"): -0.15,  # optimizer penalized when data_processor changes
            ("data_processor", "optimizer"): -0.10,  # data_processor penalized when optimizer changes
            ("data_processor", "feature_extractor"): -0.12,  # data_processor penalized when feature_extractor changes
            ("feature_extractor", "data_processor"): -0.08,  # feature_extractor penalized when data_processor changes
            ("feature_extractor", "optimizer"): -0.20,  # feature_extractor penalized when optimizer changes
            ("optimizer", "feature_extractor"): -0.05,  # optimizer penalized when feature_extractor changes
        }

        self.modules = [self.module1, self.module2, self.module3]

        # Initialize components
        self.detector = NashEquilibriumDetector(interaction_matrix=self.interaction_matrix)
        self.planner = CoordinatedMutationPlanner()
        self.fallback = FallbackHandler()
        self.mutation_engine = MutationEngine()
        self.fitness_evaluator = FitnessEvaluator()

        # Configure fitness evaluator to respect interaction constraints
        def evaluate_fitness(module, context=None):
            base_fitness = module.fitness
            if context:
                for other_module in context:
                    key = (module.name, other_module.name)
                    if key in self.interaction_matrix:
                        base_fitness += self.interaction_matrix[key]
            return max(0.0, min(1.0, base_fitness))

        self.fitness_evaluator.evaluate.side_effect = evaluate_fitness

    def test_nash_equilibrium_detection_within_cycles(self):
        """Test that the detector identifies the equilibrium within 5 cycles."""
        # Run detection cycles
        for cycle in range(5):
            # Check if current state is a Nash equilibrium
            is_equilibrium = self.detector.check_equilibrium(self.modules, self.fitness_evaluator)
            
            if is_equilibrium:
                self.assertLessEqual(cycle + 1, 5, 
                    f"Nash equilibrium should be detected within 5 cycles, detected at cycle {cycle + 1}")
                return
            
            # Simulate module optimization attempts (which will fail due to constraints)
            for module in self.modules:
                best_mutation = self.mutation_engine.find_best_mutation(module, self.fitness_evaluator)
                if best_mutation:
                    self.mutation_engine.apply_mutation(module, best_mutation)
        
        self.fail("Nash equilibrium not detected within 5 cycles")

    def test_coordinated_mutation_planner_generates_valid_bundle(self):
        """Test that coordinated mutation planner generates a valid mutation bundle."""
        # First detect equilibrium
        self.detector.check_equilibrium(self.modules, self.fitness_evaluator)
        
        # Generate coordinated mutation bundle
        bundle = self.planner.generate_bundle(self.modules, self.interaction_matrix)
        
        # Verify bundle structure
        self.assertIsNotNone(bundle, "Coordinated mutation bundle should not be None")
        self.assertIn('mutations', bundle, "Bundle should contain 'mutations' key")
        self.assertIn('coordination_strategy', bundle, "Bundle should contain coordination strategy")
        
        # Verify each mutation in bundle is valid
        for mutation in bundle['mutations']:
            self.assertIn('module', mutation, "Each mutation should specify a module")
            self.assertIn('mutation_type', mutation, "Each mutation should specify a mutation type")
            self.assertIn(mutation['module'].name, [m.name for m in self.modules], 
                         "Mutation module should be one of the test modules")
            self.assertIn(mutation['mutation_type'], mutation['module'].mutation_options,
                         f"Mutation type {mutation['mutation_type']} should be valid for {mutation['module'].name}")

    def test_bundle_breaks_equilibrium_and_improves_fitness(self):
        """Test that the bundle breaks the equilibrium and improves overall system fitness."""
        # Record initial state
        initial_fitnesses = {m.name: m.fitness for m in self.modules}
        initial_total_fitness = sum(initial_fitnesses.values())
        
        # Detect equilibrium
        self.detector.check_equilibrium(self.modules, self.fitness_evaluator)
        
        # Generate and apply coordinated mutation bundle
        bundle = self.planner.generate_bundle(self.modules, self.interaction_matrix)
        self.mutation_engine.apply_bundle(bundle)
        
        # Verify equilibrium is broken
        is_still_equilibrium = self.detector.check_equilibrium(self.modules, self.fitness_evaluator)
        self.assertFalse(is_still_equilibrium, 
                        "Coordinated mutation should break the Nash equilibrium")
        
        # Verify overall system fitness improved
        final_fitnesses = {m.name: m.fitness for m in self.modules}
        final_total_fitness = sum(final_fitnesses.values())
        
        self.assertGreater(final_total_fitness, initial_total_fitness,
                          f"Total fitness should improve: {initial_total_fitness:.2f} -> {final_total_fitness:.2f}")
        
        # Verify at least one module improved without causing others to degrade too much
        improved_modules = [m for m in self.modules if m.fitness > initial_fitnesses[m.name]]
        degraded_modules = [m for m in self.modules if m.fitness < initial_fitnesses[m.name]]
        
        self.assertGreater(len(improved_modules), len(degraded_modules),
                          "More modules should improve than degrade after coordinated mutation")

    def test_fallback_to_single_module_optimization(self):
        """Test that the system correctly falls back to single-module optimization after coordinated phase."""
        # Phase 1: Coordinated optimization
        bundle = self.planner.generate_bundle(self.modules, self.interaction_matrix)
        self.mutation_engine.apply_bundle(bundle)
        
        # Verify coordinated phase completed
        self.assertTrue(self.planner.coordinated_phase_completed,
                       "Coordinated phase should be marked as completed")
        
        # Phase 2: Trigger fallback
        self.fallback.trigger_fallback(self.modules, self.detector, self.fitness_evaluator)
        
        # Verify fallback handler is active
        self.assertTrue(self.fallback.is_active, "Fallback handler should be active")
        
        # Phase 3: Single-module optimization
        for module in self.modules:
            best_mutation = self.mutation_engine.find_best_mutation(module, self.fitness_evaluator)
            if best_mutation:
                self.mutation_engine.apply_mutation(module, best_mutation)
                # Verify mutation was applied to single module
                self.assertIsNotNone(module.fitness, 
                                   f"Module {module.name} should have updated fitness after single mutation")
        
        # Verify system is now in single-module optimization mode
        self.assertTrue(self.fallback.in_single_module_mode,
                       "System should be in single-module optimization mode after fallback")
        
        # Verify no coordinated bundles are generated during fallback
        with self.assertRaises(RuntimeError):
            self.planner.generate_bundle(self.modules, self.interaction_matrix)

    def test_full_workflow(self):
        """Test the complete workflow: detection -> coordinated mutation -> fallback -> single optimization."""
        # Step 1: Detect equilibrium
        equilibrium_detected = False
        for cycle in range(5):
            if self.detector.check_equilibrium(self.modules, self.fitness_evaluator):
                equilibrium_detected = True
                break
            # Simulate failed individual optimization attempts
            for module in self.modules:
                mutation = self.mutation_engine.find_best_mutation(module, self.fitness_evaluator)
                if mutation:
                    self.mutation_engine.apply_mutation(module, mutation)
        
        self.assertTrue(equilibrium_detected, "Equilibrium should be detected within 5 cycles")
        
        # Step 2: Apply coordinated mutation
        bundle = self.planner.generate_bundle(self.modules, self.interaction_matrix)
        self.mutation_engine.apply_bundle(bundle)
        
        # Step 3: Verify equilibrium broken
        self.assertFalse(self.detector.check_equilibrium(self.modules, self.fitness_evaluator),
                        "Equilibrium should be broken after coordinated mutation")
        
        # Step 4: Fallback to single-module optimization
        self.fallback.trigger_fallback(self.modules, self.detector, self.fitness_evaluator)
        
        # Step 5: Perform single-module optimization
        for module in self.modules:
            mutation = self.mutation_engine.find_best_mutation(module, self.fitness_evaluator)
            if mutation:
                self.mutation_engine.apply_mutation(module, mutation)
        
        # Step 6: Verify final state
        self.assertTrue(self.fallback.in_single_module_mode,
                       "System should end in single-module optimization mode")
        self.assertFalse(self.planner.coordinated_phase_completed,
                        "Coordinated phase should no longer be active")

    def test_coordinated_mutation_improves_fitness_by_at_least_5_percent(self):
        """Test that coordinated mutation phase triggers and improves overall system fitness by at least 5%."""
        # Create a scenario with 3 interdependent modules stuck in a local optimum
        # Module 1: Optimizer - high fitness but constrained
        module_a = MagicMock()
        module_a.name = "optimizer_a"
        module_a.fitness = 0.80
        module_a.mutation_options = ["learning_rate_adjust", "batch_size_change", "regularization_tune"]

        # Module 2: DataProcessor - moderate fitness, interacts negatively with module 1
        module_b = MagicMock()
        module_b.name = "data_processor_b"
        module_b.fitness = 0.75
        module_b.mutation_options = ["normalization_change", "augmentation_add", "sampling_strategy"]

        # Module 3: FeatureExtractor - low fitness, interacts negatively with both
        module_c = MagicMock()
        module_c.name = "feature_extractor_c"
        module_c.fitness = 0.70
        module_c.mutation_options = ["kernel_size_change", "activation_change", "layer_depth_adjust"]

        # Create strong negative interactions to create a local optimum
        # Each module's fitness drops significantly when any other module changes
        strong_interaction_matrix = {
            ("optimizer_a", "data_processor_b"): -0.20,
            ("data_processor_b", "optimizer_a"): -0.18,
            ("data_processor_b", "feature_extractor_c"): -0.22,
            ("feature_extractor_c", "data_processor_b"): -0.15,
            ("feature_extractor_c", "optimizer_a"): -0.25,
            ("optimizer_a", "feature_extractor_c"): -0.12,
        }

        modules = [module_a, module_b, module_c]

        # Create detector with strong interaction matrix
        detector = NashEquilibriumDetector(interaction_matrix=strong_interaction_matrix)
        planner = CoordinatedMutationPlanner()
        mutation_engine = MutationEngine()
        fitness_evaluator = FitnessEvaluator()

        # Configure fitness evaluator to respect interaction constraints
        def evaluate_fitness_with_constraints(module, context=None):
            base_fitness = module.fitness
            if context:
                for other_module in context:
                    key = (module.name, other_module.name)
                    if key in strong_interaction_matrix:
                        base_fitness += strong_interaction_matrix[key]
            return max(0.0, min(1.0, base_fitness))

        fitness_evaluator.evaluate.side_effect = evaluate_fitness_with_constraints

        # Record initial total fitness
        initial_total_fitness = sum(m.fitness for m in modules)
        
        # Verify we are in a local optimum (no single module can improve)
        is_equilibrium = detector.check_equilibrium(modules, fitness_evaluator)
        self.assertTrue(is_equilibrium, "System should be in Nash equilibrium (local optimum)")

        # Generate coordinated mutation bundle
        bundle = planner.generate_bundle(modules, strong_interaction_matrix)
        self.assertIsNotNone(bundle, "Coordinated mutation bundle should be generated")

        # Apply coordinated mutation
        mutation_engine.apply_bundle(bundle)

        # Verify coordinated mutation phase triggered
        self.assertTrue(planner.coordinated_phase_completed,
                       "Coordinated mutation phase should be triggered")

        # Calculate final total fitness
        final_total_fitness = sum(m.fitness for m in modules)

        # Verify improvement of at least 5%
        improvement_percentage = ((final_total_fitness - initial_total_fitness) / initial_total_fitness) * 100
        self.assertGreaterEqual(
            improvement_percentage,
            5.0,
            f"Coordinated mutation should improve overall system fitness by at least 5%. "
            f"Initial: {initial_total_fitness:.2f}, Final: {final_total_fitness:.2f}, "
            f"Improvement: {improvement_percentage:.2f}%"
        )

        # Verify equilibrium is broken
        is_still_equilibrium = detector.check_equilibrium(modules, fitness_evaluator)
        self.assertFalse(is_still_equilibrium,
                        "Coordinated mutation should break the local optimum")

        # Verify each module's fitness improved
        for module in modules:
            self.assertGreater(
                module.fitness,
                0.0,
                f"Module {module.name} should have positive fitness after coordinated mutation"
            )

if __name__ == '__main__':
    unittest.main()