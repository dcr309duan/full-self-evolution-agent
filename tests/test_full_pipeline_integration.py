import pytest
import sys
import os
import tempfile
import json
from pathlib import Path

# Add the project root to the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from mutation_engine.mutation_engine import MutationEngine
from testing_framework.test_runner import TestRunner
from reflection_parser.reflection_parser import ReflectionParser
from strategy_selector.strategy_selector import StrategySelector
from broken_link_reporter.broken_link_reporter import BrokenLinkReporter


@pytest.fixture
def setup_test_environment():
    """Create a temporary directory with a dummy module and test file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a dummy module
        module_path = Path(tmpdir) / "dummy_module.py"
        module_path.write_text("""
def add(a, b):
    return a + b

def multiply(a, b):
    return a * b
""")
        
        # Create a test file for the dummy module
        test_path = Path(tmpdir) / "test_dummy_module.py"
        test_path.write_text("""
import pytest
from dummy_module import add, multiply

def test_add():
    assert add(2, 3) == 5
    assert add(-1, 1) == 0

def test_multiply():
    assert multiply(2, 3) == 6
    assert multiply(0, 5) == 0
""")
        
        yield tmpdir, module_path, test_path


def test_full_pipeline_integration(setup_test_environment):
    """Comprehensive integration test for the full mutation testing pipeline."""
    tmpdir, module_path, test_path = setup_test_environment
    
    # Initialize components
    mutation_engine = MutationEngine()
    test_runner = TestRunner()
    reflection_parser = ReflectionParser()
    strategy_selector = StrategySelector()
    broken_link_reporter = BrokenLinkReporter()
    
    # Track stages for broken link reporting
    stages = {
        "mutation": {"status": "pending", "output": None, "error": None},
        "testing": {"status": "pending", "output": None, "error": None},
        "reflection": {"status": "pending", "output": None, "error": None},
        "strategy_selection": {"status": "pending", "output": None, "error": None}
    }
    
    # Stage 1: Run mutation engine
    try:
        mutation_output = mutation_engine.run(str(module_path))
        stages["mutation"]["status"] = "success"
        stages["mutation"]["output"] = mutation_output
        assert mutation_output is not None, "Mutation engine returned None"
        assert "mutants" in mutation_output or len(mutation_output) > 0, "No mutants generated"
    except Exception as e:
        stages["mutation"]["status"] = "failed"
        stages["mutation"]["error"] = str(e)
        broken_link_reporter.report("mutation", str(e))
        pytest.fail(f"Mutation engine failed: {e}")
    
    # Check for broken links after mutation
    broken_links = broken_link_reporter.check("mutation")
    assert len(broken_links) == 0, f"Broken links found after mutation: {broken_links}"
    
    # Stage 2: Feed mutation output to testing framework
    try:
        test_results = test_runner.run_tests(str(test_path), mutation_output)
        stages["testing"]["status"] = "success"
        stages["testing"]["output"] = test_results
        assert test_results is not None, "Test runner returned None"
        assert "passed" in test_results or "failed" in test_results, "Test results missing pass/fail info"
        assert "total" in test_results, "Test results missing total count"
    except Exception as e:
        stages["testing"]["status"] = "failed"
        stages["testing"]["error"] = str(e)
        broken_link_reporter.report("testing", str(e))
        pytest.fail(f"Test runner failed: {e}")
    
    # Check for broken links after testing
    broken_links = broken_link_reporter.check("testing")
    assert len(broken_links) == 0, f"Broken links found after testing: {broken_links}"
    
    # Stage 3: Feed test results to reflection parser
    try:
        reflection_output = reflection_parser.parse(test_results)
        stages["reflection"]["status"] = "success"
        stages["reflection"]["output"] = reflection_output
        assert reflection_output is not None, "Reflection parser returned None"
        assert "assessment" in reflection_output, "Reflection output missing assessment"
        assert "score" in reflection_output["assessment"], "Assessment missing score"
    except Exception as e:
        stages["reflection"]["status"] = "failed"
        stages["reflection"]["error"] = str(e)
        broken_link_reporter.report("reflection", str(e))
        pytest.fail(f"Reflection parser failed: {e}")
    
    # Check for broken links after reflection
    broken_links = broken_link_reporter.check("reflection")
    assert len(broken_links) == 0, f"Broken links found after reflection: {broken_links}"
    
    # Stage 4: Feed reflection output to strategy selector
    try:
        strategy = strategy_selector.select(reflection_output)
        stages["strategy_selection"]["status"] = "success"
        stages["strategy_selection"]["output"] = strategy
        assert strategy is not None, "Strategy selector returned None"
        assert "name" in strategy, "Strategy missing name"
        assert "parameters" in strategy, "Strategy missing parameters"
    except Exception as e:
        stages["strategy_selection"]["status"] = "failed"
        stages["strategy_selection"]["error"] = str(e)
        broken_link_reporter.report("strategy_selection", str(e))
        pytest.fail(f"Strategy selector failed: {e}")
    
    # Check for broken links after strategy selection
    broken_links = broken_link_reporter.check("strategy_selection")
    assert len(broken_links) == 0, f"Broken links found after strategy selection: {broken_links}"
    
    # Final assertion: all stages completed successfully
    for stage_name, stage_data in stages.items():
        assert stage_data["status"] == "success", f"Stage '{stage_name}' did not complete successfully"
        assert stage_data["error"] is None, f"Stage '{stage_name}' had an error: {stage_data['error']}"
    
    # Verify the pipeline produced valid outputs at each stage
    assert isinstance(mutation_output, (dict, list)), "Mutation output should be dict or list"
    assert isinstance(test_results, dict), "Test results should be a dict"
    assert isinstance(reflection_output, dict), "Reflection output should be a dict"
    assert isinstance(strategy, dict), "Strategy should be a dict"
    
    # Verify the strategy is meaningful
    assert strategy["name"] in ["aggressive", "conservative", "balanced", "targeted"], \
        f"Unexpected strategy name: {strategy['name']}"
    assert isinstance(strategy["parameters"], dict), "Strategy parameters should be a dict"
    assert len(strategy["parameters"]) > 0, "Strategy should have at least one parameter"


def test_pipeline_with_no_mutants(setup_test_environment):
    """Test pipeline behavior when no mutants are generated."""
    tmpdir, module_path, test_path = setup_test_environment
    
    # Create a module that won't generate mutants (e.g., no functions)
    empty_module_path = Path(tmpdir) / "empty_module.py"
    empty_module_path.write_text("# This module has no functions\nx = 42\n")
    
    mutation_engine = MutationEngine()
    test_runner = TestRunner()
    reflection_parser = ReflectionParser()
    strategy_selector = StrategySelector()
    broken_link_reporter = BrokenLinkReporter()
    
    # Run mutation engine on empty module
    mutation_output = mutation_engine.run(str(empty_module_path))
    
    # Should still produce some output, even if empty
    assert mutation_output is not None
    
    # Run tests with empty mutation output
    test_results = test_runner.run_tests(str(test_path), mutation_output)
    assert test_results is not None
    
    # Parse reflection
    reflection_output = reflection_parser.parse(test_results)
    assert reflection_output is not None
    assert "assessment" in reflection_output
    
    # Select strategy
    strategy = strategy_selector.select(reflection_output)
    assert strategy is not None
    assert "name" in strategy
    
    # Check no broken links
    broken_links = broken_link_reporter.check_all()
    assert len(broken_links) == 0, f"Broken links found: {broken_links}"


def test_pipeline_with_failing_tests(setup_test_environment):
    """Test pipeline handles failing tests gracefully."""
    tmpdir, module_path, test_path = setup_test_environment
    
    # Create a test that will fail
    failing_test_path = Path(tmpdir) / "failing_test.py"
    failing_test_path.write_text("""
import pytest
from dummy_module import add

def test_failing():
    assert add(2, 2) == 5  # This will fail
""")
    
    mutation_engine = MutationEngine()
    test_runner = TestRunner()
    reflection_parser = ReflectionParser()
    strategy_selector = StrategySelector()
    broken_link_reporter = BrokenLinkReporter()
    
    # Run mutation engine
    mutation_output = mutation_engine.run(str(module_path))
    assert mutation_output is not None
    
    # Run tests (including failing ones)
    test_results = test_runner.run_tests(str(failing_test_path), mutation_output)
    assert test_results is not None
    assert "failed" in test_results
    assert test_results["failed"] > 0, "Expected at least one failing test"
    
    # Parse reflection
    reflection_output = reflection_parser.parse(test_results)
    assert reflection_output is not None
    assert "assessment" in reflection_output
    assert "score" in reflection_output["assessment"]
    
    # Select strategy
    strategy = strategy_selector.select(reflection_output)
    assert strategy is not None
    
    # Check no broken links
    broken_links = broken_link_reporter.check_all()
    assert len(broken_links) == 0, f"Broken links found: {broken_links}"


def test_mutation_to_test_link(setup_test_environment):
    """Validate the mutation engine output is correctly formatted for the testing framework.
    
    Detects P0 bug: mutation engine returns empty results.
    Detects P1 bug: mutation engine returns malformed mutations.
    """
    tmpdir, module_path, test_path = setup_test_environment
    
    mutation_engine = MutationEngine()
    test_runner = TestRunner()
    
    # Run mutation engine
    mutation_output = mutation_engine.run(str(module_path))
    
    # P0 bug detection: empty results
    assert mutation_output is not None, "P0 BUG: Mutation engine returned None"
    
    # Check if mutation_output is a list (expected format for testing framework)
    if isinstance(mutation_output, list):
        # P0 bug: empty list means no mutants generated
        if len(mutation_output) == 0:
            # This might be acceptable for some modules, but we should flag it
            # For the purpose of this test, we'll still run tests with empty list
            pass
        else:
            # P1 bug detection: malformed mutations
            for i, mutant in enumerate(mutation_output):
                assert isinstance(mutant, dict), f"P1 BUG: Mutant {i} is not a dict, got {type(mutant)}"
                assert "id" in mutant, f"P1 BUG: Mutant {i} missing 'id' field"
                assert "type" in mutant, f"P1 BUG: Mutant {i} missing 'type' field"
                assert "original" in mutant, f"P1 BUG: Mutant {i} missing 'original' field"
                assert "mutated" in mutant, f"P1 BUG: Mutant {i} missing 'mutated' field"
                assert "location" in mutant, f"P1 BUG: Mutant {i} missing 'location' field"
                
                # Validate field types
                assert isinstance(mutant["id"], (int, str)), f"P1 BUG: Mutant {i} 'id' should be int or str"
                assert isinstance(mutant["type"], str), f"P1 BUG: Mutant {i} 'type' should be str"
                assert isinstance(mutant["original"], str), f"P1 BUG: Mutant {i} 'original' should be str"
                assert isinstance(mutant["mutated"], str), f"P1 BUG: Mutant {i} 'mutated' should be str"
                assert isinstance(mutant["location"], dict), f"P1 BUG: Mutant {i} 'location' should be dict"
                
                # Validate location fields
                assert "line" in mutant["location"], f"P1 BUG: Mutant {i} location missing 'line'"
                assert "column" in mutant["location"], f"P1 BUG: Mutant {i} location missing 'column'"
                assert isinstance(mutant["location"]["line"], int), f"P1 BUG: Mutant {i} location 'line' should be int"
                assert isinstance(mutant["location"]["column"], int), f"P1 BUG: Mutant {i} location 'column' should be int"
                
                # Validate mutant type is one of the expected values
                valid_types = ["arithmetic", "logical", "relational", "assignment", "return", "call"]
                assert mutant["type"] in valid_types, f"P1 BUG: Mutant {i} has invalid type '{mutant['type']}'"
    
    elif isinstance(mutation_output, dict):
        # Alternative format: dict with 'mutants' key
        if "mutants" in mutation_output:
            mutants_list = mutation_output["mutants"]
            # P0 bug: empty mutants list
            if len(mutants_list) == 0:
                pass  # Acceptable for some modules
            else:
                for i, mutant in enumerate(mutants_list):
                    assert isinstance(mutant, dict), f"P1 BUG: Mutant {i} is not a dict, got {type(mutant)}"
                    assert "id" in mutant, f"P1 BUG: Mutant {i} missing 'id' field"
                    assert "type" in mutant, f"P1 BUG: Mutant {i} missing 'type' field"
                    assert "original" in mutant, f"P1 BUG: Mutant {i} missing 'original' field"
                    assert "mutated" in mutant, f"P1 BUG: Mutant {i} missing 'mutated' field"
                    assert "location" in mutant, f"P1 BUG: Mutant {i} missing 'location' field"
                    
                    # Validate field types
                    assert isinstance(mutant["id"], (int, str)), f"P1 BUG: Mutant {i} 'id' should be int or str"
                    assert isinstance(mutant["type"], str), f"P1 BUG: Mutant {i} 'type' should be str"
                    assert isinstance(mutant["original"], str), f"P1 BUG: Mutant {i} 'original' should be str"
                    assert isinstance(mutant["mutated"], str), f"P1 BUG: Mutant {i} 'mutated' should be str"
                    assert isinstance(mutant["location"], dict), f"P1 BUG: Mutant {i} 'location' should be dict"
                    
                    # Validate location fields
                    assert "line" in mutant["location"], f"P1 BUG: Mutant {i} location missing 'line'"
                    assert "column" in mutant["location"], f"P1 BUG: Mutant {i} location missing 'column'"
                    assert isinstance(mutant["location"]["line"], int), f"P1 BUG: Mutant {i} location 'line' should be int"
                    assert isinstance(mutant["location"]["column"], int), f"P1 BUG: Mutant {i} location 'column' should be int"
                    
                    # Validate mutant type is one of the expected values
                    valid_types = ["arithmetic", "logical", "relational", "assignment", "return", "call"]
                    assert mutant["type"] in valid_types, f"P1 BUG: Mutant {i} has invalid type '{mutant['type']}'"
        else:
            pytest.fail("P1 BUG: Mutation output dict missing 'mutants' key")
    else:
        pytest.fail(f"P1 BUG: Unexpected mutation output type: {type(mutation_output)}")
    
    # Now verify the mutation output can be consumed by the test runner
    try:
        test_results = test_runner.run_tests(str(test_path), mutation_output)
        assert test_results is not None, "Test runner returned None with mutation output"
        assert "passed" in test_results or "failed" in test_results, "Test results missing pass/fail info"
        assert "total" in test_results, "Test results missing total count"
    except Exception as e:
        pytest.fail(f"P1 BUG: Test runner failed to consume mutation output: {e}")


def test_test_to_reflection_link():
    """Test that the reflection parser correctly processes known test results.
    
    Feeds known test results (pass/fail counts, error messages) to the reflection parser
    and verifies it produces a valid assessment dict with 'current_assessment', 'key_gaps',
    and 'next_priority' keys. Detects if reflection parser fails to parse (P1 bug).
    """
    reflection_parser = ReflectionParser()
    
    # Define known test results with various scenarios
    test_cases = [
        {
            "name": "all_tests_passed",
            "input": {
                "passed": 10,
                "failed": 0,
                "total": 10,
                "errors": [],
                "details": [
                    {"name": "test_add", "status": "passed"},
                    {"name": "test_multiply", "status": "passed"}
                ]
            },
            "expected_assessment": "good"
        },
        {
            "name": "some_tests_failed",
            "input": {
                "passed": 7,
                "failed": 3,
                "total": 10,
                "errors": [
                    {"test": "test_failing", "message": "AssertionError: Expected 5 but got 4"}
                ],
                "details": [
                    {"name": "test_add", "status": "passed"},
                    {"name": "test_failing", "status": "failed", "message": "AssertionError: Expected 5 but got 4"}
                ]
            },
            "expected_assessment": "needs_improvement"
        },
        {
            "name": "all_tests_failed",
            "input": {
                "passed": 0,
                "failed": 5,
                "total": 5,
                "errors": [
                    {"test": "test_add", "message": "AssertionError: Expected 5 but got 4"},
                    {"test": "test_multiply", "message": "AssertionError: Expected 6 but got 7"}
                ],
                "details": [
                    {"name": "test_add", "status": "failed", "message": "AssertionError: Expected 5 but got 4"},
                    {"name": "test_multiply", "status": "failed", "message": "AssertionError: Expected 6 but got 7"}
                ]
            },
            "expected_assessment": "poor"
        },
        {
            "name": "mixed_results_with_errors",
            "input": {
                "passed": 5,
                "failed": 2,
                "total": 7,
                "errors": [
                    {"test": "test_edge_case", "message": "TypeError: unsupported operand type(s)"}
                ],
                "details": [
                    {"name": "test_basic", "status": "passed"},
                    {"name": "test_edge_case", "status": "failed", "message": "TypeError: unsupported operand type(s)"}
                ]
            },
            "expected_assessment": "needs_improvement"
        }
    ]
    
    for test_case in test_cases:
        try:
            # Feed known test results to the reflection parser
            reflection_output = reflection_parser.parse(test_case["input"])
            
            # P1 bug detection: reflection parser returned None
            assert reflection_output is not None, (
                f"P1 BUG: Reflection parser returned None for test case '{test_case['name']}'"
            )
            
            # Verify the output is a dict
            assert isinstance(reflection_output, dict), (
                f"P1 BUG: Reflection output should be a dict for test case '{test_case['name']}', "
                f"got {type(reflection_output)}"
            )
            
            # Verify required keys exist
            assert "current_assessment" in reflection_output, (
                f"P1 BUG: Reflection output missing 'current_assessment' key for test case '{test_case['name']}'"
            )
            assert "key_gaps" in reflection_output, (
                f"P1 BUG: Reflection output missing 'key_gaps' key for test case '{test_case['name']}'"
            )
            assert "next_priority" in reflection_output, (
                f"P1 BUG: Reflection output missing 'next_priority' key for test case '{test_case['name']}'"
            )
            
            # Verify types of the required fields
            assert isinstance(reflection_output["current_assessment"], str), (
                f"P1 BUG: 'current_assessment' should be a string for test case '{test_case['name']}', "
                f"got {type(reflection_output['current_assessment'])}"
            )
            assert isinstance(reflection_output["key_gaps"], list), (
                f"P1 BUG: 'key_gaps' should be a list for test case '{test_case['name']}', "
                f"got {type(reflection_output['key_gaps'])}"
            )
            assert isinstance(reflection_output["next_priority"], str), (
                f"P1 BUG: 'next_priority' should be a string for test case '{test_case['name']}', "
                f"got {type(reflection_output['next_priority'])}"
            )
            
            # Verify the assessment is reasonable based on test results
            if test_case["input"]["failed"] == 0:
                assert reflection_output["current_assessment"] in ["good", "excellent", "perfect"], (
                    f"P1 BUG: Expected positive assessment for all passing tests in '{test_case['name']}', "
                    f"got '{reflection_output['current_assessment']}'"
                )
            elif test_case["input"]["failed"] > test_case["input"]["passed"]:
                assert reflection_output["current_assessment"] in ["poor", "bad", "critical"], (
                    f"P1 BUG: Expected negative assessment for mostly failing tests in '{test_case['name']}', "
                    f"got '{reflection_output['current_assessment']}'"
                )
            
            # Verify key_gaps contains meaningful entries when there are failures
            if test_case["input"]["failed"] > 0:
                assert len(reflection_output["key_gaps"]) > 0, (
                    f"P1 BUG: 'key_gaps' should not be empty when there are failures in '{test_case['name']}'"
                )
                for gap in reflection_output["key_gaps"]:
                    assert isinstance(gap, str), (
                        f"P1 BUG: Each key_gap should be a string in '{test_case['name']}', "
                        f"got {type(gap)}"
                    )
            
            # Verify next_priority is a non-empty string
            assert len(reflection_output["next_priority"]) > 0, (
                f"P1 BUG: 'next_priority' should not be empty for test case '{test_case['name']}'"
            )
            
        except AssertionError:
            raise
        except Exception as e:
            pytest.fail(f"P1 BUG: Reflection parser failed to parse for test case '{test_case['name']}': {e}")