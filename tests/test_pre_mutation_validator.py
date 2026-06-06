import pytest
import ast
import sys
import tempfile
import os
from pathlib import Path
from unittest.mock import MagicMock, patch, call

# Adjust import path to include the project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.pre_mutation_validator import (
    PreMutationValidator,
    MutationValidationResult,
    validate_mutation_syntax,
    validate_mutation_imports,
    generate_fallback_mutation,
    ValidationError,
    FallbackGenerationError,
)
from core.evolution_orchestrator import EvolutionOrchestrator


class TestPreMutationValidator:
    """Test suite for the PreMutationValidator class."""

    def setup_method(self):
        """Set up a fresh validator instance for each test."""
        self.validator = PreMutationValidator()
        self.validator._load_config = MagicMock(return_value={
            "strict_syntax_check": True,
            "check_imports": True,
            "fallback_enabled": True,
            "max_fallback_attempts": 3,
        })

    def test_valid_multi_module_mutation_passes(self):
        """Test that a valid mutation across multiple modules passes validation."""
        mutations = [
            {
                "file_path": "module_a.py",
                "content": "def foo():\n    return 42\n",
            },
            {
                "file_path": "module_b.py",
                "content": "from module_a import foo\n\ndef bar():\n    return foo() + 1\n",
            },
        ]

        result = self.validator.validate(mutations)
        assert result.is_valid is True
        assert result.errors == []
        assert result.warnings == []

    def test_invalid_syntax_in_one_file_fails(self):
        """Test that invalid Python syntax in any file causes validation to fail."""
        mutations = [
            {
                "file_path": "good_module.py",
                "content": "def valid_function():\n    return True\n",
            },
            {
                "file_path": "bad_module.py",
                "content": "def invalid_syntax(\n    return False\n",  # Missing closing paren
            },
        ]

        result = self.validator.validate(mutations)
        assert result.is_valid is False
        assert len(result.errors) > 0
        assert any("syntax" in error.lower() for error in result.errors)

    def test_missing_import_fails(self):
        """Test that a mutation referencing a non-existent import fails."""
        mutations = [
            {
                "file_path": "module_a.py",
                "content": "from nonexistent_library import magic_function\n\ndef use_magic():\n    return magic_function()\n",
            },
        ]

        result = self.validator.validate(mutations)
        assert result.is_valid is False
        assert len(result.errors) > 0
        assert any("import" in error.lower() for error in result.errors)

    def test_fallback_generation_produces_valid_single_file_change(self):
        """Test that fallback generation produces a valid single-file mutation when multi-module fails."""
        mutations = [
            {
                "file_path": "module_a.py",
                "content": "def helper():\n    return 100\n",
            },
            {
                "file_path": "module_b.py",
                "content": "from module_a import helper\n\ndef compute():\n    return helper() * 2\n",
            },
        ]

        # Simulate a validation failure due to missing module_a in test environment
        with patch.object(self.validator, '_check_imports', return_value=False):
            result = self.validator.validate_with_fallback(mutations)

        assert result.is_valid is True
        assert result.fallback_used is True
        assert len(result.files) == 1  # Should collapse to a single file
        # Verify the fallback content is syntactically valid
        try:
            ast.parse(result.files[0]["content"])
        except SyntaxError:
            pytest.fail("Fallback generated invalid Python syntax")

    def test_integration_with_evolution_orchestrator(self):
        """Test integration with the EvolutionOrchestrator."""
        orchestrator = EvolutionOrchestrator()
        orchestrator.pre_mutation_validator = self.validator

        # Create temporary files to simulate the module structure
        with tempfile.TemporaryDirectory() as tmpdir:
            module_a_path = os.path.join(tmpdir, "module_a.py")
            module_b_path = os.path.join(tmpdir, "module_b.py")

            # Write initial valid content
            with open(module_a_path, "w") as f:
                f.write("def existing_func():\n    return 1\n")
            with open(module_b_path, "w") as f:
                f.write("from module_a import existing_func\n\ndef other_func():\n    return existing_func() + 1\n")

            # Prepare a mutation plan
            mutation_plan = [
                {
                    "file_path": module_a_path,
                    "content": "def existing_func():\n    return 42\n",
                },
                {
                    "file_path": module_b_path,
                    "content": "from module_a import existing_func\n\ndef other_func():\n    return existing_func() * 2\n",
                },
            ]

            # Run through orchestrator's validation pipeline
            result = orchestrator.validate_mutation_plan(mutation_plan)

            assert result.is_valid is True
            assert result.errors == []

    def test_validation_result_serialization(self):
        """Test that MutationValidationResult can be properly serialized."""
        result = MutationValidationResult(
            is_valid=True,
            errors=[],
            warnings=["minor issue"],
            fallback_used=False,
            files=[{"file_path": "test.py", "content": "x = 1"}],
        )

        serialized = result.to_dict()
        assert serialized["is_valid"] is True
        assert serialized["errors"] == []
        assert serialized["warnings"] == ["minor issue"]
        assert serialized["fallback_used"] is False
        assert len(serialized["files"]) == 1

    def test_validate_mutation_syntax_function(self):
        """Test the standalone validate_mutation_syntax function."""
        valid_code = "def foo():\n    pass\n"
        invalid_code = "def foo(:\n    pass\n"

        assert validate_mutation_syntax(valid_code) is True
        assert validate_mutation_syntax(invalid_code) is False

    def test_validate_mutation_imports_function(self):
        """Test the standalone validate_mutation_imports function."""
        # Create a temporary module to import
        with tempfile.TemporaryDirectory() as tmpdir:
            sys.path.insert(0, tmpdir)
            module_path = os.path.join(tmpdir, "test_import_module.py")
            with open(module_path, "w") as f:
                f.write("TEST_CONSTANT = 42\n")

            # Test valid import
            code_valid = "from test_import_module import TEST_CONSTANT\nx = TEST_CONSTANT\n"
            assert validate_mutation_imports(code_valid, module_path) is True

            # Test invalid import
            code_invalid = "from nonexistent_module import something\nx = something\n"
            assert validate_mutation_imports(code_invalid, module_path) is False

            sys.path.remove(tmpdir)

    def test_fallback_generation_with_multiple_files(self):
        """Test fallback generation correctly merges multiple files into one."""
        mutations = [
            {"file_path": "mod1.py", "content": "def func1():\n    return 'hello'\n"},
            {"file_path": "mod2.py", "content": "def func2():\n    return 'world'\n"},
            {"file_path": "mod3.py", "content": "from mod1 import func1\nfrom mod2 import func2\n\ndef combined():\n    return func1() + ' ' + func2()\n"},
        ]

        fallback = generate_fallback_mutation(mutations)
        assert len(fallback) == 1
        assert fallback[0]["file_path"] == "mod3.py"  # Should keep the last file
        # Verify the merged content is syntactically valid
        try:
            tree = ast.parse(fallback[0]["content"])
            # Check that all functions are present in the merged output
            func_names = {node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)}
            assert "func1" in func_names
            assert "func2" in func_names
            assert "combined" in func_names
        except SyntaxError:
            pytest.fail("Fallback generated invalid Python syntax")

    def test_empty_mutation_list(self):
        """Test that an empty mutation list is handled gracefully."""
        result = self.validator.validate([])
        assert result.is_valid is True
        assert result.errors == []

    def test_validation_error_handling(self):
        """Test that ValidationError is raised appropriately."""
        with pytest.raises(ValidationError):
            self.validator._validate_syntax("def broken(:\n")

    def test_fallback_generation_error_handling(self):
        """Test that FallbackGenerationError is raised when fallback fails."""
        with pytest.raises(FallbackGenerationError):
            generate_fallback_mutation([])  # Empty list should cause error

    def test_large_mutation_set(self):
        """Test validation with a large number of mutation files."""
        mutations = []
        for i in range(100):
            mutations.append({
                "file_path": f"module_{i}.py",
                "content": f"def func_{i}():\n    return {i}\n",
            })

        result = self.validator.validate(mutations)
        assert result.is_valid is True
        assert len(result.errors) == 0

    def test_mutation_with_side_effects(self):
        """Test that mutations with side effects (print, etc.) are still valid."""
        mutations = [
            {
                "file_path": "side_effect_module.py",
                "content": "print('Loading module...')\n\ndef compute():\n    result = 42\n    print(f'Result: {result}')\n    return result\n",
            },
        ]

        result = self.validator.validate(mutations)
        assert result.is_valid is True

    def test_mutation_with_nested_imports(self):
        """Test validation of mutations with nested import dependencies."""
        mutations = [
            {
                "file_path": "base.py",
                "content": "BASE_VALUE = 10\n",
            },
            {
                "file_path": "middle.py",
                "content": "from base import BASE_VALUE\n\nMIDDLE_VALUE = BASE_VALUE * 2\n",
            },
            {
                "file_path": "top.py",
                "content": "from middle import MIDDLE_VALUE\n\nTOP_VALUE = MIDDLE_VALUE * 3\n",
            },
        ]

        result = self.validator.validate(mutations)
        assert result.is_valid is True

    def test_config_loading(self):
        """Test that configuration is properly loaded."""
        validator = PreMutationValidator()
        assert hasattr(validator, '_load_config')
        config = validator._load_config()
        assert isinstance(config, dict)

    def test_validation_with_unicode_content(self):
        """Test validation with unicode characters in mutation content."""
        mutations = [
            {
                "file_path": "unicode_module.py",
                "content": "# -*- coding: utf-8 -*-\ndef greet(name):\n    return f'Hello, {name}! 你好'\n",
            },
        ]

        result = self.validator.validate(mutations)
        assert result.is_valid is True

    def test_invalid_file_path_handling(self):
        """Test that invalid file paths are handled gracefully."""
        mutations = [
            {
                "file_path": "",  # Empty file path
                "content": "x = 1\n",
            },
        ]

        result = self.validator.validate(mutations)
        assert result.is_valid is False
        assert any("path" in error.lower() for error in result.errors)