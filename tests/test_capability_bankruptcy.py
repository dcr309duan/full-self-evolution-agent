import pytest
from unittest.mock import Mock, patch
from datetime import datetime
from typing import Dict, List, Any

from src.capability_bankruptcy import (
    BankruptcyProtocol,
    Capability,
    CapabilityScore,
    CapabilityStatus,
    KnowledgeBase,
    BankruptcyResult
)

@pytest.fixture
def sample_capabilities() -> Dict[str, Capability]:
    """Create a set of test capabilities with known scores for bankruptcy testing."""
    capabilities = {}
    
    # Create capabilities with varying scores (0-100)
    # Bottom 30% (scores 10-30): 3 capabilities
    for i in range(1, 4):
        cap = Capability(
            id=f"low_{i}",
            name=f"Low Priority Capability {i}",
            score=CapabilityScore(value=i * 10, confidence=0.8),
            status=CapabilityStatus.ACTIVE,
            essential=False,
            last_used=datetime(2024, 1, 1),
            usage_count=5
        )
        capabilities[cap.id] = cap
    
    # Middle 40% (scores 40-70): 4 capabilities
    for i in range(4, 8):
        cap = Capability(
            id=f"mid_{i}",
            name=f"Medium Priority Capability {i}",
            score=CapabilityScore(value=i * 10, confidence=0.9),
            status=CapabilityStatus.ACTIVE,
            essential=False,
            last_used=datetime(2024, 6, 1),
            usage_count=20
        )
        capabilities[cap.id] = cap
    
    # Top 30% (scores 80-100): 3 capabilities
    for i in range(8, 11):
        essential = i == 9  # Make one of the top capabilities essential
        cap = Capability(
            id=f"high_{i}",
            name=f"High Priority Capability {i}",
            score=CapabilityScore(value=i * 10, confidence=0.95),
            status=CapabilityStatus.ACTIVE,
            essential=essential,
            last_used=datetime(2024, 11, 1),
            usage_count=100
        )
        capabilities[cap.id] = cap
    
    return capabilities

@pytest.fixture
def mock_knowledge_base() -> Mock:
    """Create a mock knowledge base for testing."""
    kb = Mock(spec=KnowledgeBase)
    kb.update.return_value = True
    kb.get_capabilities.return_value = {}
    return kb

@pytest.fixture
def bankruptcy_protocol(mock_knowledge_base) -> BankruptcyProtocol:
    """Create a BankruptcyProtocol instance with mock knowledge base."""
    return BankruptcyProtocol(knowledge_base=mock_knowledge_base)

class TestCapabilityBankruptcy:
    """Test suite for the capability bankruptcy protocol."""
    
    def test_bankruptcy_process_archives_bottom_30_percent(
        self, bankruptcy_protocol, sample_capabilities, mock_knowledge_base
    ):
        """Test that the bottom 30% of capabilities are archived."""
        # Arrange
        bankruptcy_protocol.capabilities = sample_capabilities
        
        # Act
        result = bankruptcy_protocol.execute_bankruptcy()
        
        # Assert
        assert isinstance(result, BankruptcyResult)
        
        # Check that bottom 3 capabilities (30% of 10) are archived
        archived_ids = [cap.id for cap in result.archived_capabilities]
        assert "low_1" in archived_ids
        assert "low_2" in archived_ids
        assert "low_3" in archived_ids
        
        # Verify archived capabilities have ARCHIVED status
        for cap in result.archived_capabilities:
            assert cap.status == CapabilityStatus.ARCHIVED
        
        # Verify non-bottom capabilities are not archived
        assert "mid_4" not in archived_ids
        assert "high_8" not in archived_ids
    
    def test_essential_capabilities_are_reimplemented(
        self, bankruptcy_protocol, sample_capabilities, mock_knowledge_base
    ):
        """Test that essential capabilities are re-implemented with improved design."""
        # Arrange
        bankruptcy_protocol.capabilities = sample_capabilities
        
        # Act
        result = bankruptcy_protocol.execute_bankruptcy()
        
        # Assert
        # The essential capability (high_9) should be re-implemented
        reimplemented_ids = [cap.id for cap in result.reimplemented_capabilities]
        assert "high_9" in reimplemented_ids
        
        # Verify re-implemented capabilities have improved design
        for cap in result.reimplemented_capabilities:
            assert cap.design_version > 1  # Design should be improved
            assert cap.score.value >= sample_capabilities[cap.id].score.value  # Score should not decrease
        
        # Verify non-essential capabilities are not re-implemented
        assert "low_1" not in reimplemented_ids
        assert "mid_4" not in reimplemented_ids
    
    def test_knowledge_base_updated_correctly(
        self, bankruptcy_protocol, sample_capabilities, mock_knowledge_base
    ):
        """Test that the knowledge base is updated correctly after bankruptcy."""
        # Arrange
        bankruptcy_protocol.capabilities = sample_capabilities
        
        # Act
        result = bankruptcy_protocol.execute_bankruptcy()
        
        # Assert
        # Verify knowledge base update was called with correct data
        assert mock_knowledge_base.update.called
        
        # Get the call arguments
        call_args = mock_knowledge_base.update.call_args
        updated_data = call_args[0][0]
        
        # Verify archived capabilities are marked in knowledge base
        for cap in result.archived_capabilities:
            assert cap.id in updated_data
            assert updated_data[cap.id]['status'] == CapabilityStatus.ARCHIVED.value
        
        # Verify re-implemented capabilities have updated design info
        for cap in result.reimplemented_capabilities:
            assert cap.id in updated_data
            assert 'design_version' in updated_data[cap.id]
            assert updated_data[cap.id]['design_version'] > 1
        
        # Verify active capabilities remain unchanged
        for cap in result.active_capabilities:
            if cap.id not in [c.id for c in result.reimplemented_capabilities]:
                assert cap.id in updated_data
                assert updated_data[cap.id]['status'] == CapabilityStatus.ACTIVE.value
    
    def test_bankruptcy_result_contains_all_categories(
        self, bankruptcy_protocol, sample_capabilities
    ):
        """Test that bankruptcy result contains all expected categories."""
        # Arrange
        bankruptcy_protocol.capabilities = sample_capabilities
        
        # Act
        result = bankruptcy_protocol.execute_bankruptcy()
        
        # Assert
        assert hasattr(result, 'archived_capabilities')
        assert hasattr(result, 'reimplemented_capabilities')
        assert hasattr(result, 'active_capabilities')
        assert hasattr(result, 'timestamp')
        assert hasattr(result, 'summary')
        
        # Verify total count matches
        total_capabilities = (
            len(result.archived_capabilities) +
            len(result.reimplemented_capabilities) +
            len(result.active_capabilities)
        )
        assert total_capabilities == len(sample_capabilities)
    
    def test_bankruptcy_with_empty_capabilities(
        self, bankruptcy_protocol
    ):
        """Test bankruptcy process with no capabilities."""
        # Arrange
        bankruptcy_protocol.capabilities = {}
        
        # Act
        result = bankruptcy_protocol.execute_bankruptcy()
        
        # Assert
        assert len(result.archived_capabilities) == 0
        assert len(result.reimplemented_capabilities) == 0
        assert len(result.active_capabilities) == 0
        assert result.summary['total_archived'] == 0
        assert result.summary['total_reimplemented'] == 0
    
    def test_bankruptcy_preserves_top_performers(
        self, bankruptcy_protocol, sample_capabilities
    ):
        """Test that top performing capabilities remain active."""
        # Arrange
        bankruptcy_protocol.capabilities = sample_capabilities
        
        # Act
        result = bankruptcy_protocol.execute_bankruptcy()
        
        # Assert
        active_ids = [cap.id for cap in result.active_capabilities]
        
        # Top capabilities should remain active
        assert "high_8" in active_ids
        assert "high_9" in active_ids
        assert "high_10" in active_ids
        
        # Verify top capabilities maintain their status
        for cap in result.active_capabilities:
            if cap.id in ["high_8", "high_9", "high_10"]:
                assert cap.status == CapabilityStatus.ACTIVE