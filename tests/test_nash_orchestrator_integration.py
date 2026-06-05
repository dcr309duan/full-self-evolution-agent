import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from core.evolution_orchestrator import EvolutionOrchestrator
from core.mutation_engine import MutationEngine
from core.nash_equilibrium import NashEquilibriumDetector

@pytest.fixture
def mock_modules():
    """Create 3 interdependent mock modules."""
    module_a = MagicMock()
    module_a.name = "module_a"
    module_a.mutate = AsyncMock(return_value={"status": "success", "changes": ["change_a1"]})
    module_a.rollback = AsyncMock()
    module_a.get_dependencies = MagicMock(return_value=["module_b"])
    
    module_b = MagicMock()
    module_b.name = "module_b"
    module_b.mutate = AsyncMock(return_value={"status": "success", "changes": ["change_b1"]})
    module_b.rollback = AsyncMock()
    module_b.get_dependencies = MagicMock(return_value=["module_c"])
    
    module_c = MagicMock()
    module_c.name = "module_c"
    module_c.mutate = AsyncMock(return_value={"status": "success", "changes": ["change_c1"]})
    module_c.rollback = AsyncMock()
    module_c.get_dependencies = MagicMock(return_value=["module_a"])
    
    return [module_a, module_b, module_c]

@pytest.fixture
def mock_mutation_engine():
    """Create a mock mutation engine."""
    engine = MagicMock(spec=MutationEngine)
    engine.apply_mutation = AsyncMock(return_value={"status": "success", "changes": ["mock_change"]})
    engine.rollback_mutation = AsyncMock()
    engine.get_mutation_history = MagicMock(return_value=[])
    return engine

@pytest.fixture
def mock_nash_detector():
    """Create a mock Nash equilibrium detector."""
    detector = MagicMock(spec=NashEquilibriumDetector)
    detector.detect_equilibrium = AsyncMock(return_value={"in_equilibrium": False, "cycles_stuck": 0})
    detector.suggest_coordinated_mutation = AsyncMock(return_value={
        "modules": ["module_a", "module_b"],
        "changes": [{"module": "module_a", "change": "coordinated_a"}, {"module": "module_b", "change": "coordinated_b"}]
    })
    return detector

@pytest.fixture
def orchestrator(mock_modules, mock_mutation_engine, mock_nash_detector):
    """Create an orchestrator with mock dependencies."""
    orchestrator = EvolutionOrchestrator(
        modules=mock_modules,
        mutation_engine=mock_mutation_engine,
        nash_detector=mock_nash_detector
    )
    return orchestrator

@pytest.mark.asyncio
async def test_single_module_mutations_reach_equilibrium(orchestrator, mock_modules):
    """Test that single-module mutations eventually reach equilibrium."""
    # Simulate 5 cycles of single-module mutations
    for cycle in range(5):
        result = await orchestrator.run_single_module_mutation_cycle()
        
        # Verify mutation was attempted
        assert "mutations" in result
        assert len(result["mutations"]) > 0
        
        # Verify mutation results
        for mutation in result["mutations"]:
            assert "module" in mutation
            assert "status" in mutation
            assert mutation["status"] in ["success", "failure"]
    
    # After 5 cycles, check if equilibrium was detected
    equilibrium_status = await orchestrator.nash_detector.detect_equilibrium(
        orchestrator.get_mutation_history()
    )
    assert "in_equilibrium" in equilibrium_status

@pytest.mark.asyncio
async def test_coordinated_mutation_triggers_after_equilibrium(orchestrator, mock_nash_detector):
    """Test that coordinated mutation phase triggers after equilibrium is detected."""
    # Configure mock to detect equilibrium after 3 cycles
    mock_nash_detector.detect_equilibrium = AsyncMock(side_effect=[
        {"in_equilibrium": False, "cycles_stuck": 0},
        {"in_equilibrium": False, "cycles_stuck": 1},
        {"in_equilibrium": True, "cycles_stuck": 3}
    ])
    
    # Run cycles until coordinated mutation triggers
    coordinated_triggered = False
    for cycle in range(5):
        result = await orchestrator.run_evolution_cycle()
        
        if "coordinated_mutation" in result:
            coordinated_triggered = True
            break
    
    assert coordinated_triggered, "Coordinated mutation should have been triggered"
    
    # Verify coordinated mutation was suggested
    mock_nash_detector.suggest_coordinated_mutation.assert_called_once()

@pytest.mark.asyncio
async def test_atomic_application_of_multi_module_changes(orchestrator, mock_modules):
    """Test that multi-module changes are applied atomically."""
    # Prepare coordinated mutation
    coordinated_changes = [
        {"module": mock_modules[0], "change": "coordinated_a"},
        {"module": mock_modules[1], "change": "coordinated_b"}
    ]
    
    # Apply coordinated mutation atomically
    result = await orchestrator.apply_coordinated_mutation(coordinated_changes)
    
    # Verify all mutations were attempted
    for module_change in coordinated_changes:
        module = module_change["module"]
        module.mutate.assert_called_once()
    
    # Verify atomicity: if one fails, all should be rolled back
    mock_modules[0].mutate.side_effect = Exception("Mutation failed")
    
    with pytest.raises(Exception):
        await orchestrator.apply_coordinated_mutation(coordinated_changes)
    
    # Verify rollback was called for all modules
    for module in mock_modules[:2]:  # Only first two modules were part of coordinated change
        module.rollback.assert_called_once()

@pytest.mark.asyncio
async def test_full_orchestration_cycle(orchestrator, mock_nash_detector):
    """Test the full orchestration cycle including equilibrium detection and coordinated mutation."""
    # Configure mock to detect equilibrium after 4 cycles
    mock_nash_detector.detect_equilibrium = AsyncMock(side_effect=[
        {"in_equilibrium": False, "cycles_stuck": 0},
        {"in_equilibrium": False, "cycles_stuck": 1},
        {"in_equilibrium": False, "cycles_stuck": 2},
        {"in_equilibrium": True, "cycles_stuck": 4}
    ])
    
    # Run 5 full cycles
    for cycle in range(5):
        result = await orchestrator.run_evolution_cycle()
        
        # Verify result structure
        assert "cycle_number" in result
        assert "mutations" in result
        assert "equilibrium_status" in result
        
        # Check if coordinated mutation was triggered
        if result["equilibrium_status"]["in_equilibrium"]:
            assert "coordinated_mutation" in result
            assert result["coordinated_mutation"]["status"] in ["success", "failure"]

@pytest.mark.asyncio
async def test_rollback_on_coordinated_mutation_failure(orchestrator, mock_modules):
    """Test that all changes are rolled back if coordinated mutation fails."""
    # Make the second module mutation fail
    mock_modules[1].mutate.side_effect = Exception("Coordinated mutation failed")
    
    coordinated_changes = [
        {"module": mock_modules[0], "change": "change_a"},
        {"module": mock_modules[1], "change": "change_b"},
        {"module": mock_modules[2], "change": "change_c"}
    ]
    
    # Attempt coordinated mutation
    with pytest.raises(Exception, match="Coordinated mutation failed"):
        await orchestrator.apply_coordinated_mutation(coordinated_changes)
    
    # Verify rollback was called for all modules that were mutated
    mock_modules[0].rollback.assert_called_once()
    mock_modules[1].rollback.assert_not_called()  # Failed before mutation
    mock_modules[2].rollback.assert_not_called()  # Never reached due to failure
    
    # Verify mutation was only called for first module
    mock_modules[0].mutate.assert_called_once()
    mock_modules[1].mutate.assert_called_once()
    mock_modules[2].mutate.assert_not_called()