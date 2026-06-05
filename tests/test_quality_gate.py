import pytest
import ast
import sys
import os
from unittest.mock import patch, MagicMock, call
from pathlib import Path

# Add the project root to sys.path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from modules.quality_gate import QualityGate, QualityGateError
from modules.mutation_engine import MutationEngine
from modules.mutation_sandbox import MutationSandbox


@pytest.fixture
def quality_gate():
    """Fixture providing a fresh QualityGate instance."""
    return QualityGate()


@pytest.fixture
def temp_python_file(tmp_path):
    """Fixture creating a temporary Python file for testing."""
    file_path = tmp_path / "test_module.py"
    return file_path


class TestSyntaxCheck:
    """Tests for the syntax validation component of the quality gate."""

    def test_valid_syntax_passes(self, quality_gate, temp_python_file):
        """Test that valid Python code passes the syntax check."""
        valid_code = """
def hello():
    print("Hello, world!")
    return 42

class TestClass:
    def method(self):
        pass
"""
        temp_python_file.write_text(valid_code)
        # Should not raise any exception
        quality_gate.check_syntax(temp_python_file)

    def test_invalid_syntax_fails(self, quality_gate, temp_python_file):
        """Test that invalid syntax (unterminated string) fails with correct error."""
        invalid_code = """
def broken():
    message = "This string never ends
    print(message)
"""
        temp_python_file.write_text(invalid_code)
        with pytest.raises(QualityGateError) as exc_info:
            quality_gate.check_syntax(temp_python_file)
        assert "SyntaxError" in str(exc_info.value) or "syntax" in str(exc_info.value).lower()

    def test_missing_parenthesis_fails(self, quality_gate, temp_python_file):
        """Test that missing closing parenthesis is caught."""
        invalid_code = """
def compute(x, y:
    return x + y
"""
        temp_python_file.write_text(invalid_code)
        with pytest.raises(QualityGateError):
            quality_gate.check_syntax(temp_python_file)

    def test_empty_file_passes(self, quality_gate, temp_python_file):
        """Test that an empty file passes syntax check."""
        temp_python_file.write_text("")
        quality_gate.check_syntax(temp_python_file)

    def test_non_python_file_raises(self, quality_gate, tmp_path):
        """Test that non-Python files are rejected."""
        non_python_file = tmp_path / "data.txt"
        non_python_file.write_text("This is not Python code")
        with pytest.raises(QualityGateError, match="not a Python file"):
            quality_gate.check_syntax(non_python_file)


class TestTypeCheck:
    """Tests for the mypy type checking component."""

    def test_valid_types_pass(self, quality_gate, temp_python_file):
        """Test that code with correct type annotations passes."""
        valid_code = """
def add(a: int, b: int) -> int:
    return a + b

x: int = add(1, 2)
"""
        temp_python_file.write_text(valid_code)
        result = quality_gate.check_types(temp_python_file)
        assert result is True

    def test_type_violation_caught(self, quality_gate, temp_python_file):
        """Test that mypy violations are caught."""
        invalid_code = """
def greet(name: str) -> str:
    return 42  # Type mismatch: returning int instead of str

x: int = "hello"  # Type mismatch: assigning str to int
"""
        temp_python_file.write_text(invalid_code)
        with pytest.raises(QualityGateError) as exc_info:
            quality_gate.check_types(temp_python_file)
        assert "type" in str(exc_info.value).lower() or "mypy" in str(exc_info.value).lower()

    def test_missing_type_annotations_warning(self, quality_gate, temp_python_file):
        """Test that missing type annotations generate warnings."""
        code = """
def untyped_function(x, y):
    return x + y
"""
        temp_python_file.write_text(code)
        result = quality_gate.check_types(temp_python_file)
        # Should pass but may generate warnings
        assert result is True


class TestRetryMechanism:
    """Tests for the retry mechanism in the quality gate."""

    def test_retry_on_failure(self, quality_gate, temp_python_file):
        """Test that the gate retries on transient failures."""
        valid_code = "x = 1\n"
        temp_python_file.write_text(valid_code)

        # Mock the check to fail twice then succeed
        with patch.object(quality_gate, 'check_syntax') as mock_check:
            mock_check.side_effect = [
                QualityGateError("Transient error"),
                QualityGateError("Transient error"),
                None  # Success on third attempt
            ]
            quality_gate.check_syntax(temp_python_file)
            assert mock_check.call_count == 3

    def test_abandon_after_three_failures(self, quality_gate, temp_python_file):
        """Test that the gate abandons after 3 consecutive failures."""
        valid_code = "x = 1\n"
        temp_python_file.write_text(valid_code)

        with patch.object(quality_gate, 'check_syntax') as mock_check:
            mock_check.side_effect = QualityGateError("Persistent error")
            with pytest.raises(QualityGateError, match="abandoned after 3 attempts"):
                quality_gate.check_syntax(temp_python_file, retries=3)
            assert mock_check.call_count == 3

    def test_no_retry_on_success(self, quality_gate, temp_python_file):
        """Test that no retries occur on first success."""
        valid_code = "x = 1\n"
        temp_python_file.write_text(valid_code)

        with patch.object(quality_gate, 'check_syntax') as mock_check:
            mock_check.return_value = None
            quality_gate.check_syntax(temp_python_file, retries=3)
            mock_check.assert_called_once()

    def test_custom_retry_count(self, quality_gate, temp_python_file):
        """Test that custom retry count is respected."""
        valid_code = "x = 1\n"
        temp_python_file.write_text(valid_code)

        with patch.object(quality_gate, 'check_syntax') as mock_check:
            mock_check.side_effect = QualityGateError("Error")
            with pytest.raises(QualityGateError):
                quality_gate.check_syntax(temp_python_file, retries=5)
            assert mock_check.call_count == 5


class TestIntegrationWithMutationFlow:
    """Tests that the quality gate integrates correctly with the mutation flow."""

    @pytest.fixture
    def mutation_engine(self, tmp_path):
        """Fixture providing a MutationEngine with a temporary workspace."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        engine = MutationEngine(workspace=str(workspace))
        return engine

    def test_mutation_passes_quality_gate(self, mutation_engine, tmp_path):
        """Test that a valid mutation passes through the quality gate."""
        source_file = tmp_path / "source.py"
        source_file.write_text("""
def add(a: int, b: int) -> int:
    return a + b
""")
        # Apply a simple mutation that should pass
        result = mutation_engine.apply_mutation(
            source_file,
            mutation_type="add_docstring"
        )
        assert result is not None
        assert result.success is True

    def test_mutation_fails_quality_gate(self, mutation_engine, tmp_path):
        """Test that a mutation producing invalid code is rejected."""
        source_file = tmp_path / "source.py"
        source_file.write_text("""
def process(data: str) -> str:
    return data.upper()
""")
        # Attempt a mutation that would break syntax
        with patch.object(mutation_engine.quality_gate, 'check_syntax') as mock_check:
            mock_check.side_effect = QualityGateError("Syntax error in mutation")
            result = mutation_engine.apply_mutation(
                source_file,
                mutation_type="break_syntax"
            )
            assert result is not None
            assert result.success is False
            assert "quality gate" in result.error.lower()

    def test_full_mutation_flow_with_gate(self, mutation_engine, tmp_path):
        """Test the complete mutation flow including quality gate validation."""
        source_file = tmp_path / "source.py"
        source_file.write_text("""
class Calculator:
    def add(self, a: int, b: int) -> int:
        return a + b

    def multiply(self, a: int, b: int) -> int:
        return a * b
""")
        # Apply mutation and verify it goes through the gate
        with patch.object(mutation_engine.quality_gate, 'evaluate') as mock_evaluate:
            mock_evaluate.return_value = True
            result = mutation_engine.apply_mutation(
                source_file,
                mutation_type="add_method"
            )
            mock_evaluate.assert_called_once()
            assert result.success is True


class TestQualityGateEdgeCases:
    """Tests for edge cases in the quality gate."""

    def test_large_file_handling(self, quality_gate, tmp_path):
        """Test that large files are handled without memory issues."""
        large_file = tmp_path / "large.py"
        # Generate a file with many lines
        lines = [f"x{i} = {i}\n" for i in range(10000)]
        large_file.writelines(lines)
        # Should process without error
        quality_gate.check_syntax(large_file)

    def test_unicode_content(self, quality_gate, temp_python_file):
        """Test that Unicode content is handled correctly."""
        code = """
# -*- coding: utf-8 -*-
def greet(name: str) -> str:
    return f"Hello, {name}! 你好"
"""
        temp_python_file.write_text(code)
        quality_gate.check_syntax(temp_python_file)

    def test_import_side_effects_prevented(self, quality_gate, temp_python_file):
        """Test that imports with side effects are detected."""
        code = """
import os
import sys
# This should not execute during syntax check
print("This should not run")
"""
        temp_python_file.write_text(code)
        # Should only check syntax, not execute
        quality_gate.check_syntax(temp_python_file)

    def test_concurrent_access(self, quality_gate, temp_python_file):
        """Test that the gate handles concurrent access safely."""
        import threading
        import time

        code = "x = 1\n"
        temp_python_file.write_text(code)

        errors = []
        def check_syntax_thread():
            try:
                quality_gate.check_syntax(temp_python_file)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=check_syntax_thread) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Concurrent access caused errors: {errors}"