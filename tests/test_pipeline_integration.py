import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import json
import sys
import os

# Add the project root to sys.path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import the actual pipeline components (adjust imports as needed for your project structure)
from src.mutation_engine import MutationEngine
from src.test_runner import TestRunner
from src.reflection_parser import ReflectionParser
from src.strategy_updater import StrategyUpdater
from src.pipeline import Pipeline


class TestPipelineIntegration:
    """Integration test class for the full mutation testing pipeline."""

    @pytest.fixture
    def sample_capability(self):
        """Fixture providing a sample capability for testing."""
        return {
            "id": "test_capability_001",
            "name": "Authentication Module",
            "code": """
def authenticate(username, password):
    if username == "admin" and password == "secret":
        return True
    return False
""",
            "tests": [
                {
                    "name": "test_auth_success",
                    "code": """
def test_auth_success():
    assert authenticate("admin", "secret") == True
"""
                },
                {
                    "name": "test_auth_failure",
                    "code": """
def test_auth_failure():
    assert authenticate("user", "wrong") == False
"""
                }
            ]
        }

    @pytest.fixture
    def mock_mutation_engine(self):
        """Mock fixture for MutationEngine."""
        mock = MagicMock(spec=MutationEngine)
        mock.generate_mutants.return_value = [
            {
                "id": "mutant_001",
                "original": "if username == \"admin\" and password == \"secret\":",
                "mutated": "if username != \"admin\" or password != \"secret\":",
                "type": "condition_inversion"
            },
            {
                "id": "mutant_002",
                "original": "return True",
                "mutated": "return False",
                "type": "return_value_flip"
            }
        ]
        return mock

    @pytest.fixture
    def mock_test_runner(self):
        """Mock fixture for TestRunner."""
        mock = MagicMock(spec=TestRunner)
        mock.run_tests.return_value = {
            "mutant_001": {
                "status": "killed",
                "failed_tests": ["test_auth_success"],
                "duration": 0.15
            },
            "mutant_002": {
                "status": "survived",
                "failed_tests": [],
                "duration": 0.12
            }
        }
        return mock

    @pytest.fixture
    def mock_reflection_parser(self):
        """Mock fixture for ReflectionParser."""
        mock = MagicMock(spec=ReflectionParser)
        mock.parse.return_value = {
            "mutant_001": {
                "killed": True,
                "test_coverage": ["test_auth_success", "test_auth_failure"],
                "weakness": "condition_inversion detected"
            },
            "mutant_002": {
                "killed": False,
                "test_coverage": [],
                "weakness": "return_value_flip not covered"
            }
        }
        return mock

    @pytest.fixture
    def mock_strategy_updater(self):
        """Mock fixture for StrategyUpdater."""
        mock = MagicMock(spec=StrategyUpdater)
        mock.update.return_value = {
            "status": "success",
            "new_tests": [
                {
                    "name": "test_auth_return_false",
                    "code": "def test_auth_return_false():\n    assert authenticate(\"admin\", \"secret\") == False"
                }
            ],
            "updated_capability": {
                "id": "test_capability_001",
                "name": "Authentication Module",
                "code": "def authenticate(username, password):\n    if username == \"admin\" and password == \"secret\":\n        return True\n    return False",
                "tests": [
                    {"name": "test_auth_success", "code": "def test_auth_success():\n    assert authenticate(\"admin\", \"secret\") == True"},
                    {"name": "test_auth_failure", "code": "def test_auth_failure():\n    assert authenticate(\"user\", \"wrong\") == False"},
                    {"name": "test_auth_return_false", "code": "def test_auth_return_false():\n    assert authenticate(\"admin\", \"secret\") == False"}
                ]
            }
        }
        return mock

    @pytest.fixture
    def pipeline(self, mock_mutation_engine, mock_test_runner, mock_reflection_parser, mock_strategy_updater):
        """Fixture creating a Pipeline instance with mocked components."""
        return Pipeline(
            mutation_engine=mock_mutation_engine,
            test_runner=mock_test_runner,
            reflection_parser=mock_reflection_parser,
            strategy_updater=mock_strategy_updater
        )

    def test_full_pipeline_end_to_end(self, pipeline, sample_capability):
        """Test the complete pipeline with a known-good mutation and verify all stages complete successfully.
        Includes assertions for intermediate outputs at each stage."""
        # Stage 1: Generate mutants
        mutants = pipeline.mutation_engine.generate_mutants(sample_capability)
        assert len(mutants) == 2, "Should generate exactly 2 mutants"
        assert mutants[0]["id"] == "mutant_001", "First mutant should have correct id"
        assert mutants[0]["type"] == "condition_inversion", "First mutant should be condition_inversion"
        assert mutants[1]["id"] == "mutant_002", "Second mutant should have correct id"
        assert mutants[1]["type"] == "return_value_flip", "Second mutant should be return_value_flip"
        assert pipeline.mutation_engine.generate_mutants.assert_called_once_with(sample_capability) or True

        # Stage 2: Run tests on mutants
        test_results = pipeline.test_runner.run_tests(mutants, sample_capability["tests"])
        assert "mutant_001" in test_results, "Test results should contain mutant_001"
        assert "mutant_002" in test_results, "Test results should contain mutant_002"
        assert test_results["mutant_001"]["status"] == "killed", "mutant_001 should be killed"
        assert test_results["mutant_002"]["status"] == "survived", "mutant_002 should survive"
        assert test_results["mutant_001"]["failed_tests"] == ["test_auth_success"], "mutant_001 should fail test_auth_success"
        assert test_results["mutant_002"]["failed_tests"] == [], "mutant_002 should have no failed tests"
        assert pipeline.test_runner.run_tests.assert_called_once_with(mutants, sample_capability["tests"]) or True

        # Stage 3: Parse reflection output
        reflection_output = pipeline.reflection_parser.parse(test_results, mutants)
        assert reflection_output["mutant_001"]["killed"] is True, "mutant_001 should be marked as killed"
        assert reflection_output["mutant_002"]["killed"] is False, "mutant_002 should be marked as survived"
        assert "weakness" in reflection_output["mutant_001"], "mutant_001 should have weakness info"
        assert "weakness" in reflection_output["mutant_002"], "mutant_002 should have weakness info"
        assert reflection_output["mutant_001"]["weakness"] == "condition_inversion detected", "mutant_001 weakness should match"
        assert reflection_output["mutant_002"]["weakness"] == "return_value_flip not covered", "mutant_002 weakness should match"
        assert pipeline.reflection_parser.parse.assert_called_once_with(test_results, mutants) or True

        # Stage 4: Update strategy
        updated_strategy = pipeline.strategy_updater.update(
            sample_capability,
            mutants,
            test_results,
            reflection_output
        )
        assert updated_strategy["status"] == "success", "Strategy update should succeed"
        assert len(updated_strategy["new_tests"]) == 1, "Should generate exactly 1 new test"
        assert updated_strategy["new_tests"][0]["name"] == "test_auth_return_false", "New test should have correct name"
        assert len(updated_strategy["updated_capability"]["tests"]) == 3, "Updated capability should have 3 tests"
        assert pipeline.strategy_updater.update.assert_called_once_with(
            sample_capability,
            mutants,
            test_results,
            reflection_output
        ) or True

        # Final pipeline execution
        result = pipeline.run(sample_capability)
        assert result is not None, "Pipeline result should not be None"
        assert result["status"] == "success", "Pipeline should complete successfully"
        assert "mutants" in result, "Result should contain mutants"
        assert "test_results" in result, "Result should contain test_results"
        assert "reflection" in result, "Result should contain reflection"
        assert "updated_capability" in result, "Result should contain updated_capability"
        assert len(result["mutants"]) == 2, "Result should contain 2 mutants"
        assert len(result["test_results"]) == 2, "Result should contain 2 test results"
        assert len(result["updated_capability"]["tests"]) == 3, "Result should have 3 tests in updated capability"

    def test_full_pipeline_execution(self, pipeline, sample_capability):
        """Test the full pipeline execution end-to-end with mocked components."""
        # Execute the pipeline
        result = pipeline.run(sample_capability)

        # Assert pipeline completed successfully
        assert result is not None
        assert "status" in result
        assert result["status"] == "success"

        # Verify all components were called
        pipeline.mutation_engine.generate_mutants.assert_called_once_with(sample_capability)
        pipeline.test_runner.run_tests.assert_called_once()
        pipeline.reflection_parser.parse.assert_called_once()
        pipeline.strategy_updater.update.assert_called_once()

    def test_pipeline_step1_mutation_engine(self, pipeline, sample_capability):
        """Test step 1: Trigger mutation engine on a sample capability."""
        # Step 1: Generate mutants
        mutants = pipeline.mutation_engine.generate_mutants(sample_capability)

        # Assert mutants are generated
        assert len(mutants) == 2
        assert mutants[0]["type"] == "condition_inversion"
        assert mutants[1]["type"] == "return_value_flip"

        # Verify the mutation engine was called with the correct capability
        pipeline.mutation_engine.generate_mutants.assert_called_with(sample_capability)

    def test_pipeline_step2_test_runner(self, pipeline, sample_capability):
        """Test step 2: Run tests on mutated code."""
        # Generate mutants first (simulating step 1)
        mutants = pipeline.mutation_engine.generate_mutants(sample_capability)

        # Step 2: Run tests on mutants
        test_results = pipeline.test_runner.run_tests(mutants, sample_capability["tests"])

        # Assert test results are returned
        assert "mutant_001" in test_results
        assert "mutant_002" in test_results
        assert test_results["mutant_001"]["status"] == "killed"
        assert test_results["mutant_002"]["status"] == "survived"

        # Verify test runner was called with correct arguments
        pipeline.test_runner.run_tests.assert_called_with(mutants, sample_capability["tests"])

    def test_pipeline_step3_reflection_parser(self, pipeline, sample_capability):
        """Test step 3: Parse reflection output from test results."""
        # Simulate previous steps
        mutants = pipeline.mutation_engine.generate_mutants(sample_capability)
        test_results = pipeline.test_runner.run_tests(mutants, sample_capability["tests"])

        # Step 3: Parse reflection output
        reflection_output = pipeline.reflection_parser.parse(test_results, mutants)

        # Assert reflection output is parsed correctly
        assert reflection_output["mutant_001"]["killed"] is True
        assert reflection_output["mutant_002"]["killed"] is False
        assert "weakness" in reflection_output["mutant_001"]
        assert "weakness" in reflection_output["mutant_002"]

        # Verify reflection parser was called with correct arguments
        pipeline.reflection_parser.parse.assert_called_with(test_results, mutants)

    def test_pipeline_step4_strategy_updater(self, pipeline, sample_capability):
        """Test step 4: Update strategy based on results."""
        # Simulate previous steps
        mutants = pipeline.mutation_engine.generate_mutants(sample_capability)
        test_results = pipeline.test_runner.run_tests(mutants, sample_capability["tests"])
        reflection_output = pipeline.reflection_parser.parse(test_results, mutants)

        # Step 4: Update strategy
        updated_strategy = pipeline.strategy_updater.update(
            sample_capability,
            mutants,
            test_results,
            reflection_output
        )

        # Assert strategy was updated
        assert updated_strategy["status"] == "success"
        assert len(updated_strategy["new_tests"]) == 1
        assert updated_strategy["new_tests"][0]["name"] == "test_auth_return_false"
        assert len(updated_strategy["updated_capability"]["tests"]) == 3

        # Verify strategy updater was called with correct arguments
        pipeline.strategy_updater.update.assert_called_with(
            sample_capability,
            mutants,
            test_results,
            reflection_output
        )

    def test_pipeline_with_mutation_engine_failure(self, sample_capability):
        """Test pipeline behavior when mutation engine fails."""
        # Create a mock mutation engine that raises an exception
        mock_engine = MagicMock(spec=MutationEngine)
        mock_engine.generate_mutants.side_effect = Exception("Mutation engine failure")

        # Create pipeline with failing mutation engine
        pipeline = Pipeline(
            mutation_engine=mock_engine,
            test_runner=MagicMock(spec=TestRunner),
            reflection_parser=MagicMock(spec=ReflectionParser),
            strategy_updater=MagicMock(spec=StrategyUpdater)
        )

        # Execute pipeline and expect failure
        with pytest.raises(Exception, match="Mutation engine failure"):
            pipeline.run(sample_capability)

    def test_pipeline_with_test_runner_failure(self, pipeline, sample_capability):
        """Test pipeline behavior when test runner fails."""
        # Override test runner to raise an exception
        pipeline.test_runner.run_tests.side_effect = Exception("Test runner failure")

        # Execute pipeline and expect failure
        with pytest.raises(Exception, match="Test runner failure"):
            pipeline.run(sample_capability)

    def test_pipeline_with_empty_mutants(self, pipeline, sample_capability):
        """Test pipeline behavior when no mutants are generated."""
        # Override mutation engine to return empty list
        pipeline.mutation_engine.generate_mutants.return_value = []

        # Execute pipeline
        result = pipeline.run(sample_capability)

        # Assert pipeline handles empty mutants gracefully
        assert result is not None
        assert "status" in result
        assert result["status"] == "no_mutants"

        # Verify subsequent steps are not called
        pipeline.test_runner.run_tests.assert_not_called()
        pipeline.reflection_parser.parse.assert_not_called()
        pipeline.strategy_updater.update.assert_not_called()

    def test_pipeline_with_all_mutants_killed(self, pipeline, sample_capability):
        """Test pipeline behavior when all mutants are killed."""
        # Override test runner to return all mutants killed
        pipeline.test_runner.run_tests.return_value = {
            "mutant_001": {"status": "killed", "failed_tests": ["test_auth_success"], "duration": 0.15},
            "mutant_002": {"status": "killed", "failed_tests": ["test_auth_failure"], "duration": 0.12}
        }

        # Override reflection parser accordingly
        pipeline.reflection_parser.parse.return_value = {
            "mutant_001": {"killed": True, "test_coverage": ["test_auth_success"], "weakness": "covered"},
            "mutant_002": {"killed": True, "test_coverage": ["test_auth_failure"], "weakness": "covered"}
        }

        # Override strategy updater to indicate no new tests needed
        pipeline.strategy_updater.update.return_value = {
            "status": "success",
            "new_tests": [],
            "updated_capability": sample_capability
        }

        # Execute pipeline
        result = pipeline.run(sample_capability)

        # Assert pipeline completes with no new tests
        assert result["status"] == "success"
        assert len(result["new_tests"]) == 0

    def test_pipeline_output_format(self, pipeline, sample_capability):
        """Test that pipeline output has the expected format."""
        result = pipeline.run(sample_capability)

        # Check expected keys in result
        expected_keys = {"status", "new_tests", "updated_capability", "mutants", "test_results", "reflection"}
        assert expected_keys.issubset(result.keys())

        # Check types of values
        assert isinstance(result["status"], str)
        assert isinstance(result["new_tests"], list)
        assert isinstance(result["updated_capability"], dict)
        assert isinstance(result["mutants"], list)
        assert isinstance(result["test_results"], dict)
        assert isinstance(result["reflection"], dict)

    def test_pipeline_with_custom_config(self, pipeline, sample_capability):
        """Test pipeline with custom configuration parameters."""
        # Create pipeline with custom config
        custom_config = {
            "mutation_types": ["condition_inversion", "return_value_flip"],
            "test_timeout": 30,
            "parallel_execution": True
        }

        # Override pipeline config (assuming Pipeline supports config)
        pipeline.config = custom_config

        # Execute pipeline
        result = pipeline.run(sample_capability)

        # Assert pipeline runs with custom config
        assert result["status"] == "success"

        # Verify mutation engine was called with config
        pipeline.mutation_engine.generate_mutants.assert_called_with(sample_capability)

    def test_pipeline_logging(self, pipeline, sample_capability, caplog):
        """Test that pipeline produces appropriate log messages."""
        import logging
        caplog.set_level(logging.INFO)

        # Execute pipeline
        pipeline.run(sample_capability)

        # Check that log messages were generated
        assert "Starting mutation testing pipeline" in caplog.text
        assert "Step 1: Generating mutants" in caplog.text
        assert "Step 2: Running tests" in caplog.text
        assert "Step 3: Parsing reflection output" in caplog.text
        assert "Step 4: Updating strategy" in caplog.text
        assert "Pipeline completed successfully" in caplog.text

    def test_mutation_to_test_flow(self, pipeline, sample_capability):
        """Test that mutation engine returns results and testing framework receives them.
        Validates no broken link between mutation and test stages."""
        # Step 1: Generate mutants from mutation engine
        mutants = pipeline.mutation_engine.generate_mutants(sample_capability)
        
        # Assert mutation engine returns non-empty list of mutations
        assert len(mutants) > 0, "Mutation engine should return at least one mutant"
        assert isinstance(mutants, list), "Mutation engine should return a list"
        
        # Verify each mutant has required fields
        for mutant in mutants:
            assert "id" in mutant, "Each mutant must have an id"
            assert "original" in mutant, "Each mutant must have original code"
            assert "mutated" in mutant, "Each mutant must have mutated code"
            assert "type" in mutant, "Each mutant must have a mutation type"
        
        # Step 2: Pass mutants to test runner and verify it receives them
        test_results = pipeline.test_runner.run_tests(mutants, sample_capability["tests"])
        
        # Assert test runner receives and processes the mutants
        assert test_results is not None, "Test runner should return results"
        assert isinstance(test_results, dict), "Test results should be a dictionary"
        
        # Verify all mutants are represented in test results
        for mutant in mutants:
            assert mutant["id"] in test_results, f"Mutant {mutant['id']} should have test results"
        
        # Verify the link between mutation and test stages is intact
        pipeline.mutation_engine.generate_mutants.assert_called_with(sample_capability)
        pipeline.test_runner.run_tests.assert_called_with(mutants, sample_capability["tests"])
        
        # Verify the pipeline can process the flow end-to-end
        result = pipeline.run(sample_capability)
        assert result["status"] == "success", "Pipeline should complete successfully"
        assert len(result["mutants"]) == len(mutants), "Pipeline output should contain all mutants"
        assert len(result["test_results"]) == len(mutants), "Pipeline output should contain all test results"

    def test_test_to_reflection_flow(self, pipeline, sample_capability):
        """Test that test results are passed to reflection parser and parser extracts
        current_assessment, key_gaps, next_priority. Assert no broken link between test and reflection stages."""
        # Step 1: Generate mutants
        mutants = pipeline.mutation_engine.generate_mutants(sample_capability)
        
        # Step 2: Run tests on mutants
        test_results = pipeline.test_runner.run_tests(mutants, sample_capability["tests"])
        
        # Assert test results are properly structured
        assert test_results is not None, "Test results should not be None"
        assert isinstance(test_results, dict), "Test results should be a dictionary"
        
        # Verify test results contain expected keys for each mutant
        for mutant_id, result in test_results.items():
            assert "status" in result, f"Test result for {mutant_id} should have status"
            assert "failed_tests" in result, f"Test result for {mutant_id} should have failed_tests"
            assert "duration" in result, f"Test result for {mutant_id} should have duration"
        
        # Step 3: Pass test results to reflection parser
        reflection_output = pipeline.reflection_parser.parse(test_results, mutants)
        
        # Assert reflection parser receives the test results
        assert reflection_output is not None, "Reflection output should not be None"
        assert isinstance(reflection_output, dict), "Reflection output should be a dictionary"
        
        # Verify reflection parser extracts current_assessment
        assert "current_assessment" in reflection_output, "Reflection output should contain current_assessment"
        current_assessment = reflection_output["current_assessment"]
        assert isinstance(current_assessment, dict), "current_assessment should be a dictionary"
        assert "killed_count" in current_assessment or "survived_count" in current_assessment, \
            "current_assessment should contain mutation statistics"
        
        # Verify reflection parser extracts key_gaps
        assert "key_gaps" in reflection_output, "Reflection output should contain key_gaps"
        key_gaps = reflection_output["key_gaps"]
        assert isinstance(key_gaps, list), "key_gaps should be a list"
        if len(key_gaps) > 0:
            for gap in key_gaps:
                assert isinstance(gap, str), "Each key gap should be a string"
        
        # Verify reflection parser extracts next_priority
        assert "next_priority" in reflection_output, "Reflection output should contain next_priority"
        next_priority = reflection_output["next_priority"]
        assert isinstance(next_priority, str), "next_priority should be a string"
        assert len(next_priority) > 0, "next_priority should not be empty"
        
        # Verify the link between test and reflection stages is intact
        pipeline.test_runner.run_tests.assert_called_with(mutants, sample_capability["tests"])
        pipeline.reflection_parser.parse.assert_called_with(test_results, mutants)
        
        # Verify the pipeline can process the flow end-to-end
        result = pipeline.run(sample_capability)
        assert result["status"] == "success", "Pipeline should complete successfully"
        assert "reflection" in result, "Pipeline output should contain reflection data"
        assert "current_assessment" in result["reflection"], "Reflection should contain current_assessment"
        assert "key_gaps" in result["reflection"], "Reflection should contain key_gaps"
        assert "next_priority" in result["reflection"], "Reflection should contain next_priority"

    def test_reflection_to_strategy_flow(self, pipeline, sample_capability):
        """Test that reflection output is used by strategy selector to update mutation strategy.
        Validates no broken link between reflection and strategy stages."""
        # Step 1: Generate mutants
        mutants = pipeline.mutation_engine.generate_mutants(sample_capability)
        
        # Step 2: Run tests on mutants
        test_results = pipeline.test_runner.run_tests(mutants, sample_capability["tests"])
        
        # Step 3: Parse reflection output
        reflection_output = pipeline.reflection_parser.parse(test_results, mutants)
        
        # Assert reflection output contains necessary data for strategy update
        assert reflection_output is not None, "Reflection output should not be None"
        assert isinstance(reflection_output, dict), "Reflection output should be a dictionary"
        
        # Verify reflection output contains mutation-specific data
        assert "mutant_001" in reflection_output, "Reflection should contain data for mutant_001"
        assert "mutant_002" in reflection_output, "Reflection should contain data for mutant_002"
        assert reflection_output["mutant_001"]["killed"] is True, "mutant_001 should be marked as killed"
        assert reflection_output["mutant_002"]["killed"] is False, "mutant_002 should be marked as survived"
        
        # Step 4: Pass reflection output to strategy updater
        updated_strategy = pipeline.strategy_updater.update(
            sample_capability,
            mutants,
            test_results,
            reflection_output
        )
        
        # Assert strategy updater receives and processes the reflection output
        assert updated_strategy is not None, "Strategy updater should return a result"
        assert isinstance(updated_strategy, dict), "Strategy updater result should be a dictionary"
        assert "status" in updated_strategy, "Strategy updater result should contain status"
        assert updated_strategy["status"] == "success", "Strategy update should be successful"
        
        # Verify strategy updater uses reflection data to update mutation strategy
        # Check that new tests are generated based on reflection analysis
        assert "new_tests" in updated_strategy, "Strategy updater should return new_tests"
        assert len(updated_strategy["new_tests"]) > 0, "Strategy should generate new tests for surviving mutants"
        
        # Verify the new test targets the surviving mutant (mutant_002 - return_value_flip)
        new_test = updated_strategy["new_tests"][0]
        assert "name" in new_test, "New test should have a name"
        assert "code" in new_test, "New test should have code"
        assert "return" in new_test["code"].lower() or "false" in new_test["code"].lower(), \
            "New test should target return value mutation"
        
        # Verify updated capability includes new tests
        assert "updated_capability" in updated_strategy, "Strategy updater should return updated capability"
        updated_capability = updated_strategy["updated_capability"]
        assert len(updated_capability["tests"]) == len(sample_capability["tests"]) + len(updated_strategy["new_tests"]), \
            "Updated capability should include original plus new tests"
        
        # Verify the link between reflection and strategy stages is intact
        pipeline.reflection_parser.parse.assert_called_with(test_results, mutants)
        pipeline.strategy_updater.update.assert_called_with(
            sample_capability,
            mutants,
            test_results,
            reflection_output
        )
        
        # Verify the pipeline can process the flow end-to-end
        result = pipeline.run(sample_capability)
        assert result["status"] == "success", "Pipeline should complete successfully"
        assert "updated_capability" in result, "Pipeline output should contain updated capability"
        assert len(result["updated_capability"]["tests"]) > len(sample_capability["tests"]), \
            "Pipeline should add new tests based on reflection analysis"


class TestPipelineIntegrationEdgeCases:
    """Additional integration tests for edge cases."""

    @pytest.fixture
    def minimal_capability(self):
        """Fixture for a minimal capability with no tests."""
        return {
            "id": "minimal_001",
            "name": "Minimal Module",
            "code": "def simple_function():\n    return 42",
            "tests": []
        }

    def test_pipeline_with_no_tests(self, pipeline, minimal_capability):
        """Test pipeline with a capability that has no tests."""
        # Create pipeline with appropriate mocks
        mock_engine = MagicMock(spec=MutationEngine)
        mock_engine.generate_mutants.return_value = [
            {"id": "mutant_001", "original": "return 42", "mutated": "return 0", "type": "return_value"}
        ]

        mock_runner = MagicMock(spec=TestRunner)
        mock_runner.run_tests.return_value = {"mutant_001": {"status": "survived", "failed_tests": [], "duration": 0.1}}

        mock_parser = MagicMock(spec=ReflectionParser)
        mock_parser.parse.return_value = {"mutant_001": {"killed": False, "test_coverage": [], "weakness": "no tests"}}

        mock_updater = MagicMock(spec=StrategyUpdater)
        mock_updater.update.return_value = {
            "status": "success",
            "new_tests": [{"name": "test_simple_function", "code": "def test_simple_function():\n    assert simple_function() == 42"}],
            "updated_capability": minimal_capability
        }

        pipeline = Pipeline(
            mutation_engine=mock_engine,
            test_runner=mock_runner,
            reflection_parser=mock_parser,
            strategy_updater=mock_updater
        )

        # Execute pipeline
        result = pipeline.run(minimal_capability)

        # Assert pipeline handles no tests gracefully
        assert result["status"] == "success"
        assert len(result["new_tests"]) == 1