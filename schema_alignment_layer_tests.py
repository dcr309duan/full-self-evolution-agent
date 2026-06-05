import json
import tempfile
import os
import pytest
from unittest.mock import Mock, patch, MagicMock
from jsonschema import validate, ValidationError
from schema_alignment_layer import (
    SchemaValidator,
    SchemaTransformer,
    AutoAdapter,
    RuntimeAlignmentEngine,
    CANONICAL_SCHEMAS,
    load_adaptation_rules,
    save_adaptation_rules
)

# ----------------------------------------------------------------------
# Fixtures
# ----------------------------------------------------------------------

@pytest.fixture
def valid_canonical_schemas():
    """Return the CANONICAL_SCHEMAS dictionary for testing."""
    return CANONICAL_SCHEMAS

@pytest.fixture
def schema_validator():
    return SchemaValidator()

@pytest.fixture
def schema_transformer():
    return SchemaTransformer()

@pytest.fixture
def auto_adapter():
    return AutoAdapter()

@pytest.fixture
def runtime_engine():
    return RuntimeAlignmentEngine()

@pytest.fixture
def temp_rules_file():
    """Create a temporary file for persistence tests."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        f.write('{}')
        f.flush()
        yield f.name
    os.unlink(f.name)

# ----------------------------------------------------------------------
# 1. Test canonical schema definitions are valid JSON Schema
# ----------------------------------------------------------------------

class TestCanonicalSchemas:
    """Verify that all canonical schema definitions are valid JSON Schema."""

    def test_all_schemas_are_valid_json_schema(self, valid_canonical_schemas):
        """Each schema must be a valid JSON Schema draft-07."""
        for schema_name, schema in valid_canonical_schemas.items():
            # Basic structural checks
            assert isinstance(schema, dict), f"Schema '{schema_name}' is not a dict"
            assert '$schema' in schema or 'type' in schema, \
                f"Schema '{schema_name}' missing $schema or type"
            # Validate using jsonschema's meta-schema
            try:
                validate(instance={}, schema=schema)  # empty instance should not raise
            except ValidationError as e:
                pytest.fail(f"Schema '{schema_name}' is invalid: {e}")

    def test_schema_contains_required_keys(self, valid_canonical_schemas):
        """Each schema should have 'type', 'properties', and 'required'."""
        for name, schema in valid_canonical_schemas.items():
            assert 'type' in schema, f"Schema '{name}' missing 'type'"
            assert 'properties' in schema, f"Schema '{name}' missing 'properties'"
            assert 'required' in schema, f"Schema '{name}' missing 'required'"

    def test_schema_properties_are_valid(self, valid_canonical_schemas):
        """Each property definition must be a valid JSON Schema fragment."""
        for name, schema in valid_canonical_schemas.items():
            for prop_name, prop_schema in schema.get('properties', {}).items():
                assert isinstance(prop_schema, dict), \
                    f"Property '{prop_name}' in schema '{name}' is not a dict"
                assert 'type' in prop_schema, \
                    f"Property '{prop_name}' in schema '{name}' missing type"

# ----------------------------------------------------------------------
# 2. Test SchemaValidator correctly identifies valid/invalid data
# ----------------------------------------------------------------------

class TestSchemaValidator:
    """Test SchemaValidator behavior."""

    def test_valid_data_passes(self, schema_validator):
        """Data conforming to schema should pass validation."""
        data = {"name": "Alice", "age": 30}
        result = schema_validator.validate(data, "person")
        assert result.is_valid is True
        assert result.errors == []

    def test_invalid_data_fails(self, schema_validator):
        """Data violating schema should fail validation."""
        data = {"name": 123, "age": "old"}  # wrong types
        result = schema_validator.validate(data, "person")
        assert result.is_valid is False
        assert len(result.errors) > 0

    def test_missing_required_field(self, schema_validator):
        """Missing required fields should cause validation failure."""
        data = {"name": "Bob"}  # missing 'age'
        result = schema_validator.validate(data, "person")
        assert result.is_valid is False
        assert any('age' in str(e) for e in result.errors)

    def test_unknown_schema_raises(self, schema_validator):
        """Using an undefined schema name should raise ValueError."""
        with pytest.raises(ValueError):
            schema_validator.validate({"x": 1}, "nonexistent")

    def test_empty_data_validation(self, schema_validator):
        """Empty data should fail if required fields missing."""
        result = schema_validator.validate({}, "person")
        assert result.is_valid is False

    def test_optional_fields_ignored(self, schema_validator):
        """Optional fields not present should not cause errors."""
        # Assume 'person' schema has optional 'email' field
        data = {"name": "Charlie", "age": 25}
        result = schema_validator.validate(data, "person")
        assert result.is_valid is True

# ----------------------------------------------------------------------
# 3. Test SchemaTransformer correctly normalizes data between formats
# ----------------------------------------------------------------------

class TestSchemaTransformer:
    """Test SchemaTransformer normalization."""

    def test_transform_to_canonical(self, schema_transformer):
        """Data should be transformed to canonical format."""
        input_data = {"full_name": "Alice", "years_old": 30}
        expected = {"name": "Alice", "age": 30}
        result = schema_transformer.transform(input_data, source_format="legacy", target_format="canonical")
        assert result == expected

    def test_transform_from_canonical(self, schema_transformer):
        """Canonical data should be transformed to legacy format."""
        input_data = {"name": "Bob", "age": 25}
        expected = {"full_name": "Bob", "years_old": 25}
        result = schema_transformer.transform(input_data, source_format="canonical", target_format="legacy")
        assert result == expected

    def test_transform_unknown_format_raises(self, schema_transformer):
        """Unknown format should raise ValueError."""
        with pytest.raises(ValueError):
            schema_transformer.transform({"a": 1}, "unknown", "canonical")

    def test_transform_preserves_extra_fields(self, schema_transformer):
        """Fields not in mapping should be preserved."""
        input_data = {"full_name": "Charlie", "years_old": 35, "extra": "keep"}
        result = schema_transformer.transform(input_data, "legacy", "canonical")
        assert "extra" in result
        assert result["extra"] == "keep"

    def test_transform_nested_structures(self, schema_transformer):
        """Nested fields should be flattened/unflattened correctly."""
        input_data = {"user": {"first": "Alice", "last": "Smith"}}
        result = schema_transformer.transform(input_data, "nested", "flat")
        assert result == {"first_name": "Alice", "last_name": "Smith"}

    def test_transform_empty_data(self, schema_transformer):
        """Empty data should remain empty after transformation."""
        result = schema_transformer.transform({}, "legacy", "canonical")
        assert result == {}

# ----------------------------------------------------------------------
# 4. Test AutoAdapter learns from mismatch patterns
# ----------------------------------------------------------------------

class TestAutoAdapter:
    """Test AutoAdapter learning and suggestion."""

    def test_learn_from_mismatch(self, auto_adapter):
        """Adapter should learn a new mapping from mismatch example."""
        mismatch = {"expected": {"name": "Alice"}, "received": {"full_name": "Alice"}}
        auto_adapter.learn(mismatch)
        assert "full_name" in auto_adapter.mappings
        assert auto_adapter.mappings["full_name"] == "name"

    def test_suggest_mapping(self, auto_adapter):
        """Adapter should suggest mapping for known pattern."""
        auto_adapter.mappings = {"full_name": "name", "years_old": "age"}
        suggestion = auto_adapter.suggest({"full_name": "Bob", "years_old": 30})
        assert suggestion == {"name": "Bob", "age": 30}

    def test_learn_from_multiple_mismatches(self, auto_adapter):
        """Adapter should accumulate mappings from multiple examples."""
        mismatches = [
            {"expected": {"name": "A"}, "received": {"full_name": "A"}},
            {"expected": {"age": 1}, "received": {"years_old": 1}}
        ]
        for m in mismatches:
            auto_adapter.learn(m)
        assert len(auto_adapter.mappings) == 2

    def test_learn_ignores_known_mappings(self, auto_adapter):
        """Already known mappings should not be overwritten."""
        auto_adapter.mappings = {"full_name": "name"}
        auto_adapter.learn({"expected": {"name": "A"}, "received": {"full_name": "A"}})
        assert auto_adapter.mappings["full_name"] == "name"  # unchanged

    def test_suggest_empty_data(self, auto_adapter):
        """Empty data should return empty suggestion."""
        suggestion = auto_adapter.suggest({})
        assert suggestion == {}

    def test_suggest_no_mapping(self, auto_adapter):
        """Data with no known mappings should return empty suggestion."""
        suggestion = auto_adapter.suggest({"unknown_field": 1})
        assert suggestion == {}

# ----------------------------------------------------------------------
# 5. Test RuntimeAlignmentEngine orchestrates validation across modules
# ----------------------------------------------------------------------

class TestRuntimeAlignmentEngine:
    """Test RuntimeAlignmentEngine integration."""

    def test_validate_and_transform(self, runtime_engine):
        """Engine should validate then transform data."""
        data = {"full_name": "Alice", "years_old": 30}
        result = runtime_engine.process(data, source_format="legacy", target_schema="person")
        assert result.is_valid is True
        assert result.transformed_data == {"name": "Alice", "age": 30}

    def test_invalid_data_rejected(self, runtime_engine):
        """Invalid data should be rejected with errors."""
        data = {"full_name": 123, "years_old": "old"}
        result = runtime_engine.process(data, source_format="legacy", target_schema="person")
        assert result.is_valid is False
        assert len(result.errors) > 0

    def test_auto_adaptation_triggered(self, runtime_engine):
        """Engine should trigger auto-adaptation on mismatch."""
        # Simulate a mismatch that AutoAdapter can learn from
        data = {"full_name": "Bob"}
        result = runtime_engine.process(data, source_format="legacy", target_schema="person")
        # After processing, engine should have learned mapping
        assert "full_name" in runtime_engine.adapter.mappings

    def test_persistence_invoked(self, runtime_engine, temp_rules_file):
        """Engine should call save/load rules when configured."""
        runtime_engine.rules_file = temp_rules_file
        runtime_engine.process({"name": "Alice"}, source_format="canonical", target_schema="person")
        # Check that rules file was written
        with open(temp_rules_file, 'r') as f:
            content = f.read()
        assert len(content) > 0

    def test_engine_handles_empty_data(self, runtime_engine):
        """Empty data should be processed without error."""
        result = runtime_engine.process({}, source_format="legacy", target_schema="person")
        assert result.is_valid is False  # missing required fields

    def test_engine_handles_nested_structures(self, runtime_engine):
        """Nested data should be flattened correctly."""
        data = {"user": {"first": "Alice", "last": "Smith"}}
        result = runtime_engine.process(data, source_format="nested", target_schema="person")
        assert result.is_valid is True
        assert result.transformed_data.get("first_name") == "Alice"

# ----------------------------------------------------------------------
# 6. Test persistence of adaptation rules
# ----------------------------------------------------------------------

class TestPersistence:
    """Test save/load of adaptation rules."""

    def test_save_and_load_rules(self, temp_rules_file):
        """Rules should be saved and loaded correctly."""
        rules = {"full_name": "name", "years_old": "age"}
        save_adaptation_rules(rules, temp_rules_file)
        loaded = load_adaptation_rules(temp_rules_file)
        assert loaded == rules

    def test_load_empty_file(self, temp_rules_file):
        """Empty file should return empty dict."""
        with open(temp_rules_file, 'w') as f:
            f.write('')
        loaded = load_adaptation_rules(temp_rules_file)
        assert loaded == {}

    def test_load_corrupted_file(self, temp_rules_file):
        """Corrupted file should raise exception."""
        with open(temp_rules_file, 'w') as f:
            f.write('not json')
        with pytest.raises(json.JSONDecodeError):
            load_adaptation_rules(temp_rules_file)

    def test_save_overwrites_existing(self, temp_rules_file):
        """Saving new rules should overwrite old ones."""
        save_adaptation_rules({"a": "b"}, temp_rules_file)
        save_adaptation_rules({"c": "d"}, temp_rules_file)
        loaded = load_adaptation_rules(temp_rules_file)
        assert loaded == {"c": "d"}

# ----------------------------------------------------------------------
# 7. Test edge cases (empty data, nested structures, optional fields)
# ----------------------------------------------------------------------

class TestEdgeCases:
    """Test edge cases across all components."""

    def test_empty_data_validation(self, schema_validator):
        """Empty data should fail validation if required fields missing."""
        result = schema_validator.validate({}, "person")
        assert result.is_valid is False

    def test_empty_data_transformation(self, schema_transformer):
        """Empty data should remain empty after transformation."""
        result = schema_transformer.transform({}, "legacy", "canonical")
        assert result == {}

    def test_nested_structure_validation(self, schema_validator):
        """Nested data should be validated correctly."""
        data = {"address": {"city": "NYC", "zip": 10001}}
        result = schema_validator.validate(data, "address")
        assert result.is_valid is True

    def test_nested_structure_transformation(self, schema_transformer):
        """Nested data should be transformed correctly."""
        data = {"address": {"city": "NYC", "zip": 10001}}
        result = schema_transformer.transform(data, "nested", "flat")
        assert "city" in result

    def test_optional_fields_validation(self, schema_validator):
        """Optional fields not present should not cause errors."""
        # Assume 'person' schema has optional 'email' field
        data = {"name": "Alice", "age": 30}
        result = schema_validator.validate(data, "person")
        assert result.is_valid is True

    def test_optional_fields_transformation(self, schema_transformer):
        """Optional fields should be preserved if present."""
        data = {"name": "Alice", "email": "alice@example.com"}
        result = schema_transformer.transform(data, "canonical", "legacy")
        assert "email" in result

    def test_all_optional_fields_missing(self, schema_validator):
        """Data with only optional fields missing should still pass."""
        data = {"name": "Bob", "age": 25}
        result = schema_validator.validate(data, "person")
        assert result.is_valid is True

    def test_extra_fields_in_data(self, schema_validator):
        """Extra fields not in schema should be ignored (not cause errors)."""
        data = {"name": "Alice", "age": 30, "extra": "ignored"}
        result = schema_validator.validate(data, "person")
        assert result.is_valid is True

    def test_extra_fields_in_transformation(self, schema_transformer):
        """Extra fields should be preserved during transformation."""
        data = {"full_name": "Alice", "extra": "keep"}
        result = schema_transformer.transform(data, "legacy", "canonical")
        assert "extra" in result