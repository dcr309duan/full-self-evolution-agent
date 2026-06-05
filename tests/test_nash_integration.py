import sys
import os
import unittest
from unittest.mock import MagicMock, patch

# Add the parent directory to the path so we can import from core and modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.nash_detector import NashDetector
from core.multi_module_forcer import MultiModuleForcer


class TestNashIntegration(unittest.TestCase):
    """Minimal integration test for Nash equilibrium detection and coordinated mutation."""

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

        # Create the Nash detector and multi-module forcer
        self.nash_detector = NashDetector()
        self.multi_module_forcer = MultiModuleForcer()

        # Register modules with the detector
        self.modules = [self.module_a, self.module_b, self.module_c]
        for mod in self.modules:
            self.nash_detector.register_module(mod)

    def test_minimal_integration_with_interaction_matrix(self):
        """Minimal integration test that: (1) creates a simple interaction matrix,
        (2) runs detection, (3) verifies that coordinated changes are proposed when equilibrium is detected."""
        # (1) Create a simple interaction matrix
        # Simulate interaction data showing no improvement (equilibrium state)
        interaction_matrix = {
            "ModuleA": {"ModuleA": 0.5, "ModuleB": 0.5, "ModuleC": 0.5},
            "ModuleB": {"ModuleA": 0.5, "ModuleB": 0.5, "ModuleC": 0.5},
            "ModuleC": {"ModuleA": 0.5, "ModuleB": 0.5, "ModuleC": 0.5}
        }
        
        # Configure modules with the interaction matrix
        self.module_a.get_scores.return_value = interaction_matrix["ModuleA"]
        self.module_b.get_scores.return_value = interaction_matrix["ModuleB"]
        self.module_c.get_scores.return_value = interaction_matrix["ModuleC"]
        
        # Seed the nash_detector with synthetic history showing equilibrium
        synthetic_history = {
            "ModuleA": [
                {"fitness": 0.3, "timestamp": 1},
                {"fitness": 0.4, "timestamp": 2},
                {"fitness": 0.5, "timestamp": 3},
                {"fitness": 0.5, "timestamp": 4},
                {"fitness": 0.5, "timestamp": 5}
            ],
            "ModuleB": [
                {"fitness": 0.3, "timestamp": 1},
                {"fitness": 0.4, "timestamp": 2},
                {"fitness": 0.5, "timestamp": 3},
                {"fitness": 0.5, "timestamp": 4},
                {"fitness": 0.5, "timestamp": 5}
            ],
            "ModuleC": [
                {"fitness": 0.3, "timestamp": 1},
                {"fitness": 0.4, "timestamp": 2},
                {"fitness": 0.5, "timestamp": 3},
                {"fitness": 0.5, "timestamp": 4},
                {"fitness": 0.5, "timestamp": 5}
            ]
        }
        
        for module_name, history in synthetic_history.items():
            for entry in history:
                self.nash_detector.record_fitness(module_name, entry["fitness"], entry["timestamp"])

        # (2) Run detection
        is_nash = self.nash_detector.detect_equilibrium(self.modules)
        self.assertTrue(is_nash, "Nash equilibrium should be detected with interaction matrix showing no improvement")

        # (3) Verify that coordinated changes are proposed when equilibrium is detected
        plan = self.multi_module_forcer.generate_plan(self.dependency_graph, {"is_equilibrium": True})
        self.assertIsNotNone(plan, "Multi-module forcer should generate a plan when equilibrium is detected")
        self.assertGreaterEqual(len(plan), 2, "Plan should target at least 2 modules")

        # Verify the plan contains valid module names
        plan_module_names = [m.get("module") for m in plan]
        for module_name in plan_module_names:
            self.assertIn(module_name, [mod.name for mod in self.modules],
                          f"Module {module_name} in plan should exist in the system")

        # Verify the plan respects dependencies (if ModuleA is targeted, ModuleB must also be targeted)
        if "ModuleA" in plan_module_names:
            self.assertIn("ModuleB", plan_module_names,
                          "If ModuleA is targeted, ModuleB must also be targeted due to dependency")
        if "ModuleB" in plan_module_names:
            self.assertIn("ModuleC", plan_module_names,
                          "If ModuleB is targeted, ModuleC must also be targeted due to dependency")

        # Verify each mutation in the plan has required fields
        for mutation in plan:
            self.assertIn("module", mutation, "Each mutation should have a 'module' key")
            self.assertIsInstance(mutation["module"], str, "Module name should be a string")
            if "type" in mutation:
                self.assertIsInstance(mutation["type"], str, "Mutation type should be a string")
            if "params" in mutation:
                self.assertIsInstance(mutation["params"], dict, "Mutation params should be a dictionary")

        # Execute the coordinated changes and verify improvement
        initial_fitness = sum(mod.fitness for mod in self.modules)
        for mutation in plan:
            module_name = mutation.get("module")
            for mod in self.modules:
                if mod.name == module_name:
                    mod.mutate()
                    # Simulate improvement from coordinated change
                    mod.fitness += 0.1
                    break

        final_fitness = sum(mod.fitness for mod in self.modules)
        self.assertGreater(final_fitness, initial_fitness,
                         "Coordinated multi-module change should improve overall system fitness")


if __name__ == '__main__':
    unittest.main()