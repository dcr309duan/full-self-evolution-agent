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

# Mock data for complete core patterns (no gaps)
MOCK_COMPLETE_KNOWLEDGE_BASE = {
    "failure_patterns": [
        {
            "pattern": "database_connection_timeout",
            "frequency": 15,
            "severity": 0.8,
            "last_occurrence": "2024-01-15T10:30:00",
            "affected_services": ["user-service", "order-service"],
            "root_cause": "connection_pool_exhaustion"
        }
    ],
    "successes": [
        {
            "pattern": "successful_connection_pool_management",
            "frequency": 45,
            "impact": 0.9,
            "last_occurrence": "2024-01-15T12:00:00",
            "services": ["user-service", "order-service"]
        }
    ],
    "gaps": []  # No gaps - all core patterns present
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
    def mock_complete_knowledge_base(self):
        """Create a mock knowledge base with all core patterns present."""
        kb = Mock(spec=KnowledgeBase)
        kb.get_failure_patterns.return_value = MOCK_COMPLETE_KNOWLEDGE_BASE["failure_patterns"]
        kb.get_successes.return_value = MOCK_COMPLETE_KNOWLEDGE_BASE["successes"]
        kb.get_gaps.return_value = MOCK_COMPLETE_KNOWLEDGE_BASE["gaps"]
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

    @pytest.fixture
    def goal_generator_complete(self, mock_complete_knowledge_base):
        """Create a GoalGenerator instance with complete knowledge base."""
        return GoalGenerator(knowledge_base=mock_complete_knowledge_base)

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

    # New test cases for autonomous goal generation

    def test_gap_analysis_identifies_missing_core_patterns(self, goal_generator):
        """Test that gap analysis correctly identifies missing core patterns."""
        # Perform gap analysis
        gaps = goal_generator.analyze_gaps()
        
        # Verify gaps are identified
        assert len(gaps) > 0
        assert any("connection_pool_exhaustion" in gap.description for gap in gaps)
        assert any("cache_eviction" in gap.description for gap in gaps)
        
        # Verify gap metadata
        for gap in gaps:
            assert hasattr(gap, 'gap_id')
            assert hasattr(gap, 'description')
            assert hasattr(gap, 'severity')
            assert hasattr(gap, 'affected_services')
            assert gap.severity > 0

    def test_priority_heuristic_assigns_higher_scores_to_core_modifications(self, goal_generator):
        """Test that priority heuristic assigns higher scores to core modifications."""
        # Create goals with different modification types
        core_modification_goal = Goal(
            description="Fix core database connection pool",
            affected_services=["user-service", "order-service"],
            severity=0.9,
            frequency=20,
            modification_type="core"
        )
        
        cosmetic_modification_goal = Goal(
            description="Update API documentation",
            affected_services=["api-gateway"],
            severity=0.3,
            frequency=2,
            modification_type="cosmetic"
        )
        
        # Calculate priority scores
        core_score = goal_generator.priority_scorer.calculate(core_modification_goal)
        cosmetic_score = goal_generator.priority_scorer.calculate(cosmetic_modification_goal)
        
        # Core modifications should have higher priority scores
        assert core_score > cosmetic_score
        assert core_score >= 0.7  # Core modifications should score high
        assert cosmetic_score < 0.5  # Cosmetic modifications should score lower

    def test_exactly_three_goals_generated_per_cycle(self, goal_generator):
        """Test that exactly 3 goals are generated per cycle."""
        # Generate goals for one cycle
        goals = goal_generator.generate_goals(max_goals=3)
        
        # Verify exactly 3 goals are generated
        assert len(goals) == 3
        
        # Verify goals are distinct
        goal_ids = [goal.id for goal in goals]
        assert len(set(goal_ids)) == 3
        
        # Verify goals have different descriptions
        goal_descriptions = [goal.description for goal in goals]
        assert len(set(goal_descriptions)) == 3

    def test_goals_stored_with_correct_metadata(self, goal_generator):
        """Test that goals are stored with correct metadata."""
        goals = goal_generator.generate_goals()
        
        for goal in goals:
            # Check required metadata fields
            assert hasattr(goal, 'id')
            assert hasattr(goal, 'description')
            assert hasattr(goal, 'affected_services')
            assert hasattr(goal, 'severity')
            assert hasattr(goal, 'frequency')
            assert hasattr(goal, 'created_at')
            assert hasattr(goal, 'priority_score')
            assert hasattr(goal, 'status')
            assert hasattr(goal, 'source')
            
            # Verify metadata types
            assert isinstance(goal.id, str)
            assert isinstance(goal.description, str)
            assert isinstance(goal.affected_services, list)
            assert isinstance(goal.severity, float)
            assert isinstance(goal.frequency, int)
            assert isinstance(goal.created_at, datetime)
            assert isinstance(goal.priority_score, float)
            assert isinstance(goal.status, str)
            assert isinstance(goal.source, str)
            
            # Verify metadata values
            assert 0 <= goal.severity <= 1.0
            assert 0 <= goal.priority_score <= 1.0
            assert goal.status in ["pending", "active", "completed", "failed"]
            assert goal.source in ["failure_pattern", "gap_analysis", "diversity"]

    def test_edge_case_all_core_patterns_present_generates_diversity_goals(self, goal_generator_complete):
        """Test edge case when all core patterns are present (should generate diversity goals)."""
        # Generate goals when all core patterns are present
        goals = goal_generator_complete.generate_goals()
        
        # Should generate diversity goals
        assert len(goals) > 0
        
        # Verify goals are diversity-focused
        for goal in goals:
            assert goal.source == "diversity"
            assert "diversity" in goal.description.lower() or "exploration" in goal.description.lower() or "innovation" in goal.description.lower()
        
        # Verify diversity goals have appropriate metadata
        for goal in goals:
            assert goal.severity >= 0.3  # Diversity goals should have reasonable priority
            assert len(goal.affected_services) > 0
            assert goal.status == "pending"

    def test_goal_generation_cycle_consistency(self, goal_generator):
        """Test that goal generation cycle produces consistent results."""
        # Run multiple cycles
        cycle1_goals = goal_generator.generate_goals(max_goals=3)
        cycle2_goals = goal_generator.generate_goals(max_goals=3)
        
        # Verify both cycles produce 3 goals
        assert len(cycle1_goals) == 3
        assert len(cycle2_goals) == 3
        
        # Verify goals are unique across cycles
        cycle1_ids = [goal.id for goal in cycle1_goals]
        cycle2_ids = [goal.id for goal in cycle2_goals]
        assert len(set(cycle1_ids + cycle2_ids)) == 6

    def test_goal_priority_score_persistence(self, goal_generator):
        """Test that priority scores are persisted with goals."""
        goals = goal_generator.generate_goals()
        
        for goal in goals:
            # Verify priority score is stored
            assert hasattr(goal, 'priority_score')
            assert goal.priority_score > 0
            
            # Verify priority score is consistent
            calculated_score = goal_generator.priority_scorer.calculate(goal)
            assert abs(goal.priority_score - calculated_score) < 0.01

    def test_goal_generation_with_mixed_patterns(self, goal_generator):
        """Test goal generation with a mix of failure patterns and gaps."""
        goals = goal_generator.generate_goals()
        
        # Verify goals address both failure patterns and gaps
        failure_patterns = [p["pattern"] for p in MOCK_KNOWLEDGE_BASE["failure_patterns"]]
        gap_descriptions = [g["description"] for g in MOCK_KNOWLEDGE_BASE["gaps"]]
        
        goal_descriptions = [g.description for g in goals]
        
        # At least one goal should address a failure pattern
        assert any(pattern.lower() in desc.lower() for pattern in failure_patterns for desc in goal_descriptions)
        
        # At least one goal should address a gap
        assert any(gap.lower() in desc.lower() for gap in gap_descriptions for desc in goal_descriptions)

    def test_goal_generation_with_no_gaps(self, goal_generator_complete):
        """Test goal generation when there are no gaps."""
        goals = goal_generator_complete.generate_goals()
        
        # Should still generate goals (diversity goals)
        assert len(goals) > 0
        
        # All goals should be diversity-focused
        for goal in goals:
            assert goal.source == "diversity"
            assert "diversity" in goal.description.lower() or "exploration" in goal.description.lower() or "innovation" in goal.description.lower()