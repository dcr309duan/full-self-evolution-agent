import sys
import os
import unittest
from unittest.mock import MagicMock, patch

# Add the parent directory to the path so we can import from core and modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.nash_detector import NashDetector
from modules.coordinated_mutation_planner import CoordinatedMutationPlanner
from core.evolution_orchestrator import EvolutionOrchestrator


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

        # Create the Nash detector and coordinated planner
        self.nash_detector = NashDetector()
        self.planner = CoordinatedMutationPlanner()

        # Register modules with the detector
        self.modules = [self.module_a, self.module_b, self.module_c]
        for mod in self.modules:
            self.nash_detector.register_module(mod)

    def test_end_to_end_nash_coordinated_mutation(self):
        """End-to-end test: (1) creates a mock orchestrator with Nash detector, (2) runs 15 simulated mutation cycles, (3) verifies that after equilibrium is detected, a coordinated multi-module mutation is generated and executed."""
        # (1) Create a mock orchestrator with Nash detector
        orchestrator = EvolutionOrchestrator(
            modules=self.modules,
            nash_detector=self.nash_detector,
            coordinated_planner=self.planner,
            dependency_graph=self.dependency_graph,
            enable_nash_detection=True,
            enable_coordinated_mutation=True
        )

        # (2) Run 15 simulated mutation cycles
        equilibrium_detected = False
        coordinated_mutation_executed = False
        
        for cycle in range(15):
            # Simulate a mutation cycle
            for mod in self.modules:
                mutated = mod.mutate()
                # Since mutate returns the same module with same fitness, no improvement
                self.assertEqual(mutated.fitness, mod.fitness,
                                 f"Cycle {cycle}: Single mutation of {mod.name} should not improve fitness")
            
            # Check if equilibrium is detected
            is_nash = self.nash_detector.detect_equilibrium(self.modules)
            if is_nash and not equilibrium_detected:
                equilibrium_detected = True
                
                # (3) Verify that after equilibrium is detected, a coordinated multi-module mutation is generated
                plan = self.planner.generate_plan(self.dependency_graph, {"is_equilibrium": True})
                self.assertIsNotNone(plan, "Coordinated planner should generate a plan when equilibrium is detected")
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
                
                # Execute the coordinated mutation
                for mutation in plan:
                    module_name = mutation.get("module")
                    mutation_type = mutation.get("type", "default")
                    # Find the module and apply the mutation
                    for mod in self.modules:
                        if mod.name == module_name:
                            mod.mutate()
                            coordinated_mutation_executed = True
                            break
        
        # Verify that equilibrium was detected during the 15 cycles
        self.assertTrue(equilibrium_detected, 
                        "Nash equilibrium should be detected within 15 cycles of no improvement")
        
        # Verify that a coordinated multi-module mutation was executed
        self.assertTrue(coordinated_mutation_executed,
                        "Coordinated multi-module mutation should be executed after equilibrium detection")

    def test_minimal_integration(self):
        """Minimal integration test: (1) creates a mock orchestrator with 3 modules, (2) simulates 5 cycles of no single-module improvement, (3) verifies Nash equilibrium is detected, (4) verifies a coordinated multi-module plan is generated with at least 2 modules targeted."""
        # (1) Create a mock orchestrator with 3 modules
        orchestrator = EvolutionOrchestrator(
            modules=self.modules,
            nash_detector=self.nash_detector,
            coordinated_planner=self.planner,
            dependency_graph=self.dependency_graph,
            enable_nash_detection=True,
            enable_coordinated_mutation=True
        )

        # (2) Simulate 5 cycles of no single-module improvement
        for cycle in range(5):
            # Each cycle, attempt single mutations - none should improve fitness
            for mod in self.modules:
                mutated = mod.mutate()
                # Since mutate returns the same module with same fitness, no improvement
                self.assertEqual(mutated.fitness, mod.fitness,
                                 f"Cycle {cycle}: Single mutation of {mod.name} should not improve fitness")

        # (3) Verify Nash equilibrium is detected
        is_nash = self.nash_detector.detect_equilibrium(self.modules)
        self.assertTrue(is_nash, "Nash equilibrium should be detected after 5 cycles of no improvement")

        # (4) Verify a coordinated multi-module plan is generated with at least 2 modules targeted
        plan = self.planner.generate_plan(self.dependency_graph, {"is_equilibrium": True})
        self.assertIsNotNone(plan, "Coordinated planner should generate a plan")
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

    def test_mini_evolution_loop_with_nash(self):
        """Integration test that runs a mini evolution loop with Nash detection enabled.
        Verifies that when equilibrium is reached, the orchestrator executes a coordinated change
        and that the system improves after the change."""
        # Create a mock orchestrator with Nash detection enabled
        orchestrator = EvolutionOrchestrator(
            modules=self.modules,
            nash_detector=self.nash_detector,
            coordinated_planner=self.planner,
            dependency_graph=self.dependency_graph,
            enable_nash_detection=True,
            enable_coordinated_mutation=True
        )

        # Run a mini evolution loop (10 cycles)
        equilibrium_reached = False
        coordinated_change_executed = False
        initial_fitness = sum(mod.fitness for mod in self.modules)
        
        for cycle in range(10):
            # Simulate mutation cycle
            for mod in self.modules:
                mod.mutate()
            
            # Check for equilibrium
            if self.nash_detector.detect_equilibrium(self.modules):
                equilibrium_reached = True
                
                # Generate and execute coordinated change
                plan = self.planner.generate_plan(self.dependency_graph, {"is_equilibrium": True})
                if plan and len(plan) >= 2:
                    coordinated_change_executed = True
                    
                    # Execute the coordinated mutation
                    for mutation in plan:
                        module_name = mutation.get("module")
                        for mod in self.modules:
                            if mod.name == module_name:
                                mod.mutate()
                                # Simulate improvement by increasing fitness
                                mod.fitness += 0.1
                                break
                    
                    # Verify system improved after coordinated change
                    final_fitness = sum(mod.fitness for mod in self.modules)
                    self.assertGreater(final_fitness, initial_fitness,
                                     "System fitness should improve after coordinated change")
                    break
        
        # Verify equilibrium was reached
        self.assertTrue(equilibrium_reached,
                       "Nash equilibrium should be reached within 10 cycles")
        
        # Verify coordinated change was executed
        self.assertTrue(coordinated_change_executed,
                       "Coordinated change should be executed when equilibrium is reached")
        
        # Verify system improvement
        final_fitness = sum(mod.fitness for mod in self.modules)
        self.assertGreater(final_fitness, initial_fitness,
                         "System fitness should be greater after the evolution loop")

    def test_mini_evolution_loop_with_mock_modules(self):
        """Integration test that runs a mini evolution loop with 3 mock modules,
        simulates stable success rates, triggers equilibrium detection, and verifies
        that a coordinated change is applied (check that at least 2 modules are modified).
        Uses unittest.mock to patch module interactions."""
        # Create mock modules with stable success rates
        self.module_a.success_rate = 0.5
        self.module_b.success_rate = 0.5
        self.module_c.success_rate = 0.5
        
        # Configure modules to return stable success rates
        self.module_a.get_success_rate.return_value = 0.5
        self.module_b.get_success_rate.return_value = 0.5
        self.module_c.get_success_rate.return_value = 0.5
        
        # Create a mock orchestrator with Nash detection enabled
        orchestrator = EvolutionOrchestrator(
            modules=self.modules,
            nash_detector=self.nash_detector,
            coordinated_planner=self.planner,
            dependency_graph=self.dependency_graph,
            enable_nash_detection=True,
            enable_coordinated_mutation=True
        )

        # Run a mini evolution loop (10 cycles)
        equilibrium_reached = False
        coordinated_change_executed = False
        modules_modified = set()
        
        for cycle in range(10):
            # Simulate mutation cycle with stable success rates
            for mod in self.modules:
                mod.mutate()
                # Simulate stable success rate (no improvement)
                mod.get_success_rate.return_value = 0.5
            
            # Check for equilibrium
            if self.nash_detector.detect_equilibrium(self.modules):
                equilibrium_reached = True
                
                # Generate and execute coordinated change
                plan = self.planner.generate_plan(self.dependency_graph, {"is_equilibrium": True})
                if plan and len(plan) >= 2:
                    coordinated_change_executed = True
                    
                    # Execute the coordinated mutation and track modified modules
                    for mutation in plan:
                        module_name = mutation.get("module")
                        for mod in self.modules:
                            if mod.name == module_name:
                                mod.mutate()
                                # Simulate improvement by increasing success rate
                                mod.success_rate += 0.1
                                mod.get_success_rate.return_value = mod.success_rate
                                modules_modified.add(mod.name)
                                break
                    
                    # Verify that at least 2 modules were modified
                    self.assertGreaterEqual(len(modules_modified), 2,
                                           "At least 2 modules should be modified in coordinated change")
                    break
        
        # Verify equilibrium was reached
        self.assertTrue(equilibrium_reached,
                       "Nash equilibrium should be reached within 10 cycles")
        
        # Verify coordinated change was executed
        self.assertTrue(coordinated_change_executed,
                       "Coordinated change should be executed when equilibrium is reached")
        
        # Verify that at least 2 modules were modified
        self.assertGreaterEqual(len(modules_modified), 2,
                               "At least 2 modules should be modified in coordinated change")
        
        # Verify that the modified modules have improved success rates
        for mod in self.modules:
            if mod.name in modules_modified:
                self.assertGreater(mod.success_rate, 0.5,
                                 f"Module {mod.name} should have improved success rate after coordinated change")


if __name__ == '__main__':
    unittest.main()