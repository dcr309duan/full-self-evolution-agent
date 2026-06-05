import pytest
from unittest.mock import Mock, patch
from datetime import datetime
from typing import Dict, Any, Optional

# Import the modules under test
from src.pipeline.broken_link_detector import BrokenLinkDetector, FailureReport, FailurePriority
from src.pipeline.mutation_engine import MutationEngine
from src.pipeline.test_framework import TestFramework
from src.pipeline.reflection_parser import ReflectionParser
from src.pipeline.strategy_selector import StrategySelector
from src.pipeline.failure_analysis import FailureAnalyzer


class TestBrokenLinkDetector:
    """Test suite for broken link detection in the pipeline."""

    @pytest.fixture
    def mock_mutation_engine(self):
        """Create a mock mutation engine."""
        engine = Mock(spec=MutationEngine)
        engine.mutate.return_value = {"mutations": ["mutation1", "mutation2"]}
        return engine

    @pytest.fixture
    def mock_test_framework(self):
        """Create a mock test framework."""
        framework = Mock(spec=TestFramework)
        framework.run_tests.return_value = {"passed": 5, "failed": 0, "errors": []}
        return framework

    @pytest.fixture
    def mock_reflection_parser(self):
        """Create a mock reflection parser."""
        parser = Mock(spec=ReflectionParser)
        parser.parse.return_value = {"reflections": ["reflection1"]}
        return parser

    @pytest.fixture
    def mock_strategy_selector(self):
        """Create a mock strategy selector."""
        selector = Mock(spec=StrategySelector)
        selector.select.return_value = {"strategy": "default", "parameters": {}}
        return selector

    @pytest.fixture
    def mock_failure_analyzer(self):
        """Create a mock failure analyzer."""
        analyzer = Mock(spec=FailureAnalyzer)
        analyzer.analyze_failure.return_value = {"classified": True, "severity": "MEDIUM"}
        return analyzer

    @pytest.fixture
    def detector(self, mock_mutation_engine, mock_test_framework, 
                 mock_reflection_parser, mock_strategy_selector, 
                 mock_failure_analyzer):
        """Create a BrokenLinkDetector instance with mocked components."""
        return BrokenLinkDetector(
            mutation_engine=mock_mutation_engine,
            test_framework=mock_test_framework,
            reflection_parser=mock_reflection_parser,
            strategy_selector=mock_strategy_selector,
            failure_analyzer=mock_failure_analyzer
        )

    # ========== 1. Injection of Specific Failures ==========

    def test_mutation_engine_returns_none(self, detector, mock_mutation_engine):
        """Test when mutation engine returns None."""
        mock_mutation_engine.mutate.return_value = None
        
        results = detector.run_pipeline()
        
        assert len(results.failures) == 1
        failure = results.failures[0]
        assert failure.component == "mutation_engine"
        assert failure.nature == "returned_none"
        assert failure.priority == FailurePriority.CRITICAL

    def test_test_framework_returns_malformed_results(self, detector, mock_test_framework):
        """Test when test framework returns malformed results."""
        mock_test_framework.run_tests.return_value = {"invalid": "data", "missing": "fields"}
        
        results = detector.run_pipeline()
        
        assert len(results.failures) == 1
        failure = results.failures[0]
        assert failure.component == "test_framework"
        assert failure.nature == "malformed_results"
        assert "missing required fields" in failure.message.lower()

    def test_reflection_parser_throws_exception(self, detector, mock_reflection_parser):
        """Test when reflection parser throws an exception."""
        mock_reflection_parser.parse.side_effect = ValueError("Invalid reflection data")
        
        results = detector.run_pipeline()
        
        assert len(results.failures) == 1
        failure = results.failures[0]
        assert failure.component == "reflection_parser"
        assert failure.nature == "exception"
        assert "Invalid reflection data" in failure.message

    def test_strategy_selector_returns_invalid_strategy(self, detector, mock_strategy_selector):
        """Test when strategy selector returns invalid strategy."""
        mock_strategy_selector.select.return_value = {"strategy": None, "parameters": {}}
        
        results = detector.run_pipeline()
        
        assert len(results.failures) == 1
        failure = results.failures[0]
        assert failure.component == "strategy_selector"
        assert failure.nature == "invalid_strategy"

    # ========== 2. Verification of Component Identification ==========

    def test_identifies_mutation_engine_failure(self, detector, mock_mutation_engine):
        """Test that mutation engine failures are correctly identified."""
        mock_mutation_engine.mutate.return_value = None
        
        results = detector.run_pipeline()
        
        assert results.failures[0].component == "mutation_engine"
        assert results.failures[0].nature == "returned_none"
        assert results.failures[0].timestamp is not None

    def test_identifies_test_framework_failure(self, detector, mock_test_framework):
        """Test that test framework failures are correctly identified."""
        mock_test_framework.run_tests.return_value = {"passed": -1, "failed": -1}
        
        results = detector.run_pipeline()
        
        assert results.failures[0].component == "test_framework"
        assert "negative" in results.failures[0].nature.lower()

    def test_identifies_reflection_parser_failure(self, detector, mock_reflection_parser):
        """Test that reflection parser failures are correctly identified."""
        mock_reflection_parser.parse.side_effect = RuntimeError("Parser crashed")
        
        results = detector.run_pipeline()
        
        assert results.failures[0].component == "reflection_parser"
        assert results.failures[0].nature == "exception"

    def test_identifies_strategy_selector_failure(self, detector, mock_strategy_selector):
        """Test that strategy selector failures are correctly identified."""
        mock_strategy_selector.select.return_value = {}
        
        results = detector.run_pipeline()
        
        assert results.failures[0].component == "strategy_selector"
        assert "missing" in results.failures[0].nature.lower()

    # ========== 3. Priority Verification ==========

    def test_mutation_engine_failure_priority_critical(self, detector, mock_mutation_engine):
        """Test that mutation engine failures get CRITICAL priority."""
        mock_mutation_engine.mutate.return_value = None
        
        results = detector.run_pipeline()
        
        assert results.failures[0].priority == FailurePriority.CRITICAL

    def test_reflection_parser_failure_priority_high(self, detector, mock_reflection_parser):
        """Test that reflection parser failures get HIGH priority."""
        mock_reflection_parser.parse.side_effect = Exception("Parse error")
        
        results = detector.run_pipeline()
        
        assert results.failures[0].priority == FailurePriority.HIGH

    def test_strategy_selector_failure_priority_medium(self, detector, mock_strategy_selector):
        """Test that strategy selector failures get MEDIUM priority."""
        mock_strategy_selector.select.return_value = {"strategy": "invalid"}
        
        results = detector.run_pipeline()
        
        assert results.failures[0].priority == FailurePriority.MEDIUM

    def test_test_framework_failure_priority_high(self, detector, mock_test_framework):
        """Test that test framework failures get HIGH priority."""
        mock_test_framework.run_tests.return_value = {"passed": 0, "failed": 0, "errors": ["timeout"]}
        
        results = detector.run_pipeline()
        
        assert results.failures[0].priority == FailurePriority.HIGH

    # ========== 4. Failure Analysis Integration ==========

    def test_failure_analyzer_receives_failures(self, detector, mock_failure_analyzer, 
                                                 mock_mutation_engine):
        """Test that failure analyzer receives and classifies failures."""
        mock_mutation_engine.mutate.return_value = None
        
        results = detector.run_pipeline()
        
        # Verify failure analyzer was called with the failure
        mock_failure_analyzer.analyze_failure.assert_called_once()
        call_args = mock_failure_analyzer.analyze_failure.call_args[0][0]
        assert call_args.component == "mutation_engine"
        assert call_args.priority == FailurePriority.CRITICAL

    def test_failure_analyzer_classifies_multiple_failures(self, detector, mock_failure_analyzer,
                                                            mock_mutation_engine, mock_reflection_parser):
        """Test that failure analyzer handles multiple failures."""
        mock_mutation_engine.mutate.return_value = None
        mock_reflection_parser.parse.side_effect = Exception("Parse error")
        
        results = detector.run_pipeline()
        
        assert mock_failure_analyzer.analyze_failure.call_count == 2
        # Verify different priorities
        priorities = [call[0][0].priority for call in mock_failure_analyzer.analyze_failure.call_args_list]
        assert FailurePriority.CRITICAL in priorities
        assert FailurePriority.HIGH in priorities

    def test_failure_analyzer_receives_correct_nature(self, detector, mock_failure_analyzer,
                                                       mock_strategy_selector):
        """Test that failure analyzer receives correct failure nature."""
        mock_strategy_selector.select.return_value = {}
        
        results = detector.run_pipeline()
        
        call_args = mock_failure_analyzer.analyze_failure.call_args[0][0]
        assert "missing" in call_args.nature.lower()

    def test_failure_analyzer_returns_classification(self, detector, mock_failure_analyzer,
                                                      mock_mutation_engine):
        """Test that failure analyzer classification is used."""
        mock_mutation_engine.mutate.return_value = None
        mock_failure_analyzer.analyze_failure.return_value = {
            "classified": True,
            "severity": "CRITICAL",
            "action": "restart_mutation_engine"
        }
        
        results = detector.run_pipeline()
        
        assert results.actions[0] == "restart_mutation_engine"

    # ========== Edge Cases ==========

    def test_multiple_simultaneous_failures(self, detector, mock_mutation_engine,
                                             mock_test_framework, mock_reflection_parser,
                                             mock_strategy_selector):
        """Test handling of multiple simultaneous failures."""
        mock_mutation_engine.mutate.return_value = None
        mock_test_framework.run_tests.return_value = {"passed": -1}
        mock_reflection_parser.parse.side_effect = Exception("Error")
        mock_strategy_selector.select.return_value = {}
        
        results = detector.run_pipeline()
        
        assert len(results.failures) == 4
        priorities = [f.priority for f in results.failures]
        assert FailurePriority.CRITICAL in priorities
        assert FailurePriority.HIGH in priorities
        assert FailurePriority.MEDIUM in priorities

    def test_failure_with_timestamp(self, detector, mock_mutation_engine):
        """Test that failures include timestamps."""
        mock_mutation_engine.mutate.return_value = None
        
        results = detector.run_pipeline()
        
        assert results.failures[0].timestamp is not None
        assert isinstance(results.failures[0].timestamp, datetime)

    def test_clean_pipeline_no_failures(self, detector):
        """Test that clean pipeline produces no failures."""
        results = detector.run_pipeline()
        
        assert len(results.failures) == 0
        assert len(results.actions) == 0

    def test_failure_priority_ordering(self, detector, mock_mutation_engine,
                                        mock_reflection_parser, mock_strategy_selector):
        """Test that failures are ordered by priority."""
        mock_mutation_engine.mutate.return_value = None  # CRITICAL
        mock_reflection_parser.parse.side_effect = Exception("Error")  # HIGH
        mock_strategy_selector.select.return_value = {}  # MEDIUM
        
        results = detector.run_pipeline()
        
        # Verify ordering: CRITICAL first, then HIGH, then MEDIUM
        assert results.failures[0].priority == FailurePriority.CRITICAL
        assert results.failures[1].priority == FailurePriority.HIGH
        assert results.failures[2].priority == FailurePriority.MEDIUM