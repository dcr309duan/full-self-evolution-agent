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


class MockMutationGenerator:
    """Mock mutation generator that produces test mutations with known schemas."""
    
    def __init__(self):
        self.mutations = []
        self.mutation_count = 0
    
    def generate_mutation(self, record, schema_type="standard"):
        """Generate a mock mutation with a known schema."""
        self.mutation_count += 1
        mutation = {
            "id": f"mut_{self.mutation_count}",
            "original_id": record.id,
            "schema_type": schema_type,
            "mutated_fields": {},
            "status": "success"
        }
        
        if schema_type == "standard":
            mutation["mutated_fields"] = {
                "name": record.name + "_mutated",
                "value": record.value * 2,
                "category": record.category,
                "tags": record.tags + ["mutated"],
                "metadata": {**record.metadata, "mutation_source": "mock"}
            }
        elif schema_type == "format_error":
            mutation["mutated_fields"] = {
                "name": record.name,
                "value": "not_an_integer",
                "category": record.category,
                "tags": record.tags,
                "metadata": record.metadata
            }
        elif schema_type == "partial":
            mutation["mutated_fields"] = {
                "name": record.name,
                "value": record.value,
                "category": record.category,
                "tags": record.tags,
                "metadata": {**record.metadata, "extra_field": "should_warn"}
            }
        
        self.mutations.append(mutation)
        return mutation
    
    def get_mutation_by_id(self, mutation_id):
        """Retrieve a specific mutation by ID."""
        for mutation in self.mutations:
            if mutation["id"] == mutation_id:
                return mutation
        return None
    
    def clear_mutations(self):
        """Clear all generated mutations."""
        self.mutations = []
        self.mutation_count = 0


class MockTestRunner:
    """Mock test runner that simulates test results."""
    
    def __init__(self):
        self.test_results = []
        self.test_count = 0
    
    def run_tests(self, record, warnings=None, should_pass=True):
        """Simulate running tests on a record."""
        self.test_count += 1
        
        if warnings is None:
            warnings = []
        
        if should_pass:
            result = TestResult(
                passed=True,
                test_count=5,
                failure_count=0,
                warnings=warnings,
                pipeline_stage="testing"
            )
        else:
            result = TestResult(
                passed=False,
                test_count=5,
                failure_count=2,
                warnings=warnings,
                pipeline_stage="testing"
            )
        
        self.test_results.append(result)
        return result
    
    def get_last_result(self):
        """Get the most recent test result."""
        if self.test_results:
            return self.test_results[-1]
        return None
    
    def clear_results(self):
        """Clear all test results."""
        self.test_results = []
        self.test_count = 0


class SchemaAlignmentValidator:
    """Schema alignment validator that can be configured to accept/reject based on format."""
    
    def __init__(self, accept_format="standard"):
        self.accept_format = accept_format
        self.validation_results = []
        self.validation_count = 0
    
    def validate(self, record, format_type="standard"):
        """Validate a record against a schema format."""
        self.validation_count += 1
        
        if format_type == "standard":
            result = SchemaValidationResult(
                is_valid=True,
                errors=[],
                warnings=[],
                pipeline_stage="schema_alignment"
            )
        elif format_type == "format_error":
            result = SchemaValidationResult(
                is_valid=False,
                errors=[MagicMock(field="value", message="Type mismatch: expected int, got str")],
                warnings=[],
                pipeline_stage="schema_alignment"
            )
        elif format_type == "partial":
            result = SchemaValidationResult(
                is_valid=True,
                errors=[],
                warnings=[
                    MagicMock(message="Extra field 'extra_field' found"),
                    MagicMock(message="Optional field 'description' missing")
                ],
                pipeline_stage="schema_alignment"
            )
        elif format_type == "reject_all":
            result = SchemaValidationResult(
                is_valid=False,
                errors=[MagicMock(field="id", message="Record rejected by configuration")],
                warnings=[],
                pipeline_stage="schema_alignment"
            )
        else:
            result = SchemaValidationResult(
                is_valid=self.accept_format == format_type,
                errors=[] if self.accept_format == format_type else [MagicMock(field="unknown", message="Unknown format")],
                warnings=[],
                pipeline_stage="schema_alignment"
            )
        
        self.validation_results.append(result)
        return result
    
    def set_accept_format(self, format_type):
        """Configure which format to accept."""
        self.accept_format = format_type
    
    def get_last_result(self):
        """Get the most recent validation result."""
        if self.validation_results:
            return self.validation_results[-1]
        return None
    
    def clear_results(self):
        """Clear all validation results."""
        self.validation_results = []
        self.validation_count = 0


class PromotionTracker:
    """Promotion tracker that logs whether mutations were promoted."""
    
    def __init__(self):
        self.promotion_log = []
        self.promotion_count = 0
    
    def promote(self, record, test_result, warnings=None, should_promote=True):
        """Simulate promotion and log the result."""
        self.promotion_count += 1
        
        if warnings is None:
            warnings = []
        
        if should_promote:
            if warnings:
                result = PromotionResult(
                    success=True,
                    status="promoted_with_warnings",
                    data={"promoted_record": record},
                    warnings=warnings,
                    pipeline_stage="promotion"
                )
            else:
                result = PromotionResult(
                    success=True,
                    status="promoted",
                    data={"promoted_record": record},
                    warnings=[],
                    pipeline_stage="promotion"
                )
        else:
            result = PromotionResult(
                success=False,
                status="blocked",
                data={},
                warnings=warnings,
                pipeline_stage="promotion"
            )
        
        self.promotion_log.append({
            "record_id": record.id,
            "test_passed": test_result.passed if test_result else False,
            "promoted": should_promote,
            "status": result.status,
            "warnings": warnings
        })
        
        return result
    
    def get_promotion_log(self):
        """Get the full promotion log."""
        return self.promotion_log
    
    def get_promotions_by_status(self, status):
        """Get promotions filtered by status."""
        return [entry for entry in self.promotion_log if entry["status"] == status]
    
    def clear_log(self):
        """Clear the promotion log."""
        self.promotion_log = []
        self.promotion_count = 0


class TestEndToEndPipeline(unittest.TestCase):
    """Comprehensive end-to-end integration tests for the full data pipeline."""

    def setUp(self):
        """Set up test fixtures for all scenarios."""
        self.mutation_engine = MutationEngine()
        self.testing_framework = TestingFramework()
        self.schema_alignment = SchemaAlignment()
        self.promotion_logic = PromotionLogic()
        
        # Mock helpers
        self.mock_mutation_generator = MockMutationGenerator()
        self.mock_test_runner = MockTestRunner()
        self.mock_schema_validator = SchemaAlignmentValidator()
        self.mock_promotion_tracker = PromotionTracker()

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

    def test_scenario_1_valid_pipeline(self):
        """Scenario 1: Generate mutation with correct schema format, run through test suite (simulated passing), verify schema alignment passes, verify mutation is promoted."""
        # Step 1: Generate mutation with correct schema format using mock generator
        mutation = self.mock_mutation_generator.generate_mutation(self.valid_record, "standard")
        self.assertEqual(mutation["schema_type"], "standard")
        self.assertEqual(mutation["status"], "success")
        self.assertIn("mutated_fields", mutation)
        self.assertIn("name", mutation["mutated_fields"])
        self.assertIn("value", mutation["mutated_fields"])
        
        # Convert mutation dict to DataRecord for pipeline processing
        mutated_record = DataRecord(
            id=mutation["id"],
            name=mutation["mutated_fields"]["name"],
            value=mutation["mutated_fields"]["value"],
            category=mutation["mutated_fields"]["category"],
            tags=mutation["mutated_fields"]["tags"],
            metadata=mutation["mutated_fields"]["metadata"]
        )
        
        # Step 2: Schema Alignment validates the mutated record
        schema_result = self.mock_schema_validator.validate(mutated_record, "standard")
        self.assertTrue(schema_result.is_valid)
        self.assertEqual(len(schema_result.errors), 0)
        self.assertEqual(len(schema_result.warnings), 0)
        
        # Step 3: Testing Framework runs tests (simulated passing)
        test_result = self.mock_test_runner.run_tests(mutated_record, should_pass=True)
        self.assertTrue(test_result.passed)
        self.assertEqual(test_result.failure_count, 0)
        self.assertGreater(test_result.test_count, 0)
        
        # Step 4: Promotion Logic promotes the record
        promotion_result = self.mock_promotion_tracker.promote(mutated_record, test_result, should_promote=True)
        self.assertTrue(promotion_result.success)
        self.assertEqual(promotion_result.status, "promoted")
        self.assertIn("promoted_record", promotion_result.data)
        self.assertEqual(promotion_result.data["promoted_record"].id, mutated_record.id)
        
        # Verify all stages complete without errors
        self.assertEqual(schema_result.pipeline_stage, "schema_alignment")
        self.assertEqual(test_result.pipeline_stage, "testing")
        self.assertEqual(promotion_result.pipeline_stage, "promotion")
        
        # Verify promotion log
        promotion_log = self.mock_promotion_tracker.get_promotion_log()
        self.assertEqual(len(promotion_log), 1)
        self.assertTrue(promotion_log[0]["promoted"])
        self.assertEqual(promotion_log[0]["status"], "promoted")

    def test_scenario1_successful_mutation_test_promote(self):
        """Scenario 1: Successful mutation → test → promote flow with valid data."""
        # Step 1: Mutation Engine processes valid record
        mutation_result = self.mutation_engine.mutate(self.valid_record)
        self.assertIsNotNone(mutation_result)
        self.assertEqual(mutation_result.status, "success")
        self.assertIn("mutated_record", mutation_result.data)
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
        self.assertGreater(test_result.test_count, 0)

        # Step 4: Promotion Logic promotes the record
        promotion_result = self.promotion_logic.promote(mutated_record, test_result)
        self.assertTrue(promotion_result.success)
        self.assertEqual(promotion_result.status, "promoted")
        self.assertIn("promoted_record", promotion_result.data)
        self.assertEqual(promotion_result.data["promoted_record"].id, self.valid_record.id)

        # Verify full pipeline trace
        self.assertEqual(mutation_result.data["pipeline_stage"], "mutation")
        self.assertEqual(schema_result.pipeline_stage, "schema_alignment")
        self.assertEqual(test_result.pipeline_stage, "testing")
        self.assertEqual(promotion_result.pipeline_stage, "promotion")

    def test_scenario2_mutation_with_format_mismatch(self):
        """Scenario 2: Mutation with format mismatch caught by schema alignment."""
        # Step 1: Mutation Engine processes record with format mismatch
        mutation_result = self.mutation_engine.mutate(self.format_mismatch_record)
        self.assertIsNotNone(mutation_result)
        self.assertEqual(mutation_result.status, "success")  # Mutation may still succeed
        mutated_record = mutation_result.data["mutated_record"]

        # Step 2: Schema Alignment should catch the format mismatch
        schema_result = self.schema_alignment.validate(mutated_record)
        self.assertFalse(schema_result.is_valid)
        self.assertGreater(len(schema_result.errors), 0)

        # Verify specific error about value field type mismatch
        value_errors = [e for e in schema_result.errors if "value" in e.field.lower()]
        self.assertGreater(len(value_errors), 0)
        self.assertIn("type", value_errors[0].message.lower())

        # Step 3: Testing Framework should not run (or should fail) due to invalid schema
        with self.assertRaises(ValueError) as context:
            self.testing_framework.run_tests(mutated_record)
        self.assertIn("schema validation", str(context.exception).lower())

        # Step 4: Promotion should be blocked
        with self.assertRaises(PermissionError) as context:
            self.promotion_logic.promote(mutated_record, None)
        self.assertIn("invalid schema", str(context.exception).lower())

        # Verify pipeline stops at schema alignment
        self.assertEqual(mutation_result.data["pipeline_stage"], "mutation")
        self.assertEqual(schema_result.pipeline_stage, "schema_alignment")

    def test_scenario_2_format_mismatch(self):
        """Scenario 2: Generate mutation with intentionally wrong schema format, run through schema alignment layer, verify it catches the mismatch and raises appropriate error, verify mutation is NOT promoted, verify error is logged in failure analysis format."""
        # Step 1: Generate mutation with format_error schema type using mock generator
        mutation = self.mock_mutation_generator.generate_mutation(self.valid_record, "format_error")
        self.assertEqual(mutation["schema_type"], "format_error")
        self.assertEqual(mutation["status"], "success")
        self.assertIn("mutated_fields", mutation)
        self.assertEqual(mutation["mutated_fields"]["value"], "not_an_integer")
        
        # Convert mutation dict to DataRecord for pipeline processing
        mutated_record = DataRecord(
            id=mutation["id"],
            name=mutation["mutated_fields"]["name"],
            value=mutation["mutated_fields"]["value"],
            category=mutation["mutated_fields"]["category"],
            tags=mutation["mutated_fields"]["tags"],
            metadata=mutation["mutated_fields"]["metadata"]
        )
        
        # Step 2: Schema Alignment should catch the format mismatch
        schema_result = self.mock_schema_validator.validate(mutated_record, "format_error")
        self.assertFalse(schema_result.is_valid)
        self.assertGreater(len(schema_result.errors), 0)
        
        # Verify specific error about value field type mismatch
        value_errors = [e for e in schema_result.errors if "value" in e.field.lower()]
        self.assertGreater(len(value_errors), 0)
        self.assertIn("type", value_errors[0].message.lower())
        self.assertIn("expected int", value_errors[0].message.lower())
        
        # Step 3: Verify mutation is NOT promoted
        test_result = self.mock_test_runner.run_tests(mutated_record, should_pass=False)
        self.assertFalse(test_result.passed)
        
        promotion_result = self.mock_promotion_tracker.promote(mutated_record, test_result, should_promote=False)
        self.assertFalse(promotion_result.success)
        self.assertEqual(promotion_result.status, "blocked")
        
        # Verify promotion log shows blocked status
        promotion_log = self.mock_promotion_tracker.get_promotion_log()
        self.assertEqual(len(promotion_log), 1)
        self.assertFalse(promotion_log[0]["promoted"])
        self.assertEqual(promotion_log[0]["status"], "blocked")
        
        # Step 4: Verify error is logged in failure analysis format
        failure_analysis = {
            "mutation_id": mutation["id"],
            "original_record_id": self.valid_record.id,
            "schema_type": "format_error",
            "validation_errors": [
                {
                    "field": error.field,
                    "message": error.message
                }
                for error in schema_result.errors
            ],
            "test_passed": test_result.passed,
            "promotion_status": "blocked",
            "failure_reason": "Schema validation failed: type mismatch in field 'value'"
        }
        
        # Verify failure analysis structure
        self.assertIn("mutation_id", failure_analysis)
        self.assertIn("original_record_id", failure_analysis)
        self.assertIn("schema_type", failure_analysis)
        self.assertIn("validation_errors", failure_analysis)
        self.assertIn("test_passed", failure_analysis)
        self.assertIn("promotion_status", failure_analysis)
        self.assertIn("failure_reason", failure_analysis)
        
        # Verify failure analysis content
        self.assertEqual(failure_analysis["mutation_id"], mutation["id"])
        self.assertEqual(failure_analysis["original_record_id"], self.valid_record.id)
        self.assertEqual(failure_analysis["schema_type"], "format_error")
        self.assertEqual(len(failure_analysis["validation_errors"]), 1)
        self.assertEqual(failure_analysis["validation_errors"][0]["field"], "value")
        self.assertIn("type mismatch", failure_analysis["validation_errors"][0]["message"].lower())
        self.assertFalse(failure_analysis["test_passed"])
        self.assertEqual(failure_analysis["promotion_status"], "blocked")
        self.assertIn("schema validation failed", failure_analysis["failure_reason"].lower())

    def test_scenario3_partial_schema_compliance_with_warnings(self):
        """Scenario 3: Mutation with partial schema compliance triggering validation warnings."""
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

        # Verify warnings propagate through pipeline stages
        self.assertEqual(mutation_result.data["pipeline_stage"], "mutation")
        self.assertEqual(schema_result.pipeline_stage, "schema_alignment")
        self.assertEqual(test_result.pipeline_stage, "testing")
        self.assertEqual(promotion_result.pipeline_stage, "promotion")

    def test_scenario1_edge_cases(self):
        """Additional edge cases for successful flow."""
        # Test with minimum valid data
        min_valid = DataRecord(
            id="rec_min",
            name="Minimal",
            value=0,
            category="A",
            tags=[],
            metadata={}
        )
        mutation_result = self.mutation_engine.mutate(min_valid)
        self.assertEqual(mutation_result.status, "success")
        schema_result = self.schema_alignment.validate(mutation_result.data["mutated_record"])
        self.assertTrue(schema_result.is_valid)
        test_result = self.testing_framework.run_tests(mutation_result.data["mutated_record"])
        self.assertTrue(test_result.passed)
        promotion_result = self.promotion_logic.promote(
            mutation_result.data["mutated_record"], test_result
        )
        self.assertTrue(promotion_result.success)

    def test_scenario2_multiple_format_errors(self):
        """Test schema alignment catches multiple format errors."""
        multi_error_record = DataRecord(
            id="rec_multi",
            name=123,  # Should be string
            value="invalid",  # Should be int
            category=45.6,  # Should be string
            tags="not_a_list",  # Should be list
            metadata=None  # Should be dict
        )
        mutation_result = self.mutation_engine.mutate(multi_error_record)
        schema_result = self.schema_alignment.validate(mutation_result.data["mutated_record"])
        self.assertFalse(schema_result.is_valid)
        self.assertGreaterEqual(len(schema_result.errors), 4)

    def test_scenario3_warning_propagation(self):
        """Test warnings propagate correctly through pipeline."""
        # Create record that triggers specific warnings
        warning_record = DataRecord(
            id="rec_warn",
            name="Warning Test",
            value=50,
            category="D",
            tags=["test"],
            metadata={"deprecated_field": "old_value"}
        )
        mutation_result = self.mutation_engine.mutate(warning_record)
        schema_result = self.schema_alignment.validate(mutation_result.data["mutated_record"])
        self.assertTrue(schema_result.is_valid)
        self.assertGreater(len(schema_result.warnings), 0)

        # Verify warnings are passed to testing framework
        with patch.object(self.testing_framework, 'run_tests', return_value=TestResult(
            passed=True, test_count=5, failure_count=0, warnings=schema_result.warnings
        )) as mock_test:
            test_result = self.testing_framework.run_tests(
                mutation_result.data["mutated_record"], warnings=schema_result.warnings
            )
            mock_test.assert_called_once()
            self.assertEqual(test_result.warnings, schema_result.warnings)

        # Verify warnings are passed to promotion logic
        with patch.object(self.promotion_logic, 'promote', return_value=PromotionResult(
            success=True, status="promoted_with_warnings", warnings=schema_result.warnings
        )) as mock_promote:
            promotion_result = self.promotion_logic.promote(
                mutation_result.data["mutated_record"], test_result, warnings=schema_result.warnings
            )
            mock_promote.assert_called_once()
            self.assertEqual(promotion_result.warnings, schema_result.warnings)

    def test_mock_mutation_generator_standard(self):
        """Test mock mutation generator produces standard mutations."""
        mutation = self.mock_mutation_generator.generate_mutation(self.valid_record, "standard")
        self.assertEqual(mutation["schema_type"], "standard")
        self.assertEqual(mutation["original_id"], self.valid_record.id)
        self.assertIn("mutated", mutation["mutated_fields"]["tags"])
        self.assertEqual(mutation["mutated_fields"]["value"], self.valid_record.value * 2)

    def test_mock_mutation_generator_format_error(self):
        """Test mock mutation generator produces format error mutations."""
        mutation = self.mock_mutation_generator.generate_mutation(self.valid_record, "format_error")
        self.assertEqual(mutation["schema_type"], "format_error")
        self.assertEqual(mutation["mutated_fields"]["value"], "not_an_integer")

    def test_mock_mutation_generator_partial(self):
        """Test mock mutation generator produces partial mutations."""
        mutation = self.mock_mutation_generator.generate_mutation(self.valid_record, "partial")
        self.assertEqual(mutation["schema_type"], "partial")
        self.assertIn("extra_field", mutation["mutated_fields"]["metadata"])

    def test_mock_test_runner_pass(self):
        """Test mock test runner with passing tests."""
        result = self.mock_test_runner.run_tests(self.valid_record, should_pass=True)
        self.assertTrue(result.passed)
        self.assertEqual(result.failure_count, 0)
        self.assertEqual(result.test_count, 5)

    def test_mock_test_runner_fail(self):
        """Test mock test runner with failing tests."""
        result = self.mock_test_runner.run_tests(self.valid_record, should_pass=False)
        self.assertFalse(result.passed)
        self.assertEqual(result.failure_count, 2)

    def test_mock_test_runner_with_warnings(self):
        """Test mock test runner with warnings."""
        warnings = [MagicMock(message="Test warning")]
        result = self.mock_test_runner.run_tests(self.valid_record, warnings=warnings)
        self.assertEqual(result.warnings, warnings)

    def test_schema_validator_accept_standard(self):
        """Test schema validator accepts standard format."""
        result = self.mock_schema_validator.validate(self.valid_record, "standard")
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)

    def test_schema_validator_reject_format_error(self):
        """Test schema validator rejects format errors."""
        result = self.mock_schema_validator.validate(self.valid_record, "format_error")
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)

    def test_schema_validator_partial_with_warnings(self):
        """Test schema validator returns warnings for partial compliance."""
        result = self.mock_schema_validator.validate(self.valid_record, "partial")
        self.assertTrue(result.is_valid)
        self.assertGreater(len(result.warnings), 0)

    def test_schema_validator_reject_all(self):
        """Test schema validator can be configured to reject all."""
        self.mock_schema_validator.set_accept_format("reject_all")
        result = self.mock_schema_validator.validate(self.valid_record, "standard")
        self.assertFalse(result.is_valid)

    def test_promotion_tracker_successful_promotion(self):
        """Test promotion tracker logs successful promotions."""
        test_result = self.mock_test_runner.run_tests(self.valid_record, should_pass=True)
        result = self.mock_promotion_tracker.promote(self.valid_record, test_result, should_promote=True)
        self.assertTrue(result.success)
        self.assertEqual(result.status, "promoted")
        
        log = self.mock_promotion_tracker.get_promotion_log()
        self.assertEqual(len(log), 1)
        self.assertTrue(log[0]["promoted"])

    def test_promotion_tracker_blocked_promotion(self):
        """Test promotion tracker logs blocked promotions."""
        test_result = self.mock_test_runner.run_tests(self.valid_record, should_pass=False)
        result = self.mock_promotion_tracker.promote(self.valid_record, test_result, should_promote=False)
        self.assertFalse(result.success)
        self.assertEqual(result.status, "blocked")
        
        log = self.mock_promotion_tracker.get_promotion_log()
        self.assertEqual(len(log), 1)
        self.assertFalse(log[0]["promoted"])

    def test_promotion_tracker_with_warnings(self):
        """Test promotion tracker logs promotions with warnings."""
        warnings = [MagicMock(message="Test warning")]
        test_result = self.mock_test_runner.run_tests(self.valid_record, warnings=warnings)
        result = self.mock_promotion_tracker.promote(self.valid_record, test_result, warnings=warnings, should_promote=True)
        self.assertTrue(result.success)
        self.assertEqual(result.status, "promoted_with_warnings")
        
        log = self.mock_promotion_tracker.get_promotion_log()
        self.assertEqual(len(log), 1)
        self.assertEqual(log[0]["warnings"], warnings)

    def test_promotion_tracker_filter_by_status(self):
        """Test promotion tracker can filter promotions by status."""
        test_result = self.mock_test_runner.run_tests(self.valid_record, should_pass=True)
        self.mock_promotion_tracker.promote(self.valid_record, test_result, should_promote=True)
        self.mock_promotion_tracker.promote(self.valid_record, test_result, should_promote=False)
        
        promoted = self.mock_promotion_tracker.get_promotions_by_status("promoted")
        blocked = self.mock_promotion_tracker.get_promotions_by_status("blocked")
        
        self.assertEqual(len(promoted), 1)
        self.assertEqual(len(blocked), 1)

    def test_mock_helpers_clear_methods(self):
        """Test clear methods on all mock helpers."""
        self.mock_mutation_generator.generate_mutation(self.valid_record)
        self.mock_test_runner.run_tests(self.valid_record)
        self.mock_schema_validator.validate(self.valid_record)
        self.mock_promotion_tracker.promote(self.valid_record, TestResult(passed=True, test_count=1, failure_count=0))
        
        self.mock_mutation_generator.clear_mutations()
        self.mock_test_runner.clear_results()
        self.mock_schema_validator.clear_results()
        self.mock_promotion_tracker.clear_log()
        
        self.assertEqual(len(self.mock_mutation_generator.mutations), 0)
        self.assertEqual(self.mock_test_runner.test_count, 0)
        self.assertEqual(self.mock_schema_validator.validation_count, 0)
        self.assertEqual(len(self.mock_promotion_tracker.promotion_log), 0)


if __name__ == '__main__':
    unittest.main()