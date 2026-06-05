import pytest
import sys
import os
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.multi_module_forcer import MultiModuleForcer
from core.nash_detector import NashEquilibriumDetector


@pytest.fixture
def mock_modules_in_equilibrium():
    """
    Creates 3 mock modules that are in a Nash equilibrium state.
    Module A: baseline performance 50
    Module B: baseline performance 60
    Module C: baseline performance 70
    Each module's performance decreases if changed individually, but a coordinated change improves all.
    """
    class MockModuleA:
        def __init__(self):
            self.name = "ModuleA"
            self.performance = 50
            self.state = "baseline_a"
        
        def evaluate(self):
            return self.performance
        
        def mutate(self, change_type="single"):
            if change_type == "single":
                # Single change decreases performance
                return MockModuleA_with_change(self.performance - 10)
            elif change_type == "coordinated":
                # Coordinated change improves performance
                return MockModuleA_with_change(self.performance + 15)
            return self
        
        def __repr__(self):
            return f"ModuleA(perf={self.performance})"
    
    class MockModuleA_with_change:
        def __init__(self, perf):
            self.name = "ModuleA"
            self.performance = perf
            self.state = "changed_a"
        
        def evaluate(self):
            return self.performance
        
        def mutate(self, change_type="single"):
            return self
        
        def __repr__(self):
            return f"ModuleA(perf={self.performance})"
    
    class MockModuleB:
        def __init__(self):
            self.name = "ModuleB"
            self.performance = 60
            self.state = "baseline_b"
        
        def evaluate(self):
            return self.performance
        
        def mutate(self, change_type="single"):
            if change_type == "single":
                return MockModuleB_with_change(self.performance - 5)
            elif change_type == "coordinated":
                return MockModuleB_with_change(self.performance + 20)
            return self
        
        def __repr__(self):
            return f"ModuleB(perf={self.performance})"
    
    class MockModuleB_with_change:
        def __init__(self, perf):
            self.name = "ModuleB"
            self.performance = perf
            self.state = "changed_b"
        
        def evaluate(self):
            return self.performance
        
        def mutate(self, change_type="single"):
            return self
        
        def __repr__(self):
            return f"ModuleB(perf={self.performance})"
    
    class MockModuleC:
        def __init__(self):
            self.name = "ModuleC"
            self.performance = 70
            self.state = "baseline_c"
        
        def evaluate(self):
            return self.performance
        
        def mutate(self, change_type="single"):
            if change_type == "single":
                return MockModuleC_with_change(self.performance - 8)
            elif change_type == "coordinated":
                return MockModuleC_with_change(self.performance + 25)
            return self
        
        def __repr__(self):
            return f"ModuleC(perf={self.performance})"
    
    class MockModuleC_with_change:
        def __init__(self, perf):
            self.name = "ModuleC"
            self.performance = perf
            self.state = "changed_c"
        
        def evaluate(self):
            return self.performance
        
        def mutate(self, change_type="single"):
            return self
        
        def __repr__(self):
            return f"ModuleC(perf={self.performance})"
    
    return [MockModuleA(), MockModuleB(), MockModuleC()]


@pytest.fixture
def nash_detector():
    """Create a Nash equilibrium detector instance."""
    return NashEquilibriumDetector()


@pytest.fixture
def multi_module_forcer():
    """Create a multi-module forcer instance."""
    return MultiModuleForcer()


def test_initial_equilibrium_state(mock_modules_in_equilibrium, nash_detector):
    """Test that the mock system is initially in Nash equilibrium."""
    # Verify single-module changes don't improve performance
    for module in mock_modules_in_equilibrium:
        original_perf = module.evaluate()
        changed_module = module.mutate("single")
        changed_perf = changed_module.evaluate()
        assert changed_perf < original_perf, f"Single change to {module.name} should decrease performance"
    
    # Use nash_detector to confirm equilibrium
    is_equilibrium = nash_detector.check_equilibrium(mock_modules_in_equilibrium)
    assert is_equilibrium, "System should be in Nash equilibrium"


def test_single_module_changes_dont_improve(mock_modules_in_equilibrium):
    """Test that no single module can improve its performance by changing alone."""
    for module in mock_modules_in_equilibrium:
        original_perf = module.evaluate()
        changed_module = module.mutate("single")
        changed_perf = changed_module.evaluate()
        improvement = changed_perf - original_perf
        assert improvement < 0, f"Single change to {module.name} should not improve performance (got {improvement})"


def test_coordinated_change_improves_system(mock_modules_in_equilibrium, multi_module_forcer):
    """Test that multi_module_forcer finds a coordinated change that improves the system."""
    # Get the coordinated change suggestion
    coordinated_changes = multi_module_forcer.find_coordinated_change(mock_modules_in_equilibrium)
    
    assert coordinated_changes is not None, "Should find a coordinated change"
    assert len(coordinated_changes) == 3, "Should suggest changes for all 3 modules"
    
    # Apply the coordinated changes
    improved_modules = []
    for module, change in zip(mock_modules_in_equilibrium, coordinated_changes):
        improved_module = module.mutate("coordinated")
        improved_modules.append(improved_module)
    
    # Verify total system performance improves
    original_total = sum(m.evaluate() for m in mock_modules_in_equilibrium)
    improved_total = sum(m.evaluate() for m in improved_modules)
    assert improved_total > original_total, "Coordinated change should improve total system performance"


def test_system_escapes_equilibrium(mock_modules_in_equilibrium, multi_module_forcer, nash_detector):
    """Test that after applying coordinated changes, the system escapes Nash equilibrium."""
    # Apply coordinated changes
    coordinated_changes = multi_module_forcer.find_coordinated_change(mock_modules_in_equilibrium)
    improved_modules = []
    for module, change in zip(mock_modules_in_equilibrium, coordinated_changes):
        improved_module = module.mutate("coordinated")
        improved_modules.append(improved_module)
    
    # Verify the new system is no longer in equilibrium
    is_equilibrium = nash_detector.check_equilibrium(improved_modules)
    assert not is_equilibrium, "System should escape Nash equilibrium after coordinated change"


def test_full_integration_flow(mock_modules_in_equilibrium, multi_module_forcer, nash_detector):
    """Complete integration test: equilibrium -> coordinated change -> escape equilibrium."""
    # Step 1: Verify initial equilibrium
    assert nash_detector.check_equilibrium(mock_modules_in_equilibrium), "Initial state should be equilibrium"
    
    # Step 2: Find coordinated change
    coordinated_changes = multi_module_forcer.find_coordinated_change(mock_modules_in_equilibrium)
    assert coordinated_changes is not None, "Should find coordinated change"
    
    # Step 3: Apply coordinated changes
    improved_modules = []
    for module, change in zip(mock_modules_in_equilibrium, coordinated_changes):
        improved_module = module.mutate("coordinated")
        improved_modules.append(improved_module)
    
    # Step 4: Verify performance improvement
    original_total = sum(m.evaluate() for m in mock_modules_in_equilibrium)
    improved_total = sum(m.evaluate() for m in improved_modules)
    assert improved_total > original_total, "Total performance should improve"
    
    # Step 5: Verify escape from equilibrium
    assert not nash_detector.check_equilibrium(improved_modules), "System should escape equilibrium"
    
    # Step 6: Verify individual improvements
    for original, improved in zip(mock_modules_in_equilibrium, improved_modules):
        assert improved.evaluate() > original.evaluate(), f"{improved.name} should improve individually"


def test_no_false_positive_equilibrium(mock_modules_in_equilibrium, nash_detector):
    """Test that the equilibrium detection doesn't produce false positives."""
    # Modify one module to break equilibrium
    modified_modules = list(mock_modules_in_equilibrium)
    modified_modules[0] = modified_modules[0].mutate("coordinated")
    
    # Verify it's no longer equilibrium
    is_equilibrium = nash_detector.check_equilibrium(modified_modules)
    assert not is_equilibrium, "System with one improved module should not be in equilibrium"


def test_multi_module_forcer_returns_valid_changes(mock_modules_in_equilibrium, multi_module_forcer):
    """Test that multi_module_forcer returns valid change suggestions."""
    coordinated_changes = multi_module_forcer.find_coordinated_change(mock_modules_in_equilibrium)
    
    assert coordinated_changes is not None, "Should return changes"
    assert isinstance(coordinated_changes, list), "Should return a list"
    assert len(coordinated_changes) == 3, "Should return 3 changes"
    
    # Verify each change is a valid mutation instruction
    for i, change in enumerate(coordinated_changes):
        assert change is not None, f"Change for module {i} should not be None"
        assert isinstance(change, dict) or isinstance(change, str), f"Change for module {i} should be a dict or string"


def test_nash_detector_and_forcer_integration(mock_modules_in_equilibrium, nash_detector, multi_module_forcer):
    """
    Integration test that tests nash_detector + multi_module_forcer together.
    Test: (1) simulate a system at equilibrium, (2) verify the forcer can detect it via the detector,
    (3) verify it generates multi-module change proposals, (4) verify no single-module improvement exists
    but multi-module improvements do.
    """
    # (1) Simulate a system at equilibrium - verify with detector
    assert nash_detector.check_equilibrium(mock_modules_in_equilibrium), "System should be in equilibrium"
    
    # (2) Verify the forcer can detect it via the detector
    # The forcer should use the detector internally to check equilibrium
    is_equilibrium = multi_module_forcer.detect_equilibrium(mock_modules_in_equilibrium)
    assert is_equilibrium, "Forcer should detect equilibrium via detector"
    
    # (3) Verify it generates multi-module change proposals
    coordinated_changes = multi_module_forcer.find_coordinated_change(mock_modules_in_equilibrium)
    assert coordinated_changes is not None, "Forcer should generate multi-module change proposals"
    assert len(coordinated_changes) == 3, "Should generate proposals for all 3 modules"
    
    # (4) Verify no single-module improvement exists
    for module in mock_modules_in_equilibrium:
        original_perf = module.evaluate()
        changed_module = module.mutate("single")
        changed_perf = changed_module.evaluate()
        assert changed_perf < original_perf, f"No single-module improvement for {module.name}"
    
    # Verify multi-module improvements do exist
    improved_modules = []
    for module, change in zip(mock_modules_in_equilibrium, coordinated_changes):
        improved_module = module.mutate("coordinated")
        improved_modules.append(improved_module)
    
    original_total = sum(m.evaluate() for m in mock_modules_in_equilibrium)
    improved_total = sum(m.evaluate() for m in improved_modules)
    assert improved_total > original_total, "Multi-module improvement should exist"
    
    # Verify each module individually improves with coordinated change
    for original, improved in zip(mock_modules_in_equilibrium, improved_modules):
        assert improved.evaluate() > original.evaluate(), f"{original.name} should improve with coordinated change"
    
    # Verify the forcer correctly identifies that multi-module changes are needed
    needs_multi_module = multi_module_forcer.needs_multi_module_change(mock_modules_in_equilibrium)
    assert needs_multi_module, "Forcer should identify that multi-module changes are needed"


def test_force_multi_mutation_returns_valid_plan(mock_modules_in_equilibrium, multi_module_forcer):
    """
    Integration test that simulates a Nash equilibrium state and calls force_multi_mutation()
    to verify it returns a valid plan.
    """
    # Simulate a Nash equilibrium state using the mock modules
    # The mock_modules_in_equilibrium fixture already provides modules in equilibrium
    
    # Call force_multi_mutation() to get a plan for breaking the equilibrium
    plan = multi_module_forcer.force_multi_mutation(mock_modules_in_equilibrium)
    
    # Verify the plan is valid
    assert plan is not None, "force_multi_mutation() should return a valid plan"
    assert isinstance(plan, dict), "The plan should be a dictionary"
    
    # Check that the plan contains expected keys
    assert "coordinated_changes" in plan, "Plan should contain 'coordinated_changes'"
    assert "expected_improvement" in plan, "Plan should contain 'expected_improvement'"
    assert "new_equilibrium_status" in plan, "Plan should contain 'new_equilibrium_status'"
    
    # Verify coordinated_changes is a list with 3 entries
    coordinated_changes = plan["coordinated_changes"]
    assert isinstance(coordinated_changes, list), "coordinated_changes should be a list"
    assert len(coordinated_changes) == 3, "coordinated_changes should have 3 entries"
    
    # Verify expected_improvement is positive
    expected_improvement = plan["expected_improvement"]
    assert isinstance(expected_improvement, (int, float)), "expected_improvement should be numeric"
    assert expected_improvement > 0, "expected_improvement should be positive"
    
    # Verify new_equilibrium_status indicates the system will no longer be in equilibrium
    new_equilibrium_status = plan["new_equilibrium_status"]
    assert isinstance(new_equilibrium_status, bool), "new_equilibrium_status should be a boolean"
    assert not new_equilibrium_status, "new_equilibrium_status should be False (system escapes equilibrium)"
    
    # Apply the plan and verify it works
    improved_modules = []
    for module, change in zip(mock_modules_in_equilibrium, coordinated_changes):
        improved_module = module.mutate("coordinated")
        improved_modules.append(improved_module)
    
    # Verify total performance improves as expected
    original_total = sum(m.evaluate() for m in mock_modules_in_equilibrium)
    improved_total = sum(m.evaluate() for m in improved_modules)
    actual_improvement = improved_total - original_total
    assert actual_improvement > 0, "Actual improvement should be positive"
    assert actual_improvement == expected_improvement, f"Actual improvement ({actual_improvement}) should match expected ({expected_improvement})"