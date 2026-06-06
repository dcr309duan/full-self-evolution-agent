import unittest
from unittest.mock import patch, MagicMock, call
import ast
import sys
import os

# Add the parent directory to sys.path to import core modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.mutation_quality_gate import MutationQualityGate, QualityGateResult, QualityGateStage
from core.evolution_orchestrator import EvolutionOrchestrator


class TestMutationQualityGate(unittest.TestCase):
    """Comprehensive tests for the MutationQualityGate class."""

    def setUp(self):
        """Set up test fixtures."""
        self.quality_gate = MutationQualityGate()
        self.valid_patch = """
def add(a, b):
    return a + b
"""
        self.syntax_error_patch = """
def add(a, b):
    return a + b
"""
        self.type_error_patch = """
def add(a, b):
    return a + b
"""
        self.import_error_patch = """
import nonexistent_module
def add(a, b):
    return nonexistent_module.add(a, b)
"""

    def test_valid_patch_passes_all_stages(self):
        """Test that a valid patch passes syntax, type, and import checks."""
        result = self.quality_gate.check_patch(self.valid_patch)
        self.assertTrue(result.passed)
        self.assertEqual(result.stage, QualityGateStage.ALL_PASSED)
        self.assertIsNone(result.error)

    def test_syntax_error_caught(self):
        """Test that a patch with syntax errors is caught at stage 1."""
        invalid_patch = """
def add(a, b):
    return a + b
"""
        # Introduce a syntax error
        invalid_patch = invalid_patch.replace("return a + b", "return a +")
        result = self.quality_gate.check_patch(invalid_patch)
        self.assertFalse(result.passed)
        self.assertEqual(result.stage, QualityGateStage.SYNTAX_CHECK)
        self.assertIsNotNone(result.error)
        self.assertIn("syntax", result.error_category)

    def test_type_error_caught(self):
        """Test that a patch with type errors is caught at stage 2."""
        # Simulate a type error by using a type hint mismatch
        type_error_patch = """
def add(a: int, b: str) -> int:
    return a + b
"""
        result = self.quality_gate.check_patch(type_error_patch)
        self.assertFalse(result.passed)
        self.assertEqual(result.stage, QualityGateStage.TYPE_CHECK)
        self.assertIsNotNone(result.error)
        self.assertIn("type", result.error_category)

    def test_import_error_caught(self):
        """Test that a patch with import errors is caught at stage 3."""
        result = self.quality_gate.check_patch(self.import_error_patch)
        self.assertFalse(result.passed)
        self.assertEqual(result.stage, QualityGateStage.IMPORT_CHECK)
        self.assertIsNotNone(result.error)
        self.assertIn("import", result.error_category)

    def test_retry_logic_success_after_two_failures(self):
        """Test that retry logic allows a patch to pass after two failures."""
        # Mock the LLM to fail twice then succeed
        mock_llm = MagicMock()
        mock_llm.generate_patch.side_effect = [
            self.syntax_error_patch,  # First attempt: syntax error
            self.type_error_patch,    # Second attempt: type error
            self.valid_patch          # Third attempt: valid
        ]

        # Create a quality gate with retry logic
        quality_gate_with_retry = MutationQualityGate(max_retries=3)
        quality_gate_with_retry.llm = mock_llm

        # Simulate the retry process
        result = None
        for attempt in range(3):
            patch = mock_llm.generate_patch()
            result = quality_gate_with_retry.check_patch(patch)
            if result.passed:
                break

        self.assertTrue(result.passed)
        self.assertEqual(result.stage, QualityGateStage.ALL_PASSED)
        self.assertEqual(mock_llm.generate_patch.call_count, 3)

    def test_abandonment_after_three_failures(self):
        """Test that the quality gate abandons a patch after three failures."""
        # Mock the LLM to always return invalid patches
        mock_llm = MagicMock()
        mock_llm.generate_patch.return_value = self.syntax_error_patch

        # Create a quality gate with max_retries=3
        quality_gate_with_retry = MutationQualityGate(max_retries=3)
        quality_gate_with_retry.llm = mock_llm

        # Simulate the retry process
        result = None
        for attempt in range(3):
            patch = mock_llm.generate_patch()
            result = quality_gate_with_retry.check_patch(patch)
            if result.passed:
                break

        self.assertFalse(result.passed)
        self.assertEqual(result.stage, QualityGateStage.ABANDONED)
        self.assertEqual(mock_llm.generate_patch.call_count, 3)

    def test_integration_with_orchestrator(self):
        """Test that the quality gate integrates correctly with the orchestrator."""
        # Create a mock orchestrator
        mock_orchestrator = MagicMock(spec=EvolutionOrchestrator)
        mock_orchestrator.quality_gate = self.quality_gate

        # Simulate the orchestrator using the quality gate
        patch = self.valid_patch
        result = mock_orchestrator.quality_gate.check_patch(patch)

        self.assertTrue(result.passed)
        self.assertEqual(result.stage, QualityGateStage.ALL_PASSED)

        # Test that the orchestrator can handle a failed patch
        failed_patch = self.syntax_error_patch
        failed_result = mock_orchestrator.quality_gate.check_patch(failed_patch)
        self.assertFalse(failed_result.passed)

    def test_error_categorization(self):
        """Test that errors are correctly categorized."""
        # Test syntax error categorization
        syntax_patch = """
def add(a, b):
    return a +
"""
        result = self.quality_gate.check_patch(syntax_patch)
        self.assertEqual(result.error_category, "syntax")

        # Test type error categorization
        type_patch = """
def add(a: int, b: str) -> int:
    return a + b
"""
        result = self.quality_gate.check_patch(type_patch)
        self.assertEqual(result.error_category, "type")

        # Test import error categorization
        import_patch = """
import nonexistent_module
def add(a, b):
    return nonexistent_module.add(a, b)
"""
        result = self.quality_gate.check_patch(import_patch)
        self.assertEqual(result.error_category, "import")

        # Test runtime error categorization
        runtime_patch = """
def divide(a, b):
    return a / b
"""
        # This patch is syntactically correct but may cause runtime errors
        result = self.quality_gate.check_patch(runtime_patch)
        self.assertEqual(result.error_category, "runtime")

    def test_quality_gate_result_class(self):
        """Test the QualityGateResult class."""
        result = QualityGateResult(
            passed=True,
            stage=QualityGateStage.ALL_PASSED,
            error=None,
            error_category=None
        )
        self.assertTrue(result.passed)
        self.assertEqual(result.stage, QualityGateStage.ALL_PASSED)
        self.assertIsNone(result.error)
        self.assertIsNone(result.error_category)

        # Test with error
        error_result = QualityGateResult(
            passed=False,
            stage=QualityGateStage.SYNTAX_CHECK,
            error="Syntax error: invalid syntax",
            error_category="syntax"
        )
        self.assertFalse(error_result.passed)
        self.assertEqual(error_result.stage, QualityGateStage.SYNTAX_CHECK)
        self.assertIsNotNone(error_result.error)
        self.assertEqual(error_result.error_category, "syntax")

    def test_quality_gate_stage_enum(self):
        """Test the QualityGateStage enum."""
        self.assertEqual(QualityGateStage.SYNTAX_CHECK.value, 1)
        self.assertEqual(QualityGateStage.TYPE_CHECK.value, 2)
        self.assertEqual(QualityGateStage.IMPORT_CHECK.value, 3)
        self.assertEqual(QualityGateStage.ALL_PASSED.value, 4)
        self.assertEqual(QualityGateStage.ABANDONED.value, 5)

    def test_empty_patch(self):
        """Test that an empty patch is handled correctly."""
        empty_patch = ""
        result = self.quality_gate.check_patch(empty_patch)
        self.assertFalse(result.passed)
        self.assertEqual(result.stage, QualityGateStage.SYNTAX_CHECK)
        self.assertIsNotNone(result.error)

    def test_none_patch(self):
        """Test that a None patch is handled correctly."""
        result = self.quality_gate.check_patch(None)
        self.assertFalse(result.passed)
        self.assertEqual(result.stage, QualityGateStage.SYNTAX_CHECK)
        self.assertIsNotNone(result.error)

    def test_whitespace_only_patch(self):
        """Test that a whitespace-only patch is handled correctly."""
        whitespace_patch = "   \n   \n"
        result = self.quality_gate.check_patch(whitespace_patch)
        self.assertFalse(result.passed)
        self.assertEqual(result.stage, QualityGateStage.SYNTAX_CHECK)
        self.assertIsNotNone(result.error)

    def test_multiple_errors_in_patch(self):
        """Test that a patch with multiple errors is caught at the earliest stage."""
        # Patch with both syntax and import errors
        multi_error_patch = """
import nonexistent_module
def add(a, b):
    return a +
"""
        result = self.quality_gate.check_patch(multi_error_patch)
        self.assertFalse(result.passed)
        # Should fail at syntax check first
        self.assertEqual(result.stage, QualityGateStage.SYNTAX_CHECK)
        self.assertEqual(result.error_category, "syntax")

    def test_retry_logic_with_mixed_errors(self):
        """Test retry logic with different error types across attempts."""
        mock_llm = MagicMock()
        mock_llm.generate_patch.side_effect = [
            self.syntax_error_patch,  # Syntax error
            self.type_error_patch,    # Type error
            self.import_error_patch,  # Import error
            self.valid_patch          # Valid
        ]

        quality_gate_with_retry = MutationQualityGate(max_retries=4)
        quality_gate_with_retry.llm = mock_llm

        result = None
        for attempt in range(4):
            patch = mock_llm.generate_patch()
            result = quality_gate_with_retry.check_patch(patch)
            if result.passed:
                break

        self.assertTrue(result.passed)
        self.assertEqual(result.stage, QualityGateStage.ALL_PASSED)
        self.assertEqual(mock_llm.generate_patch.call_count, 4)

    def test_retry_logic_exhaustion(self):
        """Test that retry logic exhausts all attempts and abandons."""
        mock_llm = MagicMock()
        mock_llm.generate_patch.return_value = self.syntax_error_patch

        quality_gate_with_retry = MutationQualityGate(max_retries=5)
        quality_gate_with_retry.llm = mock_llm

        result = None
        for attempt in range(5):
            patch = mock_llm.generate_patch()
            result = quality_gate_with_retry.check_patch(patch)
            if result.passed:
                break

        self.assertFalse(result.passed)
        self.assertEqual(result.stage, QualityGateStage.ABANDONED)
        self.assertEqual(mock_llm.generate_patch.call_count, 5)

    def test_orchestrator_integration_with_retry(self):
        """Test that the orchestrator correctly handles retry logic."""
        mock_orchestrator = MagicMock(spec=EvolutionOrchestrator)
        mock_llm = MagicMock()
        mock_llm.generate_patch.side_effect = [
            self.syntax_error_patch,
            self.type_error_patch,
            self.valid_patch
        ]

        quality_gate_with_retry = MutationQualityGate(max_retries=3)
        quality_gate_with_retry.llm = mock_llm
        mock_orchestrator.quality_gate = quality_gate_with_retry

        # Simulate the orchestrator's retry loop
        result = None
        for attempt in range(3):
            patch = mock_orchestrator.quality_gate.llm.generate_patch()
            result = mock_orchestrator.quality_gate.check_patch(patch)
            if result.passed:
                break

        self.assertTrue(result.passed)
        self.assertEqual(result.stage, QualityGateStage.ALL_PASSED)

    def test_orchestrator_integration_abandonment(self):
        """Test that the orchestrator correctly handles abandonment."""
        mock_orchestrator = MagicMock(spec=EvolutionOrchestrator)
        mock_llm = MagicMock()
        mock_llm.generate_patch.return_value = self.syntax_error_patch

        quality_gate_with_retry = MutationQualityGate(max_retries=3)
        quality_gate_with_retry.llm = mock_llm
        mock_orchestrator.quality_gate = quality_gate_with_retry

        # Simulate the orchestrator's retry loop
        result = None
        for attempt in range(3):
            patch = mock_orchestrator.quality_gate.llm.generate_patch()
            result = mock_orchestrator.quality_gate.check_patch(patch)
            if result.passed:
                break

        self.assertFalse(result.passed)
        self.assertEqual(result.stage, QualityGateStage.ABANDONED)


if __name__ == '__main__':
    unittest.main()