import ast
import json
import os
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from core.pre_mutation_guard import PreMutationGuard
from core.mutation_quality_gate import MutationQualityGate


class MutationPipeline:
    """
    Orchestrates the mutation process with pre-mutation validation.
    Before any mutation is applied, the pipeline validates the proposal.
    If validation fails, the mutation is aborted and a structured error
    record is appended to the failure log.
    """

    def __init__(
        self,
        failure_log_path: str = "logs/failure_log.jsonl",
        guard: Optional[PreMutationGuard] = None,
        quality_gate: Optional[MutationQualityGate] = None,
    ):
        self.failure_log_path = failure_log_path
        self.guard = guard or PreMutationGuard()
        self.quality_gate = quality_gate or MutationQualityGate()
        self._ensure_failure_log_directory()

    def _ensure_failure_log_directory(self) -> None:
        """Ensure the directory for the failure log exists."""
        log_dir = os.path.dirname(self.failure_log_path)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)

    def _append_failure_record(self, record: Dict[str, Any]) -> None:
        """Append a structured error record to the failure log file."""
        with open(self.failure_log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")

    def _build_failure_record(
        self,
        error_type: str,
        file_path: str,
        line: int,
        mutation_id: str,
        details: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Build a structured failure record."""
        return {
            "error_type": error_type,
            "file": file_path,
            "line": line,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "mutation_id": mutation_id,
            "details": details or "",
        }

    def validate_and_mutate(
        self,
        file_path: str,
        mutation_proposal: Dict[str, Any],
        source_code: str,
    ) -> Optional[str]:
        """
        Validate a mutation proposal and, if valid, apply it.

        Args:
            file_path: Path to the source file being mutated.
            mutation_proposal: A dictionary describing the mutation.
                Expected keys: 'type', 'target_line', 'original_code', 'mutated_code'.
            source_code: The current source code content.

        Returns:
            The mutated source code if validation passes, or None if aborted.
        """
        mutation_id = str(uuid.uuid4())
        target_line = mutation_proposal.get("target_line", 0)

        # Step 1: Pre-mutation validation
        validation_result = self.guard.validate(mutation_proposal)
        if not validation_result.is_valid:
            record = self._build_failure_record(
                error_type="pre_mutation_validation_failed",
                file_path=file_path,
                line=target_line,
                mutation_id=mutation_id,
                details=validation_result.error_message,
            )
            self._append_failure_record(record)
            return None

        # Step 2: Quality gate check
        quality_result = self.quality_gate.evaluate(
            mutation_proposal, source_code
        )
        if not quality_result.passed:
            record = self._build_failure_record(
                error_type="quality_gate_failed",
                file_path=file_path,
                line=target_line,
                mutation_id=mutation_id,
                details=quality_result.reason,
            )
            self._append_failure_record(record)
            return None

        # Step 3: Apply the mutation
        try:
            mutated_code = self._apply_mutation(
                source_code, mutation_proposal
            )
            return mutated_code
        except Exception as e:
            record = self._build_failure_record(
                error_type="mutation_application_error",
                file_path=file_path,
                line=target_line,
                mutation_id=mutation_id,
                details=str(e),
            )
            self._append_failure_record(record)
            return None

    def _apply_mutation(
        self, source_code: str, mutation_proposal: Dict[str, Any]
    ) -> str:
        """
        Apply a mutation to the source code.

        This is a simple line-replacement strategy. More complex mutations
        can be implemented by overriding this method or extending the class.

        Args:
            source_code: The original source code.
            mutation_proposal: Contains 'target_line' and 'mutated_code'.

        Returns:
            The mutated source code as a string.
        """
        lines = source_code.splitlines(keepends=True)
        target_line = mutation_proposal.get("target_line", 0)
        mutated_code = mutation_proposal.get("mutated_code", "")

        if target_line < 0 or target_line >= len(lines):
            raise IndexError(
                f"Target line {target_line} is out of range "
                f"(file has {len(lines)} lines)."
            )

        lines[target_line] = mutated_code + "\n"
        return "".join(lines)

    def validate_syntax(self, code: str) -> bool:
        """
        Validate that the given code has valid Python syntax.

        Args:
            code: Python source code string.

        Returns:
            True if syntax is valid, False otherwise.
        """
        try:
            ast.parse(code)
            return True
        except SyntaxError:
            return False