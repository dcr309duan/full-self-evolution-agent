import unittest
from unittest.mock import patch, MagicMock
import tempfile
import os
import shutil
from pathlib import Path

# Assuming the simulation engine is in a module named 'simulation_engine'
# Adjust the import path according to your project structure
from simulation_engine import SimulationEngine, DependencyGraph, Sandbox, Mutation, TestRunner

class TestSimulationEngine(unittest.TestCase):

    def setUp(self):
        # Create a temporary directory for sandbox testing
        self.test_dir = tempfile.mkdtemp()
        self.engine = SimulationEngine()

    def tearDown(self):
        # Clean up the temporary directory
        shutil.rmtree(self.test_dir)

    def test_dependency_subgraph_cloning_simple_two_module(self):
        """Test that a simple two-module dependency subgraph is cloned correctly."""
        # Create a simple dependency graph: module_a -> module_b
        dep_graph = DependencyGraph()
        dep_graph.add_dependency('module_a', 'module_b')
        
        # Clone the subgraph for module_a
        cloned_graph = self.engine.clone_subgraph(dep_graph, 'module_a')
        
        # Verify that the cloned graph contains both modules and the dependency
        self.assertIn('module_a', cloned_graph.modules)
        self.assertIn('module_b', cloned_graph.modules)
        self.assertTrue(cloned_graph.has_dependency('module_a', 'module_b'))
        # Ensure the original graph is not modified
        self.assertEqual(len(dep_graph.modules), 2)

    def test_sandbox_isolation_no_side_effects(self):
        """Test that sandbox operations do not affect the real filesystem."""
        # Create a real file in the test directory
        real_file_path = os.path.join(self.test_dir, 'real_file.txt')
        with open(real_file_path, 'w') as f:
            f.write('original content')
        
        # Create a sandbox that should isolate operations
        sandbox = Sandbox(self.test_dir)
        
        # Perform operations inside the sandbox
        sandbox_file_path = os.path.join(sandbox.path, 'sandbox_file.txt')
        with open(sandbox_file_path, 'w') as f:
            f.write('sandbox content')
        
        # Verify that the real filesystem is not affected
        self.assertTrue(os.path.exists(real_file_path))
        self.assertFalse(os.path.exists(os.path.join(self.test_dir, 'sandbox_file.txt')))
        # Verify the sandbox file exists only in the sandbox
        self.assertTrue(os.path.exists(sandbox_file_path))

    def test_mutation_application_and_test_execution_in_sandbox(self):
        """Test that mutations are applied and tests are executed within the sandbox."""
        # Create a mock mutation
        mutation = Mutation()
        mutation.apply = MagicMock()
        mutation.undo = MagicMock()
        
        # Create a mock test runner
        test_runner = TestRunner()
        test_runner.run_tests = MagicMock(return_value=True)
        
        # Create a sandbox
        sandbox = Sandbox(self.test_dir)
        
        # Execute the mutation and test in sandbox
        result = self.engine.apply_and_test(mutation, test_runner, sandbox)
        
        # Verify that mutation was applied and undone within the sandbox
        mutation.apply.assert_called_once_with(sandbox.path)
        mutation.undo.assert_called_once_with(sandbox.path)
        # Verify tests were run
        test_runner.run_tests.assert_called_once_with(sandbox.path)
        # Verify the result
        self.assertTrue(result)

    def test_handling_of_missing_dependencies(self):
        """Test that missing dependencies are handled gracefully."""
        # Create a dependency graph with a missing dependency
        dep_graph = DependencyGraph()
        dep_graph.add_dependency('module_a', 'module_b')
        dep_graph.add_dependency('module_b', 'module_c')  # module_c is missing
        
        # Attempt to clone the subgraph for module_a
        with self.assertRaises(ValueError) as context:
            self.engine.clone_subgraph(dep_graph, 'module_a')
        
        self.assertIn('Missing dependency', str(context.exception))

    def test_performance_with_larger_dependency_graphs(self):
        """Test performance with a larger dependency graph (e.g., 1000 modules)."""
        # Create a large dependency graph
        dep_graph = DependencyGraph()
        num_modules = 1000
        for i in range(num_modules):
            dep_graph.add_module(f'module_{i}')
            if i > 0:
                dep_graph.add_dependency(f'module_{i}', f'module_{i-1}')
        
        # Measure time to clone subgraph for the last module
        import time
        start_time = time.time()
        cloned_graph = self.engine.clone_subgraph(dep_graph, f'module_{num_modules-1}')
        end_time = time.time()
        
        elapsed_time = end_time - start_time
        # Assert that cloning completes within a reasonable time (e.g., < 1 second)
        self.assertLess(elapsed_time, 1.0, f"Cloning took too long: {elapsed_time:.3f} seconds")
        
        # Verify the cloned graph has all modules
        self.assertEqual(len(cloned_graph.modules), num_modules)

if __name__ == '__main__':
    unittest.main()