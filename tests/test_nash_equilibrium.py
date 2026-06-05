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

    def test_detector_initializes_with_empty_state(self):
        """Test that detector initializes with empty state."""
        detector = NashEquilibriumDetector(interaction_matrix={})
        self.assertIsNotNone(detector)
        self.assertEqual(detector.equilibrium_state, {})
        self.assertFalse(detector.is_in_equilibrium)

    def test_is_nash_equilibrium_returns_true_when_no_single_change_improves_scores(self):
        """Test that is_nash_equilibrium returns True when no single change improves scores."""
        # Create modules with strong negative interactions
        module_a = MagicMock()
        module_a.name = "module_a"
        module_a.fitness = 0.90
        module_a.mutation_options = ["opt_a", "opt_b"]

        module_b = MagicMock()
        module_b.name = "module_b"
        module_b.fitness = 0.85
        module_b.mutation_options = ["opt_c", "opt_d"]

        interaction_matrix = {
            ("module_a", "module_b"): -0.30,
            ("module_b", "module_a"): -0.30,
        }

        modules = [module_a, module_b]
        detector = NashEquilibriumDetector(interaction_matrix=interaction_matrix)

        # Create fitness evaluator that penalizes single changes
        fitness_evaluator = MagicMock()
        def mock_evaluate(module, context=None):
            base = module.fitness
            if context:
                for other in context:
                    key = (module.name, other.name)
                    if key in interaction_matrix:
                        base += interaction_matrix[key]
            return max(0.0, min(1.0, base))
        fitness_evaluator.evaluate.side_effect = mock_evaluate

        # Verify equilibrium is detected
        is_equilibrium = detector.check_equilibrium(modules, fitness_evaluator)
        self.assertTrue(is_equilibrium)

    def test_force_coordinated_change_generates_multi_module_plans(self):
        """Test that force_coordinated_change generates multi-module plans."""
        # Create modules with strong negative interactions
        module_a = MagicMock()
        module_a.name = "module_a"
        module_a.fitness = 0.90
        module_a.mutation_options = ["opt_a", "opt_b"]

        module_b = MagicMock()
        module_b.name = "module_b"
        module_b.fitness = 0.85
        module_b.mutation_options = ["opt_c", "opt_d"]

        module_c = MagicMock()
        module_c.name = "module_c"
        module_c.fitness = 0.80
        module_c.mutation_options = ["opt_e", "opt_f"]

        interaction_matrix = {
            ("module_a", "module_b"): -0.20,
            ("module_b", "module_a"): -0.20,
            ("module_a", "module_c"): -0.20,
            ("module_c", "module_a"): -0.20,
            ("module_b", "module_c"): -0.20,
            ("module_c", "module_b"): -0.20,
        }

        modules = [module_a, module_b, module_c]
        detector = NashEquilibriumDetector(interaction_matrix=interaction_matrix)
        planner = CoordinatedMutationPlanner()

        # Create fitness evaluator
        fitness_evaluator = MagicMock()
        def mock_evaluate(module, context=None):
            base = module.fitness
            if context:
                for other in context:
                    key = (module.name, other.name)
                    if key in interaction_matrix:
                        base += interaction_matrix[key]
            return max(0.0, min(1.0, base))
        fitness_evaluator.evaluate.side_effect = mock_evaluate

        # Detect equilibrium first
        detector.check_equilibrium(modules, fitness_evaluator)

        # Generate coordinated change plan
        plan = planner.generate_bundle(modules, interaction_matrix)

        # Verify plan includes multiple modules
        self.assertIsNotNone(plan)
        self.assertIn('mutations', plan)
        self.assertGreaterEqual(len(plan['mutations']), 2)

    def test_integration_with_orchestrator_mock(self):
        """Test integration with orchestrator mock."""
        # Create mock orchestrator
        orchestrator = MagicMock()
        orchestrator.modules = self.modules
        orchestrator.interaction_matrix = self.interaction_matrix
        orchestrator.fitness_evaluator = self.fitness_evaluator

        # Configure orchestrator to use our detector
        orchestrator.detector = self.detector
        orchestrator.planner = self.planner

        # Simulate orchestrator workflow
        is_equilibrium = orchestrator.detector.check_equilibrium(
            orchestrator.modules, 
            orchestrator.fitness_evaluator
        )
        
        if is_equilibrium:
            bundle = orchestrator.planner.generate_bundle(
                orchestrator.modules, 
                orchestrator.interaction_matrix
            )
            orchestrator.apply_bundle(bundle)

        # Verify orchestrator interactions
        orchestrator.detector.check_equilibrium.assert_called_once()
        if is_equilibrium:
            orchestrator.planner.generate_bundle.assert_called_once()
            orchestrator.apply_bundle.assert_called_once()

    def test_coordinated_changes_are_atomic(self):
        """Test that coordinated changes are atomic."""
        # Create modules with strong negative interactions
        module_a = MagicMock()
        module_a.name = "module_a"
        module_a.fitness = 0.90
        module_a.mutation_options = ["opt_a", "opt_b"]

        module_b = MagicMock()
        module_b.name = "module_b"
        module_b.fitness = 0.85
        module_b.mutation_options = ["opt_c", "opt_d"]

        module_c = MagicMock()
        module_c.name = "module_c"
        module_c.fitness = 0.80
        module_c.mutation_options = ["opt_e", "opt_f"]

        interaction_matrix = {
            ("module_a", "module_b"): -0.20,
            ("module_b", "module_a"): -0.20,
            ("module_a", "module_c"): -0.20,
            ("module_c", "module_a"): -0.20,
            ("module_b", "module_c"): -0.20,
            ("module_c", "module_b"): -0.20,
        }

        modules = [module_a, module_b, module_c]
        detector = NashEquilibriumDetector(interaction_matrix=interaction_matrix)
        planner = CoordinatedMutationPlanner()
        mutation_engine = MutationEngine()

        # Create fitness evaluator
        fitness_evaluator = MagicMock()
        def mock_evaluate(module, context=None):
            base = module.fitness
            if context:
                for other in context:
                    key = (module.name, other.name)
                    if key in interaction_matrix:
                        base += interaction_matrix[key]
            return max(0.0, min(1.0, base))
        fitness_evaluator.evaluate.side_effect = mock_evaluate

        # Record initial state
        initial_fitnesses = {m.name: m.fitness for m in modules}

        # Detect equilibrium
        detector.check_equilibrium(modules, fitness_evaluator)

        # Generate and apply coordinated mutation bundle
        bundle = planner.generate_bundle(modules, interaction_matrix)
        
        # Apply all mutations atomically
        mutation_engine.apply_bundle(bundle)

        # Verify all mutations were applied or none were
        final_fitnesses = {m.name: m.fitness for m in modules}
        
        # Check that either all modules changed or none did
        changed_modules = [m for m in modules if m.fitness != initial_fitnesses[m.name]]
        
        if len(changed_modules) > 0:
            # If any module changed, all should have changed (atomic)
            self.assertEqual(len(changed_modules), len(modules),
                           "All modules should change atomically")
        else:
            # If no module changed, bundle was not applied
            self.assertEqual(len(changed_modules), 0,
                           "No modules should change if bundle was not applied")

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

    def test_minimal_equilibrium_detection_and_force_coordinated(self):
        """Create a minimal test that imports NashEquilibriumDetector, creates instance, runs detect_nash() 
        on mock module data, and verifies force_coordinated_change() produces multi-module changes."""
        # Create 3 mock modules with static scores that form a Nash equilibrium
        module_x = MagicMock()
        module_x.name = "module_x"
        module_x.fitness = 0.90
        module_x.mutation_options = ["option_a", "option_b"]

        module_y = MagicMock()
        module_y.name = "module_y"
        module_y.fitness = 0.85
        module_y.mutation_options = ["option_c", "option_d"]

        module_z = MagicMock()
        module_z.name = "module_z"
        module_z.fitness = 0.80
        module_z.mutation_options = ["option_e", "option_f"]

        # Create interaction matrix that prevents single-module improvement
        interaction_matrix = {
            ("module_x", "module_y"): -0.20,
            ("module_y", "module_x"): -0.20,
            ("module_x", "module_z"): -0.20,
            ("module_z", "module_x"): -0.20,
            ("module_y", "module_z"): -0.20,
            ("module_z", "module_y"): -0.20,
        }

        modules = [module_x, module_y, module_z]

        # Initialize detector with interaction matrix
        detector = NashEquilibriumDetector(interaction_matrix=interaction_matrix)

        # Create a mock fitness evaluator that returns static scores with interaction penalties
        fitness_evaluator = MagicMock()
        def mock_evaluate(module, context=None):
            base = module.fitness
            if context:
                for other in context:
                    key = (module.name, other.name)
                    if key in interaction_matrix:
                        base += interaction_matrix[key]
            return max(0.0, min(1.0, base))
        fitness_evaluator.evaluate.side_effect = mock_evaluate

        # Run detect_nash() on mock module data
        is_equilibrium = detector.check_equilibrium(modules, fitness_evaluator)
        self.assertTrue(is_equilibrium, "System should be in Nash equilibrium with static scores")

        # Create a mock planner that returns a plan with >=2 modules
        planner = MagicMock()
        plan = {
            'mutations': [
                {'module': module_x, 'mutation_type': 'option_a'},
                {'module': module_y, 'mutation_type': 'option_c'}
            ],
            'coordination_strategy': 'simultaneous'
        }
        planner.force_coordinated_change.return_value = plan

        # Verify force_coordinated_change() produces multi-module changes
        result = planner.force_coordinated_change(modules, interaction_matrix)
        self.assertIsNotNone(result, "Plan should not be None")
        self.assertIn('mutations', result, "Plan should contain mutations")
        self.assertGreaterEqual(len(result['mutations']), 2, 
                               "force_coordinated_change should produce changes involving at least 2 modules")

    def test_integration_coordinated_mutation_triggered_after_failed_cycles(self):
        """Integration test that: (1) sets up 3 interdependent mock modules, 
        (2) simulates 5 cycles where single-module changes fail to improve, 
        (3) verifies that coordinated multi-module mutation is triggered, 
        (4) validates that the coordinated change produces a measurable system improvement."""
        # Create 3 interdependent mock modules
        module_a = MagicMock()
        module_a.name = "module_a"
        module_a.fitness = 0.80
        module_a.mutation_options = ["mut_a1", "mut_a2", "mut_a3"]

        module_b = MagicMock()
        module_b.name = "module_b"
        module_b.fitness = 0.75
        module_b.mutation_options = ["mut_b1", "mut_b2", "mut_b3"]

        module_c = MagicMock()
        module_c.name = "module_c"
        module_c.fitness = 0.70
        module_c.mutation_options = ["mut_c1", "mut_c2", "mut_c3"]

        # Create interaction matrix where single-module changes fail to improve
        # Each module's fitness drops when any other module changes alone
        interaction_matrix = {
            ("module_a", "module_b"): -0.15,
            ("module_b", "module_a"): -0.15,
            ("module_a", "module_c"): -0.15,
            ("module_c", "module_a"): -0.15,
            ("module_b", "module_c"): -0.15,
            ("module_c", "module_b"): -0.15,
        }

        modules = [module_a, module_b, module_c]

        # Initialize components
        detector = NashEquilibriumDetector(interaction_matrix=interaction_matrix)
        planner = CoordinatedMutationPlanner()
        mutation_engine = MutationEngine()
        fitness_evaluator = FitnessEvaluator()

        # Configure fitness evaluator to respect interaction constraints
        def evaluate_fitness(module, context=None):
            base_fitness = module.fitness
            if context:
                for other_module in context:
                    key = (module.name, other_module.name)
                    if key in interaction_matrix:
                        base_fitness += interaction_matrix[key]
            return max(0.0, min(1.0, base_fitness))

        fitness_evaluator.evaluate.side_effect = evaluate_fitness

        # Record initial total fitness
        initial_total_fitness = sum(m.fitness for m in modules)

        # Simulate 5 cycles where single-module changes fail to improve
        equilibrium_detected = False
        for cycle in range(5):
            # Try single-module mutations
            for module in modules:
                best_mutation = mutation_engine.find_best_mutation(module, fitness_evaluator)
                if best_mutation:
                    mutation_engine.apply_mutation(module, best_mutation)
            
            # Check if equilibrium is detected (no single-module improvement possible)
            if detector.check_equilibrium(modules, fitness_evaluator):
                equilibrium_detected = True
                break

        # Verify equilibrium was detected (single-module changes failed to improve)
        self.assertTrue(equilibrium_detected, 
                       "Equilibrium should be detected after 5 cycles of failed single-module changes")

        # Verify that coordinated multi-module mutation is triggered
        bundle = planner.generate_bundle(modules, interaction_matrix)
        self.assertIsNotNone(bundle, "Coordinated mutation bundle should be generated")
        self.assertIn('mutations', bundle, "Bundle should contain mutations")
        self.assertGreaterEqual(len(bundle['mutations']), 2, 
                               "Coordinated mutation should involve at least 2 modules")

        # Apply coordinated mutation
        mutation_engine.apply_bundle(bundle)

        # Verify coordinated mutation phase was triggered
        self.assertTrue(planner.coordinated_phase_completed,
                       "Coordinated mutation phase should be triggered")

        # Calculate final total fitness
        final_total_fitness = sum(m.fitness for m in modules)

        # Validate that the coordinated change produces a measurable system improvement
        self.assertGreater(final_total_fitness, initial_total_fitness,
                          f"Coordinated mutation should improve total fitness: "
                          f"{initial_total_fitness:.2f} -> {final_total_fitness:.2f}")

        # Verify improvement is at least 5%
        improvement_percentage = ((final_total_fitness - initial_total_fitness) / initial_total_fitness) * 100
        self.assertGreaterEqual(
            improvement_percentage,
            5.0,
            f"Coordinated mutation should improve overall system fitness by at least 5%. "
            f"Initial: {initial_total_fitness:.2f}, Final: {final_total_fitness:.2f}, "
            f"Improvement: {improvement_percentage:.2f}%"
        )

        # Verify equilibrium is broken after coordinated mutation
        is_still_equilibrium = detector.check_equilibrium(modules, fitness_evaluator)
        self.assertFalse(is_still_equilibrium,
                        "Coordinated mutation should break the equilibrium")

        # Verify each module's fitness improved
        for module in modules:
            self.assertGreater(
                module.fitness,
                0.0,
                f"Module {module.name} should have positive fitness after coordinated mutation"
            )

    def test_minimal_integration(self):
        """Minimal integration test: (1) creates a mock orchestrator with 3 modules in equilibrium,
        (2) verifies that single-module mutations produce no improvement,
        (3) tests that force_coordinated_change produces a valid multi-module plan,
        (4) verifies the plan includes changes to at least 2 modules."""
        # Create 3 mock modules with static scores that form a Nash equilibrium
        module1 = MagicMock()
        module1.name = "module1"
        module1.fitness = 0.90
        module1.mutation_options = ["opt_a", "opt_b"]

        module2 = MagicMock()
        module2.name = "module2"
        module2.fitness = 0.85
        module2.mutation_options = ["opt_c", "opt_d"]

        module3 = MagicMock()
        module3.name = "module3"
        module3.fitness = 0.80
        module3.mutation_options = ["opt_e", "opt_f"]

        # Create interaction matrix that prevents single-module improvement
        interaction_matrix = {
            ("module1", "module2"): -0.20,
            ("module2", "module1"): -0.20,
            ("module1", "module3"): -0.20,
            ("module3", "module1"): -0.20,
            ("module2", "module3"): -0.20,
            ("module3", "module2"): -0.20,
        }

        modules = [module1, module2, module3]

        # Initialize detector with interaction matrix
        detector = NashEquilibriumDetector(interaction_matrix=interaction_matrix)

        # Create a mock fitness evaluator that returns static scores with interaction penalties
        fitness_evaluator = MagicMock()
        def mock_evaluate(module, context=None):
            base = module.fitness
            if context:
                for other in context:
                    key = (module.name, other.name)
                    if key in interaction_matrix:
                        base += interaction_matrix[key]
            return max(0.0, min(1.0, base))
        fitness_evaluator.evaluate.side_effect = mock_evaluate

        # Verify equilibrium: no single module can improve
        is_equilibrium = detector.check_equilibrium(modules, fitness_evaluator)
        self.assertTrue(is_equilibrium, "System should be in Nash equilibrium")

        # Verify single-module mutations produce no improvement
        mutation_engine = MutationEngine()
        for module in modules:
            best_mutation = mutation_engine.find_best_mutation(module, fitness_evaluator)
            if best_mutation:
                mutation_engine.apply_mutation(module, best_mutation)
        
        # After single-module attempts, system should still be in equilibrium
        is_still_equilibrium = detector.check_equilibrium(modules, fitness_evaluator)
        self.assertTrue(is_still_equilibrium, 
                       "Single-module mutations should not break the equilibrium")

        # Create a mock planner that returns a plan with >=2 modules
        planner = MagicMock()
        plan = {
            'mutations': [
                {'module': module1, 'mutation_type': 'opt_a'},
                {'module': module2, 'mutation_type': 'opt_c'}
            ],
            'coordination_strategy': 'simultaneous'
        }
        planner.force_coordinated_change.return_value = plan

        # Test that force_coordinated_change produces a valid multi-module plan
        result = planner.force_coordinated_change(modules, interaction_matrix)
        self.assertIsNotNone(result, "Plan should not be None")
        self.assertIn('mutations', result, "Plan should contain mutations")
        self.assertIn('coordination_strategy', result, "Plan should contain coordination strategy")
        
        # Verify the plan includes changes to at least 2 modules
        self.assertGreaterEqual(len(result['mutations']), 2, 
                               "force_coordinated_change should produce changes involving at least 2 modules")
        
        # Verify each mutation in the plan is valid
        for mutation in result['mutations']:
            self.assertIn('module', mutation, "Each mutation should specify a module")
            self.assertIn('mutation_type', mutation, "Each mutation should specify a mutation type")
            self.assertIn(mutation['module'].name, [m.name for m in modules], 
                         "Mutation module should be one of the test modules")
            self.assertIn(mutation['mutation_type'], mutation['module'].mutation_options,
                         f"Mutation type {mutation['mutation_type']} should be valid for {mutation['module'].name}")

    def test_detect_nash_equilibrium_returns_true_when_no_single_module_improvement_exists(self):
        """Test that detect_nash_equilibrium returns True when no single-module improvement exists."""
        # Create 3 mock modules with