import sys
import os

# Add the parent directory to sys.path to allow imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.nash_detector_and_forcer import NashEquilibriumDetectorAndForcer


def test_equilibrium_detection():
    """Test that equilibrium detection works correctly"""
    detector = NashEquilibriumDetectorAndForcer()
    
    # Initially should not be at Nash equilibrium
    assert detector.is_at_nash() == False, "is_at_nash should return False initially"
    
    # Add stable cycles to reach equilibrium
    for _ in range(3):
        detector.add_stable_cycle()
    
    # Should now be at Nash equilibrium
    assert detector.is_at_nash() == True, "is_at_nash should return True after 3 stable cycles"
    
    # Verify stable modules are detected
    stable_modules = detector.get_stable_modules()
    assert isinstance(stable_modules, list), "get_stable_modules should return a list"
    assert len(stable_modules) > 0, "get_stable_modules should return non-empty list after stable cycles"


def test_multi_module_force_generation():
    """Test that force generation works across multiple modules"""
    detector = NashEquilibriumDetectorAndForcer()
    
    # Add stable cycles to reach equilibrium
    for _ in range(3):
        detector.add_stable_cycle()
    
    # Generate forces for all stable modules
    forces = detector.generate_forces()
    
    # Verify forces are generated correctly
    assert isinstance(forces, dict), "generate_forces should return a dictionary"
    assert len(forces) > 0, "generate_forces should return non-empty dictionary"
    
    # Verify each module has a force value
    for module_name, force_value in forces.items():
        assert isinstance(module_name, str), "Module name should be a string"
        assert isinstance(force_value, float), "Force value should be a float"
        assert force_value > 0, "Force value should be positive"


def test_system_escapes_local_optima():
    """Test that the system can escape local optima"""
    detector = NashEquilibriumDetectorAndForcer()
    
    # Simulate being stuck in a local optimum
    detector.add_stable_cycle()
    detector.add_stable_cycle()
    detector.add_stable_cycle()
    
    # Record initial state
    initial_forces = detector.generate_forces()
    initial_modules = detector.get_stable_modules()
    
    # Apply perturbation to escape local optimum
    detector.apply_perturbation()
    
    # After perturbation, should detect new equilibrium
    assert detector.is_at_nash() == True, "is_at_nash should return True after perturbation"
    
    # Generate new forces after perturbation
    new_forces = detector.generate_forces()
    new_modules = detector.get_stable_modules()
    
    # Verify that forces changed (system escaped local optimum)
    assert new_forces != initial_forces, "Forces should change after escaping local optimum"
    
    # Verify modules may have changed
    assert len(new_modules) > 0, "Should still have stable modules after perturbation"


if __name__ == '__main__':
    test_equilibrium_detection()
    test_multi_module_force_generation()
    test_system_escapes_local_optima()
    print("All tests passed!")