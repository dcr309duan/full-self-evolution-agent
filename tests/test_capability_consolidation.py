import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
from typing import List, Dict, Any
from src.capability_consolidation import CapabilityConsolidator, Capability, ConsolidationResult

@pytest.fixture
def mock_capabilities() -> List[Capability]:
    """Create 25+ mock capabilities with varying usage and failure metrics."""
    capabilities = []
    base_time = datetime.now()
    
    for i in range(30):
        cap = MagicMock(spec=Capability)
        cap.id = f"cap_{i}"
        cap.name = f"Capability {i}"
        cap.description = f"Description for capability {i} with keywords: test, automation, processing"
        cap.usage_count = 100 - (i * 3)  # Decreasing usage
        cap.failure_rate = 0.01 + (i * 0.03)  # Increasing failure rate
        cap.last_used = base_time - timedelta(days=i * 5)
        cap.is_archived = False
        cap.is_active = True
        cap.created_at = base_time - timedelta(days=365)
        cap.metadata = {
            "category": "test" if i % 2 == 0 else "production",
            "version": f"1.{i}",
            "owner": f"team_{i % 5}"
        }
        capabilities.append(cap)
    
    return capabilities

@pytest.fixture
def consolidator() -> CapabilityConsolidator:
    """Create a CapabilityConsolidator instance with mocked dependencies."""
    with patch('src.capability_consolidation.CapabilityRepository') as mock_repo:
        consolidator = CapabilityConsolidator(repository=mock_repo)
        yield consolidator

class TestCapabilityConsolidation:
    """Test suite for capability consolidation functionality."""
    
    def test_selects_lowest_scoring_capabilities(self, consolidator, mock_capabilities):
        """Verify selection picks the lowest-scoring capabilities based on metrics."""
        # Mock the scoring function to return predictable scores
        with patch.object(consolidator, '_calculate_score') as mock_score:
            # Assign scores inversely proportional to index (lower index = lower score)
            mock_score.side_effect = lambda cap: mock_capabilities.index(cap)
            
            selected = consolidator._select_candidates(mock_capabilities, count=2)
            
            # Should select the two lowest-scoring capabilities (indices 0 and 1)
            assert len(selected) == 2
            assert selected[0].id == "cap_0"
            assert selected[1].id == "cap_1"
    
    def test_merged_description_contains_keywords(self, consolidator):
        """Verify merged capability description contains keywords from both originals."""
        cap1 = MagicMock(spec=Capability)
        cap1.description = "This capability handles data processing and analysis"
        cap1.name = "Data Processor"
        
        cap2 = MagicMock(spec=Capability)
        cap2.description = "This capability manages automated reporting and visualization"
        cap2.name = "Report Manager"
        
        merged = consolidator._merge_capabilities(cap1, cap2)
        
        # Check that keywords from both descriptions are present
        assert "processing" in merged.description or "analysis" in merged.description
        assert "reporting" in merged.description or "visualization" in merged.description
        assert "automated" in merged.description
    
    def test_originals_archived_and_removed(self, consolidator, mock_capabilities):
        """Verify original capabilities are archived and removed from active list."""
        # Setup
        selected = [mock_capabilities[0], mock_capabilities[1]]
        active_caps = mock_capabilities.copy()
        
        # Mock the archive operation
        with patch.object(consolidator, '_archive_capability') as mock_archive:
            with patch.object(consolidator, '_remove_from_active') as mock_remove:
                result = consolidator._process_consolidation(selected, active_caps)
                
                # Verify both originals were archived
                assert mock_archive.call_count == 2
                mock_archive.assert_any_call(mock_capabilities[0])
                mock_archive.assert_any_call(mock_capabilities[1])
                
                # Verify both originals were removed from active list
                assert mock_remove.call_count == 2
                mock_remove.assert_any_call(mock_capabilities[0])
                mock_remove.assert_any_call(mock_capabilities[1])
                
                # Verify the merged capability is in the active list
                assert result.merged_capability in active_caps
                assert mock_capabilities[0] not in active_caps
                assert mock_capabilities[1] not in active_caps
    
    def test_edge_case_less_than_20_capabilities_no_op(self, consolidator):
        """Test edge case where capabilities <= 20 results in no-op."""
        # Create only 15 capabilities
        small_cap_list = []
        for i in range(15):
            cap = MagicMock(spec=Capability)
            cap.id = f"small_cap_{i}"
            cap.is_active = True
            small_cap_list.append(cap)
        
        # Mock the consolidation method
        with patch.object(consolidator, '_select_candidates') as mock_select:
            with patch.object(consolidator, '_process_consolidation') as mock_process:
                result = consolidator.consolidate(small_cap_list)
                
                # Verify no consolidation was performed
                mock_select.assert_not_called()
                mock_process.assert_not_called()
                
                # Verify result indicates no-op
                assert result is None or result.success == False
    
    def test_consolidation_with_varying_metrics(self, consolidator, mock_capabilities):
        """Test consolidation with capabilities having varying usage and failure metrics."""
        # Modify some capabilities to have extreme metrics
        mock_capabilities[0].usage_count = 5
        mock_capabilities[0].failure_rate = 0.95
        
        mock_capabilities[1].usage_count = 10
        mock_capabilities[1].failure_rate = 0.85
        
        mock_capabilities[2].usage_count = 1000
        mock_capabilities[2].failure_rate = 0.01
        
        # Mock scoring to prioritize low usage + high failure
        with patch.object(consolidator, '_calculate_score') as mock_score:
            mock_score.side_effect = lambda cap: (
                cap.usage_count * 0.5 + cap.failure_rate * 100
            )
            
            selected = consolidator._select_candidates(mock_capabilities, count=2)
            
            # Should select capabilities with lowest scores (highest failure + lowest usage)
            assert selected[0].id == "cap_0"  # Highest failure, lowest usage
            assert selected[1].id == "cap_1"  # Second highest failure, second lowest usage
    
    def test_consolidation_result_structure(self, consolidator, mock_capabilities):
        """Verify the consolidation result has proper structure and data."""
        selected = [mock_capabilities[0], mock_capabilities[1]]
        
        with patch.object(consolidator, '_archive_capability'):
            with patch.object(consolidator, '_remove_from_active'):
                with patch.object(consolidator, '_merge_capabilities') as mock_merge:
                    mock_merge.return_value = MagicMock(spec=Capability, id="merged_cap")
                    
                    result = consolidator._process_consolidation(selected, mock_capabilities)
                    
                    # Verify result structure
                    assert isinstance(result, ConsolidationResult)
                    assert result.merged_capability is not None
                    assert len(result.original_capabilities) == 2
                    assert result.original_capabilities[0].id == "cap_0"
                    assert result.original_capabilities[1].id == "cap_1"
                    assert result.timestamp is not None
                    assert isinstance(result.timestamp, datetime)
    
    def test_consolidation_with_archived_capabilities(self, consolidator, mock_capabilities):
        """Test that already archived capabilities are not selected for consolidation."""
        # Archive some capabilities
        mock_capabilities[5].is_archived = True
        mock_capabilities[10].is_archived = True
        
        with patch.object(consolidator, '_calculate_score') as mock_score:
            mock_score.side_effect = lambda cap: mock_capabilities.index(cap)
            
            selected = consolidator._select_candidates(mock_capabilities, count=2)
            
            # Should not select archived capabilities
            for cap in selected:
                assert cap.is_archived == False
    
    def test_concurrent_consolidation_safety(self, consolidator, mock_capabilities):
        """Test that consolidation handles concurrent operations safely."""
        import threading
        results = []
        
        def consolidate_thread():
            with patch.object(consolidator, '_select_candidates') as mock_select:
                mock_select.return_value = [mock_capabilities[0], mock_capabilities[1]]
                with patch.object(consolidator, '_process_consolidation') as mock_process:
                    mock_process.return_value = ConsolidationResult(
                        merged_capability=MagicMock(),
                        original_capabilities=[mock_capabilities[0], mock_capabilities[1]],
                        timestamp=datetime.now()
                    )
                    result = consolidator.consolidate(mock_capabilities)
                    results.append(result)
        
        threads = []
        for _ in range(5):
            t = threading.Thread(target=consolidate_thread)
            threads.append(t)
            t.start()
        
        for t in threads:
            t.join()
        
        # Verify all threads completed successfully
        assert len(results) == 5
        assert all(r is not None for r in results)