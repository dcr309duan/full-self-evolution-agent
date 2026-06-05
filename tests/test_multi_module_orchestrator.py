import pytest
from unittest.mock import Mock, patch, call
from src.multi_module_orchestrator import MultiModuleOrchestrator
from src.mutation_engine import MutationEngine
from src.conflict_detector import ConflictDetector
from src.rollback_manager import RollbackManager
from src.rejection_reporter import RejectionReporter
from src.single_module_flow import SingleModuleFlow

@pytest.fixture
def mock_mutation_engine():
    return Mock(spec=MutationEngine)

@pytest.fixture
def mock_conflict_detector():
    return Mock(spec=ConflictDetector)

@pytest.fixture
def mock_rollback_manager():
    return Mock(spec=RollbackManager)

@pytest.fixture
def mock_rejection_reporter():
    return Mock(spec=RejectionReporter)

@pytest.fixture
def mock_single_module_flow():
    return Mock(spec=SingleModuleFlow)

@pytest.fixture
def orchestrator(mock_mutation_engine, mock_conflict_detector, mock_rollback_manager, mock_rejection_reporter, mock_single_module_flow):
    return MultiModuleOrchestrator(
        mutation_engine=mock_mutation_engine,
        conflict_detector=mock_conflict_detector,
        rollback_manager=mock_rollback_manager,
        rejection_reporter=mock_rejection_reporter,
        single_module_flow=mock_single_module_flow
    )

class TestMultiModuleOrchestrator:

    def test_successful_coordinated_mutation_across_3_modules(self, orchestrator, mock_mutation_engine, mock_conflict_detector):
        """Test successful coordinated mutation across 3 modules"""
        # Arrange
        modules = ["module_a", "module_b", "module_c"]
        mutations = {
            "module_a": {"func1": "new_code_1"},
            "module_b": {"func2": "new_code_2"},
            "module_c": {"func3": "new_code_3"}
        }
        mock_conflict_detector.detect_conflicts.return_value = []
        mock_mutation_engine.apply_mutation.side_effect = [
            {"status": "success", "module": "module_a"},
            {"status": "success", "module": "module_b"},
            {"status": "success", "module": "module_c"}
        ]

        # Act
        result = orchestrator.coordinate_mutations(modules, mutations)

        # Assert
        assert result["status"] == "success"
        assert result["modules_affected"] == ["module_a", "module_b", "module_c"]
        assert len(result["mutation_results"]) == 3
        mock_conflict_detector.detect_conflicts.assert_called_once_with(mutations)
        mock_mutation_engine.apply_mutation.assert_has_calls([
            call("module_a", mutations["module_a"]),
            call("module_b", mutations["module_b"]),
            call("module_c", mutations["module_c"])
        ])

    def test_conflict_detection_catches_overlapping_functions(self, orchestrator, mock_conflict_detector, mock_rejection_reporter):
        """Test conflict detection catches overlapping functions"""
        # Arrange
        modules = ["module_a", "module_b"]
        mutations = {
            "module_a": {"shared_func": "new_code_1"},
            "module_b": {"shared_func": "new_code_2"}
        }
        conflicts = [
            {"type": "overlapping_function", "function": "shared_func", "modules": ["module_a", "module_b"]}
        ]
        mock_conflict_detector.detect_conflicts.return_value = conflicts
        mock_rejection_reporter.generate_report.return_value = {"status": "rejected", "reason": "conflicts"}

        # Act
        result = orchestrator.coordinate_mutations(modules, mutations)

        # Assert
        assert result["status"] == "rejected"
        assert "conflicts" in result["reason"]
        mock_conflict_detector.detect_conflicts.assert_called_once_with(mutations)
        mock_rejection_reporter.generate_report.assert_called_once_with(conflicts, mutations)
        mock_mutation_engine.apply_mutation.assert_not_called()

    def test_rollback_on_partial_failure(self, orchestrator, mock_mutation_engine, mock_conflict_detector, mock_rollback_manager):
        """Test rollback on partial failure"""
        # Arrange
        modules = ["module_a", "module_b", "module_c"]
        mutations = {
            "module_a": {"func1": "new_code_1"},
            "module_b": {"func2": "new_code_2"},
            "module_c": {"func3": "new_code_3"}
        }
        mock_conflict_detector.detect_conflicts.return_value = []
        mock_mutation_engine.apply_mutation.side_effect = [
            {"status": "success", "module": "module_a"},
            {"status": "failure", "module": "module_b", "error": "syntax_error"},
            None  # Should not be called for module_c
        ]
        mock_rollback_manager.rollback.return_value = {"status": "rolled_back", "modules_restored": ["module_a"]}

        # Act
        result = orchestrator.coordinate_mutations(modules, mutations)

        # Assert
        assert result["status"] == "rolled_back"
        assert "module_b" in result["failed_module"]
        mock_rollback_manager.rollback.assert_called_once_with(["module_a"])
        assert mock_mutation_engine.apply_mutation.call_count == 2  # Only first two modules attempted

    def test_rejection_with_detailed_report(self, orchestrator, mock_conflict_detector, mock_rejection_reporter):
        """Test rejection with detailed report"""
        # Arrange
        modules = ["module_a", "module_b"]
        mutations = {
            "module_a": {"func1": "new_code_1"},
            "module_b": {"func2": "new_code_2"}
        }
        conflicts = [
            {"type": "dependency_issue", "function": "func1", "details": "circular_dependency"},
            {"type": "syntax_conflict", "function": "func2", "details": "invalid_syntax"}
        ]
        mock_conflict_detector.detect_conflicts.return_value = conflicts
        detailed_report = {
            "status": "rejected",
            "reason": "conflicts_found",
            "conflict_details": conflicts,
            "affected_modules": modules,
            "recommendations": ["resolve_dependency_issues", "fix_syntax_errors"]
        }
        mock_rejection_reporter.generate_report.return_value = detailed_report

        # Act
        result = orchestrator.coordinate_mutations(modules, mutations)

        # Assert
        assert result["status"] == "rejected"
        assert result["reason"] == "conflicts_found"
        assert len(result["conflict_details"]) == 2
        assert result["conflict_details"][0]["type"] == "dependency_issue"
        assert result["conflict_details"][1]["type"] == "syntax_conflict"
        mock_rejection_reporter.generate_report.assert_called_once_with(conflicts, mutations)

    def test_integration_with_existing_single_module_flow(self, orchestrator, mock_single_module_flow, mock_conflict_detector):
        """Test integration with existing single-module flow"""
        # Arrange
        modules = ["module_a"]
        mutations = {"module_a": {"func1": "new_code_1"}}
        mock_conflict_detector.detect_conflicts.return_value = []
        mock_single_module_flow.execute.return_value = {"status": "success", "module": "module_a"}

        # Act
        result = orchestrator.coordinate_mutations(modules, mutations)

        # Assert
        assert result["status"] == "success"
        mock_single_module_flow.execute.assert_called_once_with("module_a", mutations["module_a"])
        mock_conflict_detector.detect_conflicts.assert_called_once_with(mutations)

    def test_empty_modules_list(self, orchestrator):
        """Test handling of empty modules list"""
        # Arrange
        modules = []
        mutations = {}

        # Act
        result = orchestrator.coordinate_mutations(modules, mutations)

        # Assert
        assert result["status"] == "success"
        assert result["modules_affected"] == []

    def test_mutation_with_no_changes(self, orchestrator, mock_mutation_engine, mock_conflict_detector):
        """Test mutation with no actual changes"""
        # Arrange
        modules = ["module_a"]
        mutations = {"module_a": {}}
        mock_conflict_detector.detect_conflicts.return_value = []
        mock_mutation_engine.apply_mutation.return_value = {"status": "no_changes", "module": "module_a"}

        # Act
        result = orchestrator.coordinate_mutations(modules, mutations)

        # Assert
        assert result["status"] == "success"
        assert result["mutation_results"][0]["status"] == "no_changes"