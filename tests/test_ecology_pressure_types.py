import pytest
import ast
import sys
import os
from pathlib import Path

# Add the core directory to the path so we can import the module
sys.path.insert(0, str(Path(__file__).parent.parent / "core"))

from ecology_pressure_types import PressureType, get_pressure_type, PRESSURE_TYPES


class TestPressureTypeEnum:
    """Test the PressureType enum values and properties."""

    def test_enum_values(self):
        """Test that all expected pressure types exist."""
        assert PressureType.PERFORMANCE.value == "PERFORMANCE"
        assert PressureType.COMPLEXITY.value == "COMPLEXITY"
        assert PressureType.EDGE_CASE.value == "EDGE_CASE"
        assert PressureType.SECURITY.value == "SECURITY"
        assert PressureType.MAINTENANCE.value == "MAINTENANCE"
        assert PressureType.SCALABILITY.value == "SCALABILITY"

    def test_all_pressure_types_in_enum(self):
        """Test that all PRESSURE_TYPES are represented in the enum."""
        enum_values = {pt.value for pt in PressureType}
        for pt_name in PRESSURE_TYPES:
            assert pt_name in enum_values, f"{pt_name} not found in PressureType enum"

    def test_enum_members_count(self):
        """Test that we have the expected number of pressure types."""
        assert len(PressureType) >= 6


class TestGetPressureType:
    """Test the get_pressure_type factory function."""

    def test_get_performance(self):
        """Test getting PERFORMANCE pressure type."""
        pt = get_pressure_type("PERFORMANCE")
        assert pt == PressureType.PERFORMANCE

    def test_get_complexity(self):
        """Test getting COMPLEXITY pressure type."""
        pt = get_pressure_type("COMPLEXITY")
        assert pt == PressureType.COMPLEXITY

    def test_get_edge_case(self):
        """Test getting EDGE_CASE pressure type."""
        pt = get_pressure_type("EDGE_CASE")
        assert pt == PressureType.EDGE_CASE

    def test_get_security(self):
        """Test getting SECURITY pressure type."""
        pt = get_pressure_type("SECURITY")
        assert pt == PressureType.SECURITY

    def test_get_maintenance(self):
        """Test getting MAINTENANCE pressure type."""
        pt = get_pressure_type("MAINTENANCE")
        assert pt == PressureType.MAINTENANCE

    def test_get_scalability(self):
        """Test getting SCALABILITY pressure type."""
        pt = get_pressure_type("SCALABILITY")
        assert pt == PressureType.SCALABILITY

    def test_get_case_insensitive(self):
        """Test that get_pressure_type is case-insensitive."""
        pt1 = get_pressure_type("performance")
        pt2 = get_pressure_type("Performance")
        pt3 = get_pressure_type("PERFORMANCE")
        assert pt1 == pt2 == pt3 == PressureType.PERFORMANCE

    def test_get_invalid_type(self):
        """Test that invalid type raises ValueError."""
        with pytest.raises(ValueError, match="Unknown pressure type"):
            get_pressure_type("INVALID_TYPE")

    def test_get_empty_string(self):
        """Test that empty string raises ValueError."""
        with pytest.raises(ValueError):
            get_pressure_type("")


class TestPressureTypeTestGeneration:
    """Test that each pressure type generates appropriate tests."""

    def test_performance_generates_timing_tests(self):
        """Test that PERFORMANCE generates tests with timing/performance focus."""
        pt = PressureType.PERFORMANCE
        test_code = pt.generate_test("example_function", {"param1": "value1"})
        
        # Verify it's syntactically valid Python
        ast.parse(test_code)
        
        # Check for performance-related content
        assert "time" in test_code.lower() or "performance" in test_code.lower() or "benchmark" in test_code.lower()
        assert "def test_" in test_code

    def test_complexity_generates_algorithmic_tests(self):
        """Test that COMPLEXITY generates tests with algorithmic focus."""
        pt = PressureType.COMPLEXITY
        test_code = pt.generate_test("complex_algorithm", {"data": [1, 2, 3]})
        
        # Verify it's syntactically valid Python
        ast.parse(test_code)
        
        # Check for complexity-related content
        assert "complexity" in test_code.lower() or "algorithm" in test_code.lower() or "big o" in test_code.lower()
        assert "def test_" in test_code

    def test_edge_case_generates_boundary_tests(self):
        """Test that EDGE_CASE generates tests with boundary/edge focus."""
        pt = PressureType.EDGE_CASE
        test_code = pt.generate_test("boundary_function", {"input": 0})
        
        # Verify it's syntactically valid Python
        ast.parse(test_code)
        
        # Check for edge case-related content
        assert "edge" in test_code.lower() or "boundary" in test_code.lower() or "limit" in test_code.lower()
        assert "def test_" in test_code

    def test_security_generates_security_tests(self):
        """Test that SECURITY generates tests with security focus."""
        pt = PressureType.SECURITY
        test_code = pt.generate_test("secure_function", {"user_input": "test"})
        
        # Verify it's syntactically valid Python
        ast.parse(test_code)
        
        # Check for security-related content
        assert "security" in test_code.lower() or "injection" in test_code.lower() or "sanitize" in test_code.lower() or "validation" in test_code.lower()
        assert "def test_" in test_code

    def test_maintenance_generates_maintainability_tests(self):
        """Test that MAINTENANCE generates tests with maintainability focus."""
        pt = PressureType.MAINTENANCE
        test_code = pt.generate_test("maintainable_code", {"version": "1.0"})
        
        # Verify it's syntactically valid Python
        ast.parse(test_code)
        
        # Check for maintenance-related content
        assert "maintenance" in test_code.lower() or "maintain" in test_code.lower() or "refactor" in test_code.lower() or "readability" in test_code.lower()
        assert "def test_" in test_code

    def test_scalability_generates_scaling_tests(self):
        """Test that SCALABILITY generates tests with scalability focus."""
        pt = PressureType.SCALABILITY
        test_code = pt.generate_test("scalable_service", {"concurrent_users": 100})
        
        # Verify it's syntactically valid Python
        ast.parse(test_code)
        
        # Check for scalability-related content
        assert "scalability" in test_code.lower() or "scale" in test_code.lower() or "concurrent" in test_code.lower() or "load" in test_code.lower()
        assert "def test_" in test_code


class TestGeneratedTestSyntax:
    """Test that all generated tests are syntactically valid Python."""

    @pytest.mark.parametrize("pressure_type", list(PressureType))
    def test_generated_test_is_valid_python(self, pressure_type):
        """Test that generated test code is syntactically valid Python for all pressure types."""
        test_code = pressure_type.generate_test("test_function", {"arg": "value"})
        
        # This will raise SyntaxError if the code is invalid
        try:
            ast.parse(test_code)
        except SyntaxError as e:
            pytest.fail(f"Generated test for {pressure_type.value} is not valid Python: {e}")

    @pytest.mark.parametrize("pressure_type", list(PressureType))
    def test_generated_test_contains_test_function(self, pressure_type):
        """Test that generated test code contains at least one test function."""
        test_code = pressure_type.generate_test("test_function", {"arg": "value"})
        assert "def test_" in test_code, f"Generated test for {pressure_type.value} does not contain a test function"

    @pytest.mark.parametrize("pressure_type", list(PressureType))
    def test_generated_test_has_imports(self, pressure_type):
        """Test that generated test code includes necessary imports."""
        test_code = pressure_type.generate_test("test_function", {"arg": "value"})
        assert "import" in test_code, f"Generated test for {pressure_type.value} does not contain imports"


class TestPressureTypeDescriptions:
    """Test that pressure types have meaningful descriptions."""

    def test_performance_description(self):
        """Test PERFORMANCE has a description."""
        pt = PressureType.PERFORMANCE
        description = pt.get_description()
        assert isinstance(description, str)
        assert len(description) > 0

    def test_complexity_description(self):
        """Test COMPLEXITY has a description."""
        pt = PressureType.COMPLEXITY
        description = pt.get_description()
        assert isinstance(description, str)
        assert len(description) > 0

    def test_edge_case_description(self):
        """Test EDGE_CASE has a description."""
        pt = PressureType.EDGE_CASE
        description = pt.get_description()
        assert isinstance(description, str)
        assert len(description) > 0

    def test_all_types_have_descriptions(self):
        """Test that all pressure types have non-empty descriptions."""
        for pt in PressureType:
            description = pt.get_description()
            assert isinstance(description, str), f"{pt.value} description is not a string"
            assert len(description) > 0, f"{pt.value} description is empty"


class TestPressureTypeConsistency:
    """Test consistency across pressure types."""

    def test_all_types_generate_valid_python(self):
        """Test that all pressure types generate valid Python code."""
        for pt in PressureType:
            test_code = pt.generate_test("consistency_test", {})
            try:
                ast.parse(test_code)
            except SyntaxError:
                pytest.fail(f"{pt.value} generates invalid Python")

    def test_all_types_have_unique_descriptions(self):
        """Test that all pressure types have unique descriptions."""
        descriptions = [pt.get_description() for pt in PressureType]
        assert len(descriptions) == len(set(descriptions)), "Some pressure types have duplicate descriptions"

    def test_pressure_types_list_matches_enum(self):
        """Test that PRESSURE_TYPES list matches enum values."""
        enum_names = {pt.value for pt in PressureType}
        list_names = set(PRESSURE_TYPES)
        assert enum_names == list_names, f"Enum values {enum_names} don't match list {list_names}"


if __name__ == "__main__":
    pytest.main([__file__])