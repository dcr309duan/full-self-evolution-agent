import sys
import os
import subprocess
import unittest
import json
import tempfile

# Add the parent directory to the path so we can import from core and modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


class TestNashIntegration(unittest.TestCase):
    """Minimal integration test for Nash equilibrium detection and coordinated mutation using subprocess."""

    def setUp(self):
        """Set up a mock scenario with 3 modules at equilibrium using subprocess."""
        # Create a temporary directory for the test
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

    def test_nash_equilibrium_detection_via_subprocess(self):
        """Test that nash_equilibrium_check detects equilibrium via subprocess."""
        # Create a script that runs nash_equilibrium_check
        script_path = os.path.join(self.test_dir, "test_nash_detection.py")
        with open(script_path, 'w') as f:
            f.write("""
import sys
import os
import json

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from core.nash_detector import NashDetector

# Load test data
test_dir = sys.argv[1]
with open(os.path.join(test_dir, "history.json"), 'r') as f:
    history = json.load(f)
with open(os.path.join(test_dir, "interaction_matrix.json"), 'r') as f:
    interaction_matrix = json.load(f)

# Create detector and load history
detector = NashDetector()
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
    module_file = os.path.join(test_dir, f"{name}.json")
    with open(module_file, 'r') as f:
        data = json.load(f)
    modules.append(MockModule(name, data["fitness"]))

# Detect equilibrium
is_nash = detector.detect_equilibrium(modules)

# Output result as JSON
result = {"is_nash": is_nash}
print(json.dumps(result))
""")
        
        # Run the script via subprocess
        result = subprocess.run(
            [sys.executable, script_path, self.test_dir],
            capture_output=True,
            text=True,
            cwd=os.path.dirname(script_path)
        )
        
        # Check that the script ran successfully
        self.assertEqual(result.returncode, 0, f"Script failed with error: {result.stderr}")
        
        # Parse the output
        output = json.loads(result.stdout.strip())
        
        # Verify that nash_equilibrium_check detects it
        self.assertTrue(output["is_nash"], "Nash equilibrium should be detected")

    def test_coordinated_mutation_planning_via_subprocess(self):
        """Test that coordinated_mutation_planner generates a plan via subprocess."""
        # Create a script that runs coordinated_mutation_planner
        script_path = os.path.join(self.test_dir, "test_coordinated_mutation.py")
        with open(script_path, 'w') as f:
            f.write("""
import sys
import os
import json

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from core.multi_module_forcer import MultiModuleForcer

# Load test data
test_dir = sys.argv[1]
with open(os.path.join(test_dir, "dependency_graph.json"), 'r') as f:
    dependency_graph = json.load(f)

# Create forcer and generate plan
forcer = MultiModuleForcer()
plan = forcer.generate_plan(dependency_graph, {"is_equilibrium": True})

# Output result as JSON
result = {"plan": plan}
print(json.dumps(result))
""")
        
        # Run the script via subprocess
        result = subprocess.run(
            [sys.executable, script_path, self.test_dir],
            capture_output=True,
            text=True,
            cwd=os.path.dirname(script_path)
        )
        
        # Check that the script ran successfully
        self.assertEqual(result.returncode, 0, f"Script failed with error: {result.stderr}")
        
        # Parse the output
        output = json.loads(result.stdout.strip())
        
        # Verify that coordinated_mutation_planner generates a plan
        self.assertIsNotNone(output["plan"], "Coordinated mutation planner should generate a plan")
        self.assertGreaterEqual(len(output["plan"]), 2, "Plan should target at least 2 modules")
        
        # Verify the plan contains valid module names
        plan_module_names = [m.get("module") for m in output["plan"]]
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
        for mutation in output["plan"]:
            self.assertIn("module", mutation, "Each mutation should have a 'module' key")
            self.assertIsInstance(mutation["module"], str, "Module name should be a string")

    def test_full_integration_via_subprocess(self):
        """Test full integration: detect equilibrium then generate plan via subprocess."""
        # Create a script that runs both nash_equilibrium_check and coordinated_mutation_planner
        script_path = os.path.join(self.test_dir, "test_full_integration.py")
        with open(script_path, 'w') as f:
            f.write("""
import sys
import os
import json

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from core.nash_detector import NashDetector
from core.multi_module_forcer import MultiModuleForcer

# Load test data
test_dir = sys.argv[1]
with open(os.path.join(test_dir, "history.json"), 'r') as f:
    history = json.load(f)
with open(os.path.join(test_dir, "interaction_matrix.json"), 'r') as f:
    interaction_matrix = json.load(f)
with open(os.path.join(test_dir, "dependency_graph.json"), 'r') as f:
    dependency_graph = json.load(f)

# Create detector and load history
detector = NashDetector()
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
    module_file = os.path.join(test_dir, f"{name}.json")
    with open(module_file, 'r') as f:
        data = json.load(f)
    modules.append(MockModule(name, data["fitness"]))

# Detect equilibrium
is_nash = detector.detect_equilibrium(modules)

# Generate plan if equilibrium detected
plan = None
if is_nash:
    forcer = MultiModuleForcer()
    plan = forcer.generate_plan(dependency_graph, {"is_equilibrium": True})

# Output result as JSON
result = {"is_nash": is_nash, "plan": plan}
print(json.dumps(result))
""")
        
        # Run the script via subprocess
        result = subprocess.run(
            [sys.executable, script_path, self.test_dir],
            capture_output=True,
            text=True,
            cwd=os.path.dirname(script_path)
        )
        
        # Check that the script ran successfully
        self.assertEqual(result.returncode, 0, f"Script failed with error: {result.stderr}")
        
        # Parse the output
        output = json.loads(result.stdout.strip())
        
        # Verify that nash_equilibrium_check detects it
        self.assertTrue(output["is_nash"], "Nash equilibrium should be detected")
        
        # Verify that coordinated_mutation_planner generates a plan
        self.assertIsNotNone(output["plan"], "Coordinated mutation planner should generate a plan")
        self.assertGreaterEqual(len(output["plan"]), 2, "Plan should target at least 2 modules")

    def test_minimal_integration(self):
        """Minimal integration test: detect equilibrium, trigger change, verify new state."""
        # Create a script that runs the full integration
        script_path = os.path.join(self.test_dir, "test_minimal_integration.py")
        with open(script_path, 'w') as f:
            f.write("""
import sys
import os
import json

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from core.nash_detector import NashDetector
from core.multi_module_forcer import MultiModuleForcer

# Load test data
test_dir = sys.argv[1]
with open(os.path.join(test_dir, "history.json"), 'r') as f:
    history = json.load(f)
with open(os.path.join(test_dir, "interaction_matrix.json"), 'r') as f:
    interaction_matrix = json.load(f)
with open(os.path.join(test_dir, "dependency_graph.json"), 'r') as f:
    dependency_graph = json.load(f)

# Create detector and load history
detector = NashDetector()
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
    module_file = os.path.join(test_dir, f"{name}.json")
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

# Output result as JSON
result = {
    "initial_is_nash": is_nash,
    "plan_generated": plan is not None,
    "plan_length": len(plan) if plan else 0,
    "new_is_nash": new_is_nash,
    "new_fitnesses": [m.fitness for m in modules]
}
print(json.dumps(result))
""")
        
        # Run the script via subprocess
        result = subprocess.run(
            [sys.executable, script_path, self.test_dir],
            capture_output=True,
            text=True,
            cwd=os.path.dirname(script_path)
        )
        
        # Check that the script ran successfully
        self.assertEqual(result.returncode, 0, f"Script failed with error: {result.stderr}")
        
        # Parse the output
        output = json.loads(result.stdout.strip())
        
        # Step 1: Verify equilibrium detected
        self.assertTrue(output["initial_is_nash"], "Initial Nash equilibrium should be detected")
        
        # Step 2: Verify plan generated
        self.assertTrue(output["plan_generated"], "Plan should be generated after equilibrium detection")
        self.assertGreaterEqual(output["plan_length"], 2, "Plan should target at least 2 modules")
        
        # Step 3: Verify system moved to new state (no longer at equilibrium)
        self.assertFalse(output["new_is_nash"], "System should no longer be at equilibrium after mutation")
        
        # Verify fitness values changed
        for fitness in output["new_fitnesses"]:
            self.assertEqual(fitness, 0.7, "All mutated modules should have new fitness 0.7")

    def tearDown(self):
        """Clean up temporary files."""
        import shutil
        shutil.rmtree(self.test_dir, ignore_errors=True)


if __name__ == '__main__':
    unittest.main()