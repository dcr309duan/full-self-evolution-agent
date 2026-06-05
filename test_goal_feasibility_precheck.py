import unittest
from unittest.mock import Mock, patch
import sys
import os

# Add parent directory to path to import the module under test
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the module that contains the feasibility pre-check logic
# Adjust the import based on your actual module structure
try:
    from goal_feasibility_precheck import GoalFeasibilityPrecheck, FeasibilityStatus
except ImportError:
    # Create mock classes for testing if the module doesn't exist yet
    from enum import Enum
    
    class FeasibilityStatus(Enum):
        ALLOW = "ALLOW"
        BLOCK = "BLOCK"
        DOWNGRADE = "DOWNGRADE"
    
    class GoalFeasibilityPrecheck:
        def __init__(self, dependency_checker=None, coverage_analyzer=None):
            self.dependency_checker = dependency_checker or Mock()
            self.coverage_analyzer = coverage_analyzer or Mock()
        
        def check_feasibility(self, goal, modules=None):
            """Check feasibility of a goal based on dependencies and coverage."""
            pass


class TestGoalFeasibilityPrecheck(unittest.TestCase):
    """Test suite for the GoalFeasibilityPrecheck class."""
    
    def setUp(self):
        """Set up test fixtures before each test method."""
        self.dependency_checker = Mock()
        self.coverage_analyzer = Mock()
        self.precheck = GoalFeasibilityPrecheck(
            dependency_checker=self.dependency_checker,
            coverage_analyzer=self.coverage_analyzer
        )
        
        # Sample test data
        self.simple_goal = {
            'id': 'goal_001',
            'name': 'Implement user authentication',
            'dependencies': ['auth_lib', 'database'],
            'modules': ['auth_module', 'user_model']
        }
        
        self.complex_goal = {
            'id': 'goal_002',
            'name': 'Deploy microservices',
            'dependencies': ['docker', 'kubernetes', 'monitoring'],
            'modules': ['service_a', 'service_b', 'service_c']
        }
    
    def test_all_dependencies_met_high_coverage_allows_goal(self):
        """Test that a goal with all dependencies met and high test coverage gets ALLOW status."""
        # Arrange
        self.dependency_checker.check_dependencies.return_value = {
            'all_met': True,
            'missing': [],
            'available': ['auth_lib', 'database']
        }
        self.coverage_analyzer.analyze_coverage.return_value = {
            'overall_coverage': 85.0,
            'module_coverage': {
                'auth_module': 90.0,
                'user_model': 80.0
            }
        }
        
        # Act
        result = self.precheck.check_feasibility(self.simple_goal)
        
        # Assert
        self.assertEqual(result['status'], FeasibilityStatus.ALLOW)
        self.assertIn('reason', result)
        self.assertIn('all dependencies met', result['reason'].lower())
        self.assertIn('high coverage', result['reason'].lower())
        self.assertTrue(result['feasible'])
    
    def test_missing_critical_dependencies_blocks_goal(self):
        """Test that a goal with missing critical dependencies gets BLOCK status."""
        # Arrange
        self.dependency_checker.check_dependencies.return_value = {
            'all_met': False,
            'missing': ['critical_lib', 'required_framework'],
            'available': ['auth_lib'],
            'critical_missing': ['critical_lib']
        }
        self.coverage_analyzer.analyze_coverage.return_value = {
            'overall_coverage': 75.0,
            'module_coverage': {'auth_module': 75.0}
        }
        
        # Act
        result = self.precheck.check_feasibility(self.simple_goal)
        
        # Assert
        self.assertEqual(result['status'], FeasibilityStatus.BLOCK)
        self.assertIn('reason', result)
        self.assertIn('missing critical', result['reason'].lower())
        self.assertIn('critical_lib', result['reason'])
        self.assertFalse(result['feasible'])
    
    def test_partial_coverage_results_in_downgrade(self):
        """Test that a goal with partial coverage gets DOWNGRADE status."""
        # Arrange
        self.dependency_checker.check_dependencies.return_value = {
            'all_met': True,
            'missing': [],
            'available': ['docker', 'kubernetes', 'monitoring']
        }
        self.coverage_analyzer.analyze_coverage.return_value = {
            'overall_coverage': 45.0,
            'module_coverage': {
                'service_a': 60.0,
                'service_b': 30.0,
                'service_c': 45.0
            }
        }
        
        # Act
        result = self.precheck.check_feasibility(self.complex_goal)
        
        # Assert
        self.assertEqual(result['status'], FeasibilityStatus.DOWNGRADE)
        self.assertIn('reason', result)
        self.assertIn('partial coverage', result['reason'].lower())
        self.assertIn('45.0%', result['reason'])
        self.assertTrue(result['feasible'])
        self.assertIn('recommendations', result)
    
    def test_circular_dependencies_handled_gracefully(self):
        """Test that circular dependencies are detected and handled appropriately."""
        # Arrange
        circular_goal = {
            'id': 'goal_circular',
            'name': 'Circular dependency goal',
            'dependencies': ['module_a', 'module_b'],
            'modules': ['module_a', 'module_b']
        }
        
        self.dependency_checker.check_dependencies.side_effect = [
            # First call returns normal result
            {
                'all_met': False,
                'missing': [],
                'available': ['module_a', 'module_b'],
                'circular_dependency': True,
                'circular_chain': ['module_a', 'module_b', 'module_a']
            }
        ]
        
        # Act
        result = self.precheck.check_feasibility(circular_goal)
        
        # Assert
        self.assertIn('status', result)
        self.assertIn('circular', result.get('reason', '').lower())
        # Circular dependencies should result in BLOCK or DOWNGRADE depending on implementation
        self.assertIn(result['status'], [FeasibilityStatus.BLOCK, FeasibilityStatus.DOWNGRADE])
    
    def test_unknown_modules_handled_appropriately(self):
        """Test that unknown modules are detected and handled."""
        # Arrange
        unknown_goal = {
            'id': 'goal_unknown',
            'name': 'Goal with unknown modules',
            'dependencies': ['known_lib'],
            'modules': ['known_module', 'unknown_module_xyz']
        }
        
        self.dependency_checker.check_dependencies.return_value = {
            'all_met': True,
            'missing': [],
            'available': ['known_lib'],
            'unknown_modules': ['unknown_module_xyz']
        }
        self.coverage_analyzer.analyze_coverage.return_value = {
            'overall_coverage': 50.0,
            'module_coverage': {'known_module': 50.0},
            'unknown_modules': ['unknown_module_xyz']
        }
        
        # Act
        result = self.precheck.check_feasibility(unknown_goal)
        
        # Assert
        self.assertIn('status', result)
        self.assertIn('unknown', result.get('reason', '').lower())
        self.assertIn('unknown_module_xyz', result.get('reason', ''))
        # Unknown modules should typically result in DOWNGRADE or BLOCK
        self.assertNotEqual(result['status'], FeasibilityStatus.ALLOW)
    
    def test_empty_dependencies_and_modules(self):
        """Test edge case with empty dependencies and modules."""
        # Arrange
        empty_goal = {
            'id': 'goal_empty',
            'name': 'Empty goal',
            'dependencies': [],
            'modules': []
        }
        
        self.dependency_checker.check_dependencies.return_value = {
            'all_met': True,
            'missing': [],
            'available': []
        }
        self.coverage_analyzer.analyze_coverage.return_value = {
            'overall_coverage': 100.0,
            'module_coverage': {}
        }
        
        # Act
        result = self.precheck.check_feasibility(empty_goal)
        
        # Assert
        self.assertEqual(result['status'], FeasibilityStatus.ALLOW)
        self.assertTrue(result['feasible'])
    
    def test_none_goal_raises_exception(self):
        """Test that None goal raises appropriate exception."""
        # Act & Assert
        with self.assertRaises((ValueError, TypeError)):
            self.precheck.check_feasibility(None)
    
    def test_missing_required_fields_handled(self):
        """Test that goal with missing required fields is handled."""
        # Arrange
        invalid_goal = {
            'id': 'goal_invalid'
            # Missing 'name', 'dependencies', 'modules'
        }
        
        # Act & Assert
        with self.assertRaises(KeyError):
            self.precheck.check_feasibility(invalid_goal)
    
    def test_low_coverage_but_all_dependencies_met(self):
        """Test that very low coverage with all dependencies met results in DOWNGRADE."""
        # Arrange
        self.dependency_checker.check_dependencies.return_value = {
            'all_met': True,
            'missing': [],
            'available': ['auth_lib', 'database']
        }
        self.coverage_analyzer.analyze_coverage.return_value = {
            'overall_coverage': 10.0,
            'module_coverage': {
                'auth_module': 15.0,
                'user_model': 5.0
            }
        }
        
        # Act
        result = self.precheck.check_feasibility(self.simple_goal)
        
        # Assert
        self.assertEqual(result['status'], FeasibilityStatus.DOWNGRADE)
        self.assertIn('low coverage', result['reason'].lower())
        self.assertTrue(result['feasible'])
    
    def test_dependency_checker_failure_handling(self):
        """Test that dependency checker failures are handled gracefully."""
        # Arrange
        self.dependency_checker.check_dependencies.side_effect = Exception("Dependency checker failed")
        
        # Act & Assert
        with self.assertRaises(Exception):
            self.precheck.check_feasibility(self.simple_goal)
    
    def test_coverage_analyzer_failure_handling(self):
        """Test that coverage analyzer failures are handled gracefully."""
        # Arrange
        self.dependency_checker.check_dependencies.return_value = {
            'all_met': True,
            'missing': [],
            'available': ['auth_lib', 'database']
        }
        self.coverage_analyzer.analyze_coverage.side_effect = Exception("Coverage analyzer failed")
        
        # Act & Assert
        with self.assertRaises(Exception):
            self.precheck.check_feasibility(self.simple_goal)
    
    def test_multiple_goals_with_different_statuses(self):
        """Test processing multiple goals with different feasibility statuses."""
        # Arrange
        goals = [
            {
                'id': 'goal_allow',
                'name': 'Allow goal',
                'dependencies': ['dep1'],
                'modules': ['mod1']
            },
            {
                'id': 'goal_block',
                'name': 'Block goal',
                'dependencies': ['missing_dep'],
                'modules': ['mod2']
            },
            {
                'id': 'goal_downgrade',
                'name': 'Downgrade goal',
                'dependencies': ['dep2'],
                'modules': ['mod3']
            }
        ]
        
        # Configure mock to return different results based on goal
        def dependency_side_effect(goal):
            if goal['id'] == 'goal_allow':
                return {'all_met': True, 'missing': [], 'available': ['dep1']}
            elif goal['id'] == 'goal_block':
                return {'all_met': False, 'missing': ['missing_dep'], 'critical_missing': ['missing_dep']}
            else:
                return {'all_met': True, 'missing': [], 'available': ['dep2']}
        
        self.dependency_checker.check_dependencies.side_effect = dependency_side_effect
        
        def coverage_side_effect(goal):
            if goal['id'] == 'goal_allow':
                return {'overall_coverage': 90.0, 'module_coverage': {'mod1': 90.0}}
            elif goal['id'] == 'goal_block':
                return {'overall_coverage': 80.0, 'module_coverage': {'mod2': 80.0}}
            else:
                return {'overall_coverage': 40.0, 'module_coverage': {'mod3': 40.0}}
        
        self.coverage_analyzer.analyze_coverage.side_effect = coverage_side_effect
        
        # Act
        results = [self.precheck.check_feasibility(goal) for goal in goals]
        
        # Assert
        self.assertEqual(results[0]['status'], FeasibilityStatus.ALLOW)
        self.assertEqual(results[1]['status'], FeasibilityStatus.BLOCK)
        self.assertEqual(results[2]['status'], FeasibilityStatus.DOWNGRADE)
    
    def test_feasibility_thresholds_respected(self):
        """Test that coverage thresholds are properly respected."""
        # Arrange - Test near boundary values
        test_cases = [
            (70.0, FeasibilityStatus.ALLOW),  # High coverage
            (50.0, FeasibilityStatus.DOWNGRADE),  # Medium coverage
            (30.0, FeasibilityStatus.DOWNGRADE),  # Low coverage
            (0.0, FeasibilityStatus.DOWNGRADE),  # No coverage
        ]
        
        self.dependency_checker.check_dependencies.return_value = {
            'all_met': True,
            'missing': [],
            'available': ['test_dep']
        }
        
        for coverage, expected_status in test_cases:
            with self.subTest(coverage=coverage, expected_status=expected_status):
                # Arrange
                self.coverage_analyzer.analyze_coverage.return_value = {
                    'overall_coverage': coverage,
                    'module_coverage': {'test_module': coverage}
                }
                
                # Act
                result = self.precheck.check_feasibility({
                    'id': f'goal_{coverage}',
                    'name': f'Goal with {coverage}% coverage',
                    'dependencies': ['test_dep'],
                    'modules': ['test_module']
                })
                
                # Assert
                self.assertEqual(result['status'], expected_status)


if __name__ == '__main__':
    unittest.main()