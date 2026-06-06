import sys
import os
import unittest
import json
import tempfile

# Add the parent directory to the path so we can import from core
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import only from core.nash_detector_and_forcer
from core.nash_detector_and_forcer import NashDetector, MultiModuleForcer


class TestNashIntegration(unittest.TestCase):
    """Self-contained integration test for Nash equilibrium detection and coordinated mutation."""

    def setUp(self):
        """Set up mock module data for testing."""
        self.test_dir = tempfile.mkdtemp()
        
        # Create mock module data files
        self.modules = {
            "ModuleA": {"fitness": 0.5, "dependencies": ["ModuleB"]},
            "ModuleB": {"fitness": 0.5, "dependencies": ["ModuleC"]},
            "ModuleC": {"fitness": 0.5, "dependencies": []}
        }
        
        # Write module data to files
        for module_name, module_data in self.modules.items():
            module_file = os.path.join(self.test_dir, f"{module_name}.json")
            with open(module_file, 'w') as f:
                json.dump(module_data, f)
        
        # Create interaction matrix file
        interaction_matrix = {
            "ModuleA": {"ModuleA": 0.5, "ModuleB": 0.5, "ModuleC": 0.5},
            "ModuleB": {"ModuleA": 0.5, "ModuleB": 0.5, "ModuleC": 0.5},
            "ModuleC": {"ModuleA": 0.5, "ModuleB": 0.5, "ModuleC": 0.5}
        }
        interaction_file = os.path.join(self.test_dir, "interaction_matrix.json")
        with open(interaction_file, 'w') as f:
            json.dump(interaction_matrix, f)
        
        # Create dependency graph file
        dependency_graph = {
            "ModuleA": ["ModuleB"],
            "ModuleB": ["ModuleC"],
            "ModuleC": []
        }
        dependency_file = os.path.join(self.test_dir, "dependency_graph.json")
        with open(dependency_file, 'w') as f:
            json.dump(dependency_graph, f)
        
        # Create history file showing equilibrium (5 entries with <1% improvement)
        history = {
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
        history_file = os.path.join(self.test_dir, "history.json")
        with open(history_file, 'w') as f:
            json.dump(history, f)

    def test_nash_detector_identifies_equilibrium(self):
        """Test (1): NashDetector correctly identifies equilibrium when 5 single-module mutations yield <1% improvement."""
        # Load test data
        with open(os.path.join(self.test_dir, "history.json"), 'r') as f:
            history = json.load(f)
        with open(os.path.join(self.test_dir, "interaction_matrix.json"), 'r') as f:
            interaction_matrix = json.load(f)
        
        # Create detector instance
        detector = NashDetector()
        
        # Record fitness history for all modules
        for module_name, module_history in history.items():
            for entry in module_history:
                detector.record_fitness(module_name, entry["fitness"], entry["timestamp"])
        
        # Create mock modules with interaction data
        class MockModule:
            def __init__(self, name, fitness):
                self.name = name
                self.fitness = fitness
            def get_scores(self):
                return interaction_matrix[self.name]
            def mutate(self):
                return self
        
        module_names = ["ModuleA", "ModuleB", "ModuleC"]
        modules = []
        for name in module_names:
            module_file = os.path.join(self.test_dir, f"{name}.json")
            with open(module_file, 'r') as f:
                data = json.load(f)
            modules.append(MockModule(name, data["fitness"]))
        
        # Detect equilibrium
        is_nash = detector.detect_equilibrium(modules)
        
        # Verify equilibrium is detected (all modules have same fitness, <1% improvement over last 5 mutations)
        self.assertTrue(is_nash, "Nash equilibrium should be detected when all modules have equal fitness and <1% improvement")
        
        # Verify the detector has recorded history
        for module_name in module_names:
            history_data = detector.get_history(module_name)
            self.assertIsNotNone(history_data, f"History should exist for {module_name}")
            self.assertEqual(len(history_data), 5, f"History should have 5 entries for {module_name}")

    def test_multi_module_forcer_generates_coordinated_bundles(self):
        """Test (2): MultiModuleForcer generates coordinated bundles."""
        # Load test data
        with open(os.path.join(self.test_dir, "dependency_graph.json"), 'r') as f:
            dependency_graph = json.load(f)
        
        # Create forcer and generate plan
        forcer = MultiModuleForcer()
        plan = forcer.generate_plan(dependency_graph, {"is_equilibrium": True})
        
        # Verify plan is generated
        self.assertIsNotNone(plan, "Coordinated mutation planner should generate a plan")
        self.assertGreaterEqual(len(plan), 2, "Plan should target at least 2 modules")
        
        # Verify the plan contains valid module names
        plan_module_names = [m.get("module") for m in plan]
        for module_name in plan_module_names:
            self.assertIn(module_name, ["ModuleA", "ModuleB", "ModuleC"],
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

    def test_full_cycle_detection_and_forcing(self):
        """Test (3): Full cycle detection and forcing works end-to-end with mock module data."""
        # Load test data
        with open(os.path.join(self.test_dir, "history.json"), 'r') as f:
            history = json.load(f)
        with open(os.path.join(self.test_dir, "interaction_matrix.json"), 'r') as f:
            interaction_matrix = json.load(f)
        with open(os.path.join(self.test_dir, "dependency_graph.json"), 'r') as f:
            dependency_graph = json.load(f)
        
        # Create detector and load history
        detector = NashDetector()
        for module_name, module_history in history.items():
            for entry in module_history:
                detector.record_fitness(module_name, entry["fitness"], entry["timestamp"])
        
        # Create mock modules with state tracking
        class MockModule:
            def __init__(self, name, fitness):
                self.name = name
                self.fitness = fitness
                self.original_fitness = fitness
            def get_scores(self):
                return interaction_matrix[self.name]
            def mutate(self):
                return self
            def rollback(self):
                self.fitness = self.original_fitness
        
        module_names = ["ModuleA", "ModuleB", "ModuleC"]
        modules = []
        for name in module_names:
            module_file = os.path.join(self.test_dir, f"{name}.json")
            with open(module_file, 'r') as f:
                data = json.load(f)
            modules.append(MockModule(name, data["fitness"]))
        
        # Step 1: Detect equilibrium
        is_nash = detector.detect_equilibrium(modules)
        self.assertTrue(is_nash, "Initial Nash equilibrium should be detected")
        
        # Step 2: Generate coordinated plan
        forcer = MultiModuleForcer()
        plan = forcer.generate_plan(dependency_graph, {"is_equilibrium": True})
        self.assertIsNotNone(plan, "Plan should be generated after equilibrium detection")
        self.assertGreaterEqual(len(plan), 2, "Plan should target at least 2 modules")
        
        # Step 3: Apply mutations to simulate state change
        for mutation in plan:
            module_name = mutation["module"]
            for module in modules:
                if module.name == module_name:
                    module.fitness = 0.7  # New fitness after mutation
                    break
        
        # Record new fitness values in detector
        for module in modules:
            detector.record_fitness(module.name, module.fitness, 6)
        
        # Step 4: Verify system moved to new state (no longer at equilibrium)
        new_is_nash = detector.detect_equilibrium(modules)
        self.assertFalse(new_is_nash, "System should no longer be at equilibrium after mutation")
        
        # Step 5: Verify detector history is updated
        for module_name in module_names:
            history_data = detector.get_history(module_name)
            self.assertIsNotNone(history_data, f"History should exist for {module_name}")
            self.assertEqual(len(history_data), 6, f"History should have 6 entries for {module_name}")

    def test_rollback_on_partial_failure(self):
        """Test that rollback works correctly when a partial failure occurs during coordinated change."""
        # Load test data
        with open(os.path.join(self.test_dir, "history.json"), 'r') as f:
            history = json.load(f)
        with open(os.path.join(self.test_dir, "interaction_matrix.json"), 'r') as f:
            interaction_matrix = json.load(f)
        with open(os.path.join(self.test_dir, "dependency_graph.json"), 'r') as f:
            dependency_graph = json.load(f)
        
        # Create detector and load history
        detector = NashDetector()
        for module_name, module_history in history.items():
            for entry in module_history:
                detector.record_fitness(module_name, entry["fitness"], entry["timestamp"])
        
        # Create mock modules with state tracking for rollback
        class MockModule:
            def __init__(self, name, fitness):
                self.name = name
                self.fitness = fitness
                self.original_fitness = fitness
            def get_scores(self):
                return interaction_matrix[self.name]
            def mutate(self):
                return self
            def rollback(self):
                self.fitness = self.original_fitness
        
        module_names = ["ModuleA", "ModuleB", "ModuleC"]
        modules = []
        for name in module_names:
            module_file = os.path.join(self.test_dir, f"{name}.json")
            with open(module_file, 'r') as f:
                data = json.load(f)
            modules.append(MockModule(name, data["fitness"]))
        
        # Step 1: Detect equilibrium
        is_nash = detector.detect_equilibrium(modules)
        self.assertTrue(is_nash, "Initial Nash equilibrium should be detected")
        
        # Step 2: Generate plan and simulate partial failure
        forcer = MultiModuleForcer()
        plan = forcer.generate_plan(dependency_graph, {"is_equilibrium": True})
        self.assertIsNotNone(plan, "Plan should be generated")
        self.assertGreaterEqual(len(plan), 2, "Plan should target at least 2 modules")
        
        # Simulate applying mutations with a failure on the second module
        applied_modules = []
        failed = False
        for i, mutation in enumerate(plan):
            module_name = mutation["module"]
            try:
                # Simulate mutation application
                for module in modules:
                    if module.name == module_name:
                        if i == 1:  # Simulate failure on second mutation
                            raise Exception("Simulated mutation failure")
                        module.fitness = 0.7
                        applied_modules.append(module_name)
                        break
            except Exception as e:
                failed = True
                # Rollback all previously applied mutations
                for applied_name in applied_modules:
                    for module in modules:
                        if module.name == applied_name:
                            module.rollback()
                            break
                break
        
        # Step 3: Verify rollback was performed
        self.assertTrue(failed, "Partial failure should have occurred")
        
        # Verify all modules returned to original state
        for module in modules:
            self.assertEqual(module.fitness, module.original_fitness,
                             f"Module {module.name} should be rolled back to original fitness {module.original_fitness}")
        
        # Verify system is still at equilibrium after rollback
        new_is_nash = detector.detect_equilibrium(modules)
        self.assertTrue(new_is_nash, "System should still be at equilibrium after rollback")

    def test_mini_evolution_loop(self):
        """Integration test that runs a mini evolution loop (3 cycles) with mock modules."""
        # Load test data
        with open(os.path.join(self.test_dir, "history.json"), 'r') as f:
            history = json.load(f)
        with open(os.path.join(self.test_dir, "interaction_matrix.json"), 'r') as f:
            interaction_matrix = json.load(f)
        with open(os.path.join(self.test_dir, "dependency_graph.json"), 'r') as f:
            dependency_graph = json.load(f)
        
        # Create detector and load initial history
        detector = NashDetector()
        for module_name, module_history in history.items():
            for entry in module_history:
                detector.record_fitness(module_name, entry["fitness"], entry["timestamp"])
        
        # Create mock modules with state tracking
        class MockModule:
            def __init__(self, name, fitness):
                self.name = name
                self.fitness = fitness
                self.original_fitness = fitness
            def get_scores(self):
                return interaction_matrix[self.name]
            def mutate(self):
                return self
            def rollback(self):
                self.fitness = self.original_fitness
        
        module_names = ["ModuleA", "ModuleB", "ModuleC"]
        modules = []
        for name in module_names:
            module_file = os.path.join(self.test_dir, f"{name}.json")
            with open(module_file, 'r') as f:
                data = json.load(f)
            modules.append(MockModule(name, data["fitness"]))
        
        # Run mini evolution loop for 3 cycles
        cycle_results = []
        for cycle in range(3):
            cycle_data = {"cycle": cycle + 1}
            
            # Step 1: Detect equilibrium
            is_nash = detector.detect_equilibrium(modules)
            cycle_data["equilibrium_detected"] = is_nash
            
            # Step 2: If equilibrium detected, generate and apply plan
            plan = None
            if is_nash:
                forcer = MultiModuleForcer()
                plan = forcer.generate_plan(dependency_graph, {"is_equilibrium": True})
                cycle_data["plan_generated"] = plan is not None
                
                if plan:
                    # Apply mutations to simulate state change
                    for mutation in plan:
                        module_name = mutation["module"]
                        for module in modules:
                            if module.name == module_name:
                                # Apply mutation: change fitness to break equilibrium
                                module.fitness = 0.5 + (cycle + 1) * 0.1
                                break
                    
                    # Record new fitness values in detector
                    timestamp = 6 + cycle
                    for module in modules:
                        detector.record_fitness(module.name, module.fitness, timestamp)
                    
                    cycle_data["mutations_applied"] = len(plan)
                else:
                    cycle_data["mutations_applied"] = 0
            else:
                cycle_data["plan_generated"] = False
                cycle_data["mutations_applied"] = 0
            
            # Step 3: Verify state after mutation
            new_is_nash = detector.detect_equilibrium(modules)
            cycle_data["post_mutation_equilibrium"] = new_is_nash
            
            cycle_results.append(cycle_data)
        
        # Verify the evolution loop ran correctly
        self.assertEqual(len(cycle_results), 3, "Should have 3 cycles")
        
        # Verify equilibrium was detected in at least one cycle
        equilibrium_cycles = [c for c in cycle_results if c["equilibrium_detected"]]
        self.assertGreaterEqual(len(equilibrium_cycles), 1, "Equilibrium should be detected in at least one cycle")
        
        # Verify plans were generated when equilibrium was detected
        for cycle_data in cycle_results:
            if cycle_data["equilibrium_detected"]:
                self.assertTrue(cycle_data["plan_generated"],
                                f"Plan should be generated when equilibrium detected in cycle {cycle_data['cycle']}")
                self.assertGreaterEqual(cycle_data["mutations_applied"], 2,
                                        f"At least 2 mutations should be applied in cycle {cycle_data['cycle']}")
        
        # Verify that after mutations, system is no longer at equilibrium
        for cycle_data in cycle_results:
            if cycle_data["mutations_applied"] > 0:
                self.assertFalse(cycle_data["post_mutation_equilibrium"],
                                 f"System should not be at equilibrium after mutations in cycle {cycle_data['cycle']}")
        
        # Verify the detector has recorded history for all cycles
        for module_name in module_names:
            history_data = detector.get_history(module_name)
            self.assertIsNotNone(history_data, f"History should exist for {module_name}")
            # Initial 5 entries + 3 cycle entries = 8 entries
            self.assertEqual(len(history_data), 8, f"History should have 8 entries for {module_name}")

    def test_nash_equilibrium_with_stable_patterns(self):
        """Integration test that: (1) Simulates a Nash equilibrium by setting up modules with stable failure/success patterns,
        (2) Verifies detector identifies equilibrium, (3) Verifies multi-module plan is generated,
        (4) Verifies plan involves changes to 3+ modules, (5) Verifies no single-module change would produce the same improvement."""
        
        # Create a more complex setup with 4 modules to ensure 3+ module changes
        modules_data = {
            "ModuleA": {"fitness": 0.6, "dependencies": ["ModuleB", "ModuleD"]},
            "ModuleB": {"fitness": 0.6, "dependencies": ["ModuleC"]},
            "ModuleC": {"fitness": 0.6, "dependencies": ["ModuleD"]},
            "ModuleD": {"fitness": 0.6, "dependencies": []}
        }
        
        # Write module data to files
        for module_name, module_data in modules_data.items():
            module_file = os.path.join(self.test_dir, f"{module_name}.json")
            with open(module_file, 'w') as f:
                json.dump(module_data, f)
        
        # Create interaction matrix with stable patterns (all equal fitness)
        interaction_matrix = {
            "ModuleA": {"ModuleA": 0.6, "ModuleB": 0.6, "ModuleC": 0.6, "ModuleD": 0.6},
            "ModuleB": {"ModuleA": 0.6, "ModuleB": 0.6, "ModuleC": 0.6, "ModuleD": 0.6},
            "ModuleC": {"ModuleA": 0.6, "ModuleB": 0.6, "ModuleC": 0.6, "ModuleD": 0.6},
            "ModuleD": {"ModuleA": 0.6, "ModuleB": 0.6, "ModuleC": 0.6, "ModuleD": 0.6}
        }
        interaction_file = os.path.join(self.test_dir, "interaction_matrix.json")
        with open(interaction_file, 'w') as f:
            json.dump(interaction_matrix, f)
        
        # Create dependency graph
        dependency_graph = {
            "ModuleA": ["ModuleB", "ModuleD"],
            "ModuleB": ["ModuleC"],
            "ModuleC": ["ModuleD"],
            "ModuleD": []
        }
        dependency_file = os.path.join(self.test_dir, "dependency_graph.json")
        with open(dependency_file, 'w') as f:
            json.dump(dependency_graph, f)
        
        # Create history with stable failure/success patterns (all modules converge to same fitness)
        history = {
            "ModuleA": [
                {"fitness": 0.3, "timestamp": 1},
                {"fitness": 0.4, "timestamp": 2},
                {"fitness": 0.5, "timestamp": 3},
                {"fitness": 0.55, "timestamp": 4},
                {"fitness": 0.6, "timestamp": 5},
                {"fitness": 0.6, "timestamp": 6},
                {"fitness": 0.6, "timestamp": 7},
                {"fitness": 0.6, "timestamp": 8},
                {"fitness": 0.6, "timestamp": 9},
                {"fitness": 0.6, "timestamp": 10}
            ],
            "ModuleB": [
                {"fitness": 0.2, "timestamp": 1},
                {"fitness": 0.35, "timestamp": 2},
                {"fitness": 0.45, "timestamp": 3},
                {"fitness": 0.5, "timestamp": 4},
                {"fitness": 0.55, "timestamp": 5},
                {"fitness": 0.6, "timestamp": 6},
                {"fitness": 0.6, "timestamp": 7},
                {"fitness": 0.6, "timestamp": 8},
                {"fitness": 0.6, "timestamp": 9},
                {"fitness": 0.6, "timestamp": 10}
            ],
            "ModuleC": [
                {"fitness": 0.25, "timestamp": 1},
                {"fitness": 0.3, "timestamp": 2},
                {"fitness": 0.4, "timestamp": 3},
                {"fitness": 0.5, "timestamp": 4},
                {"fitness": 0.55, "timestamp": 5},
                {"fitness": 0.6, "timestamp": 6},
                {"fitness": 0.6, "timestamp": 7},
                {"fitness": 0.6, "timestamp": 8},
                {"fitness": 0.6, "timestamp": 9},
                {"fitness": 0.6, "timestamp": 10}
            ],
            "ModuleD": [
                {"fitness": 0.1, "timestamp": 1},
                {"fitness": 0.2, "timestamp": 2},
                {"fitness": 0.3, "timestamp": 3},
                {"fitness": 0.4, "timestamp": 4},
                {"fitness": 0.5, "timestamp": 5},
                {"fitness": 0.55, "timestamp": 6},
                {"fitness": 0.6, "timestamp": 7},
                {"fitness": 0.6, "timestamp": 8},
                {"fitness": 0.6, "timestamp": 9},
                {"fitness": 0.6, "timestamp": 10}
            ]
        }
        history_file = os.path.join(self.test_dir, "history.json")
        with open(history_file, 'w') as f:
            json.dump(history, f)
        
        # (1) Simulate Nash equilibrium by setting up modules with stable failure/success patterns
        detector = NashDetector()
        for module_name, module_history in history.items():
            for entry in module_history:
                detector.record_fitness(module_name, entry["fitness"], entry["timestamp"])
        
        # Create mock modules
        class MockModule:
            def __init__(self, name, fitness):
                self.name = name
                self.fitness = fitness
                self.original_fitness = fitness
            def get_scores(self):
                return interaction_matrix[self.name]
            def mutate(self):
                return self
            def rollback(self):
                self.fitness = self.original_fitness
        
        module_names = ["ModuleA", "ModuleB", "ModuleC", "ModuleD"]
        modules = []
        for name in module_names:
            module_file = os.path.join(self.test_dir, f"{name}.json")
            with open(module_file, 'r') as f:
                data = json.load(f)
            modules.append(MockModule(name, data["fitness"]))
        
        # (2) Verify detector identifies equilibrium
        is_nash = detector.detect_equilibrium(modules)
        self.assertTrue(is_nash, "Nash equilibrium should be detected with stable failure/success patterns")
        
        # (3) Verify multi-module plan is generated
        forcer = MultiModuleForcer()
        plan = forcer.generate_plan(dependency_graph, {"is_equilibrium": True})
        self.assertIsNotNone(plan, "Multi-module plan should be generated")
        
        # (4) Verify plan involves changes to 3+ modules
        plan_module_names = [m.get("module") for m in plan]
        self.assertGreaterEqual(len(plan_module_names), 3, 
                                f"Plan should involve changes to 3+ modules, but only has {len(plan_module_names)}")
        
        # Verify all modules in plan are valid
        for module_name in plan_module_names:
            self.assertIn(module_name, module_names,
                          f"Module {module_name} in plan should exist in the system")
        
        # (5) Verify no single-module change would produce the same improvement
        # Simulate single-module changes and verify they don't break equilibrium
        for module_name in module_names:
            # Create a copy of modules with only one module changed
            test_modules = []
            for m in modules:
                if m.name == module_name:
                    test_modules.append(MockModule(m.name, 0.8))  # Significant change
                else:
                    test_modules.append(MockModule(m.name, m.fitness))
            
            # Check if single-module change breaks equilibrium
            single_change_nash = detector.detect_equilibrium(test_modules)
            # A single module change should NOT break the equilibrium because
            # the other modules are still at the same fitness level
            self.assertTrue(single_change_nash, 
                           f"Single-module change to {module_name} should not break equilibrium")
        
        # Verify that a multi-module change (3+ modules) does break equilibrium
        multi_change_modules = []
        for i, m in enumerate(modules):
            if i < 3:  # Change first 3 modules
                multi_change_modules.append(MockModule(m.name, 0.8))
            else:
                multi_change_modules.append(MockModule(m.name, m.fitness))
        
        multi_change_nash = detector.detect_equilibrium(multi_change_modules)
        self.assertFalse(multi_change_nash, 
                        "Multi-module change (3+ modules) should break equilibrium")
        
        # Verify the plan respects dependencies
        for mutation in plan:
            module_name = mutation["module"]
            if module_name in dependency_graph:
                deps = dependency_graph[module_name]
                for dep in deps:
                    self.assertIn(dep, plan_module_names,
                                 f"Module {module_name} depends on {dep}, which must also be in the plan")


if __name__ == '__main__':
    unittest.main()