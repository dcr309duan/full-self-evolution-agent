import unittest
import sys
import os
import tempfile
import time
from unittest.mock import patch, MagicMock
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from curiosity_engine import CuriosityEngine, TemplateGenerator, GoalManager, Scheduler

class TestTemplateGenerator(unittest.TestCase):
    def setUp(self):
        self.generator = TemplateGenerator()

    def test_generate_valid_python_code(self):
        """Test that template generation produces valid Python code"""
        template = self.generator.generate_template('implement add function')
        # Try to compile the generated code
        try:
            compile(template, '<test>', 'exec')
            is_valid = True
        except SyntaxError:
            is_valid = False
        self.assertTrue(is_valid, f"Generated template is not valid Python: {template}")

    def test_generate_multiple_templates(self):
        """Test that multiple templates are all valid Python"""
        tasks = ['implement multiply function', 'create hello world', 'write factorial']
        for task in tasks:
            template = self.generator.generate_template(task)
            try:
                compile(template, '<test>', 'exec')
            except SyntaxError as e:
                self.fail(f"Template for '{task}' is invalid: {e}")

    def test_template_contains_expected_elements(self):
        """Test that generated templates contain function definitions"""
        template = self.generator.generate_template('implement add function')
        self.assertIn('def', template, "Template should contain function definition")
        self.assertIn('add', template.lower(), "Template should contain function name")

class TestCuriosityEngine(unittest.TestCase):
    def setUp(self):
        self.engine = CuriosityEngine()

    def test_known_solvable_task_succeeds(self):
        """Test that attempting a known-solvable task succeeds"""
        result = self.engine.attempt_task('implement add function')
        self.assertTrue(result['success'], f"Task should succeed but got: {result}")
        self.assertIn('code', result, "Result should contain generated code")
        # Verify the code actually works
        try:
            exec_globals = {}
            exec(result['code'], exec_globals)
            if 'add' in exec_globals:
                self.assertEqual(exec_globals['add'](2, 3), 5)
        except Exception as e:
            self.fail(f"Generated code failed to execute: {e}")

    def test_impossible_task_detects_failure(self):
        """Test that attempting an impossible task correctly detects failure and promotes a goal"""
        result = self.engine.attempt_task('implement halting problem solver')
        self.assertFalse(result['success'], "Impossible task should not succeed")
        self.assertIn('error', result, "Result should contain error information")
        # Check that a new goal was promoted
        self.assertIn('promoted_goal', result, "Failure should promote a new goal")
        self.assertIsNotNone(result['promoted_goal'], "Promoted goal should not be None")
        # Verify the promoted goal is different from the original impossible task
        self.assertNotEqual(result['promoted_goal'], 'implement halting problem solver')

    def test_impossible_task_returns_meaningful_error(self):
        """Test that impossible tasks return meaningful error messages"""
        result = self.engine.attempt_task('implement halting problem solver')
        self.assertIn('error', result)
        self.assertTrue(len(result['error']) > 0, "Error message should not be empty")
        self.assertIn('halt', result['error'].lower(), "Error should mention halting problem")

    def test_task_with_no_solution(self):
        """Test that tasks with no known solution are handled gracefully"""
        result = self.engine.attempt_task('solve riemann hypothesis')
        self.assertFalse(result['success'])
        self.assertIn('promoted_goal', result)

class TestGoalManager(unittest.TestCase):
    def setUp(self):
        self.manager = GoalManager()

    def test_promote_goal_creates_new_goal(self):
        """Test that promoting a goal creates a new goal"""
        original_goal = 'implement halting problem solver'
        new_goal = self.manager.promote_goal(original_goal)
        self.assertIsNotNone(new_goal)
        self.assertNotEqual(new_goal, original_goal)
        self.assertTrue(isinstance(new_goal, str))

    def test_promote_goal_is_reasonable(self):
        """Test that promoted goals are reasonable alternatives"""
        impossible_goal = 'implement halting problem solver'
        new_goal = self.manager.promote_goal(impossible_goal)
        # The new goal should be a simpler or related task
        self.assertFalse('halting' in new_goal.lower(), "Promoted goal should not be the same impossible task")

    def test_goal_history_tracking(self):
        """Test that goal history is tracked"""
        initial_count = len(self.manager.goal_history)
        self.manager.promote_goal('impossible task')
        self.assertEqual(len(self.manager.goal_history), initial_count + 1)

class TestScheduler(unittest.TestCase):
    def setUp(self):
        self.scheduler = Scheduler()

    def test_periodic_scheduling_works_correctly(self):
        """Test that periodic scheduling works correctly"""
        task_executed = [False]
        
        def test_task():
            task_executed[0] = True
        
        # Schedule a task to run after 0.1 seconds
        self.scheduler.schedule_periodic(test_task, interval=0.1)
        
        # Wait for the task to execute
        time.sleep(0.2)
        
        self.assertTrue(task_executed[0], "Scheduled task should have been executed")
        
        # Clean up
        self.scheduler.stop_all()

    def test_multiple_periodic_tasks(self):
        """Test that multiple periodic tasks can be scheduled"""
        execution_count = [0]
        
        def increment_count():
            execution_count[0] += 1
        
        # Schedule two tasks
        self.scheduler.schedule_periodic(increment_count, interval=0.05)
        self.scheduler.schedule_periodic(increment_count, interval=0.05)
        
        time.sleep(0.15)
        
        self.assertGreaterEqual(execution_count[0], 4, 
            "Multiple tasks should execute multiple times")
        
        self.scheduler.stop_all()

    def test_scheduler_stops_gracefully(self):
        """Test that the scheduler stops without errors"""
        def dummy_task():
            pass
        
        self.scheduler.schedule_periodic(dummy_task, interval=0.01)
        time.sleep(0.05)
        
        # Should not raise any exception
        self.scheduler.stop_all()
        
        # Verify no tasks are running after stop
        self.assertEqual(len(self.scheduler.active_tasks), 0)

    def test_scheduler_with_interval_accuracy(self):
        """Test that tasks are scheduled with reasonable timing accuracy"""
        execution_times = []
        
        def record_time():
            execution_times.append(time.time())
        
        self.scheduler.schedule_periodic(record_time, interval=0.1)
        time.sleep(0.35)
        self.scheduler.stop_all()
        
        # Should have executed 3-4 times in 0.35 seconds
        self.assertGreaterEqual(len(execution_times), 2, 
            "Should have executed at least 2 times")
        self.assertLessEqual(len(execution_times), 5,
            "Should not have executed too many times")

class TestIntegration(unittest.TestCase):
    def setUp(self):
        self.engine = CuriosityEngine()

    def test_full_workflow_with_solvable_task(self):
        """Test the full workflow with a solvable task"""
        # Generate template
        template = self.engine.generator.generate_template('implement add function')
        self.assertTrue(template is not None)
        
        # Attempt the task
        result = self.engine.attempt_task('implement add function')
        self.assertTrue(result['success'])
        
        # Verify the code works
        exec_globals = {}
        exec(result['code'], exec_globals)
        self.assertEqual(exec_globals['add'](2, 3), 5)

    def test_full_workflow_with_impossible_task(self):
        """Test the full workflow with an impossible task"""
        # Attempt impossible task
        result = self.engine.attempt_task('implement halting problem solver')
        self.assertFalse(result['success'])
        
        # Verify goal promotion
        self.assertIn('promoted_goal', result)
        new_goal = result['promoted_goal']
        
        # The new goal should be a valid task
        new_result = self.engine.attempt_task(new_goal)
        # It might succeed or fail, but should not raise an exception
        self.assertIn('success', new_result)

if __name__ == '__main__':
    unittest.main()