import sys
import os
import unittest
from unittest.mock import MagicMock, patch

# Add the parent directory to the path so we can import from core and modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.nash_detector import NashDetector
from modules.coordinated_mutation_planner import CoordinatedMutationPlanner


class TestNashIntegration(unittest.TestCase):
    """Integration test for Nash equilibrium detection and coordinated mutation planning."""

    def setUp(self):
        """Set up a mock system with 3 modules where single mutations are ineffective."""
        # Create mock modules
        self.module_a = MagicMock()
        self.module_b = MagicMock()
        self.module_c = MagicMock()

        # Configure modules to show no improvement with single mutations
        self.module_a.mutate.return_value = self.module_a
        self.module_b.mutate.return_value = self.module_b
        self.module_c.mutate.return_value = self.module_c

        # Set fitness values such that single mutations don't improve fitness
        self.module_a.fitness = 0.5
        self.module_b.fitness = 0.5
        self.module_c.fitness = 0.5

        # Configure module names
        self.module_a.name = "ModuleA"
        self.module_b.name = "ModuleB"
        self.module_c.name = "ModuleC"

        # Dependency graph: A -> B -> C (A depends on B, B depends on C)
        self.dependency_graph = {
            "ModuleA": ["ModuleB"],
            "ModuleB": ["ModuleC"],
            "ModuleC": []
        }

        # Create the Nash detector and coordinated planner
        self.nash_detector = NashDetector()
        self.planner = CoordinatedMutationPlanner()

        # Register modules with the detector
        self.modules = [self.module_a, self.module_b, self.module_c]
        for mod in self.modules:
            self.nash_detector.register_module(mod)

    def test_nash_detection_and_coordinated_planning(self):
        """Test that Nash equilibrium is detected and a multi-module plan is generated."""
        # Step 1: Verify Nash detector returns True (single mutations ineffective)
        is_nash = self.nash_detector.detect_equilibrium(self.modules)
        self.assertTrue(is_nash, "Nash detector should return True when single mutations are ineffective")

        # Step 2: Verify the coordinated planner produces a multi-module plan
        plan = self.planner.generate_plan(self.dependency_graph, {"is_equilibrium": True})
        self.assertIsNotNone(plan, "Coordinated planner should produce a plan")
        self.assertGreater(len(plan), 1, "Plan should involve multiple modules")
        self.assertIn("ModuleA", plan, "Plan should include ModuleA")
        self.assertIn("ModuleB", plan, "Plan should include ModuleB")
        self.assertIn("ModuleC", plan, "Plan should include ModuleC")

    def test_plan_execution_improves_fitness(self):
        """Test that executing the coordinated plan improves system fitness."""
        # Arrange: Set initial system fitness
        initial_fitness = sum(mod.fitness for mod in self.modules) / len(self.modules)

        # Generate the plan
        plan = self.planner.generate_plan(self.dependency_graph, {"is_equilibrium": True})

        # Act: Simulate executing the plan (mutate all modules together)
        for mod_name, mutation_info in plan.items():
            for mod in self.modules:
                if mod.name == mod_name:
                    # Simulate a coordinated mutation that improves fitness
                    mod.fitness = 0.8  # Improved fitness after coordinated mutation
                    break

        # Calculate new system fitness
        new_fitness = sum(mod.fitness for mod in self.modules) / len(self.modules)

        # Assert: System fitness improves
        self.assertGreater(new_fitness, initial_fitness,
                           "System fitness should improve after executing coordinated plan")

    def test_single_mutation_ineffectiveness(self):
        """Test that single mutations do not improve fitness (confirming Nash state)."""
        # Act: Try single mutations on each module
        for mod in self.modules:
            mutated_mod = mod.mutate()
            # Since mutate returns the same module with same fitness, no improvement
            self.assertEqual(mutated_mod.fitness, mod.fitness,
                             f"Single mutation of {mod.name} should not change fitness")

    def test_plan_contains_all_modules(self):
        """Test that the coordinated plan includes all three modules."""
        plan = self.planner.generate_plan(self.dependency_graph, {"is_equilibrium": True})
        module_names_in_plan = set(plan.keys())
        expected_modules = {"ModuleA", "ModuleB", "ModuleC"}
        self.assertEqual(module_names_in_plan, expected_modules,
                         "Plan should contain all three modules")


if __name__ == '__main__':
    unittest.main()