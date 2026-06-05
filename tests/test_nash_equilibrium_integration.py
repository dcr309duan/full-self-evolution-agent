import pytest
from unittest.mock import MagicMock, patch
from core.nash_detector_and_forcer import NashDetector, NashEquilibrium, CoordinatedMutation
from core.multi_module_forcer import MultiModuleForcer
from core.multi_module_applier import MultiModuleApplier

@pytest.fixture
def mock_system():
    """Create a mock system with 3 modules in Nash equilibrium.
    
    Module A: can be changed to A' but only if B and C also change
    Module B: can be changed to B' but only if A and C also change
    Module C: can be changed to C' but only if A and B also change
    """
    class MockModule:
        def __init__(self, name, current_state, possible_states):
            self.name = name
            self.current_state = current_state
            self.possible_states = possible_states
            
    modules = [
        MockModule("A", "state_a", ["state_a_prime", "state_a_alt"]),
        MockModule("B", "state_b", ["state_b_prime", "state_b_alt"]),
        MockModule("C", "state_c", ["state_c_prime", "state_c_alt"])
    ]
    
    # Define dependencies: each module requires the other two to change simultaneously
    dependencies = {
        "A": ["B", "C"],
        "B": ["A", "C"],
        "C": ["A", "B"]
    }
    
    # Define coordinated mutations that succeed
    coordinated_mutations = {
        ("A_prime", "B_prime", "C_prime"): True,
        ("A_alt", "B_alt", "C_alt"): True
    }
    
    return {
        "modules": modules,
        "dependencies": dependencies,
        "coordinated_mutations": coordinated_mutations
    }

@pytest.fixture
def detector():
    return NashDetector()

@pytest.fixture
def forcer():
    return MultiModuleForcer()

@pytest.fixture
def applier():
    return MultiModuleApplier()

def test_nash_equilibrium_detection(mock_system, detector):
    """Test that the detector correctly identifies the Nash equilibrium."""
    # Test single changes - all should fail
    for module in mock_system["modules"]:
        for new_state in module.possible_states:
            is_improvement = detector.evaluate_single_change(
                module.name, module.current_state, new_state, mock_system
            )
            assert not is_improvement, f"Single change {module.name} -> {new_state} should not be an improvement"
    
    # Test coordinated changes - should succeed
    equilibrium = detector.find_equilibrium(mock_system)
    assert equilibrium is not None, "Should find a Nash equilibrium"
    assert len(equilibrium.coordinated_mutations) > 0, "Should have coordinated mutations"

def test_coordinated_mutation_generation(mock_system, forcer):
    """Test that the orchestrator generates multi-module mutations."""
    mutations = forcer.generate_coordinated_mutations(mock_system)
    
    assert len(mutations) > 0, "Should generate at least one coordinated mutation"
    
    # Verify each mutation involves multiple modules
    for mutation in mutations:
        assert len(mutation.modules) >= 2, f"Mutation should involve at least 2 modules, got {len(mutation.modules)}"
        assert mutation.is_coordinated, "Mutation should be marked as coordinated"
        
        # Verify the mutation is valid
        assert forcer.validate_mutation(mutation, mock_system), "Mutation should be valid"

def test_atomic_application_and_rollback(mock_system, applier):
    """Test that the mutation engine applies and rolls back atomically."""
    # Create a test mutation
    mutation = CoordinatedMutation(
        modules=["A", "B", "C"],
        new_states=["state_a_prime", "state_b_prime", "state_c_prime"],
        is_coordinated=True
    )
    
    # Save original states
    original_states = {
        module.name: module.current_state 
        for module in mock_system["modules"]
    }
    
    # Apply mutation
    success = applier.apply_mutation(mutation, mock_system)
    assert success, "Mutation should apply successfully"
    
    # Verify all modules changed
    for module in mock_system["modules"]:
        if module.name == "A":
            assert module.current_state == "state_a_prime"
        elif module.name == "B":
            assert module.current_state == "state_b_prime"
        elif module.name == "C":
            assert module.current_state == "state_c_prime"
    
    # Rollback mutation
    rollback_success = applier.rollback_mutation(mutation, mock_system)
    assert rollback_success, "Rollback should succeed"
    
    # Verify all modules returned to original states
    for module in mock_system["modules"]:
        assert module.current_state == original_states[module.name], \
            f"Module {module.name} should return to original state"

def test_atomic_rollback_on_failure(mock_system, applier):
    """Test that if one module change fails, all changes are rolled back."""
    # Create a mutation where one change will fail
    mutation = CoordinatedMutation(
        modules=["A", "B", "C"],
        new_states=["state_a_prime", "invalid_state_b", "state_c_prime"],
        is_coordinated=True
    )
    
    # Save original states
    original_states = {
        module.name: module.current_state 
        for module in mock_system["modules"]
    }
    
    # Attempt to apply mutation (should fail)
    success = applier.apply_mutation(mutation, mock_system)
    assert not success, "Mutation with invalid state should fail"
    
    # Verify all modules returned to original states
    for module in mock_system["modules"]:
        assert module.current_state == original_states[module.name], \
            f"Module {module.name} should be rolled back to original state"

def test_full_integration_flow(mock_system, detector, forcer, applier):
    """Test the complete flow: detect -> generate -> apply -> rollback."""
    # Step 1: Detect equilibrium
    equilibrium = detector.find_equilibrium(mock_system)
    assert equilibrium is not None, "Should detect equilibrium"
    
    # Step 2: Generate coordinated mutations
    mutations = forcer.generate_coordinated_mutations(mock_system)
    assert len(mutations) > 0, "Should generate mutations"
    
    # Step 3: Apply the first valid mutation
    first_mutation = mutations[0]
    original_states = {
        module.name: module.current_state 
        for module in mock_system["modules"]
    }
    
    apply_success = applier.apply_mutation(first_mutation, mock_system)
    assert apply_success, "Should apply mutation successfully"
    
    # Verify state changed
    states_changed = any(
        module.current_state != original_states[module.name]
        for module in mock_system["modules"]
    )
    assert states_changed, "At least one module state should have changed"
    
    # Step 4: Rollback
    rollback_success = applier.rollback_mutation(first_mutation, mock_system)
    assert rollback_success, "Should rollback successfully"
    
    # Verify complete rollback
    for module in mock_system["modules"]:
        assert module.current_state == original_states[module.name], \
            f"Module {module.name} should return to original state after rollback"

def test_partial_mutation_rollback(mock_system, applier):
    """Test that partial mutations are properly rolled back."""
    # Create a mutation that will partially fail
    mutation = CoordinatedMutation(
        modules=["A", "B", "C"],
        new_states=["state_a_prime", "state_b_prime", "state_c_prime"],
        is_coordinated=True
    )
    
    # Mock the apply method to fail on the third module
    original_apply = applier._apply_single_module
    call_count = [0]
    
    def mock_apply(module_name, new_state, system):
        call_count[0] += 1
        if call_count[0] == 3:  # Fail on third module
            return False
        return original_apply(module_name, new_state, system)
    
    applier._apply_single_module = mock_apply
    
    try:
        # Save original states
        original_states = {
            module.name: module.current_state 
            for module in mock_system["modules"]
        }
        
        # Attempt to apply mutation
        success = applier.apply_mutation(mutation, mock_system)
        assert not success, "Mutation should fail"
        
        # Verify all modules returned to original states
        for module in mock_system["modules"]:
            assert module.current_state == original_states[module.name], \
                f"Module {module.name} should be rolled back"
    finally:
        applier._apply_single_module = original_apply