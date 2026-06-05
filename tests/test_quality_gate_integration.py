import pytest
import tempfile
import os
import sys
import subprocess
from pathlib import Path

# Add the project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from modules.mutation_engine import MutationEngine
from modules.quality_gate import QualityGate


@pytest.fixture
def temp_project_dir():
    """Create a temporary directory simulating a project structure."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a simple Python file to mutate
        project_dir = Path(tmpdir) / "test_project"
        project_dir.mkdir()
        test_file = project_dir / "example.py"
        test_file.write_text("def add(a, b):\n    return a + b\n")
        yield project_dir


@pytest.fixture
def quality_gate():
    """Create a QualityGate instance."""
    return QualityGate()


@pytest.fixture
def mutation_engine(quality_gate):
    """Create a MutationEngine with the quality gate."""
    return MutationEngine(quality_gate=quality_gate)


def test_valid_mutation_passes_quality_gate(temp_project_dir, mutation_engine):
    """Test that a valid mutation (adding a comment) passes the quality gate."""
    test_file = temp_project_dir / "example.py"
    original_content = test_file.read_text()
    
    # Apply a valid mutation: add a comment
    mutated_content = original_content + "\n# This is a valid mutation\n"
    test_file.write_text(mutated_content)
    
    # Run the quality gate
    result = mutation_engine.run_quality_gate(str(test_file))
    
    assert result["passed"] is True, f"Valid mutation should pass quality gate, got: {result}"
    assert result["syntax_check"] == "passed"
    assert result["static_analysis"] == "passed"


def test_invalid_mutation_fails_quality_gate(temp_project_dir, mutation_engine):
    """Test that an invalid mutation (syntax error) is caught by the quality gate."""
    test_file = temp_project_dir / "example.py"
    
    # Apply an invalid mutation: introduce a syntax error
    mutated_content = "def add(a, b):\n    return a + b\n\ndef broken("
    test_file.write_text(mutated_content)
    
    # Run the quality gate
    result = mutation_engine.run_quality_gate(str(test_file))
    
    assert result["passed"] is False, "Invalid mutation should fail quality gate"
    assert result["syntax_check"] == "failed"
    assert "SyntaxError" in result.get("error", "")


def test_retry_mechanism_abandons_after_three_failures(temp_project_dir, mutation_engine):
    """Test that the retry mechanism abandons after 3 failed attempts."""
    test_file = temp_project_dir / "example.py"
    
    # Create a persistently invalid mutation
    mutated_content = "def add(a, b):\n    return a + b\n\ndef broken("
    test_file.write_text(mutated_content)
    
    # Attempt mutation with retries
    result = mutation_engine.apply_mutation_with_retry(
        str(test_file),
        max_retries=3,
        retry_delay=0.1  # Short delay for testing
    )
    
    assert result["abandoned"] is True, "Should abandon after 3 failed attempts"
    assert result["attempts"] == 3, f"Should have attempted 3 times, got {result['attempts']}"
    assert result["success"] is False, "Mutation should not succeed"


def test_retry_mechanism_succeeds_on_valid_mutation(temp_project_dir, mutation_engine):
    """Test that retry mechanism succeeds when mutation becomes valid."""
    test_file = temp_project_dir / "example.py"
    
    # First attempt with invalid mutation
    invalid_content = "def add(a, b):\n    return a + b\n\ndef broken("
    test_file.write_text(invalid_content)
    
    # Simulate retry with eventual valid mutation
    result = mutation_engine.apply_mutation_with_retry(
        str(test_file),
        max_retries=5,
        retry_delay=0.1,
        on_retry=lambda: test_file.write_text("def add(a, b):\n    return a + b\n# Fixed\n")
    )
    
    assert result["abandoned"] is False, "Should not abandon when mutation becomes valid"
    assert result["success"] is True, "Mutation should succeed after fix"
    assert result["attempts"] <= 5, f"Should succeed within 5 attempts, got {result['attempts']}"


def test_quality_gate_integration_with_mutation_engine(temp_project_dir, mutation_engine):
    """Test the full integration: mutation application with quality gate."""
    test_file = temp_project_dir / "example.py"
    original_content = test_file.read_text()
    
    # Apply a valid mutation through the engine
    result = mutation_engine.apply_mutation(str(test_file))
    
    assert result["applied"] is True, "Mutation should be applied"
    assert result["quality_gate_passed"] is True, "Quality gate should pass"
    
    # Verify the file was modified
    modified_content = test_file.read_text()
    assert modified_content != original_content, "File should be modified"
    
    # Verify the modified file is still valid Python
    try:
        compile(modified_content, str(test_file), "exec")
    except SyntaxError:
        pytest.fail("Modified file should be valid Python")