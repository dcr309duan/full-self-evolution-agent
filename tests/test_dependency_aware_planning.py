import unittest
from unittest.mock import Mock, patch, MagicMock
import logging
from collections import defaultdict

# Assuming the following imports from the actual codebase
# Adjust these imports based on your actual module structure
from dependency_aware_planning import (
    DependencyGraph,
    FeasibilityEstimator,
    GoalGenerator,
    FailureAnalyzer,
    PatternMiner
)

class TestDependencyAwarePlanning(unittest.TestCase):
    """Comprehensive test suite for dependency-aware planning system."""
    
    def setUp(self):
        """Set up test fixtures before each test."""
        # Create mock dependency graph
        self.dep_graph = DependencyGraph()
        
        # Define known prerequisites for testing
        # Goal A requires B and C
        # Goal B requires D
        # Goal C requires E
        # Goal D and E have no prerequisites
        self.dep_graph.add_dependency("Goal_A", ["Goal_B", "Goal_C"])
        self.dep_graph.add_dependency("Goal_B", ["Goal_D"])
        self.dep_graph.add_dependency("Goal_C", ["Goal_E"])
        
        # Initialize components
        self.feasibility_estimator = FeasibilityEstimator(self.dep_graph)
        self.goal_generator = GoalGenerator(self.dep_graph)
        self.failure_analyzer = FailureAnalyzer()
        self.pattern_miner = PatternMiner()
        
        # Set up logging capture
        self.logger = logging.getLogger('dependency_planning')
        self.logger.setLevel(logging.DEBUG)
        
    def test_feasibility_estimator_blocks_incomplete_deps(self):
        """Test that feasibility estimator correctly blocks goals with incomplete dependencies."""
        # Initially, no dependencies are complete
        self.assertFalse(self.feasibility_estimator.is_feasible("Goal_A"))
        self.assertFalse(self.feasibility_estimator.is_feasible("Goal_B"))
        self.assertFalse(self.feasibility_estimator.is_feasible("Goal_C"))
        
        # Mark D as complete - Goal_B should become feasible
        self.dep_graph.mark_complete("Goal_D")
        self.assertTrue(self.feasibility_estimator.is_feasible("Goal_B"))
        self.assertFalse(self.feasibility_estimator.is_feasible("Goal_A"))  # Still blocked by C
        
        # Mark E as complete - Goal_C becomes feasible
        self.dep_graph.mark_complete("Goal_E")
        self.assertTrue(self.feasibility_estimator.is_feasible("Goal_C"))
        self.assertFalse(self.feasibility_estimator.is_feasible("Goal_A"))  # Still blocked by B
        
        # Mark B as complete - Goal_A still blocked by C
        self.dep_graph.mark_complete("Goal_B")
        self.assertFalse(self.feasibility_estimator.is_feasible("Goal_A"))
        
        # Mark C as complete - Goal_A becomes feasible
        self.dep_graph.mark_complete("Goal_C")
        self.assertTrue(self.feasibility_estimator.is_feasible("Goal_A"))
    
    def test_blocked_goals_logged_to_failure_analysis(self):
        """Test that blocked goals are properly logged to failure analysis."""
        with self.assertLogs('dependency_planning', level='INFO') as log:
            # Attempt to check feasibility of blocked goals
            self.feasibility_estimator.check_and_log("Goal_A")
            self.feasibility_estimator.check_and_log("Goal_B")
            self.feasibility_estimator.check_and_log("Goal_C")
            
            # Verify logs contain blocked goal information
            self.assertTrue(any("Goal_A" in message and "blocked" in message 
                              for message in log.output))
            self.assertTrue(any("Goal_B" in message and "blocked" in message 
                              for message in log.output))
            self.assertTrue(any("Goal_C" in message and "blocked" in message 
                              for message in log.output))
            
            # Verify failure analysis captures blocked goals
            blocked_goals = self.failure_analyzer.get_blocked_goals()
            self.assertIn("Goal_A", blocked_goals)
            self.assertIn("Goal_B", blocked_goals)
            self.assertIn("Goal_C", blocked_goals)
    
    def test_goal_generator_respects_blocked_goals(self):
        """Test that goal generator respects blocked goals and only generates feasible ones."""
        # Initially, no goals should be generated as all are blocked
        generated_goals = self.goal_generator.generate_goals()
        self.assertEqual(len(generated_goals), 0)
        
        # Mark D as complete - Goal_B should now be generated
        self.dep_graph.mark_complete("Goal_D")
        generated_goals = self.goal_generator.generate_goals()
        self.assertIn("Goal_B", generated_goals)
        self.assertNotIn("Goal_A", generated_goals)
        self.assertNotIn("Goal_C", generated_goals)
        
        # Mark E as complete - Goal_C should now be generated
        self.dep_graph.mark_complete("Goal_E")
        generated_goals = self.goal_generator.generate_goals()
        self.assertIn("Goal_B", generated_goals)
        self.assertIn("Goal_C", generated_goals)
        self.assertNotIn("Goal_A", generated_goals)
        
        # Mark B and C as complete - Goal_A should now be generated
        self.dep_graph.mark_complete("Goal_B")
        self.dep_graph.mark_complete("Goal_C")
        generated_goals = self.goal_generator.generate_goals()
        self.assertIn("Goal_A", generated_goals)
    
    def test_marking_dependencies_complete_unblocks_goals(self):
        """Test that marking dependencies as complete properly unblocks goals."""
        # Verify initial blocked state
        self.assertTrue(self.feasibility_estimator.is_blocked("Goal_A"))
        self.assertTrue(self.feasibility_estimator.is_blocked("Goal_B"))
        self.assertTrue(self.feasibility_estimator.is_blocked("Goal_C"))
        
        # Mark D as complete and verify Goal_B is unblocked
        self.dep_graph.mark_complete("Goal_D")
        self.assertFalse(self.feasibility_estimator.is_blocked("Goal_B"))
        self.assertTrue(self.feasibility_estimator.is_blocked("Goal_A"))
        self.assertTrue(self.feasibility_estimator.is_blocked("Goal_C"))
        
        # Mark E as complete and verify Goal_C is unblocked
        self.dep_graph.mark_complete("Goal_E")
        self.assertFalse(self.feasibility_estimator.is_blocked("Goal_C"))
        self.assertTrue(self.feasibility_estimator.is_blocked("Goal_A"))
        
        # Mark B and C as complete and verify Goal_A is unblocked
        self.dep_graph.mark_complete("Goal_B")
        self.dep_graph.mark_complete("Goal_C")
        self.assertFalse(self.feasibility_estimator.is_blocked("Goal_A"))
        
        # Verify all goals are now feasible
        self.assertTrue(self.feasibility_estimator.is_feasible("Goal_A"))
        self.assertTrue(self.feasibility_estimator.is_feasible("Goal_B"))
        self.assertTrue(self.feasibility_estimator.is_feasible("Goal_C"))
    
    def test_pattern_mining_of_blocked_goals(self):
        """Test the pattern mining of blocked goals to identify common blocking patterns."""
        # Set up multiple blocked scenarios
        blocked_scenarios = [
            {"Goal_A": ["Goal_B", "Goal_C"], "Goal_B": ["Goal_D"]},
            {"Goal_X": ["Goal_Y", "Goal_Z"], "Goal_Y": ["Goal_D"]},
            {"Goal_P": ["Goal_Q", "Goal_R"], "Goal_Q": ["Goal_D"]}
        ]
        
        # Mine patterns from blocked goals
        patterns = self.pattern_miner.mine_patterns(blocked_scenarios)
        
        # Verify common blocking patterns are identified
        self.assertIsNotNone(patterns)
        self.assertIn("Goal_D", patterns.get("common_blockers", []))
        
        # Test with specific pattern detection
        specific_pattern = self.pattern_miner.find_pattern("Goal_A", blocked_scenarios)
        self.assertIsNotNone(specific_pattern)
        self.assertIn("Goal_B", specific_pattern.get("dependencies", []))
        self.assertIn("Goal_C", specific_pattern.get("dependencies", []))
        
        # Test pattern frequency analysis
        frequency_analysis = self.pattern_miner.analyze_frequency(blocked_scenarios)
        self.assertGreater(frequency_analysis.get("Goal_D", 0), 0)
        self.assertEqual(frequency_analysis.get("Goal_D", 0), 3)  # Appears in all scenarios
    
    def test_complex_dependency_chain(self):
        """Test a more complex dependency chain scenario."""
        # Build a more complex dependency graph
        complex_graph = DependencyGraph()
        complex_graph.add_dependency("Final_Goal", ["Mid_Goal_1", "Mid_Goal_2"])
        complex_graph.add_dependency("Mid_Goal_1", ["Base_Goal_1", "Base_Goal_2"])
        complex_graph.add_dependency("Mid_Goal_2", ["Base_Goal_3"])
        complex_graph.add_dependency("Base_Goal_1", [])
        complex_graph.add_dependency("Base_Goal_2", [])
        complex_graph.add_dependency("Base_Goal_3", [])
        
        estimator = FeasibilityEstimator(complex_graph)
        
        # Initially all goals should be blocked
        self.assertTrue(estimator.is_blocked("Final_Goal"))
        self.assertTrue(estimator.is_blocked("Mid_Goal_1"))
        self.assertTrue(estimator.is_blocked("Mid_Goal_2"))
        
        # Complete base goals
        complex_graph.mark_complete("Base_Goal_1")
        complex_graph.mark_complete("Base_Goal_2")
        complex_graph.mark_complete("Base_Goal_3")
        
        # Mid goals should now be unblocked
        self.assertFalse(estimator.is_blocked("Mid_Goal_1"))
        self.assertFalse(estimator.is_blocked("Mid_Goal_2"))
        self.assertTrue(estimator.is_blocked("Final_Goal"))  # Still blocked
        
        # Complete mid goals
        complex_graph.mark_complete("Mid_Goal_1")
        complex_graph.mark_complete("Mid_Goal_2")
        
        # Final goal should now be unblocked
        self.assertFalse(estimator.is_blocked("Final_Goal"))
        self.assertTrue(estimator.is_feasible("Final_Goal"))
    
    def test_edge_cases(self):
        """Test edge cases in dependency-aware planning."""
        # Test goal with no dependencies
        self.dep_graph.add_dependency("Independent_Goal", [])
        self.assertTrue(self.feasibility_estimator.is_feasible("Independent_Goal"))
        self.assertFalse(self.feasibility_estimator.is_blocked("Independent_Goal"))
        
        # Test non-existent goal
        with self.assertRaises(KeyError):
            self.feasibility_estimator.is_feasible("NonExistentGoal")
        
        # Test circular dependencies
        circular_graph = DependencyGraph()
        circular_graph.add_dependency("Goal_A", ["Goal_B"])
        circular_graph.add_dependency("Goal_B", ["Goal_A"])
        
        circular_estimator = FeasibilityEstimator(circular_graph)
        # Circular dependencies should be detected and handled
        with self.assertRaises(ValueError):
            circular_estimator.is_feasible("Goal_A")
        
        # Test marking already completed dependency
        self.dep_graph.mark_complete("Goal_D")
        # Should not raise error when marking already completed
        self.dep_graph.mark_complete("Goal_D")  # Should be idempotent
        
        # Test removing dependency
        self.dep_graph.remove_dependency("Goal_A", "Goal_B")
        # After removal, Goal_A should still be blocked by Goal_C
        self.assertTrue(self.feasibility_estimator.is_blocked("Goal_A"))

if __name__ == '__main__':
    unittest.main()