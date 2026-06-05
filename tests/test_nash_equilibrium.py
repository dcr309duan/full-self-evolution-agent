import pytest
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.nash_detector import NashEquilibriumDetector
from src.multi_module_forcer import MultiModuleForcer

class TestNashEquilibriumMinimal:
    """Minimal test for Nash equilibrium detection and multi-module force generation."""

    def test_payoff_matrix_construction(self):
        """Test payoff matrix construction from interaction constraints."""
        # Create interaction constraints
        interaction_matrix = {
            ("module_a", "module_b"): -0.20,
            ("module_b", "module_a"): -0.20,
            ("module_a", "module_c"): -0.15,
            ("module_c", "module_a"): -0.15,
            ("module_b", "module_c"): -0.10,
            ("module_c", "module_b"): -0.10,
        }

        # Initialize detector with interaction matrix
        detector = NashEquilibriumDetector(interaction_matrix=interaction_matrix)

        # Verify payoff matrix is constructed correctly
        payoff_matrix = detector.get_payoff_matrix()
        assert payoff_matrix is not None
        assert len(payoff_matrix) > 0

        # Verify all modules are represented
        modules_in_matrix = set()
        for key in payoff_matrix.keys():
            modules_in_matrix.add(key[0])
            modules_in_matrix.add(key[1])
        assert "module_a" in modules_in_matrix
        assert "module_b" in modules_in_matrix
        assert "module_c" in modules_in_matrix

    def test_nash_detection_on_simple_2x2_case(self):
        """Test Nash detection on a simple 2x2 case."""
        # Create 2 modules with strong negative interactions
        class MockModule:
            def __init__(self, name, fitness, mutation_options):
                self.name = name
                self.fitness = fitness
                self.mutation_options = mutation_options

        module_a = MockModule("module_a", 0.90, ["opt_a", "opt_b"])
        module_b = MockModule("module_b", 0.85, ["opt_c", "opt_d"])

        # Create interaction matrix that creates a Nash equilibrium
        interaction_matrix = {
            ("module_a", "module_b"): -0.30,
            ("module_b", "module_a"): -0.30,
        }

        modules = [module_a, module_b]

        # Initialize detector
        detector = NashEquilibriumDetector(interaction_matrix=interaction_matrix)

        # Create a simple fitness evaluator
        def evaluate_fitness(module, context=None):
            base_fitness = module.fitness
            if context:
                for other_module in context:
                    key = (module.name, other_module.name)
                    if key in interaction_matrix:
                        base_fitness += interaction_matrix[key]
            return max(0.0, min(1.0, base_fitness))

        # Check if system is in Nash equilibrium
        is_equilibrium = detector.check_equilibrium(modules, evaluate_fitness)
        assert is_equilibrium is True

    def test_multi_module_force_generation(self):
        """Test multi-module force generation produces changes involving multiple modules."""
        # Create 3 modules
        class MockModule:
            def __init__(self, name, fitness, mutation_options):
                self.name = name
                self.fitness = fitness
                self.mutation_options = mutation_options

        module_a = MockModule("module_a", 0.90, ["opt_a", "opt_b"])
        module_b = MockModule("module_b", 0.85, ["opt_c", "opt_d"])
        module_c = MockModule("module_c", 0.80, ["opt_e", "opt_f"])

        # Create interaction matrix
        interaction_matrix = {
            ("module_a", "module_b"): -0.20,
            ("module_b", "module_a"): -0.20,
            ("module_a", "module_c"): -0.20,
            ("module_c", "module_a"): -0.20,
            ("module_b", "module_c"): -0.20,
            ("module_c", "module_b"): -0.20,
        }

        modules = [module_a, module_b, module_c]

        # Initialize forcer
        forcer = MultiModuleForcer()

        # Generate multi-module force plan
        plan = forcer.force_coordinated_change(modules, interaction_matrix)

        # Verify plan is valid
        assert plan is not None
        assert 'mutations' in plan
        assert len(plan['mutations']) >= 2

        # Verify each mutation references valid modules
        for mutation in plan['mutations']:
            assert 'module' in mutation
            assert 'mutation_type' in mutation
            assert mutation['module'].name in [m.name for m in modules]
            assert mutation['mutation_type'] in mutation['module'].mutation_options

    def test_full_workflow(self):
        """Test complete workflow: payoff matrix construction, Nash detection, and force generation."""
        # Create 3 modules
        class MockModule:
            def __init__(self, name, fitness, mutation_options):
                self.name = name
                self.fitness = fitness
                self.mutation_options = mutation_options

        module_a = MockModule("module_a", 0.90, ["opt_a", "opt_b"])
        module_b = MockModule("module_b", 0.85, ["opt_c", "opt_d"])
        module_c = MockModule("module_c", 0.80, ["opt_e", "opt_f"])

        # Create interaction matrix
        interaction_matrix = {
            ("module_a", "module_b"): -0.20,
            ("module_b", "module_a"): -0.20,
            ("module_a", "module_c"): -0.20,
            ("module_c", "module_a"): -0.20,
            ("module_b", "module_c"): -0.20,
            ("module_c", "module_b"): -0.20,
        }

        modules = [module_a, module_b, module_c]

        # Step 1: Construct payoff matrix
        detector = NashEquilibriumDetector(interaction_matrix=interaction_matrix)
        payoff_matrix = detector.get_payoff_matrix()
        assert payoff_matrix is not None

        # Step 2: Detect Nash equilibrium
        def evaluate_fitness(module, context=None):
            base_fitness = module.fitness
            if context:
                for other_module in context:
                    key = (module.name, other_module.name)
                    if key in interaction_matrix:
                        base_fitness += interaction_matrix[key]
            return max(0.0, min(1.0, base_fitness))

        is_equilibrium = detector.check_equilibrium(modules, evaluate_fitness)
        assert is_equilibrium is True

        # Step 3: Generate multi-module force
        forcer = MultiModuleForcer()
        plan = forcer.force_coordinated_change(modules, interaction_matrix)
        assert plan is not None
        assert len(plan['mutations']) >= 2

        # Verify the plan breaks the equilibrium
        # Apply the mutations
        for mutation in plan['mutations']:
            module = mutation['module']
            # Simulate mutation application
            module.fitness += 0.10

        # Check if equilibrium is broken
        is_still_equilibrium = detector.check_equilibrium(modules, evaluate_fitness)
        assert is_still_equilibrium is False