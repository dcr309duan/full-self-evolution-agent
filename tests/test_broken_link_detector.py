import pytest
from unittest.mock import Mock, patch
from src.broken_link_detector import BrokenLinkDetector, LinkPriority, PipelineLink

class TestBrokenLinkDetector:
    """Test suite for BrokenLinkDetector class."""

    @pytest.fixture
    def detector(self):
        """Create a BrokenLinkDetector instance for testing."""
        return BrokenLinkDetector()

    @pytest.fixture
    def sample_failures(self):
        """Provide sample integration test failures."""
        return [
            {
                "test_name": "test_mutation_to_test_integration",
                "error": "ConnectionError: Failed to connect to mutation service",
                "source": "mutation",
                "target": "test"
            },
            {
                "test_name": "test_test_to_reflection_integration",
                "error": "TimeoutError: Reflection service not responding",
                "source": "test",
                "target": "reflection"
            },
            {
                "test_name": "test_reflection_to_strategy_integration",
                "error": "ValueError: Invalid strategy response format",
                "source": "reflection",
                "target": "strategy"
            }
        ]

    def test_classify_mutation_to_test_link_as_p0(self, detector, sample_failures):
        """Test that mutation->test failures are classified as P0 priority."""
        failure = sample_failures[0]
        result = detector.classify_link(failure)
        
        assert result.priority == LinkPriority.P0
        assert result.source == "mutation"
        assert result.target == "test"
        assert result.is_broken == True

    def test_classify_test_to_reflection_link_as_p1(self, detector, sample_failures):
        """Test that test->reflection failures are classified as P1 priority."""
        failure = sample_failures[1]
        result = detector.classify_link(failure)
        
        assert result.priority == LinkPriority.P1
        assert result.source == "test"
        assert result.target == "reflection"
        assert result.is_broken == True

    def test_classify_reflection_to_strategy_link_as_p2(self, detector, sample_failures):
        """Test that reflection->strategy failures are classified as P2 priority."""
        failure = sample_failures[2]
        result = detector.classify_link(failure)
        
        assert result.priority == LinkPriority.P2
        assert result.source == "reflection"
        assert result.target == "strategy"
        assert result.is_broken == True

    def test_detect_no_broken_links_with_clean_tests(self, detector):
        """Test that no broken links are detected when all tests pass."""
        clean_results = [
            {"test_name": "test_successful_integration", "passed": True}
        ]
        
        broken_links = detector.detect_broken_links(clean_results)
        assert len(broken_links) == 0

    def test_detect_multiple_broken_links(self, detector, sample_failures):
        """Test detection of multiple broken links from various failures."""
        broken_links = detector.detect_broken_links(sample_failures)
        
        assert len(broken_links) == 3
        priorities = [link.priority for link in broken_links]
        assert LinkPriority.P0 in priorities
        assert LinkPriority.P1 in priorities
        assert LinkPriority.P2 in priorities

    def test_priority_ordering(self, detector):
        """Test that broken links are ordered by priority (P0 first, P2 last)."""
        failures = [
            {"source": "reflection", "target": "strategy", "error": "Error"},
            {"source": "mutation", "target": "test", "error": "Error"},
            {"source": "test", "target": "reflection", "error": "Error"}
        ]
        
        broken_links = detector.detect_broken_links(failures)
        
        assert broken_links[0].priority == LinkPriority.P0
        assert broken_links[1].priority == LinkPriority.P1
        assert broken_links[2].priority == LinkPriority.P2

    def test_unknown_link_classification(self, detector):
        """Test that unknown link types are classified with default priority."""
        unknown_failure = {
            "source": "unknown",
            "target": "unknown",
            "error": "Unknown error"
        }
        
        result = detector.classify_link(unknown_failure)
        assert result.priority == LinkPriority.UNKNOWN
        assert result.is_broken == True

    def test_detector_handles_empty_failure_list(self, detector):
        """Test that detector handles empty failure list gracefully."""
        broken_links = detector.detect_broken_links([])
        assert broken_links == []

    def test_detector_handles_missing_source_or_target(self, detector):
        """Test that detector handles failures with missing source or target."""
        incomplete_failure = {
            "error": "Some error without source/target"
        }
        
        result = detector.classify_link(incomplete_failure)
        assert result.is_broken == True
        assert result.priority == LinkPriority.UNKNOWN

    @patch('src.broken_link_detector.BrokenLinkDetector._get_pipeline_status')
    def test_integration_with_pipeline_status(self, mock_status, detector):
        """Test integration with pipeline status checking."""
        mock_status.return_value = {"status": "failed", "stage": "mutation"}
        
        failure = {
            "test_name": "test_mutation_to_test_integration",
            "error": "Connection failed",
            "source": "mutation",
            "target": "test"
        }
        
        result = detector.classify_link(failure)
        assert result.priority == LinkPriority.P0
        mock_status.assert_called_once()

    def test_link_priority_enum_values(self):
        """Test that LinkPriority enum has correct values."""
        assert LinkPriority.P0.value == 0
        assert LinkPriority.P1.value == 1
        assert LinkPriority.P2.value == 2
        assert LinkPriority.UNKNOWN.value == -1

    def test_pipeline_link_dataclass(self):
        """Test PipelineLink dataclass creation and attributes."""
        link = PipelineLink(
            source="mutation",
            target="test",
            priority=LinkPriority.P0,
            is_broken=True,
            error_message="Connection failed"
        )
        
        assert link.source == "mutation"
        assert link.target == "test"
        assert link.priority == LinkPriority.P0
        assert link.is_broken == True
        assert link.error_message == "Connection failed"

    @patch('src.broken_link_detector.BrokenLinkDetector._get_mutation_results')
    def test_detect_mutation_engine_not_returning_results(self, mock_mutation_results, detector):
        """Test that mutation engine returning empty list is reported as P0 bug with actionable description."""
        mock_mutation_results.return_value = []
        
        failure = {
            "test_name": "test_mutation_to_test_integration",
            "error": "Mutation engine returned no results",
            "source": "mutation",
            "target": "test"
        }
        
        result = detector.classify_link(failure)
        assert result.priority == LinkPriority.P0
        assert result.is_broken == True
        assert "Mutation engine returned no results" in result.error_message
        assert "actionable" in result.error_message.lower() or "investigate" in result.error_message.lower()