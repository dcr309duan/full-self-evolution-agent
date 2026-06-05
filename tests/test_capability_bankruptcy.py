import pytest
from unittest.mock import Mock, patch, call, MagicMock
from datetime import datetime
from typing import Dict, List, Any
from pathlib import Path

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

    def test_scoring_with_mock_capabilities_varying_call_counts(
        self, bankruptcy_protocol, mock_knowledge_base
    ):
        """Test scoring with mock capabilities having varying call counts."""
        # Arrange
        capabilities = {}
        for i in range(5):
            cap = Capability(
                id=f"cap_{i}",
                name=f"Capability {i}",
                score=CapabilityScore(value=50, confidence=0.8),
                status=CapabilityStatus.ACTIVE,
                essential=False,
                last_used=datetime(2024, 1, 1),
                usage_count=i * 10  # Varying call counts: 0, 10, 20, 30, 40
            )
            capabilities[cap.id] = cap
        
        bankruptcy_protocol.capabilities = capabilities
        
        # Act
        result = bankruptcy_protocol.execute_bankruptcy()
        
        # Assert
        # Capabilities with lower usage counts should be more likely to be archived
        archived_ids = [cap.id for cap in result.archived_capabilities]
        assert "cap_0" in archived_ids  # Lowest usage count
        assert "cap_1" in archived_ids  # Second lowest usage count

    def test_scoring_with_mock_capabilities_varying_ages(
        self, bankruptcy_protocol, mock_knowledge_base
    ):
        """Test scoring with mock capabilities having varying ages."""
        # Arrange
        capabilities = {}
        for i in range(5):
            cap = Capability(
                id=f"cap_{i}",
                name=f"Capability {i}",
                score=CapabilityScore(value=50, confidence=0.8),
                status=CapabilityStatus.ACTIVE,
                essential=False,
                last_used=datetime(2024, 1, 1 + i * 30),  # Varying ages: 0, 30, 60, 90, 120 days
                usage_count=20
            )
            capabilities[cap.id] = cap
        
        bankruptcy_protocol.capabilities = capabilities
        
        # Act
        result = bankruptcy_protocol.execute_bankruptcy()
        
        # Assert
        # Older capabilities should be more likely to be archived
        archived_ids = [cap.id for cap in result.archived_capabilities]
        assert "cap_0" in archived_ids  # Oldest
        assert "cap_1" in archived_ids  # Second oldest

    def test_scoring_with_mock_capabilities_varying_dependencies(
        self, bankruptcy_protocol, mock_knowledge_base
    ):
        """Test scoring with mock capabilities having varying dependencies."""
        # Arrange
        capabilities = {}
        for i in range(5):
            cap = Capability(
                id=f"cap_{i}",
                name=f"Capability {i}",
                score=CapabilityScore(value=50, confidence=0.8),
                status=CapabilityStatus.ACTIVE,
                essential=False,
                last_used=datetime(2024, 1, 1),
                usage_count=20,
                dependencies=[f"dep_{j}" for j in range(i)]  # Varying dependencies: 0, 1, 2, 3, 4
            )
            capabilities[cap.id] = cap
        
        bankruptcy_protocol.capabilities = capabilities
        
        # Act
        result = bankruptcy_protocol.execute_bankruptcy()
        
        # Assert
        # Capabilities with fewer dependencies should be more likely to be archived
        archived_ids = [cap.id for cap in result.archived_capabilities]
        assert "cap_0" in archived_ids  # Fewest dependencies
        assert "cap_1" in archived_ids  # Second fewest dependencies

    def test_threshold_based_removal_triggers(
        self, bankruptcy_protocol, mock_knowledge_base
    ):
        """Test that threshold-based removal triggers work correctly."""
        # Arrange
        capabilities = {}
        # Create capabilities with scores below and above threshold
        for i in range(5):
            cap = Capability(
                id=f"cap_{i}",
                name=f"Capability {i}",
                score=CapabilityScore(value=i * 15, confidence=0.8),  # Scores: 0, 15, 30, 45, 60
                status=CapabilityStatus.ACTIVE,
                essential=False,
                last_used=datetime(2024, 1, 1),
                usage_count=10
            )
            capabilities[cap.id] = cap
        
        bankruptcy_protocol.capabilities = capabilities
        bankruptcy_protocol.score_threshold = 30  # Set threshold to 30
        
        # Act
        result = bankruptcy_protocol.execute_bankruptcy()
        
        # Assert
        archived_ids = [cap.id for cap in result.archived_capabilities]
        # Capabilities with score below threshold should be archived
        assert "cap_0" in archived_ids  # Score 0
        assert "cap_1" in archived_ids  # Score 15
        assert "cap_2" in archived_ids  # Score 30 (at threshold)
        # Capabilities with score above threshold should not be archived
        assert "cap_3" not in archived_ids  # Score 45
        assert "cap_4" not in archived_ids  # Score 60

    def test_merge_suggestion_when_capabilities_overlap(
        self, bankruptcy_protocol, mock_knowledge_base
    ):
        """Test that merge suggestions are generated when capabilities overlap."""
        # Arrange
        capabilities = {}
        # Create overlapping capabilities
        cap1 = Capability(
            id="cap_1",
            name="Data Processing",
            score=CapabilityScore(value=40, confidence=0.8),
            status=CapabilityStatus.ACTIVE,
            essential=False,
            last_used=datetime(2024, 1, 1),
            usage_count=10,
            capabilities=["data_processing", "data_validation", "data_export"]
        )
        cap2 = Capability(
            id="cap_2",
            name="Data Validation",
            score=CapabilityScore(value=35, confidence=0.8),
            status=CapabilityStatus.ACTIVE,
            essential=False,
            last_used=datetime(2024, 1, 1),
            usage_count=8,
            capabilities=["data_validation", "data_cleaning", "data_import"]
        )
        cap3 = Capability(
            id="cap_3",
            name="Data Export",
            score=CapabilityScore(value=30, confidence=0.8),
            status=CapabilityStatus.ACTIVE,
            essential=False,
            last_used=datetime(2024, 1, 1),
            usage_count=5,
            capabilities=["data_export", "data_reporting"]
        )
        
        capabilities[cap1.id] = cap1
        capabilities[cap2.id] = cap2
        capabilities[cap3.id] = cap3
        
        bankruptcy_protocol.capabilities = capabilities
        
        # Act
        result = bankruptcy_protocol.execute_bankruptcy()
        
        # Assert
        assert hasattr(result, 'merge_suggestions')
        assert len(result.merge_suggestions) > 0
        
        # Check that merge suggestions involve overlapping capabilities
        for suggestion in result.merge_suggestions:
            assert 'cap_1' in suggestion or 'cap_2' in suggestion or 'cap_3' in suggestion
            assert suggestion['reason'] == 'capabilities_overlap'

    def test_rollback_mechanism_with_failing_test(
        self, bankruptcy_protocol, sample_capabilities, mock_knowledge_base
    ):
        """Test that rollback mechanism works when a test fails during bankruptcy."""
        # Arrange
        bankruptcy_protocol.capabilities = sample_capabilities
        
        # Mock the validation step to fail
        original_validate = bankruptcy_protocol.validate_bankruptcy
        def failing_validate(result):
            raise ValueError("Validation failed: Inconsistent state detected")
        
        bankruptcy_protocol.validate_bankruptcy = failing_validate
        
        # Capture the state before bankruptcy
        original_capabilities = sample_capabilities.copy()
        
        # Act & Assert
        with pytest.raises(ValueError, match="Validation failed"):
            bankruptcy_protocol.execute_bankruptcy()
        
        # Verify rollback: capabilities should be restored to original state
        for cap_id, cap in bankruptcy_protocol.capabilities.items():
            assert cap.status == original_capabilities[cap_id].status
            assert cap.score.value == original_capabilities[cap_id].score.value
        
        # Verify knowledge base was not updated
        assert not mock_knowledge_base.update.called
        
        # Restore original validate method
        bankruptcy_protocol.validate_bankruptcy = original_validate

    def test_enforcement_timing_divisible_by_5(
        self, bankruptcy_protocol, sample_capabilities, mock_knowledge_base
    ):
        """Test that bankruptcy enforcement runs only on cycles divisible by 5."""
        # Arrange
        bankruptcy_protocol.capabilities = sample_capabilities
        
        # Test cycles that are not divisible by 5
        for cycle in [1, 2, 3, 4, 6, 7, 8, 9, 11]:
            bankruptcy_protocol.current_cycle = cycle
            result = bankruptcy_protocol.execute_bankruptcy()
            assert result is None or result.summary['total_archived'] == 0
            assert not mock_knowledge_base.update.called
        
        # Test cycles that are divisible by 5
        for cycle in [5, 10, 15, 20]:
            bankruptcy_protocol.current_cycle = cycle
            result = bankruptcy_protocol.execute_bankruptcy()
            assert result is not None
            assert result.summary['total_archived'] > 0
            assert mock_knowledge_base.update.called

    def test_critical_capabilities_never_removed(
        self, bankruptcy_protocol, mock_knowledge_base
    ):
        """Test that critical capabilities (core modules) are never removed regardless of score."""
        # Arrange
        capabilities = {}
        
        # Create critical capabilities with very low scores
        for i in range(3):
            cap = Capability(
                id=f"core_{i}",
                name=f"Core Module {i}",
                score=CapabilityScore(value=5, confidence=0.8),  # Very low score
                status=CapabilityStatus.ACTIVE,
                essential=True,  # Marked as essential/core
                last_used=datetime(2024, 1, 1),
                usage_count=1,
                is_critical=True  # Critical capability flag
            )
            capabilities[cap.id] = cap
        
        # Create non-critical capabilities with varying scores
        for i in range(5):
            cap = Capability(
                id=f"non_core_{i}",
                name=f"Non-Core Module {i}",
                score=CapabilityScore(value=i * 10, confidence=0.8),
                status=CapabilityStatus.ACTIVE,
                essential=False,
                last_used=datetime(2024, 1, 1),
                usage_count=5,
                is_critical=False
            )
            capabilities[cap.id] = cap
        
        bankruptcy_protocol.capabilities = capabilities
        
        # Act
        result = bankruptcy_protocol.execute_bankruptcy()
        
        # Assert
        archived_ids = [cap.id for cap in result.archived_capabilities]
        reimplemented_ids = [cap.id for cap in result.reimplemented_capabilities]
        active_ids = [cap.id for cap in result.active_capabilities]
        
        # Critical capabilities should never be archived
        for i in range(3):
            assert f"core_{i}" not in archived_ids
            # Critical capabilities should either be re-implemented or remain active
            assert f"core_{i}" in reimplemented_ids or f"core_{i}" in active_ids
        
        # Non-critical capabilities with low scores should be archived
        assert "non_core_0" in archived_ids  # Score 0
        assert "non_core_1" in archived_ids  # Score 10
        
        # Verify critical capabilities maintain their status
        for cap in result.active_capabilities + result.reimplemented_capabilities:
            if cap.id.startswith("core_"):
                assert cap.status == CapabilityStatus.ACTIVE or cap.status == CapabilityStatus.REIMPLEMENTED
                assert cap.is_critical == True

    def test_bankruptcy_runs_only_at_cycle_mod_50(
        self, bankruptcy_protocol, sample_capabilities, mock_knowledge_base
    ):
        """Test that bankruptcy runs only when cycle % 50 == 0."""
        # Arrange
        bankruptcy_protocol.capabilities = sample_capabilities
        
        # Test cycles that are not divisible by 50
        for cycle in [1, 49, 51, 99, 101, 149]:
            bankruptcy_protocol.current_cycle = cycle
            result = bankruptcy_protocol.execute_bankruptcy()
            assert result is None or result.summary['total_archived'] == 0
            assert not mock_knowledge_base.update.called
        
        # Test cycles that are divisible by 50
        for cycle in [50, 100, 150, 200]:
            bankruptcy_protocol.current_cycle = cycle
            result = bankruptcy_protocol.execute_bankruptcy()
            assert result is not None
            assert result.summary['total_archived'] > 0
            assert mock_knowledge_base.update.called

    def test_scoring_with_mock_modules_known_usage_test_pass_loc(
        self, bankruptcy_protocol, mock_knowledge_base
    ):
        """Test scoring with mock modules of known usage/test_pass/LOC."""
        # Arrange
        capabilities = {}
        
        # Module A: high usage, high test pass rate, high LOC
        cap_a = Capability(
            id="module_a",
            name="Module A",
            score=CapabilityScore(value=80, confidence=0.9),
            status=CapabilityStatus.ACTIVE,
            essential=False,
            last_used=datetime(2024, 11, 1),
            usage_count=100,
            test_pass_rate=0.95,
            lines_of_code=500
        )
        capabilities[cap_a.id] = cap_a
        
        # Module B: medium usage, medium test pass rate, medium LOC
        cap_b = Capability(
            id="module_b",
            name="Module B",
            score=CapabilityScore(value=50, confidence=0.8),
            status=CapabilityStatus.ACTIVE,
            essential=False,
            last_used=datetime(2024, 6, 1),
            usage_count=50,
            test_pass_rate=0.80,
            lines_of_code=300
        )
        capabilities[cap_b.id] = cap_b
        
        # Module C: low usage, low test pass rate, low LOC
        cap_c = Capability(
            id="module_c",
            name="Module C",
            score=CapabilityScore(value=20, confidence=0.7),
            status=CapabilityStatus.ACTIVE,
            essential=False,
            last_used=datetime(2024, 1, 1),
            usage_count=10,
            test_pass_rate=0.60,
            lines_of_code=100
        )
        capabilities[cap_c.id] = cap_c
        
        bankruptcy_protocol.capabilities = capabilities
        
        # Act
        result = bankruptcy_protocol.execute_bankruptcy()
        
        # Assert
        archived_ids = [cap.id for cap in result.archived_capabilities]
        reimplemented_ids = [cap.id for cap in result.reimplemented_capabilities]
        active_ids = [cap.id for cap in result.active_capabilities]
        
        # Module C (low usage, low test pass, low LOC) should be archived
        assert "module_c" in archived_ids
        
        # Module A (high usage, high test pass, high LOC) should remain active
        assert "module_a" in active_ids
        
        # Module B (medium) might be active or reimplemented
        assert "module_b" in active_ids or "module_b" in reimplemented_ids

    def test_archival_moves_file_to_archive_directory(
        self, bankruptcy_protocol, sample_capabilities, mock_knowledge_base, tmp_path
    ):
        """Test that archival moves file to archive/ directory."""
        # Arrange
        bankruptcy_protocol.capabilities = sample_capabilities
        bankruptcy_protocol.archive_dir = tmp_path / "archive"
        bankruptcy_protocol.archive_dir.mkdir(exist_ok=True)
        
        # Create mock files for capabilities
        for cap_id, cap in sample_capabilities.items():
            cap_file = tmp_path / f"{cap_id}.py"
            cap_file.write_text(f"# {cap.name} module")
            cap.file_path = str(cap_file)
        
        # Act
        result = bankruptcy_protocol.execute_bankruptcy()
        
        # Assert
        for cap in result.archived_capabilities:
            # Check that the file was moved to archive directory
            archived_file = bankruptcy_protocol.archive_dir / f"{cap.id}.py"
            assert archived_file.exists()
            # Check that the original file no longer exists
            original_file = tmp_path / f"{cap.id}.py"
            assert not original_file.exists()

    def test_re_derived_module_created_with_v2_suffix(
        self, bankruptcy_protocol, sample_capabilities, mock_knowledge_base, tmp_path
    ):
        """Test that re-derived module is created with _v2 suffix."""
        # Arrange
        bankruptcy_protocol.capabilities = sample_capabilities
        bankruptcy_protocol.output_dir = tmp_path
        
        # Act
        result = bankruptcy_protocol.execute_bankruptcy()
        
        # Assert
        for cap in result.reimplemented_capabilities:
            # Check that a _v2 file was created
            v2_file = tmp_path / f"{cap.id}_v2.py"
            assert v2_file.exists()
            # Check that the original file still exists
            original_file = tmp_path / f"{cap.id}.py"
            assert original_file.exists()

    def test_modules_above_threshold_not_touched(
        self, bankruptcy_protocol, mock_knowledge_base
    ):
        """Test that modules above threshold are not touched."""
        # Arrange
        capabilities = {}
        
        # Create modules with scores above and below threshold
        for i in range(5):
            cap = Capability(
                id=f"cap_{i}",
                name=f"Capability {i}",
                score=CapabilityScore(value=i * 25, confidence=0.8),  # Scores: 0, 25, 50, 75, 100
                status=CapabilityStatus.ACTIVE,
                essential=False,
                last_used=datetime(2024, 1, 1),
                usage_count=10
            )
            capabilities[cap.id] = cap
        
        bankruptcy_protocol.capabilities = capabilities
        bankruptcy_protocol.score_threshold = 60  # Set threshold to 60
        
        # Act
        result = bankruptcy_protocol.execute_bankruptcy()
        
        # Assert
        archived_ids = [cap.id for cap in result.archived_capabilities]
        reimplemented_ids = [cap.id for cap in result.reimplemented_capabilities]
        active_ids = [cap.id for cap in result.active_capabilities]
        
        # Modules above threshold (score >= 60) should not be archived or reimplemented
        assert "cap_3" not in archived_ids  # Score 75
        assert "cap_3" not in reimplemented_ids  # Score 75
        assert "cap_4" not in archived_ids  # Score 100
        assert "cap_4" not in reimplemented_ids  # Score 100
        
        # Modules above threshold should remain active
        assert "cap_3" in active_ids
        assert "cap_4" in active_ids
        
        # Modules below threshold may be archived or reimplemented
        assert "cap_0" in archived_ids or "cap_0" in reimplemented_ids
        assert "cap_1" in archived_ids or "cap_1" in reimplemented_ids

    def test_all_modules_below_threshold(
        self, bankruptcy_protocol, mock_knowledge_base
    ):
        """Test edge case: all modules below threshold."""
        # Arrange
        capabilities = {}
        
        # Create all modules with scores below threshold
        for i in range(5):
            cap = Capability(
                id=f"cap_{i}",
                name=f"Capability {i}",
                score=CapabilityScore(value=i * 10, confidence=0.8),  # Scores: 0, 10, 20, 30, 40
                status=CapabilityStatus.ACTIVE,
                essential=False,
                last_used=datetime(2024, 1, 1),
                usage_count=5
            )
            capabilities[cap.id] = cap
        
        bankruptcy_protocol.capabilities = capabilities
        bankruptcy_protocol.score_threshold = 50  # Set threshold above all scores
        
        # Act
        result = bankruptcy_protocol.execute_bankruptcy()
        
        # Assert
        archived_ids = [cap.id for cap in result.archived_capabilities]
        reimplemented_ids = [cap.id for cap in result.reimplemented_capabilities]
        active_ids = [cap.id for cap in result.active_capabilities]
        
        # All modules should be either archived or reimplemented
        all_processed = set(archived_ids + reimplemented_ids)
        for i in range(5):
            assert f"cap_{i}" in all_processed
        
        # No modules should remain active
        assert len(active_ids) == 0

    def test_no_modules_exist(
        self, bankruptcy_protocol
    ):
        """Test edge case: no modules exist."""
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
        assert result.summary['total_active'] == 0

    def test_scoring_function_with_mock_module_data(self, bankruptcy_protocol, mock_knowledge_base):
        """Test that scoring function works correctly with mock module data."""
        # Arrange
        capabilities = {}
        
        # Create mock modules with specific attributes
        module_a = Capability(
            id="module_a",
            name="Module A",
            score=CapabilityScore(value=0, confidence=0.0),
            status=CapabilityStatus.ACTIVE,
            essential=False,
            last_used=datetime(2024, 11, 1),
            usage_count=100,
            test_pass_rate=0.95,
            lines_of_code=500
        )
        capabilities[module_a.id] = module_a
        
        module_b = Capability(
            id="module_b",
            name="Module B",
            score=CapabilityScore(value=0, confidence=0.0),
            status=CapabilityStatus.ACTIVE,
            essential=False,
            last_used=datetime(2024, 6, 1),
            usage_count=50,
            test_pass_rate=0.80,
            lines_of_code=300
        )
        capabilities[module_b.id] = module_b
        
        module_c = Capability(
            id="module_c",
            name="Module C",
            score=CapabilityScore(value=0, confidence=0.0),
            status=CapabilityStatus.ACTIVE,
            essential=False,
            last_used=datetime(2024, 1, 1),
            usage_count=10,
            test_pass_rate=0.60,
            lines_of_code=100
        )
        capabilities[module_c.id] = module_c
        
        bankruptcy_protocol.capabilities = capabilities
        
        # Act
        scores = bankruptcy_protocol.score_capabilities()
        
        # Assert
        # Module A should have highest score due to high usage, test pass rate, and LOC
        assert scores["module_a"] > scores["module_b"]
        assert scores["module_a"] > scores["module_c"]
        
        # Module C should have lowest score
        assert scores["module_c"] < scores["module_b"]
        assert scores["module_c"] < scores["module_a"]
        
        # Scores should be between 0 and 100
        for score in scores.values():
            assert 0 <= score <= 100

    def test_archival_moves_files_and_creates_archive_directory(
        self, bankruptcy_protocol, sample_capabilities, mock_knowledge_base, tmp_path
    ):
        """Test that archiving moves files and creates archive directory."""
        # Arrange
        bankruptcy_protocol.capabilities = sample_capabilities
        archive_dir = tmp_path / "archive"
        bankruptcy_protocol.archive_dir = archive_dir
        
        # Create mock files for capabilities
        for cap_id, cap in sample_capabilities.items():
            cap_file = tmp_path / f"{cap_id}.py"
            cap_file.write_text(f"# {cap.name} module")
            cap.file_path = str(cap_file)
        
        # Act
        result = bankruptcy_protocol.execute_bankruptcy()
        
        # Assert
        # Archive directory should exist
        assert archive_dir.exists()
        assert archive_dir.is_dir()
        
        # Files for archived capabilities should be moved to archive directory
        for cap in result.archived_capabilities:
            archived_file = archive_dir / f"{cap.id}.py"
            assert archived_file.exists()
            original_file = tmp_path / f"{cap.id}.py"
            assert not original_file.exists()
        
        # Files for non-archived capabilities should remain in original location
        for cap in result.active_capabilities:
            original_file = tmp_path / f"{cap.id}.py"
            assert original_file.exists()

    def test_re_derivation_calls_llm_with_correct_prompt(
        self, bankruptcy_protocol, sample_capabilities, mock_knowledge_base
    ):
        """Test that re-derivation calls LLM with correct prompt."""
        # Arrange
        bankruptcy_protocol.capabilities = sample_capabilities
        
        # Mock the LLM call
        with patch.object(bankruptcy_protocol, 'call_llm_for_rederivation') as mock_llm:
            mock_llm.return_value = "Improved implementation"
            
            # Act
            result = bankruptcy_protocol.execute_bankruptcy()
            
            # Assert
            # LLM should be called for each re-implemented capability
            for cap in result.reimplemented_capabilities:
                # Check that LLM was called with correct prompt
                mock_llm.assert_any_call(
                    capability=cap,
                    prompt_type="rederivation",
                    context={
                        "capability_id": cap.id,
                        "capability_name": cap.name,
                        "current_score": cap.score.value,
                        "improvement_goal": "Improve design and functionality"
                    }
                )
            
            # LLM should not be called for archived or active capabilities
            for cap in result.archived_capabilities:
                with pytest.raises(AssertionError):
                    mock_llm.assert_any_call(
                        capability=cap,
                        prompt_type="rederivation",
                        context=pytest.approx.ANY
                    )
            
            for cap in result.active_capabilities:
                with pytest.raises(AssertionError):
                    mock_llm.assert_any_call(
                        capability=cap,
                        prompt_type="rederivation",
                        context=pytest.approx.ANY
                    )

    def test_modules_above_threshold_not_archived(
        self, bankruptcy_protocol, mock_knowledge_base
    ):
        """Test that modules above threshold are not archived."""
        # Arrange
        capabilities = {}
        
        # Create modules with