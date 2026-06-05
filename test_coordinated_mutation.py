import pytest
from unittest.mock import Mock, patch, call
import json
import tempfile
import os
from pathlib import Path

# Import the modules under test (adjust imports as needed for your project structure)
from coordinated_mutation.detector import NashEquilibriumDetector
from coordinated_mutation.planner import CoordinatedPlanner
from coordinated_mutation.executor import AtomicExecutor
from coordinated_mutation.recovery import RecoveryManager
from coordinated_mutation.models import MutationPlan, MutationStep, SystemState

# Define tightly coupled module stubs for testing
class ModuleA:
    """Simulates a tightly coupled module that depends on ModuleB."""
    def __init__(self):
        self.state = {"value": 10, "dependency": None}
    
    def set_dependency(self, module_b):
        self.state["dependency"] = module_b.get_state()
    
    def get_state(self):
        return self.state
    
    def mutate(self, new_value):
        old_state = self.state.copy()
        self.state["value"] = new_value
        return old_state
    
    def rollback(self, old_state):
        self.state = old_state

class ModuleB:
    """Simulates a tightly coupled module that ModuleA depends on."""
    def __init__(self):
        self.state = {"threshold": 5, "flag": False}
    
    def get_state(self):
        return self.state
    
    def mutate(self, new_threshold):
        old_state = self.state.copy()
        self.state["threshold"] = new_threshold
        return old_state
    
    def rollback(self, old_state):
        self.state = old_state

class TestCoordinatedMutationPipeline:
    """Integration test for the full coordinated mutation pipeline."""
    
    @pytest.fixture
    def system_setup(self):
        """Set up a system with two tightly coupled modules."""
        module_a = ModuleA()
        module_b = ModuleB()
        module_a.set_dependency(module_b)
        
        # Create a system state representation
        system_state = SystemState(
            modules={"module_a": module_a, "module_b": module_b},
            coupling_matrix={
                ("module_a", "module_b"): 0.9,  # High coupling
                ("module_b", "module_a"): 0.3   # Lower coupling
            }
        )
        return system_state, module_a, module_b
    
    @pytest.fixture
    def detector(self):
        """Create a Nash equilibrium detector with test configuration."""
        return NashEquilibriumDetector(
            convergence_threshold=0.01,
            max_iterations=100
        )
    
    @pytest.fixture
    def planner(self):
        """Create a coordinated planner."""
        return CoordinatedPlanner(
            max_plan_size=5,
            coordination_level="full"
        )
    
    @pytest.fixture
    def executor(self):
        """Create an atomic executor."""
        return AtomicExecutor(
            timeout_seconds=30,
            rollback_on_failure=True
        )
    
    @pytest.fixture
    def recovery_manager(self):
        """Create a recovery manager."""
        return RecoveryManager(
            max_retries=3,
            backoff_factor=2.0
        )
    
    def test_full_pipeline_success(self, system_setup, detector, planner, executor, recovery_manager):
        """Test the full coordinated mutation pipeline with successful execution."""
        system_state, module_a, module_b = system_setup
        
        # Step 1: Simulate Nash equilibrium detection
        equilibrium_result = detector.detect_equilibrium(system_state)
        assert equilibrium_result.is_equilibrium, "System should be in equilibrium initially"
        
        # Step 2: Generate a coordinated mutation plan
        mutation_plan = planner.generate_plan(
            system_state,
            target_state={"module_a": {"value": 20}, "module_b": {"threshold": 10}}
        )
        
        # Verify the plan is multi-module
        assert len(mutation_plan.steps) == 2, "Plan should have steps for both modules"
        assert mutation_plan.is_coordinated, "Plan should be coordinated"
        assert mutation_plan.steps[0].module_id == "module_a"
        assert mutation_plan.steps[1].module_id == "module_b"
        
        # Step 3: Execute the plan atomically
        original_states = {
            "module_a": module_a.get_state().copy(),
            "module_b": module_b.get_state().copy()
        }
        
        execution_result = executor.execute_atomically(
            mutation_plan,
            system_state.modules
        )
        
        # Verify atomic execution
        assert execution_result.success, "Atomic execution should succeed"
        assert module_a.state["value"] == 20, "Module A should be updated"
        assert module_b.state["threshold"] == 10, "Module B should be updated"
        
        # Step 4: Verify system recovery on test failure
        # Simulate a failed test by rolling back
        recovery_result = recovery_manager.rollback(
            system_state.modules,
            original_states
        )
        
        assert recovery_result.success, "Recovery should succeed"
        assert module_a.state == original_states["module_a"], "Module A should be restored"
        assert module_b.state == original_states["module_b"], "Module B should be restored"
    
    def test_pipeline_with_nash_detection_failure(self, system_setup, detector, planner, executor, recovery_manager):
        """Test pipeline behavior when Nash equilibrium detection fails."""
        system_state, module_a, module_b = system_setup
        
        # Simulate a system not in equilibrium
        system_state.coupling_matrix[("module_a", "module_b")] = 0.1  # Low coupling
        
        equilibrium_result = detector.detect_equilibrium(system_state)
        
        if not equilibrium_result.is_equilibrium:
            # System should not proceed with mutation
            with pytest.raises(RuntimeError, match="System not in equilibrium"):
                planner.generate_plan(system_state, {})
    
    def test_pipeline_with_execution_failure_and_recovery(self, system_setup, detector, planner, executor, recovery_manager):
        """Test pipeline behavior when atomic execution fails and recovery is triggered."""
        system_state, module_a, module_b = system_setup
        
        # Step 1: Detect equilibrium
        equilibrium_result = detector.detect_equilibrium(system_state)
        assert equilibrium_result.is_equilibrium
        
        # Step 2: Generate plan
        mutation_plan = planner.generate_plan(
            system_state,
            target_state={"module_a": {"value": 30}, "module_b": {"threshold": 15}}
        )
        
        # Step 3: Simulate a failure during execution
        original_states = {
            "module_a": module_a.get_state().copy(),
            "module_b": module_b.get_state().copy()
        }
        
        # Make module_b fail during mutation
        original_mutate = module_b.mutate
        def failing_mutate(new_threshold):
            raise RuntimeError("Simulated mutation failure")
        module_b.mutate = failing_mutate
        
        execution_result = executor.execute_atomically(
            mutation_plan,
            system_state.modules
        )
        
        # Verify execution failed
        assert not execution_result.success, "Execution should fail"
        
        # Step 4: Verify recovery restores original state
        recovery_result = recovery_manager.rollback(
            system_state.modules,
            original_states
        )
        
        assert recovery_result.success, "Recovery should succeed"
        assert module_a.state == original_states["module_a"], "Module A should be restored"
        assert module_b.state == original_states["module_b"], "Module B should be restored"
        
        # Restore original method
        module_b.mutate = original_mutate
    
    def test_pipeline_with_partial_execution_and_rollback(self, system_setup, detector, planner, executor, recovery_manager):
        """Test pipeline when partial execution occurs and rollback is needed."""
        system_state, module_a, module_b = system_setup
        
        # Step 1: Detect equilibrium
        equilibrium_result = detector.detect_equilibrium(system_state)
        assert equilibrium_result.is_equilibrium
        
        # Step 2: Generate plan with multiple steps
        mutation_plan = planner.generate_plan(
            system_state,
            target_state={
                "module_a": {"value": 40},
                "module_b": {"threshold": 20}
            }
        )
        
        # Step 3: Execute with a failure after first step
        original_states = {
            "module_a": module_a.get_state().copy(),
            "module_b": module_b.get_state().copy()
        }
        
        # Simulate partial execution: module_a succeeds, module_b fails
        module_a.mutate(40)  # This succeeds
        assert module_a.state["value"] == 40, "Module A should be partially updated"
        
        # Now simulate failure and rollback
        recovery_result = recovery_manager.rollback(
            system_state.modules,
            original_states
        )
        
        assert recovery_result.success, "Rollback should succeed after partial execution"
        assert module_a.state == original_states["module_a"], "Module A should be rolled back"
        assert module_b.state == original_states["module_b"], "Module B should remain unchanged"
    
    def test_pipeline_integration_with_mocked_components(self, system_setup):
        """Test pipeline integration using mocked components for isolation."""
        system_state, module_a, module_b = system_setup
        
        # Mock the detector
        mock_detector = Mock(spec=NashEquilibriumDetector)
        mock_detector.detect_equilibrium.return_value = Mock(
            is_equilibrium=True,
            equilibrium_point={"module_a": 10, "module_b": 5}
        )
        
        # Mock the planner
        mock_planner = Mock(spec=CoordinatedPlanner)
        mock_plan = MutationPlan(
            steps=[
                MutationStep(module_id="module_a", action="update", params={"value": 50}),
                MutationStep(module_id="module_b", action="update", params={"threshold": 25})
            ],
            is_coordinated=True
        )
        mock_planner.generate_plan.return_value = mock_plan
        
        # Mock the executor
        mock_executor = Mock(spec=AtomicExecutor)
        mock_executor.execute_atomically.return_value = Mock(
            success=True,
            applied_steps=["module_a", "module_b"]
        )
        
        # Mock the recovery manager
        mock_recovery = Mock(spec=RecoveryManager)
        mock_recovery.rollback.return_value = Mock(success=True)
        
        # Execute the pipeline with mocks
        equilibrium = mock_detector.detect_equilibrium(system_state)
        assert equilibrium.is_equilibrium
        
        plan = mock_planner.generate_plan(system_state, {"module_a": {"value": 50}})
        assert plan.is_coordinated
        assert len(plan.steps) == 2
        
        execution = mock_executor.execute_atomically(plan, system_state.modules)
        assert execution.success
        
        # Verify recovery is not needed since execution succeeded
        mock_recovery.rollback.assert_not_called()
    
    def test_pipeline_state_consistency_after_mutation(self, system_setup, detector, planner, executor, recovery_manager):
        """Test that system state remains consistent after successful mutation."""
        system_state, module_a, module_b = system_setup
        
        # Record initial state
        initial_state_a = module_a.get_state().copy()
        initial_state_b = module_b.get_state().copy()
        
        # Execute full pipeline
        equilibrium = detector.detect_equilibrium(system_state)
        assert equilibrium.is_equilibrium
        
        plan = planner.generate_plan(
            system_state,
            target_state={"module_a": {"value": 60}, "module_b": {"threshold": 30}}
        )
        
        execution = executor.execute_atomically(plan, system_state.modules)
        assert execution.success
        
        # Verify state consistency
        assert module_a.state["value"] == 60, "Module A should have new value"
        assert module_b.state["threshold"] == 30, "Module B should have new threshold"
        assert module_a.state["dependency"] == module_b.get_state(), "Dependency should be consistent"
        
        # Verify coupling relationships are maintained
        assert system_state.coupling_matrix[("module_a", "module_b")] == 0.9
        assert system_state.coupling_matrix[("module_b", "module_a")] == 0.3
    
    def test_pipeline_with_concurrent_mutations(self, system_setup, detector, planner, executor, recovery_manager):
        """Test pipeline behavior when concurrent mutations are attempted."""
        system_state, module_a, module_b = system_setup
        
        # Detect equilibrium
        equilibrium = detector.detect_equilibrium(system_state)
        assert equilibrium.is_equilibrium
        
        # Generate two conflicting plans
        plan1 = planner.generate_plan(
            system_state,
            target_state={"module_a": {"value": 70}}
        )
        
        plan2 = planner.generate_plan(
            system_state,
            target_state={"module_a": {"value": 80}}
        )
        
        # Execute first plan
        original_state_a = module_a.get_state().copy()
        execution1 = executor.execute_atomically(plan1, system_state.modules)
        assert execution1.success
        assert module_a.state["value"] == 70
        
        # Attempt second plan - should detect conflict and rollback
        execution2 = executor.execute_atomically(plan2, system_state.modules)
        assert not execution2.success, "Concurrent mutation should be rejected"
        
        # Verify system rolled back to state before second mutation
        recovery_manager.rollback(system_state.modules, {"module_a": original_state_a})
        assert module_a.state["value"] == 10, "Should rollback to original state"

# Helper functions for test setup
def create_test_config():
    """Create a test configuration for the pipeline."""
    return {
        "detector": {
            "convergence_threshold": 0.01,
            "max_iterations": 100
        },
        "planner": {
            "max_plan_size": 5,
            "coordination_level": "full"
        },
        "executor": {
            "timeout_seconds": 30,
            "rollback_on_failure": True
        },
        "recovery": {
            "max_retries": 3,
            "backoff_factor": 2.0
        }
    }

def test_pipeline_with_config_file():
    """Test pipeline initialization from configuration file."""
    config = create_test_config()
    
    # Create temporary config file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(config, f)
        config_path = f.name
    
    try:
        # Initialize pipeline components from config
        detector = NashEquilibriumDetector(**config["detector"])
        planner = CoordinatedPlanner(**config["planner"])
        executor = AtomicExecutor(**config["executor"])
        recovery = RecoveryManager(**config["recovery"])
        
        # Verify components are properly initialized
        assert detector.convergence_threshold == 0.01
        assert planner.max_plan_size == 5
        assert executor.timeout_seconds == 30
        assert recovery.max_retries == 3
    finally:
        os.unlink(config_path)

if __name__ == "__main__":
    pytest.main([__file__, "-v"])