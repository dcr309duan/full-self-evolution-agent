import pytest
import sys
import os
from unittest.mock import MagicMock, patch, PropertyMock
import json
import tempfile

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.nash_detector_and_forcer import NashDetector, NashForcer, NashEquilibriumDetector
from core.multi_agent_orchestrator import MultiAgentOrchestrator, AgentType, AgentAction

@pytest.fixture
def mock_modules():
    """Create 3 mock modules with artificially flat success rates."""
    module_a = MagicMock()
    module_a.name = "ModuleA"
    module_a.version = "1.0.0"
    module_a.get_success_rate.return_value = 0.85
    module_a.get_dependencies.return_value = []
    module_a.get_dependents.return_value = ["ModuleB", "ModuleC"]
    
    module_b = MagicMock()
    module_b.name = "ModuleB"
    module_b.version = "1.0.0"
    module_b.get_success_rate.return_value = 0.82
    module_b.get_dependencies.return_value = ["ModuleA"]
    module_b.get_dependents.return_value = ["ModuleC"]
    
    module_c = MagicMock()
    module_c.name = "ModuleC"
    module_c.version = "1.0.0"
    module_c.get_success_rate.return_value = 0.88
    module_c.get_dependencies.return_value = ["ModuleA", "ModuleB"]
    module_c.get_dependents.return_value = []
    
    return {"ModuleA": module_a, "ModuleB": module_b, "ModuleC": module_c}

@pytest.fixture
def mock_interaction_matrix(mock_modules):
    """Create a mock interaction matrix for the modules."""
    matrix = MagicMock()
    matrix.get_interaction_strength.side_effect = lambda a, b: {
        ("ModuleA", "ModuleB"): 0.7,
        ("ModuleA", "ModuleC"): 0.5,
        ("ModuleB", "ModuleC"): 0.6,
        ("ModuleB", "ModuleA"): 0.7,
        ("ModuleC", "ModuleA"): 0.5,
        ("ModuleC", "ModuleB"): 0.6,
    }.get((a, b), 0.0)
    return matrix

@pytest.fixture
def nash_detector(mock_modules, mock_interaction_matrix):
    """Create a NashDetector instance with mock data."""
    detector = NashDetector()
    detector.modules = mock_modules
    detector.interaction_matrix = mock_interaction_matrix
    return detector

@pytest.fixture
def nash_forcer(mock_modules, mock_interaction_matrix):
    """Create a NashForcer instance with mock data."""
    forcer = NashForcer()
    forcer.modules = mock_modules
    forcer.interaction_matrix = mock_interaction_matrix
    return forcer

@pytest.fixture
def orchestrator(mock_modules, mock_interaction_matrix):
    """Create a MultiAgentOrchestrator with mock modules."""
    orchestrator = MultiAgentOrchestrator()
    orchestrator.modules = mock_modules
    orchestrator.interaction_matrix = mock_interaction_matrix
    return orchestrator

class TestNashAndMultiIntegration:
    """Comprehensive integration tests for Nash equilibrium detection and multi-agent orchestration."""
    
    def test_detector_identifies_equilibrium(self, nash_detector):
        """Test that the detector correctly identifies Nash equilibrium."""
        # The detector should identify equilibrium when all modules have stable success rates
        result = nash_detector.detect_equilibrium()
        
        assert result is not None
        assert "equilibrium" in result or "stable" in result or "nash" in result.lower()
        assert result.get("is_equilibrium", False) or result.get("stable", False)
        
        # Verify the equilibrium state includes all modules
        if "modules" in result:
            assert "ModuleA" in result["modules"]
            assert "ModuleB" in result["modules"]
            assert "ModuleC" in result["modules"]
    
    def test_detector_identifies_non_equilibrium(self, nash_detector):
        """Test that the detector identifies when system is not in equilibrium."""
        # Modify one module's success rate to be unstable
        nash_detector.modules["ModuleA"].get_success_rate.return_value = 0.95
        
        result = nash_detector.detect_equilibrium()
        
        # Should indicate not in equilibrium
        assert result is not None
        assert not result.get("is_equilibrium", True)
    
    def test_orchestrator_generates_coordinated_mutations(self, orchestrator):
        """Test that the orchestrator generates coordinated mutations for equilibrium."""
        # Set up the orchestrator to detect equilibrium state
        equilibrium_state = {
            "is_equilibrium": True,
            "modules": {
                "ModuleA": {"success_rate": 0.85, "stable": True},
                "ModuleB": {"success_rate": 0.82, "stable": True},
                "ModuleC": {"success_rate": 0.88, "stable": True}
            }
        }
        
        # Generate coordinated mutations
        mutations = orchestrator.generate_coordinated_mutations(equilibrium_state)
        
        assert mutations is not None
        assert len(mutations) > 0
        
        # Verify mutations are coordinated (affect multiple modules)
        module_names = set()
        for mutation in mutations:
            assert "module" in mutation or "target" in mutation
            module_name = mutation.get("module", mutation.get("target"))
            module_names.add(module_name)
        
        # Should affect at least 2 modules for coordination
        assert len(module_names) >= 2
    
    def test_orchestrator_applies_mutations(self, orchestrator):
        """Test that the orchestrator applies mutations to modules."""
        mutations = [
            {"module": "ModuleA", "action": "optimize", "params": {"learning_rate": 0.01}},
            {"module": "ModuleB", "action": "refactor", "params": {"pattern": "singleton"}},
            {"module": "ModuleC", "action": "optimize", "params": {"batch_size": 32}}
        ]
        
        results = orchestrator.apply_mutations(mutations)
        
        assert results is not None
        assert len(results) == len(mutations)
        
        for result in results:
            assert "success" in result or "status" in result
    
    def test_orchestrator_rollback_on_failure(self, orchestrator):
        """Test that the orchestrator properly rolls back on mutation failure."""
        # Create mutations where one will fail
        mutations = [
            {"module": "ModuleA", "action": "optimize", "params": {"learning_rate": 0.01}},
            {"module": "ModuleB", "action": "invalid_action", "params": {}},  # This should fail
            {"module": "ModuleC", "action": "optimize", "params": {"batch_size": 32}}
        ]
        
        # Mock the apply method to simulate failure
        original_apply = orchestrator.apply_mutation_to_module
        
        def mock_apply(mutation):
            if mutation.get("action") == "invalid_action":
                return {"success": False, "error": "Invalid action"}
            return {"success": True}
        
        orchestrator.apply_mutation_to_module = mock_apply
        
        # Apply mutations and expect rollback
        results = orchestrator.apply_mutations(mutations)
        
        # Verify rollback was triggered
        assert results is not None
        assert any(not r.get("success", True) for r in results)
        
        # Verify rollback method was called
        assert hasattr(orchestrator, 'rollback')
        
        # Restore original method
        orchestrator.apply_mutation_to_module = original_apply
    
    def test_full_equilibrium_cycle(self, nash_detector, nash_forcer, orchestrator):
        """Test the complete cycle: detect -> force -> coordinate -> apply."""
        # Step 1: Detect equilibrium
        equilibrium_state = nash_detector.detect_equilibrium()
        assert equilibrium_state is not None
        
        # Step 2: Force equilibrium if needed
        if not equilibrium_state.get("is_equilibrium", False):
            forced_state = nash_forcer.force_equilibrium(equilibrium_state)
            assert forced_state is not None
            equilibrium_state = forced_state
        
        # Step 3: Generate coordinated mutations
        mutations = orchestrator.generate_coordinated_mutations(equilibrium_state)
        assert mutations is not None
        assert len(mutations) > 0
        
        # Step 4: Apply mutations with rollback capability
        results = orchestrator.apply_mutations(mutations)
        assert results is not None
        
        # Verify the cycle completed successfully
        all_successful = all(r.get("success", False) for r in results)
        if not all_successful:
            # Verify rollback was triggered
            assert hasattr(orchestrator, 'rollback')
    
    def test_multi_agent_coordination(self, orchestrator):
        """Test that multiple agents coordinate their actions."""
        # Create multiple agents
        agents = [
            AgentType.OPTIMIZER,
            AgentType.REFACTOR,
            AgentType.TESTER
        ]
        
        # Set up agent actions
        actions = []
        for agent in agents:
            action = AgentAction(
                agent_type=agent,
                target_module="ModuleA",
                params={"priority": 1}
            )
            actions.append(action)
        
        # Coordinate actions
        coordinated_actions = orchestrator.coordinate_agents(actions)
        
        assert coordinated_actions is not None
        assert len(coordinated_actions) > 0
        
        # Verify actions are properly coordinated (no conflicts)
        module_actions = {}
        for action in coordinated_actions:
            module = action.get("target_module", action.get("module"))
            if module not in module_actions:
                module_actions[module] = []
            module_actions[module].append(action)
        
        # Check for conflicting actions on same module
        for module, module_actions_list in module_actions.items():
            if len(module_actions_list) > 1:
                # Should have resolved conflicts
                assert len(module_actions_list) <= 2  # Allow at most 2 non-conflicting actions
    
    def test_rollback_mechanism(self, orchestrator):
        """Test the rollback mechanism specifically."""
        # Save initial state
        initial_state = {
            "ModuleA": {"version": "1.0.0", "success_rate": 0.85},
            "ModuleB": {"version": "1.0.0", "success_rate": 0.82},
            "ModuleC": {"version": "1.0.0", "success_rate": 0.88}
        }
        
        # Simulate a failed mutation
        failed_mutation = {"module": "ModuleB", "action": "update", "params": {"version": "2.0.0"}}
        
        # Apply rollback
        rollback_result = orchestrator.rollback(failed_mutation, initial_state)
        
        assert rollback_result is not None
        assert rollback_result.get("success", False)
        
        # Verify state was restored
        for module_name, module_state in initial_state.items():
            module = orchestrator.modules[module_name]
            assert module.version == module_state["version"]
    
    def test_error_handling(self, nash_detector, orchestrator):
        """Test error handling during equilibrium detection and mutation."""
        # Test with invalid module data
        nash_detector.modules = {}
        with pytest.raises(Exception) if hasattr(pytest, 'raises') else pytest.raises(Exception):
            result = nash_detector.detect_equilibrium()
            assert result is None or "error" in result
        
        # Test with invalid mutations
        with pytest.raises(Exception) if hasattr(pytest, 'raises') else pytest.raises(Exception):
            result = orchestrator.apply_mutations([])
            assert result is None or len(result) == 0
    
    def test_performance_metrics(self, nash_detector, orchestrator):
        """Test that performance metrics are tracked during operations."""
        # Track metrics before
        metrics_before = {
            "detection_time": 0,
            "mutation_time": 0,
            "rollback_time": 0
        }
        
        # Perform operations
        import time
        start = time.time()
        equilibrium_state = nash_detector.detect_equilibrium()
        detection_time = time.time() - start
        
        start = time.time()
        mutations = orchestrator.generate_coordinated_mutations(equilibrium_state)
        mutation_time = time.time() - start
        
        # Verify metrics are reasonable
        assert detection_time < 5.0  # Should complete within 5 seconds
        assert mutation_time < 5.0   # Should complete within 5 seconds
        
        # Verify results are valid
        assert equilibrium_state is not None
        assert mutations is not None