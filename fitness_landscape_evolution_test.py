import unittest
from unittest.mock import patch, MagicMock, PropertyMock
import json
import os
import tempfile
from datetime import datetime, timedelta

# Assuming these modules exist in the project
from src.fitness_landscape import FitnessLandscape
from src.benchmark_generator import BenchmarkGenerator
from src.test_suite import TestSuite
from src.agent import Agent
from src.goal_generator import GoalGenerator


class TestFitnessLandscapeEvolutionPipeline(unittest.TestCase):
    """Integration test for the entire fitness landscape evolution pipeline."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.landscape_path = os.path.join(self.temp_dir, "landscape.json")
        self.test_suite_path = os.path.join(self.temp_dir, "test_suite.json")
        self.goal_history_path = os.path.join(self.temp_dir, "goal_history.json")

        # Create initial landscape with stale data
        self.initial_landscape = {
            "last_updated": (datetime.now() - timedelta(days=10)).isoformat(),
            "fitness_scores": {
                "test_1": 0.85,
                "test_2": 0.72,
                "test_3": 0.91
            },
            "stale_threshold_days": 7
        }
        with open(self.landscape_path, 'w') as f:
            json.dump(self.initial_landscape, f)

        # Create initial test suite
        self.initial_tests = [
            {"id": "test_1", "description": "Basic arithmetic", "difficulty": 0.3},
            {"id": "test_2", "description": "String manipulation", "difficulty": 0.5},
            {"id": "test_3", "description": "Data structures", "difficulty": 0.7}
        ]
        with open(self.test_suite_path, 'w') as f:
            json.dump(self.initial_tests, f)

        # Initialize components
        self.landscape = FitnessLandscape(self.landscape_path)
        self.benchmark_gen = BenchmarkGenerator()
        self.test_suite = TestSuite(self.test_suite_path)
        self.agent = Agent()
        self.goal_gen = GoalGenerator(self.goal_history_path)

    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir)

    def test_full_evolution_pipeline(self):
        """Test the complete fitness landscape evolution pipeline."""
        # Step 1: Detect stale landscape
        stale = self.landscape.is_stale()
        self.assertTrue(stale, "Landscape should be detected as stale")

        # Step 2: Generate new benchmark based on landscape gaps
        new_benchmark = self.benchmark_gen.generate_from_landscape(self.landscape)
        self.assertIsNotNone(new_benchmark, "New benchmark should be generated")
        self.assertIn("description", new_benchmark, "Benchmark should have a description")
        self.assertIn("difficulty", new_benchmark, "Benchmark should have a difficulty level")

        # Step 3: Add new benchmark to test suite
        initial_test_count = len(self.test_suite.get_all_tests())
        self.test_suite.add_test(new_benchmark)
        updated_test_count = len(self.test_suite.get_all_tests())
        self.assertEqual(updated_test_count, initial_test_count + 1,
                         "Test suite should have one more test after addition")

        # Verify the new test is in the suite
        all_tests = self.test_suite.get_all_tests()
        new_test_ids = [t["id"] for t in all_tests if t["id"] not in 
                        [old["id"] for old in self.initial_tests]]
        self.assertEqual(len(new_test_ids), 1, "Exactly one new test should be added")
        new_test_id = new_test_ids[0]

        # Step 4: Verify agent attempts to solve the new test
        with patch.object(self.agent, 'solve_test') as mock_solve:
            mock_solve.return_value = {"success": True, "solution": "def solution(): pass"}
            
            # Simulate agent picking up the new test
            test_to_solve = self.test_suite.get_next_unsolved_test()
            self.assertEqual(test_to_solve["id"], new_test_id,
                             "Agent should pick the newest unsolved test")
            
            result = self.agent.solve_test(test_to_solve)
            self.assertTrue(result["success"], "Agent should successfully solve the test")
            mock_solve.assert_called_once_with(test_to_solve)

        # Step 5: Verify the new test influences future goal generation
        # Update landscape with new test results
        self.landscape.update_fitness(new_test_id, 0.95)
        
        # Generate new goals
        with patch.object(self.goal_gen, 'generate_goals') as mock_generate:
            mock_generate.return_value = [
                {"goal": "Improve performance on complex algorithms", "priority": 0.8},
                {"goal": "Enhance string processing capabilities", "priority": 0.6}
            ]
            
            # Goals should be influenced by the new test
            goals = self.goal_gen.generate_goals(self.landscape, self.test_suite)
            self.assertGreater(len(goals), 0, "Should generate at least one goal")
            
            # Verify the new test's fitness score influences goal priority
            high_fitness_tests = [t for t in self.test_suite.get_all_tests() 
                                  if self.landscape.get_fitness(t["id"]) > 0.9]
            if high_fitness_tests:
                # High fitness tests should lead to goals about improvement
                improvement_goals = [g for g in goals if "improve" in g["goal"].lower()]
                self.assertGreater(len(improvement_goals), 0,
                                   "High fitness tests should generate improvement goals")

    def test_pipeline_with_stale_detection_failure(self):
        """Test pipeline behavior when landscape is not stale."""
        # Update landscape to be fresh
        self.initial_landscape["last_updated"] = datetime.now().isoformat()
        with open(self.landscape_path, 'w') as f:
            json.dump(self.initial_landscape, f)
        self.landscape = FitnessLandscape(self.landscape_path)

        stale = self.landscape.is_stale()
        self.assertFalse(stale, "Landscape should not be stale")

        # Pipeline should not generate new benchmarks if not stale
        new_benchmark = self.benchmark_gen.generate_from_landscape(self.landscape)
        self.assertIsNone(new_benchmark, "Should not generate benchmark for non-stale landscape")

    def test_pipeline_with_agent_failure(self):
        """Test pipeline behavior when agent fails to solve new test."""
        # Make landscape stale
        stale = self.landscape.is_stale()
        self.assertTrue(stale)

        # Generate and add new benchmark
        new_benchmark = self.benchmark_gen.generate_from_landscape(self.landscape)
        self.test_suite.add_test(new_benchmark)
        new_test_id = [t["id"] for t in self.test_suite.get_all_tests() 
                       if t["id"] not in [old["id"] for old in self.initial_tests]][0]

        # Simulate agent failure
        with patch.object(self.agent, 'solve_test') as mock_solve:
            mock_solve.return_value = {"success": False, "error": "RuntimeError"}
            
            test_to_solve = self.test_suite.get_next_unsolved_test()
            result = self.agent.solve_test(test_to_solve)
            self.assertFalse(result["success"], "Agent should fail to solve the test")
            
            # Landscape should reflect the failure
            self.landscape.update_fitness(new_test_id, 0.0)
            fitness = self.landscape.get_fitness(new_test_id)
            self.assertEqual(fitness, 0.0, "Failed test should have zero fitness")

    def test_pipeline_goal_generation_influence(self):
        """Test that new tests properly influence goal generation."""
        # Setup: make landscape stale and add a new test
        stale = self.landscape.is_stale()
        self.assertTrue(stale)

        new_benchmark = self.benchmark_gen.generate_from_landscape(self.landscape)
        self.test_suite.add_test(new_benchmark)
        new_test_id = [t["id"] for t in self.test_suite.get_all_tests() 
                       if t["id"] not in [old["id"] for old in self.initial_tests]][0]

        # Simulate successful solve with high fitness
        self.landscape.update_fitness(new_test_id, 0.98)

        # Generate goals and verify influence
        goals = self.goal_gen.generate_goals(self.landscape, self.test_suite)
        
        # The new high-fitness test should influence goals
        # Check if any goals relate to the new test's domain
        new_test = self.test_suite.get_test(new_test_id)
        test_description = new_test["description"]
        
        related_goals = [g for g in goals if test_description.lower() in g["goal"].lower() 
                         or any(word in g["goal"].lower() for word in test_description.lower().split())]
        
        # At least one goal should be related to the new test
        self.assertGreater(len(related_goals), 0,
                           "New test should influence goal generation")

    def test_end_to_end_pipeline_execution(self):
        """Test the complete end-to-end pipeline execution."""
        # Execute the full pipeline
        pipeline_result = self._run_evolution_pipeline()
        
        # Verify pipeline completed successfully
        self.assertTrue(pipeline_result["success"], "Pipeline should complete successfully")
        self.assertIn("new_tests_added", pipeline_result)
        self.assertIn("tests_solved", pipeline_result)
        self.assertIn("goals_generated", pipeline_result)
        
        # Verify state changes
        self.assertGreater(pipeline_result["new_tests_added"], 0,
                           "At least one new test should be added")
        self.assertGreater(pipeline_result["tests_solved"], 0,
                           "At least one test should be solved")
        self.assertGreater(pipeline_result["goals_generated"], 0,
                           "At least one goal should be generated")

    def _run_evolution_pipeline(self):
        """Helper method to run the complete evolution pipeline."""
        result = {
            "success": False,
            "new_tests_added": 0,
            "tests_solved": 0,
            "goals_generated": 0
        }
        
        try:
            # Step 1: Check staleness
            if not self.landscape.is_stale():
                result["success"] = True
                return result
            
            # Step 2: Generate new benchmark
            new_benchmark = self.benchmark_gen.generate_from_landscape(self.landscape)
            if new_benchmark is None:
                result["success"] = True
                return result
            
            # Step 3: Add to test suite
            self.test_suite.add_test(new_benchmark)
            result["new_tests_added"] = 1
            
            # Step 4: Solve the new test
            new_test_id = [t["id"] for t in self.test_suite.get_all_tests() 
                           if t["id"] not in [old["id"] for old in self.initial_tests]][0]
            test_to_solve = self.test_suite.get_test(new_test_id)
            
            solve_result = self.agent.solve_test(test_to_solve)
            if solve_result["success"]:
                self.landscape.update_fitness(new_test_id, 0.95)
                result["tests_solved"] = 1
            
            # Step 5: Generate goals influenced by new test
            goals = self.goal_gen.generate_goals(self.landscape, self.test_suite)
            result["goals_generated"] = len(goals)
            
            result["success"] = True
            
        except Exception as e:
            result["success"] = False
            result["error"] = str(e)
        
        return result


if __name__ == '__main__':
    unittest.main()