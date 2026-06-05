import unittest
from unittest.mock import Mock, patch
import numpy as np
from core.nash_solver import NashSolver, InteractionMatrix, EquilibriumState, MultiModulePlan

class TestNashSolver(unittest.TestCase):
    """Comprehensive tests for the Nash equilibrium solver."""

    def setUp(self):
        """Set up test fixtures."""
        self.solver = NashSolver()
        self.modules = ['module_A', 'module_B', 'module_C']

    def test_initialization(self):
        """Test that solver initializes with default parameters."""
        self.assertIsNotNone(self.solver)
        self.assertEqual(len(self.solver.modules), 0)
        self.assertIsNone(self.solver.interaction_matrix)

    def test_identify_equilibrium_from_synthetic_data(self):
        """Test that solver correctly identifies equilibrium states from synthetic interaction data."""
        # Create synthetic interaction matrix with known equilibrium
        # Payoff matrix: Prisoner's Dilemma style
        interaction_matrix = InteractionMatrix(
            modules=self.modules,
            matrix=np.array([
                [[3, 0], [5, 1]],  # module_A payoffs
                [[3, 5], [0, 1]],  # module_B payoffs
                [[2, 2], [2, 2]]   # module_C payoffs (neutral)
            ])
        )
        self.solver.interaction_matrix = interaction_matrix
        self.solver.modules = self.modules

        # Find equilibrium states
        equilibria = self.solver.find_equilibria()

        # Verify at least one equilibrium is found
        self.assertGreater(len(equilibria), 0)

        # Check that equilibrium is a Nash equilibrium (no player can benefit by unilaterally changing)
        for equilibrium in equilibria:
            self.assertTrue(self._is_nash_equilibrium(equilibrium, interaction_matrix))

    def test_identify_multiple_equilibria(self):
        """Test that solver can identify multiple equilibrium states."""
        # Create payoff matrix with multiple equilibria
        interaction_matrix = InteractionMatrix(
            modules=self.modules,
            matrix=np.array([
                [[2, 0], [0, 2]],  # module_A: coordination game
                [[2, 0], [0, 2]],  # module_B: coordination game
                [[1, 1], [1, 1]]   # module_C: indifferent
            ])
        )
        self.solver.interaction_matrix = interaction_matrix
        self.solver.modules = self.modules

        equilibria = self.solver.find_equilibria()

        # Should find at least 2 equilibria (both coordinating on same action)
        self.assertGreaterEqual(len(equilibria), 2)

    def test_generate_multi_module_plan_correct_dependencies(self):
        """Test that solver generates multi-module plans with correct dependencies."""
        # Set up modules with known dependencies
        self.solver.modules = self.modules
        self.solver.interaction_matrix = InteractionMatrix(
            modules=self.modules,
            matrix=np.random.rand(3, 2, 2)  # Random payoffs for testing
        )

        # Generate plan
        plan = self.solver.generate_plan(target_state='equilibrium')

        # Verify plan structure
        self.assertIsInstance(plan, MultiModulePlan)
        self.assertIn('module_A', plan.actions)
        self.assertIn('module_B', plan.actions)
        self.assertIn('module_C', plan.actions)

        # Check dependencies are correctly ordered (no circular dependencies)
        dependency_graph = plan.dependency_graph
        self.assertFalse(self._has_cycle(dependency_graph))

    def test_plan_dependency_topological_order(self):
        """Test that plan dependencies respect topological ordering."""
        # Create modules with explicit dependencies
        modules_with_deps = {
            'module_A': [],
            'module_B': ['module_A'],
            'module_C': ['module_B']
        }

        self.solver.modules = list(modules_with_deps.keys())
        self.solver.module_dependencies = modules_with_deps

        plan = self.solver.generate_plan(target_state='equilibrium')

        # Verify topological order
        executed_order = plan.execution_order
        for i, module in enumerate(executed_order):
            for dependency in modules_with_deps.get(module, []):
                dep_index = executed_order.index(dependency)
                self.assertLess(dep_index, i,
                    f"Dependency {dependency} must execute before {module}")

    def test_handle_empty_history(self):
        """Test that solver handles empty history gracefully."""
        empty_history = []
        
        # Should not raise exception
        result = self.solver.analyze_history(empty_history)
        
        # Should return empty or default equilibrium state
        self.assertIsNotNone(result)
        self.assertEqual(len(result.equilibria), 0)

    def test_handle_single_module_system(self):
        """Test that solver handles single module systems correctly."""
        single_module = ['module_A']
        self.solver.modules = single_module
        
        interaction_matrix = InteractionMatrix(
            modules=single_module,
            matrix=np.array([[[1, 0], [0, 1]]])  # Single player payoff
        )
        self.solver.interaction_matrix = interaction_matrix

        equilibria = self.solver.find_equilibria()
        
        # Should find at least one equilibrium for single module
        self.assertGreaterEqual(len(equilibria), 1)
        
        # Equilibrium should be a valid state for the single module
        for equilibrium in equilibria:
            self.assertIn(equilibrium.module_states['module_A'], [0, 1])

    def test_handle_invalid_interaction_matrix(self):
        """Test that solver handles invalid interaction matrix gracefully."""
        # Test with mismatched dimensions
        with self.assertRaises(ValueError):
            InteractionMatrix(
                modules=self.modules,
                matrix=np.array([[[1, 0], [0, 1]]])  # Wrong shape
            )

    def test_handle_non_square_payoff_matrix(self):
        """Test that solver handles non-square payoff matrices."""
        # Create asymmetric payoff matrix (different action spaces)
        interaction_matrix = InteractionMatrix(
            modules=['module_A', 'module_B'],
            matrix=np.array([
                [[1, 2, 3], [4, 5, 6]],  # module_A: 2 actions, 3 opponent actions
                [[1, 2], [3, 4], [5, 6]]  # module_B: 3 actions, 2 opponent actions
            ])
        )
        self.solver.interaction_matrix = interaction_matrix
        self.solver.modules = ['module_A', 'module_B']

        equilibria = self.solver.find_equilibria()
        self.assertIsNotNone(equilibria)

    def test_equilibrium_stability(self):
        """Test that identified equilibria are stable under small perturbations."""
        interaction_matrix = InteractionMatrix(
            modules=self.modules,
            matrix=np.array([
                [[3, 0], [0, 3]],  # module_A: coordination
                [[3, 0], [0, 3]],  # module_B: coordination
                [[2, 1], [1, 2]]   # module_C: slight preference
            ])
        )
        self.solver.interaction_matrix = interaction_matrix
        self.solver.modules = self.modules

        equilibria = self.solver.find_equilibria(stability_check=True)
        
        for equilibrium in equilibria:
            # Small perturbation should not change equilibrium
            perturbed_state = self._apply_small_perturbation(equilibrium)
            is_stable = self.solver.check_stability(perturbed_state)
            self.assertTrue(is_stable)

    def test_plan_generation_with_constraints(self):
        """Test that plan generation respects given constraints."""
        constraints = {
            'module_A': {'max_iterations': 10, 'convergence_threshold': 0.01},
            'module_B': {'max_iterations': 5, 'convergence_threshold': 0.1},
            'module_C': {'max_iterations': 15, 'convergence_threshold': 0.001}
        }

        self.solver.modules = self.modules
        self.solver.interaction_matrix = InteractionMatrix(
            modules=self.modules,
            matrix=np.random.rand(3, 2, 2)
        )

        plan = self.solver.generate_plan(
            target_state='equilibrium',
            constraints=constraints
        )

        # Verify constraints are reflected in the plan
        for module_name, module_constraints in constraints.items():
            module_plan = plan.module_plans[module_name]
            self.assertEqual(module_plan.max_iterations, module_constraints['max_iterations'])
            self.assertEqual(module_plan.convergence_threshold, module_constraints['convergence_threshold'])

    def test_convergence_to_equilibrium(self):
        """Test that iterative algorithm converges to equilibrium."""
        # Create a simple game with known equilibrium
        interaction_matrix = InteractionMatrix(
            modules=['module_A', 'module_B'],
            matrix=np.array([
                [[2, 0], [0, 1]],  # module_A: prefers action 0 if B chooses 0
                [[2, 0], [0, 1]]   # module_B: prefers action 0 if A chooses 0
            ])
        )
        self.solver.interaction_matrix = interaction_matrix
        self.solver.modules = ['module_A', 'module_B']

        # Run iterative algorithm
        initial_state = {'module_A': 1, 'module_B': 1}  # Start from suboptimal state
        final_state = self.solver.iterate_to_equilibrium(initial_state, max_iterations=100)

        # Should converge to (0,0) which is the Nash equilibrium
        self.assertEqual(final_state['module_A'], 0)
        self.assertEqual(final_state['module_B'], 0)

    def _is_nash_equilibrium(self, equilibrium, interaction_matrix):
        """Helper method to verify Nash equilibrium condition."""
        for module_idx, module in enumerate(self.modules):
            current_action = equilibrium.module_states[module]
            current_payoff = interaction_matrix.get_payoff(module_idx, current_action)
            
            # Check all alternative actions
            for alt_action in range(interaction_matrix.num_actions):
                if alt_action != current_action:
                    alt_payoff = interaction_matrix.get_payoff(module_idx, alt_action)
                    if alt_payoff > current_payoff:
                        return False
        return True

    def _has_cycle(self, graph):
        """Helper method to detect cycles in dependency graph."""
        visited = set()
        rec_stack = set()
        
        def dfs(node):
            visited.add(node)
            rec_stack.add(node)
            
            for neighbor in graph.get(node, []):
                if neighbor not in visited:
                    if dfs(neighbor):
                        return True
                elif neighbor in rec_stack:
                    return True
            
            rec_stack.remove(node)
            return False
        
        for node in graph:
            if node not in visited:
                if dfs(node):
                    return True
        return False

    def _apply_small_perturbation(self, equilibrium, epsilon=0.1):
        """Helper method to apply small perturbation to equilibrium state."""
        perturbed = {}
        for module, state in equilibrium.module_states.items():
            if np.random.random() < epsilon:
                perturbed[module] = 1 - state  # Flip action with small probability
            else:
                perturbed[module] = state
        return perturbed


class TestInteractionMatrix(unittest.TestCase):
    """Tests for the InteractionMatrix class."""

    def test_matrix_creation(self):
        """Test that InteractionMatrix is created correctly."""
        modules = ['A', 'B']
        matrix_data = np.array([[[1, 2], [3, 4]], [[5, 6], [7, 8]]])
        im = InteractionMatrix(modules=modules, matrix=matrix_data)
        
        self.assertEqual(im.num_modules, 2)
        self.assertEqual(im.num_actions, 2)
        self.assertEqual(im.modules, modules)

    def test_get_payoff(self):
        """Test that get_payoff returns correct values."""
        modules = ['A', 'B']
        matrix_data = np.array([[[1, 2], [3, 4]], [[5, 6], [7, 8]]])
        im = InteractionMatrix(modules=modules, matrix=matrix_data)
        
        self.assertEqual(im.get_payoff(0, 0), 1)
        self.assertEqual(im.get_payoff(1, 1), 8)


class TestEquilibriumState(unittest.TestCase):
    """Tests for the EquilibriumState class."""

    def test_state_creation(self):
        """Test that EquilibriumState is created correctly."""
        state = EquilibriumState(
            module_states={'A': 0, 'B': 1},
            payoff=3.5,
            is_stable=True
        )
        
        self.assertEqual(state.module_states['A'], 0)
        self.assertEqual(state.module_states['B'], 1)
        self.assertEqual(state.payoff, 3.5)
        self.assertTrue(state.is_stable)


class TestMultiModulePlan(unittest.TestCase):
    """Tests for the MultiModulePlan class."""

    def test_plan_creation(self):
        """Test that MultiModulePlan is created correctly."""
        plan = MultiModulePlan(
            actions={'A': 'action1', 'B': 'action2'},
            dependency_graph={'A': [], 'B': ['A']},
            execution_order=['A', 'B']
        )
        
        self.assertIn('A', plan.actions)
        self.assertIn('B', plan.actions)
        self.assertEqual(plan.execution_order, ['A', 'B'])


if __name__ == '__main__':
    unittest.main()