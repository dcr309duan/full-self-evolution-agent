import pytest
from conflict_detector import ConflictDetector, ConflictLevel

class TestConflictDetector:
    """Test suite for the ConflictDetector class."""

    @pytest.fixture
    def detector(self):
        """Fixture to create a fresh ConflictDetector instance for each test."""
        return ConflictDetector()

    def test_overlapping_function_definitions(self, detector):
        """Test detection of overlapping function definitions."""
        # Define two functions with the same name but different implementations
        detector.add_function("calculate_total", ["price", "tax"], "return price * (1 + tax)")
        detector.add_function("calculate_total", ["price", "tax", "discount"], "return price * (1 + tax) * (1 - discount)")
        
        conflicts = detector.detect_conflicts()
        
        # Should detect at least one conflict for the overlapping function
        assert len(conflicts) > 0
        assert any(
            conflict.conflict_type == "overlapping_function" and 
            conflict.name == "calculate_total"
            for conflict in conflicts
        )
        assert any(
            conflict.level == ConflictLevel.HIGH
            for conflict in conflicts
        )

    def test_shared_global_variable_conflicts(self, detector):
        """Test detection of conflicts from shared global variables."""
        # Two functions modifying the same global variable
        detector.add_global_variable("counter", initial_value=0)
        detector.add_function("increment", [], "global counter; counter += 1")
        detector.add_function("decrement", [], "global counter; counter -= 1")
        detector.add_global_variable_modification("increment", "counter", "write")
        detector.add_global_variable_modification("decrement", "counter", "write")
        
        conflicts = detector.detect_conflicts()
        
        # Should detect conflict for shared global variable
        assert len(conflicts) > 0
        assert any(
            conflict.conflict_type == "shared_global_variable" and
            conflict.name == "counter"
            for conflict in conflicts
        )
        assert any(
            conflict.level == ConflictLevel.MEDIUM
            for conflict in conflicts
        )

    def test_incompatible_interface_changes(self, detector):
        """Test detection of incompatible interface changes."""
        # Define a function and then change its signature
        detector.add_function("process_data", ["data", "config"], "return data * config")
        detector.add_function("process_data", ["data"], "return data * 2")  # Removed parameter
        
        conflicts = detector.detect_conflicts()
        
        # Should detect interface incompatibility
        assert len(conflicts) > 0
        assert any(
            conflict.conflict_type == "incompatible_interface" and
            conflict.name == "process_data"
            for conflict in conflicts
        )
        assert any(
            conflict.level == ConflictLevel.HIGH
            for conflict in conflicts
        )

    def test_no_conflict_scenario(self, detector):
        """Test that no conflicts are detected when there are none."""
        # Define completely independent functions and variables
        detector.add_function("calculate_area", ["radius"], "return 3.14 * radius * radius")
        detector.add_function("calculate_perimeter", ["length", "width"], "return 2 * (length + width)")
        detector.add_global_variable("pi", initial_value=3.14159)
        detector.add_global_variable("e", initial_value=2.71828)
        
        conflicts = detector.detect_conflicts()
        
        # Should have no conflicts
        assert len(conflicts) == 0

    def test_mixed_conflict_levels(self, detector):
        """Test detection of conflicts with different severity levels."""
        # Add a high-level conflict (overlapping function)
        detector.add_function("critical_function", ["x"], "return x * 2")
        detector.add_function("critical_function", ["x", "y"], "return x * y")
        
        # Add a medium-level conflict (shared global variable)
        detector.add_global_variable("shared_var", initial_value=10)
        detector.add_function("func_a", [], "global shared_var; shared_var += 1")
        detector.add_function("func_b", [], "global shared_var; shared_var -= 1")
        detector.add_global_variable_modification("func_a", "shared_var", "write")
        detector.add_global_variable_modification("func_b", "shared_var", "write")
        
        # Add a low-level conflict (minor interface change)
        detector.add_function("minor_function", ["a", "b"], "return a + b")
        detector.add_function("minor_function", ["a", "b", "c"], "return a + b + c")
        
        conflicts = detector.detect_conflicts()
        
        # Should detect all three types of conflicts
        assert len(conflicts) >= 3
        
        # Check for high-level conflict
        high_conflicts = [c for c in conflicts if c.level == ConflictLevel.HIGH]
        assert len(high_conflicts) >= 1
        
        # Check for medium-level conflict
        medium_conflicts = [c for c in conflicts if c.level == ConflictLevel.MEDIUM]
        assert len(medium_conflicts) >= 1
        
        # Check for low-level conflict
        low_conflicts = [c for c in conflicts if c.level == ConflictLevel.LOW]
        assert len(low_conflicts) >= 1