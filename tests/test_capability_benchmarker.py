import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
from typing import Dict, List, Optional

# Import the modules to test
from src.capability_benchmarker import CapabilityBenchmarker, CapabilityRegistry
from src.orchestrator import Orchestrator

class TestCapabilityBenchmarker:
    """Test suite for CapabilityBenchmarker functionality."""

    @pytest.fixture
    def benchmarker(self):
        """Create a fresh CapabilityBenchmarker instance for each test."""
        return CapabilityBenchmarker()

    @pytest.fixture
    def mock_registry(self):
        """Create a mock CapabilityRegistry."""
        registry = MagicMock(spec=CapabilityRegistry)
        registry.get_capabilities.return_value = {
            'cap1': {'enabled': True, 'delta': 0.0},
            'cap2': {'enabled': True, 'delta': 0.0},
            'cap3': {'enabled': False, 'delta': -0.1}
        }
        return registry

    def test_benchmark_with_and_without_capability(self, benchmarker):
        """Test that benchmark correctly compares performance with/without capability."""
        # Setup test capability
        capability_name = "test_capability"
        
        # Mock the benchmark results
        with patch.object(benchmarker, '_run_benchmark') as mock_benchmark:
            # Simulate benchmark results: with capability = 85, without = 75
            mock_benchmark.side_effect = [
                {'score': 85, 'latency': 0.5, 'throughput': 100},  # With capability
                {'score': 75, 'latency': 0.7, 'throughput': 80}    # Without capability
            ]
            
            # Execute benchmark
            result = benchmarker.benchmark_capability(capability_name)
            
            # Verify benchmark was called twice (with and without capability)
            assert mock_benchmark.call_count == 2
            
            # Verify the comparison results
            assert result['capability'] == capability_name
            assert result['with_capability']['score'] == 85
            assert result['without_capability']['score'] == 75
            assert result['delta'] == 10.0  # 85 - 75 = 10
            assert result['improvement'] > 0

    def test_benchmark_negative_delta_disables_capability(self, benchmarker, mock_registry):
        """Test that capabilities with negative delta get disabled."""
        # Setup benchmarker with mock registry
        benchmarker.registry = mock_registry
        
        capability_name = "poor_performing_capability"
        
        # Mock benchmark to return worse performance with capability
        with patch.object(benchmarker, '_run_benchmark') as mock_benchmark:
            mock_benchmark.side_effect = [
                {'score': 60, 'latency': 1.0, 'throughput': 50},   # With capability (worse)
                {'score': 80, 'latency': 0.6, 'throughput': 90}    # Without capability (better)
            ]
            
            # Execute benchmark
            result = benchmarker.benchmark_capability(capability_name)
            
            # Verify negative delta
            assert result['delta'] < 0
            assert result['improvement'] < 0
            
            # Verify capability was disabled
            mock_registry.disable_capability.assert_called_once_with(capability_name)
            
            # Verify the state was updated
            updated_state = mock_registry.get_capability_state(capability_name)
            assert updated_state['enabled'] == False

    def test_registry_persists_state_across_cycles(self, benchmarker):
        """Test that registry persists state across multiple benchmark cycles."""
        # Create a real registry (not mock) to test persistence
        registry = CapabilityRegistry()
        benchmarker.registry = registry
        
        # First benchmark cycle
        capability_name = "persistent_capability"
        with patch.object(benchmarker, '_run_benchmark') as mock_benchmark:
            mock_benchmark.side_effect = [
                {'score': 70, 'latency': 0.8, 'throughput': 85},   # With capability
                {'score': 65, 'latency': 0.9, 'throughput': 75}    # Without capability
            ]
            
            # Run first benchmark cycle
            first_result = benchmarker.benchmark_capability(capability_name)
            
            # Verify initial state
            initial_state = registry.get_capability_state(capability_name)
            assert initial_state['enabled'] == True
            assert initial_state['delta'] == 5.0
            
            # Second benchmark cycle (simulating later time)
            mock_benchmark.side_effect = [
                {'score': 55, 'latency': 1.2, 'throughput': 60},   # With capability (worse now)
                {'score': 75, 'latency': 0.7, 'throughput': 95}    # Without capability (better)
            ]
            
            # Run second benchmark cycle
            second_result = benchmarker.benchmark_capability(capability_name)
            
            # Verify state persisted and updated
            updated_state = registry.get_capability_state(capability_name)
            assert updated_state['enabled'] == False  # Should be disabled now
            assert updated_state['delta'] == -20.0  # 55 - 75 = -20
            
            # Verify historical data is maintained
            history = registry.get_capability_history(capability_name)
            assert len(history) == 2
            assert history[0]['delta'] == 5.0
            assert history[1]['delta'] == -20.0

    def test_integration_with_orchestrator(self, benchmarker):
        """Test integration between benchmarker and orchestrator."""
        # Create mock orchestrator
        orchestrator = MagicMock(spec=Orchestrator)
        orchestrator.get_capabilities.return_value = ['cap1', 'cap2', 'cap3']
        orchestrator.get_capability_config.return_value = {'enabled': True, 'threshold': 0.1}
        
        # Connect benchmarker to orchestrator
        benchmarker.set_orchestrator(orchestrator)
        
        # Mock benchmark results for multiple capabilities
        with patch.object(benchmarker, '_run_benchmark') as mock_benchmark:
            # Setup mock returns for different capabilities
            mock_benchmark.side_effect = [
                # cap1: positive delta (keep enabled)
                {'score': 90, 'latency': 0.3, 'throughput': 120},
                {'score': 70, 'latency': 0.5, 'throughput': 90},
                # cap2: negative delta (disable)
                {'score': 50, 'latency': 1.5, 'throughput': 40},
                {'score': 85, 'latency': 0.4, 'throughput': 110},
                # cap3: neutral delta (keep as is)
                {'score': 75, 'latency': 0.6, 'throughput': 95},
                {'score': 75, 'latency': 0.6, 'throughput': 95}
            ]
            
            # Run full benchmark suite
            results = benchmarker.run_full_benchmark()
            
            # Verify orchestrator interactions
            assert orchestrator.get_capabilities.called
            assert orchestrator.get_capability_config.called
            
            # Verify results processing
            assert len(results) == 3
            
            # Check cap1 (should remain enabled)
            assert results['cap1']['delta'] > 0
            orchestrator.enable_capability.assert_not_called()  # Already enabled
            
            # Check cap2 (should be disabled)
            assert results['cap2']['delta'] < 0
            orchestrator.disable_capability.assert_called_once_with('cap2')
            
            # Check cap3 (neutral, should remain as is)
            assert results['cap3']['delta'] == 0
            
            # Verify orchestrator was notified of results
            orchestrator.on_benchmark_complete.assert_called_once_with(results)

    def test_benchmark_with_edge_cases(self, benchmarker):
        """Test benchmark behavior with edge cases."""
        # Test with zero delta
        with patch.object(benchmarker, '_run_benchmark') as mock_benchmark:
            mock_benchmark.side_effect = [
                {'score': 80, 'latency': 0.5, 'throughput': 100},
                {'score': 80, 'latency': 0.5, 'throughput': 100}
            ]
            
            result = benchmarker.benchmark_capability("zero_delta_cap")
            assert result['delta'] == 0
            assert result['improvement'] == 0

        # Test with very small positive delta
        with patch.object(benchmarker, '_run_benchmark') as mock_benchmark:
            mock_benchmark.side_effect = [
                {'score': 80.1, 'latency': 0.5, 'throughput': 100},
                {'score': 80.0, 'latency': 0.5, 'throughput': 100}
            ]
            
            result = benchmarker.benchmark_capability("small_delta_cap")
            assert result['delta'] == 0.1
            assert result['improvement'] > 0

        # Test with capability that doesn't exist
        with pytest.raises(ValueError):
            benchmarker.benchmark_capability("nonexistent_capability")

    def test_registry_state_persistence(self):
        """Test that CapabilityRegistry properly persists state."""
        registry = CapabilityRegistry(storage_path="/tmp/test_registry.json")
        
        # Save some state
        test_state = {
            'cap1': {'enabled': True, 'delta': 5.0, 'last_benchmarked': datetime.now().isoformat()},
            'cap2': {'enabled': False, 'delta': -3.0, 'last_benchmarked': datetime.now().isoformat()}
        }
        registry.save_state(test_state)
        
        # Create new registry instance (simulating restart)
        new_registry = CapabilityRegistry(storage_path="/tmp/test_registry.json")
        
        # Verify state was persisted
        loaded_state = new_registry.load_state()
        assert loaded_state == test_state
        assert loaded_state['cap1']['enabled'] == True
        assert loaded_state['cap2']['enabled'] == False
        assert loaded_state['cap1']['delta'] == 5.0
        
        # Clean up test file
        import os
        os.remove("/tmp/test_registry.json")