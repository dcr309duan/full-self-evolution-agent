"""pipeline_orchestrator.py

Coordinates the full mutation -> test -> reflection -> strategy pipeline.
Integrates with broken link reporter, implements retry logic with backoff,
and provides a structured result dict with stage outputs.
"""

import time
import logging
from typing import Any, Callable, Dict, List, Optional, Tuple

from broken_link_reporter import BrokenLinkReporter

logger = logging.getLogger(__name__)


class PipelineOrchestrator:
    """Orchestrates the mutation -> test -> reflection -> strategy pipeline."""

    def __init__(
        self,
        mutation_fn: Callable[[], Any],
        test_fn: Callable[[Any], Tuple[bool, Optional[str]]],
        reflection_fn: Callable[[Any, str], Any],
        strategy_fn: Callable[[Any], Any],
        broken_link_reporter: Optional[BrokenLinkReporter] = None,
        max_retries: int = 3,
        backoff_factor: float = 2.0,
        initial_delay: float = 1.0,
        dry_run: bool = False,
    ):
        """
        Args:
            mutation_fn: Callable that returns a mutation result.
            test_fn: Callable that takes a mutation result and returns
                (success: bool, error_message: Optional[str]).
            reflection_fn: Callable that takes (mutation_result, error_message)
                and returns a reflection result.
            strategy_fn: Callable that takes a reflection result and returns
                a strategy result.
            broken_link_reporter: Optional reporter for logging broken links.
            max_retries: Maximum number of retry attempts.
            backoff_factor: Multiplier for exponential backoff.
            initial_delay: Initial delay in seconds before first retry.
            dry_run: If True, skip actual execution and log intended actions.
        """
        self.mutation_fn = mutation_fn
        self.test_fn = test_fn
        self.reflection_fn = reflection_fn
        self.strategy_fn = strategy_fn
        self.reporter = broken_link_reporter or BrokenLinkReporter()
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self.initial_delay = initial_delay
        self.dry_run = dry_run

    def run_pipeline(self) -> Dict[str, Any]:
        """Execute the full pipeline with retry logic.

        Returns:
            A structured result dict containing:
                - 'mutation_output': result from mutation stage
                - 'test_output': (success, error_message) from test stage
                - 'reflection_output': result from reflection stage
                - 'strategy_output': result from strategy stage
                - 'broken_links': list of broken links reported
                - 'retries': number of retries performed
                - 'success': overall pipeline success flag
        """
        result: Dict[str, Any] = {
            "mutation_output": None,
            "test_output": None,
            "reflection_output": None,
            "strategy_output": None,
            "broken_links": [],
            "retries": 0,
            "success": False,
        }

        if self.dry_run:
            logger.info("Dry-run mode: logging intended pipeline steps.")
            self._log_dry_run(result)
            return result

        for attempt in range(self.max_retries + 1):
            logger.info("Pipeline attempt %d/%d", attempt + 1, self.max_retries + 1)
            try:
                # Stage 1: Mutation
                mutation_output = self._run_stage("mutation", self.mutation_fn)
                result["mutation_output"] = mutation_output

                # Stage 2: Test
                test_success, test_error = self._run_stage(
                    "test", lambda: self.test_fn(mutation_output)
                )
                result["test_output"] = (test_success, test_error)

                if not test_success:
                    self._report_broken_link(
                        stage="test",
                        details=f"Test failed: {test_error}",
                    )
                    result["broken_links"].append(
                        {"stage": "test", "details": test_error}
                    )

                # Stage 3: Reflection (only if test failed)
                if not test_success:
                    reflection_output = self._run_stage(
                        "reflection",
                        lambda: self.reflection_fn(mutation_output, test_error or ""),
                    )
                    result["reflection_output"] = reflection_output
                else:
                    result["reflection_output"] = None

                # Stage 4: Strategy
                strategy_output = self._run_stage(
                    "strategy",
                    lambda: self.strategy_fn(
                        result["reflection_output"] if not test_success else None
                    ),
                )
                result["strategy_output"] = strategy_output

                # If we get here without exception, pipeline succeeded
                result["success"] = True
                logger.info("Pipeline completed successfully on attempt %d", attempt + 1)
                break

            except Exception as e:
                logger.error("Pipeline attempt %d failed: %s", attempt + 1, e)
                self._report_broken_link(
                    stage="pipeline",
                    details=f"Attempt {attempt + 1} failed: {str(e)}",
                )
                result["broken_links"].append(
                    {"stage": "pipeline", "details": str(e)}
                )

                if attempt < self.max_retries:
                    delay = self.initial_delay * (self.backoff_factor ** attempt)
                    logger.info("Retrying in %.2f seconds...", delay)
                    time.sleep(delay)
                    result["retries"] += 1
                else:
                    logger.error("Max retries reached. Pipeline failed.")
                    result["success"] = False

        # Collect any broken links from the reporter
        result["broken_links"].extend(self.reporter.get_broken_links())

        return result

    def run_with_auto_heal(self) -> Dict[str, Any]:
        """Run the pipeline with auto-healing on transient errors.

        (1) Runs the pipeline.
        (2) If any stage fails, checks if it's a transient error (timeout, resource unavailable).
        (3) Retries transient errors up to 3 times with exponential backoff.
        (4) If permanent failure, generates broken link report and stops.
        (5) Returns final pipeline status and any generated bug reports.

        Returns:
            A structured result dict containing:
                - 'mutation_output': result from mutation stage
                - 'test_output': (success, error_message) from test stage
                - 'reflection_output': result from reflection stage
                - 'strategy_output': result from strategy stage
                - 'broken_links': list of broken links reported
                - 'retries': number of retries performed
                - 'success': overall pipeline success flag
                - 'auto_heal_attempts': number of auto-heal retries performed
        """
        result: Dict[str, Any] = {
            "mutation_output": None,
            "test_output": None,
            "reflection_output": None,
            "strategy_output": None,
            "broken_links": [],
            "retries": 0,
            "success": False,
            "auto_heal_attempts": 0,
        }

        if self.dry_run:
            logger.info("Dry-run mode: logging intended pipeline steps with auto-heal.")
            self._log_dry_run(result)
            return result

        auto_heal_max_retries = 3
        auto_heal_attempts = 0

        for attempt in range(self.max_retries + 1):
            logger.info("Pipeline attempt %d/%d", attempt + 1, self.max_retries + 1)
            try:
                # Stage 1: Mutation
                mutation_output = self._run_stage("mutation", self.mutation_fn)
                result["mutation_output"] = mutation_output

                # Stage 2: Test
                test_success, test_error = self._run_stage(
                    "test", lambda: self.test_fn(mutation_output)
                )
                result["test_output"] = (test_success, test_error)

                if not test_success:
                    self._report_broken_link(
                        stage="test",
                        details=f"Test failed: {test_error}",
                    )
                    result["broken_links"].append(
                        {"stage": "test", "details": test_error}
                    )

                # Stage 3: Reflection (only if test failed)
                if not test_success:
                    reflection_output = self._run_stage(
                        "reflection",
                        lambda: self.reflection_fn(mutation_output, test_error or ""),
                    )
                    result["reflection_output"] = reflection_output
                else:
                    result["reflection_output"] = None

                # Stage 4: Strategy
                strategy_output = self._run_stage(
                    "strategy",
                    lambda: self.strategy_fn(
                        result["reflection_output"] if not test_success else None
                    ),
                )
                result["strategy_output"] = strategy_output

                # If we get here without exception, pipeline succeeded
                result["success"] = True
                logger.info("Pipeline completed successfully on attempt %d", attempt + 1)
                break

            except Exception as e:
                error_str = str(e).lower()
                is_transient = any(
                    keyword in error_str
                    for keyword in ["timeout", "resource unavailable", "temporarily unavailable", "connection refused"]
                )

                if is_transient and auto_heal_attempts < auto_heal_max_retries:
                    auto_heal_attempts += 1
                    result["auto_heal_attempts"] = auto_heal_attempts
                    delay = self.initial_delay * (self.backoff_factor ** (auto_heal_attempts - 1))
                    logger.warning(
                        "Transient error detected (attempt %d/%d): %s. Retrying in %.2f seconds...",
                        auto_heal_attempts,
                        auto_heal_max_retries,
                        e,
                        delay,
                    )
                    time.sleep(delay)
                    # Continue to next iteration of the outer loop (retry the whole pipeline)
                    continue
                else:
                    # Permanent failure or max auto-heal retries reached
                    logger.error("Permanent failure: %s", e)
                    self._report_broken_link(
                        stage="pipeline",
                        details=f"Permanent failure: {str(e)}",
                    )
                    result["broken_links"].append(
                        {"stage": "pipeline", "details": str(e)}
                    )
                    result["success"] = False
                    break

        # Collect any broken links from the reporter
        result["broken_links"].extend(self.reporter.get_broken_links())

        return result

    def _run_stage(self, stage_name: str, stage_fn: Callable[[], Any]) -> Any:
        """Execute a pipeline stage with logging.

        Args:
            stage_name: Name of the stage for logging.
            stage_fn: Callable that performs the stage logic.

        Returns:
            The result of the stage function.
        """
        logger.debug("Running stage: %s", stage_name)
        try:
            output = stage_fn()
            logger.debug("Stage '%s' completed successfully.", stage_name)
            return output
        except Exception as e:
            logger.error("Stage '%s' failed: %s", stage_name, e)
            self._report_broken_link(stage=stage_name, details=str(e))
            raise

    def _report_broken_link(self, stage: str, details: str) -> None:
        """Report a broken link via the reporter.

        Args:
            stage: The stage where the broken link occurred.
            details: Description of the broken link.
        """
        if self.reporter:
            self.reporter.report_broken_link(stage=stage, details=details)

    def _log_dry_run(self, result: Dict[str, Any]) -> None:
        """Log intended pipeline steps during dry-run mode.

        Args:
            result: The result dict to populate with dry-run info.
        """
        logger.info("[DRY RUN] Would execute mutation stage.")
        logger.info("[DRY RUN] Would execute test stage.")
        logger.info("[DRY RUN] Would execute reflection stage (if test fails).")
        logger.info("[DRY RUN] Would execute strategy stage.")
        logger.info("[DRY RUN] Would apply retry logic with max_retries=%d, backoff_factor=%.1f, initial_delay=%.1f",
                     self.max_retries, self.backoff_factor, self.initial_delay)
        logger.info("[DRY RUN] Would apply auto-heal logic with up to 3 retries for transient errors.")
        result["success"] = True  # Dry-run always succeeds
        result["dry_run"] = True


# Convenience function for quick pipeline execution
def run_pipeline(
    mutation_fn: Callable[[], Any],
    test_fn: Callable[[Any], Tuple[bool, Optional[str]]],
    reflection_fn: Callable[[Any, str], Any],
    strategy_fn: Callable[[Any], Any],
    **kwargs: Any,
) -> Dict[str, Any]:
    """Create and run a pipeline with the given functions.

    Args:
        mutation_fn: Mutation stage callable.
        test_fn: Test stage callable.
        reflection_fn: Reflection stage callable.
        strategy_fn: Strategy stage callable.
        **kwargs: Additional arguments passed to PipelineOrchestrator.

    Returns:
        Structured result dict from the pipeline.
    """
    orchestrator = PipelineOrchestrator(
        mutation_fn=mutation_fn,
        test_fn=test_fn,
        reflection_fn=reflection_fn,
        strategy_fn=strategy_fn,
        **kwargs,
    )
    return orchestrator.run_pipeline()