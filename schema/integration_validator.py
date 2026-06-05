"""Integration validator for end-to-end data flow validation.

This module validates the complete pipeline:
    reflection → goal generation → mutation → testing → self-repair

It ensures schema compatibility at each step, detects SCHEMA_MISMATCH errors early,
provides detailed diagnostics, and blocks mutations that would violate canonical schema.
"""

from __future__ import annotations

import enum
import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from schema.canonical import CanonicalSchema, SchemaField, SchemaType
from schema.goal_schema import GoalSchema
from schema.mutation_schema import MutationSchema
from schema.reflection_schema import ReflectionSchema
from schema.repair_schema import RepairSchema
from schema.test_schema import TestSchema


class ValidationSeverity(enum.Enum):
    """Severity levels for validation issues."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class ValidationStep(enum.Enum):
    """Steps in the integration pipeline."""
    REFLECTION = "reflection"
    GOAL_GENERATION = "goal_generation"
    MUTATION = "mutation"
    TESTING = "testing"
    SELF_REPAIR = "self_repair"


@dataclass
class ValidationIssue:
    """Represents a single validation issue found during integration checking."""
    step: ValidationStep
    severity: ValidationSeverity
    message: str
    source_component: str
    target_component: str
    field_path: Optional[str] = None
    expected_type: Optional[str] = None
    actual_type: Optional[str] = None
    details: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step": self.step.value,
            "severity": self.severity.value,
            "message": self.message,
            "source_component": self.source_component,
            "target_component": self.target_component,
            "field_path": self.field_path,
            "expected_type": self.expected_type,
            "actual_type": self.actual_type,
            "details": self.details or {},
        }


@dataclass
class ValidationResult:
    """Result of a complete integration validation."""
    passed: bool
    issues: List[ValidationIssue] = field(default_factory=list)
    blocked_mutations: List[str] = field(default_factory=list)
    diagnostics: Dict[str, Any] = field(default_factory=dict)

    def add_issue(self, issue: ValidationIssue) -> None:
        self.issues.append(issue)
        if issue.severity in (ValidationSeverity.ERROR, ValidationSeverity.CRITICAL):
            self.passed = False

    def merge(self, other: ValidationResult) -> None:
        self.issues.extend(other.issues)
        self.blocked_mutations.extend(other.blocked_mutations)
        self.diagnostics.update(other.diagnostics)
        if not other.passed:
            self.passed = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "passed": self.passed,
            "issues": [i.to_dict() for i in self.issues],
            "blocked_mutations": self.blocked_mutations,
            "diagnostics": self.diagnostics,
        }


class SchemaCompatibilityChecker:
    """Checks schema compatibility between two components."""

    def __init__(self, canonical_schema: CanonicalSchema):
        self.canonical = canonical_schema

    def check_field_compatibility(
        self,
        source_schema: Dict[str, Any],
        target_schema: Dict[str, Any],
        source_name: str,
        target_name: str,
        step: ValidationStep,
    ) -> ValidationResult:
        """Check that all fields in source_schema are compatible with target_schema."""
        result = ValidationResult(passed=True)

        # Check all fields in source exist in target with compatible types
        for field_name, field_def in source_schema.get("fields", {}).items():
            if field_name not in target_schema.get("fields", {}):
                issue = ValidationIssue(
                    step=step,
                    severity=ValidationSeverity.ERROR,
                    message=f"Field '{field_name}' present in {source_name} but missing in {target_name}",
                    source_component=source_name,
                    target_component=target_name,
                    field_path=field_name,
                )
                result.add_issue(issue)
                continue

            target_field = target_schema["fields"][field_name]
            if not self._types_compatible(field_def.get("type"), target_field.get("type")):
                issue = ValidationIssue(
                    step=step,
                    severity=ValidationSeverity.ERROR,
                    message=f"Type mismatch for field '{field_name}': "
                            f"expected {target_field.get('type')}, got {field_def.get('type')}",
                    source_component=source_name,
                    target_component=target_name,
                    field_path=field_name,
                    expected_type=target_field.get("type"),
                    actual_type=field_def.get("type"),
                )
                result.add_issue(issue)

        return result

    def check_canonical_compliance(
        self,
        component_schema: Dict[str, Any],
        component_name: str,
        step: ValidationStep,
    ) -> ValidationResult:
        """Check that a component schema complies with the canonical schema."""
        result = ValidationResult(passed=True)

        for field_name, field_def in component_schema.get("fields", {}).items():
            if field_name not in self.canonical.fields:
                issue = ValidationIssue(
                    step=step,
                    severity=ValidationSeverity.WARNING,
                    message=f"Field '{field_name}' in {component_name} is not defined in canonical schema",
                    source_component=component_name,
                    target_component="canonical",
                    field_path=field_name,
                )
                result.add_issue(issue)
                continue

            canonical_field = self.canonical.fields[field_name]
            if not self._types_compatible(field_def.get("type"), canonical_field.field_type.value):
                issue = ValidationIssue(
                    step=step,
                    severity=ValidationSeverity.ERROR,
                    message=f"Field '{field_name}' in {component_name} has type '{field_def.get('type')}' "
                            f"but canonical expects '{canonical_field.field_type.value}'",
                    source_component=component_name,
                    target_component="canonical",
                    field_path=field_name,
                    expected_type=canonical_field.field_type.value,
                    actual_type=field_def.get("type"),
                )
                result.add_issue(issue)

        return result

    def _types_compatible(self, type_a: Optional[str], type_b: Optional[str]) -> bool:
        """Check if two types are compatible (allowing for null/optional)."""
        if type_a is None or type_b is None:
            return True
        return type_a == type_b or type_a == "any" or type_b == "any"


class IntegrationValidator:
    """Main integration validator that checks the entire pipeline."""

    def __init__(self, canonical_schema: CanonicalSchema):
        self.canonical = canonical_schema
        self.compatibility_checker = SchemaCompatibilityChecker(canonical_schema)
        self._pipeline_state: Dict[str, Any] = {}

    def validate_reflection(self, reflection: ReflectionSchema) -> ValidationResult:
        """Validate reflection output before passing to goal generation."""
        result = ValidationResult(passed=True)

        # Check reflection schema against canonical
        reflection_schema = reflection.to_dict()
        canonical_result = self.compatibility_checker.check_canonical_compliance(
            reflection_schema, "reflection", ValidationStep.REFLECTION
        )
        result.merge(canonical_result)

        # Validate required reflection fields
        required_fields = ["system_state", "performance_metrics", "identified_issues"]
        for field in required_fields:
            if field not in reflection_schema.get("fields", {}):
                issue = ValidationIssue(
                    step=ValidationStep.REFLECTION,
                    severity=ValidationSeverity.ERROR,
                    message=f"Required field '{field}' missing from reflection output",
                    source_component="reflection",
                    target_component="goal_generation",
                    field_path=field,
                )
                result.add_issue(issue)

        self._pipeline_state["reflection"] = reflection_schema
        return result

    def validate_goal_generation(
        self, reflection: ReflectionSchema, goal: GoalSchema
    ) -> ValidationResult:
        """Validate goal generation output against reflection input."""
        result = ValidationResult(passed=True)

        # Check reflection → goal compatibility
        reflection_schema = reflection.to_dict()
        goal_schema = goal.to_dict()

        compatibility_result = self.compatibility_checker.check_field_compatibility(
            reflection_schema, goal_schema,
            "reflection", "goal_generation",
            ValidationStep.GOAL_GENERATION
        )
        result.merge(compatibility_result)

        # Check goal against canonical
        canonical_result = self.compatibility_checker.check_canonical_compliance(
            goal_schema, "goal_generation", ValidationStep.GOAL_GENERATION
        )
        result.merge(canonical_result)

        # Validate goal has required fields
        if "goals" not in goal_schema.get("fields", {}):
            issue = ValidationIssue(
                step=ValidationStep.GOAL_GENERATION,
                severity=ValidationSeverity.ERROR,
                message="Goal generation output missing 'goals' field",
                source_component="goal_generation",
                target_component="mutation",
                field_path="goals",
            )
            result.add_issue(issue)

        self._pipeline_state["goal"] = goal_schema
        return result

    def validate_mutation(
        self, goal: GoalSchema, mutation: MutationSchema
    ) -> ValidationResult:
        """Validate mutation against goal and canonical schema. Blocks invalid mutations."""
        result = ValidationResult(passed=True)

        goal_schema = goal.to_dict()
        mutation_schema = mutation.to_dict()

        # Check goal → mutation compatibility
        compatibility_result = self.compatibility_checker.check_field_compatibility(
            goal_schema, mutation_schema,
            "goal_generation", "mutation",
            ValidationStep.MUTATION
        )
        result.merge(compatibility_result)

        # Check mutation against canonical (strict check - blocks if fails)
        canonical_result = self.compatibility_checker.check_canonical_compliance(
            mutation_schema, "mutation", ValidationStep.MUTATION
        )
        result.merge(canonical_result)

        # Block mutation if it violates canonical schema
        if not canonical_result.passed:
            mutation_id = mutation_schema.get("id", "unknown")
            result.blocked_mutations.append(mutation_id)
            issue = ValidationIssue(
                step=ValidationStep.MUTATION,
                severity=ValidationSeverity.CRITICAL,
                message=f"Mutation '{mutation_id}' violates canonical schema - execution blocked",
                source_component="mutation",
                target_component="canonical",
                details={"mutation_id": mutation_id},
            )
            result.add_issue(issue)

        # Validate mutation has required fields
        required_mutation_fields = ["target_field", "new_value", "mutation_type"]
        for field in required_mutation_fields:
            if field not in mutation_schema.get("fields", {}):
                issue = ValidationIssue(
                    step=ValidationStep.MUTATION,
                    severity=ValidationSeverity.ERROR,
                    message=f"Required field '{field}' missing from mutation",
                    source_component="mutation",
                    target_component="testing",
                    field_path=field,
                )
                result.add_issue(issue)

        self._pipeline_state["mutation"] = mutation_schema
        return result

    def validate_testing(
        self, mutation: MutationSchema, test: TestSchema
    ) -> ValidationResult:
        """Validate test results against mutation expectations."""
        result = ValidationResult(passed=True)

        mutation_schema = mutation.to_dict()
        test_schema = test.to_dict()

        # Check mutation → test compatibility
        compatibility_result = self.compatibility_checker.check_field_compatibility(
            mutation_schema, test_schema,
            "mutation", "testing",
            ValidationStep.TESTING
        )
        result.merge(compatibility_result)

        # Check test against canonical
        canonical_result = self.compatibility_checker.check_canonical_compliance(
            test_schema, "testing", ValidationStep.TESTING
        )
        result.merge(canonical_result)

        # Validate test has required fields
        required_test_fields = ["test_results", "passed", "coverage"]
        for field in required_test_fields:
            if field not in test_schema.get("fields", {}):
                issue = ValidationIssue(
                    step=ValidationStep.TESTING,
                    severity=ValidationSeverity.WARNING,
                    message=f"Recommended field '{field}' missing from test output",
                    source_component="testing",
                    target_component="self_repair",
                    field_path=field,
                )
                result.add_issue(issue)

        self._pipeline_state["test"] = test_schema
        return result

    def validate_self_repair(
        self, test: TestSchema, repair: RepairSchema
    ) -> ValidationResult:
        """Validate self-repair output against test results."""
        result = ValidationResult(passed=True)

        test_schema = test.to_dict()
        repair_schema = repair.to_dict()

        # Check test → repair compatibility
        compatibility_result = self.compatibility_checker.check_field_compatibility(
            test_schema, repair_schema,
            "testing", "self_repair",
            ValidationStep.SELF_REPAIR
        )
        result.merge(compatibility_result)

        # Check repair against canonical
        canonical_result = self.compatibility_checker.check_canonical_compliance(
            repair_schema, "self_repair", ValidationStep.SELF_REPAIR
        )
        result.merge(canonical_result)

        # Validate repair has required fields
        required_repair_fields = ["repair_actions", "target_fields", "expected_outcome"]
        for field in required_repair_fields:
            if field not in repair_schema.get("fields", {}):
                issue = ValidationIssue(
                    step=ValidationStep.SELF_REPAIR,
                    severity=ValidationSeverity.ERROR,
                    message=f"Required field '{field}' missing from repair output",
                    source_component="self_repair",
                    target_component="reflection",
                    field_path=field,
                )
                result.add_issue(issue)

        self._pipeline_state["repair"] = repair_schema
        return result

    def validate_full_pipeline(
        self,
        reflection: ReflectionSchema,
        goal: GoalSchema,
        mutation: MutationSchema,
        test: TestSchema,
        repair: RepairSchema,
    ) -> ValidationResult:
        """Validate the entire pipeline end-to-end."""
        result = ValidationResult(passed=True)

        # Validate each step in order
        result.merge(self.validate_reflection(reflection))
        result.merge(self.validate_goal_generation(reflection, goal))
        result.merge(self.validate_mutation(goal, mutation))
        result.merge(self.validate_testing(mutation, test))
        result.merge(self.validate_self_repair(test, repair))

        # Generate comprehensive diagnostics
        result.diagnostics = self._generate_diagnostics(result)

        return result

    def _generate_diagnostics(self, result: ValidationResult) -> Dict[str, Any]:
        """Generate detailed diagnostics from validation results."""
        diagnostics = {
            "total_issues": len(result.issues),
            "issues_by_severity": {},
            "issues_by_step": {},
            "blocked_mutations": result.blocked_mutations,
            "pipeline_state": self._pipeline_state,
        }

        for issue in result.issues:
            severity = issue.severity.value
            if severity not in diagnostics["issues_by_severity"]:
                diagnostics["issues_by_severity"][severity] = 0
            diagnostics["issues_by_severity"][severity] += 1

            step = issue.step.value
            if step not in diagnostics["issues_by_step"]:
                diagnostics["issues_by_step"][step] = []
            diagnostics["issues_by_step"][step].append(issue.to_dict())

        return diagnostics

    def get_pipeline_state(self) -> Dict[str, Any]:
        """Get the current state of the pipeline for debugging."""
        return dict(self._pipeline_state)

    def reset_pipeline_state(self) -> None:
        """Reset the pipeline state for a new validation cycle."""
        self._pipeline_state.clear()


def create_validator(canonical_schema: Optional[CanonicalSchema] = None) -> IntegrationValidator:
    """Factory function to create an IntegrationValidator with optional canonical schema."""
    if canonical_schema is None:
        canonical_schema = CanonicalSchema()
    return IntegrationValidator(canonical_schema)


def validate_pipeline_data(
    reflection_data: Dict[str, Any],
    goal_data: Dict[str, Any],
    mutation_data: Dict[str, Any],
    test_data: Dict[str, Any],
    repair_data: Dict[str, Any],
    canonical_schema: Optional[CanonicalSchema] = None,
) -> Dict[str, Any]:
    """Convenience function to validate pipeline data from dictionaries.

    Args:
        reflection_data: Reflection output as dictionary
        goal_data: Goal generation output as dictionary
        mutation_data: Mutation output as dictionary
        test_data: Test output as dictionary
        repair_data: Repair output as dictionary
        canonical_schema: Optional canonical schema to validate against

    Returns:
        Validation result as dictionary
    """
    validator = create_validator(canonical_schema)

    reflection = ReflectionSchema.from_dict(reflection_data)
    goal = GoalSchema.from_dict(goal_data)
    mutation = MutationSchema.from_dict(mutation_data)
    test = TestSchema.from_dict(test_data)
    repair = RepairSchema.from_dict(repair_data)

    result = validator.validate_full_pipeline(reflection, goal, mutation, test, repair)
    return result.to_dict()