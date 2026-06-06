import pytest
import ast
import sys
import os
from unittest.mock import Mock, patch, MagicMock, call
from typing import Any, Dict, List, Optional

# Add parent directory to path to import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.reflection_to_action_bridge import ReflectionToActionBridge
from core.reflection_engine import ReflectionEngine
from core.orchestrator import Orchestrator
from core.mutation_spec import MutationSpec
from core.types import Reflection, ReflectionType, Action, ActionType


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_reflection_engine():
    """Create a mock reflection engine."""
    engine = Mock(spec=ReflectionEngine)
    engine.generate_reflection.return_value = Reflection(
        type=ReflectionType.ANALYTICAL,
        content="System analysis: module X has redundant code.",
        mutation_spec=None,
        confidence=0.85
    )
    return engine


@pytest.fixture
def mock_orchestrator():
    """Create a mock orchestrator."""
    orch = Mock(spec=Orchestrator)
    orch.execute_action.return_value = {"status": "success", "message": "Action executed"}
    return orch


@pytest.fixture
def bridge(mock_reflection_engine, mock_orchestrator):
    """Create a ReflectionToActionBridge with mocked dependencies."""
    return ReflectionToActionBridge(
        reflection_engine=mock_reflection_engine,
        orchestrator=mock_orchestrator
    )


@pytest.fixture
def sample_mutation_spec():
    """Create a valid MutationSpec for testing."""
    return MutationSpec(
        target_file="core/example.py",
        mutation_type="refactor",
        patch="""--- a/core/example.py
+++ b/core/example.py
@@ -1,5 +1,5 @@
 def old_function():
-    return 42
+    return 43
""",
        description="Change return value from 42 to 43"
    )


@pytest.fixture
def sample_reflection_with_mutation(sample_mutation_spec):
    """Create a reflection with a valid mutation_spec."""
    return Reflection(
        type=ReflectionType.MUTATION,
        content="Reflection: Change return value in example.py",
        mutation_spec=sample_mutation_spec,
        confidence=0.95
    )


@pytest.fixture
def sample_analytical_reflection():
    """Create an analytical-only reflection (no mutation_spec)."""
    return Reflection(
        type=ReflectionType.ANALYTICAL,
        content="System analysis: Module X has high cyclomatic complexity.",
        mutation_spec=None,
        confidence=0.80
    )


# ---------------------------------------------------------------------------
# Test 1: Reflections with valid mutation_spec are processed correctly
# ---------------------------------------------------------------------------

class TestMutationSpecProcessing:
    """Test that reflections with valid mutation_spec are processed correctly."""

    def test_process_reflection_with_mutation_spec(self, bridge, sample_reflection_with_mutation):
        """Test that a reflection with a mutation_spec is processed and forwarded to orchestrator."""
        # Act
        result = bridge.process_reflection(sample_reflection_with_mutation)

        # Assert
        assert result is not None
        assert result["status"] == "success"
        bridge.orchestrator.execute_action.assert_called_once()

    def test_mutation_spec_converted_to_action(self, bridge, sample_reflection_with_mutation):
        """Test that the mutation_spec is correctly converted to an Action."""
        # Act
        bridge.process_reflection(sample_reflection_with_mutation)

        # Assert
        call_args = bridge.orchestrator.execute_action.call_args
        assert call_args is not None
        action = call_args[0][0]
        assert isinstance(action, Action)
        assert action.type == ActionType.MUTATION
        assert action.target == sample_reflection_with_mutation.mutation_spec.target_file
        assert action.payload["patch"] == sample_reflection_with_mutation.mutation_spec.patch

    def test_high_confidence_mutation_immediate_execution(self, bridge, sample_reflection_with_mutation):
        """Test that high confidence mutations are executed immediately."""
        # Arrange
        sample_reflection_with_mutation.confidence = 0.95

        # Act
        result = bridge.process_reflection(sample_reflection_with_mutation)

        # Assert
        assert result["execution"] == "immediate"
        bridge.orchestrator.execute_action.assert_called_once()

    def test_low_confidence_mutation_requires_approval(self, bridge, sample_reflection_with_mutation):
        """Test that low confidence mutations require approval before execution."""
        # Arrange
        sample_reflection_with_mutation.confidence = 0.45

        # Act
        result = bridge.process_reflection(sample_reflection_with_mutation)

        # Assert
        assert result["execution"] == "requires_approval"
        bridge.orchestrator.execute_action.assert_not_called()

    def test_mutation_spec_with_multiple_changes(self, bridge):
        """Test processing a mutation_spec with multiple file changes."""
        # Arrange
        multi_mutation = MutationSpec(
            target_file="core/example.py",
            mutation_type="refactor",
            patch="""--- a/core/example.py
+++ b/core/example.py
@@ -1,3 +1,3 @@
 def func_a():
-    return 1
+    return 2
@@ -10,3 +10,3 @@
 def func_b():
-    return 3
+    return 4
""",
            description="Multiple changes"
        )
        reflection = Reflection(
            type=ReflectionType.MUTATION,
            content="Multiple changes needed",
            mutation_spec=multi_mutation,
            confidence=0.90
        )

        # Act
        result = bridge.process_reflection(reflection)

        # Assert
        assert result["status"] == "success"
        bridge.orchestrator.execute_action.assert_called_once()

    def test_mutation_spec_validation(self, bridge):
        """Test that invalid mutation_specs are rejected."""
        # Arrange
        invalid_spec = MutationSpec(
            target_file="",
            mutation_type="",
            patch="invalid patch without proper format",
            description=""
        )
        reflection = Reflection(
            type=ReflectionType.MUTATION,
            content="Invalid mutation",
            mutation_spec=invalid_spec,
            confidence=0.90
        )

        # Act
        result = bridge.process_reflection(reflection)

        # Assert
        assert result["status"] == "error"
        assert "validation" in result.get("error", "").lower()


# ---------------------------------------------------------------------------
# Test 2: Analytical-only reflections trigger fallback generation
# ---------------------------------------------------------------------------

class TestAnalyticalReflectionFallback:
    """Test that analytical-only reflections trigger fallback generation."""

    def test_analytical_reflection_triggers_fallback(self, bridge, sample_analytical_reflection):
        """Test that an analytical reflection without mutation_spec triggers fallback."""
        # Act
        result = bridge.process_reflection(sample_analytical_reflection)

        # Assert
        assert result["status"] == "fallback_generated"
        assert "fallback" in result
        assert result["fallback"]["type"] == "mutation"

    def test_fallback_generation_uses_reflection_content(self, bridge, sample_analytical_reflection):
        """Test that the fallback generation uses the reflection content."""
        # Act
        result = bridge.process_reflection(sample_analytical_reflection)

        # Assert
        fallback = result["fallback"]
        assert sample_analytical_reflection.content in fallback.get("context", "")

    def test_fallback_generation_creates_valid_mutation_spec(self, bridge, sample_analytical_reflection):
        """Test that fallback generation creates a valid mutation_spec."""
        # Act
        result = bridge.process_reflection(sample_analytical_reflection)

        # Assert
        fallback = result["fallback"]
        assert "mutation_spec" in fallback
        spec = fallback["mutation_spec"]
        assert isinstance(spec, MutationSpec)
        assert spec.target_file != ""
        assert spec.patch != ""
        assert spec.mutation_type != ""

    def test_multiple_analytical_reflections_accumulate(self, bridge):
        """Test that multiple analytical reflections accumulate context for better fallback."""
        # Arrange
        reflections = [
            Reflection(type=ReflectionType.ANALYTICAL, content="Issue 1: Performance bottleneck in module A", mutation_spec=None, confidence=0.70),
            Reflection(type=ReflectionType.ANALYTICAL, content="Issue 2: Memory leak in module B", mutation_spec=None, confidence=0.75),
            Reflection(type=ReflectionType.ANALYTICAL, content="Issue 3: Unused imports in module C", mutation_spec=None, confidence=0.80),
        ]

        # Act
        results = [bridge.process_reflection(r) for r in reflections]

        # Assert
        # Last reflection should have accumulated context from previous ones
        last_result = results[-1]
        assert last_result["status"] == "fallback_generated"
        assert len(last_result["fallback"].get("accumulated_context", [])) >= 2

    def test_analytical_reflection_with_high_confidence_immediate_fallback(self, bridge):
        """Test that high confidence analytical reflections get immediate fallback."""
        # Arrange
        high_conf_reflection = Reflection(
            type=ReflectionType.ANALYTICAL,
            content="Critical security vulnerability detected",
            mutation_spec=None,
            confidence=0.98
        )

        # Act
        result = bridge.process_reflection(high_conf_reflection)

        # Assert
        assert result["execution"] == "immediate"
        assert result["fallback"]["priority"] == "high"

    def test_analytical_reflection_with_low_confidence_deferred_fallback(self, bridge):
        """Test that low confidence analytical reflections get deferred fallback."""
        # Arrange
        low_conf_reflection = Reflection(
            type=ReflectionType.ANALYTICAL,
            content="Minor code style issue",
            mutation_spec=None,
            confidence=0.30
        )

        # Act
        result = bridge.process_reflection(low_conf_reflection)

        # Assert
        assert result["execution"] == "deferred"
        assert "review_required" in result


# ---------------------------------------------------------------------------
# Test 3: Fallback mutations are valid Python
# ---------------------------------------------------------------------------

class TestFallbackMutationValidity:
    """Test that fallback mutations produce valid Python code."""

    def test_fallback_patch_is_valid_python_syntax(self, bridge, sample_analytical_reflection):
        """Test that the generated fallback patch contains valid Python syntax."""
        # Act
        result = bridge.process_reflection(sample_analytical_reflection)
        fallback = result["fallback"]
        spec = fallback["mutation_spec"]

        # Extract the new code from the patch
        new_code = self._extract_new_code_from_patch(spec.patch)

        # Assert
        if new_code:
            try:
                ast.parse(new_code)
                syntax_valid = True
            except SyntaxError:
                syntax_valid = False
            assert syntax_valid, f"Generated code has invalid Python syntax: {new_code}"

    def test_fallback_patch_maintains_indentation(self, bridge, sample_analytical_reflection):
        """Test that the fallback patch maintains proper Python indentation."""
        # Act
        result = bridge.process_reflection(sample_analytical_reflection)
        fallback = result["fallback"]
        spec = fallback["mutation_spec"]

        # Assert
        lines = spec.patch.split('\n')
        for line in lines:
            if line.startswith('+') and not line.startswith('+++'):
                # Check that added lines have consistent indentation
                stripped = line[1:]  # Remove the '+' prefix
                if stripped.strip():  # Non-empty line
                    indent = len(stripped) - len(stripped.lstrip())
                    assert indent % 4 == 0, f"Indentation not multiple of 4: {line}"

    def test_fallback_patch_no_syntax_errors_in_context(self, bridge, sample_analytical_reflection):
        """Test that the fallback patch doesn't introduce syntax errors in context."""
        # Act
        result = bridge.process_reflection(sample_analytical_reflection)
        fallback = result["fallback"]
        spec = fallback["mutation_spec"]

        # Simulate applying the patch and check syntax
        try:
            # This is a simplified check - in reality you'd apply the patch to actual files
            self._simulate_patch_application(spec.patch)
            valid = True
        except Exception:
            valid = False

        assert valid, "Fallback patch would introduce syntax errors"

    def test_fallback_patch_imports_are_valid(self, bridge, sample_analytical_reflection):
        """Test that any imports in the fallback patch are valid Python imports."""
        # Act
        result = bridge.process_reflection(sample_analytical_reflection)
        fallback = result["fallback"]
        spec = fallback["mutation_spec"]

        # Extract import statements from the patch
        imports = self._extract_imports_from_patch(spec.patch)

        # Assert
        for imp in imports:
            try:
                ast.parse(imp)
                valid = True
            except SyntaxError:
                valid = False
            assert valid, f"Invalid import statement: {imp}"

    def test_fallback_patch_no_broken_fstrings(self, bridge, sample_analytical_reflection):
        """Test that the fallback patch doesn't contain broken f-strings."""
        # Act
        result = bridge.process_reflection(sample_analytical_reflection)
        fallback = result["fallback"]
        spec = fallback["mutation_spec"]

        # Assert
        lines = spec.patch.split('\n')
        for line in lines:
            if line.startswith('+') and 'f"' in line:
                # Check that f-strings are properly closed
                fstring_count = line.count('f"')
                closing_quote_count = line.count('"') - line.count('f"')
                assert fstring_count <= closing_quote_count, f"Broken f-string: {line}"

    def _extract_new_code_from_patch(self, patch: str) -> str:
        """Extract the new (added) code from a unified diff patch."""
        new_lines = []
        for line in patch.split('\n'):
            if line.startswith('+') and not line.startswith('+++'):
                new_lines.append(line[1:])  # Remove the '+' prefix
        return '\n'.join(new_lines)

    def _extract_imports_from_patch(self, patch: str) -> List[str]:
        """Extract import statements from a patch."""
        imports = []
        for line in patch.split('\n'):
            if line.startswith('+') and ('import ' in line or 'from ' in line):
                imports.append(line[1:].strip())
        return imports

    def _simulate_patch_application(self, patch: str) -> None:
        """Simulate applying a patch to check for syntax errors."""
        # This is a simplified simulation
        # In a real implementation, you'd use actual file content
        new_code = self._extract_new_code_from_patch(patch)
        if new_code.strip():
            ast.parse(new_code)


# ---------------------------------------------------------------------------
# Test 4: Integration with the orchestrator
# ---------------------------------------------------------------------------

class TestOrchestratorIntegration:
    """Test integration with the orchestrator."""

    def test_bridge_integrates_with_orchestrator(self, bridge, sample_reflection_with_mutation):
        """Test that the bridge correctly integrates with the orchestrator."""
        # Act
        result = bridge.process_reflection(sample_reflection_with_mutation)

        # Assert
        bridge.orchestrator.execute_action.assert_called_once()
        assert result["orchestrator_response"] is not None

    def test_orchestrator_failure_handling(self, bridge, sample_reflection_with_mutation):
        """Test that orchestrator failures are properly handled."""
        # Arrange
        bridge.orchestrator.execute_action.side_effect = Exception("Orchestrator error")

        # Act
        result = bridge.process_reflection(sample_reflection_with_mutation)

        # Assert
        assert result["status"] == "error"
        assert "orchestrator_error" in result

    def test_orchestrator_rollback_on_failure(self, bridge, sample_reflection_with_mutation):
        """Test that the bridge triggers rollback on orchestrator failure."""
        # Arrange
        bridge.orchestrator.execute_action.side_effect = Exception("Execution failed")
        bridge.orchestrator.rollback = Mock(return_value={"status": "rolled_back"})

        # Act
        result = bridge.process_reflection(sample_reflection_with_mutation)

        # Assert
        bridge.orchestrator.rollback.assert_called_once()
        assert result["rollback_performed"] is True

    def test_orchestrator_queues_multiple_actions(self, bridge):
        """Test that multiple reflections are properly queued in the orchestrator."""
        # Arrange
        reflections = [
            Reflection(type=ReflectionType.MUTATION, content=f"Mutation {i}", 
                      mutation_spec=MutationSpec(target_file=f"file{i}.py", mutation_type="refactor",
                                                patch=f"patch{i}", description=f"desc{i}"),
                      confidence=0.90)
            for i in range(3)
        ]

        # Act
        for reflection in reflections:
            bridge.process_reflection(reflection)

        # Assert
        assert bridge.orchestrator.execute_action.call_count == 3

    def test_orchestrator_priority_handling(self, bridge):
        """Test that high priority reflections are executed before low priority ones."""
        # Arrange
        low_priority = Reflection(type=ReflectionType.MUTATION, content="Low priority",
                                 mutation_spec=MutationSpec(target_file="low.py", mutation_type="refactor",
                                                           patch="low_patch", description="low"),
                                 confidence=0.50)
        high_priority = Reflection(type=ReflectionType.MUTATION, content="High priority",
                                  mutation_spec=MutationSpec(target_file="high.py", mutation_type="refactor",
                                                            patch="high_patch", description="high"),
                                  confidence=0.95)

        # Act
        bridge.process_reflection(low_priority)
