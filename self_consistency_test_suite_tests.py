import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any, List

# Import the module to be tested
from self_consistency_test_suite import SelfConsistencyTestSuite

# Test fixtures
@pytest.fixture
def mock_reflection_parser_output():
    """Fixture providing sample reflection parser output."""
    return {
        "goals": [
            {"id": "goal_1", "description": "Test goal 1", "priority": 1},
            {"id": "goal_2", "description": "Test goal 2", "priority": 2}
        ],
        "constraints": [
            {"type": "schema", "value": "test_schema_v1"}
        ],
        "mutations": [
            {"id": "mut_1", "type": "update", "target": "field_a", "value": "new_value"}
        ]
    }

@pytest.fixture
def mock_goal_generator_output():
    """Fixture providing sample goal generator output."""
    return {
        "goals": [
            {"id": "goal_1", "description": "Test goal 1", "priority": 1, "status": "active"},
            {"id": "goal_2", "description": "Test goal 2", "priority": 2, "status": "active"}
        ],
        "metadata": {
            "generated_at": "2024-01-01T00:00:00Z",
            "version": "1.0"
        }
    }

@pytest.fixture
def mock_mutation_engine_schema():
    """Fixture providing sample mutation engine input schema."""
    return {
        "type": "object",
        "properties": {
            "mutation_id": {"type": "string"},
            "mutation_type": {"type": "string", "enum": ["update", "delete", "create"]},
            "target_field": {"type": "string"},
            "new_value": {"type": "string"}
        },
        "required": ["mutation_id", "mutation_type", "target_field"]
    }

@pytest.fixture
def mock_orchestrator():
    """Fixture providing a mock orchestrator."""
    orchestrator = MagicMock()
    orchestrator.current_cycle = 5
    orchestrator.state = {"status": "running", "phase": "validation"}
    return orchestrator

@pytest.fixture
def test_suite():
    """Fixture providing a SelfConsistencyTestSuite instance."""
    return SelfConsistencyTestSuite()

# Test 1: Test case generation from reflection parser output
class TestTestCaseGeneration:
    def test_generates_test_cases_from_reflection_parser(self, test_suite, mock_reflection_parser_output):
        """Test that test cases are generated from reflection parser output."""
        test_cases = test_suite.generate_test_cases(mock_reflection_parser_output)
        
        assert len(test_cases) > 0
        assert all(hasattr(tc, 'id') for tc in test_cases)
        assert all(hasattr(tc, 'type') for tc in test_cases)
        assert all(hasattr(tc, 'expected_result') for tc in test_cases)
        assert all(hasattr(tc, 'input_data') for tc in test_cases)

    def test_generated_test_cases_contain_goals(self, test_suite, mock_reflection_parser_output):
        """Test that generated test cases include goal-related tests."""
        test_cases = test_suite.generate_test_cases(mock_reflection_parser_output)
        goal_tests = [tc for tc in test_cases if 'goal' in tc.type.lower()]
        assert len(goal_tests) > 0

    def test_generated_test_cases_contain_mutations(self, test_suite, mock_reflection_parser_output):
        """Test that generated test cases include mutation-related tests."""
        test_cases = test_suite.generate_test_cases(mock_reflection_parser_output)
        mutation_tests = [tc for tc in test_cases if 'mutation' in tc.type.lower()]
        assert len(mutation_tests) > 0

    def test_generated_test_cases_contain_constraints(self, test_suite, mock_reflection_parser_output):
        """Test that generated test cases include constraint-related tests."""
        test_cases = test_suite.generate_test_cases(mock_reflection_parser_output)
        constraint_tests = [tc for tc in test_cases if 'constraint' in tc.type.lower()]
        assert len(constraint_tests) > 0

# Test 2: Goal generator output validation against mutation engine schema
class TestGoalGeneratorValidation:
    def test_validates_goal_generator_output_against_schema(self, test_suite, mock_goal_generator_output, mock_mutation_engine_schema):
        """Test that goal generator output is validated against mutation engine schema."""
        is_valid = test_suite.validate_goal_generator_output(mock_goal_generator_output, mock_mutation_engine_schema)
        assert is_valid is True

    def test_identifies_schema_mismatch(self, test_suite, mock_mutation_engine_schema):
        """Test that schema mismatches are correctly identified."""
        invalid_output = {
            "goals": [
                {"id": "goal_1", "description": "Test goal 1"}  # Missing required fields
            ]
        }
        is_valid = test_suite.validate_goal_generator_output(invalid_output, mock_mutation_engine_schema)
        assert is_valid is False

    def test_validates_mutation_format(self, test_suite, mock_mutation_engine_schema):
        """Test that mutation format is validated against schema."""
        valid_mutation = {
            "mutation_id": "mut_1",
            "mutation_type": "update",
            "target_field": "field_a",
            "new_value": "new_value"
        }
        is_valid = test_suite.validate_mutation_format(valid_mutation, mock_mutation_engine_schema)
        assert is_valid is True

    def test_rejects_invalid_mutation_format(self, test_suite, mock_mutation_engine_schema):
        """Test that invalid mutation format is rejected."""
        invalid_mutation = {
            "mutation_id": "mut_1",
            "mutation_type": "invalid_type",  # Not in enum
            "target_field": "field_a"
        }
        is_valid = test_suite.validate_mutation_format(invalid_mutation, mock_mutation_engine_schema)
        assert is_valid is False

# Test 3: Rollback on failure
class TestRollbackOnFailure:
    def test_triggers_rollback_on_validation_failure(self, test_suite, mock_orchestrator):
        """Test that rollback is triggered when validation fails."""
        with patch.object(test_suite, 'rollback') as mock_rollback:
            test_suite.run_validation_cycle(mock_orchestrator, should_fail=True)
            mock_rollback.assert_called_once()

    def test_rollback_restores_previous_state(self, test_suite, mock_orchestrator):
        """Test that rollback restores the previous orchestrator state."""
        previous_state = {"status": "running", "phase": "generation"}
        mock_orchestrator.previous_state = previous_state
        
        test_suite.rollback(mock_orchestrator)
        assert mock_orchestrator.state == previous_state

    def test_rollback_logs_error(self, test_suite, mock_orchestrator):
        """Test that rollback logs the error appropriately."""
        with patch.object(test_suite, 'logger') as mock_logger:
            test_suite.rollback(mock_orchestrator, error_message="Validation failed")
            mock_logger.error.assert_called_once_with("Validation failed")

    def test_rollback_handles_multiple_failures(self, test_suite, mock_orchestrator):
        """Test that rollback handles multiple consecutive failures."""
        with patch.object(test_suite, 'rollback') as mock_rollback:
            for i in range(3):
                test_suite.run_validation_cycle(mock_orchestrator, should_fail=True)
            assert mock_rollback.call_count == 3

# Test 4: Valid mutations are not blocked
class TestValidMutationsNotBlocked:
    def test_does_not_block_valid_mutations(self, test_suite, mock_mutation_engine_schema):
        """Test that valid mutations are not blocked."""
        valid_mutation = {
            "mutation_id": "mut_1",
            "mutation_type": "update",
            "target_field": "field_a",
            "new_value": "new_value"
        }
        result = test_suite.validate_mutation(valid_mutation, mock_mutation_engine_schema)
        assert result["allowed"] is True
        assert "blocked" not in result

    def test_allows_valid_mutation_chain(self, test_suite, mock_mutation_engine_schema):
        """Test that a chain of valid mutations is allowed."""
        mutations = [
            {"mutation_id": f"mut_{i}", "mutation_type": "update", "target_field": f"field_{i}", "new_value": f"value_{i}"}
            for i in range(5)
        ]
        results = [test_suite.validate_mutation(m, mock_mutation_engine_schema) for m in mutations]
        assert all(r["allowed"] for r in results)

    def test_valid_mutation_passes_through(self, test_suite, mock_mutation_engine_schema):
        """Test that valid mutations pass through without modification."""
        valid_mutation = {
            "mutation_id": "mut_1",
            "mutation_type": "update",
            "target_field": "field_a",
            "new_value": "new_value"
        }
        result = test_suite.validate_mutation(valid_mutation, mock_mutation_engine_schema)
        assert result["mutation"] == valid_mutation

# Test 5: Integration with orchestrator's cycle
class TestOrchestratorIntegration:
    def test_integrates_with_orchestrator_cycle(self, test_suite, mock_orchestrator):
        """Test that the test suite integrates with the orchestrator's cycle."""
        with patch.object(test_suite, 'run_validation_cycle') as mock_validation:
            mock_orchestrator.run_cycle()
            mock_validation.assert_called_once()

    def test_validation_cycle_affects_orchestrator_state(self, test_suite, mock_orchestrator):
        """Test that validation cycle affects orchestrator state."""
        initial_state = mock_orchestrator.state.copy()
        test_suite.run_validation_cycle(mock_orchestrator)
        assert mock_orchestrator.state != initial_state

    def test_validation_cycle_updates_cycle_number(self, test_suite, mock_orchestrator):
        """Test that validation cycle updates the cycle number."""
        initial_cycle = mock_orchestrator.current_cycle
        test_suite.run_validation_cycle(mock_orchestrator)
        assert mock_orchestrator.current_cycle == initial_cycle + 1

    def test_validation_cycle_handles_orchestrator_errors(self, test_suite, mock_orchestrator):
        """Test that validation cycle handles orchestrator errors gracefully."""
        mock_orchestrator.run_cycle.side_effect = Exception("Orchestrator error")
        with patch.object(test_suite, 'rollback') as mock_rollback:
            test_suite.run_validation_cycle(mock_orchestrator)
            mock_rollback.assert_called_once()

# Test 6: Schema mismatch identification
class TestSchemaMismatchIdentification:
    def test_identifies_schema_mismatch_between_modules(self, test_suite):
        """Test that schema mismatches between modules are correctly identified."""
        module_a_schema = {
            "type": "object",
            "properties": {"field_a": {"type": "string"}}
        }
        module_b_schema = {
            "type": "object",
            "properties": {"field_b": {"type": "integer"}}
        }
        mismatches = test_suite.identify_schema_mismatches(module_a_schema, module_b_schema)
        assert len(mismatches) > 0

    def test_identifies_field_type_mismatch(self, test_suite):
        """Test that field type mismatches are identified."""
        module_a_schema = {
            "type": "object",
            "properties": {"field_a": {"type": "string"}}
        }
        module_b_schema = {
            "type": "object",
            "properties": {"field_a": {"type": "integer"}}
        }
        mismatches = test_suite.identify_schema_mismatches(module_a_schema, module_b_schema)
        type_mismatches = [m for m in mismatches if "type" in m.lower()]
        assert len(type_mismatches) > 0

    def test_identifies_required_field_mismatch(self, test_suite):
        """Test that required field mismatches are identified."""
        module_a_schema = {
            "type": "object",
            "properties": {"field_a": {"type": "string"}},
            "required": ["field_a"]
        }
        module_b_schema = {
            "type": "object",
            "properties": {"field_a": {"type": "string"}},
            "required": ["field_b"]
        }
        mismatches = test_suite.identify_schema_mismatches(module_a_schema, module_b_schema)
        required_mismatches = [m for m in mismatches if "required" in m.lower()]
        assert len(required_mismatches) > 0

    def test_identifies_enum_value_mismatch(self, test_suite):
        """Test that enum value mismatches are identified."""
        module_a_schema = {
            "type": "object",
            "properties": {"status": {"type": "string", "enum": ["active", "inactive"]}}
        }
        module_b_schema = {
            "type": "object",
            "properties": {"status": {"type": "string", "enum": ["active", "pending"]}}
        }
        mismatches = test_suite.identify_schema_mismatches(module_a_schema, module_b_schema)
        enum_mismatches = [m for m in mismatches if "enum" in m.lower()]
        assert len(enum_mismatches) > 0

    def test_returns_empty_for_matching_schemas(self, test_suite):
        """Test that matching schemas return no mismatches."""
        schema = {
            "type": "object",
            "properties": {"field_a": {"type": "string"}},
            "required": ["field_a"]
        }
        mismatches = test_suite.identify_schema_mismatches(schema, schema)
        assert len(mismatches) == 0