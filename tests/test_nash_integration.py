import sys
import os
import unittest
import json
import tempfile

# Add the parent directory to the path so we can import from core and modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from nash_detector_and_forcer import NashDetectorAndForcer
from multi_module_forcer import MultiModuleForcer


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

    def test_equilibrium_detection(self):
        """Test that equilibrium detection works with mock data."""
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
        """Test that multi-module forcing generates at least one coordinated change proposal."""
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

    def tearDown(self):
        """Clean up temporary files."""
        import shutil
        shutil.rmtree(self.test_dir, ignore_errors=True)


if __name__ == '__main__':
    unittest.main()