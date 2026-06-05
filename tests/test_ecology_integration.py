import os
import sys
import tempfile
import shutil
import importlib.util
import pytest
from pathlib import Path

# Import the modules under test
from core.ecology_engine import TestSuiteMutator
from core.evolution_orchestrator import EvolutionOrchestrator


class TestEcologyIntegration:
    """Integration test for the full ECOLOGY cycle."""

    @pytest.fixture
    def temp_test_dir(self):
        """Create a temporary directory with a minimal test suite."""
        temp_dir = tempfile.mkdtemp()
        original_dir = os.getcwd()
        os.chdir(temp_dir)

        # Create a minimal test file with only unit tests
        test_file = Path(temp_dir) / "test_sample.py"
        test_file.write_text("""
import pytest

def test_addition():
    assert 1 + 1 == 2

def test_subtraction():
    assert 3 - 1 == 2

class TestMath:
    def test_multiplication(self):
        assert 2 * 3 == 6

    def test_division(self):
        assert 6 / 2 == 3
""")

        yield temp_dir

        # Cleanup
        os.chdir(original_dir)
        shutil.rmtree(temp_dir)

    def test_mutate_test_suite_creates_stress_test(self, temp_test_dir):
        """Test that mutate_test_suite() adds a stress test file."""
        mutator = TestSuiteMutator()
        result = mutator.mutate_test_suite(temp_test_dir)

        assert result is True, "mutate_test_suite() should return True on success"

        # Verify the new test file exists
        new_test_file = Path(temp_test_dir) / "test_stress_sample.py"
        assert new_test_file.exists(), "Stress test file should be created"

        # Verify it's importable
        spec = importlib.util.spec_from_file_location("test_stress_sample", str(new_test_file))
        assert spec is not None, "New test file should be importable"
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        assert hasattr(module, "test_stress_addition") or hasattr(module, "test_stress"), \
            "New test module should contain stress test functions"

    def test_new_test_executes_without_errors(self, temp_test_dir):
        """Test that the newly created stress test file runs successfully with pytest."""
        mutator = TestSuiteMutator()
        mutator.mutate_test_suite(temp_test_dir)

        # Run pytest on the new test file
        new_test_file = Path(temp_test_dir) / "test_stress_sample.py"
        result = pytest.main([str(new_test_file), "-v", "--tb=short"])

        assert result == 0, f"pytest should exit with code 0, got {result}"

    def test_orchestrator_ecology_phase_completes(self, temp_test_dir):
        """Test that the orchestrator's ECOLOGY phase completes without exceptions."""
        # Create a mock orchestrator that uses our temp directory
        orchestrator = EvolutionOrchestrator()
        
        # Override the test directory to use our temp directory
        orchestrator.test_dir = temp_test_dir
        
        # Run the ECOLOGY phase
        try:
            result = orchestrator.run_ecology_phase()
            assert result is True, "ECOLOGY phase should complete successfully"
        except Exception as e:
            pytest.fail(f"ECOLOGY phase raised an exception: {e}")

    def test_full_ecology_cycle(self, temp_test_dir):
        """Test the complete ECOLOGY cycle end-to-end."""
        # Step 1: Mock a minimal test suite (already done by fixture)
        # Step 2: Run mutate_test_suite() to add a stress test
        mutator = TestSuiteMutator()
        mutation_result = mutator.mutate_test_suite(temp_test_dir)
        assert mutation_result, "Mutation should succeed"

        # Step 3: Verify the new test file is created and importable
        new_test_file = Path(temp_test_dir) / "test_stress_sample.py"
        assert new_test_file.exists(), "Stress test file should exist"
        
        spec = importlib.util.spec_from_file_location("test_stress_sample", str(new_test_file))
        assert spec is not None, "Should be importable"
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # Step 4: Run the new test file with pytest
        pytest_result = pytest.main([str(new_test_file), "--tb=short", "-q"])
        assert pytest_result == 0, "New test should pass"

        # Step 5: Verify orchestrator's ECOLOGY phase completes
        orchestrator = EvolutionOrchestrator()
        orchestrator.test_dir = temp_test_dir
        ecology_result = orchestrator.run_ecology_phase()
        assert ecology_result is True, "ECOLOGY phase should complete without exceptions"

    def test_ecology_phase_does_not_pollute_real_tests(self, temp_test_dir):
        """Test that the ECOLOGY phase only affects the temporary directory."""
        # Create a mock real test directory
        real_test_dir = Path(temp_test_dir) / "real_tests"
        real_test_dir.mkdir()
        (real_test_dir / "test_real.py").write_text("def test_real(): pass")

        # Run ECOLOGY phase on temp directory
        orchestrator = EvolutionOrchestrator()
        orchestrator.test_dir = temp_test_dir
        orchestrator.run_ecology_phase()

        # Verify real test directory is untouched
        real_files = list(real_test_dir.iterdir())
        assert len(real_files) == 1, "Real test directory should have exactly 1 file"
        assert real_files[0].name == "test_real.py", "Real test file should remain unchanged"

        # Verify only temp directory has new stress test
        temp_files = [f.name for f in Path(temp_test_dir).iterdir()]
        assert "test_stress_sample.py" in temp_files, "Stress test should be in temp directory"