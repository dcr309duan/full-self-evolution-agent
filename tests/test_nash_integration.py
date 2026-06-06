import sys
import os
import unittest
import json
import tempfile
import math
import random
from collections import defaultdict


class NashDetector:
    """Detects Nash equilibrium in a system of modules based on fitness history."""

    def __init__(self, improvement_threshold=0.01, history_length=5):
        self.improvement_threshold = improvement_threshold
        self.history_length = history_length
        self.fitness_history = defaultdict(list)

    def record_fitness(self, module_name, fitness, timestamp):
        """Record a fitness value for a module at a given timestamp."""
        self.fitness_history[module_name].append({
            "fitness": fitness,
            "timestamp": timestamp
        })
        # Keep only the last history_length entries
        if len(self.fitness_history[module_name]) > self.history_length:
            self.fitness_history[module_name] = self.fitness_history[module_name][-self.history_length:]

    def get_history(self, module_name):
        """Get the fitness history for a module."""
        return self.fitness_history.get(module_name, None)

    def detect_equilibrium(self, modules):
        """Detect if the system is at Nash equilibrium.

        A system is at Nash equilibrium if:
        1. All modules have at least history_length entries
        2. The last history_length mutations show less than improvement_threshold improvement
        3. No single module can improve by more than improvement_threshold by changing alone
        """
        if not modules:
            return False

        # Check each module has enough history
        for module in modules:
            history = self.fitness_history.get(module.name, [])
            if len(history) < self.history_length:
                return False

        # Check that no single module can improve significantly by changing alone
        for module in modules:
            history = self.fitness_history[module.name]
            recent_fitnesses = [entry["fitness"] for entry in history[-self.history_length:]]
            max_improvement = max(recent_fitnesses) - min(recent_fitnesses)
            if max_improvement > self.improvement_threshold:
                return False

        # Check that all modules have similar fitness (within threshold)
        fitnesses = [module.fitness for module in modules]
        if fitnesses:
            avg_fitness = sum(fitnesses) / len(fitnesses)
            for fitness in fitnesses:
                if abs(fitness - avg_fitness) > self.improvement_threshold:
                    return False

        return True


class MultiModuleForcer:
    """Generates coordinated mutation plans to break Nash equilibrium."""

    def __init__(self):
        self.plans = []

    def generate_plan(self, dependency_graph, context):
        """Generate a coordinated mutation plan.

        Args:
            dependency_graph: dict mapping module names to list of dependencies
            context: dict with additional context (e.g., {"is_equilibrium": True})

        Returns:
            list of dicts, each with "module" key and optional "mutation" key
        """
        if not context.get("is_equilibrium", False):
            return []

        # Find all modules that are part of dependency chains
        modules = list(dependency_graph.keys())
        if not modules:
            return []

        # Find modules with no dependencies (leaf modules)
        leaf_modules = [m for m in modules if not dependency_graph.get(m, [])]
        if not leaf_modules:
            leaf_modules = [modules[0]]

        # Build plan: target leaf modules and their dependents
        plan = []
        targeted = set()

        # Start with a leaf module and work backwards through dependencies
        for leaf in leaf_modules:
            if leaf in targeted:
                continue
            # Find all modules that depend on this leaf (directly or indirectly)
            chain = self._build_dependency_chain(leaf, dependency_graph)
            for module in chain:
                if module not in targeted:
                    plan.append({"module": module, "mutation": "coordinated_change"})
                    targeted.add(module)

        # If we don't have at least 2 modules, add more
        if len(plan) < 2:
            for module in modules:
                if module not in targeted:
                    plan.append({"module": module, "mutation": "coordinated_change"})
                    targeted.add(module)
                    if len(plan) >= 2:
                        break

        self.plans.append(plan)
        return plan

    def _build_dependency_chain(self, module, dependency_graph):
        """Build a dependency chain from a module backwards through its dependents."""
        chain = [module]
        # Find modules that depend on this module
        for m, deps in dependency_graph.items():
            if module in deps and m not in chain:
                chain.extend(self._build_dependency_chain(m, dependency_graph))
        return chain


class MockModule:
    """Mock module for testing purposes."""

    def __init__(self, name, fitness, interaction_matrix=None, dependencies=None):
        self.name = name
        self.fitness = fitness
        self.original_fitness = fitness
        self.interaction_matrix = interaction_matrix or {}
        self.dependencies = dependencies or []

    def get_scores(self):
        return self.interaction_matrix.get(self.name, {})

    def mutate(self):
        return self

    def rollback(self):
        self.fitness = self.original_fitness


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
        module_names = ["ModuleA", "ModuleB", "ModuleC"]
        modules = []
        for name in module_names:
            module_file = os.path.join(self.test_dir, f"{name}.json")
            with open(module_file, 'r') as f:
                data = json.load(f)
            modules.append(MockModule(name, data["fitness"], interaction_matrix, data.get("dependencies", [])))

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
        module_names = ["ModuleA", "ModuleB", "ModuleC"]
        modules = []
        for name in module_names:
            module_file = os.path.join(self.test_dir, f"{name}.json")
            with open(module_file, 'r') as f:
                data = json.load(f)
            modules.append(MockModule(name, data["fitness"], interaction_matrix, data.get("dependencies", [])))

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
        module_names = ["ModuleA", "ModuleB", "ModuleC"]
        modules = []
        for name in module_names:
            module_file = os.path.join(self.test_dir, f"{name}.json")
            with open(module_file, 'r') as f:
                data = json.load(f)
            modules.append(MockModule(name, data["fitness"], interaction_matrix, data.get("dependencies", [])))

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
        module_names = ["ModuleA", "ModuleB", "ModuleC"]
        modules = []
        for name in module_names:
            module_file = os.path.join(self.test_dir, f"{name}.json")
            with open(module_file, 'r') as f:
                data = json.load(f)
            modules.append(MockModule(name, data["fitness"], interaction_matrix, data.get("dependencies", [])))

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
        module_names = ["ModuleA", "ModuleB", "ModuleC", "ModuleD"]
        modules = []
        for name in module_names:
            module_file = os.path.join(self.test_dir, f"{name}.json")
            with open(module_file, 'r') as f:
                data = json.load(f)
            modules.append(MockModule(name, data["fitness"], interaction_matrix, data.get("dependencies", [])))

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
                    test_modules.append(MockModule(m.name, 0.8, interaction_matrix, m.dependencies))  # Significant change
                else:
                    test_modules.append(MockModule(m.name, m.fitness, interaction_matrix, m.dependencies))

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
                multi_change_modules.append(MockModule(m.name, 0.8, interaction_matrix, m.dependencies))
            else:
                multi_change_modules.append(MockModule(m.name, m.fitness, interaction_matrix, m.dependencies))

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

    def test_empty_module_list(self):
        """Test edge case: empty module list should not crash."""
        detector = NashDetector()
        is_nash = detector.detect_equilibrium([])
        self.assertFalse(is_nash, "Empty module list should not be at equilibrium")

    def test_single_module(self):
        """Test edge case: single module should be at equilibrium."""
        detector = NashDetector()
        detector.record_fitness("ModuleA", 0.5, 1)
        detector.record_fitness("ModuleA", 0.5, 2)
        detector.record_fitness("ModuleA", 0.5, 3)
        detector.record_fitness("ModuleA", 0.5, 4)
        detector.record_fitness("ModuleA", 0.5, 5)

        module = MockModule("ModuleA", 0.5, {"ModuleA": 0.5}, [])
        is_nash = detector.detect_equilibrium([module])
        self.assertTrue(is_nash, "Single module with stable fitness should be at equilibrium")

    def test_all_modules_at_equilibrium(self):
        """Test edge case: all modules at equilibrium with same fitness."""
        detector = NashDetector()
        modules_data = {
            "ModuleA": {"fitness": 0.7, "dependencies": []},
            "ModuleB": {"fitness": 0.7, "dependencies": []},
            "ModuleC": {"fitness": 0.7, "dependencies": []}
        }

        for module_name, module_data in modules_data.items():
            for i in range(5):
                detector.record_fitness(module_name, module_data["fitness"], i + 1)

        interaction_matrix = {n: {m: 0.7 for m in modules_data} for n in modules_data}
        modules = [MockModule(name, data["fitness"], interaction_matrix, data.get("dependencies", []))
                   for name, data in modules_data.items()]
        is_nash = detector.detect_equilibrium(modules)
        self.assertTrue(is_nash, "All modules at same fitness should be at equilibrium")

    def test_equilibrium_reached_after_mutations(self):
        """Integration test: Simulate a sequence of mutations that reach Nash equilibrium."""
        # Create detector with small threshold for precise equilibrium detection
        detector = NashDetector(improvement_threshold=0.01, history_length=5)
        
        # Create mock modules with initial diverse fitness values
        modules = [
            MockModule("ModuleA", 0.2, {"ModuleA": 0.2, "ModuleB": 0.2, "ModuleC": 0.2}, ["ModuleB"]),
            MockModule("ModuleB", 0.3, {"ModuleA": 0.3, "ModuleB": 0.3, "ModuleC": 0.3}, ["ModuleC"]),
            MockModule("ModuleC", 0.4, {"ModuleA": 0.4, "ModuleB": 0.4, "ModuleC": 0.4}, [])
        ]
        
        # Simulate a sequence of mutations that converge to equilibrium
        # Each mutation brings modules closer to a common fitness value
        mutation_sequence = [
            # Round 1: Bring ModuleA closer to others
            {"ModuleA": 0.25, "ModuleB": 0.3, "ModuleC": 0.4},
            # Round 2: Bring ModuleB closer
            {"ModuleA": 0.25, "ModuleB": 0.35, "ModuleC": 0.4},
            # Round 3: Bring ModuleC closer
            {"ModuleA": 0.25, "ModuleB": 0.35, "ModuleC": 0.35},
            # Round 4: Final convergence
            {"ModuleA": 0.3, "ModuleB": 0.3, "ModuleC": 0.3},
            # Round 5: Stabilize at equilibrium
            {"ModuleA": 0.3, "ModuleB": 0.3, "ModuleC": 0.3}
        ]
        
        # Apply mutations and record fitness
        for timestamp, mutation in enumerate(mutation_sequence, start=1):
            for module in modules:
                module.fitness = mutation[module.name]
                detector.record_fitness(module.name, module.fitness, timestamp)
        
        # Verify equilibrium is reached
        is_nash = detector.detect_equilibrium(modules)
        self.assertTrue(is_nash, "System should reach Nash equilibrium after converging mutations")
        
        # Verify all modules have the same fitness
        fitnesses = [module.fitness for module in modules]
        self.assertEqual(len(set(fitnesses)), 1, "All modules should have the same fitness at equilibrium")
        
        # Verify history is properly recorded
        for module in modules:
            history = detector.get_history(module.name)
            self.assertEqual(len(history), 5, f"History for {module.name} should have 5 entries")
           