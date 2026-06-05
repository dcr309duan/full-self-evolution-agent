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