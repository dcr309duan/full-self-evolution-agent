from collections import defaultdict
from hashlib import sha256
from typing import Dict, List, Optional, Tuple
from enum import Enum, auto


class FailureCategory(Enum):
    AST_PARSE_ERROR = auto()
    SEMANTIC_ERROR = auto()
    TEST_FAILURE = auto()
    TIMEOUT = auto()
    DEPENDENCY_MISSING = auto()


class FailurePatternClassifier:
    """
    Classifies mutation engine failure logs into categories and maintains
    failure history per mutation target. Provides recommended strategy changes
    based on observed failure patterns.
    """

    def __init__(self):
        # History: target_module -> list of (FailureCategory, error_message)
        self._history: Dict[str, List[Tuple[FailureCategory, str]]] = defaultdict(list)

        # Thresholds for strategy change recommendations
        self._ast_error_threshold = 3
        self._semantic_error_threshold = 2
        self._timeout_threshold = 2
        self._dependency_missing_threshold = 1

    def classify_failure(self, error_log: str) -> FailureCategory:
        """
        Classify a failure log string into a FailureCategory.
        """
        log_lower = error_log.lower()

        if "parse error" in log_lower or "syntax error" in log_lower or "ast" in log_lower:
            return FailureCategory.AST_PARSE_ERROR
        elif "semantic" in log_lower or "nameerror" in log_lower or "typeerror" in log_lower:
            return FailureCategory.SEMANTIC_ERROR
        elif "test" in log_lower and "fail" in log_lower:
            return FailureCategory.TEST_FAILURE
        elif "timeout" in log_lower or "timed out" in log_lower:
            return FailureCategory.TIMEOUT
        elif "dependency" in log_lower or "module not found" in log_lower or "importerror" in log_lower:
            return FailureCategory.DEPENDENCY_MISSING
        else:
            # Default to semantic error if unknown
            return FailureCategory.SEMANTIC_ERROR

    def record_failure(self, target_module: str, error_log: str) -> None:
        """
        Record a failure for a given target module.
        """
        category = self.classify_failure(error_log)
        self._history[target_module].append((category, error_log))

    def get_failure_history(self, target_module: str) -> List[Tuple[FailureCategory, str]]:
        """
        Return the list of failures for a given target module.
        """
        return self._history.get(target_module, [])

    def compute_failure_signature(self, target_module: str) -> str:
        """
        Compute a hash-based failure signature from the error type and target module.
        """
        history = self._history.get(target_module, [])
        if not history:
            return ""

        # Concatenate all error types and target module
        raw = f"{target_module}:{'|'.join(cat.name for cat, _ in history)}"
        return sha256(raw.encode()).hexdigest()

    def get_recommended_strategy_change(self, target_module: str) -> Optional[str]:
        """
        Based on failure patterns, recommend a strategy change.
        Returns a string recommendation or None if no change needed.
        """
        history = self._history.get(target_module, [])
        if not history:
            return None

        # Count failure categories
        category_counts: Dict[FailureCategory, int] = defaultdict(int)
        for cat, _ in history:
            category_counts[cat] += 1

        # Check patterns
        if category_counts[FailureCategory.AST_PARSE_ERROR] >= self._ast_error_threshold:
            return "switch_to_wrapper_strategy"
        elif category_counts[FailureCategory.SEMANTIC_ERROR] >= self._semantic_error_threshold:
            return "switch_to_simple_mutation"
        elif category_counts[FailureCategory.TIMEOUT] >= self._timeout_threshold:
            return "increase_timeout_or_skip"
        elif category_counts[FailureCategory.DEPENDENCY_MISSING] >= self._dependency_missing_threshold:
            return "install_dependency_or_skip"
        elif category_counts[FailureCategory.TEST_FAILURE] > 0:
            return "review_test_suite_or_skip"

        return None

    def clear_history(self, target_module: Optional[str] = None) -> None:
        """
        Clear failure history for a specific target or all targets.
        """
        if target_module:
            self._history.pop(target_module, None)
        else:
            self._history.clear()