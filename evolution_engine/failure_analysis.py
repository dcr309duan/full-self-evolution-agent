"""Failure analysis module with enhanced context-aware root cause classification.

This module extends basic failure analysis to leverage detailed context from
FailureContextRecorder, including AST dumps and test outputs, for deeper
root cause classification and minimal reproducible example tracking.
It also supports analysis of 'blocked goal' events for dependency management.
"""

import ast
import logging
import os
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime

from evolution_engine.failure_context_recorder import FailureContextRecorder

logger = logging.getLogger(__name__)


class FailureAnalyzer:
    """Analyzes failures with context-aware root cause classification."""

    # Classification categories for root cause analysis
    ROOT_CAUSE_CATEGORIES = {
        "syntax_error": "Syntax error in generated code",
        "type_error": "Type mismatch or type-related error",
        "name_error": "Undefined variable or function name",
        "attribute_error": "Missing or invalid attribute access",
        "import_error": "Failed import or missing module",
        "index_error": "Index out of bounds",
        "key_error": "Missing dictionary key",
        "value_error": "Invalid value or argument",
        "assertion_error": "Assertion failure in tests",
        "runtime_error": "General runtime exception",
        "logical_error": "Incorrect logic producing wrong output",
        "performance_error": "Performance or timeout related failure",
        "dependency_blocked": "Goal blocked due to missing dependencies",
        "unknown": "Unclassified failure",
    }

    def __init__(self, log_dir: str = "failure_logs"):
        """Initialize the failure analyzer.

        Args:
            log_dir: Directory to store failure logs and minimal reproducible examples
        """
        self.log_dir = log_dir
        self.failure_history: List[Dict[str, Any]] = []
        self.blocked_goal_history: List[Dict[str, Any]] = []
        self._ensure_log_directory()

    def _ensure_log_directory(self) -> None:
        """Create the log directory if it doesn't exist."""
        os.makedirs(self.log_dir, exist_ok=True)

    def analyze_with_context(self, context: FailureContextRecorder) -> Dict[str, Any]:
        """Perform deep root cause analysis using detailed context.

        Args:
            context: FailureContextRecorder instance containing AST dump,
                    test output, and other context information

        Returns:
            Dictionary containing analysis results with classification,
            root cause, and minimal reproducible example path
        """
        if not context:
            raise ValueError("Context must be provided for analysis")

        # Extract context data
        ast_dump = context.get_ast_dump()
        test_output = context.get_test_output()
        error_type = context.get_error_type()
        error_message = context.get_error_message()
        code_snippet = context.get_code_snippet()

        # Perform classification
        root_cause = self._classify_root_cause(
            error_type=error_type,
            error_message=error_message,
            ast_dump=ast_dump,
            test_output=test_output,
        )

        # Generate minimal reproducible example
        mre_path = self._create_minimal_reproducible_example(
            code_snippet=code_snippet,
            error_type=error_type,
            error_message=error_message,
            root_cause=root_cause,
        )

        # Build analysis result
        analysis_result = {
            "root_cause": root_cause,
            "classification": self.ROOT_CAUSE_CATEGORIES.get(
                root_cause, self.ROOT_CAUSE_CATEGORIES["unknown"]
            ),
            "error_type": error_type,
            "error_message": error_message,
            "minimal_reproducible_example_path": mre_path,
            "ast_analysis": self._analyze_ast(ast_dump),
            "test_output_analysis": self._analyze_test_output(test_output),
            "severity": self._assess_severity(error_type, root_cause),
        }

        # Store in history
        self.failure_history.append(analysis_result)
        self._log_failure(analysis_result)

        return analysis_result

    def log_blocked_goal(self, goal: str, missing_dependencies: List[str]) -> Dict[str, Any]:
        """Log a blocked goal event with its missing dependencies and timestamp.

        Args:
            goal: The goal that was blocked
            missing_dependencies: List of dependencies that are missing

        Returns:
            Dictionary containing the blocked goal record
        """
        blocked_record = {
            "goal": goal,
            "missing_dependencies": missing_dependencies,
            "timestamp": datetime.now().isoformat(),
            "root_cause": "dependency_blocked",
            "classification": self.ROOT_CAUSE_CATEGORIES["dependency_blocked"],
        }

        self.blocked_goal_history.append(blocked_record)
        self._log_blocked_goal(blocked_record)

        logger.info(f"Logged blocked goal: {goal} with missing deps: {missing_dependencies}")
        return blocked_record

    def _log_blocked_goal(self, blocked_record: Dict[str, Any]) -> None:
        """Log blocked goal details to a structured log file.

        Args:
            blocked_record: Dictionary containing blocked goal information
        """
        try:
            log_file = os.path.join(self.log_dir, "blocked_goals.log")
            with open(log_file, "a") as f:
                f.write(f"\n{'='*60}\n")
                f.write(f"Blocked Goal Report\n")
                f.write(f"{'='*60}\n")
                f.write(f"Goal: {blocked_record['goal']}\n")
                f.write(f"Missing Dependencies: {blocked_record['missing_dependencies']}\n")
                f.write(f"Timestamp: {blocked_record['timestamp']}\n")
                f.write(f"Root Cause: {blocked_record['root_cause']}\n")
                f.write(f"Classification: {blocked_record['classification']}\n")
                f.write(f"{'='*60}\n")
        except Exception as e:
            logger.error(f"Failed to log blocked goal: {e}")

    def _classify_root_cause(
        self,
        error_type: str,
        error_message: str,
        ast_dump: Optional[str] = None,
        test_output: Optional[str] = None,
    ) -> str:
        """Classify the root cause of a failure using available context.

        Args:
            error_type: Type of error (e.g., SyntaxError, TypeError)
            error_message: The error message text
            ast_dump: AST dump string for code analysis
            test_output: Test output for behavioral analysis

        Returns:
            Root cause category string
        """
        # Direct mapping from error type
        error_type_mapping = {
            "SyntaxError": "syntax_error",
            "IndentationError": "syntax_error",
            "TabError": "syntax_error",
            "TypeError": "type_error",
            "NameError": "name_error",
            "AttributeError": "attribute_error",
            "ImportError": "import_error",
            "ModuleNotFoundError": "import_error",
            "IndexError": "index_error",
            "KeyError": "key_error",
            "ValueError": "value_error",
            "AssertionError": "assertion_error",
        }

        if error_type in error_type_mapping:
            return error_type_mapping[error_type]

        # Analyze error message for clues
        error_lower = error_message.lower() if error_message else ""

        if "timeout" in error_lower or "performance" in error_lower:
            return "performance_error"
        if "assert" in error_lower or "expected" in error_lower:
            return "assertion_error"
        if "not defined" in error_lower or "undefined" in error_lower:
            return "name_error"

        # Use AST dump for deeper analysis if available
        if ast_dump:
            try:
                ast_analysis = self._analyze_ast(ast_dump)
                if ast_analysis.get("has_syntax_issues"):
                    return "syntax_error"
                if ast_analysis.get("has_type_issues"):
                    return "type_error"
            except Exception as e:
                logger.warning(f"AST analysis failed: {e}")

        # Use test output for behavioral analysis
        if test_output:
            test_analysis = self._analyze_test_output(test_output)
            if test_analysis.get("output_mismatch"):
                return "logical_error"

        return "unknown"

    def _analyze_ast(self, ast_dump: Optional[str]) -> Dict[str, Any]:
        """Analyze AST dump for structural issues.

        Args:
            ast_dump: String representation of AST

        Returns:
            Dictionary with AST analysis results
        """
        if not ast_dump:
            return {"has_syntax_issues": False, "has_type_issues": False}

        analysis = {
            "has_syntax_issues": False,
            "has_type_issues": False,
            "complexity": "unknown",
            "node_count": 0,
        }

        try:
            # Count nodes and detect patterns
            node_count = ast_dump.count("(")
            analysis["node_count"] = node_count

            # Detect potential issues
            if "None" in ast_dump and "Return" not in ast_dump:
                analysis["has_type_issues"] = True

            # Assess complexity
            if node_count > 100:
                analysis["complexity"] = "high"
            elif node_count > 50:
                analysis["complexity"] = "medium"
            else:
                analysis["complexity"] = "low"

        except Exception as e:
            logger.error(f"Error analyzing AST: {e}")

        return analysis

    def _analyze_test_output(self, test_output: Optional[str]) -> Dict[str, Any]:
        """Analyze test output for failure patterns.

        Args:
            test_output: String output from test execution

        Returns:
            Dictionary with test output analysis
        """
        if not test_output:
            return {"output_mismatch": False, "test_failures": 0}

        analysis = {
            "output_mismatch": False,
            "test_failures": 0,
            "failure_patterns": [],
        }

        try:
            lines = test_output.split("\n")
            for line in lines:
                # Detect common test failure patterns
                if "FAIL" in line or "FAILED" in line:
                    analysis["test_failures"] += 1
                    analysis["failure_patterns"].append(line.strip())

                if "AssertionError" in line or "assert" in line:
                    analysis["output_mismatch"] = True

                if "expected" in line.lower() and "got" in line.lower():
                    analysis["output_mismatch"] = True

        except Exception as e:
            logger.error(f"Error analyzing test output: {e}")

        return analysis

    def _assess_severity(self, error_type: str, root_cause: str) -> str:
        """Assess the severity of a failure.

        Args:
            error_type: Type of error
            root_cause: Classified root cause

        Returns:
            Severity level: 'critical', 'high', 'medium', or 'low'
        """
        critical_errors = {"syntax_error", "import_error"}
        high_errors = {"type_error", "name_error", "attribute_error", "dependency_blocked"}
        medium_errors = {"index_error", "key_error", "value_error", "assertion_error"}
        low_errors = {"logical_error", "performance_error"}

        if root_cause in critical_errors:
            return "critical"
        elif root_cause in high_errors:
            return "high"
        elif root_cause in medium_errors:
            return "medium"
        elif root_cause in low_errors:
            return "low"
        else:
            return "medium"

    def _create_minimal_reproducible_example(
        self,
        code_snippet: Optional[str],
        error_type: str,
        error_message: str,
        root_cause: str,
    ) -> Optional[str]:
        """Create and save a minimal reproducible example.

        Args:
            code_snippet: The code that caused the failure
            error_type: Type of error
            error_message: Error message
            root_cause: Classified root cause

        Returns:
            Path to the saved minimal reproducible example file, or None
        """
        if not code_snippet:
            return None

        try:
            # Create filename based on error type and root cause
            safe_root_cause = root_cause.replace(" ", "_")
            filename = f"mre_{safe_root_cause}_{hash(error_message) & 0xFFFF}.py"
            filepath = os.path.join(self.log_dir, filename)

            # Write the minimal reproducible example
            with open(filepath, "w") as f:
                f.write(f"# Minimal Reproducible Example\n")
                f.write(f"# Error: {error_type}\n")
                f.write(f"# Message: {error_message}\n")
                f.write(f"# Root Cause: {root_cause}\n")
                f.write(f"# Generated by: FailureAnalyzer\n")
                f.write(f"\n")
                f.write(code_snippet)

            logger.info(f"Saved minimal reproducible example to {filepath}")
            return filepath

        except Exception as e:
            logger.error(f"Failed to create minimal reproducible example: {e}")
            return None

    def _log_failure(self, analysis_result: Dict[str, Any]) -> None:
        """Log failure details to a structured log file.

        Args:
            analysis_result: Dictionary containing analysis results
        """
        try:
            log_file = os.path.join(self.log_dir, "failure_analysis.log")
            with open(log_file, "a") as f:
                f.write(f"\n{'='*60}\n")
                f.write(f"Failure Analysis Report\n")
                f.write(f"{'='*60}\n")
                f.write(f"Root Cause: {analysis_result['root_cause']}\n")
                f.write(f"Classification: {analysis_result['classification']}\n")
                f.write(f"Error Type: {analysis_result['error_type']}\n")
                f.write(f"Error Message: {analysis_result['error_message']}\n")
                f.write(f"Severity: {analysis_result['severity']}\n")
                f.write(
                    f"MRE Path: {analysis_result.get('minimal_reproducible_example_path', 'N/A')}\n"
                )
                f.write(f"{'='*60}\n")

        except Exception as e:
            logger.error(f"Failed to log failure: {e}")

    def get_failure_statistics(self) -> Dict[str, Any]:
        """Get statistics about analyzed failures.

        Returns:
            Dictionary with failure statistics
        """
        if not self.failure_history:
            return {"total_failures": 0, "root_cause_distribution": {}}

        root_cause_counts = {}
        severity_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}

        for failure in self.failure_history:
            root_cause = failure["root_cause"]
            root_cause_counts[root_cause] = root_cause_counts.get(root_cause, 0) + 1

            severity = failure.get("severity", "medium")
            if severity in severity_counts:
                severity_counts[severity] += 1

        return {
            "total_failures": len(self.failure_history),
            "root_cause_distribution": root_cause_counts,
            "severity_distribution": severity_counts,
            "most_common_root_cause": max(
                root_cause_counts, key=root_cause_counts.get
            )
            if root_cause_counts
            else None,
        }

    def get_blocked_goal_statistics(self) -> Dict[str, Any]:
        """Get statistics about blocked goals.

        Returns:
            Dictionary with blocked goal statistics
        """
        if not self.blocked_goal_history:
            return {"total_blocked_goals": 0, "blocked_goal_distribution": {}}

        goal_counts = {}
        dependency_counts = {}

        for record in self.blocked_goal_history:
            goal = record["goal"]
            goal_counts[goal] = goal_counts.get(goal, 0) + 1

            for dep in record["missing_dependencies"]:
                dependency_counts[dep] = dependency_counts.get(dep, 0) + 1

        return {
            "total_blocked_goals": len(self.blocked_goal_history),
            "blocked_goal_distribution": goal_counts,
            "dependency_distribution": dependency_counts,
            "most_blocked_goal": max(goal_counts, key=goal_counts.get) if goal_counts else None,
            "most_missing_dependency": max(dependency_counts, key=dependency_counts.get) if dependency_counts else None,
        }

    def analyze_blocked_goal_patterns(self) -> Dict[str, Any]:
        """Analyze patterns in blocked goals to identify systemic dependency gaps.

        This method looks for repeatedly blocked goals and common missing dependencies
        that may indicate systemic issues.

        Returns:
            Dictionary with pattern analysis results
        """
        if not self.blocked_goal_history:
            return {"patterns_found": False, "message": "No blocked goals recorded"}

        # Count occurrences of each goal and dependency
        goal_counts = {}
        dependency_counts = {}
        goal_dependency_pairs = {}

        for record in self.blocked_goal_history:
            goal = record["goal"]
            goal_counts[goal] = goal_counts.get(goal, 0) + 1

            for dep in record["missing_dependencies"]:
                dependency_counts[dep] = dependency_counts.get(dep, 0) + 1
                pair_key = (goal, dep)
                goal_dependency_pairs[pair_key] = goal_dependency_pairs.get(pair_key, 0) + 1

        # Identify patterns
        patterns = []
        systemic_gaps = []

        # Check for repeatedly blocked goals (blocked more than once)
        for goal, count in goal_counts.items():
            if count > 1:
                patterns.append({
                    "type": "repeatedly_blocked_goal",
                    "goal": goal,
                    "block_count": count,
                    "severity": "high" if count > 3 else "medium",
                })

        # Check for common missing dependencies (appearing in multiple goals)
        for dep, count in dependency_counts.items():
            if count > 1:
                patterns.append({
                    "type": "common_missing_dependency",
                    "dependency": dep,
                    "occurrence_count": count,
                    "severity": "high" if count > 3 else "medium",
                })

        # Check for systemic dependency gaps (same goal-dependency pair blocked multiple times)
        for (goal, dep), count in goal_dependency_pairs.items():
            if count > 1:
                systemic_gaps.append({
                    "goal": goal,
                    "missing_dependency": dep,
                    "block_count": count,
                    "severity": "critical" if count > 3 else "high",
                })

        return {
            "patterns_found": len(patterns) > 0,
            "patterns": patterns,
            "systemic_dependency_gaps": systemic_gaps,
            "total_blocked_goals": len(self.blocked_goal_history),
            "unique_goals_blocked": len(goal_counts),
            "unique_missing_dependencies": len(dependency_counts),
        }

    def clear_history(self) -> None:
        """Clear the failure analysis history and blocked goal history."""
        self.failure_history.clear()
        self.blocked_goal_history.clear()
        logger.info("Failure analysis history and blocked goal history cleared")