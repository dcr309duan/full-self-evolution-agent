import unittest
from unittest.mock import patch, MagicMock
import json
import os
import sys

# Add parent directory to path to import pipeline modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from mutation_engine import MutationEngine
from testing_framework import TestingFramework
from schema_alignment import SchemaAlignment
from promotion_logic import PromotionLogic
from models import DataRecord, MutationResult, TestResult, SchemaValidationResult, PromotionResult


class TestEndToEndPipeline(unittest.TestCase):
    """Minimal end-to-end integration tests for the full data pipeline."""

    def setUp(self):
        """Set up test fixtures for all scenarios."""
        self.mutation_engine = MutationEngine()
        self.testing_framework = TestingFramework()
        self.schema_alignment = SchemaAlignment()
        self.promotion_logic = PromotionLogic()

        # Valid data record matching the expected schema
        self.valid_record = DataRecord(
            id="rec_001",
            name="Test Record",
            value=42,
            category="A",
            tags=["important", "urgent"],
            metadata={"source": "test", "version": 1}
        )

        # Record with format mismatch (wrong type for 'value' field)
        self.format_mismatch_record = DataRecord(
            id="rec_002",
            name="Mismatch Record",
            value="not_an_integer",  # Should be int
            category="B",
            tags=["mismatch"],
            metadata={"source": "test"}
        )

        # Record with partial schema compliance (missing optional field, extra field)
        self.partial_compliance_record = DataRecord(
            id="rec_003",
            name="Partial Record",
            value=100,
            category="C",
            tags=[],  # Empty but valid
            metadata={"source": "partial", "extra_field": "should_warn"}
        )

    def test_happy_path_valid_mutation_promotion_succeeds(self):
        """Happy path: valid mutation output → schema validation passes → tests pass → promotion succeeds."""
        # Step 1: Mutation Engine processes valid record
        mutation_result = self.mutation_engine.mutate(self.valid_record)
        self.assertIsNotNone(mutation_result)
        self.assertEqual(mutation_result.status, "success")
        mutated_record = mutation_result.data["mutated_record"]

        # Step 2: Schema Alignment validates the mutated record
        schema_result = self.schema_alignment.validate(mutated_record)
        self.assertTrue(schema_result.is_valid)
        self.assertEqual(len(schema_result.errors), 0)
        self.assertEqual(len(schema_result.warnings), 0)

        # Step 3: Testing Framework runs tests on the validated record
        test_result = self.testing_framework.run_tests(mutated_record)
        self.assertTrue(test_result.passed)
        self.assertEqual(test_result.failure_count, 0)

        # Step 4: Promotion Logic promotes the record
        promotion_result = self.promotion_logic.promote(mutated_record, test_result)
        self.assertTrue(promotion_result.success)
        self.assertEqual(promotion_result.status, "promoted")

    def test_format_mismatch_schema_alignment_blocks_promotion(self):
        """Format mismatch: mutation output has wrong schema version/format → schema alignment layer catches and blocks it → promotion fails with clear error."""
        # Step 1: Mutation Engine processes record with format mismatch
        mutation_result = self.mutation_engine.mutate(self.format_mismatch_record)
        self.assertIsNotNone(mutation_result)
        self.assertEqual(mutation_result.status, "success")
        mutated_record = mutation_result.data["mutated_record"]

        # Step 2: Schema Alignment should catch the format mismatch
        schema_result = self.schema_alignment.validate(mutated_record)
        self.assertFalse(schema_result.is_valid)
        self.assertGreater(len(schema_result.errors), 0)

        # Verify specific error about value field type mismatch
        value_errors = [e for e in schema_result.errors if "value" in e.field.lower()]
        self.assertGreater(len(value_errors), 0)
        self.assertIn("type", value_errors[0].message.lower())

        # Step 3: Testing Framework should not run due to invalid schema
        with self.assertRaises(ValueError) as context:
            self.testing_framework.run_tests(mutated_record)
        self.assertIn("schema validation", str(context.exception).lower())

        # Step 4: Promotion should be blocked
        with self.assertRaises(PermissionError) as context:
            self.promotion_logic.promote(mutated_record, None)
        self.assertIn("invalid schema", str(context.exception).lower())

    def test_partial_compliance_schema_alignment_warns_but_allows(self):
        """Partial compliance: mutation output has valid schema but missing optional fields → schema alignment warns but allows (configurable)."""
        # Step 1: Mutation Engine processes record with partial compliance
        mutation_result = self.mutation_engine.mutate(self.partial_compliance_record)
        self.assertIsNotNone(mutation_result)
        self.assertEqual(mutation_result.status, "success")
        mutated_record = mutation_result.data["mutated_record"]

        # Step 2: Schema Alignment should pass with warnings
        schema_result = self.schema_alignment.validate(mutated_record)
        self.assertTrue(schema_result.is_valid)  # Still valid due to optional fields
        self.assertEqual(len(schema_result.errors), 0)
        self.assertGreater(len(schema_result.warnings), 0)

        # Verify specific warnings about extra field and missing optional field
        warning_messages = [w.message for w in schema_result.warnings]
        self.assertTrue(
            any("extra_field" in msg.lower() for msg in warning_messages),
            "Expected warning about extra field"
        )
        self.assertTrue(
            any("optional" in msg.lower() for msg in warning_messages),
            "Expected warning about missing optional field"
        )

        # Step 3: Testing Framework should proceed with warnings logged
        test_result = self.testing_framework.run_tests(mutated_record, warnings=schema_result.warnings)
        self.assertTrue(test_result.passed)
        self.assertGreater(len(test_result.warnings), 0)
        self.assertEqual(test_result.warnings, schema_result.warnings)

        # Step 4: Promotion should succeed but with warning flags
        promotion_result = self.promotion_logic.promote(mutated_record, test_result, warnings=schema_result.warnings)
        self.assertTrue(promotion_result.success)
        self.assertEqual(promotion_result.status, "promoted_with_warnings")
        self.assertGreater(len(promotion_result.warnings), 0)


if __name__ == '__main__':
    unittest.main()