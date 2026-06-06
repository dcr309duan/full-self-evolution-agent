import pytest
import ast
import sys
import os
from pathlib import Path
import tempfile
import shutil
import logging

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


class TestEcologyPressureEngine:
    """Test the ecology pressure engine functionality."""

    def setup_method(self):
        """Set up a temporary directory for testing."""
        self.test_dir = tempfile.mkdtemp()
        self.log_file = Path(self.test_dir) / "pressure_log.txt"
        self.engine = self._create_engine()

    def teardown_method(self):
        """Clean up temporary directory."""
        shutil.rmtree(self.test_dir)

    def _create_engine(self):
        """Create a mock pressure engine for testing."""
        # This is a simplified version of the pressure engine for testing
        class MockPressureEngine:
            def __init__(self, test_dir, log_file):
                self.test_dir = Path(test_dir)
                self.log_file = Path(log_file)
                self.logger = logging.getLogger("pressure_engine")
                self.logger.setLevel(logging.INFO)
                handler = logging.FileHandler(str(self.log_file))
                handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
                self.logger.addHandler(handler)

            def scan_and_generate_tests(self, pressure_type):
                """Scan the test directory and generate new tests based on pressure type."""
                test_files = list(self.test_dir.glob("test_*.py"))
                generated_count = 0
                for test_file in test_files:
                    with open(test_file, "r") as f:
                        content = f.read()
                    if "def test_" not in content:
                        new_test = pressure_type.generate_test("new_function", {})
                        with open(test_file, "a") as f:
                            f.write("\n" + new_test)
                        generated_count += 1
                        self.logger.info(f"Generated new test in {test_file.name}")
                return generated_count

            def remove_old_tests(self, max_age_days=30):
                """Remove tests that are older than max_age_days."""
                import time
                current_time = time.time()
                removed_count = 0
                for test_file in self.test_dir.glob("test_*.py"):
                    file_age_days = (current_time - os.path.getmtime(test_file)) / 86400
                    if file_age_days > max_age_days:
                        test_file.unlink()
                        removed_count += 1
                        self.logger.info(f"Removed old test file {test_file.name}")
                return removed_count

            def get_log_entries(self):
                """Get all log entries."""
                if not self.log_file.exists():
                    return []
                with open(self.log_file, "r") as f:
                    return f.readlines()

        return MockPressureEngine(self.test_dir, self.log_file)

    def test_new_tests_generated(self):
        """Test that new tests are generated when scanning test directory."""
        # Create a test file without any test functions
        test_file = Path(self.test_dir) / "test_example.py"
        test_file.write_text("import pytest\n\ndef helper_function():\n    pass\n")
        
        # Generate new tests
        generated = self.engine.scan_and_generate_tests(PressureType.PERFORMANCE)
        
        # Verify that new tests were generated
        assert generated > 0, "No new tests were generated"
        content = test_file.read_text()
        assert "def test_" in content, "Generated test does not contain a test function"

    def test_old_tests_removed(self):
        """Test that old tests are removed based on age."""
        # Create an old test file
        old_test_file = Path(self.test_dir) / "test_old.py"
        old_test_file.write_text("import pytest\n\ndef test_old_function():\n    assert True\n")
        
        # Set the modification time to be very old
        import time
        old_time = time.time() - (60 * 24 * 60 * 60)  # 60 days ago
        os.utime(str(old_test_file), (old_time, old_time))
        
        # Create a new test file
        new_test_file = Path(self.test_dir) / "test_new.py"
        new_test_file.write_text("import pytest\n\ndef test_new_function():\n    assert True\n")
        
        # Remove old tests (max age 30 days)
        removed = self.engine.remove_old_tests(max_age_days=30)
        
        # Verify that only the old test was removed
        assert removed == 1, f"Expected 1 old test removed, got {removed}"
        assert not old_test_file.exists(), "Old test file was not removed"
        assert new_test_file.exists(), "New test file was incorrectly removed"

    def test_log_updated(self):
        """Test that the log is updated when tests are generated or removed."""
        # Create a test file
        test_file = Path(self.test_dir) / "test_log.py"
        test_file.write_text("import pytest\n\ndef helper():\n    pass\n")
        
        # Generate a test and check log
        self.engine.scan_and_generate_tests(PressureType.COMPLEXITY)
        log_entries = self.engine.get_log_entries()
        assert len(log_entries) > 0, "Log was not updated after test generation"
        assert any("Generated" in entry for entry in log_entries), "Log does not contain generation entry"
        
        # Remove old tests and check log
        import time
        old_time = time.time() - (60 * 24 * 60 * 60)
        os.utime(str(test_file), (old_time, old_time))
        self.engine.remove_old_tests(max_age_days=30)
        log_entries = self.engine.get_log_entries()
        assert any("Removed" in entry for entry in log_entries), "Log does not contain removal entry"

    def test_handles_empty_test_directory(self):
        """Test that the engine handles empty test directories gracefully."""
        # Ensure the test directory is empty
        assert len(list(self.test_dir.glob("test_*.py"))) == 0, "Test directory should be empty"
        
        # Try to generate tests in empty directory
        generated = self.engine.scan_and_generate_tests(PressureType.SECURITY)
        assert generated == 0, f"Expected 0 tests generated in empty directory, got {generated}"
        
        # Try to remove old tests in empty directory
        removed = self.engine.remove_old_tests(max_age_days=30)
        assert removed == 0, f"Expected 0 tests removed in empty directory, got {removed}"
        
        # Check that log is still updated
        log_entries = self.engine.get_log_entries()
        assert len(log_entries) == 0, "Log should be empty when no operations performed"

    def test_multiple_pressure_types_generate_different_tests(self):
        """Test that different pressure types generate different test content."""
        test_file = Path(self.test_dir) / "test_multi.py"
        test_file.write_text("import pytest\n\ndef helper():\n    pass\n")
        
        # Generate tests with different pressure types
        content_before = test_file.read_text()
        self.engine.scan_and_generate_tests(PressureType.PERFORMANCE)
        content_after_performance = test_file.read_text()
        
        # Reset file
        test_file.write_text("import pytest\n\ndef helper():\n    pass\n")
        self.engine.scan_and_generate_tests(PressureType.SECURITY)
        content_after_security = test_file.read_text()
        
        # Verify different content was generated
        assert content_after_performance != content_after_security, "Different pressure types generated identical tests"

    def test_log_persistence_across_operations(self):
        """Test that log entries persist across multiple operations."""
        test_file = Path(self.test_dir) / "test_persist.py"
        test_file.write_text("import pytest\n\ndef helper():\n    pass\n")
        
        # Perform multiple operations
        self.engine.scan_and_generate_tests(PressureType.PERFORMANCE)
        self.engine.scan_and_generate_tests(PressureType.COMPLEXITY)
        
        # Check that all entries are in the log
        log_entries = self.engine.get_log_entries()
        assert len(log_entries) >= 2, f"Expected at least 2 log entries, got {len(log_entries)}"

    def test_engine_does_not_modify_non_test_files(self):
        """Test that the engine only modifies test files."""
        # Create a non-test file
        non_test_file = Path(self.test_dir) / "helper.py"
        non_test_file.write_text("def helper():\n    pass\n")
        
        # Create a test file
        test_file = Path(self.test_dir) / "test_valid.py"
        test_file.write_text("import pytest\n\ndef helper():\n    pass\n")
        
        # Run engine
        self.engine.scan_and_generate_tests(PressureType.MAINTENANCE)
        
        # Verify non-test file was not modified
        assert non_test_file.read_text() == "def helper():\n    pass\n", "Non-test file was modified"
        assert "def test_" in test_file.read_text(), "Test file should have been modified"


if __name__ == "__main__":
    pytest.main([__file__])