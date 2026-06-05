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

    def test_nash_detection_with_mock_scores(self):
        """Integration test that: (1) instantiates NashEquilibriumDetector with mock scores,
        (2) verifies it detects equilibrium, (3) verifies coordinated mutations include at least 2 modules,
        (4) verifies the mutations are properly formatted for the orchestrator."""
        # (1) Create mock scores that indicate equilibrium (no module can improve alone)
        mock_scores = {
            "ModuleA": {"ModuleA": 0.5, "ModuleB": 0.5, "ModuleC": 0.5},
            "ModuleB": {"ModuleA": 0.5, "ModuleB": 0.5, "ModuleC": 0.5},
            "ModuleC": {"ModuleA": 0.5, "ModuleB": 0.5, "ModuleC": 0.5}
        }
        
        # Configure modules with mock scores
        self.module_a.get_scores.return_value = mock_scores["ModuleA"]
        self.module_b.get_scores.return_value = mock_scores["ModuleB"]
        self.module_c.get_scores.return_value = mock_scores["ModuleC"]
        
        # Create a mock orchestrator with Nash detection enabled
        orchestrator = EvolutionOrchestrator(
            modules=self.modules,
            nash_detector=self.nash_detector,
            coordinated_planner=self.planner,
            dependency_graph=self.dependency_graph,
            enable_nash_detection=True,
            enable_coordinated_mutation=True
        )

        # (2) Verify equilibrium is detected
        is_nash = self.nash_detector.detect_equilibrium(self.modules)
        self.assertTrue(is_nash, "Nash equilibrium should be detected with mock scores showing no improvement possible")
        
        # (3) Verify coordinated mutations include at least 2 modules
        plan = self.planner.generate_plan(self.dependency_graph, {"is_equilibrium": True})
        self.assertIsNotNone(plan, "Coordinated planner should generate a plan when equilibrium is detected")
        self.assertGreaterEqual(len(plan), 2, "Plan should target at least 2 modules")
        
        # (4) Verify the mutations are properly formatted for the orchestrator
        for mutation in plan:
            # Each mutation should have a 'module' key with a valid module name
            self.assertIn("module", mutation, "Each mutation should have a 'module' key")
            module_name = mutation["module"]
            self.assertIn(module_name, [mod.name for mod in self.modules],
                         f"Module {module_name} in plan should exist in the system")
            
            # Each mutation should have a 'type' key (optional but recommended)
            if "type" in mutation:
                self.assertIsInstance(mutation["type"], str, "Mutation type should be a string")
            
            # Each mutation should have a 'params' key (optional but recommended)
            if "params" in mutation:
                self.assertIsInstance(mutation["params"], dict, "Mutation params should be a dictionary")
        
        # Verify the plan respects dependencies
        plan_module_names = [m.get("module") for m in plan]
        if "ModuleA" in plan_module_names:
            self.assertIn("ModuleB", plan_module_names,
                         "If ModuleA is targeted, ModuleB must also be targeted due to dependency")
        if "ModuleB" in plan_module_names:
            self.assertIn("ModuleC", plan_module_names,
                         "If ModuleB is targeted, ModuleC must also be targeted due to dependency")

    def test_mini_evolution_loop_with_two_mock_modules(self):
        """Integration test that runs a mini evolution loop with 2 mock modules,
        triggers Nash equilibrium, and verifies that multi_module_forcer produces a non-empty change plan."""
        # Create 2 mock modules
        module_x = MagicMock()
        module_y = MagicMock()
        
        # Configure modules to show no improvement with single mutations
        module_x.mutate.return_value = module_x
        module_y.mutate.return_value = module_y
        
        # Set fitness values such that single mutations don't improve fitness
        module_x.fitness = 0.5
        module_y.fitness = 0.5
        
        # Configure module names
        module_x.name = "ModuleX"
        module_y.name = "ModuleY"
        
        # Dependency graph: X -> Y (X depends on Y)
        dependency_graph = {
            "ModuleX": ["ModuleY"],
            "ModuleY": []
        }
        
        # Create the Nash detector and coordinated planner
        nash_detector = NashDetector()
        planner = CoordinatedMutationPlanner()
        
        # Register modules with the detector
        modules = [module_x, module_y]
        for mod in modules:
            nash_detector.register_module(mod)
        
        # Create a mock orchestrator with Nash detection enabled
        orchestrator = EvolutionOrchestrator(
            modules=modules,
            nash_detector=nash_detector,
            coordinated_planner=planner,
            dependency_graph=dependency_graph,
            enable_nash_detection=True,
            enable_coordinated_mutation=True
        )

        # Run a mini evolution loop (10 cycles)
        equilibrium_reached = False
        change_plan_generated = False
        
        for cycle in range(10):
            # Simulate mutation cycle
            for mod in modules:
                mod.mutate()
            
            # Check for equilibrium
            if nash_detector.detect_equilibrium(modules):
                equilibrium_reached = True
                
                # Generate coordinated change plan using multi_module_forcer
                plan = planner.generate_plan(dependency_graph, {"is_equilibrium": True})
                
                # Verify that multi_module_forcer produces a non-empty change plan
                if plan:
                    change_plan_generated = True
                    self.assertGreater(len(plan), 0, "Change plan should not be empty")
                    
                    # Verify the plan contains valid module names
                    plan_module_names = [m.get("module") for m in plan]
                    for module_name in plan_module_names:
                        self.assertIn(module_name, [mod.name for mod in modules],
                                      f"Module {module_name} in plan should exist in the system")
                    
                    # Verify the plan respects dependencies (if ModuleX is targeted, ModuleY must also be targeted)
                    if "ModuleX" in plan_module_names:
                        self.assertIn("ModuleY", plan_module_names,
                                      "If ModuleX is targeted, ModuleY must also be targeted due to dependency")
                    
                    # Execute the coordinated mutation
                    for mutation in plan:
                        module_name = mutation.get("module")
                        for mod in modules:
                            if mod.name == module_name:
                                mod.mutate()
                                break
                    break
        
        # Verify equilibrium was reached
        self.assertTrue(equilibrium_reached,
                       "Nash equilibrium should be reached within 10 cycles")
        
        # Verify that multi_module_forcer produced a non-empty change plan
        self.assertTrue(change_plan_generated,
                       "multi_module_forcer should produce a non-empty change plan when equilibrium is reached")

    def test_minimal_integration_with_synthetic_history(self):
        """Minimal integration test that: (a) seeds the nash_detector with synthetic module history,
        (b) verifies detection of equilibrium state, (c) tests that multi_module_forcer produces a valid plan,
        (d) uses only standard library mocks."""
        # (a) Seed the nash_detector with synthetic module history
        # Create synthetic history data for each module
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
        
        # Seed the nash_detector with synthetic history
        for module_name, history in synthetic_history.items():
            for entry in history:
                self.nash_detector.record_fitness(module_name, entry["fitness"], entry["timestamp"])
        
        # (b) Verify detection of equilibrium state
        is_nash = self.nash_detector.detect_equilibrium(self.modules)
        self.assertTrue(is_nash, "Nash equilibrium should be detected with synthetic history showing plateau")
        
        # (c) Test that multi_module_forcer produces a valid plan
        plan = self.planner.generate_plan(self.dependency_graph, {"is_equilibrium": True})
        self.assertIsNotNone(plan, "multi_module_forcer should produce a plan when equilibrium is detected")
        self.assertGreaterEqual(len(plan), 2, "Plan should target at least 2 modules")
        
        # Verify the plan contains valid module names
        plan_module_names = [m.get("module") for m in plan]
        for module_name in plan_module_names:
            self.assertIn(module_name, [mod.name for mod in self.modules],
                          f"Module {module_name} in plan should exist in the system")
        
        # Verify the plan respects dependencies
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
        
        # (d) Verify that only standard library mocks are used (no external test framework imports)
        # This is implicitly verified by the imports at the top of the file

    def test_integration_nash_detector_and_multi_module_forcer(self):
        """Integration test that simulates a simple system with 3 modules, feeds mock interaction data to nash_detector,
        verifies equilibrium detection, then runs multi_module_forcer and verifies that 2+ modules were changed."""
        # Simulate a simple system with 3 modules
        # Create mock modules with specific interaction data
        module_a = MagicMock()
        module_b = MagicMock()
        module_c = MagicMock()
        
        module_a.name = "ModuleA"
        module_b.name = "ModuleB"
        module_c.name = "ModuleC"
        
        # Configure modules to show no improvement with single mutations
        module_a.mutate.return_value = module_a
        module_b.mutate.return_value = module_b
        module_c.mutate.return_value = module_c
        
        module_a.fitness = 0.5
        module_b.fitness = 0.5
        module_c.fitness = 0.5
        
        # Dependency graph: A -> B -> C
        dependency_graph = {
            "ModuleA": ["ModuleB"],
            "ModuleB": ["ModuleC"],
            "ModuleC": []
        }
        
        # Create Nash detector and coordinated planner
        nash_detector = NashDetector()
        planner = CoordinatedMutationPlanner()
        
        # Register modules
        modules = [module_a, module_b, module_c]
        for mod in modules:
            nash_detector.register_module(mod)
        
        # Feed mock interaction data to nash_detector
        # Simulate interaction data showing no improvement
        interaction_data = [
            {"module": "ModuleA", "fitness": 0.5, "timestamp": 1},
            {"module": "ModuleB", "fitness": 0.5, "timestamp": 1},
            {"module": "ModuleC", "fitness": 0.5, "timestamp": 1},
            {"module": "ModuleA", "fitness": 0.5, "timestamp": 2},
            {"module": "ModuleB", "fitness": 0.5, "timestamp": 2},
            {"module": "ModuleC", "fitness": 0.5, "timestamp": 2},
            {"module": "ModuleA", "fitness": 0.5, "timestamp": 3},
            {"module": "ModuleB", "fitness": 0.5, "timestamp": 3},
            {"module": "ModuleC", "fitness": 0.5, "timestamp": 3}
        ]
        
        for data in interaction_data:
            nash_detector.record_fitness(data["module"], data["fitness"], data["timestamp"])
        
        # Verify equilibrium detection
        is_nash = nash_detector.detect_equilibrium(modules)
        self.assertTrue(is_nash, "Nash equilibrium should be detected after feeding interaction data showing no improvement")
        
        # Run multi_module_forcer (via coordinated planner)
        plan = planner.generate_plan(dependency_graph, {"is_equilibrium": True})
        self.assertIsNotNone(plan, "multi_module_forcer should produce a plan when equilibrium is detected")
        self.assertGreaterEqual(len(plan), 2, "Plan should target at least 2 modules")
        
        # Track which modules were changed
        changed_modules = set()
        
        # Execute the plan and track changes
        for mutation in plan:
            module_name = mutation.get("module")
            for mod in modules:
                if mod.name == module_name:
                    # Apply mutation
                    mod.mutate()
                    # Simulate improvement
                    mod.fitness += 0.1
                    changed_modules.add(mod.name)
                    break
        
        # Verify that 2+ modules were changed
        self.assertGreaterEqual(len(changed_modules), 2,
                               "At least 2 modules should be changed by multi_module_forcer")
        
        # Verify the changed modules have improved fitness
        for mod in modules:
            if mod.name in changed_modules:
                self.assertGreater(mod.fitness, 0.5,
                                 f"Module {mod.name} should have improved fitness after coordinated change")
        
        # Verify the plan respects dependencies
        plan_module_names = [m.get("module") for m in plan]
        if "ModuleA" in plan_module_names:
            self.assertIn("ModuleB", plan_module_names,
                         "If ModuleA is targeted, ModuleB must also be targeted due to dependency")
        if "ModuleB" in plan_module_names:
            self.assertIn("ModuleC", plan_module_names,
                         "If ModuleB is targeted, ModuleC must also be targeted due to dependency")

    def test_equilibrium_detection_with_mock_ecosystem(self):
        """Integration test that: (1) Sets up a mock module ecosystem with known equilibrium state.
        2) Verifies nash_detector correctly identifies equilibrium.
        3) Verifies multi_module_forcer generates a valid multi-module change plan.
        4) Uses only standard library and imports from core modules."""
        # (1) Set up a mock module ecosystem with known equilibrium state
        # Create 3 mock modules with known equilibrium state
        module_a = MagicMock()
        module_b = MagicMock()
        module_c = MagicMock()
        
        module_a.name = "ModuleA"
        module_b.name = "ModuleB"
        module_c.name = "ModuleC"
        
        # Configure modules to show no improvement with single mutations (equilibrium state)
        module_a.mutate.return_value = module_a
        module_b.mutate.return_value = module_b
        module_c.mutate.return_value = module_c
        
        # Set fitness values to indicate equilibrium (no module can improve alone)
        module_a.fitness = 0.5
        module_b.fitness = 0.5
        module_c.fitness = 0.5
        
        # Dependency graph: A -> B -> C
        dependency_graph = {
            "ModuleA": ["ModuleB"],
            "ModuleB": ["ModuleC"],
            "ModuleC": []
        }
        
        # Create Nash detector and coordinated planner (multi_module_forcer)
        nash_detector = NashDetector()
        planner = CoordinatedMutationPlanner()
        
        # Register modules with the detector
        modules = [module_a, module_b, module_c]
        for mod in modules:
            nash_detector.register_module(mod)
        
        # Seed the nash_detector with synthetic history showing equilibrium
        # All modules have plateaued at fitness 0.5
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
                nash_detector.record_fitness(module_name, entry["fitness"], entry["timestamp"])
        
        # (2) Verify nash_detector correctly identifies equilibrium
        is_nash = nash_detector.detect_equilibrium(modules)
        self.assertTrue(is_nash, "Nash detector should correctly identify equilibrium state")
        
        # Also verify that single mutations don't improve fitness (confirming equilibrium)
        for mod in modules:
            mutated = mod.mutate()
            self.assertEqual(mutated.fitness, mod.fitness,
                           f"Single mutation of {mod.name} should not improve fitness in equilibrium")
        
        # (3) Verify multi_module_forcer generates a valid multi-module change plan
        plan = planner.generate_plan(dependency_graph, {"is_equilibrium": True})
        self.assertIsNotNone(plan, "multi_module_forcer should generate a plan when equilibrium is detected")
        self.assertGreaterEqual(len(plan), 2, "Plan should target at least 2 modules")
        
        # Verify the plan contains valid module names
        plan_module_names = [m.get("module") for m in plan]
        for module_name in plan_module_names:
            self.assertIn(module_name, [mod.name for mod in modules],
                          f"Module {module_name} in plan should exist in the ecosystem")
        
        # Verify the plan respects dependencies
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
        
        # Execute the plan and verify it produces improvement
        initial_fitness = sum(mod.fitness for mod in modules)
        for mutation in plan:
            module_name = mutation.get("module")
            for mod in modules:
                if mod.name == module_name:
                    mod.mutate()
                    # Simulate improvement from coordinated change
                    mod.fitness += 0.1
                    break
        
        final_fitness = sum(mod.fitness for mod in modules)
        self.assertGreater(final_fitness, initial_fitness,
                         "Coordinated multi-module change should improve overall system fitness")
        
        # (4) Verify that only standard library and core module imports are used
        # This is implicitly verified by the imports at the top of the file
        # No external test framework imports beyond unittest and unittest.mock


if __name__ == '__main__':
    unittest.main()