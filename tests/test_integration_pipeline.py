import pytest
from unittest.mock import Mock, patch, PropertyMock
from typing import Dict, Any, Optional
import json
import time
from datetime import datetime

# Import the actual components (adjust imports as needed)
from src.mutation_engine import MutationEngine
from src.test_framework import TestFramework
from src.reflection_parser import ReflectionParser
from src.strategy_selector import StrategySelector
from src.pipeline import Pipeline


class TestIntegrationPipeline:
    """Comprehensive integration test suite for the full pipeline flow."""

    @pytest.fixture
    def mock_components(self):
        """Set up mock components for testing."""
        mutation_engine = Mock(spec=MutationEngine)
        test_framework = Mock(spec=TestFramework)
        reflection_parser = Mock(spec=ReflectionParser)
        strategy_selector = Mock(spec=StrategySelector)
        
        return {
            'mutation_engine': mutation_engine,
            'test_framework': test_framework,
            'reflection_parser': reflection_parser,
            'strategy_selector': strategy_selector
        }

    @pytest.fixture
    def pipeline(self, mock_components):
        """Create a pipeline instance with mock components."""
        pipeline = Pipeline(
            mutation_engine=mock_components['mutation_engine'],
            test_framework=mock_components['test_framework'],
            reflection_parser=mock_components['reflection_parser'],
            strategy_selector=mock_components['strategy_selector']
        )
        return pipeline

    def test_full_pipeline_flow(self, mock_components, pipeline):
        """Test the complete pipeline flow from mutation to strategy update."""
        # Arrange
        source_code = "def add(a, b): return a + b"
        mutation_result = {
            'mutant_id': 'mutant_001',
            'mutated_code': "def add(a, b): return a - b",
            'mutation_type': 'arithmetic_operator'
        }
        test_result = {
            'mutant_id': 'mutant_001',
            'tests_passed': 2,
            'tests_failed': 1,
            'test_duration': 0.5,
            'test_output': 'Test results: 2 passed, 1 failed'
        }
        reflection_result = {
            'mutant_id': 'mutant_001',
            'assessment': 'high_impact',
            'weakness_identified': 'arithmetic_operator',
            'confidence': 0.85,
            'suggestions': ['Consider boundary testing']
        }
        strategy_update = {
            'strategy': 'adaptive',
            'focus_areas': ['arithmetic_operators'],
            'priority': 'high'
        }

        # Configure mock returns
        mock_components['mutation_engine'].generate_mutation.return_value = mutation_result
        mock_components['test_framework'].run_tests.return_value = test_result
        mock_components['reflection_parser'].parse_assessment.return_value = reflection_result
        mock_components['strategy_selector'].update_strategy.return_value = strategy_update

        # Act
        result = pipeline.run(source_code)

        # Assert
        # Verify mutation engine was called with correct input
        mock_components['mutation_engine'].generate_mutation.assert_called_once_with(source_code)
        
        # Verify test framework received mutation output
        mock_components['test_framework'].run_tests.assert_called_once_with(
            mutation_result['mutated_code'],
            mutation_result['mutation_type']
        )
        
        # Verify reflection parser received test output
        mock_components['reflection_parser'].parse_assessment.assert_called_once_with(
            test_result['test_output'],
            mutation_result['mutation_type']
        )
        
        # Verify strategy selector received reflection output
        mock_components['strategy_selector'].update_strategy.assert_called_once_with(
            reflection_result['assessment'],
            reflection_result['weakness_identified'],
            reflection_result['confidence']
        )
        
        # Verify final result
        assert result == strategy_update

    def test_data_flow_format_consistency(self, mock_components, pipeline):
        """Validate that output of one component matches input format of the next."""
        # Arrange
        source_code = "class Calculator: pass"
        
        # Create realistic data that matches expected formats
        mutation_result = {
            'mutant_id': 'mutant_002',
            'mutated_code': "class Calculator: pass  # modified",
            'mutation_type': 'class_modification',
            'original_line': 1,
            'modified_line': 1
        }
        
        test_result = {
            'mutant_id': 'mutant_002',
            'tests_passed': 5,
            'tests_failed': 0,
            'test_duration': 1.2,
            'test_output': 'All tests passed',
            'coverage': 0.95
        }
        
        reflection_result = {
            'mutant_id': 'mutant_002',
            'assessment': 'low_impact',
            'weakness_identified': 'class_modification',
            'confidence': 0.75,
            'suggestions': ['No issues found'],
            'timestamp': time.time()
        }
        
        strategy_update = {
            'strategy': 'conservative',
            'focus_areas': ['class_modifications'],
            'priority': 'medium',
            'timestamp': time.time()
        }

        # Configure mocks
        mock_components['mutation_engine'].generate_mutation.return_value = mutation_result
        mock_components['test_framework'].run_tests.return_value = test_result
        mock_components['reflection_parser'].parse_assessment.return_value = reflection_result
        mock_components['strategy_selector'].update_strategy.return_value = strategy_update

        # Act
        result = pipeline.run(source_code)

        # Assert data format consistency
        # Mutation engine output should contain required fields
        assert 'mutant_id' in mutation_result
        assert 'mutated_code' in mutation_result
        assert 'mutation_type' in mutation_result
        
        # Test framework should receive mutated code and mutation type
        call_args = mock_components['test_framework'].run_tests.call_args
        assert len(call_args[0]) == 2
        assert call_args[0][0] == mutation_result['mutated_code']
        assert call_args[0][1] == mutation_result['mutation_type']
        
        # Reflection parser should receive test output and mutation type
        call_args = mock_components['reflection_parser'].parse_assessment.call_args
        assert len(call_args[0]) == 2
        assert call_args[0][0] == test_result['test_output']
        assert call_args[0][1] == mutation_result['mutation_type']
        
        # Strategy selector should receive assessment, weakness, and confidence
        call_args = mock_components['strategy_selector'].update_strategy.call_args
        assert len(call_args[0]) == 3
        assert call_args[0][0] == reflection_result['assessment']
        assert call_args[0][1] == reflection_result['weakness_identified']
        assert call_args[0][2] == reflection_result['confidence']
        
        # Verify final result format
        assert 'strategy' in result
        assert 'focus_areas' in result
        assert 'priority' in result

    def test_mutation_engine_failure_propagation(self, mock_components, pipeline):
        """Test error propagation when mutation engine fails."""
        # Arrange
        source_code = "def test(): pass"
        mock_components['mutation_engine'].generate_mutation.side_effect = ValueError("Invalid source code")
        
        # Act & Assert
        with pytest.raises(ValueError, match="Invalid source code"):
            pipeline.run(source_code)
        
        # Verify no other components were called
        mock_components['test_framework'].run_tests.assert_not_called()
        mock_components['reflection_parser'].parse_assessment.assert_not_called()
        mock_components['strategy_selector'].update_strategy.assert_not_called()

    def test_reflection_parser_timeout(self, mock_components, pipeline):
        """Test error propagation when reflection parser times out."""
        # Arrange
        source_code = "def add(a, b): return a + b"
        mutation_result = {
            'mutant_id': 'mutant_003',
            'mutated_code': "def add(a, b): return a * b",
            'mutation_type': 'arithmetic_operator'
        }
        test_result = {
            'mutant_id': 'mutant_003',
            'tests_passed': 1,
            'tests_failed': 1,
            'test_duration': 0.3,
            'test_output': 'Test results: 1 passed, 1 failed'
        }
        
        mock_components['mutation_engine'].generate_mutation.return_value = mutation_result
        mock_components['test_framework'].run_tests.return_value = test_result
        mock_components['reflection_parser'].parse_assessment.side_effect = TimeoutError("Reflection parser timed out")
        
        # Act & Assert
        with pytest.raises(TimeoutError, match="Reflection parser timed out"):
            pipeline.run(source_code)
        
        # Verify mutation engine and test framework were called, but strategy selector was not
        mock_components['mutation_engine'].generate_mutation.assert_called_once()
        mock_components['test_framework'].run_tests.assert_called_once()
        mock_components['strategy_selector'].update_strategy.assert_not_called()

    def test_strategy_selector_crash(self, mock_components, pipeline):
        """Test error propagation when strategy selector crashes."""
        # Arrange
        source_code = "def multiply(a, b): return a * b"
        mutation_result = {
            'mutant_id': 'mutant_004',
            'mutated_code': "def multiply(a, b): return a / b",
            'mutation_type': 'arithmetic_operator'
        }
        test_result = {
            'mutant_id': 'mutant_004',
            'tests_passed': 3,
            'tests_failed': 0,
            'test_duration': 0.8,
            'test_output': 'All tests passed'
        }
        reflection_result = {
            'mutant_id': 'mutant_004',
            'assessment': 'low_impact',
            'weakness_identified': 'arithmetic_operator',
            'confidence': 0.9,
            'suggestions': ['No issues']
        }
        
        mock_components['mutation_engine'].generate_mutation.return_value = mutation_result
        mock_components['test_framework'].run_tests.return_value = test_result
        mock_components['reflection_parser'].parse_assessment.return_value = reflection_result
        mock_components['strategy_selector'].update_strategy.side_effect = RuntimeError("Strategy selector crashed")
        
        # Act & Assert
        with pytest.raises(RuntimeError, match="Strategy selector crashed"):
            pipeline.run(source_code)
        
        # Verify all previous components were called
        mock_components['mutation_engine'].generate_mutation.assert_called_once()
        mock_components['test_framework'].run_tests.assert_called_once()
        mock_components['reflection_parser'].parse_assessment.assert_called_once()

    def test_pipeline_with_empty_source_code(self, mock_components, pipeline):
        """Test pipeline behavior with empty source code."""
        # Arrange
        source_code = ""
        mock_components['mutation_engine'].generate_mutation.side_effect = ValueError("Empty source code")
        
        # Act & Assert
        with pytest.raises(ValueError, match="Empty source code"):
            pipeline.run(source_code)
        
        # Verify no other components were called
        mock_components['test_framework'].run_tests.assert_not_called()
        mock_components['reflection_parser'].parse_assessment.assert_not_called()
        mock_components['strategy_selector'].update_strategy.assert_not_called()

    def test_pipeline_with_none_source_code(self, mock_components, pipeline):
        """Test pipeline behavior with None source code."""
        # Arrange
        source_code = None
        mock_components['mutation_engine'].generate_mutation.side_effect = TypeError("Source code cannot be None")
        
        # Act & Assert
        with pytest.raises(TypeError, match="Source code cannot be None"):
            pipeline.run(source_code)
        
        # Verify no other components were called
        mock_components['test_framework'].run_tests.assert_not_called()
        mock_components['reflection_parser'].parse_assessment.assert_not_called()
        mock_components['strategy_selector'].update_strategy.assert_not_called()

    def test_multiple_pipeline_runs(self, mock_components, pipeline):
        """Test that pipeline can be run multiple times with different inputs."""
        # Arrange
        source_codes = [
            "def add(a, b): return a + b",
            "def subtract(a, b): return a - b",
            "def multiply(a, b): return a * b"
        ]
        
        mutation_results = [
            {'mutant_id': f'mutant_00{i}', 'mutated_code': f'code_{i}', 'mutation_type': 'op'}
            for i in range(1, 4)
        ]
        
        test_results = [
            {'mutant_id': f'mutant_00{i}', 'tests_passed': 2, 'tests_failed': 0, 
             'test_duration': 0.5, 'test_output': f'output_{i}'}
            for i in range(1, 4)
        ]
        
        reflection_results = [
            {'mutant_id': f'mutant_00{i}', 'assessment': 'low', 'weakness_identified': 'op',
             'confidence': 0.8, 'suggestions': []}
            for i in range(1, 4)
        ]
        
        strategy_updates = [
            {'strategy': 'adaptive', 'focus_areas': ['op'], 'priority': 'low'}
            for _ in range(3)
        ]
        
        # Configure side effects
        mock_components['mutation_engine'].generate_mutation.side_effect = mutation_results
        mock_components['test_framework'].run_tests.side_effect = test_results
        mock_components['reflection_parser'].parse_assessment.side_effect = reflection_results
        mock_components['strategy_selector'].update_strategy.side_effect = strategy_updates
        
        # Act
        results = [pipeline.run(code) for code in source_codes]
        
        # Assert
        assert len(results) == 3
        for i, result in enumerate(results):
            assert result == strategy_updates[i]
            assert result['strategy'] == 'adaptive'
        
        # Verify each component was called three times
        assert mock_components['mutation_engine'].generate_mutation.call_count == 3
        assert mock_components['test_framework'].run_tests.call_count == 3
        assert mock_components['reflection_parser'].parse_assessment.call_count == 3
        assert mock_components['strategy_selector'].update_strategy.call_count == 3

    def test_orchestrator_sequences_components_correctly(self, mock_components, pipeline):
        """Test that orchestrator correctly sequences mutation -> test -> reflection -> strategy update."""
        # Arrange
        source_code = "def add(a, b): return a + b"
        mutation_result = {
            'mutant_id': 'mutant_001',
            'mutated_code': "def add(a, b): return a - b",
            'mutation_type': 'arithmetic_operator'
        }
        test_result = {
            'mutant_id': 'mutant_001',
            'tests_passed': 2,
            'tests_failed': 1,
            'test_duration': 0.5,
            'test_output': 'Test results: 2 passed, 1 failed'
        }
        reflection_result = {
            'mutant_id': 'mutant_001',
            'assessment': 'high_impact',
            'weakness_identified': 'arithmetic_operator',
            'confidence': 0.85,
            'suggestions': ['Consider boundary testing']
        }
        strategy_update = {
            'strategy': 'adaptive',
            'focus_areas': ['arithmetic_operators'],
            'priority': 'high'
        }

        # Configure mock returns
        mock_components['mutation_engine'].generate_mutation.return_value = mutation_result
        mock_components['test_framework'].run_tests.return_value = test_result
        mock_components['reflection_parser'].parse_assessment.return_value = reflection_result
        mock_components['strategy_selector'].update_strategy.return_value = strategy_update

        # Track call order
        call_order = []
        original_generate_mutation = mock_components['mutation_engine'].generate_mutation
        original_run_tests = mock_components['test_framework'].run_tests
        original_parse_assessment = mock_components['reflection_parser'].parse_assessment
        original_update_strategy = mock_components['strategy_selector'].update_strategy

        def track_mutation(*args, **kwargs):
            call_order.append('mutation')
            return original_generate_mutation(*args, **kwargs)

        def track_tests(*args, **kwargs):
            call_order.append('test')
            return original_run_tests(*args, **kwargs)

        def track_reflection(*args, **kwargs):
            call_order.append('reflection')
            return original_parse_assessment(*args, **kwargs)

        def track_strategy(*args, **kwargs):
            call_order.append('strategy')
            return original_update_strategy(*args, **kwargs)

        mock_components['mutation_engine'].generate_mutation.side_effect = track_mutation
        mock_components['test_framework'].run_tests.side_effect = track_tests
        mock_components['reflection_parser'].parse_assessment.side_effect = track_reflection
        mock_components['strategy_selector'].update_strategy.side_effect = track_strategy

        # Act
        pipeline.run(source_code)

        # Assert correct sequencing
        assert call_order == ['mutation', 'test', 'reflection', 'strategy'], \
            f"Expected order: mutation -> test -> reflection -> strategy, got: {call_order}"

    def test_orchestrator_timeout_handling(self, mock_components, pipeline):
        """Test timeout handling: if a component takes too long, orchestrator should abort and report."""
        # Arrange
        source_code = "def add(a, b): return a + b"
        mutation_result = {
            'mutant_id': 'mutant_001',
            'mutated_code': "def add(a, b): return a - b",
            'mutation_type': 'arithmetic_operator'
        }
        test_result = {
            'mutant_id': 'mutant_001',
            'tests_passed': 2,
            'tests_failed': 1,
            'test_duration': 0.5,
            'test_output': 'Test results: 2 passed, 1 failed'
        }

        mock_components['mutation_engine'].generate_mutation.return_value = mutation_result
        mock_components['test_framework'].run_tests.return_value = test_result
        
        # Simulate timeout in reflection parser
        mock_components['reflection_parser'].parse_assessment.side_effect = TimeoutError("Component timed out after 30 seconds")

        # Act & Assert
        with pytest.raises(TimeoutError, match="Component timed out after 30 seconds"):
            pipeline.run(source_code)
        
        # Verify that strategy selector was not called (pipeline aborted)
        mock_components['strategy_selector'].update_strategy.assert_not_called()
        
        # Verify that mutation and test were called before timeout
        mock_components['mutation_engine'].generate_mutation.assert_called_once()
        mock_components['test_framework'].run_tests.assert_called_once()

    def test_orchestrator_retry_logic(self, mock_components, pipeline):
        """Test retry logic: if a component fails transiently, orchestrator retries up to configured limit."""
        # Arrange
        source_code = "def add(a, b): return a + b"
        mutation_result = {
            'mutant_id': 'mutant_001',
            'mutated_code': "def add(a, b): return a - b",
            'mutation_type': 'arithmetic_operator'
        }
        test_result = {
            'mutant_id': 'mutant_001',
            'tests_passed': 2,
            'tests_failed': 1,
            'test_duration': 0.5,
            'test_output': 'Test results: 2 passed, 1 failed'
        }
        reflection_result = {
            'mutant_id': 'mutant_001',
            'assessment': 'high_impact',
            'weakness_identified': 'arithmetic_operator',
            'confidence': 0.85,
            'suggestions': ['Consider boundary testing']
        }
        strategy_update = {
            'strategy': 'adaptive',
            'focus_areas': ['arithmetic_operators'],
            'priority': 'high'
        }

        # Configure mock returns with transient failure for test framework
        mock_components['mutation_engine'].generate_mutation.return_value = mutation_result
        
        # Test framework fails twice then succeeds
        mock_components['test_framework'].run_tests.side_effect = [
            ConnectionError("Temporary network issue"),
            ConnectionError("Temporary network issue"),
            test_result
        ]
        
        mock_components['reflection_parser'].parse_assessment.return_value = reflection_result
        mock_components['strategy_selector'].update_strategy.return_value = strategy_update

        # Act
        result = pipeline.run(source_code)

        # Assert
        # Verify test framework was called 3 times (2 failures + 1 success)
        assert mock_components['test_framework'].run_tests.call_count == 3
        
        # Verify other components were called correctly
        mock_components['mutation_engine'].generate_mutation.assert_called_once()
        mock_components['reflection_parser'].parse_assessment.assert_called_once()
        mock_components['strategy_selector'].update_strategy.assert_called_once()
        
        # Verify final result
        assert result == strategy_update

    def test_orchestrator_retry_exhaustion(self, mock_components, pipeline):
        """Test that orchestrator stops retrying after configured limit and raises error."""
        # Arrange
        source_code = "def add(a, b): return a + b"
        mutation_result = {
            'mutant_id': 'mutant_001',
            'mutated_code': "def add(a, b): return a - b",
            'mutation_type': 'arithmetic_operator'
        }

        mock_components['mutation_engine'].generate_mutation.return_value = mutation_result
        
        # Test framework fails consistently (more than retry limit)
        mock_components['test_framework'].run_tests.side_effect = ConnectionError("Persistent network failure")

        # Act & Assert
        with pytest.raises(ConnectionError, match="Persistent network failure"):
            pipeline.run(source_code)
        
        # Verify test framework was called multiple times (retries exhausted)
        assert mock_components['test_framework'].run_tests.call_count >= 3
        
        # Verify subsequent components were not called
        mock_components['reflection_parser'].parse_assessment.assert_not_called()
        mock_components['strategy_selector'].update_strategy.assert_not_called()

    def test_orchestrator_logs_pipeline_stages(self, mock_components, pipeline):
        """Test that orchestrator logs all pipeline stages with timestamps for debugging."""
        # Arrange
        source_code = "def add(a, b): return a + b"
        mutation_result = {
            'mutant_id': 'mutant_001',
            'mutated_code': "def add(a, b): return a - b",
            'mutation_type': 'arithmetic_operator'
        }
        test_result = {
            'mutant_id': 'mutant_001',
            'tests_passed': 2,
            'tests_failed': 1,
            'test_duration': 0.5,
            'test_output': 'Test results: 2 passed, 1 failed'
        }
        reflection_result = {
            'mutant_id': 'mutant_001',
            'assessment': 'high_impact',
            'weakness_identified': 'arithmetic_operator',
            'confidence': 0.85,
            'suggestions': ['Consider boundary testing']
        }
        strategy_update = {
            'strategy': 'adaptive',
            'focus_areas': ['arithmetic_operators'],
            'priority': 'high'
        }

        # Configure mock returns
        mock_components['mutation_engine'].generate_mutation.return_value = mutation_result
        mock_components['test_framework'].run_tests.return_value = test_result
        mock_components['reflection_parser'].parse_assessment.return_value = reflection_result
        mock_components['strategy_selector'].update_strategy.return_value = strategy_update

        # Mock the logger
        with patch('src.pipeline.logger') as mock_logger:
            # Act
            pipeline.run(source_code)

            # Assert
            # Verify that log messages were generated for each stage
            log_calls = mock_logger.info.call_args_list
            
            # Check that we have log entries for each pipeline stage
            log_messages = [call[0][0] for call in log_calls]
            
            # Verify stage-specific log messages exist
            stage_messages = [
                "Starting mutation engine",
                "Mutation engine completed",
                "Starting test framework",
                "Test framework completed",
                "Starting reflection parser",
                "Reflection parser completed",
                "Starting strategy selector",
                "Strategy selector completed"
            ]
            
            for stage_msg in stage_messages:
                assert any(stage_msg in msg for msg in log_messages), \
                    f"Expected log message '{stage_msg}' not found in: {log_messages}"
            
            # Verify timestamps are present in log messages
            for log_call in log_calls:
                # Check that log records have timestamp information
                # This assumes the logger is configured to include timestamps
                assert hasattr(log_call[0], 'created') or 'timestamp' in str(log_call[0]).lower(), \
                    f"Log message missing timestamp: {log_call[0]}"

    def test_orchestrator_logs_with_timestamps(self, mock_components, pipeline):
        """Test that orchestrator logs include proper timestamp formatting."""
        # Arrange
        source_code = "def add(a, b): return a + b"
        mutation_result = {
            'mutant_id': 'mutant_001',
            'mutated_code': "def add(a, b): return a - b",
            'mutation_type': 'arithmetic_operator'
        }
        test_result = {
            'mutant_id': 'mutant_001',
            'tests_passed': 2,
            'tests_failed': 1,
            'test_duration': 0.5,
            'test_output': 'Test results: 2 passed, 1 failed'
        }
        reflection_result = {
            'mutant_id': 'mutant_001',
            'assessment': 'high_impact',
            'weakness_identified': 'arithmetic_operator',
            'confidence': 0.85,
            'suggestions': ['Consider boundary testing']
        }
        strategy_update = {
            'strategy': 'adaptive',
            'focus_areas': ['arithmetic_operators'],
            'priority': 'high'
        }

        # Configure mock returns
        mock_components['mutation_engine'].generate_mutation.return_value = mutation_result
        mock_components['test_framework'].run_tests.return_value = test_result
        mock_components['reflection_parser'].parse_assessment.return_value = reflection_result
        mock_components['strategy_selector'].update_strategy.return_value = strategy_update

        # Mock the logger with a custom handler to capture log records
        log_records = []
        
        class LogCaptureHandler:
            def emit(self, record):
                log_records.append(record)

        with patch('src.pipeline.logger') as mock_logger:
            mock_logger.handlers = [LogCaptureHandler()]
            
            # Act
            pipeline.run(source_code)

            # Assert
            # Verify that log records have timestamp information
            for record in log_records:
                assert hasattr(record, 'created'), "Log record missing 'created' timestamp"
                assert isinstance(record.created, float), "Timestamp should be a float"
                # Verify timestamp is reasonable (within last minute)
                assert time.time() - record.created < 60, "Timestamp is too old"