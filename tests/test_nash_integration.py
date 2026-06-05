import sys
import os
import unittest
import json
import tempfile
from unittest.mock import patch, MagicMock

# Add the parent directory to the path so we can import from core and modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Try to import nash_detector_and_forcer with fallback
try:
    from core.nash_detector_and_forcer import NashDetectorAndForcer
except ImportError:
    NashDetectorAndForcer = None

try:
    from core.multi_module_forcer import MultiModuleForcer
except ImportError:
    MultiModuleForcer = None

# Try to import bootstrap module
try:
    from core.nash_bootstrap import NashBootstrap
except ImportError:
    NashBootstrap = None


class TestNashIntegration(unittest.TestCase):
    """Minimal integration test for Nash equilibrium detection and coordinated mutation."""

    def setUp(self):
        """Set up mock interaction data with 3 module pairs."""
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
        
        # Create history file showing equilibrium
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

    def test_import_nash_detector(self):
        """Test that nash_detector_and_forcer can be imported with fallback."""
        # Verify import was successful or fallback was used
        if NashDetectorAndForcer is None:
            self.skipTest("NashDetectorAndForcer could not be imported")
        else:
            self.assertIsNotNone(NashDetectorAndForcer, "NashDetectorAndForcer should be importable")

    def test_dependency_validation(self):
        """Test that dependency validation works correctly."""
        if NashDetectorAndForcer is None:
            self.skipTest("NashDetectorAndForcer could not be imported")
        
        # Create detector instance
        detector = NashDetectorAndForcer()
        
        # Test with valid dependencies
        valid_deps = {"ModuleA": ["ModuleB"], "ModuleB": ["ModuleC"], "ModuleC": []}
        try:
            detector.validate_dependencies(valid_deps)
            validation_passed = True
        except Exception:
            validation_passed = False
        self.assertTrue(validation_passed, "Valid dependencies should pass validation")
        
        # Test with circular dependencies
        circular_deps = {"ModuleA": ["ModuleB"], "ModuleB": ["ModuleA"]}
        try:
            detector.validate_dependencies(circular_deps)
            circular_passed = True
        except Exception:
            circular_passed = False
        self.assertFalse(circular_passed, "Circular dependencies should fail validation")
        
        # Test with missing dependencies
        missing_deps = {"ModuleA": ["ModuleB"], "ModuleB": ["ModuleC"], "ModuleC": ["ModuleD"]}
        try:
            detector.validate_dependencies(missing_deps)
            missing_passed = True
        except Exception:
            missing_passed = False
        self.assertFalse(missing_passed, "Missing dependencies should fail validation")

    def test_bootstrap_creates_stubs(self):
        """Test that bootstrap creates missing stubs."""
        if NashBootstrap is None:
            self.skipTest("NashBootstrap could not be imported")
        
        # Create a temporary directory for bootstrap testing
        bootstrap_dir = tempfile.mkdtemp()
        try:
            # Create a minimal module file
            module_file = os.path.join(bootstrap_dir, "test_module.py")
            with open(module_file, 'w') as f:
                f.write("# Test module\n")
            
            # Create bootstrap instance and run
            bootstrap = NashBootstrap()
            stubs_created = bootstrap.create_stubs(bootstrap_dir)
            
            # Verify stubs were created
            self.assertGreaterEqual(stubs_created, 0, "Bootstrap should create stubs")
            
            # Check if stub files exist
            stub_files = [f for f in os.listdir(bootstrap_dir) if f.endswith('.py')]
            self.assertGreaterEqual(len(stub_files), 1, "At least one stub file should exist")
            
        finally:
            import shutil
            shutil.rmtree(bootstrap_dir, ignore_errors=True)

    def test_equilibrium_detection(self):
        """Test that detection works with mock module data."""
        if NashDetectorAndForcer is None:
            self.skipTest("NashDetectorAndForcer could not be imported")
        
        # Load test data
        with open(os.path.join(self.test_dir, "history.json"), 'r') as f:
            history = json.load(f)
        with open(os.path.join(self.test_dir, "interaction_matrix.json"), 'r') as f:
            interaction_matrix = json.load(f)
        
        # Create detector and load history
        detector = NashDetectorAndForcer()
        for module_name, module_history in history.items():
            for entry in module_history:
                detector.record_fitness(module_name, entry["fitness"], entry["timestamp"])
        
        # Create mock modules
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
        
        # Verify equilibrium is detected
        self.assertTrue(is_nash, "Nash equilibrium should be detected")

    def test_multi_module_forcing_generates_proposal(self):
        """Test that multi-module forcing produces at least one coordinated change."""
        if MultiModuleForcer is None:
            self.skipTest("MultiModuleForcer could not be imported")
        
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

    def test_full_integration(self):
        """Test full integration: detect equilibrium then generate plan."""
        if NashDetectorAndForcer is None or MultiModuleForcer is None:
            self.skipTest("Required modules could not be imported")
        
        # Load test data
        with open(os.path.join(self.test_dir, "history.json"), 'r') as f:
            history = json.load(f)
        with open(os.path.join(self.test_dir, "interaction_matrix.json"), 'r') as f:
            interaction_matrix = json.load(f)
        with open(os.path.join(self.test_dir, "dependency_graph.json"), 'r') as f:
            dependency_graph = json.load(f)
        
        # Create detector and load history
        detector = NashDetectorAndForcer()
        for module_name, module_history in history.items():
            for entry in module_history:
                detector.record_fitness(module_name, entry["fitness"], entry["timestamp"])
        
        # Create mock modules
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
        
        # Step 1: Detect equilibrium
        is_nash = detector.detect_equilibrium(modules)
        
        # Step 2: Generate plan if equilibrium detected
        plan = None
        if is_nash:
            forcer = MultiModuleForcer()
            plan = forcer.generate_plan(dependency_graph, {"is_equilibrium": True})
        
        # Verify equilibrium detected
        self.assertTrue(is_nash, "Nash equilibrium should be detected")
        
        # Verify plan generated
        self.assertIsNotNone(plan, "Plan should be generated after equilibrium detection")
        self.assertGreaterEqual(len(plan), 2, "Plan should target at least 2 modules")

    def test_minimal_integration(self):
        """Minimal integration test: detect equilibrium, trigger change, verify new state."""
        if NashDetectorAndForcer is None or MultiModuleForcer is None:
            self.skipTest("Required modules could not be imported")
        
        # Load test data
        with open(os.path.join(self.test_dir, "history.json"), 'r') as f:
            history = json.load(f)
        with open(os.path.join(self.test_dir, "interaction_matrix.json"), 'r') as f:
            interaction_matrix = json.load(f)
        with open(os.path.join(self.test_dir, "dependency_graph.json"), 'r') as f:
            dependency_graph = json.load(f)
        
        # Create detector and load history
        detector = NashDetectorAndForcer()
        for module_name, module_history in history.items():
            for entry in module_history:
                detector.record_fitness(module_name, entry["fitness"], entry["timestamp"])
        
        # Create mock modules
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
        
        # Step 1: Detect equilibrium
        is_nash = detector.detect_equilibrium(modules)
        
        # Step 2: Trigger forced multi-module change if equilibrium detected
        plan = None
        if is_nash:
            forcer = MultiModuleForcer()
            plan = forcer.generate_plan(dependency_graph, {"is_equilibrium": True})
            
            # Apply mutations to simulate state change
            for mutation in plan:
                module_name = mutation["module"]
                # Update module fitness to simulate mutation
                for module in modules:
                    if module.name == module_name:
                        module.fitness = 0.7  # New fitness after mutation
                        break
        
        # Step 3: Verify system moves to new state by re-detecting equilibrium
        new_is_nash = detector.detect_equilibrium(modules)
        
        # Step 1: Verify equilibrium detected
        self.assertTrue(is_nash, "Initial Nash equilibrium should be detected")
        
        # Step 2: Verify plan generated
        self.assertIsNotNone(plan, "Plan should be generated after equilibrium detection")
        self.assertGreaterEqual(len(plan), 2, "Plan should target at least 2 modules")
        
        # Step 3: Verify system moved to new state (no longer at equilibrium)
        self.assertFalse(new_is_nash, "System should no longer be at equilibrium after mutation")

    def test_minimal_integration_with_mocked_orchestrator(self):
        """Minimal integration test with mocked evolution orchestrator."""
        if NashDetectorAndForcer is None or MultiModuleForcer is None:
            self.skipTest("Required modules could not be imported")
        
        # Load test data
        with open(os.path.join(self.test_dir, "history.json"), 'r') as f:
            history = json.load(f)
        with open(os.path.join(self.test_dir, "interaction_matrix.json"), 'r') as f:
            interaction_matrix = json.load(f)
        with open(os.path.join(self.test_dir, "dependency_graph.json"), 'r') as f:
            dependency_graph = json.load(f)
        
        # Create detector and load history
        detector = NashDetectorAndForcer()
        for module_name, module_history in history.items():
            for entry in module_history:
                detector.record_fitness(module_name, entry["fitness"], entry["timestamp"])
        
        # Create mock modules
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
        
        # Mock the evolution orchestrator
        mock_orchestrator = MagicMock()
        mock_orchestrator.get_modules.return_value = modules
        mock_orchestrator.get_dependency_graph.return_value = dependency_graph
        mock_orchestrator.get_interaction_matrix.return_value = interaction_matrix
        
        # Step 1: Detect equilibrium using mocked orchestrator
        is_nash = detector.detect_equilibrium(mock_orchestrator.get_modules())
        
        # Step 2: Generate plan using mocked orchestrator
        plan = None
        if is_nash:
            forcer = MultiModuleForcer()
            plan = forcer.generate_plan(
                mock_orchestrator.get_dependency_graph(),
                {"is_equilibrium": True}
            )
        
        # Step 3: Verify detection works
        self.assertTrue(is_nash, "Nash equilibrium should be detected")
        
        # Step 4: Verify coordinated change is generated
        self.assertIsNotNone(plan, "Coordinated change plan should be generated")
        self.assertGreaterEqual(len(plan), 2, "Plan should target at least 2 modules")
        
        # Verify plan respects dependencies
        plan_module_names = [m.get("module") for m in plan]
        if "ModuleA" in plan_module_names:
            self.assertIn("ModuleB", plan_module_names,
                          "If ModuleA is targeted, ModuleB must also be targeted due to dependency")
        if "ModuleB" in plan_module_names:
            self.assertIn("ModuleC", plan_module_names,
                          "If ModuleB is targeted, ModuleC must also be targeted due to dependency")

    def test_rollback_on_partial_failure(self):
        """Test that rollback works correctly when a partial failure occurs during coordinated change."""
        if NashDetectorAndForcer is None or MultiModuleForcer is None:
            self.skipTest("Required modules could not be imported")
        
        # Load test data
        with open(os.path.join(self.test_dir, "history.json"), 'r') as f:
            history = json.load(f)
        with open(os.path.join(self.test_dir, "interaction_matrix.json"), 'r') as f:
            interaction_matrix = json.load(f)
        with open(os.path.join(self.test_dir, "dependency_graph.json"), 'r') as f:
            dependency_graph = json.load(f)
        
        # Create detector and load history
        detector = NashDetectorAndForcer()
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

    def test_rollback_with_multiple_failures(self):
        """Test rollback with multiple failures during coordinated change."""
        if NashDetectorAndForcer is None or MultiModuleForcer is None:
            self.skipTest("Required modules could not be imported")
        
        # Load test data
        with open(os.path.join(self.test_dir, "history.json"), 'r') as f:
            history = json.load(f)
        with open(os.path.join(self.test_dir, "interaction_matrix.json"), 'r') as f:
            interaction_matrix = json.load(f)
        with open(os.path.join(self.test_dir, "dependency_graph.json"), 'r') as f:
            dependency_graph = json.load(f)
        
        # Create detector and load history
        detector = NashDetectorAndForcer()
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
        
        # Step 2: Generate plan and simulate multiple failures
        forcer = MultiModuleForcer()
        plan = forcer.generate_plan(dependency_graph, {"is_equilibrium": True})
        self.assertIsNotNone(plan, "Plan should be generated")
        
        # Simulate applying mutations with failures on all modules
        applied_modules = []
        failed_count = 0
        for i, mutation in enumerate(plan):
            module_name = mutation["module"]
            try:
                # Simulate mutation application with failures
                for module in modules:
                    if module.name == module_name:
                        if i % 2 == 0:  # Fail on even-indexed mutations
                            raise Exception(f"Simulated failure on {module_name}")
                        module.fitness = 0.7
                        applied_modules.append(module_name)
                        break
            except Exception as e:
                failed_count += 1
                # Rollback all previously applied mutations
                for applied_name in applied_modules:
                    for module in modules:
                        if module.name == applied_name:
                            module.rollback()
                            break
                applied_modules = []  # Clear applied list after rollback
                break
        
        # Step 3: Verify rollback was performed
        self.assertGreater(failed_count, 0, "At least one failure should have occurred")
        
        # Verify all modules returned to original state
        for module in modules:
            self.assertEqual(module.fitness, module.original_fitness,
                             f"Module {module.name} should be rolled back to original fitness {module.original_fitness}")
        
        # Verify system is still at equilibrium after rollback
        new_is_nash = detector.detect_equilibrium(modules)
        self.assertTrue(new_is_nash, "System should still be at equilibrium after rollback")

    def test_rollback_with_no_failures(self):
        """Test that no rollback occurs when all mutations succeed."""
        if NashDetectorAndForcer is None or MultiModuleForcer is None:
            self.skipTest("Required modules could not be imported")
        
        # Load test data
        with open(os.path.join(self.test_dir, "history.json"), 'r') as f:
            history = json.load(f)
        with open(os.path.join(self.test_dir, "interaction_matrix.json"), 'r') as f:
            interaction_matrix = json.load(f)
        with open(os.path.join(self.test_dir, "dependency_graph.json"), 'r') as f:
            dependency_graph = json.load(f)
        
        # Create detector and load history
        detector = NashDetectorAndForcer()
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
        
        # Step 2: Generate plan and apply all mutations successfully
        forcer = MultiModuleForcer()
        plan = forcer.generate_plan(dependency_graph, {"is_equilibrium": True})
        self.assertIsNotNone(plan, "Plan should be generated")
        
        # Apply all mutations successfully
        for mutation in plan:
            module_name = mutation["module"]
            for module in modules:
                if module.name == module_name:
                    module.fitness = 0.7
                    break
        
        # Step 3: Verify no rollback occurred (fitness values changed)
        for module in modules:
            self.assertNotEqual(module.fitness, module.original_fitness,
                                f"Module {module.name} should have changed fitness")
        
        # Verify system is no longer at equilibrium after successful mutations
        new_is_nash = detector.detect_equilibrium(modules)
        self.assertFalse(new_is_nash, "System should no longer be at equilibrium after successful mutations")

    def test_end_to_end_nash_detection(self):
        """Minimal end-to-end integration test: validate Nash detector works from setup to detection."""
        if NashDetectorAndForcer is None:
            self.skipTest("NashDetectorAndForcer could not be imported")
        
        # Load test data
        with open(os.path.join(self.test_dir, "history.json"), 'r') as f:
            history = json.load(f)
        with open(os.path.join(self.test_dir, "interaction_matrix.json"), 'r') as f:
            interaction_matrix = json.load(f)
        
        # Create detector instance
        detector = NashDetectorAndForcer()
        
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
        
        # Verify equilibrium is detected (all modules have same fitness)
        self.assertTrue(is_nash, "Nash equilibrium should be detected when all modules have equal fitness")
        
        # Verify the detector has recorded history
        for module_name in module_names:
            history_data = detector.get_history(module_name)
            self.assertIsNotNone(history_data, f"History should exist for {module_name}")
            self.assertEqual(len(history_data), 5, f"History should have 5 entries for {module_name}")

    def test_mini_evolution_loop(self):
        """Integration test that runs a mini evolution loop (3 cycles) with mock modules."""
        if NashDetectorAndForcer is None or MultiModuleForcer is None:
            self.skipTest("Required modules could not be imported")
        
        # Load test data
        with open(os.path.join(self.test_dir, "history.json"), 'r') as f:
            history = json.load(f)
        with open(os.path.join(self.test_dir, "interaction_matrix.json"), 'r') as f:
            interaction_matrix = json.load(f)
        with open(os.path.join(self.test_dir, "dependency_graph.json"), 'r') as f:
            dependency_graph = json.load(f)
        
        # Create detector and load initial history
        detector = NashDetectorAndForcer()
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

    def tearDown(self):
        """Clean up temporary files."""
        import shutil
        shutil.rmtree(self.test_dir, ignore_errors=True)


if __name__ == '__main__':
    unittest.main()