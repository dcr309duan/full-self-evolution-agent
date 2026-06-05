import pytest
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, List, Any
from datetime import datetime

# Import the module to test
from src.goal_generator import GoalGenerator, Goal, PriorityScore
from src.orchestrator import Orchestrator
from src.knowledge_base import KnowledgeBase

# Mock data for knowledge base
MOCK_KNOWLEDGE_BASE = {
    "failure_patterns": [
        {
            "pattern": "database_connection_timeout",
            "frequency": 15,
            "severity": 0.8,
            "last_occurrence": "2024-01-15T10:30:00",
            "affected_services": ["user-service", "order-service"],
            "root_cause": "connection_pool_exhaustion"
        },
        {
            "pattern": "memory_leak_in_cache",
            "frequency": 8,
            "severity": 0.6,
            "last_occurrence": "2024-01-14T08:15:00",
            "affected_services": ["cache-service"],
            "root_cause": "improper_cache_eviction"
        },
        {
            "pattern": "api_rate_limiting",
            "frequency": 3,
            "severity": 0.4,
            "last_occurrence": "2024-01-13T14:00:00",
            "affected_services": ["api-gateway"],
            "root_cause": "missing_throttling_config"
        }
    ],
    "successes": [
        {
            "pattern": "successful_connection_pool_management",
            "frequency": 45,
            "impact": 0.9,
            "last_occurrence": "2024-01-15T12:00:00",
            "services": ["user-service", "order-service"]
        },
        {
            "pattern": "efficient_cache_usage",
            "frequency": 30,
            "impact": 0.7,
            "last_occurrence": "2024-01-14T16:30:00",
            "services": ["cache-service"]
        }
    ],
    "gaps": [
        {
            "gap_id": "gap_001",
            "description": "No monitoring for connection pool exhaustion",
            "severity": 0.8,
            "affected_services": ["user-service", "order-service"]
        },
        {
            "gap_id": "gap_002",
            "description": "Insufficient cache eviction policies",
            "severity": 0.6,
            "affected_services": ["cache-service"]
        }
    ]
}

class TestGoalGenerator:
    """Test suite for the GoalGenerator class."""

    @pytest.fixture
    def mock_knowledge_base(self):
        """Create a mock knowledge base with predefined data."""
        kb = Mock(spec=KnowledgeBase)
        kb.get_failure_patterns.return_value = MOCK_KNOWLEDGE_BASE["failure_patterns"]
        kb.get_successes.return_value = MOCK_KNOWLEDGE_BASE["successes"]
        kb.get_gaps.return_value = MOCK_KNOWLEDGE_BASE["gaps"]
        return kb

    @pytest.fixture
    def mock_orchestrator(self):
        """Create a mock orchestrator."""
        orchestrator = Mock(spec=Orchestrator)
        orchestrator.process_goal.return_value = {"status": "success", "goal_id": "goal_001"}
        return orchestrator

    @pytest.fixture
    def goal_generator(self, mock_knowledge_base):
        """Create a GoalGenerator instance with mock knowledge base."""
        return GoalGenerator(knowledge_base=mock_knowledge_base)

    def test_initialization_with_knowledge_base(self, mock_knowledge_base):
        """Test that GoalGenerator initializes correctly with a knowledge base."""
        generator = GoalGenerator(knowledge_base=mock_knowledge_base)
        assert generator.knowledge_base == mock_knowledge_base
        assert hasattr(generator, 'priority_scorer')

    def test_generate_goals_from_failure_patterns(self, goal_generator):
        """Test that goals are generated from identified failure patterns."""
        goals = goal_generator.generate_goals()
        
        # Should generate goals for high-severity failure patterns
        assert len(goals) > 0
        goal_descriptions = [g.description for g in goals]
        
        # Check that the most severe failure pattern generates a goal
        assert any("database_connection_timeout" in desc for desc in goal_descriptions)
        assert any("connection_pool_exhaustion" in desc for desc in goal_descriptions)

    def test_generate_goals_address_gaps(self, goal_generator):
        """Test that generated goals address identified gaps."""
        goals = goal_generator.generate_goals()
        
        # Verify goals address the gaps
        gap_descriptions = [g["description"] for g in MOCK_KNOWLEDGE_BASE["gaps"]]
        goal_descriptions = [g.description for g in goals]
        
        # Check that goals address the gaps
        for gap_desc in gap_descriptions:
            assert any(gap_desc.lower() in desc.lower() for desc in goal_descriptions)

    def test_priority_scoring_logic(self, goal_generator):
        """Test the priority scoring logic for goals."""
        # Test scoring for a high-priority goal
        high_priority_goal = Goal(
            description="Fix connection pool exhaustion",
            affected_services=["user-service", "order-service"],
            severity=0.8,
            frequency=15
        )
        
        # Test scoring for a low-priority goal
        low_priority_goal = Goal(
            description="Optimize API rate limiting",
            affected_services=["api-gateway"],
            severity=0.4,
            frequency=3
        )
        
        high_score = goal_generator.priority_scorer.calculate(high_priority_goal)
        low_score = goal_generator.priority_scorer.calculate(low_priority_goal)
        
        assert high_score > low_score, "High priority goal should have higher score"
        assert isinstance(high_score, float)
        assert 0 <= high_score <= 1.0
        assert 0 <= low_score <= 1.0

    def test_priority_score_components(self, goal_generator):
        """Test individual components of priority scoring."""
        goal = Goal(
            description="Test goal",
            affected_services=["test-service"],
            severity=0.5,
            frequency=10
        )
        
        score = goal_generator.priority_scorer.calculate(goal)
        components = goal_generator.priority_scorer.get_components(goal)
        
        assert "severity_score" in components
        assert "frequency_score" in components
        assert "impact_score" in components
        assert components["severity_score"] == 0.5
        assert components["frequency_score"] > 0

    def test_goal_generation_with_empty_knowledge_base(self):
        """Test goal generation with empty knowledge base."""
        empty_kb = Mock(spec=KnowledgeBase)
        empty_kb.get_failure_patterns.return_value = []
        empty_kb.get_successes.return_value = []
        empty_kb.get_gaps.return_value = []
        
        generator = GoalGenerator(knowledge_base=empty_kb)
        goals = generator.generate_goals()
        
        assert len(goals) == 0

    def test_integration_with_orchestrator(self, goal_generator, mock_orchestrator):
        """Test integration with the orchestrator."""
        goals = goal_generator.generate_goals()
        
        # Simulate orchestrator processing
        for goal in goals:
            result = mock_orchestrator.process_goal(goal)
            assert result["status"] == "success"
            assert "goal_id" in result
        
        # Verify orchestrator was called for each goal
        assert mock_orchestrator.process_goal.call_count == len(goals)

    def test_goal_prioritization(self, goal_generator):
        """Test that goals are properly prioritized."""
        goals = goal_generator.generate_goals()
        prioritized_goals = goal_generator.prioritize_goals(goals)
        
        # Check that goals are sorted by priority (highest first)
        for i in range(len(prioritized_goals) - 1):
            current_score = goal_generator.priority_scorer.calculate(prioritized_goals[i])
            next_score = goal_generator.priority_scorer.calculate(prioritized_goals[i + 1])
            assert current_score >= next_score

    def test_goal_generation_with_success_patterns(self, goal_generator):
        """Test that success patterns influence goal generation."""
        goals = goal_generator.generate_goals()
        
        # Success patterns should not generate goals, but may influence existing ones
        success_patterns = [s["pattern"] for s in MOCK_KNOWLEDGE_BASE["successes"]]
        goal_descriptions = [g.description for g in goals]
        
        # Success patterns themselves should not appear as goals
        for success_pattern in success_patterns:
            assert success_pattern not in goal_descriptions

    def test_goal_metadata(self, goal_generator):
        """Test that generated goals contain proper metadata."""
        goals = goal_generator.generate_goals()
        
        for goal in goals:
            assert hasattr(goal, 'id')
            assert hasattr(goal, 'description')
            assert hasattr(goal, 'affected_services')
            assert hasattr(goal, 'severity')
            assert hasattr(goal, 'frequency')
            assert hasattr(goal, 'created_at')
            assert isinstance(goal.created_at, datetime)

    def test_goal_generation_with_multiple_failure_patterns(self, goal_generator):
        """Test generation with multiple failure patterns."""
        goals = goal_generator.generate_goals()
        
        # Should generate goals for patterns above severity threshold
        high_severity_patterns = [p for p in MOCK_KNOWLEDGE_BASE["failure_patterns"] 
                                 if p["severity"] >= 0.5]
        
        assert len(goals) >= len(high_severity_patterns)

    def test_priority_scorer_initialization(self, goal_generator):
        """Test that priority scorer initializes with correct parameters."""
        scorer = goal_generator.priority_scorer
        
        assert hasattr(scorer, 'severity_weight')
        assert hasattr(scorer, 'frequency_weight')
        assert hasattr(scorer, 'impact_weight')
        assert scorer.severity_weight + scorer.frequency_weight + scorer.impact_weight == 1.0

    def test_goal_generation_error_handling(self, mock_knowledge_base):
        """Test error handling during goal generation."""
        mock_knowledge_base.get_failure_patterns.side_effect = Exception("Database error")
        
        generator = GoalGenerator(knowledge_base=mock_knowledge_base)
        
        with pytest.raises(Exception) as exc_info:
            generator.generate_goals()
        
        assert "Database error" in str(exc_info.value)

    def test_goal_generation_with_custom_thresholds(self):
        """Test goal generation with custom severity thresholds."""
        kb = Mock(spec=KnowledgeBase)
        kb.get_failure_patterns.return_value = MOCK_KNOWLEDGE_BASE["failure_patterns"]
        kb.get_successes.return_value = MOCK_KNOWLEDGE_BASE["successes"]
        kb.get_gaps.return_value = MOCK_KNOWLEDGE_BASE["gaps"]
        
        # Create generator with custom threshold
        generator = GoalGenerator(knowledge_base=kb, severity_threshold=0.7)
        goals = generator.generate_goals()
        
        # Only patterns with severity >= 0.7 should generate goals
        high_severity_patterns = [p for p in MOCK_KNOWLEDGE_BASE["failure_patterns"] 
                                 if p["severity"] >= 0.7]
        
        assert len(goals) == len(high_severity_patterns)