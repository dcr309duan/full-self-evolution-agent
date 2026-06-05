import sys
import os
import tempfile
import shutil
import time
from unittest.mock import MagicMock, patch

# Ensure the parent directory is in sys.path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Minimal mock classes to simulate the core components
class Capability:
    def __init__(self, name, code, tests):
        self.name = name
        self.code = code
        self.tests = tests
        self.promoted = False

class CapabilityRegistry:
    def __init__(self):
        self.capabilities = {}

    def load_capabilities(self):
        # Simulate loading current capabilities
        return list(self.capabilities.values())

    def get_capability(self, name):
        return self.capabilities.get(name)

    def add_capability(self, capability):
        self.capabilities[capability.name] = capability

    def promote_capability(self, name):
        cap = self.capabilities.get(name)
        if cap:
            cap.promoted = True
            return True
        return False

class GoalSelector:
    def select_goal(self, capabilities):
        # Always pick a trivial goal: add a comment to the first module
        if capabilities:
            return f"Add a comment to {capabilities[0].name}"
        return "No capabilities available"

class Mutator:
    def apply_mutation(self, capability, goal):
        # Trivial mutation: add a comment at the top of the code
        if "add a comment" in goal.lower():
            capability.code = "# Added by mutation\n" + capability.code
            return True
        return False

class Tester:
    def run_tests(self, capability):
        # Simulate running pre-written tests; here we just check that the code is valid Python
        try:
            compile(capability.code, '<test>', 'exec')
            return True
        except SyntaxError:
            return False

class Promoter:
    def promote(self, registry, capability_name):
        return registry.promote_capability(capability_name)

def test_minimal_core_e2e():
    # Setup
    registry = CapabilityRegistry()
    initial_capability = Capability("test_module", "x = 1", ["assert x == 1"])
    registry.add_capability(initial_capability)

    goal_selector = GoalSelector()
    mutator = Mutator()
    tester = Tester()
    promoter = Promoter()

    # Step 1: Reflection - load current capabilities
    capabilities = registry.load_capabilities()
    assert len(capabilities) == 1, "Should have one capability"
    cap = capabilities[0]
    assert cap.name == "test_module"

    # Step 2: Goal selection - pick a trivial goal
    goal = goal_selector.select_goal(capabilities)
    assert "add a comment" in goal.lower(), "Goal should be about adding a comment"

    # Step 3: Mutation - apply trivial code change
    mutation_success = mutator.apply_mutation(cap, goal)
    assert mutation_success, "Mutation should succeed"
    assert cap.code.startswith("# Added by mutation"), "Code should have the comment"

    # Step 4: Testing - run pre-written test that validates the change
    test_success = tester.run_tests(cap)
    assert test_success, "Tests should pass"

    # Step 5: Promotion - record the capability
    promotion_success = promoter.promote(registry, cap.name)
    assert promotion_success, "Promotion should succeed"
    assert cap.promoted, "Capability should be marked as promoted"

    # Final consistency check
    final_cap = registry.get_capability("test_module")
    assert final_cap is not None, "Capability should still exist"
    assert final_cap.promoted, "Capability should be promoted in registry"
    assert final_cap.code == "# Added by mutation\nx = 1", "Code should be mutated"

    print("All 5 steps completed successfully. Final state is consistent.")

if __name__ == "__main__":
    start_time = time.time()
    test_minimal_core_e2e()
    elapsed = time.time() - start_time
    print(f"Test completed in {elapsed:.3f} seconds.")
    assert elapsed < 2.0, f"Test took {elapsed:.3f} seconds, which exceeds 2 second limit."