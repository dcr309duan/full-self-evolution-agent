import unittest
from unittest.mock import patch, MagicMock
from core.coordinated_mutation_planner import CoordinatedMutationPlanner
from core.multi_module_forcer import MultiModuleForcer
from core.nash_detector import NashDetector

class TestCoordinatedMutation(unittest.TestCase):
    def setUp(self):
        self.planner = CoordinatedMutationPlanner()
        self.forcer = MultiModuleForcer()
        self.detector = NashDetector()
        
        # Create mock modules
        self.module_a = MagicMock()
        self.module_a.name = "module_a"
        self.module_a.f = MagicMock(return_value=1)
        
        self.module_b = MagicMock()
        self.module_b.name = "module_b"
        self.module_b.g = MagicMock(side_effect=lambda: self.module_a.f() + 1)
        
        self.modules = {"module_a": self.module_a, "module_b": self.module_b}

    def test_plan_generation(self):
        """Test that coordinated plan is generated correctly"""
        plan = self.planner.generate_coordinated_mutations(self.modules)
        
        self.assertIsNotNone(plan)
        self.assertIn("module_a", plan)
        self.assertIn("module_b", plan)
        
        # Verify module_a plan changes f() to return 2
        self.assertEqual(plan["module_a"]["target"], "f")
        self.assertEqual(plan["module_a"]["new_return_value"], 2)
        
        # Verify module_b plan updates g() to use new return value
        self.assertEqual(plan["module_b"]["target"], "g")
        self.assertTrue("2" in str(plan["module_b"]["new_implementation"]) or 
                       "new_return_value" in str(plan["module_b"]["new_implementation"]))

    def test_atomic_application(self):
        """Test that plan is applied atomically and both modules change"""
        # Generate and apply plan
        plan = self.planner.generate_coordinated_mutations(self.modules)
        result = self.planner.apply_plan_atomically(self.modules, plan)
        
        self.assertTrue(result)
        
        # Verify module_a changed
        self.assertEqual(self.module_a.f(), 2)
        
        # Verify module_b changed and uses new return value
        self.assertEqual(self.module_b.g(), 3)  # f() returns 2, so g() returns 3

    def test_rollback_on_failure(self):
        """Test that changes are reverted if second module change fails"""
        # Generate plan
        plan = self.planner.generate_coordinated_mutations(self.modules)
        
        # Simulate failure in module_b change
        with patch.object(self.planner, '_apply_single_mutation', side_effect=[
            True,  # module_a succeeds
            False  # module_b fails
        ]):
            result = self.planner.apply_plan_atomically(self.modules, plan)
            
            self.assertFalse(result)
            
            # Verify module_a was reverted
            self.assertEqual(self.module_a.f(), 1)
            
            # Verify module_b was not changed
            self.assertEqual(self.module_b.g(), 2)  # f() still returns 1

    def test_rollback_restores_original_state(self):
        """Test that rollback completely restores original state"""
        original_a_return = self.module_a.f()
        original_b_return = self.module_b.g()
        
        plan = self.planner.generate_coordinated_mutations(self.modules)
        
        # Force failure during application
        with patch.object(self.planner, '_apply_single_mutation', return_value=False):
            result = self.planner.apply_plan_atomically(self.modules, plan)
            
            self.assertFalse(result)
            
            # Verify complete restoration
            self.assertEqual(self.module_a.f(), original_a_return)
            self.assertEqual(self.module_b.g(), original_b_return)

    def test_nash_equilibrium_detection_and_escape(self):
        """Integration test: (1) sets up 3 mock modules with interdependent fitness functions,
        (2) artificially creates a Nash equilibrium, (3) verifies the coordinated mutation
        orchestrator detects it and applies multi-module changes, (4) confirms the system
        escapes the local optimum."""
        
        # (1) Set up 3 mock modules with interdependent fitness functions
        module_x = MagicMock()
        module_x.name = "module_x"
        module_x.fitness = MagicMock(return_value=0.5)
        module_x.value = 10
        
        module_y = MagicMock()
        module_y.name = "module_y"
        module_y.fitness = MagicMock(side_effect=lambda: module_x.fitness() * 0.8)
        module_y.value = 20
        
        module_z = MagicMock()
        module_z.name = "module_z"
        module_z.fitness = MagicMock(side_effect=lambda: module_y.fitness() + 0.1)
        module_z.value = 30
        
        modules = {"module_x": module_x, "module_y": module_y, "module_z": module_z}
        
        # (2) Artificially create a Nash equilibrium by setting fitness values
        # that are locally optimal but globally suboptimal
        module_x.fitness.return_value = 0.5
        # module_y depends on module_x, module_z depends on module_y
        # This creates a chain where no single module can improve without others changing
        
        # (3) Verify the coordinated mutation orchestrator detects it and applies multi-module changes
        plan = self.planner.generate_coordinated_mutations(modules)
        
        self.assertIsNotNone(plan)
        self.assertIn("module_x", plan)
        self.assertIn("module_y", plan)
        self.assertIn("module_z", plan)
        
        # Apply the coordinated plan atomically
        result = self.planner.apply_plan_atomically(modules, plan)
        self.assertTrue(result)
        
        # (4) Confirm the system escapes the local optimum
        # After coordinated changes, all modules should have improved fitness
        new_fitness_x = module_x.fitness()
        new_fitness_y = module_y.fitness()
        new_fitness_z = module_z.fitness()
        
        # Verify all modules improved from their original values
        self.assertGreater(new_fitness_x, 0.5, "Module X should have improved fitness")
        self.assertGreater(new_fitness_y, 0.4, "Module Y should have improved fitness")  # 0.5 * 0.8 = 0.4
        self.assertGreater(new_fitness_z, 0.5, "Module Z should have improved fitness")  # 0.4 + 0.1 = 0.5
        
        # Verify the chain dependency is maintained correctly
        self.assertAlmostEqual(new_fitness_y, new_fitness_x * 0.8, places=5)
        self.assertAlmostEqual(new_fitness_z, new_fitness_y + 0.1, places=5)
        
        # Verify the system is now in a better state (higher combined fitness)
        original_combined = 0.5 + (0.5 * 0.8) + ((0.5 * 0.8) + 0.1)
        new_combined = new_fitness_x + new_fitness_y + new_fitness_z
        self.assertGreater(new_combined, original_combined, 
                          "Combined fitness should be higher after escaping Nash equilibrium")

    def test_forcer_detects_nash_equilibrium(self):
        """Integration test: (1) forcer detects when nash_detector reports equilibrium,
        (2) forcer generates a coordinated change plan, (3) the plan involves 2-3 modules."""
        
        # Create 3 mock modules with interdependent behavior
        module_a = MagicMock()
        module_a.name = "module_a"
        module_a.fitness = MagicMock(return_value=0.6)
        module_a.value = 10
        
        module_b = MagicMock()
        module_b.name = "module_b"
        module_b.fitness = MagicMock(side_effect=lambda: module_a.fitness() * 0.9)
        module_b.value = 20
        
        module_c = MagicMock()
        module_c.name = "module_c"
        module_c.fitness = MagicMock(side_effect=lambda: module_b.fitness() + 0.05)
        module_c.value = 30
        
        modules = {"module_a": module_a, "module_b": module_b, "module_c": module_c}
        
        # Create interaction matrix for Nash detector
        interaction_matrix = {
            "module_a": {"module_b": 0.5, "module_c": 0.3},
            "module_b": {"module_a": 0.4, "module_c": 0.2},
            "module_c": {"module_a": 0.1, "module_b": 0.6}
        }
        
        # (1) Forcer detects when nash_detector reports equilibrium
        # Set up the detector to report equilibrium
        with patch.object(self.detector, 'detect_equilibrium', return_value=True):
            equilibrium_detected = self.detector.detect_equilibrium(modules, interaction_matrix)
            self.assertTrue(equilibrium_detected, "Nash detector should report equilibrium")
            
            # (2) Forcer generates a coordinated change plan
            plan = self.forcer.generate_plan(modules, interaction_matrix)
            self.assertIsNotNone(plan, "Forcer should generate a plan")
            
            # (3) The plan involves 2-3 modules
            self.assertGreaterEqual(len(plan), 2, "Plan should involve at least 2 modules")
            self.assertLessEqual(len(plan), 3, "Plan should involve at most 3 modules")
            
            # Verify the plan contains valid module names
            for module_name in plan:
                self.assertIn(module_name, modules, f"Plan module {module_name} should be in modules dict")
            
            # Apply the plan
            result = self.forcer.apply_plan(modules, plan)
            self.assertTrue(result, "Plan application should succeed")
            
            # Verify modules were changed
            self.assertNotEqual(module_a.fitness(), 0.6, "Module A fitness should change")
            self.assertNotEqual(module_b.fitness(), 0.54, "Module B fitness should change")
            self.assertNotEqual(module_c.fitness(), 0.59, "Module C fitness should change")

    def test_forcer_generates_coordinated_change_plan(self):
        """Test that forcer generates a coordinated change plan with 2-3 modules"""
        
        # Create 2 mock modules
        module_x = MagicMock()
        module_x.name = "module_x"
        module_x.fitness = MagicMock(return_value=0.7)
        module_x.value = 15
        
        module_y = MagicMock()
        module_y.name = "module_y"
        module_y.fitness = MagicMock(side_effect=lambda: module_x.fitness() * 0.85)
        module_y.value = 25
        
        modules = {"module_x": module_x, "module_y": module_y}
        
        interaction_matrix = {
            "module_x": {"module_y": 0.8},
            "module_y": {"module_x": 0.7}
        }
        
        # Generate plan
        plan = self.forcer.generate_plan(modules, interaction_matrix)
        
        # Verify plan exists and involves 2 modules
        self.assertIsNotNone(plan)
        self.assertEqual(len(plan), 2, "Plan should involve exactly 2 modules")
        self.assertIn("module_x", plan)
        self.assertIn("module_y", plan)
        
        # Apply plan
        result = self.forcer.apply_plan(modules, plan)
        self.assertTrue(result)
        
        # Verify changes were made
        self.assertNotEqual(module_x.fitness(), 0.7, "Module X fitness should change")
        self.assertNotEqual(module_y.fitness(), 0.595, "Module Y fitness should change")

if __name__ == '__main__':
    unittest.main()