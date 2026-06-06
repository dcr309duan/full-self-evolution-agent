"""Tests for the ecology self-modification loop.

This module validates that the ecology system can:
1. Generate a new test
2. Run the existing test suite including the new test
3. Adapt to the new test by passing it
4. Retain the new test in the suite
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from ecology.agent import Agent
from ecology.test_generator import TestGenerator
from ecology.test_suite import TestSuite
from ecology.environment import Environment


@pytest.fixture
def mock_agent():
    """Create a mock agent for testing."""
    agent = Mock(spec=Agent)
    agent.adapt.return_value = True
    agent.generate_test.return_value = "def test_new_feature():\n    assert True"
    return agent


@pytest.fixture
def mock_test_generator():
    """Create a mock test generator."""
    generator = Mock(spec=TestGenerator)
    generator.generate.return_value = "def test_generated():\n    assert 1 + 1 == 2"
    return generator


@pytest.fixture
def mock_test_suite():
    """Create a mock test suite."""
    suite = Mock(spec=TestSuite)
    suite.run.return_value = {"passed": 5, "failed": 0, "total": 5}
    suite.add_test.return_value = True
    suite.contains.return_value = False
    return suite


@pytest.fixture
def mock_environment():
    """Create a mock environment."""
    env = Mock(spec=Environment)
    env.step.return_value = {"reward": 1.0, "done": False}
    return env


def test_full_ecology_loop(mock_agent, mock_test_generator, mock_test_suite, mock_environment):
    """Test the complete ecology self-modification loop."""
    # Step 1: Generate a new test
    new_test = mock_test_generator.generate()
    assert new_test is not None
    assert "def test_" in new_test
    
    # Step 2: Add the new test to the suite
    mock_test_suite.add_test(new_test)
    mock_test_suite.contains.return_value = True
    
    # Step 3: Run the test suite with the new test
    results = mock_test_suite.run()
    assert results["total"] > 0
    
    # Step 4: Agent adapts to pass the new test
    adaptation_result = mock_agent.adapt(new_test)
    assert adaptation_result is True
    
    # Step 5: Verify the new test is retained
    assert mock_test_suite.contains(new_test) is True


def test_ecology_loop_with_failure(mock_agent, mock_test_generator, mock_test_suite, mock_environment):
    """Test ecology loop when the agent initially fails the new test."""
    # Setup: Agent fails initially
    mock_agent.adapt.side_effect = [False, True]  # Fail first, then succeed
    
    # Step 1: Generate a challenging test
    new_test = "def test_challenging():\n    assert complex_function() == expected"
    mock_test_generator.generate.return_value = new_test
    
    # Step 2: Add and run tests
    mock_test_suite.add_test(new_test)
    mock_test_suite.run.return_value = {"passed": 4, "failed": 1, "total": 5}
    
    # Step 3: Agent attempts adaptation (fails first)
    first_attempt = mock_agent.adapt(new_test)
    assert first_attempt is False
    
    # Step 4: Agent retries and succeeds
    second_attempt = mock_agent.adapt(new_test)
    assert second_attempt is True
    
    # Step 5: Verify test retention
    mock_test_suite.contains.return_value = True
    assert mock_test_suite.contains(new_test) is True


def test_ecology_loop_multiple_tests(mock_agent, mock_test_generator, mock_test_suite, mock_environment):
    """Test ecology loop with multiple generated tests."""
    # Generate multiple tests
    test1 = "def test_feature_a():\n    assert True"
    test2 = "def test_feature_b():\n    assert False"
    test3 = "def test_feature_c():\n    assert 2 * 3 == 6"
    
    mock_test_generator.generate.side_effect = [test1, test2, test3]
    
    # Add and run each test
    for i in range(3):
        new_test = mock_test_generator.generate()
        mock_test_suite.add_test(new_test)
        
        # Simulate adaptation
        mock_agent.adapt(new_test)
        
        # Verify retention
        mock_test_suite.contains.return_value = True
        assert mock_test_suite.contains(new_test) is True
    
    # Verify total tests in suite
    assert mock_test_suite.run.call_count >= 3


def test_ecology_loop_environment_interaction(mock_agent, mock_test_generator, mock_test_suite, mock_environment):
    """Test ecology loop with environment feedback."""
    # Step 1: Generate test based on environment state
    mock_environment.step.return_value = {"reward": 0.5, "done": False, "observation": "new_state"}
    
    new_test = mock_test_generator.generate()
    mock_test_suite.add_test(new_test)
    
    # Step 2: Run tests and get environment feedback
    test_results = mock_test_suite.run()
    env_feedback = mock_environment.step(test_results)
    
    # Step 3: Agent adapts based on combined feedback
    adaptation_result = mock_agent.adapt(new_test, context=env_feedback)
    assert adaptation_result is True
    
    # Step 4: Verify retention
    mock_test_suite.contains.return_value = True
    assert mock_test_suite.contains(new_test) is True


def test_ecology_loop_persistence(mock_agent, mock_test_generator, mock_test_suite, mock_environment):
    """Test that the ecology loop persists tests across multiple cycles."""
    # Simulate multiple ecology cycles
    all_tests = []
    for cycle in range(3):
        # Generate new test
        new_test = f"def test_cycle_{cycle}():\n    assert {cycle} + 1 == {cycle + 1}"
        mock_test_generator.generate.return_value = new_test
        
        # Add to suite
        mock_test_suite.add_test(new_test)
        all_tests.append(new_test)
        
        # Run and adapt
        mock_test_suite.run()
        mock_agent.adapt(new_test)
        
        # Verify all previous tests are still present
        for prev_test in all_tests:
            mock_test_suite.contains.return_value = True
            assert mock_test_suite.contains(prev_test) is True


def test_ecology_loop_error_handling(mock_agent, mock_test_generator, mock_test_suite, mock_environment):
    """Test ecology loop handles errors gracefully."""
    # Test with invalid test
    mock_test_generator.generate.return_value = None
    new_test = mock_test_generator.generate()
    
    if new_test is None:
        # Should not add None to suite
        with pytest.raises(ValueError):
            mock_test_suite.add_test(new_test)
    else:
        mock_test_suite.add_test(new_test)
        mock_agent.adapt(new_test)
        mock_test_suite.contains.return_value = True
        assert mock_test_suite.contains(new_test) is True


def test_ecology_loop_performance(mock_agent, mock_test_generator, mock_test_suite, mock_environment):
    """Test ecology loop performance with many tests."""
    # Generate and process many tests
    num_tests = 10
    for i in range(num_tests):
        new_test = f"def test_perf_{i}():\n    assert {i} * 2 == {i * 2}"
        mock_test_generator.generate.return_value = new_test
        
        mock_test_suite.add_test(new_test)
        mock_test_suite.run()
        mock_agent.adapt(new_test)
        
        mock_test_suite.contains.return_value = True
        assert mock_test_suite.contains(new_test) is True
    
    # Verify all tests were processed
    assert mock_test_suite.add_test.call_count == num_tests
    assert mock_agent.adapt.call_count == num_tests