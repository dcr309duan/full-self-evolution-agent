import os
import sys
import tempfile
import shutil
import importlib.util
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Import the modules under test
from core.ecology_pressure_engine import EcologyPressureEngine
from core.goal_generator import GoalGenerator
from tests.test_ecology_feedback import TestEcologyFeedback


class TestEcologyIntegration:
    """Integration test for the full ECOLOGY cycle."""

    @pytest.fixture
    def temp_test_dir(self):
        """Create a temporary directory with a minimal test suite."""
        temp_dir = tempfile.mkdtemp()
        original_dir = os.getcwd()
        os.chdir(temp_dir)

        # Create a minimal test file with only unit tests
        test_file = Path(temp_dir) / "test_sample.py"
        test_file.write_text("""
import pytest

def test_addition():
    assert 1 + 1 == 2

def test_subtraction():
    assert 3 - 1 == 2

class TestMath:
    def test_multiplication(self):
        assert 2 * 3 == 6

    def test_division(self):
        assert 6 / 2 == 3
""")

        yield temp_dir

        # Cleanup
        os.chdir(original_dir)
        shutil.rmtree(temp_dir)

    def test_ecology_pressure_engine_generates_novel_test_case(self, temp_test_dir):
        """Test that ecology_pressure_engine can generate a novel test case."""
        engine = EcologyPressureEngine()
        
        # Generate a novel test case
        novel_test = engine.generate_novel_test_case(temp_test_dir)
        
        assert novel_test is not None, "Should generate a novel test case"
        assert 'file' in novel_test, "Novel test case should have a file name"
        assert 'content' in novel_test, "Novel test case should have content"
        
        # Verify the test case is valid Python
        try:
            compile(novel_test['content'], str(Path(temp_test_dir) / novel_test['file']), 'exec')
        except SyntaxError as e:
            pytest.fail(f"Generated test case has invalid syntax: {e}")
        
        # Verify the test case contains test functions
        assert 'def test_' in novel_test['content'], "Generated test case should contain test functions"

    def test_novel_test_case_can_be_executed(self, temp_test_dir):
        """Test that the generated novel test case can be executed."""
        engine = EcologyPressureEngine()
        
        # Generate a novel test case
        novel_test = engine.generate_novel_test_case(temp_test_dir)
        
        # Write the test case to a file
        test_file_path = Path(temp_test_dir) / novel_test['file']
        test_file_path.write_text(novel_test['content'])
        
        # Execute the test case with pytest
        result = pytest.main([str(test_file_path), "--tb=short", "-q"])
        
        assert result == 0, f"Novel test case should pass, got exit code {result}"

    def test_agent_detects_stale_test_suite(self, temp_test_dir):
        """Test that the agent can detect when its test suite is stale and generate new tests."""
        # Create a goal generator
        goal_generator = GoalGenerator()
        
        # Create an ecology pressure engine
        engine = EcologyPressureEngine()
        
        # Simulate a stale test suite by creating a test file with old tests
        test_file = Path(temp_test_dir) / "test_old.py"
        test_file.write_text("""
import pytest

def test_old_feature():
    assert True

def test_another_old_feature():
    assert 1 + 1 == 2
""")
        
        # Check if the test suite is stale
        is_stale = goal_generator.detect_stale_test_suite(temp_test_dir)
        
        # If the test suite is stale, generate new tests
        if is_stale:
            new_tests = goal_generator.generate_new_tests(temp_test_dir)
            
            assert len(new_tests) > 0, "Should generate at least one new test"
            
            # Write and execute the new tests
            for test in new_tests:
                test_file_path = Path(temp_test_dir) / test['file']
                test_file_path.write_text(test['content'])
                
                # Execute the new test
                result = pytest.main([str(test_file_path), "--tb=short", "-q"])
                assert result == 0, f"New test {test['file']} should pass"
        
        # Verify the test suite is no longer stale
        is_stale_after = goal_generator.detect_stale_test_suite(temp_test_dir)
        assert not is_stale_after, "Test suite should not be stale after generating new tests"

    def test_full_ecology_cycle(self, temp_test_dir):
        """Test the complete ECOLOGY cycle end-to-end."""
        # Step 1: Create the ecology pressure engine and goal generator
        engine = EcologyPressureEngine()
        goal_generator = GoalGenerator()
        
        # Step 2: Generate a novel test case
        novel_test = engine.generate_novel_test_case(temp_test_dir)
        assert novel_test is not None, "Should generate a novel test case"
        
        # Step 3: Write and execute the novel test case
        test_file_path = Path(temp_test_dir) / novel_test['file']
        test_file_path.write_text(novel_test['content'])
        
        result = pytest.main([str(test_file_path), "--tb=short", "-q"])
        assert result == 0, "Novel test case should pass"
        
        # Step 4: Check if the test suite is stale
        is_stale = goal_generator.detect_stale_test_suite(temp_test_dir)
        
        # Step 5: If stale, generate new tests
        if is_stale:
            new_tests = goal_generator.generate_new_tests(temp_test_dir)
            for test in new_tests:
                test_file_path = Path(temp_test_dir) / test['file']
                test_file_path.write_text(test['content'])
                
                result = pytest.main([str(test_file_path), "--tb=short", "-q"])
                assert result == 0, f"New test {test['file']} should pass"
        
        # Step 6: Verify the test suite is no longer stale
        is_stale_after = goal_generator.detect_stale_test_suite(temp_test_dir)
        assert not is_stale_after, "Test suite should not be stale after generating new tests"

    def test_ecology_pressure_engine_generates_multiple_novel_tests(self, temp_test_dir):
        """Test that ecology_pressure_engine can generate multiple novel test cases."""
        engine = EcologyPressureEngine()
        
        # Generate multiple novel test cases
        novel_tests = []
        for _ in range(3):
            novel_test = engine.generate_novel_test_case(temp_test_dir)
            if novel_test:
                novel_tests.append(novel_test)
        
        assert len(novel_tests) > 0, "Should generate at least one novel test case"
        
        # Verify each test case is unique and valid
        file_names = [test['file'] for test in novel_tests]
        assert len(file_names) == len(set(file_names)), "Each test case should have a unique file name"
        
        for test in novel_tests:
            try:
                compile(test['content'], str(Path(temp_test_dir) / test['file']), 'exec')
            except SyntaxError as e:
                pytest.fail(f"Generated test case {test['file']} has invalid syntax: {e}")

    def test_goal_generator_detects_stale_suite_with_old_tests(self, temp_test_dir):
        """Test that goal_generator detects stale test suite with old tests."""
        goal_generator = GoalGenerator()
        
        # Create a test file with old tests (no recent modifications)
        test_file = Path(temp_test_dir) / "test_old.py"
        test_file.write_text("""
import pytest

def test_old_feature():
    assert True
""")
        
        # Set the modification time to be old (e.g., 30 days ago)
        old_time = time.time() - (30 * 24 * 60 * 60)
        os.utime(str(test_file), (old_time, old_time))
        
        # Check if the test suite is stale
        is_stale = goal_generator.detect_stale_test_suite(temp_test_dir)
        assert is_stale, "Test suite with old tests should be detected as stale"

    def test_goal_generator_generates_new_tests_for_stale_suite(self, temp_test_dir):
        """Test that goal_generator generates new tests for a stale test suite."""
        goal_generator = GoalGenerator()
        
        # Create a stale test suite
        test_file = Path(temp_test_dir) / "test_old.py"
        test_file.write_text("""
import pytest

def test_old_feature():
    assert True
""")
        
        # Generate new tests
        new_tests = goal_generator.generate_new_tests(temp_test_dir)
        
        assert len(new_tests) > 0, "Should generate at least one new test"
        
        # Verify each new test is valid and executable
        for test in new_tests:
            test_file_path = Path(temp_test_dir) / test['file']
            test_file_path.write_text(test['content'])
            
            # Verify the test file exists
            assert test_file_path.exists(), f"Test file {test['file']} should exist"
            
            # Verify the test is valid Python
            try:
                compile(test['content'], str(test_file_path), 'exec')
            except SyntaxError as e:
                pytest.fail(f"Generated test {test['file']} has invalid syntax: {e}")
            
            # Execute the test
            result = pytest.main([str(test_file_path), "--tb=short", "-q"])
            assert result == 0, f"New test {test['file']} should pass"

    def test_ecology_pressure_engine_and_goal_generator_integration(self, temp_test_dir):
        """Test the integration between ecology_pressure_engine and goal_generator."""
        engine = EcologyPressureEngine()
        goal_generator = GoalGenerator()
        
        # Step 1: Generate a novel test case using ecology_pressure_engine
        novel_test = engine.generate_novel_test_case(temp_test_dir)
        assert novel_test is not None, "Should generate a novel test case"
        
        # Step 2: Write the novel test case
        test_file_path = Path(temp_test_dir) / novel_test['file']
        test_file_path.write_text(novel_test['content'])
        
        # Step 3: Execute the novel test case
        result = pytest.main([str(test_file_path), "--tb=short", "-q"])
        assert result == 0, "Novel test case should pass"
        
        # Step 4: Check if the test suite is stale
        is_stale = goal_generator.detect_stale_test_suite(temp_test_dir)
        
        # Step 5: If stale, generate new tests using goal_generator
        if is_stale:
            new_tests = goal_generator.generate_new_tests(temp_test_dir)
            for test in new_tests:
                test_file_path = Path(temp_test_dir) / test['file']
                test_file_path.write_text(test['content'])
                
                result = pytest.main([str(test_file_path), "--tb=short", "-q"])
                assert result == 0, f"New test {test['file']} should pass"
        
        # Step 6: Verify the test suite is no longer stale
        is_stale_after = goal_generator.detect_stale_test_suite(temp_test_dir)
        assert not is_stale_after, "Test suite should not be stale after generating new tests"

    def test_ecology_feedback_integration(self, temp_test_dir):
        """Test integration with test_ecology_feedback module."""
        feedback = TestEcologyFeedback()
        
        # Create a test file
        test_file = Path(temp_test_dir) / "test_feedback.py"
        test_file.write_text("""
import pytest

def test_feedback():
    assert True
""")
        
        # Test the feedback mechanism
        result = feedback.provide_feedback(temp_test_dir)
        assert result is not None, "Feedback should be provided"

    def test_bootstrap_ecology_creates_new_test_file(self, temp_test_dir):
        """Integration test: (1) runs bootstrap_ecology, (2) verifies a new test file is created, (3) runs the new test, (4) validates the agent can adapt to the new pressure."""
        # Step 1: Run bootstrap_ecology
        engine = EcologyPressureEngine()
        goal_generator = GoalGenerator()
        
        # Bootstrap the ecology process
        bootstrap_result = engine.bootstrap_ecology(temp_test_dir)
        assert bootstrap_result is not None, "bootstrap_ecology should return a result"
        
        # Step 2: Verify a new test file is created
        test_files = list(Path(temp_test_dir).glob("test_*.py"))
        original_test_files = [f for f in test_files if f.name != "test_sample.py"]
        new_test_files = [f for f in original_test_files if f.name not in ["test_old.py", "test_feedback.py"]]
        
        # Check if any new test file was created by bootstrap_ecology
        assert len(new_test_files) > 0, "bootstrap_ecology should create at least one new test file"
        
        # Step 3: Run the new test
        for test_file in new_test_files:
            result = pytest.main([str(test_file), "--tb=short", "-q"])
            assert result == 0, f"New test file {test_file.name} should pass"
        
        # Step 4: Validate the agent can adapt to the new pressure
        # Simulate the new pressure by checking if the test suite is stale
        is_stale = goal_generator.detect_stale_test_suite(temp_test_dir)
        
        # If stale, generate new tests to adapt
        if is_stale:
            new_tests = goal_generator.generate_new_tests(temp_test_dir)
            assert len(new_tests) > 0, "Should generate new tests to adapt to pressure"
            
            for test in new_tests:
                test_file_path = Path(temp_test_dir) / test['file']
                test_file_path.write_text(test['content'])
                
                result = pytest.main([str(test_file_path), "--tb=short", "-q"])
                assert result == 0, f"Adaptation test {test['file']} should pass"
        
        # Verify the agent has adapted (test suite is no longer stale)
        is_stale_after = goal_generator.detect_stale_test_suite(temp_test_dir)
        assert not is_stale_after, "Agent should adapt to the new pressure"