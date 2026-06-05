"""Pre-mutation test hook module.

Intercepts mutation requests before application, runs the full end-to-end
integration test suite, and either allows the mutation to proceed or triggers
a rollback based on test results.
"""

import logging
import sys
import traceback
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

from core.rollback_manager import RollbackManager
from core.failure_patterns import FailurePatternLogger

logger = logging.getLogger(__name__)

# Path to the integration test suite
INTEGRATION_TEST_PATH = Path("tests/test_integration.py")


class PreMutationTestHook:
    """Hook that intercepts mutations and runs integration tests before allowing them."""

    def __init__(self, rollback_manager: Optional[RollbackManager] = None,
                 failure_logger: Optional[FailurePatternLogger] = None):
        self.rollback_manager = rollback_manager or RollbackManager()
        self.failure_logger = failure_logger or FailurePatternLogger()

    def run_integration_tests(self) -> Tuple[bool, Optional[str]]:
        """Run the full end-to-end integration test suite.

        Returns:
            Tuple of (success: bool, error_message: Optional[str])
        """
        if not INTEGRATION_TEST_PATH.exists():
            logger.error("Integration test file not found: %s", INTEGRATION_TEST_PATH)
            return False, f"Integration test file not found: {INTEGRATION_TEST_PATH}"

        try:
            # Run the integration tests using pytest
            import pytest
            exit_code = pytest.main([str(INTEGRATION_TEST_PATH), "-x", "--tb=short"])

            if exit_code == 0:
                logger.info("All integration tests passed.")
                return True, None
            else:
                logger.error("Integration tests failed with exit code: %d", exit_code)
                return False, f"Integration tests failed with exit code: {exit_code}"

        except Exception as e:
            error_msg = f"Failed to run integration tests: {e}\n{traceback.format_exc()}"
            logger.error(error_msg)
            return False, error_msg

    def intercept_mutation(self, mutation_context: dict) -> bool:
        """Intercept a mutation request, run tests, and decide whether to allow it.

        Args:
            mutation_context: Dictionary containing mutation details (module, error_type, etc.)

        Returns:
            True if mutation is allowed, False if blocked and rollback triggered.
        """
        module_name = mutation_context.get("module", "unknown")
        error_type = mutation_context.get("error_type", "unknown")
        timestamp = datetime.utcnow().isoformat()

        logger.info("Intercepting mutation for module '%s' with error type '%s'", module_name, error_type)

        # Run integration tests
        tests_passed, error_message = self.run_integration_tests()

        if tests_passed:
            logger.info("Mutation allowed for module '%s'", module_name)
            return True
        else:
            # Log the failure pattern
            self.failure_logger.log_failure(
                error_type=error_type,
                module=module_name,
                timestamp=timestamp,
                details=error_message or "Integration tests failed"
            )

            # Trigger rollback
            logger.warning("Triggering rollback for module '%s' due to test failure", module_name)
            self.rollback_manager.rollback(module_name, error_type, timestamp)

            # Block the mutation
            logger.info("Mutation blocked for module '%s'", module_name)
            return False


def create_pre_mutation_hook() -> PreMutationTestHook:
    """Factory function to create a PreMutationTestHook with default dependencies."""
    rollback_manager = RollbackManager()
    failure_logger = FailurePatternLogger()
    return PreMutationTestHook(rollback_manager, failure_logger)


# Convenience function for use as a decorator or interceptor
def pre_mutation_hook(mutation_context: dict) -> bool:
    """Run the pre-mutation hook with default settings.

    Args:
        mutation_context: Dictionary with mutation details.

    Returns:
        True if mutation is allowed, False otherwise.
    """
    hook = create_pre_mutation_hook()
    return hook.intercept_mutation(mutation_context)