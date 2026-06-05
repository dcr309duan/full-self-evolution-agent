"""Evolution Orchestrator with schema alignment validation and self-consistency checks.

This module provides an orchestrator that ensures all inter-module communication
adheres to the defined schema alignment. It includes startup validation to verify
that all active modules produce schema-compliant data and logs violations as critical errors.
It also integrates self-consistency checks into the evolution loop.
"""

import logging
from typing import Any, Dict, List, Optional, Set
from dataclasses import dataclass, field
from enum import Enum

from agent_core.schema_alignment import SchemaValidator, SchemaViolation, SchemaRegistry
from agent_core.module_interface import ModuleInterface, ModuleStatus

logger = logging.getLogger(__name__)


class ValidationResult(Enum):
    """Result of a schema validation check."""
    PASS = "pass"
    FAIL = "fail"
    WARNING = "warning"


@dataclass
class ModuleValidationReport:
    """Report of schema validation for a single module."""
    module_id: str
    module_name: str
    status: ValidationResult
    violations: List[SchemaViolation] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


@dataclass
class OrchestratorValidationReport:
    """Complete validation report for the orchestrator startup."""
    overall_status: ValidationResult
    module_reports: Dict[str, ModuleValidationReport] = field(default_factory=dict)
    critical_errors: List[str] = field(default_factory=list)


class EvolutionOrchestrator:
    """Orchestrator that manages module communication with schema alignment validation."""

    def __init__(self, schema_registry: Optional[SchemaRegistry] = None):
        self._modules: Dict[str, ModuleInterface] = {}
        self._schema_validator = SchemaValidator(schema_registry or SchemaRegistry())
        self._initialized: bool = False
        self._validation_report: Optional[OrchestratorValidationReport] = None
        self._rollback_stack: List[Dict[str, Any]] = []  # Stack for rollback operations

    def register_module(self, module_id: str, module: ModuleInterface) -> None:
        """Register a module with the orchestrator.

        Args:
            module_id: Unique identifier for the module.
            module: The module interface instance.

        Raises:
            ValueError: If module_id already registered or module is invalid.
        """
        if module_id in self._modules:
            raise ValueError(f"Module '{module_id}' is already registered.")
        if not isinstance(module, ModuleInterface):
            raise ValueError(f"Module '{module_id}' must implement ModuleInterface.")

        self._modules[module_id] = module
        logger.info(f"Registered module '{module_id}' ({module.__class__.__name__})")

    def unregister_module(self, module_id: str) -> None:
        """Unregister a module from the orchestrator.

        Args:
            module_id: Unique identifier for the module to remove.
        """
        if module_id in self._modules:
            del self._modules[module_id]
            logger.info(f"Unregistered module '{module_id}'")
        else:
            logger.warning(f"Attempted to unregister non-existent module '{module_id}'")

    def get_active_modules(self) -> Dict[str, ModuleInterface]:
        """Get all currently active modules.

        Returns:
            Dictionary of module_id to ModuleInterface for active modules.
        """
        return {
            mod_id: mod
            for mod_id, mod in self._modules.items()
            if mod.get_status() == ModuleStatus.ACTIVE
        }

    def validate_module_output(self, module_id: str, data: Any, schema_name: str) -> ValidationResult:
        """Validate that a module's output conforms to the expected schema.

        Args:
            module_id: The module producing the data.
            data: The data to validate.
            schema_name: The expected schema name.

        Returns:
            ValidationResult indicating pass/fail/warning.
        """
        try:
            violations = self._schema_validator.validate(data, schema_name)
            if violations:
                for violation in violations:
                    logger.error(
                        f"Schema violation from module '{module_id}': "
                        f"Field '{violation.field}': {violation.message}"
                    )
                return ValidationResult.FAIL
            return ValidationResult.PASS
        except Exception as e:
            logger.error(f"Validation error for module '{module_id}': {str(e)}")
            return ValidationResult.WARNING

    def validate_inter_module_communication(self, source_module: str, target_module: str,
                                             data: Any, schema_name: str) -> bool:
        """Validate communication between two modules.

        Args:
            source_module: The module sending data.
            target_module: The module receiving data.
            data: The data being communicated.
            schema_name: The expected schema for this communication.

        Returns:
            True if communication is schema-compliant, False otherwise.
        """
        result = self.validate_module_output(source_module, data, schema_name)
        if result == ValidationResult.FAIL:
            logger.critical(
                f"Inter-module communication schema violation: "
                f"{source_module} -> {target_module} (schema: {schema_name})"
            )
            return False
        return True

    def perform_startup_validation(self) -> OrchestratorValidationReport:
        """Validate all active modules produce schema-compliant data.

        This method checks each active module by requesting sample output data
        and validating it against the registered schemas.

        Returns:
            OrchestratorValidationReport with detailed results.
        """
        report = OrchestratorValidationReport(overall_status=ValidationResult.PASS)
        active_modules = self.get_active_modules()

        if not active_modules:
            logger.warning("No active modules found during startup validation")
            report.overall_status = ValidationResult.WARNING
            return report

        for module_id, module in active_modules.items():
            module_report = ModuleValidationReport(
                module_id=module_id,
                module_name=module.__class__.__name__,
                status=ValidationResult.PASS
            )

            try:
                # Attempt to get sample data from the module for validation
                sample_data = module.get_sample_output()
                if sample_data is None:
                    module_report.warnings.append(
                        f"Module '{module_id}' returned no sample data for validation"
                    )
                    module_report.status = ValidationResult.WARNING
                    report.module_reports[module_id] = module_report
                    continue

                # Get the expected schema for this module's output
                schema_name = module.get_output_schema_name()
                if not schema_name:
                    module_report.warnings.append(
                        f"Module '{module_id}' has no output schema defined"
                    )
                    module_report.status = ValidationResult.WARNING
                    report.module_reports[module_id] = module_report
                    continue

                # Validate the sample data against the schema
                violations = self._schema_validator.validate(sample_data, schema_name)
                if violations:
                    module_report.violations = violations
                    module_report.status = ValidationResult.FAIL
                    for violation in violations:
                        error_msg = (
                            f"Startup validation failed for module '{module_id}': "
                            f"Schema violation in field '{violation.field}': {violation.message}"
                        )
                        logger.critical(error_msg)
                        report.critical_errors.append(error_msg)
                else:
                    logger.info(f"Module '{module_id}' passed startup schema validation")

            except Exception as e:
                error_msg = f"Error during startup validation for module '{module_id}': {str(e)}"
                logger.critical(error_msg)
                report.critical_errors.append(error_msg)
                module_report.status = ValidationResult.FAIL
                module_report.warnings.append(str(e))

            report.module_reports[module_id] = module_report

        # Determine overall status
        if report.critical_errors:
            report.overall_status = ValidationResult.FAIL
        elif any(
            mod_report.status == ValidationResult.WARNING
            for mod_report in report.module_reports.values()
        ):
            report.overall_status = ValidationResult.WARNING

        self._validation_report = report
        return report

    def initialize(self) -> bool:
        """Initialize the orchestrator with startup validation.

        Returns:
            True if initialization succeeded (all modules passed validation),
            False if critical schema violations were detected.
        """
        if self._initialized:
            logger.warning("Orchestrator already initialized")
            return True

        logger.info("Starting orchestrator initialization with schema validation")
        report = self.perform_startup_validation()

        if report.overall_status == ValidationResult.FAIL:
            logger.critical(
                f"Orchestrator initialization failed: {len(report.critical_errors)} "
                f"critical schema violations detected"
            )
            self._initialized = False
            return False

        self._initialized = True
        logger.info("Orchestrator initialized successfully with schema-compliant modules")
        return True

    def send_message(self, source_module: str, target_module: str,
                     data: Any, schema_name: str) -> bool:
        """Send a message from one module to another with schema validation.

        Args:
            source_module: The module sending the message.
            target_module: The module receiving the message.
            data: The message data.
            schema_name: The expected schema for this message.

        Returns:
            True if message was sent successfully, False if schema violation occurred.
        """
        if not self._initialized:
            logger.error("Orchestrator not initialized. Call initialize() first.")
            return False

        if source_module not in self._modules:
            logger.error(f"Source module '{source_module}' not registered")
            return False

        if target_module not in self._modules:
            logger.error(f"Target module '{target_module}' not registered")
            return False

        if not self.validate_inter_module_communication(
            source_module, target_module, data, schema_name
        ):
            return False

        try:
            target = self._modules[target_module]
            target.receive_message(source_module, data)
            logger.debug(
                f"Message sent from '{source_module}' to '{target_module}' "
                f"(schema: {schema_name})"
            )
            return True
        except Exception as e:
            logger.error(
                f"Failed to send message from '{source_module}' to '{target_module}': {str(e)}"
            )
            return False

    def get_validation_report(self) -> Optional[OrchestratorValidationReport]:
        """Get the most recent validation report.

        Returns:
            The last validation report, or None if no validation has been performed.
        """
        return self._validation_report

    def is_initialized(self) -> bool:
        """Check if the orchestrator has been initialized.

        Returns:
            True if initialized, False otherwise.
        """
        return self._initialized

    def run_self_consistency_checks(self) -> bool:
        """Run self-consistency checks on all active modules.

        This method checks that each active module's internal state is consistent
        and that its output conforms to expected schemas.

        Returns:
            True if all checks pass, False otherwise.
        """
        logger.info("Running self-consistency checks on all active modules")
        all_pass = True
        active_modules = self.get_active_modules()

        for module_id, module in active_modules.items():
            try:
                # Check module internal consistency
                if hasattr(module, 'check_consistency'):
                    if not module.check_consistency():
                        logger.error(f"Self-consistency check failed for module '{module_id}'")
                        all_pass = False
                        continue

                # Validate module output schema
                sample_data = module.get_sample_output()
                if sample_data is not None:
                    schema_name = module.get_output_schema_name()
                    if schema_name:
                        result = self.validate_module_output(module_id, sample_data, schema_name)
                        if result == ValidationResult.FAIL:
                            logger.error(
                                f"Schema validation failed during self-consistency check "
                                f"for module '{module_id}'"
                            )
                            all_pass = False
            except Exception as e:
                logger.error(
                    f"Error during self-consistency check for module '{module_id}': {str(e)}"
                )
                all_pass = False

        if all_pass:
            logger.info("All self-consistency checks passed")
        else:
            logger.warning("Some self-consistency checks failed")

        return all_pass

    def rollback_last_mutation(self) -> bool:
        """Rollback the last mutation operation.

        This method restores the state to before the last mutation was applied.

        Returns:
            True if rollback was successful, False otherwise.
        """
        if not self._rollback_stack:
            logger.warning("No mutations to rollback")
            return False

        try:
            rollback_data = self._rollback_stack.pop()
            # Restore module states from rollback data
            for module_id, state in rollback_data.items():
                if module_id in self._modules:
                    module = self._modules[module_id]
                    if hasattr(module, 'restore_state'):
                        module.restore_state(state)
                        logger.info(f"Rolled back module '{module_id}' to previous state")
                    else:
                        logger.warning(
                            f"Module '{module_id}' does not support state restoration"
                        )
            logger.info("Rollback completed successfully")
            return True
        except Exception as e:
            logger.error(f"Rollback failed: {str(e)}")
            return False

    def save_mutation_state(self) -> None:
        """Save the current state of all modules for potential rollback."""
        state_snapshot = {}
        for module_id, module in self._modules.items():
            if hasattr(module, 'get_state'):
                state_snapshot[module_id] = module.get_state()
        self._rollback_stack.append(state_snapshot)
        logger.debug("Saved mutation state for potential rollback")

    def apply_mutation(self, mutation_func, *args, **kwargs) -> bool:
        """Apply a mutation with self-consistency checks and automatic rollback.

        This method integrates the self-consistency test suite into the evolution loop.
        After each mutation is applied and before the next cycle, it calls
        run_self_consistency_checks(). If any check fails, it triggers automatic rollback
        and logs the failure with details.

        Args:
            mutation_func: The function that applies the mutation.
            *args: Arguments to pass to the mutation function.
            **kwargs: Keyword arguments to pass to the mutation function.

        Returns:
            True if mutation was applied successfully and passed consistency checks,
            False otherwise.
        """
        # Save current state before mutation
        self.save_mutation_state()

        try:
            # Apply the mutation
            logger.info("Applying mutation")
            result = mutation_func(*args, **kwargs)

            if not result:
                logger.error("Mutation function returned failure")
                self.rollback_last_mutation()
                return False

            # Run self-consistency checks after mutation
            if not self.run_self_consistency_checks():
                logger.error(
                    "Self-consistency check failed after mutation. "
                    "Triggering automatic rollback."
                )
                # Log failure details
                failed_modules = []
                for module_id, module in self.get_active_modules().items():
                    if hasattr(module, 'check_consistency'):
                        if not module.check_consistency():
                            failed_modules.append(module_id)
                logger.error(
                    f"Self-consistency failure details - failed modules: {failed_modules}"
                )
                self.rollback_last_mutation()
                return False

            logger.info("Mutation applied successfully with all consistency checks passed")
            return True

        except Exception as e:
            logger.error(f"Mutation failed with exception: {str(e)}")
            self.rollback_last_mutation()
            return False